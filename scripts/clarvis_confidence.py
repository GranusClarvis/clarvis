#!/usr/bin/env python3
"""
Clarvis Confidence Tracking - v1
Track predictions with numeric confidence, record outcomes, measure calibration.
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

CALIBRATION_DIR = "/home/agent/.openclaw/workspace/data/calibration"
PREDICTIONS_FILE = f"{CALIBRATION_DIR}/predictions.jsonl"
os.makedirs(CALIBRATION_DIR, exist_ok=True)


def _load_predictions():
    """Load all predictions from disk."""
    if not os.path.exists(PREDICTIONS_FILE):
        return []
    entries = []
    with open(PREDICTIONS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _save_predictions(entries):
    """Rewrite all predictions to disk."""
    with open(PREDICTIONS_FILE, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def predict(event: str, expected: str, confidence: float) -> dict:
    """
    Log a prediction.

    Args:
        event: What you're predicting about (e.g. "deploy_success")
        expected: What you think will happen (e.g. "no errors")
        confidence: 0.0 to 1.0 how confident you are
    """
    confidence = max(0.0, min(1.0, float(confidence)))

    entry = {
        "event": event,
        "expected": expected,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome": None,  # filled by outcome()
        "correct": None,  # filled by outcome()
    }

    with open(PREDICTIONS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Store in brain
    _brain_store(
        f"Prediction: {event} — expected '{expected}' (confidence: {confidence:.0%})",
        importance=0.4,
    )

    print(f"Logged prediction: {event} @ {confidence:.0%} confidence")
    return entry


def outcome(event: str, actual: str) -> dict | None:
    """
    Record what actually happened for a prediction.
    Matches the most recent unresolved prediction for this event.

    Args:
        event: The event name (must match a prior predict() call)
        actual: What actually happened
    Returns:
        The updated entry, or None if no matching prediction found.
    """
    entries = _load_predictions()

    # Find most recent unresolved prediction for this event
    target = None
    for entry in reversed(entries):
        if entry["event"] == event and entry["outcome"] is None:
            target = entry
            break

    if target is None:
        print(f"No unresolved prediction found for '{event}'")
        return None

    target["outcome"] = actual
    target["correct"] = actual.lower().strip() == target["expected"].lower().strip()
    _save_predictions(entries)

    status = "CORRECT" if target["correct"] else "WRONG"
    _brain_store(
        f"Outcome: {event} — predicted '{target['expected']}' ({target['confidence']:.0%}), "
        f"got '{actual}' → {status}",
        importance=0.6,
    )

    print(f"Recorded: {event} → {status} (was {target['confidence']:.0%} confident)")
    return target


def calibration() -> dict:
    """
    Compute calibration stats.
    Groups predictions into buckets (0-30%, 30-60%, 60-90%, 90-100%)
    and shows what % actually came true in each bucket.
    """
    entries = _load_predictions()
    resolved = [e for e in entries if e["correct"] is not None]

    if not resolved:
        return {"total": len(entries), "resolved": 0, "buckets": {}}

    buckets = {
        "low (0-30%)": {"range": (0.0, 0.3), "correct": 0, "total": 0},
        "med (30-60%)": {"range": (0.3, 0.6), "correct": 0, "total": 0},
        "high (60-90%)": {"range": (0.6, 0.9), "correct": 0, "total": 0},
        "very_high (90-100%)": {"range": (0.9, 1.01), "correct": 0, "total": 0},
    }

    for entry in resolved:
        conf = entry["confidence"]
        for bucket in buckets.values():
            lo, hi = bucket["range"]
            if lo <= conf < hi:
                bucket["total"] += 1
                if entry["correct"]:
                    bucket["correct"] += 1
                break

    # Build result
    result = {"total": len(entries), "resolved": len(resolved), "buckets": {}}
    for name, bucket in buckets.items():
        if bucket["total"] > 0:
            accuracy = bucket["correct"] / bucket["total"]
            result["buckets"][name] = {
                "accuracy": round(accuracy, 2),
                "correct": bucket["correct"],
                "total": bucket["total"],
            }

    # Overall Brier score (lower = better, 0 = perfect)
    brier = sum(
        (e["confidence"] - (1.0 if e["correct"] else 0.0)) ** 2 for e in resolved
    ) / len(resolved)
    result["brier_score"] = round(brier, 4)

    return result


def _brain_store(text: str, importance: float = 0.5):
    """Store to brain if available, fail silently if not."""
    try:
        from brain import brain
        brain.store(
            text,
            collection="clarvis-memories",
            importance=importance,
            tags=["confidence", "prediction"],
            source="confidence_tracker",
        )
    except Exception:
        pass  # brain not available, that's fine


# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Clarvis Confidence Tracker v1")
        print(f"Data: {PREDICTIONS_FILE}")
        print()
        print("Usage:")
        print('  predict <event> <expected> <confidence>  — log a prediction')
        print('  outcome <event> <actual>                 — record what happened')
        print("  calibration                              — show calibration stats")
        print("  list                                     — show all predictions")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "predict" and len(sys.argv) >= 5:
        predict(sys.argv[2], sys.argv[3], float(sys.argv[4]))

    elif cmd == "outcome" and len(sys.argv) >= 4:
        outcome(sys.argv[2], sys.argv[3])

    elif cmd == "calibration":
        stats = calibration()
        print(f"Predictions: {stats['total']} ({stats.get('resolved', 0)} resolved)")
        if stats.get("brier_score") is not None and stats["resolved"] > 0:
            print(f"Brier score: {stats['brier_score']} (lower = better)")
        for name, data in stats.get("buckets", {}).items():
            print(f"  {name}: {data['correct']}/{data['total']} = {data['accuracy']:.0%} accurate")

    elif cmd == "list":
        for entry in _load_predictions():
            status = ""
            if entry["correct"] is True:
                status = " ✓"
            elif entry["correct"] is False:
                status = " ✗"
            else:
                status = " ?"
            print(f"  {entry['event']}: '{entry['expected']}' @ {entry['confidence']:.0%}{status}")

    else:
        print(f"Unknown command: {cmd}")
        print("Try: predict, outcome, calibration, list")
