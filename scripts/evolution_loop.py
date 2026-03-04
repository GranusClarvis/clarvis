#!/usr/bin/env python3
"""
Hive-style Evolution Loop — Failure → Evolve → Redeploy

When something fails, this system:
1. CAPTURES the failure (what broke, context, error output)
2. ANALYZES it (pattern match against past failures, identify root cause)
3. GENERATES a fix strategy (concrete steps to resolve)
4. DEPLOYS the fix (via Claude Code or direct patch)
5. VERIFIES (re-run the failed operation)

Integrates with brain.py for persistent memory of failures and fixes.

Usage:
    from evolution_loop import EvolutionLoop
    loop = EvolutionLoop()

    # Log a failure
    failure_id = loop.capture_failure(
        component="cron_autonomous",
        error="timeout after 600s",
        context="running task: optimize brain queries",
        exit_code=124
    )

    # Analyze and generate fix
    analysis = loop.analyze_failure(failure_id)

    # Or run the full cycle
    result = loop.evolve(failure_id)

CLI:
    python evolution_loop.py capture <component> <error> [context]
    python evolution_loop.py analyze <failure_id>
    python evolution_loop.py evolve <failure_id>
    python evolution_loop.py status
    python evolution_loop.py history [n]
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Directories
DATA_DIR = Path("/home/agent/.openclaw/workspace/data/evolution")
FAILURES_DIR = DATA_DIR / "failures"
FIXES_DIR = DATA_DIR / "fixes"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FAILURES_DIR.mkdir(parents=True, exist_ok=True)
FIXES_DIR.mkdir(parents=True, exist_ok=True)


class EvolutionLoop:
    """Hive-style failure → evolve → redeploy cycle."""

    def __init__(self):
        self._brain = None

    @property
    def brain(self):
        if self._brain is None:
            try:
                from brain import brain as b
                self._brain = b
            except Exception:
                self._brain = None
        return self._brain

    # === PHASE 1: CAPTURE ===

    def capture_failure(self, component: str, error: str,
                        context: str = "", exit_code: int = 1,
                        stdout: str = "", stderr: str = "") -> str:
        """
        Capture a failure with full context.

        Args:
            component: What failed (script name, cron job, etc.)
            error: Error message or description
            context: What was being attempted
            exit_code: Process exit code
            stdout: Captured stdout (truncated to last 2000 chars)
            stderr: Captured stderr (truncated to last 2000 chars)

        Returns:
            failure_id string
        """
        now = datetime.now(timezone.utc)
        failure_id = f"fail_{now.strftime('%Y%m%d_%H%M%S')}_{component}"

        failure = {
            "id": failure_id,
            "component": component,
            "error": error,
            "context": context,
            "exit_code": exit_code,
            "stdout": stdout[-2000:] if stdout else "",
            "stderr": stderr[-2000:] if stderr else "",
            "timestamp": now.isoformat(),
            "status": "captured",  # captured → analyzing → fix_generated → fix_applied → verified | failed
            "fix_id": None,
            "retries": 0,
            "max_retries": 2,
        }

        # Save to disk
        failure_file = FAILURES_DIR / f"{failure_id}.json"
        failure_file.write_text(json.dumps(failure, indent=2))

        # Store in brain for pattern matching
        if self.brain:
            self.brain.store(
                f"FAILURE in {component}: {error}. Context: {context}",
                collection="clarvis-learnings",
                importance=0.8,
                tags=["failure", component, failure_id],
                source="evolution_loop",
            )

        return failure_id

    # === PHASE 2: ANALYZE ===

    def analyze_failure(self, failure_id: str) -> dict:
        """
        Analyze a failure: find patterns, similar past failures, root cause hypothesis.

        Returns dict with:
            - similar_failures: past failures with same component or error pattern
            - pattern: identified failure pattern (if any)
            - root_cause: hypothesized root cause
            - fix_strategy: recommended fix approach
        """
        failure = self._load_failure(failure_id)
        if not failure:
            return {"error": f"Failure {failure_id} not found"}

        failure["status"] = "analyzing"
        self._save_failure(failure)

        analysis = {
            "failure_id": failure_id,
            "similar_failures": [],
            "pattern": None,
            "root_cause": None,
            "fix_strategy": None,
        }

        # Find similar past failures
        past_failures = self._get_all_failures()
        for pf in past_failures:
            if pf["id"] == failure_id:
                continue
            # Match by component or similar error text
            if (pf["component"] == failure["component"] or
                    self._error_similarity(pf["error"], failure["error"]) > 0.5):
                analysis["similar_failures"].append({
                    "id": pf["id"],
                    "component": pf["component"],
                    "error": pf["error"][:100],
                    "status": pf["status"],
                    "fix_id": pf.get("fix_id"),
                })

        # Check brain for related learnings
        if self.brain:
            related = self.brain.recall(
                f"failure {failure['component']} {failure['error']}",
                collections=["clarvis-learnings"],
                n=3
            )
            for r in related:
                if "fix" in r["document"].lower() or "solution" in r["document"].lower():
                    analysis["pattern"] = r["document"][:200]

        # Generate root cause hypothesis based on error patterns
        analysis["root_cause"] = self._hypothesize_root_cause(failure)
        analysis["fix_strategy"] = self._generate_fix_strategy(failure, analysis)

        return analysis

    # === PHASE 3: EVOLVE (GENERATE + APPLY FIX) ===

    def evolve(self, failure_id: str, auto_apply: bool = True) -> dict:
        """
        Full evolution cycle: analyze → generate fix → apply → verify.

        Args:
            failure_id: The failure to fix
            auto_apply: Whether to auto-apply the fix (default True)

        Returns:
            Evolution result dict
        """
        failure = self._load_failure(failure_id)
        if not failure:
            return {"error": f"Failure {failure_id} not found"}

        # Don't retry too many times
        if failure["retries"] >= failure["max_retries"]:
            failure["status"] = "failed"
            self._save_failure(failure)
            return {"error": "Max retries exceeded", "failure_id": failure_id}

        # Step 1: Analyze
        analysis = self.analyze_failure(failure_id)

        # Step 2: Generate fix
        fix = self._generate_fix(failure, analysis)

        # Step 3: Apply fix
        if auto_apply and fix.get("action"):
            result = self._apply_fix(failure, fix)
            fix["applied"] = True
            fix["apply_result"] = result

            # Step 4: Verify
            if result.get("success"):
                failure["status"] = "verified"
                fix["verified"] = True

                # Store success in brain
                if self.brain:
                    self.brain.store(
                        f"FIX WORKED for {failure['component']}: {fix['description']}. "
                        f"Root cause: {analysis.get('root_cause', 'unknown')}",
                        collection="clarvis-learnings",
                        importance=0.9,
                        tags=["fix", "success", failure["component"]],
                        source="evolution_loop",
                    )
            else:
                failure["retries"] += 1
                failure["status"] = "fix_failed"
                fix["verified"] = False
        else:
            fix["applied"] = False

        # Save everything
        fix_file = FIXES_DIR / f"{fix['id']}.json"
        fix_file.write_text(json.dumps(fix, indent=2))
        failure["fix_id"] = fix["id"]
        self._save_failure(failure)

        return {
            "failure_id": failure_id,
            "fix_id": fix["id"],
            "status": failure["status"],
            "fix_description": fix["description"],
            "analysis": analysis,
        }

    # === PHASE 4: STATUS & HISTORY ===

    def status(self) -> dict:
        """Get current evolution loop status."""
        failures = self._get_all_failures()
        fixes = self._get_all_fixes()

        by_status = {}
        for f in failures:
            s = f["status"]
            by_status[s] = by_status.get(s, 0) + 1

        # Compute evolution velocity (fixes per day over last 7 days)
        recent_fixes = [
            fx for fx in fixes
            if fx.get("timestamp", "") >= (
                datetime.now(timezone.utc).isoformat()[:10]
            )
        ]

        return {
            "total_failures": len(failures),
            "total_fixes": len(fixes),
            "by_status": by_status,
            "recent_fixes_today": len(recent_fixes),
            "unresolved": [
                f["id"] for f in failures
                if f["status"] not in ("verified", "failed")
            ],
        }

    def history(self, n: int = 10) -> list:
        """Get recent failure/fix history."""
        failures = self._get_all_failures()
        failures.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return [
            {
                "id": f["id"],
                "component": f["component"],
                "error": f["error"][:80],
                "status": f["status"],
                "timestamp": f["timestamp"][:19],
            }
            for f in failures[:n]
        ]

    # === INTERNAL HELPERS ===

    def _load_failure(self, failure_id: str) -> dict | None:
        path = FAILURES_DIR / f"{failure_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def _save_failure(self, failure: dict):
        path = FAILURES_DIR / f"{failure['id']}.json"
        path.write_text(json.dumps(failure, indent=2))

    def _get_all_failures(self) -> list:
        failures = []
        for f in FAILURES_DIR.glob("fail_*.json"):
            try:
                failures.append(json.loads(f.read_text()))
            except json.JSONDecodeError:
                pass
        return failures

    def _get_all_fixes(self) -> list:
        fixes = []
        for f in FIXES_DIR.glob("fix_*.json"):
            try:
                fixes.append(json.loads(f.read_text()))
            except json.JSONDecodeError:
                pass
        return fixes

    def _error_similarity(self, err1: str, err2: str) -> float:
        """Simple word-overlap similarity between two error strings."""
        words1 = set(err1.lower().split())
        words2 = set(err2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def _hypothesize_root_cause(self, failure: dict) -> str:
        """Generate a root cause hypothesis based on error patterns."""
        error = failure["error"].lower()
        component = failure["component"]
        exit_code = failure.get("exit_code", 1)

        # Common patterns
        if exit_code == 124 or "timeout" in error:
            return f"Timeout: {component} exceeded time limit. Likely slow operation or infinite loop."
        if "no such file" in error or "not found" in error or "FileNotFoundError" in error:
            return f"Missing dependency: {component} references a file/module that doesn't exist."
        if "permission" in error or exit_code == 126:
            return f"Permission issue: {component} lacks required permissions."
        if "import" in error or "ModuleNotFoundError" in error:
            return f"Import error: {component} missing a Python dependency."
        if "memory" in error or "MemoryError" in error or exit_code == 137:
            return f"OOM: {component} ran out of memory (exit code 137 = killed)."
        if "connection" in error or "refused" in error:
            return f"Network/connection issue: {component} can't reach a required service."
        if "syntax" in error or "SyntaxError" in error:
            return f"Syntax error in {component} code."

        return f"Unknown failure in {component} (exit code {exit_code}): {failure['error'][:100]}"

    def _generate_fix_strategy(self, failure: dict, analysis: dict) -> str:
        """Generate a fix strategy based on analysis."""
        root_cause = analysis.get("root_cause", "")
        similar = analysis.get("similar_failures", [])

        # Check if a similar failure was already fixed
        for sf in similar:
            if sf.get("fix_id") and sf["status"] == "verified":
                return f"Reuse fix from {sf['fix_id']} (similar failure was already resolved)."

        if "timeout" in root_cause.lower():
            return "Increase timeout or optimize the slow operation. Check for infinite loops."
        if "missing" in root_cause.lower() or "import" in root_cause.lower():
            return "Install missing dependency or fix import path."
        if "permission" in root_cause.lower():
            return "Fix file permissions (chmod) or run with correct user."
        if "oom" in root_cause.lower():
            return "Reduce memory usage or add swap. Consider chunked processing."
        if "syntax" in root_cause.lower():
            return "Fix the syntax error in the source file."

        return "Spawn Claude Code to diagnose and fix the issue."

    def _generate_fix(self, failure: dict, analysis: dict) -> dict:
        """Generate a concrete fix object."""
        now = datetime.now(timezone.utc)
        fix_id = f"fix_{now.strftime('%Y%m%d_%H%M%S')}_{failure['component']}"

        fix = {
            "id": fix_id,
            "failure_id": failure["id"],
            "timestamp": now.isoformat(),
            "description": analysis.get("fix_strategy", "Manual investigation needed"),
            "root_cause": analysis.get("root_cause", "Unknown"),
            "action": None,  # Will be filled with concrete action
            "applied": False,
            "verified": False,
        }

        # Generate concrete action based on strategy
        strategy = analysis.get("fix_strategy", "")

        if "reuse fix" in strategy.lower():
            # Find the referenced fix and copy its action
            for sf in analysis.get("similar_failures", []):
                if sf.get("fix_id"):
                    old_fix_path = FIXES_DIR / f"{sf['fix_id']}.json"
                    if old_fix_path.exists():
                        old_fix = json.loads(old_fix_path.read_text())
                        fix["action"] = old_fix.get("action")
                        fix["description"] = f"Reapply: {old_fix.get('description', '')}"

        if not fix["action"]:
            # Generate a new action — queue for evolution
            fix["action"] = {
                "type": "evolution_task",
                "task": f"Fix failure in {failure['component']}: {failure['error'][:200]}",
                "context": failure.get("context", ""),
                "stderr_tail": failure.get("stderr", "")[-500:],
            }

        return fix

    def _apply_fix(self, failure: dict, fix: dict) -> dict:
        """
        Apply a fix. For 'evolution_task' type, adds to evolution queue.
        For 'script' type, runs the fix script directly.
        """
        action = fix.get("action", {})
        action_type = action.get("type", "")

        if action_type == "evolution_task":
            # Add to evolution queue for next heartbeat
            task_desc = action.get("task", "Unknown fix")
            self._add_to_queue(task_desc)
            return {
                "success": True,
                "method": "queued_evolution_task",
                "detail": f"Added to QUEUE.md: {task_desc[:80]}",
            }

        if action_type == "script":
            # Run a fix script directly
            cmd = action.get("command", "")
            if not cmd:
                return {"success": False, "method": "script", "detail": "No command"}
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=120,
                    cwd="/home/agent/.openclaw/workspace"
                )
                return {
                    "success": result.returncode == 0,
                    "method": "script",
                    "detail": result.stdout[-500:] if result.stdout else result.stderr[-500:],
                    "exit_code": result.returncode,
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "method": "script", "detail": "Fix script timed out"}

        return {"success": False, "method": "unknown", "detail": f"Unknown action type: {action_type}"}

    def _add_to_queue(self, task: str):
        """Add a fix task to the evolution queue under P0 via shared queue_writer."""
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from queue_writer import add_task
            add_task(task, priority="P0", source="evolution-loop")
        except ImportError:
            # Fallback: direct write
            queue_path = Path("/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md")
            if not queue_path.exists():
                return
            content = queue_path.read_text()
            marker = "## P0 — Do Next Heartbeat"
            if marker in content:
                parts = content.split(marker, 1)
                new_task = f"\n- [ ] [AUTO-FIX] {task}"
                content = parts[0] + marker + new_task + parts[1]
                queue_path.write_text(content)


# === Module-level convenience function for heartbeat integration ===

def run_with_evolution(command: str, component: str, context: str = "",
                       timeout: int = 600) -> dict:
    """
    Run a command with evolution loop wrapping.
    If it fails, capture the failure and trigger evolution.

    Args:
        command: Shell command to run
        component: Name of the component being run
        context: Description of what's being attempted
        timeout: Timeout in seconds

    Returns:
        dict with success, output, and evolution info
    """
    loop = EvolutionLoop()

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd="/home/agent/.openclaw/workspace"
        )

        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout[-2000:],
                "component": component,
            }

        # FAILURE — trigger evolution
        failure_id = loop.capture_failure(
            component=component,
            error=f"Exit code {result.returncode}",
            context=context,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        # Run evolution cycle
        evolution_result = loop.evolve(failure_id, auto_apply=True)

        return {
            "success": False,
            "output": result.stderr[-1000:],
            "component": component,
            "failure_id": failure_id,
            "evolution": evolution_result,
        }

    except subprocess.TimeoutExpired:
        failure_id = loop.capture_failure(
            component=component,
            error=f"Timeout after {timeout}s",
            context=context,
            exit_code=124,
        )

        evolution_result = loop.evolve(failure_id, auto_apply=True)

        return {
            "success": False,
            "output": f"TIMEOUT after {timeout}s",
            "component": component,
            "failure_id": failure_id,
            "evolution": evolution_result,
        }


# CLI
if __name__ == "__main__":
    loop = EvolutionLoop()

    if len(sys.argv) < 2:
        print("Clarvis Evolution Loop — Failure → Evolve → Redeploy")
        print()
        print("Usage:")
        print("  capture <component> <error> [context]  — log a failure")
        print("  analyze <failure_id>                   — analyze a failure")
        print("  evolve <failure_id>                    — full evolution cycle")
        print("  status                                 — show loop status")
        print("  history [n]                            — recent failures")
        print("  test                                   — run self-test")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "capture":
        component = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        error = sys.argv[3] if len(sys.argv) > 3 else "unspecified error"
        context = sys.argv[4] if len(sys.argv) > 4 else ""
        fid = loop.capture_failure(component, error, context)
        print(f"Captured: {fid}")

    elif cmd == "analyze":
        fid = sys.argv[2]
        analysis = loop.analyze_failure(fid)
        print(json.dumps(analysis, indent=2))

    elif cmd == "evolve":
        fid = sys.argv[2]
        result = loop.evolve(fid)
        print(json.dumps(result, indent=2))

    elif cmd == "status":
        s = loop.status()
        print(f"Total failures: {s['total_failures']}")
        print(f"Total fixes: {s['total_fixes']}")
        print(f"By status: {json.dumps(s['by_status'])}")
        if s["unresolved"]:
            print(f"Unresolved: {', '.join(s['unresolved'])}")
        else:
            print("All failures resolved.")

    elif cmd == "history":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        for entry in loop.history(n):
            print(f"  {entry['timestamp']} [{entry['status']}] {entry['component']}: {entry['error']}")

    elif cmd == "test":
        print("=== Evolution Loop Self-Test ===")

        # Test 1: Capture a failure
        fid = loop.capture_failure(
            component="test_component",
            error="ImportError: No module named 'nonexistent'",
            context="Testing evolution loop",
            exit_code=1,
            stderr="Traceback: ImportError: No module named 'nonexistent'",
        )
        print(f"1. Captured failure: {fid}")

        # Test 2: Analyze it
        analysis = loop.analyze_failure(fid)
        print(f"2. Root cause: {analysis['root_cause']}")
        print(f"   Fix strategy: {analysis['fix_strategy']}")

        # Test 3: Evolve (without auto-apply to avoid modifying queue)
        result = loop.evolve(fid, auto_apply=False)
        print(f"3. Evolution result: status={result['status']}, fix={result['fix_id']}")

        # Test 4: Status
        s = loop.status()
        print(f"4. Status: {s['total_failures']} failures, {s['total_fixes']} fixes")

        # Test 5: run_with_evolution
        r = run_with_evolution("echo 'hello world'", "test_echo", "testing echo")
        print(f"5. run_with_evolution (success): {r['success']}")

        r = run_with_evolution("exit 1", "test_fail", "testing failure capture")
        print(f"6. run_with_evolution (failure): success={r['success']}, evolved={r.get('failure_id', 'none')}")

        print("\n=== All tests passed ===")

    else:
        print(f"Unknown command: {cmd}")
