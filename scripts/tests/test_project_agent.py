"""
Unit tests for project_agent.py — spawn prompt construction & output parsing.

Run: python3 -m pytest scripts/tests/test_project_agent.py -v
"""
import json
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

from unittest.mock import patch, MagicMock

from project_agent import (
    build_spawn_prompt,
    build_spawn_command,
    _parse_agent_output,
    _is_task_failure,
    _build_retry_context,
    cmd_spawn_with_retry,
    CLAUDE_BIN,
    MAX_RETRIES,
)


# ── Fixtures ──

@pytest.fixture
def agent_config():
    return {
        "name": "test-project",
        "repo_url": "https://github.com/test/repo.git",
        "branch": "dev",
        "constraints": [
            "Do NOT push to main",
            "Run tests before PR",
        ],
        "budget": {"max_timeout": 1800},
    }


@pytest.fixture
def agent_dir(tmp_path):
    """Create a minimal agent directory structure."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    memory = tmp_path / "memory"
    memory.mkdir()
    data = tmp_path / "data" / "brain"
    data.mkdir(parents=True)

    # Write a procedures file
    proc_file = memory / "procedures.md"
    proc_file.write_text("## Build\nnpm run build\n## Test\nnpm test\n")

    return tmp_path


# ── build_spawn_prompt tests ──

class TestBuildSpawnPrompt:
    def test_contains_task(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "Fix the login bug", agent_config, agent_dir
        )
        assert "Fix the login bug" in prompt

    def test_contains_constraints(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, agent_dir
        )
        assert "Do NOT push to main" in prompt
        assert "Run tests before PR" in prompt

    def test_contains_output_protocol(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, agent_dir
        )
        assert "Output Protocol" in prompt
        assert '"status"' in prompt
        assert '"pr_url"' in prompt
        assert "```json" in prompt

    def test_contains_procedures(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, agent_dir
        )
        assert "npm run build" in prompt
        assert "Known Procedures" in prompt

    def test_no_procedures_if_missing(self, agent_config, tmp_path):
        """No procedures section when file doesn't exist."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, tmp_path
        )
        assert "Known Procedures" not in prompt

    def test_context_included(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, agent_dir,
            context="Previous PR had merge conflicts"
        )
        assert "Context from Clarvis" in prompt
        assert "merge conflicts" in prompt

    def test_context_excluded_when_empty(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, agent_dir, context=""
        )
        assert "Context from Clarvis" not in prompt

    def test_agent_name_in_prompt(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "my-agent", "task", agent_config, agent_dir
        )
        assert "my-agent" in prompt

    def test_working_directory_in_prompt(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "task", agent_config, agent_dir
        )
        assert str(agent_dir / "workspace") in prompt

    def test_brain_dir_in_prompt(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "task", agent_config, agent_dir
        )
        assert str(agent_dir / "data" / "brain") in prompt


# ── build_spawn_command tests ──

class TestBuildSpawnCommand:
    def test_reads_from_file_not_inline(self):
        """Command must read prompt from file via $(cat), not pass inline."""
        cmd = build_spawn_command("/tmp/prompt.txt", 1200)
        assert "$(cat " in cmd
        assert "/tmp/prompt.txt" in cmd

    def test_contains_timeout(self):
        cmd = build_spawn_command("/tmp/prompt.txt", 900)
        assert "timeout 900 " in cmd

    def test_contains_claude_binary(self):
        cmd = build_spawn_command("/tmp/prompt.txt", 1200)
        assert CLAUDE_BIN in cmd

    def test_contains_permissions_flag(self):
        cmd = build_spawn_command("/tmp/prompt.txt", 1200)
        assert "--dangerously-skip-permissions" in cmd

    def test_contains_model_flag(self):
        cmd = build_spawn_command("/tmp/prompt.txt", 1200)
        assert "--model claude-opus-4-6" in cmd

    def test_unsets_nesting_guards(self):
        cmd = build_spawn_command("/tmp/prompt.txt", 1200)
        assert "-u CLAUDECODE" in cmd
        assert "-u CLAUDE_CODE_ENTRYPOINT" in cmd

    def test_prompt_file_is_quoted(self):
        """File paths with spaces should be safely quoted."""
        cmd = build_spawn_command("/tmp/my agent prompt.txt", 1200)
        assert "'/tmp/my agent prompt.txt'" in cmd

    def test_no_raw_prompt_content(self):
        """The command string must NOT contain the prompt content itself."""
        cmd = build_spawn_command("/tmp/prompt.txt", 1200)
        # After the -p flag there should be a $(cat ...) not a long string
        # Find " -p " (with spaces) to avoid matching --dangerously-skip-permissions
        assert " -p " in cmd
        p_idx = cmd.index(" -p ") + 4
        after_p = cmd[p_idx:].strip()
        assert after_p.startswith('"$(cat')


# ── _parse_agent_output tests ──

class TestParseAgentOutput:
    def test_parses_json_block(self):
        output = textwrap.dedent("""\
            Did some work...

            ```json
            {
              "status": "success",
              "pr_url": "https://github.com/test/repo/pull/42",
              "branch": "feature/login-fix",
              "summary": "Fixed the login bug",
              "files_changed": ["src/auth.ts"],
              "procedures": ["Test: npm test"],
              "follow_ups": [],
              "tests_passed": true
            }
            ```
        """)
        result = _parse_agent_output(output)
        assert result["status"] == "success"
        assert result["pr_url"] == "https://github.com/test/repo/pull/42"
        assert result["tests_passed"] is True

    def test_parses_last_json_block(self):
        """When multiple JSON blocks exist, use the last one."""
        output = textwrap.dedent("""\
            ```json
            {"status": "partial", "summary": "first attempt"}
            ```

            Did more work...

            ```json
            {"status": "success", "summary": "final result"}
            ```
        """)
        result = _parse_agent_output(output)
        assert result["status"] == "success"
        assert result["summary"] == "final result"

    def test_parses_raw_json_line(self):
        output = 'Some output\n{"status": "success", "summary": "done"}\n'
        result = _parse_agent_output(output)
        assert result["status"] == "success"

    def test_empty_output(self):
        result = _parse_agent_output("")
        assert result["status"] == "failed"
        assert "No output" in result["summary"]

    def test_no_json_output(self):
        result = _parse_agent_output("Just some text without any JSON")
        assert result["status"] == "unknown"

    def test_malformed_json_falls_through(self):
        output = "```json\n{bad json\n```\n"
        result = _parse_agent_output(output)
        assert result["status"] == "unknown"


# ── _is_task_failure tests ──

class TestIsTaskFailure:
    def test_success_is_not_failure(self):
        result = {"exit_code": 0, "result": {"status": "success"}}
        assert _is_task_failure(result) is False

    def test_partial_is_not_failure(self):
        result = {"exit_code": 0, "result": {"status": "partial"}}
        assert _is_task_failure(result) is False

    def test_nonzero_exit_is_failure(self):
        result = {"exit_code": 1, "result": {"status": "success"}}
        assert _is_task_failure(result) is True

    def test_timeout_exit_is_failure(self):
        result = {"exit_code": 124, "result": {"status": "unknown"}}
        assert _is_task_failure(result) is True

    def test_failed_status_is_failure(self):
        result = {"exit_code": 0, "result": {"status": "failed"}}
        assert _is_task_failure(result) is True

    def test_unknown_status_is_failure(self):
        result = {"exit_code": 0, "result": {"status": "unknown"}}
        assert _is_task_failure(result) is True

    def test_config_error_not_retryable(self):
        """Config errors (agent not found) should not be treated as retryable."""
        result = {"error": "Agent 'foo' not found"}
        assert _is_task_failure(result) is False


# ── _build_retry_context tests ──

class TestBuildRetryContext:
    def test_contains_attempt_number(self):
        result = {"exit_code": 1, "result": {"status": "failed"}, "output_tail": ""}
        ctx = _build_retry_context(result, 1, 2)
        assert "RETRY ATTEMPT 1/2" in ctx

    def test_contains_exit_code(self):
        result = {"exit_code": 124, "result": {"status": "unknown"}, "output_tail": ""}
        ctx = _build_retry_context(result, 1, 2)
        assert "124" in ctx

    def test_contains_error_output(self):
        result = {
            "exit_code": 1,
            "result": {"status": "failed", "summary": "npm build error"},
            "output_tail": "Error: Cannot find module 'react'",
        }
        ctx = _build_retry_context(result, 1, 2)
        assert "Cannot find module" in ctx
        assert "npm build error" in ctx

    def test_contains_retry_strategies(self):
        result = {"exit_code": 1, "result": {"status": "failed"}, "output_tail": ""}
        ctx = _build_retry_context(result, 1, 2)
        assert "Strategies" in ctx
        assert "simpler approach" in ctx


# ── cmd_spawn_with_retry tests (mocked) ──

class TestSpawnWithRetry:
    def _make_result(self, status="success", exit_code=0, task_id="t001",
                     elapsed=60.0, output_tail="done"):
        return {
            "task_id": task_id,
            "agent": "test",
            "exit_code": exit_code,
            "elapsed": elapsed,
            "result": {"status": status},
            "output_tail": output_tail,
            "log": "/tmp/test.log",
        }

    @patch("project_agent.cmd_spawn")
    @patch("project_agent.time.sleep")
    def test_no_retry_on_success(self, mock_sleep, mock_spawn):
        """Successful first attempt should not retry."""
        mock_spawn.return_value = self._make_result(status="success")

        result = cmd_spawn_with_retry("test", "do thing", max_retries=2)

        assert mock_spawn.call_count == 1
        assert mock_sleep.call_count == 0
        assert result["retry_metadata"]["total_attempts"] == 1
        assert result["retry_metadata"]["succeeded_on_attempt"] == 0

    @patch("project_agent.cmd_spawn")
    @patch("project_agent.time.sleep")
    def test_retries_on_failure_then_succeeds(self, mock_sleep, mock_spawn):
        """Should retry on failure and return success when retry works."""
        mock_spawn.side_effect = [
            self._make_result(status="failed", exit_code=1, task_id="t001"),
            self._make_result(status="success", exit_code=0, task_id="t002"),
        ]

        result = cmd_spawn_with_retry("test", "do thing", max_retries=2)

        assert mock_spawn.call_count == 2
        assert mock_sleep.call_count == 1  # backoff before retry
        assert result["retry_metadata"]["total_attempts"] == 2
        assert result["retry_metadata"]["succeeded_on_attempt"] == 1
        assert result["result"]["status"] == "success"

    @patch("project_agent.cmd_spawn")
    @patch("project_agent.time.sleep")
    def test_exhausts_retries(self, mock_sleep, mock_spawn):
        """Should stop after max_retries + 1 total attempts."""
        mock_spawn.return_value = self._make_result(
            status="failed", exit_code=1)

        result = cmd_spawn_with_retry("test", "do thing", max_retries=2)

        assert mock_spawn.call_count == 3  # 1 initial + 2 retries
        assert mock_sleep.call_count == 2
        assert result["retry_metadata"]["total_attempts"] == 3
        assert result["retry_metadata"]["succeeded_on_attempt"] is None

    @patch("project_agent.cmd_spawn")
    @patch("project_agent.time.sleep")
    def test_config_error_no_retry(self, mock_sleep, mock_spawn):
        """Config errors (agent not found) should not trigger retries."""
        mock_spawn.return_value = {"error": "Agent 'foo' not found"}

        result = cmd_spawn_with_retry("foo", "do thing", max_retries=2)

        assert mock_spawn.call_count == 1
        assert mock_sleep.call_count == 0

    @patch("project_agent.cmd_spawn")
    @patch("project_agent.time.sleep")
    def test_retry_passes_error_context(self, mock_sleep, mock_spawn):
        """Retry should include error context from previous failure."""
        mock_spawn.side_effect = [
            self._make_result(status="failed", exit_code=1,
                              output_tail="Error: ENOENT"),
            self._make_result(status="success", exit_code=0),
        ]

        result = cmd_spawn_with_retry("test", "do thing",
                                      context="initial ctx", max_retries=1)

        # Check that the second call received retry context
        second_call_context = mock_spawn.call_args_list[1][1].get("context", "")
        if not second_call_context:
            # positional arg
            second_call_context = mock_spawn.call_args_list[1][0][3] if len(mock_spawn.call_args_list[1][0]) > 3 else ""
        assert "RETRY ATTEMPT" in second_call_context
        assert "ENOENT" in second_call_context

    @patch("project_agent.cmd_spawn")
    @patch("project_agent.time.sleep")
    def test_max_retries_capped(self, mock_sleep, mock_spawn):
        """Retries should be capped at MAX_RETRIES even if higher value passed."""
        mock_spawn.return_value = self._make_result(
            status="failed", exit_code=1)

        result = cmd_spawn_with_retry("test", "do thing", max_retries=10)

        # MAX_RETRIES is 2, so max 3 total attempts
        assert mock_spawn.call_count == 3

    @patch("project_agent.cmd_spawn")
    @patch("project_agent.time.sleep")
    def test_partial_status_not_retried(self, mock_sleep, mock_spawn):
        """Partial status (some work done) should not be retried."""
        mock_spawn.return_value = self._make_result(status="partial", exit_code=0)

        result = cmd_spawn_with_retry("test", "do thing", max_retries=2)

        assert mock_spawn.call_count == 1
        assert result["retry_metadata"]["succeeded_on_attempt"] == 0
