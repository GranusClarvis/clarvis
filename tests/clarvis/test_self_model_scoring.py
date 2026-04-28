"""Tests for self_model autonomous_execution scoring — anchors on canonical
heartbeat postflight outcome lines and rejects loose 'FAILED' substring matches
that previously inflated the failure count (SELF-TEST FAILED, PERF GATE: FAIL,
task names containing FAILURE_HANDLING, etc.)."""
import os
import tempfile
import unittest


class TestAutonomousExecutionScoring(unittest.TestCase):
    """Verify that _assess_autonomous_execution correctly classifies log lines."""

    def _make_log(self, lines):
        tf = tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False)
        tf.write('\n'.join(lines) + '\n')
        tf.close()
        return tf.name

    def _run_assessor(self, log_path, today='2026-03-09', yesterday='2026-03-08'):
        """Mirror the log-parsing portion of _assess_autonomous_execution.

        Must stay in sync with clarvis/metrics/self_model.py:_assess_autonomous_execution.
        """
        with open(log_path) as f:
            lines = f.readlines()
        recent_lines = [l for l in lines if today in l or yesterday in l]
        outcome_lines = [l for l in recent_lines if "Recording outcome: success" in l]
        exec_success = [l for l in recent_lines if "EXECUTION:" in l and "exit=0" in l]
        log_completed = max(len(outcome_lines), len(exec_success))
        outcome_fail = [
            l for l in recent_lines
            if "Recording outcome: failure" in l
            or "Recording outcome: timeout" in l
            or "Recording outcome: crash" in l
        ]
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

    def test_self_test_failed_not_counted_as_failure(self):
        """POSTFLIGHT: SELF-TEST FAILED (pytest health check) must NOT count as task failure."""
        lines = [
            "[2026-03-09T06:08:10] POSTFLIGHT: SELF-TEST FAILED: pytest_exit=1, brain_ok=True",
            "[2026-03-09T06:05:55] EXECUTION: executor=claude exit=0 duration=345s timeout=1800s tier=reasoning",
            "[2026-03-09T06:05:55] POSTFLIGHT: Recording outcome: success (exit=0, duration=345s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 1)
            self.assertEqual(failed, 0, "SELF-TEST FAILED is a postflight health check, not a task failure")
        finally:
            os.unlink(log_path)

    def test_perf_gate_fail_not_counted_as_failure(self):
        """POSTFLIGHT: PERF GATE: FAIL must NOT count as task failure."""
        lines = [
            "[2026-03-09T06:08:20] POSTFLIGHT: PERF GATE: FAIL — trajectory_eval (8.59s)",
            "[2026-03-09T06:05:55] EXECUTION: executor=claude exit=0 duration=345s timeout=1800s tier=reasoning",
            "[2026-03-09T06:05:55] POSTFLIGHT: Recording outcome: success (exit=0, duration=345s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 1)
            self.assertEqual(failed, 0, "PERF GATE: FAIL is a perf check, not a task failure")
        finally:
            os.unlink(log_path)

    def test_task_name_with_failure_word_not_counted(self):
        """A task whose NAME contains FAILURE/FAILED must not inflate the failure count."""
        lines = [
            "[2026-03-09T07:00:13] EXECUTING (salience=0.5, section=P0): **[P0_PROJECT_AGENT_MIRROR_RESET_FAILURE_HANDLING]** Improve",
            "[2026-03-09T07:09:06] EXECUTION: executor=claude exit=0 duration=510s timeout=1500s tier=complex",
            "[2026-03-09T07:09:06] POSTFLIGHT: Recording outcome: success (exit=0, duration=510s)",
            "Recorded: ___P0_PROJECT_AGENT_MIRROR_RESET_FAILURE_HANDLING_____script -> CORRECT (was 78% confident)",
            "[2026-03-09T07:02:29] POSTFLIGHT: Task not found in QUEUE.md for completion: **[P0_PROJECT_AGENT_MIRROR_RESET_FAILURE_HANDLING]**",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 1)
            self.assertEqual(failed, 0, "Task name containing FAILURE must not count as failure")
        finally:
            os.unlink(log_path)

    def test_real_failure_still_counted(self):
        """Actual execution failures (Recording outcome: failure) must still count."""
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
        """Recording outcome: timeout must count as failure."""
        lines = [
            "[2026-03-09T10:00:00] EXECUTION: executor=claude exit=124 duration=1500s timeout=1500s tier=complex",
            "[2026-03-09T10:00:00] POSTFLIGHT: Recording outcome: timeout (exit=124, duration=1500s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 0)
            self.assertEqual(failed, 1)
        finally:
            os.unlink(log_path)

    def test_crash_counted_as_failure(self):
        """Recording outcome: crash (signal/SIGKILL) must count as failure."""
        lines = [
            "[2026-03-09T10:00:00] EXECUTION: executor=claude exit=137 duration=42s timeout=1500s tier=complex",
            "[2026-03-09T10:00:00] POSTFLIGHT: Recording outcome: crash (exit=137, duration=42s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 0)
            self.assertEqual(failed, 1, "crash outcome must count as failure")
        finally:
            os.unlink(log_path)

    def test_mixed_success_and_lock_lines(self):
        """Multiple lock-held + self-test failure messages + successes -> 0 failures."""
        lines = [
            "[2026-03-08T07:00:15] PREFLIGHT: Verification FAILED: lock held: clarvis_claude_global.lock (pid 111)",
            "[2026-03-08T09:00:15] PREFLIGHT: Verification FAILED: lock held: clarvis_claude_global.lock (pid 222)",
            "[2026-03-08T11:00:13] PREFLIGHT: Verification FAILED: lock held: clarvis_claude_global.lock (pid 333)",
            "[2026-03-08T07:09:06] EXECUTION: executor=claude exit=0 duration=510s timeout=1500s tier=complex",
            "[2026-03-08T07:09:06] POSTFLIGHT: Recording outcome: success (exit=0, duration=510s)",
            "[2026-03-08T07:11:10] POSTFLIGHT: SELF-TEST FAILED: pytest_exit=1, brain_ok=True",
            "[2026-03-09T15:02:20] EXECUTION: executor=claude exit=0 duration=105s timeout=1200s tier=vision",
            "[2026-03-09T15:02:21] POSTFLIGHT: Recording outcome: success (exit=0, duration=105s)",
            "[2026-03-09T15:04:00] POSTFLIGHT: PERF GATE: FAIL — trajectory_eval (8.59s)",
        ]
        log_path = self._make_log(lines)
        try:
            completed, failed = self._run_assessor(log_path)
            self.assertEqual(completed, 2)
            self.assertEqual(failed, 0, "Lock-held / SELF-TEST / PERF GATE lines must not inflate failures")
        finally:
            os.unlink(log_path)


class TestAssessorMatchesProductionRegex(unittest.TestCase):
    """Lock-step test: the in-test parser must mirror the production assessor.

    If self_model.py is edited, this test fails fast unless the test parser is
    updated in the same PR. Catches drift between the test mirror and reality.
    """

    def test_production_assessor_uses_anchored_outcome_patterns(self):
        import os as _os
        repo_root = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..', '..'))
        sm_path = _os.path.join(repo_root, 'clarvis', 'metrics', 'self_model.py')
        with open(sm_path) as f:
            src = f.read()
        # Production must anchor success on "Recording outcome: success"
        self.assertIn('"Recording outcome: success"', src)
        # Production must anchor failures on the three task_status terminal states
        self.assertIn('"Recording outcome: failure"', src)
        self.assertIn('"Recording outcome: timeout"', src)
        self.assertIn('"Recording outcome: crash"', src)
        # The loose 'FAILED' substring match must be gone (it was the source of
        # SELF-TEST FAILED / PERF GATE: FAIL false positives).
        self.assertNotIn('"FAILED" in l', src)


if __name__ == '__main__':
    unittest.main()
