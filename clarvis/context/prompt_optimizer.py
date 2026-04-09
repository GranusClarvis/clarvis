"""Prompt Self-Optimization Loop (APE/SPO-inspired).

Records heartbeat prompt->outcome pairs, maintains prompt variant performance
stats, and selects best-performing variants via Thompson sampling.

Variant dimensions inject short meta-instructions into the heartbeat prompt.
Each dimension has 2-4 variants; one is selected per heartbeat and tracked.

Data: data/prompt_optimization/prompt_outcomes.jsonl
      data/prompt_optimization/variant_stats.json

Usage:
    from clarvis.context.prompt_optimizer import select_variant, record_outcome
    result = select_variant("Fix retrieval quality")
    record_outcome(result["variant_id"], "bugfix", "success", 120)
"""

import json
import os
import random
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "data/prompt_optimization")
OUTCOMES_FILE = os.path.join(DATA_DIR, "prompt_outcomes.jsonl")
STATS_FILE = os.path.join(DATA_DIR, "variant_stats.json")

# === VARIANT DEFINITIONS ===
VARIANT_DIMENSIONS = {
    "approach": {
        "analyze_first": (
            "APPROACH: Before writing code, briefly analyze: "
            "1. What files need to change and why "
            "2. What could go wrong (check failure patterns above) "
            "3. How to verify success (check criteria above)\n"
            "Then implement, test, and report what you accomplished."
        ),
        "test_driven": (
            "APPROACH: Write a failing test first, then implement the minimum code "
            "to make it pass. Iterate until the task is complete. "
            "Report test results in your summary."
        ),
        "incremental": (
            "APPROACH: Break this into the smallest possible steps. "
            "Complete and verify each step before moving to the next. "
            "If time is short, deliver the most impactful step fully done."
        ),
        "dive_in": (
            "APPROACH: Start implementing immediately. "
            "Focus on concrete output over analysis."
        ),
    },
    "success_framing": {
        "criteria_check": (
            "SUCCESS CRITERIA: Before finishing, verify each criterion listed above is met. "
            "List which criteria you satisfied in your summary."
        ),
        "output_focus": (
            "SUCCESS CRITERIA: Deliver working, tested code. "
            "A concrete artifact (file, config, test) is better than analysis."
        ),
        "minimal": "",  # no extra framing
    },
    "failure_guard": {
        "strong": (
            "FAILURE AVOIDANCE: Check the failure patterns above BEFORE starting. "
            "If a similar task failed before, explicitly address what went wrong. "
            "Avoid the exact same approach that led to failure."
        ),
        "light": (
            "AVOID THESE FAILURE PATTERNS: see somatic markers above."
        ),
        "none": "",  # no extra guard
    },
}

DEFAULT_COMBO = {
    "approach": "analyze_first",
    "success_framing": "criteria_check",
    "failure_guard": "strong",
}

MIN_OBSERVATIONS = 3


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_stats():
    """Load variant performance stats (Beta distribution params)."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    stats = {}
    for dim, variants in VARIANT_DIMENSIONS.items():
        stats[dim] = {}
        for v_name in variants:
            stats[dim][v_name] = {"alpha": 1.0, "beta": 1.0, "n": 0,
                                  "total_duration": 0, "successes": 0, "failures": 0,
                                  "total_quality": 0.0, "quality_count": 0,
                                  "by_task_type": {}}
    return stats


def _save_stats(stats):
    _ensure_dir()
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)


def _get_effective_params(params):
    """Get effective alpha/beta, incorporating quality weighting when available."""
    alpha = params["alpha"]
    beta = params["beta"]
    total_quality = params.get("total_quality", 0.0)
    quality_count = params.get("quality_count", 0)

    if quality_count > MIN_OBSERVATIONS and total_quality > 0:
        alpha = alpha + total_quality
    return alpha, beta


def _thompson_sample(stats_dim, task_type=None):
    """Thompson sampling: draw from Beta(alpha, beta) for each variant, pick highest."""
    best_name = None
    best_sample = -1.0
    for v_name, params in stats_dim.items():
        use_params = params
        if task_type:
            by_type = params.get("by_task_type", {})
            type_stats = by_type.get(task_type)
            if type_stats and type_stats.get("n", 0) >= MIN_OBSERVATIONS:
                use_params = type_stats

        alpha, beta = _get_effective_params(use_params)
        sample = random.betavariate(alpha, beta)
        if sample > best_sample:
            best_sample = sample
            best_name = v_name
    return best_name


def _classify_task_type(task_text):
    """Rough task classification for per-type tracking."""
    task_lower = task_text.lower() if task_text else ""
    if any(kw in task_lower for kw in ["test", "pytest", "coverage"]):
        return "testing"
    if any(kw in task_lower for kw in ["refactor", "extract", "rename", "cleanup", "hygiene"]):
        return "refactoring"
    if any(kw in task_lower for kw in ["research", "survey", "review", "read", "analyze"]):
        return "research"
    if any(kw in task_lower for kw in ["fix", "bug", "error", "broken", "failing"]):
        return "bugfix"
    if any(kw in task_lower for kw in ["build", "create", "add", "implement", "wire"]):
        return "implementation"
    if any(kw in task_lower for kw in ["optimize", "speed", "perf", "benchmark"]):
        return "optimization"
    return "general"


def select_variant(task_text="", explore_rate=0.10):
    """Select a variant combo for this heartbeat.

    Uses Thompson sampling with optional epsilon-greedy exploration.

    Args:
        task_text: The task description (for per-type stats)
        explore_rate: Probability of pure random exploration (default 10%)

    Returns:
        dict with keys: variant_id (str), combo (dict), meta_instruction (str)
    """
    stats = _load_stats()
    combo = {}
    task_type = _classify_task_type(task_text)

    if random.random() < explore_rate:
        for dim, variants in VARIANT_DIMENSIONS.items():
            combo[dim] = random.choice(list(variants.keys()))
    else:
        for dim in VARIANT_DIMENSIONS:
            if dim in stats and any(stats[dim][v]["n"] >= MIN_OBSERVATIONS
                                    for v in stats[dim]):
                combo[dim] = _thompson_sample(stats[dim], task_type=task_type)
            else:
                combo[dim] = DEFAULT_COMBO.get(dim,
                    list(VARIANT_DIMENSIONS[dim].keys())[0])

    parts = []
    for dim, v_name in combo.items():
        text = VARIANT_DIMENSIONS[dim][v_name]
        if text:
            parts.append(text)

    variant_id = "|".join(f"{d}={v}" for d, v in sorted(combo.items()))
    meta_instruction = "\n".join(parts)

    return {
        "variant_id": variant_id,
        "combo": combo,
        "meta_instruction": meta_instruction,
        "task_type": _classify_task_type(task_text),
    }


def _init_stat_entry():
    """Return a fresh stat entry with Beta(1,1) prior."""
    return {"alpha": 1.0, "beta": 1.0, "n": 0,
            "total_duration": 0, "successes": 0, "failures": 0,
            "total_quality": 0.0, "quality_count": 0}


def _update_stat_entry(s, is_success, duration_s, quality_score=None):
    """Update a single stat entry (aggregate or per-task-type) in-place."""
    s["n"] += 1
    s["total_duration"] += duration_s
    if is_success:
        s["alpha"] += 1.0
        s["successes"] += 1
    else:
        s["beta"] += 1.0
        s["failures"] += 1
    if quality_score is not None:
        s.setdefault("total_quality", 0.0)
        s.setdefault("quality_count", 0)
        s["total_quality"] += quality_score
        s["quality_count"] += 1


def record_outcome(variant_id, task_type, outcome, duration_s, task_text="",
                   quality_score=None):
    """Record a prompt->outcome pair and update variant stats.

    Args:
        variant_id: str from select_variant()
        task_type: str task classification
        outcome: "success" | "failure" | "timeout"
        duration_s: int, seconds the task took
        task_text: str, the full task description
        quality_score: optional float 0.0-1.0, quality rating of the outcome
    """
    _ensure_dir()

    if quality_score is not None:
        quality_score = max(0.0, min(1.0, float(quality_score)))

    combo = {}
    for part in variant_id.split("|"):
        if "=" in part:
            dim, val = part.split("=", 1)
            combo[dim] = val

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "variant_id": variant_id,
        "combo": combo,
        "task_type": task_type,
        "outcome": outcome,
        "duration_s": duration_s,
        "task_snippet": (task_text[:120] if task_text else ""),
    }
    if quality_score is not None:
        record["quality_score"] = quality_score
    with open(OUTCOMES_FILE, 'a') as f:
        f.write(json.dumps(record) + "\n")

    stats = _load_stats()
    is_success = (outcome == "success")

    for dim, v_name in combo.items():
        if dim not in stats:
            stats[dim] = {}
        if v_name not in stats[dim]:
            entry = _init_stat_entry()
            entry["by_task_type"] = {}
            stats[dim][v_name] = entry

        s = stats[dim][v_name]
        s.setdefault("total_quality", 0.0)
        s.setdefault("quality_count", 0)
        s.setdefault("by_task_type", {})

        _update_stat_entry(s, is_success, duration_s, quality_score)

        if task_type:
            if task_type not in s["by_task_type"]:
                s["by_task_type"][task_type] = _init_stat_entry()
            _update_stat_entry(s["by_task_type"][task_type],
                               is_success, duration_s, quality_score)

    _save_stats(stats)
    return record


def _format_stat_line(v_name, s, indent="  "):
    """Format a single stat entry as a report line."""
    n = s["n"]
    rate = s["successes"] / n if n > 0 else 0
    avg_dur = s["total_duration"] / n if n > 0 else 0
    alpha, beta = _get_effective_params(s)
    mean = alpha / (alpha + beta)
    quality_count = s.get("quality_count", 0)
    quality_avg = s.get("total_quality", 0) / quality_count if quality_count > 0 else None
    quality_str = f"  q_avg={quality_avg:.3f}({quality_count})" if quality_avg is not None else ""
    return (f"{indent}{v_name:20s}  n={n:3d}  "
            f"win={rate:.0%}  avg_dur={avg_dur:.0f}s  "
            f"E[θ]={mean:.3f}{quality_str}")


def get_report():
    """Generate a human-readable report of variant performance."""
    stats = _load_stats()
    lines = ["=== Prompt Variant Performance ===", ""]

    for dim in sorted(stats.keys()):
        lines.append(f"Dimension: {dim}")
        variants = stats[dim]
        sorted_v = sorted(variants.items(),
                          key=lambda x: x[1]["successes"] / max(x[1]["n"], 1),
                          reverse=True)
        for v_name, s in sorted_v:
            lines.append(_format_stat_line(v_name, s))

            by_type = s.get("by_task_type", {})
            if by_type:
                for tt in sorted(by_type.keys()):
                    ts = by_type[tt]
                    if ts.get("n", 0) > 0:
                        lines.append(_format_stat_line(f"[{tt}]", ts, indent="      "))
        lines.append("")

    if os.path.exists(OUTCOMES_FILE):
        with open(OUTCOMES_FILE) as f:
            recent = f.readlines()[-10:]
        lines.append("Recent outcomes (last 10):")
        for line in recent:
            try:
                r = json.loads(line)
                q_str = ""
                if "quality_score" in r:
                    q_str = f" q={r['quality_score']:.2f}"
                lines.append(f"  {r['outcome']:8s} {r['variant_id'][:50]}  "
                             f"({r['task_type']}, {r['duration_s']}s{q_str})")
            except (json.JSONDecodeError, KeyError):
                pass

    return "\n".join(lines)


def get_ab_summary():
    """Generate A/B test summary: which variants outperform others."""
    stats = _load_stats()
    lines = ["=== A/B Test Summary ===", ""]

    for dim in sorted(stats.keys()):
        variants = stats[dim]
        tested = {v: s for v, s in variants.items() if s["n"] >= MIN_OBSERVATIONS}
        if len(tested) < 2:
            lines.append(f"{dim}: insufficient data (need {MIN_OBSERVATIONS} obs each)")
            continue

        sorted_v = sorted(tested.items(),
                          key=lambda x: x[1]["alpha"] / (x[1]["alpha"] + x[1]["beta"]),
                          reverse=True)
        best_name, best_s = sorted_v[0]
        best_mean = best_s["alpha"] / (best_s["alpha"] + best_s["beta"])

        lines.append(f"{dim}: BEST = {best_name} (E[θ]={best_mean:.3f}, n={best_s['n']})")
        for v_name, s in sorted_v[1:]:
            mean = s["alpha"] / (s["alpha"] + s["beta"])
            diff = best_mean - mean
            lines.append(f"  vs {v_name}: E[θ]={mean:.3f} (Δ={diff:+.3f}, n={s['n']})")
        lines.append("")

    return "\n".join(lines)
