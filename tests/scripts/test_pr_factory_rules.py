"""
Acceptance tests for PR Factory Phase 1 — prompt injection + A2A pr_class.

Run: python3 -m pytest scripts/tests/test_pr_factory_rules.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
import _paths  # noqa: F401,E402

from clarvis.orch.pr_rules import build_pr_rules_section, PR_CLASSES
from project_agent import (
    build_spawn_prompt,
    validate_a2a_result,
    normalize_a2a_result,
    A2A_RESULT_SCHEMA,
)


# ── Fixtures ──

@pytest.fixture
def agent_config():
    return {
        "name": "test-project",
        "repo_url": "https://github.com/test/repo.git",
        "branch": "dev",
        "constraints": ["Run tests before PR"],
        "budget": {"max_timeout": 1800},
    }


@pytest.fixture
def agent_dir(tmp_path):
    (tmp_path / "workspace").mkdir()
    (tmp_path / "memory").mkdir()
    (tmp_path / "data" / "brain").mkdir(parents=True)
    return tmp_path


# ── PR Rules Content Tests ──

class TestPRRulesContent:
    """Tests 1-6: verify the rules section contains required content."""

    def test_rules_contain_all_pr_classes(self):
        """#1: Output mentions Class A, Class B, Class C."""
        text = "\n".join(build_pr_rules_section())
        assert "Class A" in text
        assert "Class B" in text
        assert "Class C" in text

    def test_rules_contain_two_pr_policy(self):
        """#2: Output mentions two-PR policy."""
        text = "\n".join(build_pr_rules_section())
        assert "Two-PR Policy" in text or "two-PR" in text.lower()

    def test_rules_contain_max_refinement_limit(self):
        """#3: Output mentions max 2 refinement loops."""
        text = "\n".join(build_pr_rules_section())
        assert "Max 2" in text or "No fourth pass" in text

    def test_rules_contain_task_linkage_fields(self):
        """#4: Output mentions all four task-linkage fields."""
        text = "\n".join(build_pr_rules_section())
        assert "Original task:" in text
        assert "Blocker:" in text
        assert "Unblocks:" in text
        assert "Next PR:" in text

    def test_rules_no_blocking_language(self):
        """#5: Output does NOT contain unconditional blocker language."""
        text = "\n".join(build_pr_rules_section())
        # These phrases would tell the agent to halt unconditionally
        assert "must prove" not in text.lower()
        assert "halt immediately" not in text.lower()
        assert "abort unconditionally" not in text.lower()

    def test_rules_evidence_steers_not_blocks(self):
        """#6: Output contains evidence-steers-not-blocks principle."""
        text = "\n".join(build_pr_rules_section())
        assert "never an excuse" in text.lower() or "steers" in text.lower()

    def test_rules_return_list_of_strings(self):
        """Rules should return a list of strings."""
        result = build_pr_rules_section()
        assert isinstance(result, list)
        assert all(isinstance(line, str) for line in result)

    def test_rules_contain_truthfulness(self):
        """Rules mention truthfulness / no misrepresentation."""
        text = "\n".join(build_pr_rules_section())
        assert "Truthfulness" in text or "misrepresent" in text.lower()

    def test_rules_contain_done_definition(self):
        """Rules define what 'done' means."""
        text = "\n".join(build_pr_rules_section())
        assert "Done" in text


# ── Prompt Integration Tests ──

class TestPromptIntegration:
    """Tests 7-9: verify rules are wired into build_spawn_prompt."""

    def test_spawn_prompt_includes_pr_rules(self, agent_config, agent_dir):
        """#7: build_spawn_prompt output contains PR Factory Rules section."""
        prompt = build_spawn_prompt(
            "test-project", "Fix auth bug", agent_config, agent_dir
        )
        assert "PR Factory Rules" in prompt
        assert "Class A" in prompt
        assert "Class B" in prompt
        assert "Class C" in prompt

    def test_spawn_prompt_includes_a2a_pr_class(self, agent_config, agent_dir):
        """#8: A2A protocol section in prompt mentions pr_class field."""
        prompt = build_spawn_prompt(
            "test-project", "Fix auth bug", agent_config, agent_dir
        )
        assert '"pr_class"' in prompt

    def test_spawn_prompt_graceful_without_factory(self, agent_config, agent_dir):
        """#9: If pr_factory_rules not importable, prompt still builds."""
        with patch.dict("sys.modules", {"pr_factory_rules": None}):
            # Force ImportError by patching __import__
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            def mock_import(name, *args, **kwargs):
                if name == "pr_factory_rules":
                    raise ImportError("mocked away")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                prompt = build_spawn_prompt(
                    "test-project", "Fix auth bug", agent_config, agent_dir
                )
                # Prompt still works — has task and output protocol
                assert "Fix auth bug" in prompt
                assert "Output Protocol" in prompt

    def test_pr_rules_appear_before_task_section(self, agent_config, agent_dir):
        """Rules section should appear before the Task section."""
        prompt = build_spawn_prompt(
            "test-project", "Do something", agent_config, agent_dir
        )
        rules_pos = prompt.find("PR Factory Rules")
        task_pos = prompt.find("## Task")
        assert rules_pos != -1
        assert task_pos != -1
        assert rules_pos < task_pos, "PR Factory Rules must appear before Task"


# ── A2A Protocol Extension Tests ──

class TestA2AProtocolExtension:
    """Tests 10-11: verify pr_class validation in A2A protocol."""

    def test_a2a_schema_includes_pr_class(self):
        """Schema has pr_class field."""
        assert "pr_class" in A2A_RESULT_SCHEMA

    def test_a2a_validates_pr_class_when_pr_url_set(self):
        """#10: Validation warns if pr_url set but pr_class missing."""
        result = {
            "status": "success",
            "summary": "Did the thing",
            "pr_url": "https://github.com/test/repo/pull/1",
            # pr_class intentionally omitted
        }
        is_valid, warnings = validate_a2a_result(result)
        assert any("pr_class" in w for w in warnings), \
            f"Expected pr_class warning, got: {warnings}"

    def test_a2a_validates_invalid_pr_class(self):
        """Validation warns if pr_class is not A/B/C."""
        result = {
            "status": "success",
            "summary": "Did the thing",
            "pr_url": "https://github.com/test/repo/pull/1",
            "pr_class": "D",
        }
        is_valid, warnings = validate_a2a_result(result)
        assert any("pr_class" in w for w in warnings), \
            f"Expected pr_class warning for invalid value, got: {warnings}"

    def test_a2a_accepts_valid_pr_class_a(self):
        """#11: Validation passes for pr_class A."""
        result = {
            "status": "success",
            "summary": "Task fully done",
            "pr_url": "https://github.com/test/repo/pull/1",
            "pr_class": "A",
        }
        is_valid, warnings = validate_a2a_result(result)
        assert not any("pr_class" in w for w in warnings)

    def test_a2a_accepts_valid_pr_class_b(self):
        """Validation passes for pr_class B."""
        result = {
            "status": "partial",
            "summary": "Core done, blocker remains",
            "pr_url": "https://github.com/test/repo/pull/2",
            "pr_class": "B",
        }
        is_valid, warnings = validate_a2a_result(result)
        assert not any("pr_class" in w for w in warnings)

    def test_a2a_accepts_valid_pr_class_c(self):
        """Validation passes for pr_class C."""
        result = {
            "status": "success",
            "summary": "Unblocking CI scaffolding",
            "pr_url": "https://github.com/test/repo/pull/3",
            "pr_class": "C",
        }
        is_valid, warnings = validate_a2a_result(result)
        assert not any("pr_class" in w for w in warnings)

    def test_a2a_no_warning_without_pr_url(self):
        """No pr_class warning when no PR was created."""
        result = {
            "status": "failed",
            "summary": "Could not complete, no PR",
        }
        is_valid, warnings = validate_a2a_result(result)
        assert not any("pr_class" in w for w in warnings)

    def test_normalize_preserves_pr_class(self):
        """normalize_a2a_result preserves pr_class when present."""
        result = {
            "status": "success",
            "summary": "Done",
            "pr_class": "A",
        }
        normalized = normalize_a2a_result(result)
        assert normalized["pr_class"] == "A"

    def test_normalize_defaults_pr_class_to_none(self):
        """normalize_a2a_result defaults pr_class to None when absent."""
        result = {
            "status": "success",
            "summary": "Done",
        }
        normalized = normalize_a2a_result(result)
        assert normalized["pr_class"] is None


# ── PR_CLASSES constant ──

class TestPRClassesConstant:
    def test_pr_classes_set(self):
        assert PR_CLASSES == {"A", "B", "C"}
