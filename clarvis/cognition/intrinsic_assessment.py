"""Intrinsic Self-Assessment — performance evaluation, failure pattern detection, autocurriculum.

Evaluates agent performance after tasks, detects recurring failure patterns,
and generates self-remediation tasks (autocurriculum) from failure clusters.

Integrates with:
  - episodes.json (task outcomes)
  - meta_learning analysis (strategy effectiveness, failure clusters)
  - prediction calibration (confidence accuracy)
  - self_model (capability domain scores)

Reference: Absolute Zero (self-play reasoning) + Intrinsic Motivation literature.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

_log = logging.getLogger("clarvis.cognition.intrinsic_assessment")

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
EPISODES_PATH = os.path.join(WORKSPACE, "data", "episodes.json")
ASSESSMENT_PATH = os.path.join(WORKSPACE, "data", "intrinsic_assessment.json")
AUTOCURRICULUM_PATH = os.path.join(WORKSPACE, "data", "autocurriculum.json")
QUEUE_PATH = os.path.join(WORKSPACE, "QUEUE.md")


def _load_episodes(days: int = 7) -> list[dict]:
    """Load recent episodes within the given time window."""
    try:
        with open(EPISODES_PATH) as f:
            episodes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [ep for ep in episodes if ep.get("timestamp", "") >= cutoff]


def _load_meta_analysis() -> dict:
    """Load latest meta-learning analysis."""
    path = os.path.join(WORKSPACE, "data", "meta_learning", "analysis.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _classify_failure(ep: dict) -> str | None:
    """Classify a failed episode into a failure category."""
    error = (ep.get("error") or "").lower()
    task = (ep.get("task") or "").lower()

    if ep.get("outcome") not in ("failure", "timeout", "soft_failure"):
        return None

    if ep.get("outcome") == "timeout":
        return "timeout"
    if "import" in error:
        return "import_error"
    if any(w in error for w in ("chromadb", "brain", "recall", "embed")):
        return "memory_error"
    if any(w in error for w in ("permission", "access", "denied")):
        return "permission_error"
    if any(w in error for w in ("syntax", "indent", "parse")):
        return "syntax_error"
    if error:
        return "runtime_error"
    return "unknown"


def assess_recent(days: int = 7) -> dict:
    """Evaluate recent performance across multiple dimensions.

    Returns:
        Dict with dimension scores, failure patterns, and overall health.
    """
    episodes = _load_episodes(days)
    if not episodes:
        return {"status": "no_data", "episodes": 0}

    # --- Dimension 1: Success Rate ---
    outcomes = Counter(ep.get("outcome", "unknown") for ep in episodes)
    total = len(episodes)
    successes = outcomes.get("success", 0)
    success_rate = successes / total if total > 0 else 0.0

    # --- Dimension 2: Failure Pattern Concentration ---
    failures = [ep for ep in episodes if ep.get("outcome") != "success"]
    failure_classes = Counter(
        _classify_failure(ep) for ep in failures
    )
    failure_classes.pop(None, None)

    # Concentration: how many failure types dominate (1.0 = all same type, 0.0 = evenly spread)
    if failure_classes:
        top_count = failure_classes.most_common(1)[0][1]
        fail_concentration = top_count / sum(failure_classes.values())
    else:
        fail_concentration = 0.0

    # --- Dimension 3: Efficiency (avg duration for successes vs failures) ---
    success_durations = [
        ep.get("duration_s", 0) for ep in episodes
        if ep.get("outcome") == "success" and ep.get("duration_s")
    ]
    failure_durations = [
        ep.get("duration_s", 0) for ep in episodes
        if ep.get("outcome") != "success" and ep.get("duration_s")
    ]
    avg_success_dur = sum(success_durations) / len(success_durations) if success_durations else 0
    avg_failure_dur = sum(failure_durations) / len(failure_durations) if failure_durations else 0

    # --- Dimension 4: Improvement Trend (compare first half to second half) ---
    mid = total // 2
    if mid > 0:
        first_half_rate = sum(
            1 for ep in episodes[:mid] if ep.get("outcome") == "success"
        ) / mid
        second_half_rate = sum(
            1 for ep in episodes[mid:] if ep.get("outcome") == "success"
        ) / (total - mid)
        trend = second_half_rate - first_half_rate
    else:
        trend = 0.0

    # --- Dimension 5: Recurring Failures (same task pattern failing repeatedly) ---
    task_failures = defaultdict(int)
    for ep in failures:
        # Extract action verb as pattern key
        task = ep.get("task", "")
        match = re.match(r'^(\w+)\s', task)
        prefix = match.group(1).lower() if match else "unknown"
        task_failures[prefix] += 1
    recurring = {k: v for k, v in task_failures.items() if v >= 2}

    # --- Composite Score ---
    score = (
        0.40 * success_rate
        + 0.20 * (1.0 - fail_concentration)
        + 0.15 * max(0, min(1.0, 1.0 - avg_failure_dur / 600))
        + 0.15 * max(0, min(1.0, 0.5 + trend))
        + 0.10 * (1.0 if not recurring else max(0, 1.0 - len(recurring) * 0.2))
    )

    assessment = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "days_window": days,
        "episodes_total": total,
        "composite_score": round(score, 3),
        "dimensions": {
            "success_rate": round(success_rate, 3),
            "failure_concentration": round(fail_concentration, 3),
            "avg_success_duration_s": round(avg_success_dur, 1),
            "avg_failure_duration_s": round(avg_failure_dur, 1),
            "improvement_trend": round(trend, 3),
            "recurring_failures": recurring,
        },
        "outcome_counts": dict(outcomes),
        "failure_classes": dict(failure_classes),
    }

    # Persist
    try:
        os.makedirs(os.path.dirname(ASSESSMENT_PATH), exist_ok=True)
        with open(ASSESSMENT_PATH, "w") as f:
            json.dump(assessment, f, indent=2)
    except Exception as exc:
        _log.warning("Failed to save assessment: %s", exc)

    return assessment


def detect_failure_patterns(days: int = 14) -> list[dict]:
    """Detect recurring failure patterns that warrant autocurriculum tasks.

    Returns patterns sorted by severity (frequency × recency).
    """
    episodes = _load_episodes(days)
    failures = [ep for ep in episodes if ep.get("outcome") != "success"]

    if not failures:
        return []

    # Group by failure class + task verb
    patterns = defaultdict(list)
    for ep in failures:
        fclass = _classify_failure(ep)
        task = ep.get("task", "")
        match = re.match(r'^(\w+)\s', task)
        verb = match.group(1).lower() if match else "unknown"
        key = f"{fclass}:{verb}"
        patterns[key].append(ep)

    result = []
    now = datetime.now(timezone.utc)
    for key, eps in patterns.items():
        if len(eps) < 2:
            continue

        fclass, verb = key.split(":", 1)

        # Recency weight: more recent failures score higher
        latest_ts = max(ep.get("timestamp", "") for ep in eps)
        try:
            latest_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
            days_ago = (now - latest_dt).total_seconds() / 86400
        except (ValueError, TypeError):
            days_ago = 14.0

        severity = len(eps) * max(0.1, 1.0 - days_ago / 14.0)

        # Extract common error snippets
        errors = [ep.get("error", "")[:100] for ep in eps if ep.get("error")]
        common_error = Counter(errors).most_common(1)

        result.append({
            "pattern": key,
            "failure_class": fclass,
            "task_verb": verb,
            "count": len(eps),
            "severity": round(severity, 2),
            "latest": latest_ts[:19],
            "common_error": common_error[0][0] if common_error else None,
            "example_tasks": [ep.get("task", "")[:80] for ep in eps[:3]],
        })

    result.sort(key=lambda p: p["severity"], reverse=True)
    return result


def generate_autocurriculum(max_tasks: int = 5) -> list[dict]:
    """Generate self-remediation tasks from detected failure patterns.

    Each task targets a specific failure pattern with a concrete action plan.
    Tasks are deduped against existing QUEUE.md entries.
    """
    patterns = detect_failure_patterns(days=14)
    if not patterns:
        return []

    # Load existing queue to avoid duplicates
    existing_queue = set()
    try:
        with open(QUEUE_PATH) as f:
            for line in f:
                existing_queue.add(line.strip().lower()[:80])
    except FileNotFoundError:
        pass

    # Template mapping: failure_class → remediation strategy
    remediation_templates = {
        "timeout": "Break '{verb}' tasks into smaller sub-tasks. Recent {count}x timeouts suggest scope too large. Add incremental checkpoints.",
        "import_error": "Fix import chain for '{verb}' tasks. {count}x import failures — verify sys.path and dependencies.",
        "runtime_error": "Add defensive error handling for '{verb}' tasks. {count}x runtime errors — common: {error}",
        "memory_error": "Investigate brain/ChromaDB issues in '{verb}' tasks. {count}x memory errors — check collection health.",
        "permission_error": "Fix file/process permissions for '{verb}' tasks. {count}x permission errors.",
        "syntax_error": "Improve code generation quality for '{verb}' tasks. {count}x syntax errors — add validation before write.",
        "unknown": "Investigate recurring failures in '{verb}' tasks ({count}x). Root cause unclear — add better error capture.",
    }

    tasks = []
    for pattern in patterns[:max_tasks]:
        template = remediation_templates.get(
            pattern["failure_class"],
            remediation_templates["unknown"],
        )
        task_text = template.format(
            verb=pattern["task_verb"],
            count=pattern["count"],
            error=(pattern["common_error"] or "various")[:60],
        )

        # Skip if already in queue
        if task_text.lower()[:80] in existing_queue:
            continue

        tasks.append({
            "task": task_text,
            "priority": "P1" if pattern["severity"] > 3.0 else "P2",
            "source": "autocurriculum",
            "pattern": pattern["pattern"],
            "severity": pattern["severity"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    # Persist autocurriculum
    try:
        os.makedirs(os.path.dirname(AUTOCURRICULUM_PATH), exist_ok=True)
        with open(AUTOCURRICULUM_PATH, "w") as f:
            json.dump({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "tasks": tasks,
                "patterns_analyzed": len(patterns),
            }, f, indent=2)
    except Exception as exc:
        _log.warning("Failed to save autocurriculum: %s", exc)

    return tasks


def inject_autocurriculum(dry_run: bool = False) -> dict:
    """Generate autocurriculum tasks and inject them into QUEUE.md.

    Args:
        dry_run: If True, don't write to QUEUE.md, just return what would be injected.

    Returns:
        Dict with injected tasks and count.
    """
    tasks = generate_autocurriculum()
    if not tasks:
        return {"injected": 0, "tasks": []}

    if not dry_run:
        try:
            with open(QUEUE_PATH, "a") as f:
                f.write("\n## Autocurriculum (self-generated)\n")
                for t in tasks:
                    f.write(f"- [{t['priority']}] {t['task']}\n")
        except Exception as exc:
            _log.warning("Failed to inject into QUEUE.md: %s", exc)

    return {"injected": len(tasks), "tasks": tasks}


def full_assessment(days: int = 7) -> dict:
    """Run complete self-assessment: evaluate performance + detect patterns + generate curriculum.

    Returns combined results.
    """
    assessment = assess_recent(days)
    patterns = detect_failure_patterns(days=14)
    curriculum = generate_autocurriculum()

    result = {
        "assessment": assessment,
        "failure_patterns": patterns[:10],
        "autocurriculum": curriculum,
        "summary": _generate_summary(assessment, patterns, curriculum),
    }

    return result


def _generate_summary(assessment: dict, patterns: list, curriculum: list) -> str:
    """Generate a human-readable summary of the self-assessment."""
    if assessment.get("status") == "no_data":
        return "No recent episodes to assess."

    score = assessment.get("composite_score", 0)
    rate = assessment.get("dimensions", {}).get("success_rate", 0)
    trend = assessment.get("dimensions", {}).get("improvement_trend", 0)
    total = assessment.get("episodes_total", 0)

    trend_word = "improving" if trend > 0.05 else "declining" if trend < -0.05 else "stable"

    lines = [
        f"Performance: {score:.0%} composite ({total} episodes, {rate:.0%} success rate, {trend_word})",
    ]

    if patterns:
        top = patterns[0]
        lines.append(
            f"Top failure pattern: {top['failure_class']}:{top['task_verb']} "
            f"({top['count']}x, severity {top['severity']:.1f})"
        )

    if curriculum:
        lines.append(f"Generated {len(curriculum)} autocurriculum task(s) for self-remediation.")

    return " | ".join(lines)


# === CLI ===

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "full"

    if cmd == "assess":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        result = assess_recent(days)
        print(json.dumps(result, indent=2))
    elif cmd == "patterns":
        patterns = detect_failure_patterns()
        for p in patterns:
            print(f"  [{p['severity']:.1f}] {p['pattern']} ({p['count']}x)")
    elif cmd == "curriculum":
        tasks = generate_autocurriculum()
        for t in tasks:
            print(f"  [{t['priority']}] {t['task']}")
        if not tasks:
            print("  No autocurriculum tasks needed.")
    elif cmd == "inject":
        dry = "--dry-run" in sys.argv
        result = inject_autocurriculum(dry_run=dry)
        print(f"Injected {result['injected']} tasks")
        for t in result["tasks"]:
            print(f"  [{t['priority']}] {t['task']}")
    elif cmd == "full":
        result = full_assessment()
        print(result["summary"])
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Usage: {sys.argv[0]} [assess|patterns|curriculum|inject|full]")
