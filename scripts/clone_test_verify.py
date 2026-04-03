#!/usr/bin/env python3
"""Clone → Test → Verify pipeline for safe code changes.

ROADMAP Phase 3.2: Self-Improvement Loop — gate code changes through
worktree isolation + automated test verification before promotion.

Flow:
  1. clone:  Create git worktree from HEAD (or apply a callback's changes)
  2. test:   Run pytest in the worktree
  3. verify: Parse results, decide promote/reject
  4. promote or rollback the worktree

Usage (CLI):
  clone_test_verify.py create [--branch NAME]     # Create isolated worktree
  clone_test_verify.py test <worktree_path>        # Run tests in worktree
  clone_test_verify.py verify <worktree_path>      # Full test + parse + verdict
  clone_test_verify.py promote <worktree_path>     # Merge worktree to main
  clone_test_verify.py cleanup [--max-age 24]      # Remove stale worktrees
  clone_test_verify.py status                      # List active worktrees

Usage (Python API):
  from clone_test_verify import CloneTestVerify
  ctv = CloneTestVerify()
  wt = ctv.create_worktree()
  result = ctv.run_tests(wt["path"])
  if result["safe_to_promote"]:
      ctv.promote_worktree(wt["path"])
  else:
      ctv.rollback_worktree(wt["path"])
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path("/home/agent/.openclaw/workspace")
WORKTREE_DIR = WORKSPACE / ".claude" / "worktrees"
LOG_DIR = WORKSPACE / "memory" / "cron"
DATA_DIR = WORKSPACE / "data"
VERIFY_LOG = DATA_DIR / "clone_test_verify.jsonl"

# Test commands to run in priority order
TEST_COMMANDS = [
    # Fast smoke tests first
    {
        "name": "import_check",
        "cmd": ["python3", "-c", "from clarvis.brain import brain; print('brain OK')"],
        "timeout": 30,
        "critical": True,
    },
    # Full pytest suite
    {
        "name": "pytest",
        "cmd": ["python3", "-m", "pytest", "--tb=short", "-q", "--no-header", "-x"],
        "timeout": 120,
        "critical": True,
    },
    # Ruff lint (non-critical — advisory only)
    {
        "name": "ruff",
        "cmd": ["python3", "-m", "ruff", "check", "--select", "E9,F63,F7,F82", "."],
        "timeout": 30,
        "critical": False,
    },
]


class CloneTestVerify:
    """Orchestrates the clone → test → verify pipeline."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or WORKSPACE
        self.worktree_dir = self.workspace / ".claude" / "worktrees"
        self.worktree_dir.mkdir(parents=True, exist_ok=True)

    def create_worktree(self, branch_name: str | None = None) -> dict:
        """Create an isolated git worktree from HEAD.

        Returns dict with: path, branch, created_at, status
        """
        agent_id = f"ctv-{datetime.now(timezone.utc).strftime('%m%d-%H%M%S')}-{os.getpid()}"
        branch = branch_name or f"agent/{agent_id}"
        wt_path = self.worktree_dir / agent_id

        result = subprocess.run(
            ["git", "-C", str(self.workspace), "worktree", "add",
             "-b", branch, str(wt_path), "HEAD"],
            capture_output=True, text=True, timeout=30,
        )

        if result.returncode != 0:
            return {
                "status": "error",
                "error": result.stderr.strip(),
                "path": None,
                "branch": branch,
            }

        return {
            "status": "created",
            "path": str(wt_path),
            "branch": branch,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def run_tests(self, worktree_path: str) -> dict:
        """Run test suite in the given worktree (or main workspace).

        Returns structured result with pass/fail counts and verdict.
        """
        wt = Path(worktree_path)
        if not wt.exists():
            return {"status": "error", "error": f"Path does not exist: {worktree_path}"}

        results = []
        all_critical_pass = True
        total_passed = 0
        total_failed = 0
        total_errors = 0

        for test_spec in TEST_COMMANDS:
            name = test_spec["name"]
            start = time.monotonic()
            try:
                proc = subprocess.run(
                    test_spec["cmd"],
                    capture_output=True, text=True,
                    timeout=test_spec["timeout"],
                    cwd=str(wt),
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                elapsed = time.monotonic() - start
                passed, failed, errors = self._parse_test_output(name, proc)

                entry = {
                    "name": name,
                    "exit_code": proc.returncode,
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                    "elapsed_s": round(elapsed, 2),
                    "output_tail": proc.stdout[-500:] if proc.stdout else "",
                    "stderr_tail": proc.stderr[-300:] if proc.stderr else "",
                }
                results.append(entry)

                total_passed += passed
                total_failed += failed
                total_errors += errors

                if proc.returncode != 0 and test_spec["critical"]:
                    all_critical_pass = False

            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - start
                results.append({
                    "name": name,
                    "exit_code": -1,
                    "passed": 0,
                    "failed": 0,
                    "errors": 1,
                    "elapsed_s": round(elapsed, 2),
                    "output_tail": f"TIMEOUT after {test_spec['timeout']}s",
                    "stderr_tail": "",
                })
                total_errors += 1
                if test_spec["critical"]:
                    all_critical_pass = False

            except Exception as e:
                results.append({
                    "name": name,
                    "exit_code": -2,
                    "passed": 0,
                    "failed": 0,
                    "errors": 1,
                    "elapsed_s": 0,
                    "output_tail": str(e),
                    "stderr_tail": "",
                })
                total_errors += 1
                if test_spec["critical"]:
                    all_critical_pass = False

        # Compute changed files (worktree vs HEAD)
        changed_files = self._get_changed_files(wt)

        verdict = {
            "status": "pass" if all_critical_pass else "fail",
            "safe_to_promote": all_critical_pass,
            "tests_passed": total_passed,
            "tests_failed": total_failed,
            "tests_errors": total_errors,
            "changed_files": changed_files,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "worktree_path": str(wt),
        }

        # Log verdict
        self._log_verdict(verdict)

        return verdict

    def verify(self, worktree_path: str, baseline_comparison: bool = True) -> dict:
        """Full verify: run tests + return promotion decision.

        If baseline_comparison is True and worktree_path differs from the main
        workspace, also runs tests in main workspace and only rejects if the
        worktree introduced NEW failures (failures not in the baseline).
        """
        result = self.run_tests(worktree_path)

        if result.get("status") == "error":
            return result

        # Baseline comparison: only reject for NEW failures
        wt_is_main = Path(worktree_path).resolve() == self.workspace.resolve()
        if baseline_comparison and not wt_is_main and not result.get("safe_to_promote"):
            baseline = self.run_tests(str(self.workspace))
            baseline_failures = {
                r["name"] for r in baseline.get("results", [])
                if r["exit_code"] != 0
            }
            wt_failures = {
                r["name"] for r in result.get("results", [])
                if r["exit_code"] != 0
            }
            new_failures = wt_failures - baseline_failures
            result["baseline_failures"] = sorted(baseline_failures)
            result["new_failures"] = sorted(new_failures)

            if not new_failures:
                # All failures are pre-existing — safe to promote
                result["safe_to_promote"] = True
                result["status"] = "pass"

        # Add recommendation
        if result.get("safe_to_promote"):
            if result.get("new_failures") is not None:
                result["recommendation"] = "PROMOTE — no new failures (pre-existing failures present in baseline)"
            else:
                result["recommendation"] = "PROMOTE — all critical tests pass"
        else:
            new = result.get("new_failures")
            if new:
                result["recommendation"] = f"REJECT — new failures introduced: {', '.join(new)}"
            else:
                failing = [r["name"] for r in result.get("results", [])
                           if r["exit_code"] != 0 and r["name"] in
                           {t["name"] for t in TEST_COMMANDS if t["critical"]}]
                result["recommendation"] = f"REJECT — critical failures: {', '.join(failing)}"

        return result

    def promote_worktree(self, worktree_path: str) -> dict:
        """Merge worktree changes back to main branch."""
        wt = Path(worktree_path)
        if not wt.exists():
            return {"status": "error", "error": "Worktree path does not exist"}

        # Get the branch name
        branch = self._get_worktree_branch(wt)
        if not branch:
            return {"status": "error", "error": "Cannot determine worktree branch"}

        # Check for uncommitted changes, commit them first
        status = subprocess.run(
            ["git", "-C", str(wt), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        if status.stdout.strip():
            subprocess.run(
                ["git", "-C", str(wt), "add", "-A"],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "-C", str(wt), "commit", "-m",
                 f"Auto-commit before promote ({branch})"],
                capture_output=True, timeout=10,
            )

        # Merge the worktree branch into main
        merge = subprocess.run(
            ["git", "-C", str(self.workspace), "merge", "--no-ff",
             branch, "-m", f"Promote verified changes from {branch}"],
            capture_output=True, text=True, timeout=30,
        )

        if merge.returncode != 0:
            return {
                "status": "merge_conflict",
                "error": merge.stderr.strip(),
                "branch": branch,
            }

        # Clean up worktree
        self._remove_worktree(wt, branch)

        return {
            "status": "promoted",
            "branch": branch,
            "merged_to": "main",
        }

    def rollback_worktree(self, worktree_path: str) -> dict:
        """Remove worktree without merging (reject changes)."""
        wt = Path(worktree_path)
        branch = self._get_worktree_branch(wt)
        self._remove_worktree(wt, branch)
        return {
            "status": "rolled_back",
            "branch": branch or "unknown",
            "path": str(wt),
        }

    def cleanup_stale(self, max_age_hours: int = 24) -> dict:
        """Remove worktrees older than max_age_hours."""
        if not self.worktree_dir.exists():
            return {"removed": 0, "kept": 0}

        removed = []
        kept = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        for entry in self.worktree_dir.iterdir():
            if not entry.is_dir():
                continue
            # Check age via directory mtime
            mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                branch = self._get_worktree_branch(entry)
                self._remove_worktree(entry, branch)
                removed.append(str(entry.name))
            else:
                kept.append(str(entry.name))

        return {"removed": len(removed), "kept": len(kept), "removed_names": removed}

    def list_worktrees(self) -> list[dict]:
        """List all active worktrees with metadata."""
        result = subprocess.run(
            ["git", "-C", str(self.workspace), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        worktrees = []
        current = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line.split(" ", 1)[1]}
            elif line.startswith("branch "):
                current["branch"] = line.split(" ", 1)[1]
            elif line.startswith("HEAD "):
                current["head"] = line.split(" ", 1)[1]
            elif line == "":
                if current:
                    worktrees.append(current)
                current = {}
        if current:
            worktrees.append(current)

        # Filter to only our managed worktrees
        return [w for w in worktrees if "/.claude/worktrees/" in w.get("path", "")]

    # --- Private helpers ---

    def _parse_test_output(self, name: str, proc: subprocess.CompletedProcess) -> tuple[int, int, int]:
        """Parse test counts from command output."""
        if name == "import_check":
            return (1, 0, 0) if proc.returncode == 0 else (0, 1, 0)

        if name == "ruff":
            if proc.returncode == 0:
                return (1, 0, 0)
            # Count ruff errors from output lines
            errors = len([l for l in proc.stdout.splitlines() if l.strip() and ":" in l])
            return (0, errors or 1, 0)

        if name == "pytest":
            # Parse pytest summary line: "X passed, Y failed, Z errors"
            text = proc.stdout + proc.stderr
            passed = failed = errors = 0

            m = re.search(r"(\d+) passed", text)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+) failed", text)
            if m:
                failed = int(m.group(1))
            m = re.search(r"(\d+) error", text)
            if m:
                errors = int(m.group(1))

            # If no counts found but exit code is non-zero, count as 1 error
            if proc.returncode != 0 and passed == 0 and failed == 0 and errors == 0:
                errors = 1

            return (passed, failed, errors)

        return (1, 0, 0) if proc.returncode == 0 else (0, 1, 0)

    def _get_changed_files(self, wt: Path) -> list[str]:
        """Get list of files changed in worktree vs HEAD."""
        try:
            # Diff against the base commit (parent of worktree)
            result = subprocess.run(
                ["git", "-C", str(wt), "diff", "--name-only", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            staged = subprocess.run(
                ["git", "-C", str(wt), "diff", "--name-only", "--cached"],
                capture_output=True, text=True, timeout=10,
            )
            untracked = subprocess.run(
                ["git", "-C", str(wt), "ls-files", "--others", "--exclude-standard"],
                capture_output=True, text=True, timeout=10,
            )
            files = set()
            for r in [result, staged, untracked]:
                files.update(f.strip() for f in r.stdout.splitlines() if f.strip())
            return sorted(files)
        except Exception:
            return []

    def _get_worktree_branch(self, wt: Path) -> str | None:
        """Get the branch name for a worktree."""
        try:
            result = subprocess.run(
                ["git", "-C", str(wt), "branch", "--show-current"],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or None
        except Exception:
            return None

    def _remove_worktree(self, wt: Path, branch: str | None):
        """Safely remove a worktree and its branch."""
        try:
            subprocess.run(
                ["git", "-C", str(self.workspace), "worktree", "remove", "--force", str(wt)],
                capture_output=True, timeout=15,
            )
        except Exception:
            pass
        if branch and branch not in ("main", "master"):
            try:
                subprocess.run(
                    ["git", "-C", str(self.workspace), "branch", "-D", branch],
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass

    def _log_verdict(self, verdict: dict):
        """Append verdict to JSONL log."""
        try:
            VERIFY_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(VERIFY_LOG, "a") as f:
                f.write(json.dumps(verdict, default=str) + "\n")
        except Exception:
            pass


def main():
    """CLI entrypoint."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    ctv = CloneTestVerify()

    if cmd == "create":
        branch = None
        for arg in sys.argv[2:]:
            if arg.startswith("--branch"):
                branch = arg.split("=", 1)[1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1]
        result = ctv.create_worktree(branch)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["status"] == "created" else 1)

    elif cmd == "test":
        if len(sys.argv) < 3:
            # Default: test in main workspace
            path = str(WORKSPACE)
        else:
            path = sys.argv[2]
        result = ctv.run_tests(path)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("safe_to_promote") else 1)

    elif cmd == "verify":
        if len(sys.argv) < 3:
            path = str(WORKSPACE)
        else:
            path = sys.argv[2]
        result = ctv.verify(path)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("safe_to_promote") else 1)

    elif cmd == "promote":
        if len(sys.argv) < 3:
            print("Usage: clone_test_verify.py promote <worktree_path>")
            sys.exit(1)
        result = ctv.promote_worktree(sys.argv[2])
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["status"] == "promoted" else 1)

    elif cmd == "cleanup":
        max_age = 24
        for arg in sys.argv[2:]:
            if arg.startswith("--max-age"):
                max_age = int(arg.split("=", 1)[1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1])
        result = ctv.cleanup_stale(max_age)
        print(json.dumps(result, indent=2))

    elif cmd == "status":
        wts = ctv.list_worktrees()
        if not wts:
            print("No active worktrees.")
        else:
            for w in wts:
                print(f"  {w.get('branch', '?'):40s} {w.get('path', '?')}")
        print(f"\nTotal: {len(wts)} worktree(s)")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: create, test, verify, promote, cleanup, status")
        sys.exit(1)


if __name__ == "__main__":
    main()
