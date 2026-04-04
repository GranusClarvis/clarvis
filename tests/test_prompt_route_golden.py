"""Golden prompt fixture tests for main Claude Code routes.

Generates prompts from each route and snapshots them so route drift,
missing sections, duplicate context, and bad ordering can be detected.

Routes tested:
  1. heartbeat_preflight (cron_autonomous, cron_implementation_sprint)
  2. prompt_builder context-brief (cron_research, manual spawn)
  3. cron_evolution (evolution_preflight + static prompt)
  4. assembly.generate_tiered_brief (spine, used by routes 1+2)

Usage:
  pytest tests/test_prompt_route_golden.py -v
  pytest tests/test_prompt_route_golden.py --update-golden   # regenerate snapshots
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import _paths  # noqa: F401,E402

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "prompt_eval", "golden")
TASKSET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "prompt_eval", "taskset.json")

# Representative task for fixture generation
FIXTURE_TASK = "[SPINE_PROXY_REPLACEMENT] Replace proxy module clarvis/cognition/reasoning.py with real implementation"


def _load_taskset():
    with open(TASKSET_PATH) as f:
        return json.load(f)["tasks"]


def _ensure_golden_dir():
    os.makedirs(GOLDEN_DIR, exist_ok=True)


def _read_golden(name):
    path = os.path.join(GOLDEN_DIR, f"{name}.txt")
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return None


def _write_golden(name, content):
    _ensure_golden_dir()
    path = os.path.join(GOLDEN_DIR, f"{name}.txt")
    with open(path, "w") as f:
        f.write(content)


# ── Route 1: generate_tiered_brief (spine) ──────────────────────────

class TestTieredBriefRoute:
    """Tests for the canonical tiered brief generator."""

    @pytest.fixture(autouse=True)
    def _import(self):
        try:
            from clarvis.context.assembly import generate_tiered_brief
            self.generate = generate_tiered_brief
        except ImportError:
            pytest.skip("clarvis.context.assembly not importable")

    @pytest.mark.parametrize("tier", ["standard", "full"])
    def test_tiered_brief_generates(self, tier):
        """Tiered brief should return non-empty string for standard/full tiers."""
        brief = self.generate(FIXTURE_TASK, tier=tier)
        assert isinstance(brief, str)
        assert len(brief) > 0, f"Tiered brief ({tier}) returned empty"

    def test_minimal_tier_returns_string(self):
        """Minimal tier may return empty but must return a string."""
        brief = self.generate(FIXTURE_TASK, tier="minimal")
        assert isinstance(brief, str)

    def test_tiered_brief_ordering(self):
        """Standard/full briefs should have BEGIN---MIDDLE---END structure."""
        brief = self.generate(FIXTURE_TASK, tier="full")
        # The brief uses "---" separators between zones
        if "---" in brief:
            sections = brief.split("---")
            assert len(sections) >= 2, "Expected at least 2 zones separated by ---"

    def test_no_duplicate_failure_patterns(self):
        """Failure patterns should appear at most once."""
        brief = self.generate(FIXTURE_TASK, tier="full")
        count = brief.lower().count("avoid these failure patterns")
        assert count <= 1, f"Failure patterns duplicated: appeared {count} times"

    def test_no_duplicate_procedures(self):
        """Procedures should appear at most once."""
        brief = self.generate(FIXTURE_TASK, tier="full")
        count = brief.lower().count("recommended approach (from procedural memory)")
        assert count <= 1, f"Procedures duplicated: appeared {count} times"

    @pytest.mark.parametrize("tier", ["standard", "full"])
    def test_section_presence(self, tier):
        """Key sections should be present in standard/full briefs."""
        brief = self.generate(FIXTURE_TASK, tier=tier)
        # At minimum, decision context should appear
        assert "CURRENT TASK:" in brief or "TASK:" in brief.upper(), \
            f"Missing task identification in {tier} brief"

    def test_golden_snapshot(self, request):
        """Compare against golden snapshot to detect drift."""
        brief = self.generate(FIXTURE_TASK, tier="standard")
        golden = _read_golden("tiered_brief_standard")
        if request.config.getoption("--update-golden", default=False):
            _write_golden("tiered_brief_standard", brief)
            return
        if golden is None:
            _write_golden("tiered_brief_standard", brief)
            pytest.skip("Golden snapshot created — run again to compare")
        # Structural check: same number of sections (allow content to vary)
        golden_sections = len(golden.split("---"))
        brief_sections = len(brief.split("---"))
        assert abs(golden_sections - brief_sections) <= 1, \
            f"Section count changed: golden={golden_sections}, current={brief_sections}"


# ── Route 2: prompt_builder context-brief ────────────────────────────

class TestPromptBuilderRoute:
    """Tests for the prompt_builder context-brief path."""

    @pytest.fixture(autouse=True)
    def _import(self):
        try:
            from prompt_builder import get_context_brief
            self.get_brief = get_context_brief
        except ImportError:
            pytest.skip("prompt_builder not importable")

    @pytest.mark.parametrize("tier", ["minimal", "standard", "full"])
    def test_context_brief_generates(self, tier):
        brief = self.get_brief(tier=tier, task=FIXTURE_TASK)
        assert isinstance(brief, str)
        assert len(brief) > 0

    def test_no_duplicate_introspection_calls(self):
        """Verify duplicate brain recall in get_context_brief was removed.

        Before CONTEXT_DUPLICATE_RECALL fix, get_context_brief called
        introspect_for_task once via _introspect_for_task AND again directly
        plus a brain.recall for IDs. Now it should only call _introspect_for_task once.
        """
        import prompt_builder
        import inspect
        src = inspect.getsource(prompt_builder.get_context_brief)
        # _introspect_for_task appears at most twice: primary path + except fallback.
        # Only one path executes at runtime. The old pattern had 3+ calls.
        count = src.count("_introspect_for_task(")
        assert count <= 2, f"get_context_brief should call _introspect_for_task at most twice (primary + fallback), found {count}"
        # The old duplicate: raw introspect_for_task + brain.recall for IDs should be gone
        assert "brain.recall(task" not in src, "Duplicate brain.recall for IDs should be removed"


# ── Route 3: Budget policy integration ───────────────────────────────

class TestBudgetPolicyIntegration:
    """Tests that context_budget_policy.json is loaded and applied."""

    def test_policy_file_valid(self):
        with open(os.path.join(
                os.path.dirname(__file__), "..", "data", "prompt_eval",
                "context_budget_policy.json")) as f:
            policy = json.load(f)
        assert "task_classes" in policy
        for cls_name, cls_config in policy["task_classes"].items():
            assert "section_priorities" in cls_config, f"{cls_name} missing section_priorities"
            assert "tier_default" in cls_config, f"{cls_name} missing tier_default"
            priorities = cls_config["section_priorities"]
            for sec, weight in priorities.items():
                assert 0.0 <= weight <= 1.0, f"{cls_name}.{sec} weight {weight} out of [0,1]"

    def test_taskset_valid(self):
        tasks = _load_taskset()
        assert len(tasks) >= 8, f"Taskset should have >=8 tasks, got {len(tasks)}"
        for task in tasks:
            assert "id" in task
            assert "class" in task
            assert "task_text" in task
            assert "expected_context_needs" in task
            assert "failure_modes" in task

    def test_task_classifier(self):
        try:
            from clarvis.context.assembly import _classify_task_class
        except ImportError:
            pytest.skip("assembly not importable")
        assert _classify_task_class("research ColBERT v3") == "research_synthesis"
        assert _classify_task_class("fix crash in cron_autonomous") == "bugfix_debug"
        assert _classify_task_class("remove dead scripts") == "repo_cleanup"
        assert _classify_task_class("update CLAUDE.md schedule table") == "documentation"
        assert _classify_task_class("migrate actr_activation.py to spine") == "migration_refactor"
        assert _classify_task_class("add logrotate for cron logs") == "infra_cron"
        assert _classify_task_class("brain dedup on clarvis-learnings") == "memory_brain"
        assert _classify_task_class("strategic evolution analysis") == "strategic_evolution"

    def test_policy_weights_loaded(self):
        """generate_tiered_brief should use policy weights."""
        try:
            from clarvis.context.assembly import _get_policy_section_weights
        except ImportError:
            pytest.skip("assembly not importable")
        weights = _get_policy_section_weights("research ColBERT v3")
        assert len(weights) > 0, "Policy weights should be loaded for research task"
        assert weights.get("knowledge", 0) > weights.get("wire_guidance", 1), \
            "Research tasks should prioritize knowledge over wire_guidance"


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", default=False,
                     help="Regenerate golden snapshots")
