"""Incremental TF-IDF index for streaming document indexing.

Supports adding documents one at a time without recomputing the entire corpus.
Key operations:
  - add(doc_id, text)   — index a new document incrementally
  - search(query, k)    — return top-k most relevant documents
  - remove(doc_id)      — remove a document from the index

The IDF component uses an approximation that updates incrementally:
  IDF(t) = log(1 + N / (1 + df(t)))
where N = total docs and df(t) = document frequency of term t.

When N changes, all IDF values shift — but we store df(t) and recompute IDF
on-the-fly during search, so results are always accurate against the current
corpus state. TF vectors are stored per-document as sparse dicts.
"""

import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

_log = logging.getLogger("clarvis.cognition.incremental_tfidf")

# Simple tokenizer: lowercase, split on non-alphanumeric, filter short tokens
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")

# Common English stop words (kept small for speed)
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "of", "and", "or",
    "for", "with", "was", "are", "be", "has", "had", "have", "this", "that",
    "from", "by", "as", "but", "not", "do", "if", "so", "no", "we", "he",
    "she", "they", "you", "i", "my", "me", "our", "us", "its", "am", "been",
    "being", "did", "does", "done", "will", "would", "could", "should", "can",
    "may", "might", "shall", "into", "than", "then", "when", "where", "which",
    "who", "what", "how", "all", "each", "some", "any", "most", "more", "very",
    "just", "also", "about", "up", "out", "over", "after", "before",
})


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase terms, removing stop words."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP_WORDS and len(t) > 1]


class IncrementalTFIDF:
    """Incremental TF-IDF index with streaming document support.

    Parameters
    ----------
    persist_path : str or Path, optional
        File path for JSON persistence. If provided, state is saved after
        each modification.
    """

    def __init__(self, persist_path=None):
        # doc_id -> {term: tf_count}
        self._docs: dict[str, dict[str, int]] = {}
        # doc_id -> total token count (for TF normalization)
        self._doc_lengths: dict[str, int] = {}
        # doc_id -> raw text (for returning results)
        self._doc_texts: dict[str, str] = {}
        # term -> set of doc_ids containing that term
        self._df: dict[str, set[str]] = defaultdict(set)
        # Total document count
        self._n: int = 0

        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path and self._persist_path.exists():
            self._load()

    # -- Core operations ---------------------------------------------------

    def add(self, doc_id: str, text: str) -> None:
        """Add a document to the index incrementally.

        If doc_id already exists, it is updated (removed then re-added).
        """
        if doc_id in self._docs:
            self.remove(doc_id)

        tokens = tokenize(text)
        if not tokens:
            return

        tf = Counter(tokens)
        self._docs[doc_id] = dict(tf)
        self._doc_lengths[doc_id] = len(tokens)
        self._doc_texts[doc_id] = text
        self._n += 1

        # Update document frequency
        for term in tf:
            self._df[term].add(doc_id)

        if self._persist_path:
            self._save()

    def remove(self, doc_id: str) -> bool:
        """Remove a document from the index. Returns True if found."""
        if doc_id not in self._docs:
            return False

        tf = self._docs.pop(doc_id)
        self._doc_lengths.pop(doc_id, None)
        self._doc_texts.pop(doc_id, None)
        self._n -= 1

        # Update document frequency
        for term in tf:
            self._df[term].discard(doc_id)
            if not self._df[term]:
                del self._df[term]

        if self._persist_path:
            self._save()
        return True

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Search the index for the top-k most relevant documents.

        Returns a list of dicts: [{doc_id, score, text}, ...] sorted by
        descending TF-IDF cosine similarity score.
        """
        if self._n == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Build query TF-IDF vector (sparse)
        query_tf = Counter(query_tokens)
        query_vec = {}
        for term, count in query_tf.items():
            df = len(self._df.get(term, set()))
            if df == 0:
                continue
            idf = math.log(1 + self._n / (1 + df))
            query_vec[term] = (count / len(query_tokens)) * idf

        if not query_vec:
            return []

        # Score each candidate document (only those sharing at least one query term)
        candidate_ids = set()
        for term in query_vec:
            candidate_ids.update(self._df.get(term, set()))

        scores = []
        query_norm = math.sqrt(sum(v * v for v in query_vec.values()))

        for doc_id in candidate_ids:
            doc_tf = self._docs[doc_id]
            doc_len = self._doc_lengths[doc_id]

            # Compute dot product and doc norm (only over shared terms)
            dot = 0.0
            doc_norm_sq = 0.0
            for term, q_weight in query_vec.items():
                raw_tf = doc_tf.get(term, 0)
                if raw_tf == 0:
                    continue
                df = len(self._df.get(term, set()))
                idf = math.log(1 + self._n / (1 + df))
                d_weight = (raw_tf / doc_len) * idf
                dot += q_weight * d_weight
                doc_norm_sq += d_weight * d_weight

            if dot <= 0 or doc_norm_sq <= 0:
                continue

            # Cosine similarity
            cosine = dot / (query_norm * math.sqrt(doc_norm_sq))
            scores.append((doc_id, cosine))

        # Sort by score descending, return top-k
        scores.sort(key=lambda x: x[1], reverse=True)
        return [
            {"doc_id": did, "score": round(sc, 6), "text": self._doc_texts.get(did, "")}
            for did, sc in scores[:k]
        ]

    # -- Properties --------------------------------------------------------

    @property
    def doc_count(self) -> int:
        return self._n

    @property
    def vocab_size(self) -> int:
        return len(self._df)

    @property
    def stats(self) -> dict:
        return {
            "doc_count": self._n,
            "vocab_size": len(self._df),
            "avg_doc_length": (
                sum(self._doc_lengths.values()) / self._n if self._n else 0
            ),
        }

    # -- Persistence -------------------------------------------------------

    def _save(self) -> None:
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "docs": self._docs,
                "doc_lengths": self._doc_lengths,
                "doc_texts": self._doc_texts,
                "df": {t: list(ids) for t, ids in self._df.items()},
                "n": self._n,
            }
            with open(self._persist_path, "w") as f:
                json.dump(state, f)
        except Exception as e:
            _log.warning("Failed to save TF-IDF index: %s", e)

    def _load(self) -> None:
        try:
            with open(self._persist_path) as f:
                state = json.load(f)
            self._docs = state.get("docs", {})
            self._doc_lengths = state.get("doc_lengths", {})
            self._doc_texts = state.get("doc_texts", {})
            self._df = defaultdict(set)
            for t, ids in state.get("df", {}).items():
                self._df[t] = set(ids)
            self._n = state.get("n", 0)
            _log.info("Loaded TF-IDF index: %d docs, %d terms", self._n, len(self._df))
        except Exception as e:
            _log.warning("Failed to load TF-IDF index: %s", e)
