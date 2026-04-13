"""Bloom filter for fast duplicate pre-check in brain.store().

A Bloom filter is a probabilistic set-membership structure. It can tell us
with certainty that an item is NOT in the set (no false negatives), and with
high probability that an item IS in the set (tunable false-positive rate).

Usage in brain.store():
  - Before the expensive ChromaDB L2-distance dedup query, check the bloom
    filter.  If the text is definitely not in the filter, skip the query
    entirely (guaranteed no duplicate).
  - If the filter says "maybe present", proceed with the ChromaDB query as
    before (the filter may have a false positive).

The filter is keyed on normalized text content, not embeddings — this catches
exact and near-exact textual duplicates cheaply.  Semantic duplicates (different
wording, same meaning) still rely on the ChromaDB L2 path.

Persistence: the filter state is saved to disk so it survives restarts.
It is rebuilt from scratch periodically or when the false-positive rate
drifts above threshold.
"""

import hashlib
import json
import logging
import math
import os
import struct
import time
from pathlib import Path

_log = logging.getLogger("clarvis.brain.bloom_filter")

# ---------------------------------------------------------------------------
# Bit-array backed by a mutable bytearray
# ---------------------------------------------------------------------------

class _BitArray:
    """Compact bit array backed by a bytearray."""

    __slots__ = ("_size", "_array")

    def __init__(self, size: int):
        self._size = size
        self._array = bytearray((size + 7) // 8)

    def set(self, idx: int) -> None:
        self._array[idx >> 3] |= 1 << (idx & 7)

    def get(self, idx: int) -> bool:
        return bool(self._array[idx >> 3] & (1 << (idx & 7)))

    def to_bytes(self) -> bytes:
        return bytes(self._array)

    @classmethod
    def from_bytes(cls, data: bytes, size: int) -> "_BitArray":
        ba = cls.__new__(cls)
        ba._size = size
        ba._array = bytearray(data)
        return ba

    @property
    def size(self) -> int:
        return self._size

    def count_ones(self) -> int:
        return sum(bin(b).count("1") for b in self._array)


# ---------------------------------------------------------------------------
# Bloom filter
# ---------------------------------------------------------------------------

def _optimal_params(expected_items: int, fp_rate: float):
    """Compute optimal bit-array size (m) and hash count (k)."""
    if expected_items <= 0:
        expected_items = 1
    m = -expected_items * math.log(fp_rate) / (math.log(2) ** 2)
    m = int(math.ceil(m))
    k = max(1, int(round((m / expected_items) * math.log(2))))
    return m, k


def _hash_indices(text: str, m: int, k: int) -> list[int]:
    """Generate k bit positions using double-hashing (Kirschner & Mitzenmacher)."""
    # Two independent 64-bit hashes from MD5 (128 bit)
    digest = hashlib.md5(text.encode("utf-8", errors="replace")).digest()
    h1, h2 = struct.unpack_from("<QQ", digest)
    return [(h1 + i * h2) % m for i in range(k)]


def _normalize(text: str) -> str:
    """Normalize text for bloom-filter keying: lowercase, collapse whitespace."""
    return " ".join(text.lower().split())


class BloomFilter:
    """Memory-efficient Bloom filter with persistence and stats tracking.

    Parameters
    ----------
    expected_items : int
        Estimated number of unique items (memories).
    fp_rate : float
        Target false-positive rate (default 0.005 = 0.5%).
    persist_path : Path or str, optional
        File path for saving/loading the filter state.
    """

    def __init__(self, expected_items: int = 10_000, fp_rate: float = 0.005,
                 persist_path=None):
        self._expected = expected_items
        self._fp_rate = fp_rate
        self._m, self._k = _optimal_params(expected_items, fp_rate)
        self._bits = _BitArray(self._m)
        self._item_count = 0
        self._persist_path = Path(persist_path) if persist_path else None

        # Stats
        self._checks = 0
        self._definite_new = 0  # bloom said "not present" → skipped ChromaDB
        self._maybe_dup = 0     # bloom said "maybe present" → ChromaDB queried

        if self._persist_path and self._persist_path.exists():
            self._load()

    # -- Core operations ---------------------------------------------------

    def add(self, text: str) -> None:
        """Add a text to the filter."""
        normed = _normalize(text)
        for idx in _hash_indices(normed, self._m, self._k):
            self._bits.set(idx)
        self._item_count += 1

    def might_contain(self, text: str) -> bool:
        """Check if text might be in the filter.

        Returns False → definitely not present (skip expensive dedup).
        Returns True  → possibly present (proceed with ChromaDB query).
        """
        normed = _normalize(text)
        self._checks += 1
        for idx in _hash_indices(normed, self._m, self._k):
            if not self._bits.get(idx):
                self._definite_new += 1
                return False
        self._maybe_dup += 1
        return True

    # -- Persistence -------------------------------------------------------

    def save(self) -> None:
        """Save filter state to disk."""
        if not self._persist_path:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            meta = {
                "expected": self._expected,
                "fp_rate": self._fp_rate,
                "m": self._m,
                "k": self._k,
                "item_count": self._item_count,
                "saved_at": time.time(),
            }
            meta_path = self._persist_path.with_suffix(".meta.json")
            with open(meta_path, "w") as f:
                json.dump(meta, f)
            with open(self._persist_path, "wb") as f:
                f.write(self._bits.to_bytes())
            _log.debug("Bloom filter saved: %d items, %d bits", self._item_count, self._m)
        except Exception as e:
            _log.warning("Failed to save bloom filter: %s", e)

    def _load(self) -> None:
        """Load filter state from disk."""
        try:
            meta_path = self._persist_path.with_suffix(".meta.json")
            if not meta_path.exists():
                return
            with open(meta_path) as f:
                meta = json.load(f)
            # Only load if parameters match (otherwise rebuild is needed)
            if meta.get("m") != self._m or meta.get("k") != self._k:
                _log.info("Bloom filter params changed, starting fresh")
                return
            with open(self._persist_path, "rb") as f:
                data = f.read()
            self._bits = _BitArray.from_bytes(data, self._m)
            self._item_count = meta.get("item_count", 0)
            _log.info("Bloom filter loaded: %d items", self._item_count)
        except Exception as e:
            _log.warning("Failed to load bloom filter: %s", e)

    # -- Stats -------------------------------------------------------------

    @property
    def stats(self) -> dict:
        """Return operational statistics."""
        fill_ratio = self._bits.count_ones() / self._m if self._m else 0
        # Estimated actual FP rate based on fill ratio
        est_fp = fill_ratio ** self._k if self._k else 0
        return {
            "items": self._item_count,
            "bits": self._m,
            "hashes": self._k,
            "fill_ratio": round(fill_ratio, 4),
            "target_fp_rate": self._fp_rate,
            "estimated_fp_rate": round(est_fp, 6),
            "checks": self._checks,
            "definite_new": self._definite_new,
            "maybe_duplicate": self._maybe_dup,
            "chromadb_queries_avoided": self._definite_new,
            "skip_rate": round(self._definite_new / self._checks, 4) if self._checks else 0,
        }

    @property
    def needs_rebuild(self) -> bool:
        """True if the filter is overfull and FP rate has likely drifted."""
        return self._item_count > self._expected * 1.5

    def __repr__(self) -> str:
        s = self.stats
        return (f"BloomFilter(items={s['items']}, bits={s['bits']}, "
                f"fill={s['fill_ratio']:.1%}, est_fp={s['estimated_fp_rate']:.4%})")


# ---------------------------------------------------------------------------
# Module-level singleton per collection
# ---------------------------------------------------------------------------

_filters: dict[str, BloomFilter] = {}
_BLOOM_DIR = None


def _get_bloom_dir() -> Path:
    global _BLOOM_DIR
    if _BLOOM_DIR is None:
        ws = os.environ.get("CLARVIS_WORKSPACE",
                            os.path.expanduser("~/.openclaw/workspace"))
        _BLOOM_DIR = Path(ws) / "data" / "clarvisdb" / "bloom"
        _BLOOM_DIR.mkdir(parents=True, exist_ok=True)
    return _BLOOM_DIR


def get_filter(collection: str) -> BloomFilter:
    """Get (or create) the bloom filter for a collection."""
    if collection not in _filters:
        bloom_dir = _get_bloom_dir()
        safe_name = collection.replace("-", "_")
        path = bloom_dir / f"{safe_name}.bloom"
        _filters[collection] = BloomFilter(
            expected_items=5_000,
            fp_rate=0.005,
            persist_path=path,
        )
    return _filters[collection]


def save_all() -> None:
    """Persist all active bloom filters to disk."""
    for bf in _filters.values():
        bf.save()


def get_all_stats() -> dict:
    """Return stats for all active filters."""
    return {col: bf.stats for col, bf in _filters.items()}


def seed_filter(collection: str, chroma_collection) -> int:
    """Seed a bloom filter from an existing ChromaDB collection.

    Call this once after brain init to populate the filter with existing
    memories, so the filter is accurate from the start.

    Returns the number of items seeded.
    """
    bf = get_filter(collection)
    try:
        col_count = chroma_collection.count()
    except Exception:
        col_count = 0
    # Skip if already seeded with a reasonable fraction of the collection
    if bf._item_count > 0 and bf._item_count >= col_count * 0.8:
        return bf._item_count

    try:
        count = chroma_collection.count()
        if count == 0:
            return 0
        # Fetch in batches to avoid memory spikes
        batch_size = 500
        seeded = 0
        offset = 0
        while offset < count:
            results = chroma_collection.get(
                limit=batch_size,
                offset=offset,
                include=["documents"],
            )
            docs = results.get("documents") or []
            if not docs:
                break
            for doc in docs:
                if doc:
                    bf.add(doc)
                    seeded += 1
            offset += batch_size
        bf.save()
        _log.info("Seeded bloom filter for %s: %d items", collection, seeded)
        return seeded
    except Exception as e:
        _log.warning("Failed to seed bloom filter for %s: %s", collection, e)
        return 0
