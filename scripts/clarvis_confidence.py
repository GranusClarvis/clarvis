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


def predict_specific(domain: str) -> dict | None:
    """Generate a domain-specific prediction with real uncertainty.

    Instead of predicting "will this task succeed" (almost always yes),
    predict specific measurable outcomes where failure is plausible.

    Args:
        domain: One of 'retrieval', 'phi', 'procedure', 'chain', 'calibration'

    Returns:
        Prediction entry dict, or None if domain unknown.
    """
    import random

    generators = {
        "retrieval": lambda: predict(
            "retrieval_quality_improvement",
            "avg_distance_below_1.0",
            max(0.3, min(0.8, dynamic_confidence() - 0.1)),
        ),
        "phi": lambda: predict(
            "phi_increase_next_measurement",
            "phi_higher_than_previous",
            max(0.3, min(0.7, dynamic_confidence() - 0.15)),
        ),
        "procedure": lambda: predict(
            "procedure_reuse_next_cycle",
            "at_least_one_procedure_matched",
            max(0.2, min(0.6, 0.3 + random.uniform(0, 0.2))),
        ),
        "chain": lambda: predict(
            "reasoning_chain_outcome_recorded",
            "chain_closed_with_outcome",
            max(0.4, min(0.8, dynamic_confidence() - 0.05)),
        ),
        "calibration": lambda: predict(
            "brier_score_below_0.1",
            "brier_under_threshold",
            max(0.3, min(0.7, 0.5)),
        ),
    }

    gen = generators.get(domain)
    if gen:
        return gen()
    return None


def dynamic_confidence(event: str = "") -> float:
    """
    Calculate what confidence to use for the next prediction based on
    historical calibration data. Adjusts toward actual success rate.

    Strategy:
    - Start with base rate from historical outcomes
    - Apply Bayesian shrinkage toward 0.7 when sample size is small
    - Cap at 0.95 (never be 100% sure) and floor at 0.3

    Returns:
        float: Recommended confidence for next prediction (0.3-0.95)
    """
    entries = _load_predictions()
    resolved = [e for e in entries if e["correct"] is not None]

    if len(resolved) < 3:
        return 0.7  # Not enough data, use conservative default

    # Overall success rate
    successes = sum(1 for e in resolved if e["correct"])
    success_rate = successes / len(resolved)

    # Bayesian shrinkage: blend observed rate with prior (0.7)
    # As sample size grows, trust observed rate more
    prior = 0.7
    prior_weight = 5  # equivalent to 5 pseudo-observations
    n = len(resolved)
    blended = (success_rate * n + prior * prior_weight) / (n + prior_weight)

    # Calculate calibration gap: how far off are current predictions?
    avg_confidence = sum(e["confidence"] for e in resolved) / len(resolved)
    gap = success_rate - avg_confidence  # positive = underconfident

    # Adjust: move toward closing the gap (but only partially — be conservative)
    adjusted = avg_confidence + gap * 0.6

    # Final: blend Bayesian estimate with gap-adjusted estimate
    final = (blended + adjusted) / 2

    # Clamp to reasonable range
    final = max(0.3, min(0.95, final))

    return round(final, 2)


def review() -> dict:
    """
    Deep calibration review with curve analysis and recommendations.
    Returns structured analysis for storing in brain.
    """
    entries = _load_predictions()
    resolved = [e for e in entries if e["correct"] is not None]

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_predictions": len(entries),
        "resolved": len(resolved),
        "unresolved": len(entries) - len(resolved),
    }

    if not resolved:
        result["diagnosis"] = "No resolved predictions yet"
        result["recommendation"] = "Keep making predictions, review after 10+"
        return result

    # Basic stats
    successes = sum(1 for e in resolved if e["correct"])
    failures = len(resolved) - successes
    success_rate = successes / len(resolved)
    avg_confidence = sum(e["confidence"] for e in resolved) / len(resolved)

    result["success_rate"] = round(success_rate, 3)
    result["failure_rate"] = round(1 - success_rate, 3)
    result["avg_confidence"] = round(avg_confidence, 3)

    # Brier score
    brier = sum(
        (e["confidence"] - (1.0 if e["correct"] else 0.0)) ** 2 for e in resolved
    ) / len(resolved)
    result["brier_score"] = round(brier, 4)

    # Calibration curve: confidence vs actual outcome in buckets
    buckets = [
        ("0-20%", 0.0, 0.2),
        ("20-40%", 0.2, 0.4),
        ("40-60%", 0.4, 0.6),
        ("60-80%", 0.6, 0.8),
        ("80-100%", 0.8, 1.01),
    ]
    curve = {}
    for label, lo, hi in buckets:
        in_bucket = [e for e in resolved if lo <= e["confidence"] < hi]
        if in_bucket:
            actual = sum(1 for e in in_bucket if e["correct"]) / len(in_bucket)
            midpoint = (lo + min(hi, 1.0)) / 2
            curve[label] = {
                "count": len(in_bucket),
                "predicted_avg": round(midpoint, 2),
                "actual_rate": round(actual, 3),
                "gap": round(actual - midpoint, 3),
            }
    result["calibration_curve"] = curve

    # Diagnose
    gap = success_rate - avg_confidence
    if gap > 0.15:
        diagnosis = "UNDERCONFIDENT"
        detail = f"Predicting {avg_confidence:.0%} but succeeding {success_rate:.0%} of the time (+{gap:.0%} gap)"
    elif gap < -0.15:
        diagnosis = "OVERCONFIDENT"
        detail = f"Predicting {avg_confidence:.0%} but only succeeding {success_rate:.0%} ({gap:.0%} gap)"
    else:
        diagnosis = "WELL_CALIBRATED"
        detail = f"Confidence {avg_confidence:.0%} vs actual {success_rate:.0%} — close match"

    result["diagnosis"] = diagnosis
    result["detail"] = detail

    # Recommendation
    recommended = dynamic_confidence()
    result["recommended_confidence"] = recommended
    result["current_default"] = avg_confidence

    if diagnosis == "UNDERCONFIDENT":
        result["recommendation"] = f"Raise default confidence from {avg_confidence:.0%} to {recommended:.0%}"
        result["action"] = "threshold_raised"
    elif diagnosis == "OVERCONFIDENT":
        result["recommendation"] = f"Lower default confidence from {avg_confidence:.0%} to {recommended:.0%}"
        result["action"] = "threshold_lowered"
    else:
        result["recommendation"] = f"Maintain current confidence ~{recommended:.0%}"
        result["action"] = "maintain"

    return result


THRESHOLDS_FILE = f"{CALIBRATION_DIR}/thresholds.json"


def save_threshold(confidence: float, reason: str):
    """Save the current dynamic threshold for cron_autonomous.sh to read."""
    data = {
        "confidence": confidence,
        "reason": reason,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    with open(THRESHOLDS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def load_threshold() -> float:
    """Load the saved dynamic threshold. Falls back to 0.7 if none saved."""
    if os.path.exists(THRESHOLDS_FILE):
        with open(THRESHOLDS_FILE, "r") as f:
            data = json.load(f)
            return data.get("confidence", 0.7)
    return 0.7


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

    elif cmd == "review":
        result = review()
        print(f"=== Calibration Review ===")
        print(f"Predictions: {result['total_predictions']} ({result['resolved']} resolved)")
        if result['resolved'] > 0:
            print(f"Success rate: {result.get('success_rate', 0):.0%}")
            print(f"Avg confidence: {result.get('avg_confidence', 0):.0%}")
            print(f"Brier score: {result.get('brier_score', 'N/A')}")
            print(f"Diagnosis: {result.get('diagnosis', 'N/A')}")
            print(f"  {result.get('detail', '')}")
            print(f"Recommendation: {result.get('recommendation', '')}")
            print(f"New threshold: {result.get('recommended_confidence', 0.7)}")
            curve = result.get("calibration_curve", {})
            if curve:
                print(f"\nCalibration curve:")
                for label, data in curve.items():
                    bar = "#" * int(data["actual_rate"] * 20)
                    print(f"  {label}: predicted={data['predicted_avg']:.0%} actual={data['actual_rate']:.0%} (n={data['count']}) {bar}")

    elif cmd == "dynamic":
        conf = dynamic_confidence()
        print(f"{conf}")

    elif cmd == "apply":
        # Run review and save the new threshold
        result = review()
        new_conf = result.get("recommended_confidence", 0.7)
        reason = result.get("recommendation", "calibration review")
        saved = save_threshold(new_conf, reason)
        print(f"Threshold updated to {new_conf} — {reason}")
        # Store insight in brain
        _brain_store(
            f"Calibration review ({result.get('diagnosis', 'unknown')}): "
            f"success_rate={result.get('success_rate', 'N/A')}, "
            f"avg_confidence={result.get('avg_confidence', 'N/A')}, "
            f"brier={result.get('brier_score', 'N/A')}. "
            f"Adjusted threshold to {new_conf}.",
            importance=0.7,
        )

    elif cmd == "threshold":
        t = load_threshold()
        print(f"{t}")

    elif cmd == "predict-specific":
        domain = sys.argv[2] if len(sys.argv) > 2 else ""
        if domain:
            result = predict_specific(domain)
            if result:
                print(f"Logged specific prediction for domain '{domain}'")
            else:
                print(f"Unknown domain: {domain}. Try: retrieval, phi, procedure, chain, calibration")
        else:
            # Generate predictions for all domains
            domains = ["retrieval", "phi", "procedure", "chain", "calibration"]
            for d in domains:
                result = predict_specific(d)
                if result:
                    print(f"  {d}: predicted '{result['expected']}' @ {result['confidence']:.0%}")

    else:
        print(f"Unknown command: {cmd}")
        print("Try: predict, outcome, calibration, list, review, dynamic, apply, threshold, predict-specific")
