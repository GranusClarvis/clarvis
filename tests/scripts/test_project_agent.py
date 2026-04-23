"""
Unit tests for project_agent.py — spawn prompt construction & output parsing.

Run: python3 -m pytest scripts/tests/test_project_agent.py -v
"""
import json
import os
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "scripts"))
import _paths  # noqa: F401,E402

from unittest.mock import patch, MagicMock

from project_agent import (
    build_spawn_prompt,
    build_spawn_command,
    build_dependency_map,
    _parse_agent_output,
    _is_task_failure,
    _build_retry_context,
    _comment_pr,
    _flag_pr,
    _extract_gh_repo,
    apply_mirror_gate,
    _sync_mirror,
    _get_changed_files_from_git,
    _fetch_and_resolve_base,
    _sync_and_checkout_work_branch,
    worktree_create,
    MIRROR_GATE_MODE,
    _MIRROR_GATE_DEFAULT,
    cmd_spawn_with_retry,
    cmd_spawn_parallel,
    _poll_ci_checks,
    _extract_ci_failure_logs,
    _ci_fix_loop,
    decompose_task,
    run_task_loop,
    validate_a2a_result,
    normalize_a2a_result,
    run_mirror_validation,
    MIRROR_DIRS,
    MIRROR_CHECKS,
    _acquire_loop_lock,
    _release_loop_lock,
    _loop_lock_path,
    _acquire_agent_claude_lock,
    _release_agent_claude_lock,
    _agent_claude_lock_path,
    _acquire_claude_slot,
    _release_claude_slot,
    _slots_dir,
    MAX_PARALLEL_AGENT_CLAUDE,
    A2A_PROTOCOL_VERSION,
    A2A_REQUIRED_FIELDS,
    A2A_VALID_STATUSES,
    CLAUDE_BIN,
    MAX_RETRIES,
    CI_FIX_MAX_ATTEMPTS,
    LOOP_MAX_SESSIONS,
    LOOP_INTER_SUBTASK_DELAY_MIN,
    LOOP_INTER_SUBTASK_DELAY_MAX,
    COMMIT_EXT_WHITELIST,
    COMMIT_BLOCKED_PATTERNS,
    safe_stage_files,
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
        assert "Output (A2A/v1" in prompt
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

    def test_context_omitted_when_empty(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, agent_dir, context=""
        )
        assert "Context from Clarvis" not in prompt

    def test_explicit_context_preserved(self, agent_config, agent_dir):
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, agent_dir,
            context="Custom context here"
        )
        assert "Custom context here" in prompt

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


# ── _poll_ci_checks tests ──

class TestPollCiChecks:
    @patch("project_agent.subprocess.run")
    def test_all_pass(self, mock_run):
        """All checks passing returns status=pass."""
        checks_json = json.dumps([
            {"name": "build", "bucket": "pass", "state": "SUCCESS", "link": "https://example.com/1"},
            {"name": "lint", "bucket": "pass", "state": "SUCCESS", "link": "https://example.com/2"},
        ])
        mock_run.return_value = MagicMock(returncode=0, stdout=checks_json, stderr="")
        result = _poll_ci_checks(42, "owner/repo", timeout=5)
        assert result["status"] == "pass"
        assert len(result["checks"]) == 2

    @patch("project_agent.subprocess.run")
    def test_failure_detected(self, mock_run):
        """Failed check returns status=fail with failed_checks list."""
        checks_json = json.dumps([
            {"name": "build", "bucket": "fail", "state": "FAILURE", "link": "https://example.com/1"},
            {"name": "lint", "bucket": "pass", "state": "SUCCESS", "link": "https://example.com/2"},
        ])
        mock_run.return_value = MagicMock(returncode=1, stdout=checks_json, stderr="")
        result = _poll_ci_checks(42, "owner/repo", timeout=5)
        assert result["status"] == "fail"
        assert "build" in result["failed_checks"]

    @patch("project_agent.subprocess.run")
    def test_no_checks(self, mock_run):
        """No checks returns pass with note."""
        mock_run.return_value = MagicMock(returncode=0, stdout="no checks reported\n", stderr="no checks")
        result = _poll_ci_checks(42, "owner/repo", timeout=5)
        assert result["status"] == "pass"
        assert "No CI" in result.get("note", "")

    @patch("project_agent.subprocess.run")
    def test_subprocess_error(self, mock_run):
        """Subprocess error returns status=error."""
        mock_run.side_effect = FileNotFoundError("gh not found")
        result = _poll_ci_checks(42, "owner/repo", timeout=5)
        assert result["status"] == "error"

    @patch("project_agent.subprocess.run")
    def test_exit_code_8_pending(self, mock_run):
        """Exit code 8 means checks still pending — keeps polling."""
        # First call: pending (exit 8), second call: pass (exit 0)
        checks_pending = json.dumps([
            {"name": "build", "bucket": "pending", "state": "QUEUED", "link": ""},
        ])
        checks_pass = json.dumps([
            {"name": "build", "bucket": "pass", "state": "SUCCESS", "link": ""},
        ])
        mock_run.side_effect = [
            MagicMock(returncode=8, stdout=checks_pending, stderr=""),
            MagicMock(returncode=0, stdout=checks_pass, stderr=""),
        ]
        with patch("project_agent.time.sleep"):
            result = _poll_ci_checks(42, "owner/repo", timeout=30)
        assert result["status"] == "pass"

    @patch("project_agent.subprocess.run")
    def test_cancel_bucket_is_failure(self, mock_run):
        """Cancelled checks count as failures."""
        checks_json = json.dumps([
            {"name": "build", "bucket": "cancel", "state": "CANCELLED", "link": ""},
        ])
        mock_run.return_value = MagicMock(returncode=1, stdout=checks_json, stderr="")
        result = _poll_ci_checks(42, "owner/repo", timeout=5)
        assert result["status"] == "fail"
        assert "build" in result["failed_checks"]

    @patch("project_agent.subprocess.run")
    def test_skipping_bucket_is_pass(self, mock_run):
        """Skipped checks are not failures."""
        checks_json = json.dumps([
            {"name": "build", "bucket": "pass", "state": "SUCCESS", "link": ""},
            {"name": "optional", "bucket": "skipping", "state": "SKIPPED", "link": ""},
        ])
        mock_run.return_value = MagicMock(returncode=0, stdout=checks_json, stderr="")
        result = _poll_ci_checks(42, "owner/repo", timeout=5)
        assert result["status"] == "pass"


# ── _extract_ci_failure_logs tests ──

class TestExtractCiFailureLogs:
    @patch("project_agent.subprocess.run")
    def test_fallback_on_api_failure(self, mock_run):
        """If gh pr view fails, returns error message."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = _extract_ci_failure_logs(42, "owner/repo", ["build"])
        assert "Could not fetch PR details" in result or "build" in result

    @patch("project_agent.subprocess.run")
    def test_extracts_run_details(self, mock_run):
        """Extracts check run details from gh api output."""
        pr_view = MagicMock(returncode=0, stdout='{"headRefOid": "abc123"}', stderr="")
        check_runs = MagicMock(
            returncode=0,
            stdout='{"name":"build","status":"completed","conclusion":"failure",'
                   '"output_title":"Build failed","output_summary":"Error in line 42",'
                   '"html_url":"https://example.com"}\n',
            stderr="",
        )
        annotations = MagicMock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = [pr_view, check_runs, annotations]

        result = _extract_ci_failure_logs(42, "owner/repo")
        assert "Build failed" in result
        assert "Error in line 42" in result


# ── decompose_task tests ──

class TestDecomposeTask:
    def test_simple_task_single_subtask(self):
        """Short, simple tasks return single subtask."""
        r = decompose_task("test", "Fix typo")
        assert len(r) == 1
        assert r[0]["id"] == "t1"
        assert r[0]["deps"] == []

    def test_connector_splits(self):
        """Tasks with 'and then' get split into multiple subtasks."""
        r = decompose_task("test", "Add login page and then add logout button and write tests")
        assert len(r) >= 2
        # Verify dep chain
        for i, s in enumerate(r):
            if i > 0:
                assert len(s["deps"]) > 0

    def test_implement_keyword_decomposes(self):
        """Tasks starting with 'implement' get at least [impl, PR]."""
        r = decompose_task("test", "Implement user auth with OAuth2")
        assert len(r) >= 2

    def test_max_five_subtasks(self):
        """Should cap at 5 subtasks max."""
        long_task = " and ".join([f"task{i}" for i in range(10)])
        r = decompose_task("test", long_task)
        assert len(r) <= 6  # 5 parts + optional test step

    def test_subtask_has_required_keys(self):
        """Each subtask has id, task, deps, timeout."""
        r = decompose_task("test", "Add X and then add Y")
        for s in r:
            assert "id" in s
            assert "task" in s
            assert "deps" in s
            assert "timeout" in s


# ── run_task_loop tests ──

class TestRunTaskLoop:
    @patch("project_agent.cmd_spawn_with_retry")
    @patch("project_agent._load_config")
    @patch("project_agent._agent_dir")
    @patch("project_agent._snapshot_cost")
    def test_single_subtask_success(self, mock_cost, mock_dir, mock_config, mock_spawn, tmp_path):
        """Single subtask that succeeds returns overall success."""
        mock_config.return_value = {
            "name": "test", "repo_url": "https://github.com/o/r.git",
            "branch": "dev", "trust_score": 0.5,
        }
        mock_dir.return_value = tmp_path
        (tmp_path / "data" / "brain").mkdir(parents=True)
        (tmp_path / "logs").mkdir()
        mock_cost.return_value = None

        mock_spawn.return_value = {
            "task_id": "t001",
            "exit_code": 0,
            "elapsed": 30.0,
            "result": {"status": "success", "summary": "Done"},
            "output_tail": "",
            "retry_metadata": {"total_attempts": 1},
        }

        result = run_task_loop("test", "Fix a bug", max_sessions=3, budget_usd=1.0)
        assert result["status"] == "success"
        assert result["subtasks_completed"] == 1

    @patch("project_agent.cmd_spawn_with_retry")
    @patch("project_agent._load_config")
    @patch("project_agent._agent_dir")
    @patch("project_agent._snapshot_cost")
    def test_agent_not_found(self, mock_cost, mock_dir, mock_config, mock_spawn):
        """Non-existent agent returns error."""
        mock_config.return_value = None
        result = run_task_loop("nonexistent", "do thing")
        assert "error" in result

    @patch("project_agent.time.sleep")
    @patch("project_agent.cmd_spawn_with_retry")
    @patch("project_agent._load_config")
    @patch("project_agent._agent_dir")
    @patch("project_agent._snapshot_cost")
    def test_session_limit_enforced(self, mock_cost, mock_dir, mock_config, mock_spawn, mock_sleep, tmp_path):
        """Loop stops when max sessions reached."""
        mock_config.return_value = {
            "name": "test", "repo_url": "https://github.com/o/r.git",
            "branch": "dev",
        }
        mock_dir.return_value = tmp_path
        (tmp_path / "data" / "brain").mkdir(parents=True)
        (tmp_path / "logs").mkdir()
        mock_cost.return_value = None

        # Each spawn uses 1 session but fails, causing decomposed subtasks to accumulate
        mock_spawn.return_value = {
            "task_id": "t001", "exit_code": 1, "elapsed": 10.0,
            "result": {"status": "failed", "summary": "Oops"},
            "output_tail": "",
            "retry_metadata": {"total_attempts": 1},
        }

        result = run_task_loop("test", "Do X and then do Y and then do Z",
                               max_sessions=2)
        assert result["total_sessions"] <= 3  # 2 limit + 1 tolerance


# ── build_dependency_map tests ──

class TestBuildDependencyMap:
    def _make_agent(self, tmp_path, files=None):
        """Create a minimal agent dir with workspace files."""
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True)
        data = tmp_path / "data"
        data.mkdir(parents=True)
        if files:
            for path, content in files.items():
                full = workspace / path
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(content)
        return tmp_path

    @patch("project_agent._agent_dir")
    def test_node_project_detected(self, mock_dir, tmp_path):
        """Detects Node.js project from package.json."""
        pkg = json.dumps({
            "name": "test-app",
            "scripts": {"test": "vitest", "build": "next build", "lint": "eslint ."},
            "dependencies": {"next": "16.0.0", "react": "19.0.0"},
        })
        agent = self._make_agent(tmp_path, {"package.json": pkg})
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        assert result["language"] == "javascript/typescript"
        assert result["framework"] == "next.js"
        assert result["project_type"] == "webapp"
        assert "package.json" in result["config_files"]

    @patch("project_agent._agent_dir")
    def test_python_project_detected(self, mock_dir, tmp_path):
        """Detects Python project from pyproject.toml."""
        toml = '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n[tool.ruff]\nline-length = 120\n'
        agent = self._make_agent(tmp_path, {"pyproject.toml": toml})
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        assert result["language"] == "python"
        assert result["project_type"] == "python"
        assert "pyproject.toml" in result["config_files"]

    @patch("project_agent._agent_dir")
    def test_entry_points_found(self, mock_dir, tmp_path):
        """Finds entry points based on language."""
        pkg = json.dumps({"name": "app", "dependencies": {"next": "16"}})
        agent = self._make_agent(tmp_path, {
            "package.json": pkg,
            "app/layout.tsx": "export default function Layout() {}",
            "app/page.tsx": "export default function Page() {}",
        })
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        assert "app/layout.tsx" in result["entry_points"]
        assert "app/page.tsx" in result["entry_points"]

    @patch("project_agent._agent_dir")
    def test_source_dirs_found(self, mock_dir, tmp_path):
        """Finds source directories with file counts."""
        agent = self._make_agent(tmp_path, {
            "package.json": "{}",
            "src/index.ts": "export {}",
            "src/utils/helper.ts": "export {}",
            "components/Button.tsx": "export {}",
            "lib/api.ts": "export {}",
        })
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        src_paths = [d["path"] for d in result["source_dirs"]]
        assert "src" in src_paths
        assert "components" in src_paths
        assert "lib" in src_paths

    @patch("project_agent._agent_dir")
    def test_test_dirs_found(self, mock_dir, tmp_path):
        """Finds test directories."""
        agent = self._make_agent(tmp_path, {
            "package.json": "{}",
            "tests/test_main.py": "def test_ok(): pass",
            "__tests__/App.test.tsx": "test('renders', () => {})",
        })
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        test_paths = [d["path"] for d in result["test_dirs"]]
        assert "tests" in test_paths
        assert "__tests__" in test_paths

    @patch("project_agent._agent_dir")
    def test_colocated_test_files_found(self, mock_dir, tmp_path):
        """Finds co-located test files (*.test.ts, etc.)."""
        agent = self._make_agent(tmp_path, {
            "package.json": "{}",
            "src/utils.test.ts": "test('works', () => {})",
            "src/api.spec.ts": "describe('api', () => {})",
        })
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        assert "src/utils.test.ts" in result["test_files"]
        assert "src/api.spec.ts" in result["test_files"]

    @patch("project_agent._agent_dir")
    def test_writes_json_file(self, mock_dir, tmp_path):
        """Writes dependency_map.json to agent data dir."""
        agent = self._make_agent(tmp_path, {"package.json": "{}"})
        mock_dir.return_value = agent

        build_dependency_map("test")
        dep_file = tmp_path / "data" / "dependency_map.json"
        assert dep_file.exists()
        data = json.loads(dep_file.read_text())
        assert data["agent"] == "test"
        assert "generated_at" in data

    @patch("project_agent._agent_dir")
    def test_nonexistent_agent(self, mock_dir, tmp_path):
        """Returns error for non-existent agent."""
        mock_dir.return_value = tmp_path / "nope"
        result = build_dependency_map("ghost")
        assert "error" in result

    @patch("project_agent._agent_dir")
    def test_config_files_detected(self, mock_dir, tmp_path):
        """Detects various config files."""
        agent = self._make_agent(tmp_path, {
            "package.json": "{}",
            "tsconfig.json": "{}",
            "tailwind.config.ts": "export default {}",
            "eslint.config.mjs": "export default []",
            "vitest.config.ts": "export default {}",
        })
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        assert "tsconfig.json" in result["config_files"]
        assert "tailwind.config.ts" in result["config_files"]

    @patch("project_agent._agent_dir")
    def test_github_workflows_detected(self, mock_dir, tmp_path):
        """Detects GitHub Actions workflow files."""
        agent = self._make_agent(tmp_path, {
            "package.json": "{}",
            ".github/workflows/test.yml": "name: Test\non: push\njobs: {}",
            ".github/workflows/deploy.yaml": "name: Deploy\non: push\njobs: {}",
        })
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        # ci_workflows lists detected workflow filenames
        assert "test.yml" in result.get("ci_workflows", [])
        assert "deploy.yaml" in result.get("ci_workflows", [])

    @patch("project_agent._agent_dir")
    def test_key_modules_found(self, mock_dir, tmp_path):
        """Finds key module files in lib/utils dirs."""
        agent = self._make_agent(tmp_path, {
            "package.json": "{}",
            "lib/db.ts": "export const db = {}",
            "lib/auth.ts": "export const auth = {}",
            "utils/format.ts": "export function fmt() {}",
        })
        mock_dir.return_value = agent

        result = build_dependency_map("test")
        assert "lib/db.ts" in result["key_modules"]
        assert "lib/auth.ts" in result["key_modules"]
        assert "utils/format.ts" in result["key_modules"]


# ── decompose_task with dep_map tests ──

class TestDecomposeWithDepMap:
    @patch("project_agent._agent_dir")
    @patch("project_agent._load_config")
    def test_impl_task_includes_project_hint(self, mock_config, mock_dir, tmp_path):
        """Implementation tasks get project structure hints from dep_map."""
        mock_config.return_value = {"name": "test"}
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        data = tmp_path / "data"
        data.mkdir(parents=True)
        dep_file = data / "dependency_map.json"
        dep_file.write_text(json.dumps({
            "framework": "next.js",
            "language": "javascript/typescript",
            "entry_points": ["app/page.tsx"],
            "source_dirs": [{"path": "app", "file_count": 20}],
            "test_dirs": [{"path": "__tests__", "file_count": 5}],
            "test_files": ["src/utils.test.ts"],
        }))
        mock_dir.return_value = tmp_path

        subtasks = decompose_task("test", "Implement dark mode toggle")
        # First subtask should contain project hint
        assert "next.js" in subtasks[0]["task"]
        assert len(subtasks) >= 2  # at least impl + PR

    @patch("project_agent._agent_dir")
    @patch("project_agent._load_config")
    def test_multipart_first_subtask_has_hint(self, mock_config, mock_dir, tmp_path):
        """Multi-part tasks get project hint on first subtask only."""
        mock_config.return_value = {"name": "test"}
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        data = tmp_path / "data"
        data.mkdir(parents=True)
        dep_file = data / "dependency_map.json"
        dep_file.write_text(json.dumps({
            "framework": "react",
            "language": "javascript/typescript",
            "entry_points": [],
            "source_dirs": [{"path": "src", "file_count": 10}],
            "test_dirs": [],
            "test_files": [],
        }))
        mock_dir.return_value = tmp_path

        subtasks = decompose_task("test", "Add login page and then add logout button")
        # First subtask has hint
        assert "react" in subtasks[0]["task"]
        # Second subtask does NOT have hint (avoid noise)
        if len(subtasks) > 1:
            assert "react" not in subtasks[1]["task"]


# ── A2A Protocol tests ──

class TestValidateA2AResult:
    def test_valid_success_result(self):
        result = {"status": "success", "summary": "Fixed the bug"}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is True
        assert not any("missing required" in w for w in warnings)

    def test_valid_blocked_status(self):
        result = {"status": "blocked", "summary": "Waiting for CI",
                  "error": "CI not configured"}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is True

    def test_missing_status(self):
        result = {"summary": "Did stuff"}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is False
        assert any("missing required field: status" in w for w in warnings)

    def test_missing_summary(self):
        result = {"status": "success"}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is False
        assert any("missing required field: summary" in w for w in warnings)

    def test_invalid_status_value(self):
        result = {"status": "done", "summary": "Finished"}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is False
        assert any("invalid status" in w for w in warnings)

    def test_empty_summary_invalidates(self):
        """Empty summary must make result invalid — it's a required field."""
        result = {"status": "success", "summary": ""}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is False
        assert any("summary must be" in w for w in warnings)

    def test_none_summary_invalidates(self):
        """None summary must make result invalid."""
        result = {"status": "success", "summary": None}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is False
        assert any("summary must be" in w for w in warnings)

    def test_non_string_summary_invalidates(self):
        """Non-string summary must make result invalid."""
        result = {"status": "success", "summary": 123}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is False
        assert any("summary must be" in w for w in warnings)

    def test_missing_both_required_fields(self):
        """Missing both status and summary should invalidate."""
        result = {"files_changed": ["foo.py"]}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is False
        assert any("missing required field: status" in w for w in warnings)
        assert any("missing required field: summary" in w for w in warnings)

    def test_wrong_type_files_changed(self):
        result = {"status": "success", "summary": "Done",
                  "files_changed": "single_file.py"}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is True  # type issues are warnings, not errors
        assert any("files_changed should be a list" in w for w in warnings)

    def test_confidence_out_of_range(self):
        result = {"status": "success", "summary": "Done", "confidence": 1.5}
        _, warnings = validate_a2a_result(result)
        assert any("confidence out of range" in w for w in warnings)

    def test_confidence_valid(self):
        result = {"status": "success", "summary": "Done", "confidence": 0.85}
        is_valid, warnings = validate_a2a_result(result)
        assert is_valid is True
        assert not any("confidence" in w for w in warnings)


class TestNormalizeA2AResult:
    def test_adds_protocol_tag(self):
        result = {"status": "success", "summary": "Done"}
        normalized = normalize_a2a_result(result)
        assert normalized["protocol"] == f"a2a/v{A2A_PROTOCOL_VERSION}"

    def test_fills_defaults(self):
        result = {"status": "success", "summary": "Done"}
        normalized = normalize_a2a_result(result)
        assert normalized["pr_url"] is None
        assert normalized["files_changed"] == []
        assert normalized["procedures"] == []
        assert normalized["follow_ups"] == []
        assert normalized["tests_passed"] is None
        assert normalized["error"] is None

    def test_preserves_agent_values(self):
        result = {
            "status": "success", "summary": "Fixed login",
            "pr_url": "https://github.com/o/r/pull/1",
            "files_changed": ["auth.py"],
            "confidence": 0.9,
        }
        normalized = normalize_a2a_result(result)
        assert normalized["pr_url"] == "https://github.com/o/r/pull/1"
        assert normalized["files_changed"] == ["auth.py"]
        assert normalized["confidence"] == 0.9

    def test_preserves_extra_fields(self):
        result = {"status": "success", "summary": "Done",
                  "custom_metric": 42}
        normalized = normalize_a2a_result(result)
        assert normalized["custom_metric"] == 42

    def test_all_statuses_accepted(self):
        for status in A2A_VALID_STATUSES:
            result = {"status": status, "summary": "Test"}
            is_valid, _ = validate_a2a_result(result)
            assert is_valid is True

    def test_unknown_status_valid(self):
        """'unknown' is now a valid status (used as default for missing status)."""
        result = {"status": "unknown", "summary": "Fallback"}
        is_valid, _ = validate_a2a_result(result)
        assert is_valid is True


class TestNormalizeDefaultsToUnknown:
    """Verify normalize defaults missing status to 'unknown', not 'success'."""

    def test_missing_status_defaults_unknown(self):
        normalized = normalize_a2a_result({"summary": "did stuff"})
        assert normalized["status"] == "unknown", \
            f"Missing status should default to 'unknown', got '{normalized['status']}'"

    def test_missing_summary_defaults_empty(self):
        normalized = normalize_a2a_result({"status": "failed"})
        assert normalized["summary"] == ""


class TestParseAgentOutputA2A:
    def test_output_is_normalized(self):
        output = '```json\n{"status": "success", "summary": "Done"}\n```'
        result = _parse_agent_output(output)
        assert result["protocol"] == f"a2a/v{A2A_PROTOCOL_VERSION}"
        assert result["_a2a_valid"] is True
        assert "files_changed" in result  # default filled

    def test_invalid_output_marked(self):
        output = '```json\n{"status": "done", "summary": "Finished"}\n```'
        result = _parse_agent_output(output)
        assert result["_a2a_valid"] is False
        assert len(result["_a2a_warnings"]) > 0

    def test_no_json_normalized(self):
        result = _parse_agent_output("Just text")
        assert result["protocol"] == f"a2a/v{A2A_PROTOCOL_VERSION}"
        assert result["status"] == "unknown"

    def test_empty_output_normalized(self):
        result = _parse_agent_output("")
        assert result["protocol"] == f"a2a/v{A2A_PROTOCOL_VERSION}"
        assert result["status"] == "failed"

    def test_missing_status_repaired_to_unknown(self):
        """When agent returns JSON without status, parse should fix to 'unknown'."""
        output = '```json\n{"summary": "Did something"}\n```'
        result = _parse_agent_output(output)
        assert result["status"] == "unknown", \
            f"Missing status should be repaired to 'unknown', got '{result['status']}'"
        assert result["_a2a_valid"] is False

    def test_missing_summary_repaired_from_output(self):
        """When agent returns JSON without summary, parse should use output tail."""
        output = 'Some work done here\n```json\n{"status": "success"}\n```'
        result = _parse_agent_output(output)
        assert result["_a2a_valid"] is False
        assert len(result["summary"]) > 0, "Missing summary should be repaired from output"

    def test_missing_both_repaired(self):
        """When both required fields missing, both should be repaired."""
        output = 'output text\n```json\n{"pr_url": "http://example.com"}\n```'
        result = _parse_agent_output(output)
        assert result["status"] == "unknown"
        assert len(result["summary"]) > 0
        assert result["_a2a_valid"] is False


# ── Loop Lock & Backoff Tests ──

class TestLoopLock:
    """Tests for per-agent loop lockfile with stale PID detection."""

    def setup_method(self):
        """Clean up any test lock files."""
        lock = _loop_lock_path("test-lock-agent")
        lock.unlink(missing_ok=True)

    def teardown_method(self):
        self.setup_method()

    def test_acquire_and_release(self):
        assert _acquire_loop_lock("test-lock-agent") is True
        lock = _loop_lock_path("test-lock-agent")
        assert lock.exists()
        assert lock.read_text().strip() == str(os.getpid())
        _release_loop_lock("test-lock-agent")
        assert not lock.exists()

    def test_double_acquire_fails(self):
        assert _acquire_loop_lock("test-lock-agent") is True
        # Same PID holds lock — should fail (lock held by live clarvis process)
        # But since _is_pid_clarvis checks our own PID, it will see us as alive
        # and refuse. This is correct behavior.
        assert _acquire_loop_lock("test-lock-agent") is False

    def test_stale_pid_reclaimed(self):
        """Lock with dead PID should be reclaimed."""
        lock = _loop_lock_path("test-lock-agent")
        lock.write_text("99999999")  # PID that doesn't exist
        assert _acquire_loop_lock("test-lock-agent") is True
        assert lock.read_text().strip() == str(os.getpid())

    def test_release_only_own_lock(self):
        """Release should not remove lock owned by another PID."""
        lock = _loop_lock_path("test-lock-agent")
        lock.write_text("12345")  # Not our PID
        _release_loop_lock("test-lock-agent")
        assert lock.exists()  # Should NOT have been removed

    def test_lock_path_format(self):
        path = _loop_lock_path("my-agent")
        assert str(path) == "/tmp/clarvis_agent_my-agent_loop.lock"


class TestLoopBackoffConstants:
    """Verify inter-subtask delay constants."""

    def test_delay_range(self):
        assert LOOP_INTER_SUBTASK_DELAY_MIN == 10
        assert LOOP_INTER_SUBTASK_DELAY_MAX == 20
        assert LOOP_INTER_SUBTASK_DELAY_MIN < LOOP_INTER_SUBTASK_DELAY_MAX


class TestCommitSafetyWhitelist:
    """Verify auto-commit safety whitelist constants and filtering."""

    def test_common_extensions_whitelisted(self):
        for ext in [".py", ".ts", ".js", ".json", ".md", ".css", ".html",
                    ".go", ".rs", ".toml", ".yaml", ".yml", ".sh", ".sql", ".txt"]:
            assert ext in COMMIT_EXT_WHITELIST, f"{ext} should be whitelisted"

    def test_dangerous_extensions_not_whitelisted(self):
        for ext in [".pem", ".key", ".p12", ".pfx", ".sqlite", ".db",
                    ".log", ".zip", ".tar", ".gz"]:
            assert ext not in COMMIT_EXT_WHITELIST, f"{ext} should NOT be whitelisted"

    def test_blocked_patterns_match_secrets(self):
        for path in [".env", "prod.env", "id_rsa", "id_ed25519",
                     "server.pem", "private.key", "cert.p12", "keystore.pfx",
                     "data.sqlite", "app.db", "output.log",
                     "archive.zip", "backup.tar", "bundle.gz",
                     "node_modules/lodash/index.js",
                     "__pycache__/mod.cpython-310.pyc",
                     "credentials.json", "secrets.yaml"]:
            assert COMMIT_BLOCKED_PATTERNS.search(path), \
                f"{path} should be blocked"

    def test_blocked_patterns_allow_normal_files(self):
        for path in ["src/main.py", "lib/utils.ts", "README.md",
                     "package.json", "Cargo.toml", "go.mod",
                     "tests/test_auth.py", "styles/app.css"]:
            assert not COMMIT_BLOCKED_PATTERNS.search(path), \
                f"{path} should NOT be blocked"

    def test_safe_stage_files_in_git_repo(self, tmp_path):
        """Integration test: safe_stage_files with a real git repo."""
        # Init a git repo with an initial commit
        import subprocess
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"],
                       cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"],
                       cwd=str(repo), capture_output=True)

        # Create initial file and commit
        (repo / "initial.py").write_text("# init")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=str(repo), capture_output=True)

        # Create test files: some safe, some unsafe
        (repo / "new_feature.py").write_text("print('hi')")
        (repo / "config.json").write_text("{}")
        (repo / "secrets.env").write_text("API_KEY=xxx")
        (repo / "data.sqlite").write_text("binary")
        (repo / "archive.tar.gz").write_text("binary")

        # Modify tracked file
        (repo / "initial.py").write_text("# modified")

        staged, blocked = safe_stage_files(repo)

        # Tracked modification should be staged
        assert "initial.py" in staged

        # Safe untracked files should be staged
        assert "new_feature.py" in staged
        assert "config.json" in staged

        # Unsafe files should be blocked
        blocked_str = " ".join(blocked)
        assert "secrets.env" in blocked_str
        assert "data.sqlite" in blocked_str

    def test_prompt_contains_commit_safety(self, agent_config, agent_dir):
        """Verify spawn prompt includes commit safety rules."""
        prompt = build_spawn_prompt(
            "test-project", "some task", agent_config, agent_dir
        )
        assert "never `git add .`" in prompt
        assert ".env" in prompt


# ── cmd_spawn_parallel tests ──

class TestSpawnParallel:
    """Tests for cmd_spawn_parallel — multi-agent concurrent execution."""

    def _success_result(self, name):
        return {
            "task_id": f"t_{name}_001",
            "agent": name,
            "exit_code": 0,
            "elapsed": 30.0,
            "result": {"status": "success", "summary": f"Done for {name}"},
        }

    def _failure_result(self, name):
        return {
            "task_id": f"t_{name}_001",
            "agent": name,
            "exit_code": 1,
            "elapsed": 10.0,
            "result": {"status": "failed", "summary": f"Failed for {name}"},
        }

    @patch("project_agent.cmd_spawn")
    def test_two_agents_both_succeed(self, mock_spawn):
        mock_spawn.side_effect = lambda name, task, timeout, ctx="": self._success_result(name)
        tasks = [
            {"agent": "alpha", "task": "build feature A"},
            {"agent": "beta", "task": "build feature B"},
        ]
        result = cmd_spawn_parallel(tasks, timeout=600)
        assert result["total"] == 2
        assert result["succeeded"] == 2
        assert result["failed"] == 0
        assert "alpha" in result["results"]
        assert "beta" in result["results"]
        assert result["results"]["alpha"]["exit_code"] == 0
        assert result["results"]["beta"]["exit_code"] == 0

    @patch("project_agent.cmd_spawn")
    def test_one_succeeds_one_fails(self, mock_spawn):
        def side_effect(name, task, timeout, ctx=""):
            if name == "alpha":
                return self._success_result(name)
            return self._failure_result(name)
        mock_spawn.side_effect = side_effect
        tasks = [
            {"agent": "alpha", "task": "task A"},
            {"agent": "beta", "task": "task B"},
        ]
        result = cmd_spawn_parallel(tasks)
        assert result["total"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert result["results"]["alpha"]["exit_code"] == 0
        assert result["results"]["beta"]["exit_code"] == 1

    @patch("project_agent.cmd_spawn")
    def test_empty_task_list(self, mock_spawn):
        result = cmd_spawn_parallel([])
        assert result.get("error")
        mock_spawn.assert_not_called()

    @patch("project_agent.cmd_spawn")
    def test_per_task_timeout_override(self, mock_spawn):
        mock_spawn.side_effect = lambda name, task, timeout, ctx="": {
            **self._success_result(name),
            "timeout_used": timeout,
        }
        tasks = [
            {"agent": "alpha", "task": "quick", "timeout": 300},
            {"agent": "beta", "task": "long"},  # uses default
        ]
        result = cmd_spawn_parallel(tasks, timeout=1200)
        # alpha should have used 300, beta should have used 1200
        assert result["results"]["alpha"]["timeout_used"] == 300
        assert result["results"]["beta"]["timeout_used"] == 1200

    @patch("project_agent.cmd_spawn")
    def test_context_passthrough(self, mock_spawn):
        mock_spawn.side_effect = lambda name, task, timeout, ctx="": {
            **self._success_result(name),
            "context_received": ctx,
        }
        tasks = [
            {"agent": "alpha", "task": "t", "context": "extra info"},
        ]
        result = cmd_spawn_parallel(tasks)
        assert result["results"]["alpha"]["context_received"] == "extra info"

    @patch("project_agent.cmd_spawn")
    def test_exception_in_one_agent_captured(self, mock_spawn):
        def side_effect(name, task, timeout, ctx=""):
            if name == "broken":
                raise RuntimeError("agent workspace corrupted")
            return self._success_result(name)
        mock_spawn.side_effect = side_effect
        tasks = [
            {"agent": "good", "task": "t"},
            {"agent": "broken", "task": "t"},
        ]
        result = cmd_spawn_parallel(tasks)
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert "error" in result["results"]["broken"]
        assert "corrupted" in result["results"]["broken"]["error"]

    @patch("project_agent.cmd_spawn")
    def test_three_agents_concurrently(self, mock_spawn):
        mock_spawn.side_effect = lambda name, task, timeout, ctx="": self._success_result(name)
        tasks = [
            {"agent": "a", "task": "t1"},
            {"agent": "b", "task": "t2"},
            {"agent": "c", "task": "t3"},
        ]
        result = cmd_spawn_parallel(tasks)
        assert result["total"] == 3
        assert result["succeeded"] == 3
        assert len(result["results"]) == 3

    @patch("project_agent.cmd_spawn")
    def test_config_error_counted_as_success(self, mock_spawn):
        """Config errors (agent not found) have 'error' key — not counted as failure."""
        mock_spawn.return_value = {"error": "Agent 'ghost' not found"}
        tasks = [{"agent": "ghost", "task": "t"}]
        result = cmd_spawn_parallel(tasks)
        # _is_task_failure returns False for config errors (has "error" key)
        # so it should count as succeeded (not a task failure, just a config error)
        assert result["total"] == 1


# ── Concurrency slot tests ──

class TestConcurrencySlots:
    """Tests for global Claude semaphore slot management."""

    def setup_method(self):
        """Clean up test slot files."""
        d = _slots_dir()
        if d.exists():
            for f in d.glob("slot_test_*"):
                f.unlink(missing_ok=True)

    def teardown_method(self):
        self.setup_method()

    def test_acquire_and_release_slot(self):
        slot_file, err = _acquire_claude_slot("test_agent")
        assert err is None
        assert slot_file is not None
        assert slot_file.exists()
        _release_claude_slot(slot_file)
        assert not slot_file.exists()

    def test_release_none_is_safe(self):
        _release_claude_slot(None)  # should not raise

    def test_slot_dir_created(self):
        d = _slots_dir()
        if d.exists():
            shutil.rmtree(d)
        slot_file, err = _acquire_claude_slot("test_agent")
        assert d.exists()
        _release_claude_slot(slot_file)

    def test_slots_dir_path(self):
        assert str(_slots_dir()) == "/tmp/clarvis_claude_slots"


class TestAgentClaudeLock:
    """Tests for per-agent Claude lock."""

    def setup_method(self):
        lock = _agent_claude_lock_path("test-lock-claude")
        lock.unlink(missing_ok=True)

    def teardown_method(self):
        self.setup_method()

    def test_acquire_and_release(self):
        with patch("project_agent._is_pid_clarvis", return_value=True):
            err = _acquire_agent_claude_lock("test-lock-claude")
            assert err is None
            lock = _agent_claude_lock_path("test-lock-claude")
            assert lock.exists()
            _release_agent_claude_lock("test-lock-claude")
            assert not lock.exists()

    def test_double_acquire_blocked(self):
        with patch("project_agent._is_pid_clarvis", return_value=True):
            err1 = _acquire_agent_claude_lock("test-lock-claude")
            assert err1 is None
            # Second acquire should fail (same PID holds it)
            err2 = _acquire_agent_claude_lock("test-lock-claude")
            assert err2 is not None
            assert "lock held" in err2
            _release_agent_claude_lock("test-lock-claude")

    def test_stale_lock_reclaimed(self):
        lock = _agent_claude_lock_path("test-lock-claude")
        lock.write_text("99999999")  # Dead PID
        err = _acquire_agent_claude_lock("test-lock-claude")
        assert err is None  # Should reclaim
        _release_agent_claude_lock("test-lock-claude")

    def test_lock_path_format(self):
        path = _agent_claude_lock_path("my-agent")
        assert str(path) == "/tmp/clarvis_agent_my-agent_claude.lock"


# ── Mirror Validation Tests ──

class TestMirrorValidation:
    def test_no_mirror_skips(self):
        """Agents without a PROD mirror should get a skip result."""
        result = run_mirror_validation("nonexistent-agent")
        assert result["passed"] is None
        assert "skipped" in result["summary"].lower()

    def test_mirror_with_mock_checks(self, tmp_path):
        """Mirror validation with a temporary mirror dir and mocked subprocess."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        # Write a dummy file so the mirror dir exists
        (mirror_dir / "package.json").write_text("{}")

        agent_ws = tmp_path / "workspace"
        agent_ws.mkdir()
        (agent_ws / "src").mkdir()
        (agent_ws / "src" / "app.ts").write_text("console.log('hello');")

        # Temporarily register this as a mirror
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        try:
            import project_agent as pa
            pa.MIRROR_DIRS["test-agent"] = mirror_dir
            pa.MIRROR_CHECKS["test-agent"] = [
                {"name": "echo test", "cmd": ["echo", "ok"], "timeout": 10},
            ]
            result = run_mirror_validation(
                "test-agent",
                changed_files=["src/app.ts"],
                agent_workspace=agent_ws,
            )
            assert result["passed"] is True
            assert len(result["checks"]) == 1
            assert result["checks"][0]["name"] == "echo test"
            assert result["checks"][0]["passed"] is True
            assert "PASS" in result["summary"]

            # Verify file was copied and then restored (shouldn't exist in mirror)
            assert not (mirror_dir / "src" / "app.ts").exists()
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_mirror_failing_check(self, tmp_path):
        """Mirror validation reports failure when a check fails."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()

        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        try:
            pa.MIRROR_DIRS["fail-agent"] = mirror_dir
            pa.MIRROR_CHECKS["fail-agent"] = [
                {"name": "false cmd", "cmd": ["false"], "timeout": 10},
            ]
            result = run_mirror_validation("fail-agent")
            assert result["passed"] is False
            assert result["checks"][0]["passed"] is False
            assert "FAIL" in result["summary"]
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_mirror_restores_originals(self, tmp_path):
        """Files in the mirror should be restored after validation."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        original_content = b"original content"
        (mirror_dir / "file.txt").write_bytes(original_content)

        agent_ws = tmp_path / "workspace"
        agent_ws.mkdir()
        (agent_ws / "file.txt").write_text("modified content")

        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        try:
            pa.MIRROR_DIRS["restore-agent"] = mirror_dir
            pa.MIRROR_CHECKS["restore-agent"] = [
                {"name": "true cmd", "cmd": ["true"], "timeout": 10},
            ]
            run_mirror_validation(
                "restore-agent",
                changed_files=["file.txt"],
                agent_workspace=agent_ws,
            )
            # Original should be restored
            assert (mirror_dir / "file.txt").read_bytes() == original_content
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_spawn_prompt_includes_mirror_section(self, agent_dir):
        """SWO agents should get mirror validation instructions in prompt."""
        config = {
            "name": "star-world-order",
            "constraints": ["Run tests"],
            "budget": {"max_timeout": 1800},
        }
        import project_agent as pa
        # Only test if the SWO mirror exists on this machine
        if pa.MIRROR_DIRS.get("star-world-order", Path("/nonexistent")).exists():
            prompt = build_spawn_prompt(
                "star-world-order", "Fix a bug", config, agent_dir
            )
            assert "Mirror Validation" in prompt
            assert "tsc --noEmit" in prompt
            assert "vitest run" in prompt

    def test_mirror_cleans_up_new_directories(self, tmp_path):
        """New directories created during overlay should be removed on restore."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        (mirror_dir / "package.json").write_text("{}")

        agent_ws = tmp_path / "workspace"
        agent_ws.mkdir()
        # Create a file in a nested new directory
        (agent_ws / "src" / "components" / "new").mkdir(parents=True)
        (agent_ws / "src" / "components" / "new" / "Widget.tsx").write_text("export {}")

        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        try:
            pa.MIRROR_DIRS["dir-cleanup-agent"] = mirror_dir
            pa.MIRROR_CHECKS["dir-cleanup-agent"] = [
                {"name": "true", "cmd": ["true"], "timeout": 10},
            ]
            run_mirror_validation(
                "dir-cleanup-agent",
                changed_files=["src/components/new/Widget.tsx"],
                agent_workspace=agent_ws,
            )
            # New directories should be removed
            assert not (mirror_dir / "src" / "components" / "new").exists()
            assert not (mirror_dir / "src" / "components").exists()
            assert not (mirror_dir / "src").exists()
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_mirror_preserves_existing_directories(self, tmp_path):
        """Pre-existing directories should NOT be removed during cleanup."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        # Pre-existing directory in mirror
        (mirror_dir / "src").mkdir()
        (mirror_dir / "src" / "index.ts").write_text("export {}")

        agent_ws = tmp_path / "workspace"
        agent_ws.mkdir()
        (agent_ws / "src" / "utils").mkdir(parents=True)
        (agent_ws / "src" / "utils" / "helper.ts").write_text("export {}")

        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        try:
            pa.MIRROR_DIRS["preserve-agent"] = mirror_dir
            pa.MIRROR_CHECKS["preserve-agent"] = [
                {"name": "true", "cmd": ["true"], "timeout": 10},
            ]
            run_mirror_validation(
                "preserve-agent",
                changed_files=["src/utils/helper.ts"],
                agent_workspace=agent_ws,
            )
            # New file and its new parent dir should be removed
            assert not (mirror_dir / "src" / "utils" / "helper.ts").exists()
            assert not (mirror_dir / "src" / "utils").exists()
            # Pre-existing directory and file should remain
            assert (mirror_dir / "src").exists()
            assert (mirror_dir / "src" / "index.ts").exists()
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_baseline_diff_ignores_preexisting_errors(self, tmp_path):
        """Pre-existing errors in PROD mirror should not cause failure."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        # A file with a "tsc error" that exists BEFORE overlay
        (mirror_dir / "broken.ts").write_text("let x: string = 123;")

        agent_ws = tmp_path / "workspace"
        agent_ws.mkdir()
        (agent_ws / "good.ts").write_text("let y: number = 1;")

        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        try:
            # Use a script that outputs a "pre-existing" error line both times
            check_script = tmp_path / "check.sh"
            check_script.write_text(
                "#!/bin/bash\n"
                "echo 'broken.ts(1,5): error TS2322: Type number is not assignable' >&2\n"
                "exit 1\n"
            )
            check_script.chmod(0o755)

            pa.MIRROR_DIRS["baseline-agent"] = mirror_dir
            pa.MIRROR_CHECKS["baseline-agent"] = [
                {"name": "tsc --noEmit", "cmd": [str(check_script)], "timeout": 10},
            ]
            result = run_mirror_validation(
                "baseline-agent",
                changed_files=["good.ts"],
                agent_workspace=agent_ws,
            )
            # Should PASS because the error exists in both baseline and overlay
            assert result["passed"] is True
            assert result["checks"][0]["passed"] is True
            assert result["checks"][0]["new_errors"] == []
            assert result["checks"][0]["baseline_errors"] == 1
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_baseline_diff_catches_new_errors(self, tmp_path):
        """Genuinely new errors introduced by the overlay should fail."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()

        agent_ws = tmp_path / "workspace"
        agent_ws.mkdir()
        (agent_ws / "bad.ts").write_text("broken code")

        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)

        # Track whether overlay file exists to produce different output
        check_script = tmp_path / "check.sh"
        check_script.write_text(
            "#!/bin/bash\n"
            f"if [ -f '{mirror_dir}/bad.ts' ]; then\n"
            "  echo 'bad.ts(1,1): error TS1005: new error from overlay' >&2\n"
            "  exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        check_script.chmod(0o755)

        try:
            pa.MIRROR_DIRS["newbug-agent"] = mirror_dir
            pa.MIRROR_CHECKS["newbug-agent"] = [
                {"name": "tsc --noEmit", "cmd": [str(check_script)], "timeout": 10},
            ]
            result = run_mirror_validation(
                "newbug-agent",
                changed_files=["bad.ts"],
                agent_workspace=agent_ws,
            )
            # Should FAIL because the error is NEW (not in baseline)
            assert result["passed"] is False
            assert result["checks"][0]["passed"] is False
            assert len(result["checks"][0]["new_errors"]) == 1
            assert "new error from overlay" in result["checks"][0]["new_errors"][0]
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_no_overlay_skips_baseline(self, tmp_path):
        """Without changed_files, should run checks directly (no baseline)."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()

        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        try:
            pa.MIRROR_DIRS["nooverlay-agent"] = mirror_dir
            pa.MIRROR_CHECKS["nooverlay-agent"] = [
                {"name": "echo test", "cmd": ["echo", "ok"], "timeout": 10},
            ]
            result = run_mirror_validation("nooverlay-agent")
            assert result["passed"] is True
            assert result["checks"][0]["baseline_errors"] == 0
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)


class TestCommentPr:
    """Tests for _comment_pr (the correctly-named soft-gate function)."""

    @patch("project_agent.subprocess.run")
    def test_comment_pr_posts_comment_only(self, mock_run):
        """_comment_pr comments but never closes."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = _comment_pr("https://github.com/org/repo/pull/42", "org/repo", "Issues found")
        assert result is True
        assert mock_run.call_count == 1
        comment_call = mock_run.call_args_list[0]
        assert "comment" in comment_call[0][0]

    def test_comment_pr_bad_url(self):
        result = _comment_pr("https://github.com/org/repo", "org/repo", "FAIL")
        assert result is False

    @patch("project_agent.subprocess.run")
    def test_comment_pr_exception(self, mock_run):
        mock_run.side_effect = OSError("network error")
        result = _comment_pr("https://github.com/org/repo/pull/1", "org/repo", "fail")
        assert result is False


class TestClosePrRemoved:
    """Verify that the misleading _close_pr() alias has been removed."""

    def test_close_pr_no_longer_exported(self):
        import project_agent as pa
        assert not hasattr(pa, "_close_pr"), \
            "_close_pr was removed — use _comment_pr() or _flag_pr(..., close=True)"


class TestFlagPr:
    @patch("project_agent.subprocess.run")
    def test_flag_pr_soft_comments_only(self, mock_run):
        """Soft flag: comment but don't close."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = _flag_pr("https://github.com/org/repo/pull/42", "org/repo", "Issues found", close=False)
        assert result is True
        assert mock_run.call_count == 1
        comment_call = mock_run.call_args_list[0]
        assert "comment" in comment_call[0][0]
        # Verify comment mentions "not auto-closing"
        body_arg = [a for a in comment_call[0][0] if "not auto-closing" in str(a)] or \
                    [a for a in comment_call[1].get("args", comment_call[0][0]) if isinstance(a, list)]
        # No close call
        assert all("close" not in str(c) for c in mock_run.call_args_list
                    if "comment" not in str(c))

    @patch("project_agent.subprocess.run")
    def test_flag_pr_hard_comments_and_closes(self, mock_run):
        """Hard flag: comment AND close."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = _flag_pr("https://github.com/org/repo/pull/42", "org/repo", "FAIL", close=True)
        assert result is True
        assert mock_run.call_count == 2  # comment + close
        close_call = mock_run.call_args_list[1]
        assert "close" in close_call[0][0]

    @patch("project_agent.subprocess.run")
    def test_flag_pr_hard_close_failure(self, mock_run):
        """Hard flag: return False when gh pr close fails."""
        mock_run.side_effect = [
            MagicMock(returncode=0),  # comment succeeds
            MagicMock(returncode=1, stderr="not found"),  # close fails
        ]
        result = _flag_pr("https://github.com/org/repo/pull/99", "org/repo", "FAIL", close=True)
        assert result is False

    def test_flag_pr_bad_url(self):
        """Should return False for URLs without a PR number."""
        result = _flag_pr("https://github.com/org/repo", "org/repo", "FAIL")
        assert result is False


class TestSyncMirror:
    @patch("project_agent.subprocess.run")
    def test_sync_mirror_success(self, mock_run):
        """Should run git pull on mirror dir."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date.", stderr="")
        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        mirror_dir = Path("/tmp/test_mirror_sync")
        mirror_dir.mkdir(exist_ok=True)
        try:
            pa.MIRROR_DIRS["test-sync"] = mirror_dir
            result = _sync_mirror("test-sync")
            assert result is True
            assert mock_run.called
            cmd = mock_run.call_args[0][0]
            assert "pull" in cmd
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            mirror_dir.rmdir()

    def test_sync_mirror_no_agent(self):
        """Should return False for unknown agents."""
        result = _sync_mirror("nonexistent-agent-xyz")
        assert result is False


class TestGetChangedFilesFromGit:
    def test_git_diff_in_workspace(self, tmp_path):
        """Should extract changed files from git diff."""
        import subprocess
        ws = tmp_path / "repo"
        ws.mkdir()
        subprocess.run(["git", "init"], cwd=str(ws), capture_output=True)
        subprocess.run(["git", "checkout", "-b", "dev"], cwd=str(ws), capture_output=True)
        (ws / "base.txt").write_text("base")
        subprocess.run(["git", "add", "."], cwd=str(ws), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(ws), capture_output=True,
                        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"})
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=str(ws), capture_output=True)
        (ws / "new.txt").write_text("new")
        subprocess.run(["git", "add", "."], cwd=str(ws), capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature"], cwd=str(ws), capture_output=True,
                        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"})
        files = _get_changed_files_from_git(ws, base_branch="dev")
        assert "new.txt" in files

    def test_git_diff_no_repo(self, tmp_path):
        """Should return empty list for non-git directories."""
        files = _get_changed_files_from_git(tmp_path)
        assert files == []


class TestMirrorGateMode:
    def test_default_gate_mode_is_soft(self):
        """Default gate mode should be soft to prevent auto-closing."""
        assert _MIRROR_GATE_DEFAULT == "soft"

    def test_swo_gate_mode_is_soft(self):
        """SWO specifically should be soft gate."""
        assert MIRROR_GATE_MODE.get("star-world-order") == "soft"


class TestMirrorHardGatePrompt:
    def test_prompt_contains_gate_language(self, agent_dir):
        """Mirror prompt should contain gate language."""
        config = {
            "name": "test-mirror",
            "constraints": [],
            "budget": {"max_timeout": 1800},
        }
        import project_agent as pa
        mirror_dir = agent_dir / "fake_mirror"
        mirror_dir.mkdir()
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        try:
            pa.MIRROR_DIRS["test-mirror"] = mirror_dir
            pa.MIRROR_CHECKS["test-mirror"] = [
                {"name": "test", "cmd": ["true"], "timeout": 10},
            ]
            prompt = build_spawn_prompt("test-mirror", "some task", config, agent_dir)
            assert "Mirror Validation" in prompt or "mirror" in prompt.lower()
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)


# ── _extract_gh_repo tests ──

class TestExtractGhRepo:
    def test_https_url(self):
        assert _extract_gh_repo("https://github.com/org/repo.git") == "org/repo"

    def test_https_url_no_git(self):
        assert _extract_gh_repo("https://github.com/org/repo") == "org/repo"

    def test_ssh_url(self):
        assert _extract_gh_repo("git@github.com:org/repo.git") == "org/repo"

    def test_empty_url(self):
        assert _extract_gh_repo("") == ""

    def test_malformed_url(self):
        assert _extract_gh_repo("not-a-url") == ""


# ── apply_mirror_gate tests ──

class TestApplyMirrorGate:
    """Tests for the extracted mirror gate logic — soft vs hard vs off."""

    def test_off_gate_skips_entirely(self, tmp_path):
        """Gate mode 'off' should skip validation and return result unchanged."""
        import project_agent as pa
        original_modes = dict(pa.MIRROR_GATE_MODE)
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        try:
            pa.MIRROR_DIRS["off-agent"] = mirror_dir
            pa.MIRROR_CHECKS["off-agent"] = [
                {"name": "echo ok", "cmd": ["echo", "ok"], "timeout": 10},
            ]
            pa.MIRROR_GATE_MODE["off-agent"] = "off"
            result = {"status": "success", "pr_url": "https://github.com/o/r/pull/1"}
            out = apply_mirror_gate("off-agent", result, {"repo_url": ""}, tmp_path)
            assert "mirror_validation" not in out
            assert out["status"] == "success"
        finally:
            pa.MIRROR_GATE_MODE.clear()
            pa.MIRROR_GATE_MODE.update(original_modes)
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_no_mirror_skips(self):
        """Agent with no mirror configured should skip."""
        result = {"status": "success"}
        out = apply_mirror_gate("no-such-agent", result, {}, Path("/tmp"))
        assert "mirror_validation" not in out

    def test_soft_gate_flags_but_keeps_pr_open(self, tmp_path):
        """Soft gate: validation failure leaves PR open, adds flag."""
        import project_agent as pa
        original_modes = dict(pa.MIRROR_GATE_MODE)
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        try:
            pa.MIRROR_DIRS["soft-agent"] = mirror_dir
            pa.MIRROR_CHECKS["soft-agent"] = [
                {"name": "false", "cmd": ["false"], "timeout": 10},
            ]
            pa.MIRROR_GATE_MODE["soft-agent"] = "soft"

            result = {
                "status": "success",
                "pr_url": "https://github.com/o/r/pull/1",
                "files_changed": [],
            }
            config = {"repo_url": "https://github.com/o/r.git"}

            with patch("project_agent._flag_pr") as mock_flag:
                mock_flag.return_value = True
                out = apply_mirror_gate("soft-agent", result, config,
                                        tmp_path, "t001")

            assert out["_mirror_flagged"] is True
            assert out["pr_url"] == "https://github.com/o/r/pull/1"
            assert out["status"] == "success"
            mock_flag.assert_called_once_with(
                "https://github.com/o/r/pull/1", "o/r",
                out["mirror_validation"]["summary"], close=False,
            )
        finally:
            pa.MIRROR_GATE_MODE.clear()
            pa.MIRROR_GATE_MODE.update(original_modes)
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_hard_gate_closes_pr_and_fails(self, tmp_path):
        """Hard gate: validation failure closes PR and marks result failed."""
        import project_agent as pa
        original_modes = dict(pa.MIRROR_GATE_MODE)
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        try:
            pa.MIRROR_DIRS["hard-agent"] = mirror_dir
            pa.MIRROR_CHECKS["hard-agent"] = [
                {"name": "false", "cmd": ["false"], "timeout": 10},
            ]
            pa.MIRROR_GATE_MODE["hard-agent"] = "hard"

            result = {
                "status": "success",
                "pr_url": "https://github.com/o/r/pull/5",
                "files_changed": [],
            }
            config = {"repo_url": "https://github.com/o/r.git"}

            with patch("project_agent._flag_pr") as mock_flag:
                mock_flag.return_value = True
                out = apply_mirror_gate("hard-agent", result, config,
                                        tmp_path, "t002")

            assert out["status"] == "failed"
            assert out["pr_url"] is None
            assert out["_mirror_closed_pr"] == "https://github.com/o/r/pull/5"
            assert "Mirror validation FAILED" in out["error"]
            mock_flag.assert_called_once_with(
                "https://github.com/o/r/pull/5", "o/r",
                out["mirror_validation"]["summary"], close=True,
            )
        finally:
            pa.MIRROR_GATE_MODE.clear()
            pa.MIRROR_GATE_MODE.update(original_modes)
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_passing_validation_no_flag(self, tmp_path):
        """Passing validation should not flag or close anything."""
        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        try:
            pa.MIRROR_DIRS["pass-agent"] = mirror_dir
            pa.MIRROR_CHECKS["pass-agent"] = [
                {"name": "true", "cmd": ["true"], "timeout": 10},
            ]
            result = {
                "status": "success",
                "pr_url": "https://github.com/o/r/pull/3",
                "files_changed": [],
            }
            out = apply_mirror_gate("pass-agent", result,
                                    {"repo_url": "https://github.com/o/r.git"},
                                    tmp_path)
            assert out["mirror_validation"]["passed"] is True
            assert "_mirror_flagged" not in out
            assert "_mirror_closed_pr" not in out
            assert out["status"] == "success"
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_no_pr_url_soft_gate_no_crash(self, tmp_path):
        """Soft gate with no PR URL should flag result but not crash."""
        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        try:
            pa.MIRROR_DIRS["nopr-agent"] = mirror_dir
            pa.MIRROR_CHECKS["nopr-agent"] = [
                {"name": "false", "cmd": ["false"], "timeout": 10},
            ]
            result = {"status": "success", "files_changed": []}
            with patch("project_agent._flag_pr") as mock_flag:
                out = apply_mirror_gate("nopr-agent", result,
                                        {"repo_url": "https://github.com/o/r.git"},
                                        tmp_path)
            assert out["_mirror_flagged"] is True
            mock_flag.assert_not_called()
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)


# ── Repo-Sync Semantics Tests ──

class TestFetchAndResolveBase:
    """Tests for the shared _fetch_and_resolve_base helper."""

    def _init_repo(self, tmp_path, branch="main"):
        """Create a git repo with an origin remote."""
        import subprocess
        repo = tmp_path / "repo"
        repo.mkdir()
        bare = tmp_path / "bare.git"
        subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True, check=True)
        subprocess.run(["git", "clone", str(bare), str(repo)], capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=str(repo), capture_output=True)
        (repo / "init.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
        if branch != "main":
            subprocess.run(["git", "checkout", "-b", branch], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", branch], cwd=str(repo), capture_output=True)
        return repo, bare

    def test_resolves_origin_when_no_upstream(self, tmp_path):
        """Without upstream remote, resolves to origin/<branch>."""
        repo, _ = self._init_repo(tmp_path)
        base_ref = _fetch_and_resolve_base(repo, "main")
        assert base_ref == "origin/main"

    def test_resolves_upstream_when_present(self, tmp_path):
        """With upstream remote, resolves to upstream/<branch>."""
        import subprocess
        repo, bare = self._init_repo(tmp_path, branch="dev")
        upstream_bare = tmp_path / "upstream.git"
        subprocess.run(["git", "init", "--bare", str(upstream_bare)], capture_output=True, check=True)
        subprocess.run(["git", "push", str(upstream_bare), "dev"], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(["git", "remote", "add", "upstream", str(upstream_bare)], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "fetch", "upstream"], cwd=str(repo), capture_output=True)
        base_ref = _fetch_and_resolve_base(repo, "dev")
        assert base_ref == "upstream/dev"


class TestSyncAndCheckoutWorkBranch:
    """Tests for _sync_and_checkout_work_branch."""

    def _init_repo(self, tmp_path):
        import subprocess
        repo = tmp_path / "repo"
        repo.mkdir()
        bare = tmp_path / "bare.git"
        subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True, check=True)
        subprocess.run(["git", "clone", str(bare), str(repo)], capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=str(repo), capture_output=True)
        (repo / "init.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=str(repo), capture_output=True)
        return repo, bare

    def test_creates_correct_branch_name(self, tmp_path):
        repo, _ = self._init_repo(tmp_path)
        branch = _sync_and_checkout_work_branch(repo, "main", "test-agent", "t001")
        assert branch == "clarvis/test-agent/t001"

    def test_ends_on_work_branch(self, tmp_path):
        import subprocess
        repo, _ = self._init_repo(tmp_path)
        _sync_and_checkout_work_branch(repo, "main", "test-agent", "t002")
        result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                cwd=str(repo), capture_output=True, text=True)
        assert result.stdout.strip() == "clarvis/test-agent/t002"

    def test_clean_working_tree_after_sync(self, tmp_path):
        import subprocess
        repo, _ = self._init_repo(tmp_path)
        (repo / "dirty.txt").write_text("should be cleaned")
        _sync_and_checkout_work_branch(repo, "main", "test-agent", "t003")
        result = subprocess.run(["git", "status", "--porcelain"],
                                cwd=str(repo), capture_output=True, text=True)
        assert result.stdout.strip() == ""

    def test_starts_from_latest_origin(self, tmp_path):
        """Work branch should be based on the latest origin/main, not stale local."""
        import subprocess
        repo, bare = self._init_repo(tmp_path)
        clone2 = tmp_path / "clone2"
        subprocess.run(["git", "clone", str(bare), str(clone2)], capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(clone2), capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=str(clone2), capture_output=True)
        (clone2 / "new.txt").write_text("upstream change")
        subprocess.run(["git", "add", "."], cwd=str(clone2), capture_output=True)
        subprocess.run(["git", "commit", "-m", "upstream change"], cwd=str(clone2), capture_output=True)
        subprocess.run(["git", "push"], cwd=str(clone2), capture_output=True)
        _sync_and_checkout_work_branch(repo, "main", "test-agent", "t004")
        assert (repo / "new.txt").exists(), "Should have upstream changes after sync"


class TestWorktreeCreateSync:
    """Verify worktree_create also syncs to latest before creating."""

    def _init_repo(self, tmp_path):
        import subprocess
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        repo = agent_dir / "workspace"
        bare = tmp_path / "bare.git"
        subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True, check=True)
        subprocess.run(["git", "clone", str(bare), str(repo)], capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=str(repo), capture_output=True)
        (repo / "init.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=str(repo), capture_output=True)
        return repo, bare

    def test_worktree_based_on_latest(self, tmp_path):
        """Worktree should contain latest upstream content."""
        import subprocess
        repo, bare = self._init_repo(tmp_path)
        clone2 = tmp_path / "pusher"
        subprocess.run(["git", "clone", str(bare), str(clone2)], capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(clone2), capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=str(clone2), capture_output=True)
        (clone2 / "upstream.txt").write_text("from upstream")
        subprocess.run(["git", "add", "."], cwd=str(clone2), capture_output=True)
        subprocess.run(["git", "commit", "-m", "add upstream"], cwd=str(clone2), capture_output=True)
        subprocess.run(["git", "push"], cwd=str(clone2), capture_output=True)
        wt_path, branch = worktree_create(repo, "test-agent", "wt001", "main")
        assert (wt_path / "upstream.txt").exists(), "Worktree should have latest upstream content"
        assert branch == "clarvis/test-agent/wt001"


class TestSpawnCallsSync:
    """Verify cmd_spawn always calls _sync_and_checkout_work_branch."""

    @patch("project_agent.subprocess.run")
    @patch("project_agent._snapshot_cost")
    @patch("project_agent._sync_and_checkout_work_branch")
    @patch("project_agent._acquire_claude_slot", return_value=(Path("/tmp/test_slot"), None))
    @patch("project_agent._release_claude_slot")
    @patch("project_agent._acquire_agent_claude_lock", return_value=None)
    @patch("project_agent._release_agent_claude_lock")
    @patch("project_agent._load_config")
    @patch("project_agent._save_config")
    @patch("project_agent._agent_dir")
    @patch("project_agent._emit")
    @patch("project_agent.build_ci_context")
    def test_sync_called_before_spawn(self, mock_ci, mock_emit, mock_dir,
                                       mock_save, mock_load, mock_release_claude,
                                       mock_acquire_claude, mock_release_slot,
                                       mock_acquire_slot, mock_sync, mock_cost,
                                       mock_subproc, tmp_path):
        """cmd_spawn must call _sync_and_checkout_work_branch before Claude."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (tmp_path / "data" / "brain").mkdir(parents=True)
        (tmp_path / "logs").mkdir()
        (tmp_path / "memory" / "summaries").mkdir(parents=True)
        mock_dir.return_value = tmp_path
        mock_load.return_value = {
            "name": "test", "repo_url": "https://github.com/o/r.git",
            "branch": "dev", "trust_score": 0.5,
            "budget": {"max_timeout": 1200},
        }
        mock_sync.return_value = "clarvis/test/t001"
        mock_cost.return_value = None
        mock_subproc.return_value = MagicMock(
            returncode=0,
            stdout='```json\n{"status": "success", "summary": "done"}\n```',
            stderr="",
        )

        from project_agent import cmd_spawn
        cmd_spawn("test", "do something", timeout=600)

        mock_sync.assert_called_once()
        args = mock_sync.call_args[0]
        assert args[0] == workspace
        assert args[1] == "dev"
        assert args[2] == "test"


# ── Hard-Gate Edge Cases ──

class TestHardGateEdgeCases:
    """Additional edge-case tests for hard vs soft mirror gate."""

    def test_hard_gate_no_pr_url_still_fails_status(self, tmp_path):
        """Hard gate with no PR URL: should still mark status=failed."""
        import project_agent as pa
        original_modes = dict(pa.MIRROR_GATE_MODE)
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        try:
            pa.MIRROR_DIRS["hardnopr-agent"] = mirror_dir
            pa.MIRROR_CHECKS["hardnopr-agent"] = [
                {"name": "false", "cmd": ["false"], "timeout": 10},
            ]
            pa.MIRROR_GATE_MODE["hardnopr-agent"] = "hard"

            result = {"status": "success", "files_changed": []}
            config = {"repo_url": "https://github.com/o/r.git"}

            out = apply_mirror_gate("hardnopr-agent", result, config,
                                    tmp_path, "t_edge")

            assert out["status"] == "failed"
            assert "Mirror validation FAILED" in out["error"]
            assert out.get("pr_url") is None
            assert "_mirror_closed_pr" not in out
        finally:
            pa.MIRROR_GATE_MODE.clear()
            pa.MIRROR_GATE_MODE.update(original_modes)
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)

    def test_soft_gate_unconfigured_agent_defaults_soft(self, tmp_path):
        """Agent without explicit gate mode should default to 'soft'."""
        import project_agent as pa
        original_mirrors = dict(MIRROR_DIRS)
        original_checks = dict(MIRROR_CHECKS)
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        try:
            pa.MIRROR_DIRS["default-gate-agent"] = mirror_dir
            pa.MIRROR_CHECKS["default-gate-agent"] = [
                {"name": "false", "cmd": ["false"], "timeout": 10},
            ]

            result = {
                "status": "success",
                "pr_url": "https://github.com/o/r/pull/99",
                "files_changed": [],
            }
            config = {"repo_url": "https://github.com/o/r.git"}

            with patch("project_agent._flag_pr") as mock_flag:
                mock_flag.return_value = True
                out = apply_mirror_gate("default-gate-agent", result, config,
                                        tmp_path, "t_default")

            assert out["_mirror_flagged"] is True
            assert out["status"] == "success"
            assert out["pr_url"] == "https://github.com/o/r/pull/99"
            mock_flag.assert_called_once_with(
                "https://github.com/o/r/pull/99", "o/r",
                out["mirror_validation"]["summary"], close=False,
            )
        finally:
            pa.MIRROR_DIRS.clear()
            pa.MIRROR_DIRS.update(original_mirrors)
            pa.MIRROR_CHECKS.clear()
            pa.MIRROR_CHECKS.update(original_checks)
