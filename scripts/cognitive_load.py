#!/usr/bin/env python3
"""Cognitive Load Monitor — homeostatic regulation for Clarvis.

Tracks system health across 4 dimensions:
  1. Failure rate (from watchdog logs)
  2. Queue velocity (tasks completed vs added)
  3. Memory growth rate (brain stats over time)
  4. Cron execution times (durations + timeouts)

Computes a single cognitive load score 0.0–1.0.
When load > 0.8, signals auto-throttle: defer P1/P2 tasks, focus on recovery.

Usage:
    python3 cognitive_load.py check          # Print load score + components as JSON
    python3 cognitive_load.py should-defer   # Exit 0 if should defer, 1 if OK to proceed
    python3 cognitive_load.py history        # Print load history (last 7 days)
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path("/home/agent/.openclaw/workspace")
CRON_LOG_DIR = BASE / "memory" / "cron"
QUEUE_PATH = BASE / "memory" / "evolution" / "QUEUE.md"
HISTORY_PATH = BASE / "data" / "cognitive_load_history.json"
CAPABILITY_HISTORY = BASE / "data" / "capability_history.json"

# Thresholds
OVERLOAD_THRESHOLD = 0.8
CAUTION_THRESHOLD = 0.5

# Weights for composite score
W_FAILURE = 0.30     # Failures are the strongest signal
W_QUEUE = 0.25       # Queue backlog signals overwhelm
W_CRON_TIME = 0.25   # Slow/timing-out crons signal stress
W_CAPABILITY = 0.20  # Capability degradation signals systemic issues


def _parse_timestamp(ts_str):
    """Parse ISO timestamp from log line like [2026-02-22T14:00:01]."""
    try:
        return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _now_utc():
    return datetime.now(timezone.utc)


# ─── Metric 1: Failure Rate (from watchdog.log) ─────────────────────

def measure_failure_rate(hours=24):
    """Count watchdog failures in last N hours. Returns 0.0–1.0."""
    log_path = CRON_LOG_DIR / "watchdog.log"
    if not log_path.exists():
        return 0.0  # No watchdog = no signal (assume healthy)

    cutoff = _now_utc() - timedelta(hours=hours)
    total_checks = 0
    failed_checks = 0

    try:
        lines = log_path.read_text().strip().split("\n")
    except Exception:
        return 0.0

    for line in lines:
        m = re.match(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\] Watchdog check: (\d+) failures?", line)
        if not m:
            continue
        ts = _parse_timestamp(m.group(1))
        if ts is None or ts < cutoff:
            continue
        total_checks += 1
        failures = int(m.group(2))
        if failures > 0:
            failed_checks += 1

    if total_checks == 0:
        return 0.0

    # Ratio of checks that found failures, capped at 1.0
    return min(1.0, failed_checks / total_checks)


# ─── Metric 2: Queue Velocity ─────────────────────────────────────────

def measure_queue_velocity():
    """Ratio of pending to completed tasks. Returns 0.0–1.0.

    0.0 = all tasks completed (healthy)
    1.0 = queue is 100% pending (overwhelmed)
    """
    if not QUEUE_PATH.exists():
        return 0.0

    try:
        content = QUEUE_PATH.read_text()
    except Exception:
        return 0.0

    completed = len(re.findall(r"^\- \[x\]", content, re.MULTILINE))
    pending = len(re.findall(r"^\- \[ \]", content, re.MULTILINE))
    total = completed + pending

    if total == 0:
        return 0.0

    # Pending ratio — higher = more backlog pressure
    return pending / total


# ─── Metric 3: Cron Execution Times ───────────────────────────────────

def measure_cron_times(hours=24):
    """Analyze autonomous.log for task durations and timeouts. Returns 0.0–1.0."""
    log_path = CRON_LOG_DIR / "autonomous.log"
    if not log_path.exists():
        return 0.0

    cutoff = _now_utc() - timedelta(hours=hours)
    durations = []
    timeouts = 0
    total_tasks = 0

    try:
        lines = log_path.read_text().strip().split("\n")
    except Exception:
        return 0.0

    # Track EXECUTING timestamps to compute durations
    last_execute_ts = None

    for line in lines:
        # Parse timestamp from any line
        ts_match = re.match(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]", line)
        if not ts_match:
            continue
        ts = _parse_timestamp(ts_match.group(1))
        if ts is None or ts < cutoff:
            # Track last execute even if before cutoff (for duration of first in-window task)
            if "EXECUTING:" in line:
                last_execute_ts = ts
            continue

        if "EXECUTING:" in line:
            last_execute_ts = ts
            total_tasks += 1

        elif "COMPLETED:" in line and last_execute_ts:
            duration = (ts - last_execute_ts).total_seconds()
            if 0 < duration < 7200:  # Sanity: ignore >2h durations (likely log gaps)
                durations.append(duration)
            last_execute_ts = None

        elif "TIMEOUT" in line:
            timeouts += 1
            total_tasks = max(total_tasks, 1)  # Ensure counted
            last_execute_ts = None

        elif "FAILED" in line:
            last_execute_ts = None

    if total_tasks == 0:
        return 0.0

    # Components:
    # 1. Timeout ratio (very bad — 0.6 weight within this metric)
    timeout_ratio = timeouts / total_tasks if total_tasks > 0 else 0.0

    # 2. Avg duration relative to the 600s limit (0.4 weight)
    if durations:
        avg_duration = sum(durations) / len(durations)
        duration_ratio = min(1.0, avg_duration / 600.0)  # 600s = timeout limit
    else:
        duration_ratio = 0.0

    return min(1.0, 0.6 * timeout_ratio + 0.4 * duration_ratio)


# ─── Metric 4: Capability Degradation ─────────────────────────────────

def measure_capability_degradation():
    """Check if capabilities are declining. Returns 0.0–1.0.

    0.0 = stable or improving
    1.0 = severe degradation across all domains
    """
    if not CAPABILITY_HISTORY.exists():
        return 0.0

    try:
        history = json.loads(CAPABILITY_HISTORY.read_text())
    except Exception:
        return 0.0

    if len(history) < 2:
        return 0.0

    # Compare latest to previous entry
    latest = history[-1]
    previous = history[-2]

    latest_scores = latest.get("capabilities", {})
    previous_scores = previous.get("capabilities", {})

    if not latest_scores or not previous_scores:
        return 0.0

    # Count domains that degraded
    degraded = 0
    total = 0
    total_drop = 0.0

    for domain in latest_scores:
        if domain in previous_scores:
            total += 1
            drop = previous_scores[domain] - latest_scores[domain]
            if drop > 0.05:  # Only count meaningful drops (>5%)
                degraded += 1
                total_drop += drop

    if total == 0:
        return 0.0

    # Combine: fraction degraded * average drop magnitude
    frac_degraded = degraded / total
    avg_drop = total_drop / max(degraded, 1)

    # Scale: 50% domains degrading by 20% each → load = 0.5
    return min(1.0, frac_degraded * min(1.0, avg_drop * 5.0))


# ─── Composite Score ──────────────────────────────────────────────────

def compute_load():
    """Compute composite cognitive load score. Returns dict with score + components."""
    failure_rate = measure_failure_rate()
    queue_pressure = measure_queue_velocity()
    cron_stress = measure_cron_times()
    capability_drop = measure_capability_degradation()

    score = (
        W_FAILURE * failure_rate +
        W_QUEUE * queue_pressure +
        W_CRON_TIME * cron_stress +
        W_CAPABILITY * capability_drop
    )
    score = min(1.0, max(0.0, score))

    if score >= OVERLOAD_THRESHOLD:
        status = "OVERLOADED"
        action = "defer_all_non_recovery"
    elif score >= CAUTION_THRESHOLD:
        status = "CAUTION"
        action = "defer_p2"
    else:
        status = "HEALTHY"
        action = "proceed"

    return {
        "score": round(score, 3),
        "status": status,
        "action": action,
        "components": {
            "failure_rate": round(failure_rate, 3),
            "queue_pressure": round(queue_pressure, 3),
            "cron_stress": round(cron_stress, 3),
            "capability_drop": round(capability_drop, 3),
        },
        "weights": {
            "failure": W_FAILURE,
            "queue": W_QUEUE,
            "cron_time": W_CRON_TIME,
            "capability": W_CAPABILITY,
        },
        "thresholds": {
            "overload": OVERLOAD_THRESHOLD,
            "caution": CAUTION_THRESHOLD,
        },
        "timestamp": _now_utc().isoformat(),
    }


def should_defer_task(task_section):
    """Decide whether to defer a task based on load and its priority section.

    Returns (should_defer: bool, reason: str).
    """
    load = compute_load()
    score = load["score"]
    status = load["status"]

    # P0 tasks always run (unless truly overloaded)
    if task_section == "P0":
        if status == "OVERLOADED":
            return True, f"OVERLOADED (load={score:.2f}) — even P0 deferred, run recovery only"
        return False, f"P0 always runs (load={score:.2f})"

    # P1 tasks: defer if overloaded
    if task_section == "P1":
        if status == "OVERLOADED":
            return True, f"OVERLOADED (load={score:.2f}) — P1 deferred"
        return False, f"P1 OK (load={score:.2f})"

    # P2 tasks: defer if caution or overloaded
    if task_section == "P2":
        if status in ("OVERLOADED", "CAUTION"):
            return True, f"{status} (load={score:.2f}) — P2 deferred"
        return False, f"P2 OK (load={score:.2f})"

    # Unknown section: treat like P1
    if status == "OVERLOADED":
        return True, f"OVERLOADED (load={score:.2f}) — unknown section deferred"
    return False, f"OK (load={score:.2f})"


# ─── Task Sizing Estimation ──────────────────────────────────────────────

# Complexity signals that indicate a task may exceed single-heartbeat capacity.
# Derived from analysis of 184 episodes: timeouts avg 290 chars, multi-step keywords.
COMPLEXITY_KEYWORDS = {
    # High complexity: multi-step build tasks
    "test suite": 3, "multi-step": 3, "comprehensive": 2, "refactor": 2,
    "migrate": 2, "benchmark suite": 3, "full audit": 3,
    # Medium complexity: creation tasks
    "create scripts/": 1, "build module": 1, "implement": 1,
    "create.*py": 1, "new module": 1,
}

# Implementation sprint slot allows longer tasks (1800s vs 1200s)
# Expanded to cover core work hours (06:00-20:00 UTC)
IMPLEMENTATION_SLOT_HOURS = {6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}  # 14:00 CET reference


def estimate_task_complexity(task_text):
    """Estimate task complexity from description text.

    Returns dict with:
      - complexity: "simple" | "medium" | "complex" | "oversized"
      - score: 0.0-1.0 composite
      - signals: list of matched signals
      - recommendation: "proceed" | "warn" | "defer_to_sprint"
    """
    task_lower = task_text.lower()
    signals = []
    score = 0.0

    # Signal 1: Task description length (timeouts avg 290 chars, success avg 251)
    length = len(task_text)
    if length > 400:
        score += 0.2
        signals.append(f"long_description ({length} chars)")
    elif length > 300:
        score += 0.1
        signals.append(f"medium_description ({length} chars)")

    # Signal 2: Complexity keywords
    for keyword, weight in COMPLEXITY_KEYWORDS.items():
        if keyword in task_lower:
            score += 0.15 * weight
            signals.append(f"keyword:{keyword}")

    # Signal 3: Step count indicators (numbered lists, multiple dashes)
    step_indicators = task_lower.count(" — ") + task_lower.count("; ") + task_lower.count(". ")
    if step_indicators >= 4:
        score += 0.2
        signals.append(f"multi_step ({step_indicators} separators)")
    elif step_indicators >= 2:
        score += 0.1
        signals.append(f"some_steps ({step_indicators} separators)")

    # Signal 4: Multiple file references
    import re as _re
    file_refs = len(_re.findall(r'\w+\.py|\w+\.sh|\w+\.js', task_text))
    if file_refs >= 3:
        score += 0.15
        signals.append(f"multi_file ({file_refs} refs)")

    # Signal 5: Check episodic memory for similar task failures/timeouts
    ep_signal = _check_episodic_history(task_text)
    if ep_signal:
        score += ep_signal["penalty"]
        signals.append(ep_signal["signal"])

    score = min(1.0, score)

    if score >= 0.7:
        complexity = "oversized"
        recommendation = "defer_to_sprint"
    elif score >= 0.4:
        complexity = "complex"
        recommendation = "warn"
    elif score >= 0.2:
        complexity = "medium"
        recommendation = "proceed"
    else:
        complexity = "simple"
        recommendation = "proceed"

    # If we're in an implementation sprint slot, allow complex tasks
    now_hour = _now_utc().hour
    if now_hour in IMPLEMENTATION_SLOT_HOURS and recommendation == "defer_to_sprint":
        recommendation = "warn"
        signals.append("implementation_sprint_slot")

    return {
        "complexity": complexity,
        "score": round(score, 3),
        "signals": signals,
        "recommendation": recommendation,
    }


def _check_episodic_history(task_text):
    """Check if similar tasks have failed or timed out."""
    ep_file = BASE / "data" / "episodes.json"
    if not ep_file.exists():
        return None

    try:
        episodes = json.loads(ep_file.read_text())
    except Exception:
        return None

    task_lower = task_text.lower()
    # Extract key words for matching (>4 chars, not stopwords)
    stopwords = {"the", "and", "for", "from", "with", "this", "that", "into", "create", "build"}
    words = set(w for w in re.findall(r'[a-z_]{4,}', task_lower) if w not in stopwords)

    if not words:
        return None

    for ep in reversed(episodes):  # Check most recent first
        ep_task = ep.get("task", "").lower()
        ep_words = set(re.findall(r'[a-z_]{4,}', ep_task))
        overlap = words & ep_words
        if len(overlap) < 3:
            continue

        outcome = ep.get("outcome", "")
        if outcome == "timeout":
            return {
                "penalty": 0.3,
                "signal": f"similar_task_timeout (ep={ep.get('id', '?')}, overlap={len(overlap)})",
            }
        elif outcome == "failure":
            return {
                "penalty": 0.15,
                "signal": f"similar_task_failure (ep={ep.get('id', '?')}, overlap={len(overlap)})",
            }

    return None


# ─── Tracking Metric ─────────────────────────────────────────────────

SIZING_LOG = BASE / "data" / "task_sizing_log.jsonl"


def log_sizing(task_text, sizing_result, actual_outcome=None):
    """Log task sizing decisions for calibration tracking."""
    entry = {
        "timestamp": _now_utc().isoformat(),
        "task_preview": task_text[:120],
        "complexity": sizing_result["complexity"],
        "score": sizing_result["score"],
        "recommendation": sizing_result["recommendation"],
        "signals": sizing_result["signals"],
    }
    if actual_outcome:
        entry["actual_outcome"] = actual_outcome

    SIZING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SIZING_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Cap at 500 entries
    try:
        lines = SIZING_LOG.read_text().strip().split("\n")
        if len(lines) > 500:
            SIZING_LOG.write_text("\n".join(lines[-500:]) + "\n")
    except Exception:
        pass


# ─── History Tracking ──────────────────────────────────────────────────

def record_load(load_data):
    """Append load measurement to history file (90-day cap)."""
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text())
        except Exception:
            history = []

    history.append(load_data)

    # Cap at 90 days (~4320 entries at 30min intervals)
    history = history[-4320:]

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def get_history(days=7):
    """Get load history for the last N days."""
    if not HISTORY_PATH.exists():
        return []

    try:
        history = json.loads(HISTORY_PATH.read_text())
    except Exception:
        return []

    cutoff = (_now_utc() - timedelta(days=days)).isoformat()
    return [h for h in history if h.get("timestamp", "") >= cutoff]


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: cognitive_load.py [check|should-defer|history]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "check":
        load = compute_load()
        record_load(load)
        print(json.dumps(load, indent=2))

    elif cmd == "should-defer":
        # Optional: pass task section as arg
        section = sys.argv[2] if len(sys.argv) > 2 else "P1"
        defer, reason = should_defer_task(section)
        print(reason)
        sys.exit(0 if defer else 1)

    elif cmd == "history":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        hist = get_history(days)
        if not hist:
            print("No history recorded yet.")
        else:
            scores = [h["score"] for h in hist]
            print(f"Load history ({len(hist)} measurements, last {days} days):")
            print(f"  Current: {scores[-1]:.3f}")
            print(f"  Avg:     {sum(scores)/len(scores):.3f}")
            print(f"  Min:     {min(scores):.3f}")
            print(f"  Max:     {max(scores):.3f}")
            overloaded = sum(1 for s in scores if s >= OVERLOAD_THRESHOLD)
            caution = sum(1 for s in scores if CAUTION_THRESHOLD <= s < OVERLOAD_THRESHOLD)
            print(f"  Overloaded: {overloaded}/{len(scores)} ({100*overloaded/len(scores):.0f}%)")
            print(f"  Caution:    {caution}/{len(scores)} ({100*caution/len(scores):.0f}%)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
