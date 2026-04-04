"""Trajectory evaluation harness (agentevals-style execution scoring).

Scores execution trajectories using outcome + quality signals:
  - task completion outcome
  - validation error burden
  - retrieval alignment with outcome
  - efficiency (duration)
  - tool-call trajectory shape (when available)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
TRAJECTORY_HISTORY = Path(WORKSPACE) / "data" / "trajectory_eval" / "history.jsonl"

TRAJECTORY_SCHEMA_VERSION = "1.0"

WEIGHTS = {
    "completion": 0.35,
    "validation": 0.20,
    "retrieval_alignment": 0.15,
    "efficiency": 0.15,
    "trajectory_shape": 0.15,
}

GATE_THRESHOLDS = {
    "min_episodes": 5,
    "min_avg_score": 0.62,
    "min_pass_rate": 0.60,
}


def _score_completion(outcome: str) -> float:
    outcome = (outcome or "").lower()
    if outcome == "success":
        return 1.0
    if outcome == "timeout":
        return 0.45
    if outcome == "failure":
        return 0.0
    return 0.3


def _score_validation(errors: int) -> float:
    err = max(0, int(errors or 0))
    if err == 0:
        return 1.0
    # Decrease linearly to zero by 10+ errors.
    return max(0.0, round(1.0 - min(err, 10) / 10.0, 3))


def _score_efficiency(duration_s: int | float | None) -> float:
    if duration_s is None:
        return 0.5
    d = float(duration_s)
    if d <= 0:
        return 0.5
    if d <= 300:
        return 1.0
    if d <= 900:
        return 0.8
    if d <= 1800:
        return 0.5
    return 0.2


def _score_retrieval_alignment(verdict: str | None, outcome: str) -> float:
    verdict = (verdict or "SKIPPED").upper()
    outcome = (outcome or "").lower()
    table = {
        ("CORRECT", "success"): 1.0,
        ("CORRECT", "failure"): 0.35,
        ("CORRECT", "timeout"): 0.40,
        ("AMBIGUOUS", "success"): 0.70,
        ("AMBIGUOUS", "failure"): 0.45,
        ("AMBIGUOUS", "timeout"): 0.50,
        ("INCORRECT", "success"): 0.20,
        ("INCORRECT", "failure"): 0.65,
        ("INCORRECT", "timeout"): 0.55,
        ("SKIPPED", "success"): 0.60,
        ("SKIPPED", "failure"): 0.50,
        ("SKIPPED", "timeout"): 0.50,
        ("NO_RESULTS", "success"): 0.55,
        ("NO_RESULTS", "failure"): 0.50,
        ("NO_RESULTS", "timeout"): 0.50,
        ("ERROR", "success"): 0.35,
        ("ERROR", "failure"): 0.40,
        ("ERROR", "timeout"): 0.40,
    }
    return table.get((verdict, outcome), 0.5)


def _score_trajectory_shape(tool_call_count: int | None) -> float:
    if tool_call_count is None:
        return 0.6
    calls = int(tool_call_count)
    if calls <= 0:
        return 0.25
    if calls <= 15:
        return 1.0
    if calls <= 30:
        return 0.75
    return 0.45


def score_trajectory_episode(event: dict[str, Any]) -> dict[str, Any]:
    """Score one trajectory event and return enriched event."""
    outcome = event.get("task_outcome", "failure")
    completion = _score_completion(outcome)
    validation = _score_validation(event.get("code_validation_errors", 0))
    retrieval_alignment = _score_retrieval_alignment(
        event.get("retrieval_verdict"), outcome
    )
    efficiency = _score_efficiency(event.get("duration_s"))
    trajectory_shape = _score_trajectory_shape(event.get("tool_call_count"))

    weighted = (
        WEIGHTS["completion"] * completion
        + WEIGHTS["validation"] * validation
        + WEIGHTS["retrieval_alignment"] * retrieval_alignment
        + WEIGHTS["efficiency"] * efficiency
        + WEIGHTS["trajectory_shape"] * trajectory_shape
    )

    score = round(weighted, 3)
    scored = dict(event)
    scored["trajectory_score"] = score
    scored["trajectory_components"] = {
        "completion": round(completion, 3),
        "validation": round(validation, 3),
        "retrieval_alignment": round(retrieval_alignment, 3),
        "efficiency": round(efficiency, 3),
        "trajectory_shape": round(trajectory_shape, 3),
    }
    scored["trajectory_schema_version"] = TRAJECTORY_SCHEMA_VERSION
    return scored


def record_trajectory_event(event: dict[str, Any]) -> dict[str, Any]:
    """Append a scored trajectory event to history."""
    TRAJECTORY_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(event)
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
    scored = score_trajectory_episode(payload)
    with open(TRAJECTORY_HISTORY, "a") as f:
        f.write(json.dumps(scored) + "\n")
    return scored


def load_trajectory_events(hours: int = 24) -> list[dict[str, Any]]:
    """Load trajectory events from the last N hours."""
    if not TRAJECTORY_HISTORY.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    events: list[dict[str, Any]] = []
    try:
        lines = TRAJECTORY_HISTORY.read_text().splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = item.get("ts")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if dt >= cutoff:
            events.append(item)
    return events


def evaluate_trajectory_gate(summary: dict[str, Any]) -> dict[str, Any]:
    failures = []
    episodes = summary.get("episodes", 0)
    avg_score = summary.get("avg_score", 0.0) or 0.0
    pass_rate = summary.get("pass_rate", 0.0) or 0.0

    if episodes < GATE_THRESHOLDS["min_episodes"]:
        failures.append(
            f"episodes={episodes} < min_episodes={GATE_THRESHOLDS['min_episodes']}"
        )
    if avg_score < GATE_THRESHOLDS["min_avg_score"]:
        failures.append(
            f"avg_score={avg_score:.3f} < min_avg_score={GATE_THRESHOLDS['min_avg_score']:.3f}"
        )
    if pass_rate < GATE_THRESHOLDS["min_pass_rate"]:
        failures.append(
            f"pass_rate={pass_rate:.3f} < min_pass_rate={GATE_THRESHOLDS['min_pass_rate']:.3f}"
        )
    return {"pass": not failures, "failures": failures}


def summarize_trajectory(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {
            "episodes": 0,
            "avg_score": None,
            "pass_rate": 0.0,
            "outcomes": {},
            "avg_components": {},
            "gate": {"pass": False, "failures": ["no trajectory data"]},
            "schema_version": TRAJECTORY_SCHEMA_VERSION,
        }

    scored = [score_trajectory_episode(e) for e in events]
    scores = [e["trajectory_score"] for e in scored]
    pass_count = sum(1 for s in scores if s >= GATE_THRESHOLDS["min_avg_score"])
    outcomes: dict[str, int] = {}
    for e in scored:
        key = (e.get("task_outcome") or "unknown").lower()
        outcomes[key] = outcomes.get(key, 0) + 1

    comp_names = ("completion", "validation", "retrieval_alignment", "efficiency", "trajectory_shape")
    avg_components = {}
    for name in comp_names:
        vals = [e["trajectory_components"][name] for e in scored]
        avg_components[name] = round(sum(vals) / len(vals), 3)

    summary = {
        "episodes": len(scored),
        "avg_score": round(sum(scores) / len(scores), 3),
        "pass_rate": round(pass_count / len(scored), 3),
        "outcomes": outcomes,
        "avg_components": avg_components,
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
    }
    summary["gate"] = evaluate_trajectory_gate(summary)
    return summary


def format_trajectory_summary(summary: dict[str, Any], hours: int = 24) -> str:
    lines = [f"=== Trajectory Eval Summary (last {hours}h) ==="]
    lines.append(f"Episodes: {summary.get('episodes', 0)}")
    if summary.get("episodes", 0) == 0:
        gate = summary.get("gate", {})
        if gate.get("failures"):
            lines.append(f"Gate: FAIL ({'; '.join(gate['failures'])})")
        return "\n".join(lines)

    lines.append(f"Avg score: {summary.get('avg_score')}")
    lines.append(f"Pass rate: {summary.get('pass_rate', 0.0):.1%}")
    lines.append("Outcomes:")
    for k, v in sorted(summary.get("outcomes", {}).items()):
        lines.append(f"  - {k}: {v}")
    lines.append("Component means:")
    for k, v in sorted(summary.get("avg_components", {}).items()):
        lines.append(f"  - {k}: {v}")
    gate = summary.get("gate", {})
    if gate.get("pass"):
        lines.append("Gate: PASS")
    else:
        lines.append("Gate: FAIL")
        for failure in gate.get("failures", []):
            lines.append(f"  - {failure}")
    return "\n".join(lines)
