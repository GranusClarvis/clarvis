"""
Tests for PR Factory Phase 3 — Execution Brief Compiler + Writeback.

Run: python3 -m pytest scripts/tests/test_pr_factory.py -v
"""
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "scripts"))
import _paths  # noqa: F401,E402

from pr_factory import (
    classify_task,
    build_execution_brief,
    build_factory_context,
    format_brief_for_prompt,
    run_writeback,
    _build_episode_summary,
    _find_relevant_files,
    _infer_success_criteria,
    _get_non_negotiables,
    _extract_validations,
    BRIEF_TOKEN_CAP,
)


# ── Fixtures ──

@pytest.fixture
def agent_dir(tmp_path):
    """Create a minimal agent directory structure."""
    ad = tmp_path / "agent"
    ad.mkdir()
    (ad / "data").mkdir()
    (ad / "data" / "brain").mkdir()
    (ad / "data" / "artifacts").mkdir()
    (ad / "data" / "indexes").mkdir()
    (ad / "memory").mkdir()
    (ad / "logs").mkdir()
    return ad


@pytest.fixture
def mock_litebrain():
    """Patch pr_factory._lite_brain_mod so LiteBrain() returns our mock."""
    mock_lb_instance = MagicMock()
    mock_lb_instance.recall.return_value = []
    mock_lb_instance.store.return_value = "lb-abc123"

    mock_lb_class = MagicMock(return_value=mock_lb_instance)

    fake_module = types.ModuleType("lite_brain")
    fake_module.LiteBrain = mock_lb_class

    import pr_factory as _pf
    old_mod = _pf._lite_brain_mod
    _pf._lite_brain_mod = fake_module
    yield mock_lb_instance, mock_lb_class
    _pf._lite_brain_mod = old_mod


@pytest.fixture
def sample_result():
    """A2A result from a successful agent run."""
    return {
        "status": "success",
        "summary": "Added login validation with email format check and rate limiting",
        "pr_url": "https://github.com/org/repo/pull/42",
        "pr_class": "A",
        "branch": "clarvis/agent/task_abc123",
        "files_changed": ["src/auth/login.ts", "src/auth/login.test.ts"],
        "procedures": ["npm run test", "npm run lint"],
        "follow_ups": ["Add E2E tests for login flow"],
        "tests_passed": True,
        "confidence": 0.92,
        "error": None,
    }


@pytest.fixture
def sample_result_low_confidence():
    """A2A result with low confidence — should NOT generate golden QA."""
    return {
        "status": "partial",
        "summary": "Attempted to fix the issue but needs more investigation",
        "pr_class": "B",
        "confidence": 0.5,
        "files_changed": ["src/utils.ts"],
        "procedures": [],
        "follow_ups": ["Needs root cause analysis"],
    }


# ── Task Classification Tests ──

class TestClassifyTask:
    def test_bugfix_classification(self):
        assert classify_task("Fix the login crash when email is empty") == "bugfix"

    def test_feature_classification(self):
        assert classify_task("Add dark mode toggle to settings") == "feature"

    def test_refactor_classification(self):
        assert classify_task("Refactor the auth module and restructure code") == "refactor"

    def test_docs_classification(self):
        assert classify_task("Document the API endpoints in README") == "docs"

    def test_tests_classification(self):
        assert classify_task("Add unit tests for payment module") == "tests"

    def test_config_classification(self):
        assert classify_task("Update CI workflow YAML for Node 20") == "config"

    def test_hardening_classification(self):
        assert classify_task("Harden input validation and sanitize user data") == "hardening"

    def test_investigation_classification(self):
        assert classify_task("Investigate and diagnose the memory leak") == "investigation"

    def test_default_classification(self):
        assert classify_task("Do something with the thingamajig") == "feature"

    def test_mixed_keywords_highest_wins(self):
        # "fix" + "bug" = 2 hits for bugfix vs "test" = 1 hit for tests
        result = classify_task("Fix the bug in test runner")
        assert result == "bugfix"


# ── Execution Brief Tests ──

class TestExecutionBrief:
    def test_brief_contains_required_fields(self, agent_dir, mock_litebrain):
        brief = build_execution_brief("test-agent", "Fix login bug", agent_dir)

        assert "task_interpretation" in brief
        assert "task_class" in brief
        assert "success_criteria" in brief
        assert "non_negotiables" in brief
        assert "relevant_files" in brief
        assert "verify_loop" in brief
        assert "pr_class_decision" in brief
        assert "compiled_at" in brief

    def test_brief_task_class_set(self, agent_dir, mock_litebrain):
        brief = build_execution_brief("test-agent", "Fix login bug", agent_dir)
        assert brief["task_class"] == "bugfix"

    def test_brief_saved_to_disk(self, agent_dir, mock_litebrain):
        build_execution_brief("test-agent", "Add dark mode feature", agent_dir)
        brief_path = agent_dir / "data" / "execution_brief.json"
        assert brief_path.exists()
        data = json.loads(brief_path.read_text())
        assert data["task_class"] == "feature"

    def test_brief_verify_loop_present(self, agent_dir, mock_litebrain):
        brief = build_execution_brief("test-agent", "Fix bug", agent_dir)
        vl = brief["verify_loop"]
        assert vl["max_refinements"] == 2
        assert "test_failure" in vl["allowed_triggers"]
        assert "scope_bloat" in vl["allowed_triggers"]

    def test_brief_pr_class_decision_present(self, agent_dir, mock_litebrain):
        brief = build_execution_brief("test-agent", "Fix bug", agent_dir)
        pcd = brief["pr_class_decision"]
        assert pcd["default"] == "A"
        assert "B" in str(pcd)
        assert "C" in str(pcd)


# ── Format Brief for Prompt Tests ──

class TestFormatBriefForPrompt:
    def test_format_includes_task_class(self):
        brief = {"task_class": "bugfix", "success_criteria": ["Bug fixed"]}
        text = format_brief_for_prompt(brief)
        assert "bugfix" in text

    def test_format_includes_success_criteria(self):
        brief = {"task_class": "feature", "success_criteria": ["Tests pass", "Feature works"]}
        text = format_brief_for_prompt(brief)
        assert "Tests pass" in text
        assert "Feature works" in text

    def test_format_includes_verify_loop(self):
        brief = {
            "task_class": "bugfix",
            "verify_loop": {"max_refinements": 2, "allowed_triggers": ["test_failure"]},
        }
        text = format_brief_for_prompt(brief)
        assert "max 2" in text
        assert "test_failure" in text

    def test_format_respects_token_cap(self):
        brief = {
            "task_class": "feature",
            "relevant_facts": ["x" * 500] * 10,
            "relevant_episodes": ["y" * 500] * 10,
            "success_criteria": ["z" * 200] * 10,
        }
        text = format_brief_for_prompt(brief)
        assert len(text) <= BRIEF_TOKEN_CAP

    def test_format_includes_pr_class_decision(self):
        brief = {
            "task_class": "feature",
            "pr_class_decision": {
                "default": "A",
                "downgrade_to_B_if": "blocker",
                "downgrade_to_C_if": "hard blocker",
            },
        }
        text = format_brief_for_prompt(brief)
        assert "default A" in text


# ── Writeback Tests ──

class TestWriteback:
    def test_writeback_creates_episode_summary(self, agent_dir, sample_result, mock_litebrain):
        run_writeback("test-agent", agent_dir, sample_result, "Fix login bug")

        episode_path = agent_dir / "data" / "episode_summary.json"
        assert episode_path.exists()
        data = json.loads(episode_path.read_text())
        assert data["status"] == "success"
        assert data["pr_class"] == "A"
        assert data["task_class"] == "bugfix"
        assert "login" in data["task"].lower()

    def test_writeback_stores_episode_in_litebrain(self, agent_dir, sample_result, mock_litebrain):
        mock_lb, _ = mock_litebrain
        run_writeback("test-agent", agent_dir, sample_result, "Fix login bug")

        all_texts = [c[0][0] for c in mock_lb.store.call_args_list]
        assert any("SUCCESS" in t for t in all_texts)

    def test_writeback_stores_procedures(self, agent_dir, sample_result, mock_litebrain):
        mock_lb, _ = mock_litebrain
        run_writeback("test-agent", agent_dir, sample_result, "Fix login bug")

        all_texts = [c[0][0] for c in mock_lb.store.call_args_list]
        assert any("npm run test" in t for t in all_texts)
        assert any("npm run lint" in t for t in all_texts)

    def test_writeback_stores_facts(self, agent_dir, sample_result, mock_litebrain):
        mock_lb, _ = mock_litebrain
        run_writeback("test-agent", agent_dir, sample_result, "Fix login bug")

        all_texts = [c[0][0] for c in mock_lb.store.call_args_list]
        assert any("login.ts" in t for t in all_texts)

    def test_writeback_updates_golden_qa_high_confidence(self, agent_dir, sample_result, mock_litebrain):
        run_writeback("test-agent", agent_dir, sample_result, "Fix login bug")

        qa_path = agent_dir / "data" / "golden_qa.json"
        assert qa_path.exists()
        entries = json.loads(qa_path.read_text())
        assert len(entries) == 1
        assert "login" in entries[0]["query"].lower()

    def test_writeback_skips_golden_qa_low_confidence(self, agent_dir, sample_result_low_confidence, mock_litebrain):
        run_writeback("test-agent", agent_dir, sample_result_low_confidence, "Fix something")

        qa_path = agent_dir / "data" / "golden_qa.json"
        assert not qa_path.exists()

    def test_writeback_no_duplicate_golden_qa(self, agent_dir, sample_result, mock_litebrain):
        run_writeback("test-agent", agent_dir, sample_result, "Fix login bug")
        run_writeback("test-agent", agent_dir, sample_result, "Fix login bug")

        qa_path = agent_dir / "data" / "golden_qa.json"
        entries = json.loads(qa_path.read_text())
        assert len(entries) == 1  # No duplicate

    def test_writeback_graceful_without_litebrain(self, agent_dir, sample_result):
        """Writeback should not crash if LiteBrain import fails."""
        with patch.dict(sys.modules, {"lite_brain": None}):
            run_writeback("test-agent", agent_dir, sample_result, "Fix login bug")

            episode_path = agent_dir / "data" / "episode_summary.json"
            assert episode_path.exists()


# ── Episode Summary Tests ──

class TestEpisodeSummary:
    def test_episode_fields(self, sample_result):
        episode = _build_episode_summary("Fix login bug", sample_result)
        assert episode["task"] == "Fix login bug"
        assert episode["task_class"] == "bugfix"
        assert episode["status"] == "success"
        assert episode["pr_class"] == "A"
        assert episode["pr_url"] == "https://github.com/org/repo/pull/42"
        assert episode["tests_passed"] is True
        assert episode["confidence"] == 0.92
        assert "timestamp" in episode


# ── Helper Tests ──

class TestHelpers:
    def test_success_criteria_for_bugfix(self):
        criteria = _infer_success_criteria("Fix crash", "bugfix")
        assert any("fix" in c.lower() for c in criteria)
        assert any("test" in c.lower() for c in criteria)

    def test_non_negotiables_always_include_safety(self):
        nn = _get_non_negotiables("feature")
        assert any("secret" in n.lower() for n in nn)
        assert any("scope" in n.lower() for n in nn)

    def test_extract_validations_from_commands(self):
        cmds = {"test": "npm test", "lint": "eslint .", "build": "npm run build"}
        validations = _extract_validations(cmds)
        assert "npm test" in validations
        assert "eslint ." in validations

    def test_find_relevant_files_from_route_index(self):
        indexes = {
            "route_index": {
                "data": {
                    "routes": [
                        {"path": "/api/login", "file": "app/api/login/route.ts"},
                        {"path": "/api/users", "file": "app/api/users/route.ts"},
                    ]
                }
            }
        }
        files = _find_relevant_files("Fix the login endpoint", indexes)
        assert "app/api/login/route.ts" in files

    def test_find_relevant_files_from_file_index(self):
        indexes = {
            "file_index": {
                "data": {
                    "files": [
                        {"path": "src/components/Login.tsx"},
                        {"path": "src/components/Header.tsx"},
                    ]
                }
            }
        }
        files = _find_relevant_files("Fix the Login component", indexes)
        assert "src/components/Login.tsx" in files


# ── Integration with project_agent.py Tests ──

class TestProjectAgentIntegration:
    def test_spawn_prompt_includes_execution_brief(self, mock_litebrain):
        """build_spawn_prompt should include Phase 3 execution brief when available."""
        from project_agent import build_spawn_prompt

        config = {"repo_url": "https://github.com/test/repo", "branch": "main"}
        agent_dir = Path("/tmp/test_agent_integration_phase3")
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "data" / "brain").mkdir(parents=True, exist_ok=True)

        prompt = build_spawn_prompt("test-agent", "Add dark mode feature", config, agent_dir)
        # Phase 3 is now installed, so it should include the brief
        assert "Execution Brief" in prompt

    def test_spawn_prompt_graceful_without_factory(self):
        """build_spawn_prompt should work even if pr_factory is not importable."""
        from project_agent import build_spawn_prompt

        config = {"repo_url": "https://github.com/test/repo", "branch": "main"}
        agent_dir = Path("/tmp/test_agent_integration2_phase3")
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Even without pr_factory, prompt should still build
        prompt = build_spawn_prompt("test-agent", "Add dark mode feature", config, agent_dir)
        assert "## Task" in prompt
        assert "Add dark mode feature" in prompt
