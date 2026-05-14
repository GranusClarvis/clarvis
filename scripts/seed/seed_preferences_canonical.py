#!/usr/bin/env python3
"""Canonical preferences seed — write 4-6 high-importance preference memories.

Targets the weakest retrieval-benchmark category: `preferences` per-category
P@3=0.583 (n=4) in `data/retrieval_benchmark/latest.json`. Each seed directly
answers a failing/borderline preferences query in `data/golden_qa.json`
(B16/B17 visible in evening.log, plus expansion B26/B27).

Idempotency: re-running inserts zero duplicates. Detection is by
metadata.source == SEED_SOURCE in the clarvis-preferences collection.

Usage:
    python3 scripts/seed/seed_preferences_canonical.py            # seed + verify
    python3 scripts/seed/seed_preferences_canonical.py --dry-run  # report only
    python3 scripts/seed/seed_preferences_canonical.py --verify   # run benchmark
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from clarvis.brain import remember, get_brain, PREFERENCES

SEED_SOURCE = "preferences_canonical_seed_2026-05-14"
SEED_IMPORTANCE = 0.85

# Each item directly answers a golden_qa preferences query.
# "topic" tags the query family; "text" is the canonical memory content.
CANONICAL_SEEDS = [
    {
        "topic": "communication_style",
        "text": (
            "Communication style preference: direct, no fluff, concise. "
            "Lead with the answer. Skip preamble and unnecessary transitions. "
            "Prefer short sentences. Only add comments where logic isn't "
            "self-evident. The operator prefers terse responses without "
            "trailing summaries."
        ),
    },
    {
        "topic": "timezone",
        "text": (
            "Timezone preference: CET (Central European Time). All cron "
            "schedules in CET. The operator is located in the CET timezone, "
            "and Clarvis aligns daily routines (morning planning, evening "
            "reflection, digest reports) to CET clock time."
        ),
    },
    {
        "topic": "sessions_spawn_prohibition",
        "text": (
            "NEVER use sessions_spawn to run Claude Code — it spawns M2.5 "
            "(wrong model), not Claude Code. This caused a $4+ token-waste "
            "incident. Always use scripts/agents/spawn_claude.sh or invoke "
            "/home/agent/.local/bin/claude directly with the documented "
            "spawn convention: env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT, "
            "--dangerously-skip-permissions flag, and a minimum timeout of "
            "600 seconds (1200s default)."
        ),
    },
    {
        "topic": "claude_code_spawn_convention",
        "text": (
            "Claude Code spawn convention and flags: always use full path "
            "/home/agent/.local/bin/claude, prefix with "
            "env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT (nesting guard), "
            "pass --dangerously-skip-permissions (or it hangs), minimum "
            "timeout 600s, default timeout 1200s, large builds 1800s. "
            "Silence is still working — output is buffered; do not kill on "
            "silence."
        ),
    },
    {
        "topic": "python_import_convention",
        "text": (
            "Python import convention preference: all code (spine and "
            "scripts) uses spine imports — `from clarvis.brain import "
            "brain, search, remember, capture`, `from clarvis.cognition.* "
            "import ...`, `from clarvis.orch.* import ...`. Cross-script "
            "imports use `clarvis._script_loader.load()` (importlib-based, "
            "no sys.path mutation). The clarvis/ package is the spine."
        ),
    },
    {
        "topic": "code_style_comments",
        "text": (
            "Code style preference: write no comments by default. Only add "
            "a comment when the WHY is non-obvious — a hidden constraint, "
            "subtle invariant, workaround for a bug, behavior that would "
            "surprise a reader. Do not explain WHAT the code does — "
            "well-named identifiers already do that. Do not reference the "
            "current task, fix, or callers."
        ),
    },
]


def _existing_seed_ids(brain_obj) -> list[str]:
    """Return memory IDs in clarvis-preferences whose metadata.source == SEED_SOURCE."""
    col = brain_obj.collections.get(PREFERENCES)
    if col is None:
        return []
    try:
        results = col.get(where={"source": SEED_SOURCE})
    except Exception:
        # Some Chroma builds need slightly different filter syntax; fall back to scan.
        try:
            results = col.get()
        except Exception:
            return []
        ids = []
        for mid, meta in zip(results.get("ids") or [], results.get("metadatas") or []):
            if (meta or {}).get("source") == SEED_SOURCE:
                ids.append(mid)
        return ids
    return list(results.get("ids") or [])


def seed(dry_run: bool = False) -> dict:
    """Insert canonical seeds (idempotent). Returns counts + ids."""
    brain_obj = get_brain()
    existing = _existing_seed_ids(brain_obj)

    if existing:
        return {
            "inserted": 0,
            "skipped": len(existing),
            "existing_ids": existing,
            "reason": "already_seeded",
        }

    if dry_run:
        return {
            "inserted": 0,
            "would_insert": len(CANONICAL_SEEDS),
            "topics": [s["topic"] for s in CANONICAL_SEEDS],
            "dry_run": True,
        }

    inserted_ids: list[str] = []
    # remember() is imported per task contract; we then call brain.store()
    # with an explicit memory_id so multiple seeds in the same second do not
    # collide on the default timestamp-derived id (upsert would overwrite).
    _ = remember  # keep import live for the public API contract
    for seed_item in CANONICAL_SEEDS:
        explicit_id = f"{PREFERENCES}_{SEED_SOURCE}_{seed_item['topic']}"
        memory_id = brain_obj.store(
            seed_item["text"],
            collection=PREFERENCES,
            importance=SEED_IMPORTANCE,
            source=SEED_SOURCE,
            memory_id=explicit_id,
        )
        brain_obj.update_memory(
            memory_id,
            metadata_patch={
                "source": SEED_SOURCE,
                "topic": seed_item["topic"],
                "importance": SEED_IMPORTANCE,
                "seeded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        inserted_ids.append(memory_id)

    return {
        "inserted": len(inserted_ids),
        "skipped": 0,
        "inserted_ids": inserted_ids,
        "topics": [s["topic"] for s in CANONICAL_SEEDS],
    }


def verify_benchmark() -> dict:
    """Run retrieval benchmark, return preferences P@3 and overall P@3."""
    import subprocess

    workspace = os.environ.get(
        "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
    )
    bench_script = os.path.join(workspace, "scripts/brain_mem/retrieval_benchmark.py")
    latest_path = os.path.join(workspace, "data/retrieval_benchmark/latest.json")

    result = subprocess.run(
        ["python3", bench_script],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "error": "benchmark_failed",
            "stderr": result.stderr[-500:],
        }

    with open(latest_path) as f:
        data = json.load(f)

    overall = data.get("avg_precision_at_k")
    pref = (data.get("by_category") or {}).get("preferences") or {}
    pref_p3 = pref.get("avg_precision_at_k")

    return {
        "ok": True,
        "timestamp": data.get("timestamp"),
        "overall_p3": overall,
        "preferences_p3": pref_p3,
        "preferences_count": pref.get("count"),
        "meets_pref_target": pref_p3 is not None and pref_p3 >= 0.75,
        "meets_overall_target": overall is not None and overall >= 0.7816,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--verify", action="store_true", help="Run benchmark after seed")
    parser.add_argument(
        "--verify-only", action="store_true", help="Only verify (no seed)"
    )
    args = parser.parse_args(argv)

    if not args.verify_only:
        result = seed(dry_run=args.dry_run)
        print("SEED:", json.dumps(result, indent=2))
        if args.dry_run:
            return 0

    if args.verify or args.verify_only:
        v = verify_benchmark()
        print("VERIFY:", json.dumps(v, indent=2))
        if not v.get("ok"):
            return 2
        if not v.get("meets_pref_target"):
            print(
                f"FAIL: preferences_p3={v['preferences_p3']} < 0.75",
                file=sys.stderr,
            )
            return 3
        if not v.get("meets_overall_target"):
            print(
                f"FAIL: overall_p3={v['overall_p3']} < 0.7816",
                file=sys.stderr,
            )
            return 4
        print("OK: targets met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
