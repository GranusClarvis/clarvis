#!/usr/bin/env python3
"""
Task Router — Selective reasoning for Clarvis heartbeat loop.

DEPRECATED: Core logic moved to clarvis.orch.router (Phase 7 spine migration).
This wrapper delegates to the spine module for backward compatibility.

Usage:
    python3 task_router.py classify "Build a new cron script for X"
    python3 task_router.py execute-openrouter "Task text" [model]
    python3 task_router.py stats
"""

import json
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

# Spine delegation — all logic now lives in clarvis.orch.router
from clarvis.orch.router import (  # noqa: E402
    classify_task, execute_openrouter, log_decision, get_stats,
    score_dimension, DIMENSIONS, TIER_BOUNDARIES, OPENROUTER_MODELS,
    FORCE_CLAUDE_PATTERNS, FORCE_SIMPLE_PATTERNS, VISION_PATTERNS,
    WEB_SEARCH_PATTERNS, ROUTER_LOG, DATA_DIR,
)

warnings.warn(
    "task_router.py is deprecated — use clarvis.orch.router instead",
    DeprecationWarning,
    stacklevel=2,
)

# === CLI (kept here for backward-compatible invocation) ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  task_router.py classify <task_text>     # Classify complexity")
        print("  task_router.py route <task_text>         # Classify + output JSON for bash")
        print("  task_router.py execute-openrouter <task> # Execute via OpenRouter")
        print("  task_router.py stats                     # Show routing statistics")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "classify":
        task = " ".join(sys.argv[2:])
        result = classify_task(task)
        print(json.dumps(result, indent=2))

    elif cmd == "route":
        task = " ".join(sys.argv[2:])
        result = classify_task(task)
        print(json.dumps(result))

    elif cmd == "execute-openrouter":
        task = " ".join(sys.argv[2:])
        model = os.environ.get("OPENROUTER_MODEL")
        context = os.environ.get("TASK_CONTEXT", "")
        proc_hint = os.environ.get("TASK_PROC_HINT", "")
        episode_hint = os.environ.get("TASK_EPISODE_HINT", "")
        result = execute_openrouter(task, model, context, proc_hint, episode_hint)
        print(result["output"])
        if result.get("usage"):
            usage_json = json.dumps(result["usage"])
            print(f"OPENROUTER_USAGE: {usage_json}", file=sys.stderr)
        if result.get("fallback"):
            print("NEEDS_CLAUDE_CODE: true", file=sys.stderr)
        sys.exit(result["exit_code"])

    elif cmd == "stats":
        stats = get_stats()
        print("Routing Stats:")
        print(f"  Total decisions: {stats['total']}")
        print(f"  Gemini (simple): {stats['gemini']} ({stats['gemini_pct']}%)")
        print(f"  Claude (complex): {stats['claude']}")
        print(f"  Fallbacks: {stats['fallbacks']}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
