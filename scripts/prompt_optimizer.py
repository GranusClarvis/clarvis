#!/usr/bin/env python3
"""
Prompt Self-Optimization Loop (APE/SPO-inspired)

Records heartbeat prompt→outcome pairs, maintains prompt variant performance
stats, and selects best-performing variants via Thompson sampling.

Variant dimensions inject short meta-instructions into the heartbeat prompt.
Each dimension has 2-4 variants; one is selected per heartbeat and tracked.

Data: data/prompt_optimization/prompt_outcomes.jsonl
      data/prompt_optimization/variant_stats.json

Usage:
    # From preflight: select best variant combo for this task
    python3 prompt_optimizer.py select [task_type]

    # From postflight: record outcome
    python3 prompt_optimizer.py record <variant_id> <task_type> <outcome> <duration>

    # Report: show variant performance
    python3 prompt_optimizer.py report

    # A/B summary
    python3 prompt_optimizer.py ab-summary
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timezone

DATA_DIR = "/home/agent/.openclaw/workspace/data/prompt_optimization"
OUTCOMES_FILE = os.path.join(DATA_DIR, "prompt_outcomes.jsonl")
STATS_FILE = os.path.join(DATA_DIR, "variant_stats.json")

# === VARIANT DEFINITIONS ===
# Each dimension has named variants with the meta-instruction they inject.
# Keep instructions short — they go into the context brief.

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

# Default variant combo (used before enough data to optimize)
DEFAULT_COMBO = {
    "approach": "analyze_first",
    "success_framing": "criteria_check",
    "failure_guard": "strong",
}

# Minimum observations before we trust a variant's stats
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

    # Initialize: Beta(1,1) prior for each variant in each dimension
    stats = {}
    for dim, variants in VARIANT_DIMENSIONS.items():
        stats[dim] = {}
        for v_name in variants:
            stats[dim][v_name] = {"alpha": 1.0, "beta": 1.0, "n": 0,
                                  "total_duration": 0, "successes": 0, "failures": 0}
    return stats


def _save_stats(stats):
    _ensure_dir()
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)


def _thompson_sample(stats_dim):
    """Thompson sampling: draw from Beta(alpha, beta) for each variant, pick highest."""
    best_name = None
    best_sample = -1.0
    for v_name, params in stats_dim.items():
        sample = random.betavariate(params["alpha"], params["beta"])
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
        task_text: The task description (for per-type stats in future)
        explore_rate: Probability of pure random exploration (default 10%)

    Returns:
        dict with keys: variant_id (str), combo (dict), meta_instruction (str)
    """
    stats = _load_stats()
    combo = {}

    if random.random() < explore_rate:
        # Pure exploration: random combo
        for dim, variants in VARIANT_DIMENSIONS.items():
            combo[dim] = random.choice(list(variants.keys()))
    else:
        # Thompson sampling per dimension
        for dim in VARIANT_DIMENSIONS:
            if dim in stats and any(stats[dim][v]["n"] >= MIN_OBSERVATIONS
                                    for v in stats[dim]):
                combo[dim] = _thompson_sample(stats[dim])
            else:
                # Not enough data — use default
                combo[dim] = DEFAULT_COMBO.get(dim,
                    list(VARIANT_DIMENSIONS[dim].keys())[0])

    # Build meta-instruction from selected variants
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


def record_outcome(variant_id, task_type, outcome, duration_s, task_text=""):
    """Record a prompt→outcome pair and update variant stats.

    Args:
        variant_id: str from select_variant()
        task_type: str task classification
        outcome: "success" | "failure" | "timeout"
        duration_s: int, seconds the task took
        task_text: str, the full task description
    """
    _ensure_dir()

    # Parse variant_id back to combo
    combo = {}
    for part in variant_id.split("|"):
        if "=" in part:
            dim, val = part.split("=", 1)
            combo[dim] = val

    # Append to JSONL log
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "variant_id": variant_id,
        "combo": combo,
        "task_type": task_type,
        "outcome": outcome,
        "duration_s": duration_s,
        "task_snippet": (task_text[:120] if task_text else ""),
    }
    with open(OUTCOMES_FILE, 'a') as f:
        f.write(json.dumps(record) + "\n")

    # Update Beta distribution stats
    stats = _load_stats()
    is_success = (outcome == "success")

    for dim, v_name in combo.items():
        if dim not in stats:
            stats[dim] = {}
        if v_name not in stats[dim]:
            stats[dim][v_name] = {"alpha": 1.0, "beta": 1.0, "n": 0,
                                  "total_duration": 0, "successes": 0, "failures": 0}
        s = stats[dim][v_name]
        s["n"] += 1
        s["total_duration"] += duration_s
        if is_success:
            s["alpha"] += 1.0
            s["successes"] += 1
        else:
            s["beta"] += 1.0
            s["failures"] += 1

    _save_stats(stats)
    return record


def get_report():
    """Generate a human-readable report of variant performance."""
    stats = _load_stats()
    lines = ["=== Prompt Variant Performance ===", ""]

    for dim in sorted(stats.keys()):
        lines.append(f"Dimension: {dim}")
        variants = stats[dim]
        # Sort by success rate descending
        sorted_v = sorted(variants.items(),
                          key=lambda x: x[1]["successes"] / max(x[1]["n"], 1),
                          reverse=True)
        for v_name, s in sorted_v:
            n = s["n"]
            rate = s["successes"] / n if n > 0 else 0
            avg_dur = s["total_duration"] / n if n > 0 else 0
            mean = s["alpha"] / (s["alpha"] + s["beta"])
            lines.append(f"  {v_name:20s}  n={n:3d}  "
                         f"win={rate:.0%}  avg_dur={avg_dur:.0f}s  "
                         f"E[θ]={mean:.3f}")
        lines.append("")

    # Recent outcomes
    if os.path.exists(OUTCOMES_FILE):
        with open(OUTCOMES_FILE) as f:
            recent = f.readlines()[-10:]
        lines.append("Recent outcomes (last 10):")
        for line in recent:
            try:
                r = json.loads(line)
                lines.append(f"  {r['outcome']:8s} {r['variant_id'][:50]}  "
                             f"({r['task_type']}, {r['duration_s']}s)")
            except (json.JSONDecodeError, KeyError):
                pass

    return "\n".join(lines)


def get_ab_summary():
    """Generate A/B test summary: which variants outperform others."""
    stats = _load_stats()
    lines = ["=== A/B Test Summary ===", ""]

    for dim in sorted(stats.keys()):
        variants = stats[dim]
        # Need at least 2 variants with MIN_OBSERVATIONS each
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


# === CLI ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: prompt_optimizer.py select|record|report|ab-summary")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "select":
        task = sys.argv[2] if len(sys.argv) > 2 else ""
        result = select_variant(task)
        print(json.dumps(result))

    elif cmd == "record":
        if len(sys.argv) < 6:
            print("Usage: prompt_optimizer.py record <variant_id> <task_type> <outcome> <duration>")
            sys.exit(1)
        variant_id = sys.argv[2]
        task_type = sys.argv[3]
        outcome = sys.argv[4]
        duration = int(sys.argv[5])
        task_text = sys.argv[6] if len(sys.argv) > 6 else ""
        r = record_outcome(variant_id, task_type, outcome, duration, task_text)
        print(json.dumps(r))

    elif cmd == "report":
        print(get_report())

    elif cmd == "ab-summary":
        print(get_ab_summary())

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
