#!/usr/bin/env python3
"""
Perfect State Acceptance Check — automated verification of Clarvis operational health.

Checks all automatable criteria from docs/internal/perfect_state_acceptance_criteria.md.
Returns exit 0 if all CRITICAL checks pass, exit 1 otherwise.

Usage:
    python3 scripts/infra/acceptance_check.py          # Full check
    python3 scripts/infra/acceptance_check.py --quick   # Critical checks only
    python3 scripts/infra/acceptance_check.py --json    # JSON output
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
os.chdir(WS)


def _run(cmd, timeout=30):
    """Run shell command, return (ok, output)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip()
    except (subprocess.TimeoutExpired, Exception) as e:
        return False, str(e)


def _age_hours(path):
    """Return age of file in hours, or None if missing."""
    try:
        mtime = os.path.getmtime(path)
        return (time.time() - mtime) / 3600
    except FileNotFoundError:
        return None


class AcceptanceCheck:
    def __init__(self):
        self.results = []

    def check(self, name, category, critical, fn):
        """Run a check and record result."""
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"Exception: {e}"
        self.results.append({
            "name": name,
            "category": category,
            "critical": critical,
            "passed": ok,
            "detail": detail,
        })
        return ok

    def run_all(self, quick=False):
        """Run all checks."""
        self._cron_health()
        self._queue_flow()
        self._preflight_integrity()
        self._digest_freshness()
        if not quick:
            self._memory_integrity()
            self._spine_availability()
            self._runtime_cleanliness()
            self._performance_baselines()

    def _cron_health(self):
        self.check("crontab_valid", "cron", True,
                    lambda: _run("crontab -l 2>/dev/null | grep -c 'clarvis\\|CLARVIS'"))
        self.check("lockfiles_clean", "cron", True,
                    lambda: self._check_lockfiles())
        self.check("cron_env_loads", "cron", True,
                    lambda: _run(f"bash -c 'source {WS}/scripts/cron/cron_env.sh && echo $CLARVIS_WORKSPACE'"))

    def _check_lockfiles(self):
        import glob
        locks = glob.glob("/tmp/clarvis_*.lock")
        stale = []
        for lf in locks:
            try:
                pid = open(lf).read().strip()
                if pid.isdigit():
                    # Check if PID is alive
                    try:
                        os.kill(int(pid), 0)
                    except ProcessLookupError:
                        stale.append(lf)
            except (IOError, ValueError):
                stale.append(lf)
        if stale:
            return False, f"Stale locks: {stale}"
        return True, f"{len(locks)} active locks, 0 stale"

    def _queue_flow(self):
        self.check("queue_nonempty", "queue", True,
                    lambda: self._check_queue_pending())
        self.check("sidecar_parseable", "queue", True,
                    lambda: self._check_sidecar())

    def _check_queue_pending(self):
        qf = os.path.join(WS, "memory/evolution/QUEUE.md")
        try:
            content = open(qf).read()
            pending = content.count("- [ ]")
            if pending >= 3:
                return True, f"{pending} pending tasks"
            return False, f"Only {pending} pending tasks (minimum 3)"
        except FileNotFoundError:
            return False, "QUEUE.md missing"

    def _check_sidecar(self):
        sf = os.path.join(WS, "data/queue_state.json")
        try:
            with open(sf) as f:
                data = json.load(f)
            total = len(data)
            stuck = sum(1 for v in data.values()
                        if v.get("state") == "running" and v.get("attempts", 0) > 5)
            if stuck > 0:
                return False, f"Sidecar: {total} entries, {stuck} stuck"
            return True, f"Sidecar: {total} entries, 0 stuck"
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return False, str(e)

    def _preflight_integrity(self):
        self.check("gate_functional", "preflight", True,
                    lambda: _run(f'python3 -c "from clarvis.heartbeat.gate import check_gate; d,r,c = check_gate(); print(d)"'))
        self.check("gate_wired_in_autonomous", "preflight", False,
                    lambda: _run(f"grep -q 'run_gate\\|check_gate\\|GATE_DECISION' {WS}/scripts/cron/cron_autonomous.sh"))

    def _digest_freshness(self):
        self.check("digest_fresh", "digest", False,
                    lambda: self._check_file_age("memory/cron/digest.md", max_hours=26))
        self.check("daily_memory_exists", "digest", False,
                    lambda: self._check_daily_memory())

    def _check_file_age(self, relpath, max_hours):
        fpath = os.path.join(WS, relpath)
        age = _age_hours(fpath)
        if age is None:
            return False, f"{relpath} missing"
        if age > max_hours:
            return False, f"{relpath} is {age:.1f}h old (max {max_hours}h)"
        return True, f"{relpath} is {age:.1f}h old"

    def _check_daily_memory(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fpath = os.path.join(WS, f"memory/{today}.md")
        if os.path.exists(fpath):
            return True, f"memory/{today}.md exists"
        return False, f"memory/{today}.md missing"

    def _memory_integrity(self):
        self.check("brain_stats", "memory", True,
                    lambda: _run('python3 -c "from clarvis.brain import brain; s=brain.stats(); assert s[\'total_memories\'] >= 2500; print(s[\'total_memories\'])"', timeout=60))
        self.check("brain_search", "memory", True,
                    lambda: _run('python3 -m clarvis brain search "test" --n 3 2>/dev/null | grep -c "."', timeout=60))

    def _spine_availability(self):
        imports = [
            "from clarvis.brain import brain, search, remember, capture",
            "from clarvis.cognition.reasoning import ReasoningChain",
            "from clarvis.queue.engine import QueueEngine",
            "from clarvis.queue.writer import add_task, prune_sidecar",
            "from clarvis.heartbeat.gate import check_gate, run_gate",
        ]
        for imp in imports:
            module = imp.split("import")[0].strip().split("from ")[-1].strip()
            self.check(f"import_{module}", "spine", True,
                       lambda i=imp: _run(f'python3 -c "{i}"'))

    def _runtime_cleanliness(self):
        self.check("no_old_acp", "runtime", False,
                    lambda: self._check_old_acp())
        self.check("backup_recent", "runtime", False,
                    lambda: self._check_backup())

    def _check_old_acp(self):
        ok, output = _run("ps -eo pid,etimes,cmd | awk '/claude-agent-acp/ && $2 > 172800 {count++} END {print count+0}'")
        if ok:
            count = int(output.strip() or "0")
            if count > 0:
                return False, f"{count} ACP processes older than 48h"
            return True, "No old ACP processes"
        return True, "Could not check (ps failed)"

    def _check_backup(self):
        backup_dir = os.path.expanduser("~/.openclaw/backups")
        latest = os.path.join(backup_dir, "latest")
        if os.path.islink(latest) or os.path.isdir(latest):
            age = _age_hours(latest)
            if age and age < 26:
                return True, f"Backup {age:.1f}h old"
            return False, f"Backup {age:.1f}h old (max 26h)" if age else "Backup age unknown"
        return False, "No latest backup symlink"

    def _performance_baselines(self):
        self.check("pi_score", "performance", False,
                    lambda: self._check_pi())

    def _check_pi(self):
        metrics_file = os.path.join(WS, "data/performance_metrics.json")
        try:
            with open(metrics_file) as f:
                data = json.load(f)
            pi = data.get("pi_score") or data.get("metrics", {}).get("pi_score", 0)
            if pi >= 0.65:
                return True, f"PI={pi:.3f}"
            return False, f"PI={pi:.3f} (target ≥0.65)"
        except (FileNotFoundError, json.JSONDecodeError):
            return False, "performance_metrics.json missing or invalid"

    def report(self, json_mode=False):
        """Print report and return exit code."""
        passed = sum(1 for r in self.results if r["passed"])
        failed = sum(1 for r in self.results if not r["passed"])
        critical_fail = sum(1 for r in self.results if not r["passed"] and r["critical"])

        if json_mode:
            print(json.dumps({
                "passed": passed,
                "failed": failed,
                "critical_failures": critical_fail,
                "checks": self.results,
            }, indent=2))
        else:
            print(f"=== Clarvis Acceptance Check ===")
            print(f"Passed: {passed}/{passed + failed}")
            if critical_fail:
                print(f"CRITICAL FAILURES: {critical_fail}")
            print()
            for r in self.results:
                icon = "✓" if r["passed"] else ("✗ CRIT" if r["critical"] else "✗")
                print(f"  [{icon}] {r['category']}/{r['name']}: {r['detail']}")
            print()
            if critical_fail:
                print("RESULT: FAIL (critical checks failed)")
            elif failed:
                print(f"RESULT: WARN ({failed} non-critical failures)")
            else:
                print("RESULT: PASS (all checks passed)")

        return 1 if critical_fail else 0


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    json_mode = "--json" in sys.argv
    ac = AcceptanceCheck()
    ac.run_all(quick=quick)
    sys.exit(ac.report(json_mode=json_mode))
