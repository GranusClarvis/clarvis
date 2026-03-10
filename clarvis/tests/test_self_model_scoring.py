"""Tests for self_model autonomous_execution scoring — verifies FAILED-line filtering."""
import os
import tempfile
import unittest
from unittest.mock import patch


class TestAutonomousExecutionScoring(unittest.TestCase):
    """Verify that _assess_autonomous_execution correctly classifies log lines."""

    def _make_log(self, lines):
        """Create a temp log file with given lines and return its path."""
        tf = tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False)
        tf.write('\n'.join(lines) + '\n')
        tf.close()
        return tf.name

    def _run_assessor(self, log_path, today='2026-03-09', yesterday='2026-03-08'):
        """Run the log-parsing portion of the assessor and return counts."""
        with open(log_path) as f:
            lines = f.readlines()
        recent_lines = [l for l in lines if today in l or yesterday in l]
        outcome_lines = [l for l in recent_lines if "outcome: success" in l or "COMPLETED" in l]
        exec_success = [l for l in recent_lines if "EXECUTION:" in l and "exit=0" in l]
        log_completed = max(len(outcome_lines), len(exec_success))
        # This must match the FIXED pattern in self_model.py
        outcome_fail = [l for l in recent_lines if "outcome: timeout" in l or "outcome: failure" in l or ("FAILED" in l and "Verification FAILED" not in l)]
        exec_fail = [l for l in recent_lines if "EXECUTION:" in l and "exit=" in l and "exit=0" not in l]
        log_failed = max(len(outcome_fail), len(exec_fail))
        return log_completed, log_failed

    def test_verification_failed_not_counted_as_failure(self):
        """Verification FAILED (lock held) must NOT count as an execution failure."""
        lines = [
            "[2026-03-09T07:00:15] PREFLIGHT: Verification FAILED: lock held: clarvis_claude_global.lock (pid 123)",
            "[2026-03-09T07:09:06] EXECUTION: executor=claude exit=0 duration=510s timeout=1500s tier=complex",
            "[2026-03-09T07:09:06] POSTFLIGHT: Recording outcome: success (exit=0, duration=510s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 1)
            self.assertEqual(failed, 0, "Verification FAILED should not count as failure")
        finally:
            os.unlink(log_path)

    def test_real_failure_still_counted(self):
        """Actual execution failures (outcome: failure) must still count."""
        lines = [
            "[2026-03-09T07:09:06] EXECUTION: executor=claude exit=1 duration=30s timeout=1500s tier=complex",
            "[2026-03-09T07:09:06] POSTFLIGHT: Recording outcome: failure (exit=1, duration=30s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 0)
            self.assertEqual(failed, 1)
        finally:
            os.unlink(log_path)

    def test_timeout_counted_as_failure(self):
        """Timeout outcomes must count as failures."""
        lines = [
            "[2026-03-09T10:00:00] POSTFLIGHT: Recording outcome: timeout (exit=124, duration=1500s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 0)
            self.assertEqual(failed, 1)
        finally:
            os.unlink(log_path)

    def test_mixed_success_and_lock_lines(self):
        """Multiple lock-held messages + successes should yield 0 failures."""
        lines = [
            "[2026-03-08T07:00:15] PREFLIGHT: Verification FAILED: lock held: clarvis_claude_global.lock (pid 111)",
            "[2026-03-08T09:00:15] PREFLIGHT: Verification FAILED: lock held: clarvis_claude_global.lock (pid 222)",
            "[2026-03-08T11:00:13] PREFLIGHT: Verification FAILED: lock held: clarvis_claude_global.lock (pid 333)",
            "[2026-03-08T07:09:06] EXECUTION: executor=claude exit=0 duration=510s timeout=1500s tier=complex",
            "[2026-03-08T07:09:06] POSTFLIGHT: Recording outcome: success (exit=0, duration=510s)",
            "[2026-03-09T15:02:20] EXECUTION: executor=claude exit=0 duration=105s timeout=1200s tier=vision",
            "[2026-03-09T15:02:21] POSTFLIGHT: Recording outcome: success (exit=0, duration=105s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 2)
            self.assertEqual(failed, 0, "Lock-held lines must not inflate failure count")
        finally:
            os.unlink(log_path)


if __name__ == '__main__':
    unittest.main()
