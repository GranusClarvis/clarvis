#!/usr/bin/env python3
# STATUS: production-wired via heartbeat_preflight
# (Misclassified as "research prototype with zero callers" in SPINE_USAGE_AUDIT.md §3.2)
"""
Automation Insights — Pattern analysis across episodes to deepen automation.

Analyzes episode history to produce:
1. Success pattern extraction: what makes tasks succeed?
2. Failure pattern warnings: what patterns predict failure?
3. Duration-based complexity hints: task phrasing patterns that predict long runs
4. Domain competence map: which domains are strong/weak
5. Preflight warnings: inject into context brief to prevent known pitfalls

Wired into heartbeat_preflight.py to enrich context with actionable warnings.
"""

import json
import re
import sys
import os
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

EPISODES_FILE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/episodes.json"


def _load_episodes():
    if EPISODES_FILE.exists():
        with open(EPISODES_FILE) as f:
            return json.load(f)
    return []


def _extract_action_verb(task_text):
    """Extract the leading action verb from a task description."""
    if not task_text:
        return ""
    words = task_text.strip().split()
    if not words:
        return ""
    # Skip bracketed tags like [SPAWN_FIX]
    for w in words:
        clean = w.strip("[]()").lower()
        if clean and not clean.startswith("["):
            return clean
    return words[0].lower().strip("[]()")


def _extract_keywords(text, min_len=4):
    """Extract meaningful keywords from text."""
    return set(
        w.lower() for w in re.split(r'[\s\-_/.,;:()]+', text)
        if len(w) >= min_len and w.isalpha()
    )


def analyze_success_patterns(episodes=None):
    """Identify what makes tasks succeed.

    Returns dict with:
    - strong_verbs: action verbs with >70% success rate
    - weak_verbs: action verbs with <50% success rate
    - optimal_duration_range: [p25, p75] of successful task durations
    - success_keywords: keywords that correlate with success
    """
    if episodes is None:
        episodes = _load_episodes()

    # Filter to real executions only
    real = [e for e in episodes if e["outcome"] != "soft_failure"]
    if len(real) < 5:
        return {"insufficient_data": True}

    # Verb analysis
    verb_outcomes = defaultdict(lambda: {"success": 0, "fail": 0})
    for ep in real:
        verb = _extract_action_verb(ep["task"])
        if not verb:
            continue
        if ep["outcome"] == "success":
            verb_outcomes[verb]["success"] += 1
        else:
            verb_outcomes[verb]["fail"] += 1

    strong_verbs = []
    weak_verbs = []
    for verb, counts in verb_outcomes.items():
        total = counts["success"] + counts["fail"]
        if total < 2:
            continue
        rate = counts["success"] / total
        if rate >= 0.7:
            strong_verbs.append((verb, round(rate, 2), total))
        elif rate < 0.5:
            weak_verbs.append((verb, round(rate, 2), total))

    # Duration analysis (successful tasks only)
    success_durations = [
        ep["duration_s"] for ep in real
        if ep["outcome"] == "success" and ep.get("duration_s", 0) > 0
    ]
    if success_durations:
        success_durations.sort()
        n = len(success_durations)
        p25 = success_durations[n // 4] if n >= 4 else success_durations[0]
        p75 = success_durations[3 * n // 4] if n >= 4 else success_durations[-1]
    else:
        p25, p75 = 0, 300

    # Keyword correlation
    success_kws = Counter()
    fail_kws = Counter()
    for ep in real:
        kws = _extract_keywords(ep["task"])
        if ep["outcome"] == "success":
            success_kws.update(kws)
        else:
            fail_kws.update(kws)

    # Keywords that appear mostly in successes
    correlated_success = []
    for kw, count in success_kws.most_common(30):
        fail_count = fail_kws.get(kw, 0)
        total = count + fail_count
        if total >= 2 and count / total >= 0.8:
            correlated_success.append((kw, count, total))

    return {
        "strong_verbs": sorted(strong_verbs, key=lambda x: -x[1])[:10],
        "weak_verbs": sorted(weak_verbs, key=lambda x: x[1])[:10],
        "optimal_duration_range": [p25, p75],
        "success_keywords": correlated_success[:10],
        "total_real_episodes": len(real),
        "success_rate": round(
            sum(1 for e in real if e["outcome"] == "success") / len(real), 2
        ),
    }


def generate_preflight_warnings(task_text, episodes=None):
    """Generate warnings for a specific task based on historical patterns.

    Returns list of warning strings to inject into context brief.
    """
    if episodes is None:
        episodes = _load_episodes()

    warnings = []
    task_kws = _extract_keywords(task_text)
    task_verb = _extract_action_verb(task_text)

    # 1. Check for similar failed tasks
    real = [e for e in episodes if e["outcome"] != "soft_failure"]
    failures = [e for e in real if e["outcome"] in ("failure", "timeout")]
    for fail_ep in failures:
        fail_kws = _extract_keywords(fail_ep["task"])
        overlap = len(task_kws & fail_kws)
        if overlap >= 3:
            err = fail_ep.get("error", "")[:100] if fail_ep.get("error") else "unknown"
            warnings.append(
                f"SIMILAR TASK FAILED BEFORE: '{fail_ep['task'][:80]}' "
                f"(error: {err})"
            )

    # 2. Check verb success rate
    verb_stats = defaultdict(lambda: {"success": 0, "fail": 0})
    for ep in real:
        v = _extract_action_verb(ep["task"])
        if ep["outcome"] == "success":
            verb_stats[v]["success"] += 1
        else:
            verb_stats[v]["fail"] += 1

    if task_verb in verb_stats:
        v = verb_stats[task_verb]
        total = v["success"] + v["fail"]
        rate = v["success"] / total if total else 0
        if total >= 3 and rate < 0.5:
            warnings.append(
                f"LOW SUCCESS VERB: '{task_verb}' tasks succeed only {rate:.0%} "
                f"of the time ({v['success']}/{total})"
            )

    # 3. Check for long-duration patterns
    long_tasks = [
        e for e in real
        if e.get("duration_s", 0) > 300 and e["outcome"] != "success"
    ]
    for lt in long_tasks:
        lt_kws = _extract_keywords(lt["task"])
        if len(task_kws & lt_kws) >= 2:
            warnings.append(
                f"DURATION RISK: Similar task '{lt['task'][:60]}' took "
                f"{lt['duration_s']}s and {lt['outcome']}"
            )
            break

    # 4. Domain-specific advice from soft failures
    soft_failures = [e for e in episodes if e["outcome"] == "soft_failure"]
    relevant_soft = []
    for sf in soft_failures:
        sf_kws = _extract_keywords(sf["task"])
        if len(task_kws & sf_kws) >= 2:
            relevant_soft.append(sf)

    if relevant_soft:
        # Extract unique error patterns
        error_types = set()
        for sf in relevant_soft[:5]:
            err = sf.get("error", "")
            if "shallow_reasoning" in err:
                error_types.add("shallow_reasoning")
            if "long_duration" in err:
                error_types.add("long_duration")

        if "shallow_reasoning" in error_types:
            warnings.append(
                "PATTERN: Similar tasks showed shallow reasoning. "
                "Break into explicit sub-steps before executing."
            )
        if "long_duration" in error_types:
            warnings.append(
                "PATTERN: Similar tasks ran long. Set a hard time limit "
                "and focus on the smallest viable increment."
            )

    return warnings[:4]  # Cap at 4 warnings


def domain_competence_map(episodes=None):
    """Build a competence map: which domains are strong vs weak.

    Returns dict of domain -> {success_rate, total, competence_level}.
    """
    if episodes is None:
        episodes = _load_episodes()

    DOMAINS = {
        "research": ["research", "paper", "read", "study", "survey", "bundle"],
        "implementation": ["implement", "build", "create", "add", "write"],
        "fixing": ["fix", "debug", "repair", "patch", "resolve"],
        "wiring": ["wire", "integrate", "connect", "hook", "link"],
        "optimization": ["optimize", "improve", "boost", "reduce", "speed"],
        "infrastructure": ["cron", "script", "automat", "pipeline", "scheduler"],
    }

    domain_stats = defaultdict(lambda: {"success": 0, "fail": 0, "total": 0})

    real = [e for e in episodes if e["outcome"] != "soft_failure"]
    for ep in real:
        task_lower = ep["task"].lower()
        matched = False
        for domain, keywords in DOMAINS.items():
            if any(kw in task_lower for kw in keywords):
                domain_stats[domain]["total"] += 1
                if ep["outcome"] == "success":
                    domain_stats[domain]["success"] += 1
                else:
                    domain_stats[domain]["fail"] += 1
                matched = True
        if not matched:
            domain_stats["other"]["total"] += 1
            if ep["outcome"] == "success":
                domain_stats["other"]["success"] += 1
            else:
                domain_stats["other"]["fail"] += 1

    result = {}
    for domain, stats in domain_stats.items():
        total = stats["total"]
        if total == 0:
            continue
        rate = stats["success"] / total
        if rate >= 0.8:
            level = "strong"
        elif rate >= 0.6:
            level = "moderate"
        else:
            level = "weak"
        result[domain] = {
            "success_rate": round(rate, 2),
            "total": total,
            "successes": stats["success"],
            "failures": stats["fail"],
            "competence_level": level,
        }

    return result


def format_warnings_for_brief(warnings):
    """Format warnings for injection into context brief."""
    if not warnings:
        return ""
    lines = ["AVOID THESE FAILURE PATTERNS:"]
    for w in warnings:
        lines.append(f"- AVOID: {w}")
    return " ".join(lines)


def format_insights_for_brief(task_text, episodes=None):
    """Single entry point: generate all insights formatted for context brief.

    Returns a compact string suitable for injection into the preflight brief.
    """
    if episodes is None:
        episodes = _load_episodes()

    parts = []

    # Warnings
    warnings = generate_preflight_warnings(task_text, episodes)
    if warnings:
        parts.append(format_warnings_for_brief(warnings))

    # Relevant knowledge from success patterns
    patterns = analyze_success_patterns(episodes)
    if not patterns.get("insufficient_data"):
        # Include only if relevant to the current task
        task_verb = _extract_action_verb(task_text)
        weak = [v for v, rate, _ in patterns.get("weak_verbs", []) if v == task_verb]
        if weak:
            parts.append(
                f"RELEVANT KNOWLEDGE: '{task_verb}' tasks have low success — "
                f"consider breaking into smaller sub-tasks."
            )

    return " ".join(parts) if parts else ""


# CLI interface
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: automation_insights.py <patterns|warnings|competence|brief> [task_text]")
        sys.exit(1)

    cmd = sys.argv[1]
    episodes = _load_episodes()

    if cmd == "patterns":
        result = analyze_success_patterns(episodes)
        print(json.dumps(result, indent=2))

    elif cmd == "warnings":
        task = sys.argv[2] if len(sys.argv) > 2 else "test task"
        warnings = generate_preflight_warnings(task, episodes)
        for w in warnings:
            print(f"  ! {w}")
        if not warnings:
            print("  (no warnings for this task)")

    elif cmd == "competence":
        cmap = domain_competence_map(episodes)
        print(json.dumps(cmap, indent=2))

    elif cmd == "brief":
        task = sys.argv[2] if len(sys.argv) > 2 else "test task"
        brief = format_insights_for_brief(task, episodes)
        print(brief if brief else "(no insights for this task)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
