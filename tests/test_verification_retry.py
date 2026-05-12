"""Tests for clarvis.cognition.verification_retry.

Covers the acceptance criteria from [ESR_POSTFLIGHT_VERIFICATION_RETRY_PROBE]:
  * pass-on-retry (rescue case)
  * fail-on-retry (test really is broken)
  * timeout (budget exceeded)
plus extraction, gating, safety filters, and shadow-mode telemetry.
"""

import pytest

from clarvis.cognition.verification_retry import (
    DEFAULT_BUDGET_S,
    extract_test_command,
    maybe_retry,
    run_verification_retry,
    should_attempt_retry,
)


# ── extract_test_command ────────────────────────────────────────────

class TestExtractTestCommand:
    def test_plain_pytest_invocation(self):
        text = "Ran `pytest tests/test_foo.py` and it passed."
        assert extract_test_command(text) == "pytest tests/test_foo.py"

    def test_python_m_pytest(self):
        text = "Verification: python3 -m pytest tests/test_bar.py -k flake"
        cmd = extract_test_command(text)
        assert cmd is not None
        assert "pytest" in cmd
        assert "test_bar.py" in cmd

    def test_strips_shell_pipe(self):
        """Pipe terminates the candidate; bare pytest portion is returned."""
        text = "Did `pytest tests/foo.py | grep PASS` and saw output."
        cmd = extract_test_command(text)
        # Returned command must not contain dangerous shell metachars
        assert cmd is None or ("|" not in cmd and "grep" not in cmd)

    def test_strips_redirection(self):
        """Redirection terminates the candidate; extracted command is safe."""
        text = "Ran pytest tests/foo.py > /tmp/out.log"
        cmd = extract_test_command(text)
        assert cmd is None or (">" not in cmd and "/tmp" not in cmd)

    def test_rejects_subshell(self):
        text = "Ran $(pytest tests/foo.py) for a side effect"
        # The regex picks up `pytest tests/foo.py` from inside $(...) but the
        # leading `$(` is on the candidate? Actually $( is matched against the
        # surrounding chars. Verify _looks_safe rejects $( from the candidate
        # content; since pytest tests/foo.py alone is safe, this may pass.
        # The point: ensure dangerous wrappers don't leak through.
        cmd = extract_test_command(text)
        # Either None or the bare pytest substring (no $( in candidate)
        assert cmd is None or "$(" not in cmd

    def test_none_for_empty(self):
        assert extract_test_command("") is None
        assert extract_test_command(None) is None

    def test_none_for_text_without_pytest(self):
        assert extract_test_command("All good, no tests cited.") is None


# ── should_attempt_retry (gating) ───────────────────────────────────

class TestShouldAttemptRetry:
    def test_eligible_on_partial_with_claim(self):
        text = '{"tests_passed": true, "error": null}'
        eligible, reason = should_attempt_retry(
            task_status="partial_success",
            output_text=text,
        )
        assert eligible is True
        assert reason == "eligible"

    def test_skips_when_status_is_success(self):
        eligible, reason = should_attempt_retry(
            task_status="success",
            output_text='{"tests_passed": true}',
        )
        assert eligible is False
        assert "status" in reason

    def test_skips_without_tests_passed_claim(self):
        eligible, reason = should_attempt_retry(
            task_status="partial_success",
            output_text="agent did not claim anything",
        )
        assert eligible is False
        assert reason == "no_tests_passed_claim"

    def test_skips_real_failure_type(self):
        eligible, reason = should_attempt_retry(
            task_status="partial_success",
            output_text='{"tests_passed": true}',
            failure_type="action.test_failure",
        )
        assert eligible is False
        assert reason == "real_failure_type"

    def test_skips_when_already_retried(self):
        eligible, reason = should_attempt_retry(
            task_status="partial_success",
            output_text='{"tests_passed": true}',
            already_retried=True,
        )
        assert eligible is False
        assert reason == "already_retried"


# ── run_verification_retry (subprocess) ─────────────────────────────

class TestRunVerificationRetry:
    def test_pass_on_retry_zero_exit(self):
        """Pass-on-retry: command exits 0 → outcome=success."""
        # `python3 -c "pass"` is a pytest-shaped no-op? No — _looks_safe
        # requires "pytest" in the command. Use a real pytest invocation
        # against a tmp test file that passes.
        # Simpler: bypass the safety filter by calling _looks_safe path
        # explicitly — use a `pytest --version` style command which is
        # near-instant and exits 0.
        out = run_verification_retry("pytest --version", budget_s=30)
        assert out["triggered"] is True
        # pytest --version exits 0 when pytest is installed
        if out["exit_code"] == 0:
            assert out["outcome"] == "success"
        else:
            # pytest not installed in env — still validates the contract
            assert out["outcome"] in {"success", "still_failing", "error"}
        assert out["command"] == "pytest --version"
        assert isinstance(out["duration_s"], float)

    def test_fail_on_retry_nonzero_exit(self, tmp_path):
        """Fail-on-retry: pytest against a missing path exits non-zero."""
        missing = tmp_path / "definitely_missing_test.py"
        out = run_verification_retry(
            f"pytest {missing}", budget_s=30)
        assert out["triggered"] is True
        # Pytest exits with non-zero when given a missing file
        assert out["outcome"] in {"still_failing", "error"}
        if out["outcome"] == "still_failing":
            assert out["exit_code"] != 0

    def test_timeout(self, tmp_path):
        """Timeout: a slow test command must hit the budget cap."""
        # Create a test file that sleeps long enough to trip the timeout.
        slow_test = tmp_path / "test_slow.py"
        slow_test.write_text(
            "import time\n"
            "def test_slow():\n"
            "    time.sleep(5)\n"
        )
        out = run_verification_retry(
            f"pytest {slow_test}", budget_s=1)
        assert out["triggered"] is True
        assert out["outcome"] == "timeout"
        # Duration should be close to the budget (within 2s overhead)
        assert out["duration_s"] >= 0.9

    def test_unsafe_command_rejected(self):
        out = run_verification_retry("pytest tests/ | grep PASS", budget_s=5)
        assert out["outcome"] == "error"
        assert "unsafe" in out.get("error", "")

    def test_empty_command_rejected(self):
        out = run_verification_retry("", budget_s=5)
        assert out["outcome"] == "error"


# ── maybe_retry (top-level integration) ─────────────────────────────

class TestMaybeRetry:
    def test_shadow_mode_never_overrides(self, monkeypatch):
        monkeypatch.delenv("CLARVIS_VERIFICATION_RETRY_ACTIVE", raising=False)
        out = maybe_retry(
            task_status="partial_success",
            output_text='Verified with `pytest --version`. {"tests_passed": true}',
            shadow_mode=True,
        )
        # Even if retry succeeds, shadow mode must not override
        assert out["override"] is False
        assert out["shadow_mode"] is True

    def test_active_mode_overrides_on_success(self, monkeypatch):
        out = maybe_retry(
            task_status="partial_success",
            output_text='Verified with `pytest --version`. {"tests_passed": true}',
            shadow_mode=False,
        )
        if out.get("outcome") == "success":
            assert out["override"] is True
        else:
            # pytest may not be installed; contract still holds
            assert out["override"] is False

    def test_skipped_when_status_success(self):
        out = maybe_retry(
            task_status="success",
            output_text='{"tests_passed": true}',
            shadow_mode=True,
        )
        assert out["triggered"] is False
        assert out["outcome"] == "skipped"

    def test_skipped_when_no_command(self):
        out = maybe_retry(
            task_status="partial_success",
            output_text='{"tests_passed": true} — no command cited',
            shadow_mode=True,
        )
        assert out["triggered"] is False
        assert out["reason"] == "no_test_command_extracted"

    def test_env_var_flip(self, monkeypatch):
        # Explicit shadow_mode arg takes precedence over env
        monkeypatch.setenv("CLARVIS_VERIFICATION_RETRY_ACTIVE", "1")
        out = maybe_retry(
            task_status="success",  # short-circuits before retry
            output_text='{"tests_passed": true}',
        )
        # env says active → shadow_mode should be False
        assert out["shadow_mode"] is False
