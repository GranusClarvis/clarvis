#!/usr/bin/env python3
"""
Task Selector — Attention-based task prioritization for Clarvis

CLI wrapper — canonical scoring logic lives in clarvis.orch.task_selector (spine module).

Usage:
    python3 task_selector.py           # Output best task as JSON
    python3 task_selector.py --all     # Output all scored tasks
"""

import json
import sys
import os

# Ensure clarvis package is importable
_workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

# Import everything from the canonical spine module
from clarvis.orch.task_selector import (  # noqa: E402
    # Constants
    QUEUE_FILE, QUALITY_GATE_FILE,
    AGI_KEYWORDS, INTEGRATION_KEYWORDS, ARCHITECTURAL_KEYWORDS,
    # Functions
    parse_tasks, score_tasks,
    _get_spotlight_themes, _spotlight_alignment,
    _check_quality_gate, _is_repair_task,
)

from clarvis.cognition.attention import attention  # noqa: E402


def select_best_task():
    """Main entry: parse, score, return best task as JSON on stdout."""
    tasks = parse_tasks()

    if not tasks:
        result = {"error": "no_tasks", "message": "Queue empty"}
        print(json.dumps(result))
        return None

    scored = score_tasks(tasks)

    # Check memory quality gate — if degraded, only allow repair/P0 tasks
    gate = _check_quality_gate()
    if gate:
        print(f"QUALITY GATE ACTIVE: {gate.get('violations', [])}", file=sys.stderr)
        repair_tasks = [t for t in scored if t["section"] == "P0" or _is_repair_task(t["text"])]
        if repair_tasks:
            scored = repair_tasks
            print(f"QUALITY GATE: filtered to {len(scored)} repair/P0 tasks", file=sys.stderr)
        else:
            print("QUALITY GATE: no repair tasks found, allowing best task anyway", file=sys.stderr)

    # Log all scores to stderr (captured in cron log)
    for t in scored:
        print(
            f"SALIENCE: {t['salience']:.4f} [{t['section']}] {t['text'][:80]}",
            file=sys.stderr,
        )

    best = scored[0]

    # Also run attention tick (competition cycle) to maintain spotlight health
    attention.tick()

    # Output best task as JSON on stdout
    print(json.dumps(best))
    return best


if __name__ == "__main__":
    if "--all" in sys.argv:
        tasks = parse_tasks()
        if not tasks:
            print("No pending tasks in queue.")
            sys.exit(0)
        scored = score_tasks(tasks)
        print(f"\n{'='*70}")
        print(f"  ATTENTION-SCORED TASK RANKING ({len(scored)} tasks)")
        print(f"{'='*70}")
        for i, t in enumerate(scored):
            marker = " >>> BEST" if i == 0 else ""
            print(f"  {i+1}. [{t['salience']:.4f}] [{t['section']}] {t['text'][:70]}{marker}")
            d = t["details"]
            print(f"     importance={d['section_importance']}  relevance={d['combined_relevance']}"
                  f"  agi={d['agi_boost']}  integration={d['integration_boost']}"
                  f"  arch={d.get('architectural_boost', 0)}"
                  f"  spotlight={d.get('spotlight_alignment', 0)}"
                  f"  somatic={d.get('somatic_bias', 0)}({d.get('somatic_signal', 'n/a')})"
                  f"  codelet={d.get('codelet_bias', 0)}"
                  f"  fail_pen={d.get('failure_penalty', 0)}")
        print(f"{'='*70}")
    else:
        select_best_task()
