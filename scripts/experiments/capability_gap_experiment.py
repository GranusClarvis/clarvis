#!/usr/bin/env python3
"""
Capability Gap Experiment: Reasoning Chain Depth
=================================================
Experiment ID: exp_reasoning_depth_20260414
Hypothesis: Reconnecting the ClarvisReasoning spine module to the heartbeat
pipeline (broken since package→spine migration) will increase 4+ step chains
from ~3% to >30% of sessions, improving reasoning quality grade distribution.

Baseline (2026-04-14):
  - 61 sessions total, 2 with 4+ steps (3.3% deep rate)
  - 47/61 with outcomes (77% completion rate)
  - Depth distribution: {1:1, 2:13, 3:45, 6:1, 7:1}
  - cr_reasoner was None — sessions created only by direct API calls
  - All 295 legacy chains permanently frozen at depth 2-3

Intervention (applied 2026-04-14):
  1. Reconnected cr_reasoner import in reasoning_chain_hook.py
  2. Expanded decomposition maps (3→4+ sub-problems per task type)
  3. Fixed get_reasoning_score to evaluate sessions separately from frozen legacy

Success criteria (measure after 48h):
  - Deep session rate (4+ steps) > 30%
  - Session completion rate > 80%
  - Reasoning quality grade 'good' > 50% of completed sessions

Usage:
    python3 scripts/experiments/capability_gap_experiment.py baseline
    python3 scripts/experiments/capability_gap_experiment.py measure
    python3 scripts/experiments/capability_gap_experiment.py report
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = Path(_WS) / "data" / "reasoning_chains"
SESSIONS_DIR = DATA_DIR / "sessions"
EXPERIMENT_FILE = Path(_WS) / "data" / "experiments" / "reasoning_depth_experiment.json"
EXPERIMENT_FILE.parent.mkdir(parents=True, exist_ok=True)


def collect_metrics() -> dict:
    """Collect current reasoning chain metrics."""
    from clarvis.cognition.reasoning import ReasoningSession

    sessions = list(SESSIONS_DIR.glob("rs_*.json"))
    legacy = list(DATA_DIR.glob("chain_*.json"))

    total_sessions = len(sessions)
    depth_dist = {}
    deep_count = 0
    completed = 0
    grades = {"good": 0, "adequate": 0, "shallow": 0, "poor": 0, "empty": 0}
    outcomes = {}
    depths_by_outcome = {}

    for f in sessions:
        try:
            s = ReasoningSession.load(f.stem)
            n = len(s.steps)
            depth_dist[n] = depth_dist.get(n, 0) + 1
            if n >= 4 and s.completed:
                deep_count += 1
            if s.completed:
                completed += 1
            ev = s.evaluate()
            grade = ev.get("quality_grade", "empty")
            grades[grade] = grades.get(grade, 0) + 1
            outcome = s.actual_outcome or "none"
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            depths_by_outcome.setdefault(outcome, []).append(n)
        except Exception:
            continue

    deep_rate = deep_count / max(total_sessions, 1)
    completion_rate = completed / max(total_sessions, 1)
    good_rate = grades["good"] / max(completed, 1)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_sessions": total_sessions,
        "total_legacy": len(legacy),
        "completed": completed,
        "deep_count": deep_count,
        "deep_rate": round(deep_rate, 3),
        "completion_rate": round(completion_rate, 3),
        "good_rate": round(good_rate, 3),
        "depth_distribution": {str(k): v for k, v in sorted(depth_dist.items())},
        "grade_distribution": grades,
        "outcome_distribution": outcomes,
        "avg_depth_by_outcome": {
            k: round(sum(v) / len(v), 2) for k, v in depths_by_outcome.items()
        },
    }


def save_baseline():
    """Record baseline metrics before intervention."""
    metrics = collect_metrics()
    experiment = {
        "experiment_id": "exp_reasoning_depth_20260414",
        "hypothesis": "Reconnecting cr_reasoner + deeper decomposition increases 4+ step chains from ~3% to >30%",
        "started": datetime.now(timezone.utc).isoformat(),
        "baseline": metrics,
        "measurements": [],
        "status": "running",
    }
    EXPERIMENT_FILE.write_text(json.dumps(experiment, indent=2))
    print(f"Baseline recorded: {metrics['total_sessions']} sessions, "
          f"{metrics['deep_rate']:.1%} deep rate, "
          f"{metrics['good_rate']:.1%} good grade rate")
    return experiment


def measure():
    """Take a measurement and compare to baseline."""
    if not EXPERIMENT_FILE.exists():
        print("No experiment found. Run 'baseline' first.")
        return

    experiment = json.loads(EXPERIMENT_FILE.read_text())
    metrics = collect_metrics()

    # Only count sessions created after the intervention
    baseline = experiment["baseline"]
    baseline_total = baseline["total_sessions"]
    new_sessions = metrics["total_sessions"] - baseline_total

    experiment["measurements"].append(metrics)
    EXPERIMENT_FILE.write_text(json.dumps(experiment, indent=2))

    print(f"Measurement #{len(experiment['measurements'])}:")
    print(f"  New sessions since baseline: {new_sessions}")
    print(f"  Deep rate: {baseline['deep_rate']:.1%} → {metrics['deep_rate']:.1%}")
    print(f"  Completion rate: {baseline['completion_rate']:.1%} → {metrics['completion_rate']:.1%}")
    print(f"  Good grade rate: {baseline['good_rate']:.1%} → {metrics['good_rate']:.1%}")
    print(f"  Depth distribution: {metrics['depth_distribution']}")


def report():
    """Full experiment report."""
    if not EXPERIMENT_FILE.exists():
        print("No experiment found.")
        return

    experiment = json.loads(EXPERIMENT_FILE.read_text())
    baseline = experiment["baseline"]

    print("=" * 60)
    print(f"Experiment: {experiment['experiment_id']}")
    print(f"Hypothesis: {experiment['hypothesis']}")
    print(f"Started: {experiment['started']}")
    print(f"Status: {experiment['status']}")
    print(f"Measurements: {len(experiment['measurements'])}")
    print()
    print("BASELINE:")
    print(f"  Sessions: {baseline['total_sessions']}")
    print(f"  Deep (4+ steps): {baseline['deep_count']} ({baseline['deep_rate']:.1%})")
    print(f"  Completion: {baseline['completion_rate']:.1%}")
    print(f"  Good grade: {baseline['good_rate']:.1%}")
    print(f"  Depth dist: {baseline['depth_distribution']}")

    if experiment["measurements"]:
        latest = experiment["measurements"][-1]
        print()
        print("LATEST:")
        print(f"  Sessions: {latest['total_sessions']}")
        print(f"  Deep (4+ steps): {latest['deep_count']} ({latest['deep_rate']:.1%})")
        print(f"  Completion: {latest['completion_rate']:.1%}")
        print(f"  Good grade: {latest['good_rate']:.1%}")
        print(f"  Depth dist: {latest['depth_distribution']}")
        print()

        # Check success criteria
        criteria = [
            ("Deep rate > 30%", latest["deep_rate"] > 0.30),
            ("Completion > 80%", latest["completion_rate"] > 0.80),
            ("Good grade > 50%", latest["good_rate"] > 0.50),
        ]
        print("SUCCESS CRITERIA:")
        for name, met in criteria:
            print(f"  {'PASS' if met else 'FAIL'}: {name}")

    print("=" * 60)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "baseline":
        save_baseline()
    elif cmd == "measure":
        measure()
    elif cmd == "report":
        report()
    else:
        print(f"Unknown command: {cmd}. Use: baseline, measure, report")
