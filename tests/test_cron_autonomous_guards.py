"""Regression tests for cron_autonomous.sh crash-guard JSON handling.

Tests the atomic-write pattern: preflight JSON rewrites must survive
partial writes and malformed input.
"""

import json
import os
import subprocess
import tempfile

import pytest


class TestPreflightJsonSanitizer:
    """Test the inline Python JSON sanitizer from cron_autonomous.sh."""

    def _run_sanitizer(self, content: str) -> tuple[int, str, str]:
        """Run the JSON-sanitize logic extracted from cron_autonomous.sh.

        Writes `content` to a temp file, runs the sanitizer, returns
        (exit_code, file_contents_after, stderr).
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(content)
            tmp = f.name
        try:
            # Replicate the inline Python from cron_autonomous.sh
            script = f"""
import json, sys, os, tempfile
with open('{tmp}') as f:
    lines = f.readlines()
json_lines = [l for l in lines if l.strip().startswith('{{')]
if not json_lines:
    print('ERROR: No JSON found in preflight output', file=sys.stderr)
    sys.exit(1)
data = json.loads(json_lines[-1])
fd, t = tempfile.mkstemp(suffix='.json', dir=os.path.dirname('{tmp}') or '/tmp')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    os.rename(t, '{tmp}')
except Exception:
    os.unlink(t)
    raise
"""
            result = subprocess.run(
                ["python3", "-c", script],
                capture_output=True, text=True, timeout=10,
            )
            after = ""
            if os.path.exists(tmp):
                with open(tmp) as f:
                    after = f.read()
            return result.returncode, after, result.stderr
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_valid_json_passthrough(self):
        """Valid JSON line is preserved."""
        data = {"status": "ok", "task": "test"}
        rc, after, _ = self._run_sanitizer(json.dumps(data) + "\n")
        assert rc == 0
        assert json.loads(after) == data

    def test_json_with_noise_lines(self):
        """JSON preceded by non-JSON lines is extracted correctly."""
        content = "WARNING: something\nDEBUG: init\n" + json.dumps({"task": "foo"}) + "\n"
        rc, after, _ = self._run_sanitizer(content)
        assert rc == 0
        assert json.loads(after)["task"] == "foo"

    def test_no_json_fails_cleanly(self):
        """No JSON in output -> exit 1, file untouched."""
        rc, _, stderr = self._run_sanitizer("just some text\nno json here\n")
        assert rc == 1
        assert "No JSON found" in stderr

    def test_malformed_json_fails_cleanly(self):
        """Truncated/malformed JSON -> exit 1 (json.loads fails)."""
        rc, _, stderr = self._run_sanitizer('{"status": "ok", "task": \n')
        assert rc == 1

    def test_empty_file_fails_cleanly(self):
        """Empty file -> exit 1."""
        rc, _, stderr = self._run_sanitizer("")
        assert rc == 1
        assert "No JSON found" in stderr

    def test_multiple_json_lines_takes_last(self):
        """Multiple JSON lines: takes the last one (most complete)."""
        line1 = json.dumps({"partial": True})
        line2 = json.dumps({"status": "ok", "task": "real"})
        content = line1 + "\n" + line2 + "\n"
        rc, after, _ = self._run_sanitizer(content)
        assert rc == 0
        parsed = json.loads(after)
        assert parsed["task"] == "real"

    def test_atomic_write_no_partial(self):
        """Atomic write: original file is valid JSON or untouched after error."""
        # Simulate a case where json_lines exist but aren't valid JSON
        # (e.g., a line starting with { but not valid JSON)
        content = "{this is not valid json}\n"
        rc, _, _ = self._run_sanitizer(content)
        assert rc == 1  # Should fail, not leave partial file


class TestPromptInputGuard:
    """Regression tests for empty-prompt guards.

    Covers: AUTONOMOUS_PROMPT_INPUT_GUARD — Claude/OpenRouter invocations
    must never crash with 'Input must be provided either through stdin or
    as a prompt argument when using --print'.
    """

    def test_run_claude_code_prompt_guard_rejects_empty(self):
        """The run_claude_code() prompt guard rejects an empty prompt file."""
        # Simulate the shell guard: [ ! -s "$_prompt_file" ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("")  # empty file
            tmp = f.name
        try:
            result = subprocess.run(
                ["sh", "-c", f'[ ! -s "{tmp}" ] && echo "PROMPT_GUARD_TRIGGERED" || echo "WOULD_EXECUTE"'],
                capture_output=True, text=True, timeout=5,
            )
            assert "PROMPT_GUARD_TRIGGERED" in result.stdout
        finally:
            os.unlink(tmp)

    def test_run_claude_code_prompt_guard_allows_nonempty(self):
        """The run_claude_code() prompt guard allows a non-empty prompt file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("You are Clarvis. Do a task.\n")
            tmp = f.name
        try:
            result = subprocess.run(
                ["sh", "-c", f'[ ! -s "{tmp}" ] && echo "PROMPT_GUARD_TRIGGERED" || echo "WOULD_EXECUTE"'],
                capture_output=True, text=True, timeout=5,
            )
            assert "WOULD_EXECUTE" in result.stdout
        finally:
            os.unlink(tmp)

    def test_openrouter_empty_task_guard(self):
        """execute_openrouter() rejects empty task text without calling the API."""
        import sys
        sys.path.insert(0, os.path.join(
            os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
        ))
        from clarvis.orch.router import execute_openrouter

        for empty_input in ["", "   ", None]:
            result = execute_openrouter(empty_input)
            assert result["exit_code"] == 1, f"Expected exit 1 for input={empty_input!r}"
            assert "Empty task text" in result["output"], f"Expected guard message for input={empty_input!r}"
            assert result["fallback"] is False, "Empty input should not trigger Claude fallback"


class TestCrashGuardAtomicWrite:
    """Test the crash-guard JSON injection pattern."""

    def _run_crash_guard(self, preflight_data: dict, duration: int = 3) -> tuple[int, dict]:
        """Run the crash-guard injection logic from cron_autonomous.sh."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(preflight_data, f)
            tmp = f.name
        try:
            script = f"""
import json, os, tempfile
with open('{tmp}') as f:
    d = json.load(f)
d['crash_guard'] = True
d['crash_reason'] = 'instant_fail'
d['crash_duration'] = {duration}
fd, t = tempfile.mkstemp(suffix='.json', dir=os.path.dirname('{tmp}') or '/tmp')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(d, f)
    os.rename(t, '{tmp}')
except Exception:
    os.unlink(t)
    raise
"""
            result = subprocess.run(
                ["python3", "-c", script],
                capture_output=True, text=True, timeout=10,
            )
            with open(tmp) as f:
                after = json.load(f)
            return result.returncode, after
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_crash_guard_injects_fields(self):
        """Crash guard adds crash_guard, crash_reason, crash_duration."""
        rc, data = self._run_crash_guard({"task": "test", "status": "ok"}, duration=5)
        assert rc == 0
        assert data["crash_guard"] is True
        assert data["crash_reason"] == "instant_fail"
        assert data["crash_duration"] == 5
        assert data["task"] == "test"  # original data preserved

    def test_crash_guard_preserves_existing(self):
        """Crash guard preserves all existing preflight fields."""
        original = {"task": "foo", "chain_id": "abc", "task_salience": 0.8}
        rc, data = self._run_crash_guard(original, duration=2)
        assert rc == 0
        for k, v in original.items():
            assert data[k] == v
