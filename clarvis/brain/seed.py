"""Brain seed data — populate initial memories on fresh installs.

Gives the brain useful content from day one so that searches return
results and the demo feels alive instead of empty.

Usage:
    python3 -m clarvis brain seed          # Seed if not already done
    python3 -m clarvis brain seed --force  # Re-seed (skips dedup marker check)
"""

import logging
import time

_logger = logging.getLogger("clarvis.brain.seed")

# Marker document stored in IDENTITY to prevent re-seeding.
_SEED_MARKER = "clarvis-brain-seed-complete"

SEED_MEMORIES = [
    # ── Identity ──────────────────────────────────────────────────────
    {
        "collection": "clarvis-identity",
        "text": (
            "Clarvis is a dual-layer cognitive agent. The conscious layer handles "
            "direct conversation, while the subconscious layer runs autonomous "
            "evolution, reflection, and research via scheduled tasks."
        ),
        "importance": 0.8,
        "tags": ["core", "architecture"],
    },
    {
        "collection": "clarvis-identity",
        "text": (
            "ClarvisDB is the local vector memory system built on ChromaDB with "
            "ONNX MiniLM embeddings. It runs entirely on-device with no cloud "
            "dependency. Memories are stored across 10 semantic collections."
        ),
        "importance": 0.8,
        "tags": ["core", "brain"],
    },
    # ── Procedures ────────────────────────────────────────────────────
    {
        "collection": "clarvis-procedures",
        "text": (
            "To search memories use: clarvis brain search \"your query\". "
            "The brain routes queries to the most relevant collections "
            "automatically based on keyword patterns."
        ),
        "importance": 0.7,
        "tags": ["howto", "cli"],
    },
    {
        "collection": "clarvis-procedures",
        "text": (
            "To store a new memory use the Python API: "
            "from clarvis.brain import remember; "
            "remember('your text here', importance=0.8). "
            "Category and tags are auto-detected from the text content."
        ),
        "importance": 0.7,
        "tags": ["howto", "api"],
    },
    {
        "collection": "clarvis-procedures",
        "text": (
            "To check brain health run: clarvis brain health. "
            "This shows memory count, graph stats, consolidation status, "
            "and runs a store/recall round-trip test."
        ),
        "importance": 0.7,
        "tags": ["howto", "cli"],
    },
    {
        "collection": "clarvis-procedures",
        "text": (
            "Available CLI commands: clarvis brain (memory ops), "
            "clarvis demo (self-test), clarvis heartbeat (pipeline), "
            "clarvis cron (job management), clarvis mode (runtime control), "
            "clarvis welcome (onboarding guide). Run any with --help for details."
        ),
        "importance": 0.7,
        "tags": ["howto", "cli"],
    },
    # ── Goals ─────────────────────────────────────────────────────────
    {
        "collection": "clarvis-goals",
        "text": (
            "Goal: Learn and grow through experience. Build up useful memories, "
            "develop reliable procedures, and improve cognitive capabilities "
            "over time through reflection and autonomous learning."
        ),
        "importance": 0.7,
        "tags": ["goal", "core"],
    },
    {
        "collection": "clarvis-goals",
        "text": (
            "Goal: Maintain brain health. Keep memory quality high through "
            "regular optimization, deduplication, and decay. Monitor retrieval "
            "quality and graph integrity."
        ),
        "importance": 0.7,
        "tags": ["goal", "maintenance"],
    },
    # ── Learnings ─────────────────────────────────────────────────────
    {
        "collection": "clarvis-learnings",
        "text": (
            "Clarvis uses a local-first design: ChromaDB vector store and ONNX "
            "MiniLM embeddings run on-device. No API keys are needed for core "
            "brain operations, search, or the CLI."
        ),
        "importance": 0.7,
        "tags": ["architecture", "local-first"],
    },
    {
        "collection": "clarvis-learnings",
        "text": (
            "The heartbeat pipeline is a three-stage process: "
            "gate (zero-LLM decision to wake or skip), "
            "preflight (attention scoring, task selection, context assembly), "
            "then task execution followed by postflight (episode encoding, "
            "brain storage)."
        ),
        "importance": 0.7,
        "tags": ["architecture", "heartbeat"],
    },
    {
        "collection": "clarvis-learnings",
        "text": (
            "The graph backend uses SQLite with WAL mode for ACID-safe "
            "relationship storage. Graph edges connect related memories "
            "across collections, enabling traversal and contextual enrichment."
        ),
        "importance": 0.6,
        "tags": ["architecture", "graph"],
    },
]


def is_seeded(brain_instance) -> bool:
    """Check if the brain has already been seeded."""
    try:
        col = brain_instance.collections.get("clarvis-identity")
        if col is None:
            return False
        results = col.get(where_document={"$contains": _SEED_MARKER})
        return bool(results and results.get("ids"))
    except Exception:
        return False


def seed_initial_memories(force=False) -> dict:
    """Populate the brain with initial seed memories.

    Args:
        force: If True, skip the already-seeded check and re-seed.

    Returns:
        Dict with seeded count, skipped count, and status.
    """
    from clarvis.brain import get_brain

    b = get_brain()

    if not force and is_seeded(b):
        return {"status": "already_seeded", "seeded": 0, "skipped": len(SEED_MEMORIES)}

    seeded = 0
    skipped = 0
    errors = []

    for mem in SEED_MEMORIES:
        col_name = mem["collection"]
        col = b.collections.get(col_name)
        if col is None:
            skipped += 1
            errors.append(f"Collection {col_name} not available")
            continue

        try:
            # Check for near-duplicate before storing (distance < 0.3)
            existing = col.query(query_texts=[mem["text"]], n_results=1)
            if (existing and existing.get("distances")
                    and existing["distances"][0]
                    and existing["distances"][0][0] < 0.3):
                skipped += 1
                continue

            mem_id = f"seed-{col_name.split('-')[-1]}-{seeded:03d}"
            col.add(
                ids=[mem_id],
                documents=[mem["text"]],
                metadatas=[{
                    "importance": mem["importance"],
                    "source": "seed",
                    "tags": ",".join(mem.get("tags", [])),
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "created_epoch": time.time(),
                }],
            )
            seeded += 1
        except Exception as e:
            skipped += 1
            errors.append(f"{col_name}: {e}")

    # Store the seed marker so we don't re-seed on next run
    if seeded > 0:
        try:
            id_col = b.collections.get("clarvis-identity")
            if id_col:
                id_col.add(
                    ids=["seed-marker"],
                    documents=[_SEED_MARKER],
                    metadatas=[{
                        "importance": 0.1,
                        "source": "seed",
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }],
                )
        except Exception:
            pass  # Non-critical — seed still worked

    result = {
        "status": "seeded",
        "seeded": seeded,
        "skipped": skipped,
        "total": len(SEED_MEMORIES),
    }
    if errors:
        result["errors"] = errors

    return result
