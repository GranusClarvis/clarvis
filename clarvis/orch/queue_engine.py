"""
Queue Engine v2 — sidecar state model for evolution queue.

Design: docs/QUEUE_V2_PRESSURE_TEST_2026-04-03.md section 5.

QUEUE.md remains the human-editable source of truth for task existence/priority.
data/queue_state.json is a machine-managed sidecar tracking volatile runtime state
(attempts, failure reasons, timestamps, state machine). The sidecar is disposable:
if deleted, retry counters reset to zero.

State machine:
    pending -> running -> succeeded
    pending -> running -> failed -> pending  (retry <= max)
    failed -> deferred  (max retries exceeded)
    any -> removed  (operator deletes from QUEUE.md)

Usage:
    from clarvis.orch.queue_engine import engine

    task = engine.select_next()       # reconciles QUEUE.md + sidecar
    engine.mark_running(task["tag"])
    engine.mark_succeeded(task["tag"], "done 2026-04-03")
    engine.stats()                    # observability dict
"""

import fcntl
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

_WS = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
QUEUE_FILE = os.path.join(_WS, "memory", "evolution", "QUEUE.md")
SIDECAR_FILE = os.path.join(_WS, "data", "queue_state.json")
RUNS_FILE = os.path.join(_WS, "data", "queue_runs.jsonl")

# Max retries per priority before moving to deferred
MAX_RETRIES = {"P0": 3, "P1": 2, "P2": 1}
DEFAULT_MAX_RETRIES = 2

# Backoff: skip N heartbeats after failure (capped at 2)
BACKOFF_CAP = 2

# Tag extraction pattern: [TAG] at start of task text
_TAG_RE = re.compile(r"^\[([A-Z][A-Za-z0-9_:.-]+)\]")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_tag(text: str) -> Optional[str]:
    """Extract [TAG] from task text. Returns None if no tag."""
    m = _TAG_RE.match(text.strip())
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# QUEUE.md parser (reusable, no heavy imports)
# ---------------------------------------------------------------------------

def parse_queue(queue_file: str = QUEUE_FILE) -> list[dict]:
    """Parse unchecked tasks from QUEUE.md with priority and tag.

    Returns list of dicts: {tag, text, priority, line_num}.
    Only returns tasks with a [TAG] — untagged items are skipped.
    """
    if not os.path.exists(queue_file):
        return []

    tasks = []
    current_priority = "P2"

    with open(queue_file) as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()

            # Detect priority sections
            if "## P0" in line:
                current_priority = "P0"
            elif "## P1" in line:
                current_priority = "P1"
            elif "## P2" in line:
                current_priority = "P2"

            # Match unchecked tasks only
            m = re.match(r"^- \[ \] (.+)$", stripped)
            if not m:
                continue

            text = m.group(1)
            tag = _extract_tag(text)
            if not tag:
                continue

            tasks.append({
                "tag": tag,
                "text": text,
                "priority": current_priority,
                "line_num": line_num,
            })

    return tasks


# ---------------------------------------------------------------------------
# Sidecar state persistence (atomic writes)
# ---------------------------------------------------------------------------

def _load_sidecar() -> dict:
    """Load sidecar state. Returns empty dict on missing/corrupt file."""
    if not os.path.exists(SIDECAR_FILE):
        return {}
    try:
        with open(SIDECAR_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_sidecar(data: dict) -> None:
    """Atomically save sidecar state (write tmp + rename)."""
    os.makedirs(os.path.dirname(SIDECAR_FILE), exist_ok=True)
    tmp = SIDECAR_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.rename(tmp, SIDECAR_FILE)


def _default_entry(tag: str, priority: str) -> dict:
    """Default sidecar entry for a newly discovered task."""
    now = _now_iso()
    return {
        "state": "pending",
        "attempts": 0,
        "last_run": None,
        "last_failure": None,
        "failure_reason": None,
        "created_at": now,
        "updated_at": now,
        "priority": priority,
        "skip_until": 0,  # epoch timestamp — skip heartbeats until this time
    }


# ---------------------------------------------------------------------------
# Queue Engine
# ---------------------------------------------------------------------------

class QueueEngine:
    """Sidecar-based queue engine for evolution task management."""

    def __init__(self, queue_file: str = QUEUE_FILE, sidecar_file: str = SIDECAR_FILE,
                 runs_file: str = RUNS_FILE):
        self.queue_file = queue_file
        self.sidecar_file = sidecar_file
        self.runs_file = runs_file
        self._lock_path = self.queue_file + ".lock"

    # -- locking --

    def _acquire_lock(self):
        os.makedirs(os.path.dirname(self._lock_path), exist_ok=True)
        fd = open(self._lock_path, "w")
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    def _release_lock(self, fd):
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            fd.close()

    # -- sidecar I/O (use module-level for atomic writes) --

    def _load(self) -> dict:
        if not os.path.exists(self.sidecar_file):
            return {}
        try:
            with open(self.sidecar_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.sidecar_file), exist_ok=True)
        tmp = self.sidecar_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.rename(tmp, self.sidecar_file)

    # -- reconciliation --

    def reconcile(self) -> tuple[list[dict], dict]:
        """Reconcile QUEUE.md tasks with sidecar state.

        Returns (tasks, sidecar) where tasks have sidecar state merged in,
        and sidecar has been updated with new/stale entries.
        """
        md_tasks = parse_queue(self.queue_file)
        sidecar = self._load()
        md_tags = {t["tag"] for t in md_tasks}

        # Add default entries for new tags
        for task in md_tasks:
            tag = task["tag"]
            if tag not in sidecar:
                sidecar[tag] = _default_entry(tag, task["priority"])
            else:
                # Update priority if it changed in QUEUE.md
                sidecar[tag]["priority"] = task["priority"]

        # Mark stale entries (in sidecar but removed from QUEUE.md)
        for tag in list(sidecar.keys()):
            if tag not in md_tags:
                if sidecar[tag].get("state") not in ("succeeded", "removed"):
                    sidecar[tag]["state"] = "removed"
                    sidecar[tag]["updated_at"] = _now_iso()

        # Merge sidecar state into task dicts
        for task in md_tasks:
            entry = sidecar[task["tag"]]
            task["state"] = entry["state"]
            task["attempts"] = entry["attempts"]
            task["last_run"] = entry.get("last_run")
            task["failure_reason"] = entry.get("failure_reason")
            task["skip_until"] = entry.get("skip_until", 0)

        self._save(sidecar)
        return md_tasks, sidecar

    # -- scoring (simplified: 3 factors) --

    def _score(self, task: dict) -> float:
        """Score a task for selection. 3 factors: priority, idle time, failure penalty.

        Higher = more urgent.
        """
        # Factor 1: priority weight
        priority_weight = {"P0": 1.0, "P1": 0.6, "P2": 0.3}.get(task["priority"], 0.3)

        # Factor 2: idle time (hours since last run, capped at 72h for normalization)
        last_run = task.get("last_run")
        if last_run:
            try:
                last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                idle_hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
            except (ValueError, TypeError):
                idle_hours = 24.0
        else:
            idle_hours = 48.0  # never run = high idle

        idle_score = min(1.0, idle_hours / 72.0)

        # Factor 3: failure penalty (more attempts = lower score)
        attempts = task.get("attempts", 0)
        failure_penalty = min(0.5, attempts * 0.15)

        # Weighted combination
        score = 0.50 * priority_weight + 0.35 * idle_score - 0.15 * failure_penalty
        return round(max(0.0, score), 4)

    # -- selection --

    def select_next(self) -> Optional[dict]:
        """Select the next task to execute.

        Reconciles QUEUE.md with sidecar, filters eligible tasks,
        scores them, and returns the best candidate.

        Returns None if no eligible tasks.
        """
        tasks, sidecar = self.reconcile()
        now_epoch = time.time()

        eligible = []
        for task in tasks:
            state = task["state"]

            # Only pending and failed-but-retryable tasks are eligible
            if state not in ("pending", "failed"):
                continue

            # Backoff: skip if within skip_until window
            skip_until = task.get("skip_until", 0)
            if skip_until and now_epoch < skip_until:
                continue

            # Check retry limit for failed tasks
            if state == "failed":
                max_r = MAX_RETRIES.get(task["priority"], DEFAULT_MAX_RETRIES)
                if task["attempts"] >= max_r:
                    # Auto-defer: exceeded max retries
                    self.defer(task["tag"], f"exceeded {max_r} retries")
                    continue

            task["score"] = self._score(task)
            eligible.append(task)

        if not eligible:
            return None

        eligible.sort(key=lambda t: t["score"], reverse=True)
        return eligible[0]

    # -- state transitions --

    def mark_running(self, tag: str) -> bool:
        """Transition task to running state."""
        fd = self._acquire_lock()
        try:
            sidecar = self._load()
            if tag not in sidecar:
                return False
            entry = sidecar[tag]
            entry["state"] = "running"
            entry["last_run"] = _now_iso()
            entry["attempts"] = entry.get("attempts", 0) + 1
            entry["updated_at"] = _now_iso()
            self._save(sidecar)
            return True
        finally:
            self._release_lock(fd)

    def mark_succeeded(self, tag: str, annotation: str = "") -> bool:
        """Transition task to succeeded. Also marks [x] in QUEUE.md."""
        fd = self._acquire_lock()
        try:
            sidecar = self._load()
            if tag not in sidecar:
                return False
            entry = sidecar[tag]
            entry["state"] = "succeeded"
            entry["updated_at"] = _now_iso()
            entry["failure_reason"] = None
            self._save(sidecar)

            # Mark [x] in QUEUE.md
            self._mark_checkbox(tag, annotation)
            return True
        finally:
            self._release_lock(fd)

    def mark_failed(self, tag: str, reason: str = "") -> bool:
        """Transition task to failed with backoff.

        If max retries exceeded, auto-defers.
        """
        fd = self._acquire_lock()
        try:
            sidecar = self._load()
            if tag not in sidecar:
                return False
            entry = sidecar[tag]
            entry["state"] = "failed"
            entry["failure_reason"] = reason[:500] if reason else None
            entry["last_failure"] = _now_iso()
            entry["updated_at"] = _now_iso()

            # Compute backoff (capped at BACKOFF_CAP heartbeat cycles ~= hours)
            attempts = entry.get("attempts", 1)
            skip_hours = min(BACKOFF_CAP, attempts)
            entry["skip_until"] = time.time() + (skip_hours * 3600)

            # Check if we should auto-defer
            max_r = MAX_RETRIES.get(entry.get("priority", "P1"), DEFAULT_MAX_RETRIES)
            if attempts >= max_r:
                entry["state"] = "deferred"
                # Annotate in QUEUE.md so operator sees it
                self._annotate_deferred(tag, reason)

            self._save(sidecar)
            return True
        finally:
            self._release_lock(fd)

    def defer(self, tag: str, reason: str = "") -> bool:
        """Explicitly defer a task (max retries exceeded or manual)."""
        fd = self._acquire_lock()
        try:
            sidecar = self._load()
            if tag not in sidecar:
                return False
            entry = sidecar[tag]
            entry["state"] = "deferred"
            entry["failure_reason"] = reason[:500] if reason else entry.get("failure_reason")
            entry["updated_at"] = _now_iso()
            self._save(sidecar)
            self._annotate_deferred(tag, reason)
            return True
        finally:
            self._release_lock(fd)

    def reset(self, tag: str) -> bool:
        """Reset a deferred/failed task back to pending (operator retry)."""
        fd = self._acquire_lock()
        try:
            sidecar = self._load()
            if tag not in sidecar:
                return False
            entry = sidecar[tag]
            entry["state"] = "pending"
            entry["attempts"] = 0
            entry["failure_reason"] = None
            entry["skip_until"] = 0
            entry["updated_at"] = _now_iso()
            self._save(sidecar)
            return True
        finally:
            self._release_lock(fd)

    # -- QUEUE.md manipulation --

    def _mark_checkbox(self, tag: str, annotation: str = "") -> None:
        """Mark a task [x] in QUEUE.md by tag."""
        if not os.path.exists(self.queue_file):
            return
        with open(self.queue_file) as f:
            content = f.read()

        tag_pattern = re.compile(
            rf"^(- \[) \] (\[{re.escape(tag)}\].*)$", re.MULTILINE
        )
        suffix = f" ({annotation})" if annotation else ""

        new_content, count = tag_pattern.subn(
            rf"\g<1>x] \g<2>{suffix}", content, count=1
        )
        if count > 0:
            with open(self.queue_file, "w") as f:
                f.write(new_content)

    def _annotate_deferred(self, tag: str, reason: str = "") -> None:
        """Add a deferred annotation to a task in QUEUE.md."""
        if not os.path.exists(self.queue_file):
            return
        with open(self.queue_file) as f:
            content = f.read()

        tag_pattern = re.compile(
            rf"^(- \[ \] \[{re.escape(tag)}\].*)$", re.MULTILINE
        )
        reason_short = reason[:100] if reason else "max retries"
        annotation = f" *(deferred: {reason_short})*"

        # Only annotate if not already annotated
        if f"*(deferred:" in content and tag in content:
            return

        new_content, count = tag_pattern.subn(
            rf"\g<1>{annotation}", content, count=1
        )
        if count > 0:
            with open(self.queue_file, "w") as f:
                f.write(new_content)

    # -- observability --

    def stats(self) -> dict:
        """Queue health metrics for monitoring and CLI."""
        tasks, sidecar = self.reconcile()
        now = datetime.now(timezone.utc)

        # Count by state
        counts = {"pending": 0, "running": 0, "failed": 0, "deferred": 0, "succeeded": 0}
        completed_24h = 0
        failed_24h = 0
        attempt_totals = []
        oldest_pending_hours = 0.0
        stuck_running = []
        chronic_failures = []

        for tag, entry in sidecar.items():
            state = entry.get("state", "pending")
            if state in counts:
                counts[state] += 1

            updated = entry.get("updated_at", "")
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    age_hours = (now - updated_dt).total_seconds() / 3600
                except (ValueError, TypeError):
                    age_hours = 0

                if state == "succeeded" and age_hours <= 24:
                    completed_24h += 1
                if state == "failed" and age_hours <= 24:
                    failed_24h += 1
                if state == "running" and age_hours > 2:
                    stuck_running.append(tag)

            if state == "succeeded":
                attempt_totals.append(entry.get("attempts", 1))

            if state == "pending":
                created = entry.get("created_at", "")
                if created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        pending_hours = (now - created_dt).total_seconds() / 3600
                        oldest_pending_hours = max(oldest_pending_hours, pending_hours)
                    except (ValueError, TypeError):
                        pass

            if state == "deferred":
                chronic_failures.append(tag)

        avg_attempts = round(sum(attempt_totals) / len(attempt_totals), 2) if attempt_totals else 0.0

        return {
            "pending": counts["pending"],
            "running": counts["running"],
            "failed": counts["failed"],
            "deferred": counts["deferred"],
            "total": sum(counts.values()),
            "completed_24h": completed_24h,
            "failed_24h": failed_24h,
            "avg_attempts": avg_attempts,
            "oldest_pending_hours": round(oldest_pending_hours, 1),
            "stuck_running": stuck_running,
            "chronic_failures": chronic_failures,
        }

    def get_task_state(self, tag: str) -> Optional[dict]:
        """Get sidecar state for a specific tag."""
        sidecar = self._load()
        return sidecar.get(tag)

    # -- run records --

    def start_run(self, tag: str) -> str:
        """Start a run record for a task. Returns run_id.

        Also calls mark_running() to transition state.
        """
        run_id = f"{tag}-{uuid.uuid4().hex[:8]}"
        self.mark_running(tag)
        record = {
            "run_id": run_id,
            "tag": tag,
            "started_at": _now_iso(),
            "ended_at": None,
            "duration_s": None,
            "outcome": "running",
            "error": None,
            "exit_code": None,
        }
        _append_run(record, self.runs_file)
        return run_id

    def end_run(self, run_id: str, outcome: str, exit_code: int = 0,
                error: str = "", duration_s: float = None) -> bool:
        """End a run record by run_id. Also calls mark_succeeded/mark_failed.

        outcome: 'success', 'failure', 'timeout', 'crash'
        Returns True if the run record was found and updated.
        """
        now = _now_iso()
        tag = run_id.rsplit("-", 1)[0] if "-" in run_id else run_id
        # Extract tag properly (everything before the last -hexchars)
        parts = run_id.split("-")
        if len(parts) >= 2:
            tag = "-".join(parts[:-1])

        # Update the run record in-place (find last matching run_id)
        updated = _update_run(run_id, {
            "ended_at": now,
            "duration_s": round(duration_s, 2) if duration_s else None,
            "outcome": outcome,
            "exit_code": exit_code,
            "error": error[:500] if error else None,
        }, self.runs_file)

        # Update sidecar state
        if outcome == "success":
            self.mark_succeeded(tag, now)
        elif outcome in ("failure", "timeout", "crash"):
            self.mark_failed(tag, error or outcome)

        return updated

    def get_runs(self, tag: str, limit: int = 20) -> list[dict]:
        """Get run records for a specific task tag, most recent first."""
        runs = _load_runs(runs_file=self.runs_file)
        matching = [r for r in runs if r.get("tag") == tag]
        return list(reversed(matching[-limit:]))

    def recent_runs(self, limit: int = 20) -> list[dict]:
        """Get the most recent run records across all tasks."""
        runs = _load_runs(runs_file=self.runs_file)
        return list(reversed(runs[-limit:]))

    def run_stats(self) -> dict:
        """Run record summary statistics."""
        runs = _load_runs(runs_file=self.runs_file)
        now = datetime.now(timezone.utc)
        day_ago = now.timestamp() - 86400

        total = len(runs)
        recent = [r for r in runs if _parse_ts(r.get("started_at")) > day_ago]
        outcomes = {}
        durations = []
        for r in recent:
            o = r.get("outcome", "unknown")
            outcomes[o] = outcomes.get(o, 0) + 1
            if r.get("duration_s"):
                durations.append(r["duration_s"])

        return {
            "total_runs": total,
            "runs_24h": len(recent),
            "outcomes_24h": outcomes,
            "avg_duration_24h": round(sum(durations) / len(durations), 1) if durations else None,
            "success_rate_24h": round(
                outcomes.get("success", 0) / len(recent), 3
            ) if recent else None,
        }


# ---------------------------------------------------------------------------
# Run record persistence (append-only JSONL)
# ---------------------------------------------------------------------------

def _append_run(record: dict, runs_file: str = RUNS_FILE) -> None:
    """Append a run record to the JSONL file."""
    os.makedirs(os.path.dirname(runs_file), exist_ok=True)
    with open(runs_file, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _load_runs(limit: int = 500, runs_file: str = RUNS_FILE) -> list[dict]:
    """Load recent run records (tail of JSONL file)."""
    if not os.path.exists(runs_file):
        return []
    records = []
    try:
        with open(runs_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return []
    return records[-limit:]


def _update_run(run_id: str, updates: dict, runs_file: str = RUNS_FILE) -> bool:
    """Update a run record in the JSONL file by rewriting matching line.

    Only updates the last occurrence of run_id (the active run).
    """
    if not os.path.exists(runs_file):
        return False
    try:
        with open(runs_file) as f:
            lines = f.readlines()
    except OSError:
        return False

    # Find last line with matching run_id
    target_idx = None
    for i in range(len(lines) - 1, -1, -1):
        try:
            rec = json.loads(lines[i])
            if rec.get("run_id") == run_id:
                target_idx = i
                break
        except (json.JSONDecodeError, ValueError):
            continue

    if target_idx is None:
        return False

    rec = json.loads(lines[target_idx])
    rec.update(updates)
    lines[target_idx] = json.dumps(rec, default=str) + "\n"

    tmp = runs_file + ".tmp"
    with open(tmp, "w") as f:
        f.writelines(lines)
    os.rename(tmp, runs_file)
    return True


def _parse_ts(iso_str: str) -> float:
    """Parse ISO timestamp to epoch seconds. Returns 0 on failure."""
    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0


# Module-level singleton
engine = QueueEngine()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    """Minimal CLI for queue engine operations."""
    import sys
    args = sys.argv[1:] if len(sys.argv) > 1 else ["stats"]
    cmd = args[0]

    if cmd == "stats":
        s = engine.stats()
        print(json.dumps(s, indent=2))

    elif cmd == "select":
        task = engine.select_next()
        if task:
            print(json.dumps(task, indent=2, default=str))
        else:
            print("No eligible tasks.")

    elif cmd == "state" and len(args) > 1:
        tag = args[1]
        state = engine.get_task_state(tag)
        if state:
            print(json.dumps(state, indent=2))
        else:
            print(f"No state for tag: {tag}")

    elif cmd == "mark-running" and len(args) > 1:
        ok = engine.mark_running(args[1])
        print("OK" if ok else "FAIL: tag not found")

    elif cmd == "mark-succeeded" and len(args) > 1:
        annotation = args[2] if len(args) > 2 else ""
        ok = engine.mark_succeeded(args[1], annotation)
        print("OK" if ok else "FAIL: tag not found")

    elif cmd == "mark-failed" and len(args) > 1:
        reason = args[2] if len(args) > 2 else ""
        ok = engine.mark_failed(args[1], reason)
        print("OK" if ok else "FAIL: tag not found")

    elif cmd == "reset" and len(args) > 1:
        ok = engine.reset(args[1])
        print("OK" if ok else "FAIL: tag not found")

    elif cmd == "reconcile":
        tasks, _ = engine.reconcile()
        for t in tasks:
            print(f"[{t['tag']}] state={t['state']} attempts={t['attempts']} priority={t['priority']}")

    elif cmd == "runs" and len(args) > 1:
        runs = engine.get_runs(args[1])
        for r in runs:
            print(json.dumps(r, indent=2))

    elif cmd == "recent-runs":
        runs = engine.recent_runs()
        for r in runs:
            dur = f"{r['duration_s']}s" if r.get("duration_s") else "?"
            print(f"[{r['tag']}] {r['outcome']} ({dur}) run={r['run_id']}")

    elif cmd == "run-stats":
        print(json.dumps(engine.run_stats(), indent=2))

    else:
        print("Usage: queue_engine.py {stats|select|state TAG|mark-running TAG|"
              "mark-succeeded TAG [ann]|mark-failed TAG [reason]|reset TAG|"
              "reconcile|runs TAG|recent-runs|run-stats}")


if __name__ == "__main__":
    _cli()
