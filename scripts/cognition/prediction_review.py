#!/usr/bin/env python3
"""
Prediction Review — Analyze prediction outcomes by domain.
When predictions are consistently wrong in a domain, auto-generate
a QUEUE.md task to investigate why.

Used by cron_evolution.sh for self-improvement feedback loop.
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

PREDICTIONS_FILE = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "data/calibration/predictions.jsonl")
QUEUE_FILE = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "memory/evolution/QUEUE.md")
REVIEW_STATE_FILE = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "data/calibration/review_state.json")

# Domain classification keywords — map event name patterns to domains
DOMAIN_PATTERNS = {
    "bug_fix": [r"[Ff]ix[\s_]", r"[Bb]ug"],
    "integration": [r"[Ww]ire", r"[Ii]ntegrat", r"[Hh]ook"],
    "new_capability": [r"[Bb]uild[\s_]", r"[Cc]reate[\s_]", r"[Ii]mplement"],
    "analysis": [r"[Rr]eview", r"[Aa]nalyz", r"[Aa]ssess", r"[Rr]un[\s_]"],
    "optimization": [r"[Oo]ptimiz", r"[Rr]efactor", r"[Ii]mprov"],
    "research": [r"[Rr]esearch", r"[Ss]tudy", r"[Aa]nalysis"],
}


def classify_domain(event_name: str) -> str:
    """Classify a prediction event into a domain based on its name."""
    for domain, patterns in DOMAIN_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, event_name):
                return domain
    return "general"


def load_predictions() -> list:
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


def load_review_state() -> dict:
    """Load previous review state to avoid duplicate queue entries."""
    if os.path.exists(REVIEW_STATE_FILE):
        with open(REVIEW_STATE_FILE, "r") as f:
            return json.load(f)
    return {"alerted_domains": {}, "last_review": None}


def save_review_state(state: dict):
    """Save review state."""
    os.makedirs(os.path.dirname(REVIEW_STATE_FILE), exist_ok=True)
    with open(REVIEW_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def analyze_by_domain(predictions: list) -> dict:
    """
    Group resolved predictions by domain, compute per-domain stats.

    Returns:
        Dict of domain -> {total, correct, wrong, accuracy, avg_confidence, failures: [...]}
    """
    resolved = [p for p in predictions if p.get("correct") is not None]
    domains = defaultdict(lambda: {
        "total": 0, "correct": 0, "wrong": 0,
        "confidences": [], "failures": []
    })

    for p in resolved:
        domain = classify_domain(p["event"])
        domains[domain]["total"] += 1
        domains[domain]["confidences"].append(p["confidence"])
        if p["correct"]:
            domains[domain]["correct"] += 1
        else:
            domains[domain]["wrong"] += 1
            domains[domain]["failures"].append({
                "event": p["event"],
                "expected": p["expected"],
                "confidence": p["confidence"],
                "timestamp": p.get("timestamp", ""),
            })

    # Compute derived stats
    result = {}
    for domain, data in domains.items():
        accuracy = data["correct"] / data["total"] if data["total"] > 0 else 1.0
        avg_conf = sum(data["confidences"]) / len(data["confidences"]) if data["confidences"] else 0
        result[domain] = {
            "total": data["total"],
            "correct": data["correct"],
            "wrong": data["wrong"],
            "accuracy": round(accuracy, 3),
            "avg_confidence": round(avg_conf, 3),
            "failures": data["failures"],
        }

    return result


def find_problem_domains(domain_stats: dict, min_predictions: int = 3, max_accuracy: float = 0.6) -> list:
    """
    Find domains where predictions are consistently wrong.

    Args:
        domain_stats: Output of analyze_by_domain()
        min_predictions: Minimum predictions in a domain before we flag it
        max_accuracy: Accuracy below this threshold triggers an alert

    Returns:
        List of (domain, stats) tuples for problem domains
    """
    problems = []
    for domain, stats in domain_stats.items():
        if stats["total"] >= min_predictions and stats["accuracy"] <= max_accuracy:
            problems.append((domain, stats))

    # Sort by accuracy ascending (worst first)
    problems.sort(key=lambda x: x[1]["accuracy"])
    return problems


def generate_queue_task(domain: str, stats: dict) -> str:
    """Generate a QUEUE.md task entry for a problem domain."""
    failure_events = [f["event"][:50] for f in stats["failures"][:3]]
    failures_str = ", ".join(failure_events)
    return (
        f"- [ ] Investigate prediction failures in '{domain}' domain — "
        f"accuracy {stats['accuracy']:.0%} ({stats['wrong']}/{stats['total']} wrong). "
        f"Avg confidence was {stats['avg_confidence']:.0%}. "
        f"Failed tasks: {failures_str}. "
        f"Analyze root causes: are tasks too hard, predictions miscalibrated, or domain needs new approach?"
    )


def append_to_queue(tasks: list[str]):
    """Append auto-generated tasks to QUEUE.md under P1 via shared queue_writer."""
    if not tasks:
        return
    # Strip leading "- [ ] " if already present in task strings
    import re
    clean_tasks = [re.sub(r'^- \[[ x]\] ', '', t).strip() for t in tasks]
    try:
        from clarvis.queue.writer import add_tasks
        added = add_tasks(clean_tasks, priority="P1", source="prediction-review")
        if added:
            print(f"  Injected {len(added)} prediction-review tasks into QUEUE.md")
    except ImportError:
        # Fallback: direct write
        with open(QUEUE_FILE, "r") as f:
            content = f.read()
        header = "### Auto-generated " + datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if "## P1" in content:
            p1_idx = content.index("## P1")
            nl = content.index("\n", p1_idx)
            block = f"\n{header} (prediction-review)\n" + "\n".join(tasks) + "\n"
            content = content[:nl + 1] + block + content[nl + 1:]
        else:
            content += f"\n## P1 — This Week\n\n{header} (prediction-review)\n" + "\n".join(tasks) + "\n"
        with open(QUEUE_FILE, "w") as f:
            f.write(content)


def review_and_generate() -> dict:
    """
    Main entry point: review predictions, find problem domains,
    generate queue tasks for investigation.

    Returns:
        Summary dict with findings and actions taken.
    """
    predictions = load_predictions()
    state = load_review_state()

    domain_stats = analyze_by_domain(predictions)
    problems = find_problem_domains(domain_stats)

    # Filter out domains we've already alerted about recently
    new_problems = []
    for domain, stats in problems:
        last_alert = state["alerted_domains"].get(domain)
        if last_alert:
            # Don't re-alert within 7 days unless new failures occurred
            last_wrong = last_alert.get("wrong_count", 0)
            if stats["wrong"] <= last_wrong:
                continue  # No new failures since last alert
        new_problems.append((domain, stats))

    # Generate queue tasks for new problems
    tasks = []
    for domain, stats in new_problems:
        task = generate_queue_task(domain, stats)
        tasks.append(task)
        state["alerted_domains"][domain] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "wrong_count": stats["wrong"],
            "accuracy": stats["accuracy"],
        }

    if tasks:
        append_to_queue(tasks)

    state["last_review"] = datetime.now(timezone.utc).isoformat()
    save_review_state(state)

    # Store review in brain
    try:
        from brain import brain
        summary_parts = []
        for domain, stats in domain_stats.items():
            summary_parts.append(f"{domain}: {stats['accuracy']:.0%} ({stats['total']} predictions)")
        brain.store(
            f"Prediction review: {', '.join(summary_parts)}. "
            f"Problem domains: {[d for d, _ in new_problems] or 'none'}. "
            f"Tasks generated: {len(tasks)}.",
            collection="clarvis-memories",
            importance=0.6,
            tags=["prediction", "calibration", "self-improvement"],
            source="prediction_review",
        )
    except Exception:
        pass

    return {
        "total_predictions": len(predictions),
        "resolved": len([p for p in predictions if p.get("correct") is not None]),
        "domains": domain_stats,
        "problem_domains": [(d, s) for d, s in new_problems],
        "tasks_generated": len(tasks),
        "tasks": tasks,
    }


# CLI
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "domains":
        # Just show domain stats
        predictions = load_predictions()
        stats = analyze_by_domain(predictions)
        for domain, data in sorted(stats.items(), key=lambda x: x[1]["accuracy"]):
            status = "OK" if data["accuracy"] > 0.6 else "PROBLEM"
            print(f"  {domain}: {data['accuracy']:.0%} accuracy ({data['correct']}/{data['total']}) [{status}]")
    elif len(sys.argv) > 1 and sys.argv[1] == "classify":
        # Classify all predictions for debugging
        predictions = load_predictions()
        for p in predictions:
            domain = classify_domain(p["event"])
            correct = "?" if p["correct"] is None else ("Y" if p["correct"] else "N")
            print(f"  [{domain}] {correct} {p['event'][:60]}")
    else:
        # Full review with queue generation
        result = review_and_generate()
        print("Prediction Review Complete:")
        print(f"  Total: {result['total_predictions']} ({result['resolved']} resolved)")
        print(f"  Domains analyzed: {len(result['domains'])}")
        for domain, stats in result["domains"].items():
            marker = " *** PROBLEM" if stats["accuracy"] <= 0.6 and stats["total"] >= 3 else ""
            print(f"    {domain}: {stats['accuracy']:.0%} ({stats['correct']}/{stats['total']}){marker}")
        if result["tasks_generated"] > 0:
            print(f"  Auto-generated {result['tasks_generated']} investigation task(s) in QUEUE.md")
            for t in result["tasks"]:
                print(f"    {t[:100]}...")
        else:
            print("  No problem domains found — all domains performing well")
