#!/usr/bin/env python3
"""
Decision Event Bus — Log important decisions with evidence and outcomes.

Every significant decision (task selection, architecture choice, parameter change,
discard/keep) gets logged with:
  - evidence: what information was available
  - reasoning: why this choice was made
  - confidence: 0.0-1.0 how certain we were
  - outcome: recorded later when results are known

This enables learning from decisions, not just task results.

Usage:
    python3 decision_event_bus.py log "chose X over Y" --evidence "metric was 0.4" --confidence 0.8
    python3 decision_event_bus.py outcome <decision_id> --result "success" --notes "metric improved to 0.7"
    python3 decision_event_bus.py review             # Show recent decisions + outcomes
    python3 decision_event_bus.py learn              # Analyze decision quality patterns
    python3 decision_event_bus.py stats              # Disposition/confidence stats

Data: data/decisions.jsonl
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DECISIONS_FILE = Path(WORKSPACE) / "data" / "decisions.jsonl"

# Decision categories
CATEGORIES = (
    "task_selection",    # Which task to work on
    "architecture",      # Design/structure choices
    "parameter",         # Threshold/config changes
    "discard",           # Chose NOT to do something
    "strategy",          # High-level approach decisions
    "other",
)


def log_decision(description, evidence=None, reasoning=None, confidence=0.5,
                 category="other", context=None):
    """Log a decision with evidence and reasoning.

    Args:
        description: What was decided
        evidence: What information was available (list of strings or single string)
        reasoning: Why this choice was made
        confidence: 0.0-1.0 certainty level
        category: One of CATEGORIES
        context: Optional dict of extra context (task_id, metric values, etc.)

    Returns:
        decision_id (str)
    """
    decision_id = f"dec_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    if isinstance(evidence, str):
        evidence = [evidence]

    entry = {
        "id": decision_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": description,
        "evidence": evidence or [],
        "reasoning": reasoning or "",
        "confidence": max(0.0, min(1.0, float(confidence))),
        "category": category if category in CATEGORIES else "other",
        "context": context or {},
        "outcome": None,
        "outcome_recorded_at": None,
        "outcome_notes": None,
    }

    DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DECISIONS_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    return decision_id


def record_outcome(decision_id, result, notes=None, learned=None):
    """Record the outcome of a previous decision.

    Args:
        decision_id: ID from log_decision()
        result: "success", "failure", "partial", or "neutral"
        notes: What happened
        learned: What we learned from this outcome

    Returns:
        True if decision was found and updated, False otherwise.
    """
    if not DECISIONS_FILE.exists():
        return False

    entries = _load_all()
    found = False
    for entry in entries:
        if entry.get("id") == decision_id:
            entry["outcome"] = result
            entry["outcome_recorded_at"] = datetime.now(timezone.utc).isoformat()
            entry["outcome_notes"] = notes
            if learned:
                entry["learned"] = learned
            found = True
            break

    if found:
        _save_all(entries)
    return found


def review(n=10):
    """Show recent decisions with their outcomes."""
    entries = _load_all()
    if not entries:
        return []
    # Most recent first
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entries[:n]


def learn():
    """Analyze decision quality patterns.

    Returns dict with:
      - calibration: how well confidence predicts success
      - category_success: success rate by category
      - overconfident: decisions where high confidence led to failure
      - underconfident: decisions where low confidence led to success
    """
    entries = _load_all()
    with_outcome = [e for e in entries if e.get("outcome")]

    if not with_outcome:
        return {"message": "No outcomes recorded yet", "total": len(entries)}

    # Calibration: bin by confidence, measure success rate
    bins = {"low": [], "mid": [], "high": []}
    for e in with_outcome:
        conf = e.get("confidence", 0.5)
        success = 1 if e.get("outcome") == "success" else 0
        if conf < 0.4:
            bins["low"].append(success)
        elif conf < 0.7:
            bins["mid"].append(success)
        else:
            bins["high"].append(success)

    calibration = {}
    for level, outcomes in bins.items():
        if outcomes:
            calibration[level] = {
                "count": len(outcomes),
                "success_rate": sum(outcomes) / len(outcomes),
            }

    # Success rate by category
    cat_stats = {}
    for e in with_outcome:
        cat = e.get("category", "other")
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "success": 0}
        cat_stats[cat]["total"] += 1
        if e.get("outcome") == "success":
            cat_stats[cat]["success"] += 1

    for cat in cat_stats:
        t = cat_stats[cat]["total"]
        cat_stats[cat]["rate"] = cat_stats[cat]["success"] / t if t else 0

    # Mis-calibrated decisions
    overconfident = [
        e for e in with_outcome
        if e.get("confidence", 0) >= 0.7 and e.get("outcome") == "failure"
    ]
    underconfident = [
        e for e in with_outcome
        if e.get("confidence", 0) <= 0.3 and e.get("outcome") == "success"
    ]

    return {
        "total_decisions": len(entries),
        "with_outcome": len(with_outcome),
        "calibration": calibration,
        "category_success": cat_stats,
        "overconfident_count": len(overconfident),
        "underconfident_count": len(underconfident),
    }


def stats():
    """Quick disposition stats."""
    entries = _load_all()
    if not entries:
        return {"total": 0}

    by_cat = {}
    by_outcome = {}
    confidences = []
    for e in entries:
        cat = e.get("category", "other")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        outcome = e.get("outcome")
        if outcome:
            by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        confidences.append(e.get("confidence", 0.5))

    return {
        "total": len(entries),
        "by_category": by_cat,
        "by_outcome": by_outcome,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
        "outcome_rate": len([e for e in entries if e.get("outcome")]) / len(entries),
    }


def _load_all():
    """Load all decision entries."""
    if not DECISIONS_FILE.exists():
        return []
    entries = []
    with open(DECISIONS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def _save_all(entries):
    """Rewrite all entries (used for outcome updates)."""
    with open(DECISIONS_FILE, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, default=str) + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: decision_event_bus.py log|outcome|review|learn|stats")
        print()
        print("Commands:")
        print("  log <description> [--evidence E] [--reasoning R] [--confidence C] [--category CAT]")
        print("  outcome <decision_id> --result success|failure|partial|neutral [--notes N] [--learned L]")
        print("  review [--n N]          Show recent decisions")
        print("  learn                   Analyze decision quality patterns")
        print("  stats                   Quick stats")
        sys.exit(1)

    cmd = sys.argv[1]

    def _get_arg(flag, default=None):
        for i, a in enumerate(sys.argv):
            if a == flag and i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        return default

    if cmd == "log":
        if len(sys.argv) < 3:
            print("Usage: decision_event_bus.py log <description> [--evidence E] [--confidence C]")
            sys.exit(1)
        desc = sys.argv[2]
        evidence = _get_arg("--evidence")
        reasoning = _get_arg("--reasoning")
        confidence = float(_get_arg("--confidence", "0.5"))
        category = _get_arg("--category", "other")
        did = log_decision(desc, evidence=evidence, reasoning=reasoning,
                           confidence=confidence, category=category)
        print(f"Logged decision: {did}")

    elif cmd == "outcome":
        if len(sys.argv) < 3:
            print("Usage: decision_event_bus.py outcome <decision_id> --result R [--notes N]")
            sys.exit(1)
        did = sys.argv[2]
        result = _get_arg("--result", "neutral")
        notes = _get_arg("--notes")
        learned = _get_arg("--learned")
        ok = record_outcome(did, result, notes=notes, learned=learned)
        if ok:
            print(f"Outcome recorded for {did}: {result}")
        else:
            print(f"Decision {did} not found", file=sys.stderr)
            sys.exit(1)

    elif cmd == "review":
        n = int(_get_arg("--n", "10"))
        decisions = review(n)
        if not decisions:
            print("No decisions logged yet.")
            return
        for d in decisions:
            outcome_str = f" -> {d['outcome']}" if d.get("outcome") else " (pending)"
            print(f"[{d['id']}] [{d['category']}] conf={d['confidence']:.1f}{outcome_str}")
            print(f"  {d['description']}")
            if d.get("evidence"):
                print(f"  Evidence: {', '.join(d['evidence'][:3])}")
            if d.get("outcome_notes"):
                print(f"  Notes: {d['outcome_notes']}")
            print()

    elif cmd == "learn":
        result = learn()
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        result = stats()
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
