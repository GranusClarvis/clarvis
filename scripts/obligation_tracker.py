#!/usr/bin/env python3
"""
Obligation Tracker — Durable promise enforcement for Clarvis.

Root problem: Clarvis says "I'll do X going forward" but no durable state records
the obligation, so it drifts after context compression / restarts.

This module provides:
1. A durable obligation registry (JSON file, survives restarts)
2. Standing instructions with frequency-based enforcement
3. Git hygiene checks as the first concrete application
4. CLI for managing obligations
5. Integration hooks for heartbeat preflight/postflight

Obligation lifecycle:
  RECEIVED → RECORDED → CHECKED → SATISFIED / VIOLATED / PENDING

Usage:
    from obligation_tracker import ObligationTracker
    tracker = ObligationTracker()
    tracker.check_all()            # Run all due checks
    tracker.record_obligation(...) # Record a new obligation
    tracker.git_hygiene_check()    # Run git hygiene specifically

CLI:
    python3 obligation_tracker.py check          # Run all due obligation checks
    python3 obligation_tracker.py list           # List all obligations
    python3 obligation_tracker.py add "desc"     # Add a new obligation
    python3 obligation_tracker.py git-hygiene    # Run git hygiene check
    python3 obligation_tracker.py status         # Summary status
    python3 obligation_tracker.py verify         # Self-test / verification
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
OBLIGATIONS_FILE = os.path.join(WORKSPACE, "data", "obligations.json")
OBLIGATIONS_LOG = os.path.join(WORKSPACE, "data", "obligations_log.jsonl")
QUEUE_FILE = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE.md")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


class ObligationTracker:
    """Manages durable obligations with state tracking and enforcement."""

    def __init__(self, filepath: str = OBLIGATIONS_FILE):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"obligations": [], "version": 1}

    def _save(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        tmp = self.filepath + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.filepath)

    def _log_event(self, obligation_id: str, event: str, detail: str = ""):
        """Append to audit log."""
        entry = {
            "ts": _now(),
            "obligation_id": obligation_id,
            "event": event,
            "detail": detail,
        }
        os.makedirs(os.path.dirname(OBLIGATIONS_LOG), exist_ok=True)
        with open(OBLIGATIONS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # ── CRUD ──────────────────────────────────────────────────────────

    def get(self, obligation_id: str) -> Optional[dict]:
        for ob in self.data["obligations"]:
            if ob["id"] == obligation_id:
                return ob
        return None

    def list_all(self) -> list:
        return self.data["obligations"]

    def list_active(self) -> list:
        return [ob for ob in self.data["obligations"]
                if ob["state"]["status"] not in ("retired", "superseded")]

    def record_obligation(self, label: str, description: str,
                          ob_type: str = "standing_instruction",
                          frequency: str = "every_heartbeat",
                          check_command: Optional[str] = None,
                          source: str = "manual",
                          tags: Optional[list] = None) -> dict:
        """Record a new obligation. Returns the obligation dict."""
        ob_id = f"ob_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{len(self.data['obligations'])}"
        ob = {
            "id": ob_id,
            "type": ob_type,
            "label": label,
            "description": description,
            "source": source,
            "created_at": _now(),
            "frequency": frequency,
            "check_command": check_command,
            "tags": tags or [],
            "state": {
                "status": "active",
                "last_checked": None,
                "last_satisfied": None,
                "check_count": 0,
                "satisfied_count": 0,
                "violated_count": 0,
                "consecutive_violations": 0,
                "escalation_level": 0,
            },
        }
        self.data["obligations"].append(ob)
        self._save()
        self._log_event(ob_id, "recorded", f"source={source}: {label}")
        return ob

    def retire(self, obligation_id: str, reason: str = ""):
        ob = self.get(obligation_id)
        if ob:
            ob["state"]["status"] = "retired"
            ob["state"]["retired_at"] = _now()
            ob["state"]["retire_reason"] = reason
            self._save()
            self._log_event(obligation_id, "retired", reason)

    # ── CHECKING ENGINE ───────────────────────────────────────────────

    def _is_due(self, ob: dict) -> bool:
        """Check if an obligation is due for verification."""
        if ob["state"]["status"] != "active":
            return False

        last = ob["state"]["last_checked"]
        if last is None:
            return True

        freq = ob.get("frequency", "every_heartbeat")
        last_dt = _parse_iso(last)
        now = datetime.now(timezone.utc)

        intervals = {
            "every_heartbeat": timedelta(minutes=30),
            "hourly": timedelta(hours=1),
            "every_4h": timedelta(hours=4),
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
        }
        interval = intervals.get(freq, timedelta(hours=1))
        return (now - last_dt) >= interval

    def check_obligation(self, ob: dict) -> dict:
        """Run a single obligation check. Returns {satisfied, detail}."""
        ob["state"]["last_checked"] = _now()
        ob["state"]["check_count"] += 1

        # If it has a check_command, run it
        if ob.get("check_command"):
            try:
                result = subprocess.run(
                    ob["check_command"],
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=WORKSPACE,
                )
                satisfied = result.returncode == 0
                detail = result.stdout.strip()[:500] or result.stderr.strip()[:500]
            except subprocess.TimeoutExpired:
                satisfied = False
                detail = "check_command timed out"
            except Exception as e:
                satisfied = False
                detail = f"check_command error: {e}"
        # Built-in checks by tag
        elif "git-hygiene" in ob.get("tags", []):
            check_result = self.git_hygiene_check()
            satisfied = check_result["clean"]
            detail = check_result["summary"]
        else:
            # No check mechanism — just mark as checked
            satisfied = True
            detail = "no check mechanism; assumed satisfied"

        # Update state
        if satisfied:
            ob["state"]["satisfied_count"] += 1
            ob["state"]["last_satisfied"] = _now()
            ob["state"]["consecutive_violations"] = 0
            if ob["state"]["escalation_level"] > 0:
                ob["state"]["escalation_level"] = max(0, ob["state"]["escalation_level"] - 1)
        else:
            ob["state"]["violated_count"] += 1
            ob["state"]["consecutive_violations"] += 1
            # Escalate after repeated violations
            if ob["state"]["consecutive_violations"] >= 3:
                ob["state"]["escalation_level"] = min(3, ob["state"]["escalation_level"] + 1)

        self._save()
        event = "satisfied" if satisfied else "violated"
        self._log_event(ob["id"], event, detail[:200])

        return {"satisfied": satisfied, "detail": detail, "obligation_id": ob["id"]}

    def check_all(self) -> list:
        """Check all due obligations. Returns list of results."""
        results = []
        for ob in self.list_active():
            if self._is_due(ob):
                result = self.check_obligation(ob)
                results.append(result)
        return results

    def get_violations(self) -> list:
        """Get all obligations with active violations (for escalation)."""
        return [ob for ob in self.list_active()
                if ob["state"]["consecutive_violations"] > 0]

    def get_escalations(self) -> list:
        """Get obligations that need escalation (3+ consecutive violations)."""
        return [ob for ob in self.list_active()
                if ob["state"]["escalation_level"] > 0]

    # ── GIT HYGIENE (concrete application) ────────────────────────────

    def git_hygiene_check(self) -> dict:
        """Check git hygiene: dirty tree age, unpushed commits, ahead-of-origin.

        Returns:
            {clean: bool, dirty_files: int, dirty_age_minutes: float,
             unpushed_commits: int, ahead_count: int, behind_count: int,
             summary: str, actions: list}
        """
        result = {
            "clean": True,
            "dirty_files": 0,
            "dirty_age_minutes": 0.0,
            "unpushed_commits": 0,
            "ahead_count": 0,
            "behind_count": 0,
            "summary": "",
            "actions": [],
        }

        try:
            # 1. Check for uncommitted changes
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10, cwd=WORKSPACE,
            )
            dirty_files = [l for l in status.stdout.strip().split("\n") if l.strip()]
            result["dirty_files"] = len(dirty_files)

            if dirty_files:
                result["clean"] = False
                # Estimate dirty age from tracked changes AND untracked files
                try:
                    # Tracked modified files from git diff
                    mtime_cmd = subprocess.run(
                        ["git", "diff", "--name-only"],
                        capture_output=True, text=True, timeout=10, cwd=WORKSPACE,
                    )
                    changed_files = [f for f in mtime_cmd.stdout.strip().split("\n") if f.strip()]
                    # Also include untracked files from porcelain output
                    for line in dirty_files:
                        if line.startswith("??"):
                            upath = line[3:].strip()
                            if upath and upath not in changed_files:
                                changed_files.append(upath)
                    if changed_files:
                        oldest_mtime = None
                        for cf in changed_files[:20]:
                            fpath = os.path.join(WORKSPACE, cf)
                            if os.path.exists(fpath):
                                mt = os.path.getmtime(fpath)
                                if oldest_mtime is None or mt < oldest_mtime:
                                    oldest_mtime = mt
                        if oldest_mtime:
                            age_min = (time.time() - oldest_mtime) / 60
                            result["dirty_age_minutes"] = round(age_min, 1)
                except Exception:
                    pass

                result["actions"].append("commit_or_stash")

            # 2. Check for unpushed commits (ahead of origin)
            try:
                ahead = subprocess.run(
                    ["git", "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True, text=True, timeout=10, cwd=WORKSPACE,
                )
                if ahead.returncode == 0:
                    count = int(ahead.stdout.strip())
                    result["ahead_count"] = count
                    result["unpushed_commits"] = count
                    if count > 0:
                        result["clean"] = False
                        result["actions"].append("push")
            except Exception:
                pass

            # 3. Check if behind origin
            try:
                behind = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD..origin/main"],
                    capture_output=True, text=True, timeout=10, cwd=WORKSPACE,
                )
                if behind.returncode == 0:
                    count = int(behind.stdout.strip())
                    result["behind_count"] = count
                    if count > 0:
                        result["actions"].append("pull")
            except Exception:
                pass

            # Build summary
            parts = []
            if result["dirty_files"] > 0:
                age_str = f" ({result['dirty_age_minutes']:.0f}m old)" if result["dirty_age_minutes"] > 0 else ""
                parts.append(f"{result['dirty_files']} dirty files{age_str}")
            if result["ahead_count"] > 0:
                parts.append(f"{result['ahead_count']} unpushed commits")
            if result["behind_count"] > 0:
                parts.append(f"{result['behind_count']} commits behind origin")
            if not parts:
                parts.append("clean")
            result["summary"] = "; ".join(parts)

        except Exception as e:
            result["summary"] = f"git check error: {e}"
            result["clean"] = False

        return result

    # ── AUTO-COMMIT+PUSH (git hygiene enforcement) ─────────────────

    # Files/patterns that must NEVER be auto-committed
    SECRET_PATTERNS = (
        ".env", "credentials", "auth.json", "secret", "token",
        ".pem", ".key", "id_rsa", "id_ed25519", ".p12",
        "budget_config.json",  # contains Telegram bot token
    )

    def auto_commit_push(self, dry_run: bool = False) -> dict:
        """Auto-commit and push if dirty tree >60min and changes are safe.

        Safety checks:
        1. No files matching secret patterns
        2. No binary files over 1MB
        3. Dirty age > 60 minutes (avoids committing in-progress work)
        4. Only pushes if commits are ahead of origin

        Returns:
            {acted: bool, action: str, detail: str}
        """
        result = {"acted": False, "action": "none", "detail": ""}

        try:
            hygiene = self.git_hygiene_check()

            # Case 1: Unpushed commits — push them
            if hygiene["unpushed_commits"] > 0 and hygiene["dirty_files"] == 0:
                if dry_run:
                    result["action"] = "would_push"
                    result["detail"] = f"{hygiene['unpushed_commits']} unpushed commits"
                    return result
                push = subprocess.run(
                    ["git", "push", "origin", "main"],
                    capture_output=True, text=True, timeout=60, cwd=WORKSPACE,
                )
                if push.returncode == 0:
                    result["acted"] = True
                    result["action"] = "pushed"
                    result["detail"] = f"Pushed {hygiene['unpushed_commits']} commits"
                    self._log_event("git-hygiene", "auto_pushed", result["detail"])
                else:
                    result["detail"] = f"Push failed: {push.stderr.strip()[:200]}"
                    self._log_event("git-hygiene", "auto_push_failed", result["detail"])
                return result

            # Case 2: Dirty tree — check if safe to commit
            if hygiene["dirty_files"] == 0:
                result["detail"] = "clean tree"
                return result

            if hygiene["dirty_age_minutes"] < 60:
                result["detail"] = f"Dirty {hygiene['dirty_age_minutes']:.0f}m (< 60m threshold)"
                return result

            # Get list of changed files
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10, cwd=WORKSPACE,
            )
            changed_files = []
            for line in status.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                # Extract filename (handle renames: "R  old -> new")
                parts = line[3:].strip()
                if " -> " in parts:
                    parts = parts.split(" -> ")[-1]
                changed_files.append(parts)

            if not changed_files:
                result["detail"] = "no changed files detected"
                return result

            # Safety check: no secrets
            for f in changed_files:
                f_lower = f.lower()
                for pattern in self.SECRET_PATTERNS:
                    if pattern.lower() in f_lower:
                        result["detail"] = f"Blocked: {f} matches secret pattern '{pattern}'"
                        self._log_event("git-hygiene", "auto_commit_blocked_secret", result["detail"])
                        return result

            # Safety check: no large binary files (>1MB)
            for f in changed_files:
                fpath = os.path.join(WORKSPACE, f)
                if os.path.exists(fpath) and os.path.getsize(fpath) > 1_000_000:
                    # Check if it's binary
                    try:
                        with open(fpath, "rb") as fh:
                            chunk = fh.read(8192)
                            if b"\x00" in chunk:
                                result["detail"] = f"Blocked: {f} is a large binary ({os.path.getsize(fpath)} bytes)"
                                self._log_event("git-hygiene", "auto_commit_blocked_binary", result["detail"])
                                return result
                    except (OSError, IOError):
                        pass

            if dry_run:
                result["action"] = "would_commit_push"
                result["detail"] = f"{len(changed_files)} files, {hygiene['dirty_age_minutes']:.0f}m old"
                return result

            # Stage all changes
            add_result = subprocess.run(
                ["git", "add", "-A"],
                capture_output=True, text=True, timeout=30, cwd=WORKSPACE,
            )
            if add_result.returncode != 0:
                result["detail"] = f"git add failed: {add_result.stderr.strip()[:200]}"
                return result

            # Commit with descriptive message
            file_summary = ", ".join(changed_files[:5])
            if len(changed_files) > 5:
                file_summary += f" (+{len(changed_files) - 5} more)"
            commit_msg = (
                f"chore: auto-commit {len(changed_files)} files "
                f"(dirty {hygiene['dirty_age_minutes']:.0f}m)\n\n"
                f"Files: {file_summary}\n"
                f"Auto-committed by obligation_tracker git-hygiene enforcement."
            )
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True, text=True, timeout=30, cwd=WORKSPACE,
            )
            if commit_result.returncode != 0:
                result["detail"] = f"git commit failed: {commit_result.stderr.strip()[:200]}"
                self._log_event("git-hygiene", "auto_commit_failed", result["detail"])
                return result

            # Push
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True, text=True, timeout=60, cwd=WORKSPACE,
            )
            if push_result.returncode == 0:
                result["acted"] = True
                result["action"] = "committed_and_pushed"
                result["detail"] = f"Committed {len(changed_files)} files ({hygiene['dirty_age_minutes']:.0f}m old) and pushed"
                self._log_event("git-hygiene", "auto_committed_pushed", result["detail"])
            else:
                # Commit succeeded but push failed — still count as acted
                result["acted"] = True
                result["action"] = "committed"
                result["detail"] = f"Committed {len(changed_files)} files but push failed: {push_result.stderr.strip()[:200]}"
                self._log_event("git-hygiene", "auto_committed_push_failed", result["detail"])

        except Exception as e:
            result["detail"] = f"auto_commit_push error: {e}"
            self._log_event("git-hygiene", "auto_commit_push_error", str(e)[:200])

        return result

    def escalate_to_queue(self, ob: dict, reason: str = ""):
        """Push an escalation task to QUEUE.md via queue_writer if available."""
        tag = f"OBLIGATION_ESCALATION_{ob['id']}"
        desc = f"[{tag}] Obligation violated {ob['state']['consecutive_violations']}x: {ob['label']}. {reason}"

        try:
            sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
            from queue_writer import add_task
            added = add_task(desc, priority="P1", source="obligation_tracker")
            if added:
                self._log_event(ob["id"], "escalated_to_queue", desc[:200])
        except ImportError:
            # Fallback: append directly
            try:
                with open(QUEUE_FILE, "a") as f:
                    f.write(f"\n- [ ] {desc}\n")
                self._log_event(ob["id"], "escalated_to_queue_direct", desc[:200])
            except Exception as e:
                self._log_event(ob["id"], "escalation_failed", str(e))

    # ── PREFLIGHT / POSTFLIGHT HOOKS ──────────────────────────────────

    def preflight_check(self) -> dict:
        """Run during heartbeat preflight. Returns context for the executor.

        Returns:
            {checked: int, violations: list, escalations: list,
             git_hygiene: dict, obligation_context: str}
        """
        results = self.check_all()

        violations = self.get_violations()
        escalations = self.get_escalations()

        # Auto-escalate if needed
        for ob in escalations:
            if ob["state"]["escalation_level"] >= 2 and ob["state"].get("_last_queue_escalation") != _now()[:10]:
                self.escalate_to_queue(ob, "repeated violations")
                ob["state"]["_last_queue_escalation"] = _now()[:10]
                self._save()

        # Build context string for prompt injection
        context_parts = []
        if violations:
            context_parts.append("OBLIGATION VIOLATIONS:")
            for ob in violations:
                context_parts.append(
                    f"  - {ob['label']}: {ob['state']['consecutive_violations']}x violated "
                    f"(escalation level {ob['state']['escalation_level']})"
                )
        git_result = self.git_hygiene_check()
        if not git_result["clean"]:
            context_parts.append(f"GIT HYGIENE: {git_result['summary']}")
            if git_result["dirty_age_minutes"] > 60:
                context_parts.append(
                    f"  WARNING: dirty tree is {git_result['dirty_age_minutes']:.0f}m old — commit useful work"
                )
            if git_result["unpushed_commits"] > 0:
                context_parts.append(
                    f"  WARNING: {git_result['unpushed_commits']} commits not pushed to origin"
                )

        return {
            "checked": len(results),
            "violations": [{"id": ob["id"], "label": ob["label"],
                           "consecutive": ob["state"]["consecutive_violations"]}
                          for ob in violations],
            "escalations": [{"id": ob["id"], "label": ob["label"],
                            "level": ob["state"]["escalation_level"]}
                           for ob in escalations],
            "git_hygiene": git_result,
            "obligation_context": "\n".join(context_parts) if context_parts else "",
        }

    def postflight_record(self, task: str, task_status: str, output_text: str = ""):
        """Record obligation-relevant outcomes after task execution.

        Scans output for promise patterns and auto-records new obligations.
        """
        # 1. Check if task addressed any active obligation
        for ob in self.list_active():
            if self._task_addresses_obligation(task, ob):
                if task_status == "success":
                    ob["state"]["last_satisfied"] = _now()
                    ob["state"]["satisfied_count"] += 1
                    ob["state"]["consecutive_violations"] = 0
                    self._log_event(ob["id"], "addressed_by_task", task[:100])
                self._save()

        # 2. Scan output for promise patterns (best-effort)
        promises = self._extract_promises(output_text)
        for promise in promises:
            self._log_event("system", "promise_detected", promise[:200])

    def _task_addresses_obligation(self, task: str, ob: dict) -> bool:
        """Heuristic: does this task address this obligation?"""
        task_lower = task.lower()
        label_lower = ob["label"].lower()
        # Check tag overlap
        for tag in ob.get("tags", []):
            if tag.lower() in task_lower:
                return True
        # Check label word overlap
        label_words = set(re.findall(r'[a-z]+', label_lower))
        task_words = set(re.findall(r'[a-z]+', task_lower))
        if len(label_words) > 0:
            overlap = len(label_words & task_words) / len(label_words)
            if overlap > 0.5:
                return True
        return False

    def _extract_promises(self, text: str) -> list:
        """Extract promise-like patterns from output text."""
        if not text:
            return []
        # Match common promise patterns
        patterns = [
            r"I(?:'ll| will) (?:do|handle|take care of|ensure|make sure|keep|maintain|always|never) .{10,80}(?:going forward|from now on|in the future|automatically|every time)",
            r"(?:going forward|from now on),? I(?:'ll| will) .{10,80}",
            r"I(?:'ve| have) set up .{10,60} (?:to run|to check|to monitor|automatically)",
        ]
        promises = []
        text_lower = text[-5000:]  # Only scan tail
        for pat in patterns:
            matches = re.findall(pat, text_lower, re.IGNORECASE)
            promises.extend(matches[:3])  # Cap per pattern
        return promises[:5]  # Cap total

    # ── STATUS / REPORTING ────────────────────────────────────────────

    def status_summary(self) -> str:
        """Human-readable status summary."""
        active = self.list_active()
        violations = self.get_violations()
        escalations = self.get_escalations()
        git = self.git_hygiene_check()

        lines = [f"=== Obligation Tracker Status ==="]
        lines.append(f"Active obligations: {len(active)}")
        lines.append(f"Current violations: {len(violations)}")
        lines.append(f"Escalations: {len(escalations)}")
        lines.append(f"Git hygiene: {'CLEAN' if git['clean'] else 'DIRTY — ' + git['summary']}")
        lines.append("")

        for ob in active:
            s = ob["state"]
            status_icon = "✓" if s["consecutive_violations"] == 0 else f"✗ ({s['consecutive_violations']}x)"
            lines.append(f"  [{status_icon}] {ob['label']} ({ob['type']}, {ob['frequency']})")
            if s["last_checked"]:
                lines.append(f"      Last checked: {s['last_checked'][:19]}")
            if s["last_satisfied"]:
                lines.append(f"      Last satisfied: {s['last_satisfied'][:19]}")

        return "\n".join(lines)


# ── SEED: Default obligations ─────────────────────────────────────────

def seed_defaults(tracker: ObligationTracker):
    """Seed the default obligations if the file is empty."""
    if tracker.list_all():
        return  # Already seeded

    # Git hygiene standing instruction
    tracker.record_obligation(
        label="Git hygiene: commit and push useful work",
        description=(
            "Standing instruction from operator: commit and push useful work without prompting. "
            "Detect dirty tree age >60min, unpushed commits, ahead-of-origin state. "
            "If fully autonomous commit/push is not safe, escalate to queue instead of ignoring."
        ),
        ob_type="standing_instruction",
        frequency="every_heartbeat",
        source="user_directive",
        tags=["git-hygiene", "user-directive"],
    )

    # Promise follow-through meta-obligation
    tracker.record_obligation(
        label="Promise follow-through enforcement",
        description=(
            "Meta-obligation: when Clarvis says 'I will do X going forward', "
            "the obligation must be recorded durably or the promise must be explicitly declined. "
            "Speech without state transition is a bug."
        ),
        ob_type="standing_instruction",
        frequency="daily",
        check_command=(
            "python3 -c \""
            "import json, os; "
            "f=os.path.join(os.environ.get('CLARVIS_WORKSPACE','/home/agent/.openclaw/workspace'),'data','obligations_log.jsonl'); "
            "lines=open(f).readlines()[-50:] if os.path.exists(f) else []; "
            "promises=[l for l in lines if 'promise_detected' in l]; "
            "print(f'{len(promises)} promises detected in last 50 log entries'); "
            "exit(0)\""
        ),
        source="system",
        tags=["meta", "promise-enforcement"],
    )


# ── VERIFICATION ──────────────────────────────────────────────────────

def run_verification() -> bool:
    """Self-test: create, check, violate, escalate, retire — then clean up."""
    import tempfile
    print("=== Obligation Tracker Verification ===")
    errors = []

    # Use temp file for test
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        test_file = tf.name

    try:
        tracker = ObligationTracker(filepath=test_file)

        # 1. Record
        ob = tracker.record_obligation(
            label="Test obligation",
            description="Verify the tracker works",
            frequency="every_heartbeat",
            source="test",
            tags=["test"],
        )
        assert ob["id"], "Missing ID"
        assert tracker.get(ob["id"]) is not None, "Get failed"
        print(f"  [PASS] Record obligation: {ob['id']}")

        # 2. Check (no check_command, assumed satisfied)
        result = tracker.check_obligation(ob)
        assert result["satisfied"], "Should be satisfied with no check_command"
        assert ob["state"]["check_count"] == 1
        assert ob["state"]["satisfied_count"] == 1
        print(f"  [PASS] Check obligation (satisfied)")

        # 3. Simulate violations
        ob["check_command"] = "exit 1"  # Will fail
        tracker._save()
        for i in range(4):
            result = tracker.check_obligation(ob)
            assert not result["satisfied"], f"Should be violated (iter {i})"
        assert ob["state"]["consecutive_violations"] == 4
        assert ob["state"]["escalation_level"] > 0
        print(f"  [PASS] Violation tracking: {ob['state']['consecutive_violations']}x, level {ob['state']['escalation_level']}")

        # 4. Recovery
        ob["check_command"] = "exit 0"
        tracker._save()
        result = tracker.check_obligation(ob)
        assert result["satisfied"]
        assert ob["state"]["consecutive_violations"] == 0
        print(f"  [PASS] Recovery: violations reset to 0")

        # 5. Git hygiene check
        git_result = tracker.git_hygiene_check()
        assert "summary" in git_result
        assert "clean" in git_result
        print(f"  [PASS] Git hygiene: {git_result['summary']}")

        # 6. Preflight hook
        pf = tracker.preflight_check()
        assert "checked" in pf
        assert "git_hygiene" in pf
        print(f"  [PASS] Preflight check: {pf['checked']} obligations checked")

        # 7. Promise extraction
        test_text = "I'll make sure to commit all changes going forward and keep the repo clean."
        promises = tracker._extract_promises(test_text)
        print(f"  [PASS] Promise extraction: {len(promises)} promises found in test text")

        # 8. Retire
        tracker.retire(ob["id"], "test complete")
        assert ob["state"]["status"] == "retired"
        assert len(tracker.list_active()) == 0
        print(f"  [PASS] Retire obligation")

        # 9. List/status
        assert len(tracker.list_all()) == 1
        status = tracker.status_summary()
        assert "Obligation Tracker Status" in status
        print(f"  [PASS] Status summary")

        print("\n=== ALL CHECKS PASSED ===")
        return True

    except Exception as e:
        print(f"\n  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.unlink(test_file)


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: obligation_tracker.py <check|list|add|git-hygiene|status|verify|seed>")
        sys.exit(1)

    cmd = sys.argv[1]
    tracker = ObligationTracker()

    if cmd == "check":
        results = tracker.check_all()
        for r in results:
            icon = "✓" if r["satisfied"] else "✗"
            print(f"  [{icon}] {r['obligation_id']}: {r['detail'][:100]}")
        if not results:
            print("  No obligations due for checking.")

    elif cmd == "list":
        for ob in tracker.list_all():
            s = ob["state"]
            status_str = s["status"]
            if s["consecutive_violations"] > 0:
                status_str += f" (VIOLATED {s['consecutive_violations']}x)"
            print(f"  {ob['id']}: {ob['label']} [{status_str}]")

    elif cmd == "add":
        if len(sys.argv) < 3:
            print("Usage: obligation_tracker.py add 'description' [--freq hourly|daily|every_heartbeat]")
            sys.exit(1)
        desc = sys.argv[2]
        freq = "daily"
        if "--freq" in sys.argv:
            idx = sys.argv.index("--freq")
            if idx + 1 < len(sys.argv):
                freq = sys.argv[idx + 1]
        ob = tracker.record_obligation(label=desc, description=desc, frequency=freq, source="cli")
        print(f"Recorded: {ob['id']}")

    elif cmd == "auto-fix":
        dry = "--dry-run" in sys.argv
        result = tracker.auto_commit_push(dry_run=dry)
        print(f"Auto-fix: {result['action']}")
        print(f"  {result['detail']}")
        if result["acted"]:
            print("  Git hygiene enforced successfully.")

    elif cmd == "git-hygiene":
        result = tracker.git_hygiene_check()
        print(f"Git hygiene: {'CLEAN' if result['clean'] else 'DIRTY'}")
        print(f"  {result['summary']}")
        if result["actions"]:
            print(f"  Actions needed: {', '.join(result['actions'])}")

    elif cmd == "status":
        print(tracker.status_summary())

    elif cmd == "verify":
        success = run_verification()
        sys.exit(0 if success else 1)

    elif cmd == "seed":
        seed_defaults(tracker)
        print(f"Seeded. Total obligations: {len(tracker.list_all())}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
