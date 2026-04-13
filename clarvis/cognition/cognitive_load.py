"""Cognitive Load Monitor — homeostatic regulation for Clarvis.

Tracks system health across 4 dimensions:
  1. Failure rate (from watchdog logs)
  2. Queue velocity (tasks completed vs added)
  3. Memory growth rate (brain stats over time)
  4. Cron execution times (durations + timeouts)

Computes a single cognitive load score 0.0-1.0.
When load > 0.8, signals auto-throttle: defer P1/P2 tasks, focus on recovery.
"""

import json
import re
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
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


# --- Metric 1: Failure Rate (from watchdog.log) ---

def measure_failure_rate(hours=24):
    """Measure failure severity from watchdog logs. Returns 0.0-1.0.

    Uses the LATEST watchdog check's failure count as a ratio of total
    monitored jobs, rather than the fraction of checks that had any failure.
    This prevents a single persistent stale job from inflating the score to 1.0.
    """
    log_path = CRON_LOG_DIR / "watchdog.log"
    if not log_path.exists():
        return 0.0

    cutoff = _now_utc() - timedelta(hours=hours)
    latest_failures = 0
    latest_ts = None

    # Total monitored jobs in watchdog (count of check_job calls)
    TOTAL_MONITORED_JOBS = 30  # approximate count from watchdog script

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
        # Keep the latest check's failure count
        if latest_ts is None or ts >= latest_ts:
            latest_ts = ts
            latest_failures = int(m.group(2))

    if latest_ts is None:
        return 0.0

    # Return ratio of failing jobs to total, not binary "any failure" metric
    return min(1.0, latest_failures / TOTAL_MONITORED_JOBS)


# --- Metric 2: Queue Velocity ---

def measure_queue_velocity():
    """Ratio of pending to completed tasks. Returns 0.0-1.0."""
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

    return pending / total


# --- Metric 3: Cron Execution Times ---

def measure_cron_times(hours=24):
    """Analyze autonomous.log for task durations and timeouts. Returns 0.0-1.0.

    Only counts actual EXECUTING→TIMEOUT/COMPLETED cycles, not heartbeat
    deferrals (which log "All N candidates deferred" without EXECUTING).
    Heartbeat cycles that correctly defer all tasks are normal operation,
    not a sign of cron stress.
    """
    log_path = CRON_LOG_DIR / "autonomous.log"
    if not log_path.exists():
        return 0.0

    cutoff = _now_utc() - timedelta(hours=hours)
    durations = []
    timeouts = 0
    total_tasks = 0
    total_cycles = 0  # Total heartbeat cycles (including deferrals)

    try:
        lines = log_path.read_text().strip().split("\n")
    except Exception:
        return 0.0

    last_execute_ts = None

    for line in lines:
        ts_match = re.match(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]", line)
        if not ts_match:
            continue
        ts = _parse_timestamp(ts_match.group(1))
        if ts is None or ts < cutoff:
            if "EXECUTING:" in line:
                last_execute_ts = ts
            continue

        if "GATE: wake" in line or "Heartbeat starting" in line:
            total_cycles += 1
        elif "EXECUTING:" in line:
            last_execute_ts = ts
            total_tasks += 1
        elif "COMPLETED:" in line and last_execute_ts:
            duration = (ts - last_execute_ts).total_seconds()
            if 0 < duration < 7200:
                durations.append(duration)
            last_execute_ts = None
        elif "TIMEOUT" in line and "TIMEOUT" not in line.split(":")[-1] if "skip" in line.lower() else True:
            # Only count actual execution timeouts, not log lines about timeout classifications
            if last_execute_ts is not None:
                timeouts += 1
                last_execute_ts = None
        elif "FAILED" in line:
            last_execute_ts = None

    # If no tasks were actually executed, cron stress is low (deferrals ≠ stress)
    if total_tasks == 0:
        # If cycles ran but nothing executed, it's a deferral situation, not stress
        # Return a small value so it doesn't dominate the score
        return 0.1 if total_cycles > 0 else 0.0

    timeout_ratio = timeouts / total_tasks if total_tasks > 0 else 0.0

    if durations:
        avg_duration = sum(durations) / len(durations)
        duration_ratio = min(1.0, avg_duration / 600.0)
    else:
        duration_ratio = 0.0

    return min(1.0, 0.6 * timeout_ratio + 0.4 * duration_ratio)


# --- Metric 4: Capability Degradation ---

def measure_capability_degradation():
    """Check if capabilities are declining. Returns 0.0-1.0."""
    if not CAPABILITY_HISTORY.exists():
        return 0.0

    try:
        history = json.loads(CAPABILITY_HISTORY.read_text())
    except Exception:
        return 0.0

    if isinstance(history, dict) and "snapshots" in history:
        history = history["snapshots"]

    if not isinstance(history, list) or len(history) < 2:
        return 0.0

    latest = history[-1]
    previous = history[-2]

    latest_scores = latest.get("scores", latest.get("capabilities", {}))
    previous_scores = previous.get("scores", previous.get("capabilities", {}))

    if not latest_scores or not previous_scores:
        return 0.0

    degraded = 0
    total = 0
    total_drop = 0.0

    for domain in latest_scores:
        if domain in previous_scores:
            total += 1
            drop = previous_scores[domain] - latest_scores[domain]
            if drop > 0.05:
                degraded += 1
                total_drop += drop

    if total == 0:
        return 0.0

    frac_degraded = degraded / total
    avg_drop = total_drop / max(degraded, 1)

    return min(1.0, frac_degraded * min(1.0, avg_drop * 5.0))


# --- Composite Score ---

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

    if task_section == "P0":
        if status == "OVERLOADED":
            return True, f"OVERLOADED (load={score:.2f}) — even P0 deferred, run recovery only"
        return False, f"P0 always runs (load={score:.2f})"

    if task_section == "P1":
        if status == "OVERLOADED":
            return True, f"OVERLOADED (load={score:.2f}) — P1 deferred"
        return False, f"P1 OK (load={score:.2f})"

    if task_section == "P2":
        if status in ("OVERLOADED", "CAUTION"):
            return True, f"{status} (load={score:.2f}) — P2 deferred"
        return False, f"P2 OK (load={score:.2f})"

    if status == "OVERLOADED":
        return True, f"OVERLOADED (load={score:.2f}) — unknown section deferred"
    return False, f"OK (load={score:.2f})"


# --- Task Sizing Estimation ---

COMPLEXITY_KEYWORDS = {
    "test suite": 3, "multi-step": 3, "comprehensive": 2, "refactor": 2,
    "migrate": 2, "benchmark suite": 3, "full audit": 3,
    "create scripts/": 1, "build module": 1, "implement": 1,
    "create.*py": 1, "new module": 1,
}

IMPLEMENTATION_SLOT_HOURS = {6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}


def estimate_task_complexity(task_text):
    """Estimate task complexity from description text.

    Returns dict with:
      - complexity: "simple" | "medium" | "complex" | "oversized"
      - score: 0.0-1.0 composite
      - signals: list of matched signals
      - recommendation: "proceed" | "warn" | "defer_to_sprint"
    """
    task_text = task_text or ""
    task_lower = task_text.lower()
    signals = []
    score = 0.0

    length = len(task_text)
    if length > 400:
        score += 0.2
        signals.append(f"long_description ({length} chars)")
    elif length > 300:
        score += 0.1
        signals.append(f"medium_description ({length} chars)")

    for keyword, weight in COMPLEXITY_KEYWORDS.items():
        if keyword in task_lower:
            score += 0.15 * weight
            signals.append(f"keyword:{keyword}")

    step_indicators = task_lower.count(" — ") + task_lower.count("; ") + task_lower.count(". ")
    if step_indicators >= 4:
        score += 0.2
        signals.append(f"multi_step ({step_indicators} separators)")
    elif step_indicators >= 2:
        score += 0.1
        signals.append(f"some_steps ({step_indicators} separators)")

    file_refs = len(re.findall(r'\w+\.py|\w+\.sh|\w+\.js', task_text))
    if file_refs >= 3:
        score += 0.15
        signals.append(f"multi_file ({file_refs} refs)")

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
    stopwords = {"the", "and", "for", "from", "with", "this", "that", "into", "create", "build"}
    words = set(w for w in re.findall(r'[a-z_]{4,}', task_lower) if w not in stopwords)

    if not words:
        return None

    for ep in reversed(episodes):
        ep_task = (ep.get("task") or "").lower()
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


# --- Tracking ---

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

    try:
        lines = SIZING_LOG.read_text().strip().split("\n")
        if len(lines) > 500:
            SIZING_LOG.write_text("\n".join(lines[-500:]) + "\n")
    except Exception:
        pass


# --- History Tracking ---

def record_load(load_data):
    """Append load measurement to history file (90-day cap)."""
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text())
        except Exception:
            history = []

    history.append(load_data)
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
