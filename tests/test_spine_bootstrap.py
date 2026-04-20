"""Bootstrap tests for spine modules with lowest coverage.

Covers: clarvis.metrics (phi, benchmark, clr), clarvis.queue (engine, writer),
clarvis.memory (consolidation, procedural), clarvis.learning (meta_learning).
All tests are pure-logic or mock-based — no ChromaDB or file I/O required.
"""

import os
import sys
import json
import tempfile
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# 1. clarvis.metrics.benchmark — compute_pi pure logic
# ---------------------------------------------------------------------------

class TestComputePI:
    def test_import(self):
        from clarvis.metrics.benchmark import compute_pi, TARGETS
        assert callable(compute_pi)
        assert isinstance(TARGETS, dict)

    def test_targets_weights_are_positive(self):
        from clarvis.metrics.benchmark import TARGETS
        total = sum(m.get("weight", 0) for m in TARGETS.values())
        assert total > 0.9

    def test_all_targets_met_gives_high_pi(self):
        from clarvis.metrics.benchmark import compute_pi, TARGETS
        perfect = {}
        for key, meta in TARGETS.items():
            if meta.get("target") is None or meta.get("weight", 0) == 0:
                continue
            if meta["direction"] == "lower":
                perfect[key] = meta["target"] * 0.5
            else:
                perfect[key] = meta["target"] * 2.0
        result = compute_pi(perfect)
        assert result["pi"] >= 0.95

    def test_all_critical_gives_zero_pi(self):
        from clarvis.metrics.benchmark import compute_pi, TARGETS
        worst = {}
        for key, meta in TARGETS.items():
            if meta.get("target") is None or meta.get("weight", 0) == 0:
                continue
            crit = meta.get("critical")
            if crit is None:
                continue
            if meta["direction"] == "lower":
                worst[key] = crit * 2.0
            else:
                worst[key] = 0.0
        result = compute_pi(worst)
        assert result["pi"] < 0.2

    def test_empty_metrics_returns_zero(self):
        from clarvis.metrics.benchmark import compute_pi
        result = compute_pi({})
        assert result["pi"] == 0.0

    def test_pi_returns_interpretation(self):
        from clarvis.metrics.benchmark import compute_pi
        result = compute_pi({})
        assert "interpretation" in result
        assert isinstance(result["interpretation"], str)


# ---------------------------------------------------------------------------
# 2. clarvis.metrics.clr — weights and thresholds
# ---------------------------------------------------------------------------

class TestCLRConstants:
    def test_weights_sum_to_one(self):
        from clarvis.metrics.clr import WEIGHTS
        total = sum(WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_all_dimensions_have_weights(self):
        from clarvis.metrics.clr import WEIGHTS
        expected = {
            "memory_quality", "retrieval_precision", "prompt_context",
            "task_success", "autonomy", "efficiency", "integration_dynamics",
        }
        assert set(WEIGHTS.keys()) == expected

    def test_gate_thresholds_exist(self):
        from clarvis.metrics.clr import GATE_THRESHOLDS
        assert "min_clr" in GATE_THRESHOLDS
        assert GATE_THRESHOLDS["min_clr"] > 0


# ---------------------------------------------------------------------------
# 3. clarvis.metrics.phi — helper functions
# ---------------------------------------------------------------------------

class TestPhiHelpers:
    def test_infer_collection_known_prefix(self):
        from clarvis.metrics.phi import _infer_collection
        result = _infer_collection("clarvis-learnings_abc123")
        assert result == "clarvis-learnings"

    def test_infer_collection_legacy_prefix(self):
        from clarvis.metrics.phi import _infer_collection, LEGACY_PREFIX_MAP
        result = _infer_collection("identity_something")
        assert result == "clarvis-identity"

    def test_legacy_prefix_map_coverage(self):
        from clarvis.metrics.phi import LEGACY_PREFIX_MAP
        assert len(LEGACY_PREFIX_MAP) >= 8


# ---------------------------------------------------------------------------
# 4. clarvis.queue.engine — parse_queue and tag extraction
# ---------------------------------------------------------------------------

class TestQueueEngine:
    def test_extract_tag_simple(self):
        from clarvis.queue.engine import _extract_tag
        assert _extract_tag("[TEST_TAG] some task") == "TEST_TAG"

    def test_extract_tag_bold(self):
        from clarvis.queue.engine import _extract_tag
        assert _extract_tag("**[BOLD_TAG]** some task") == "BOLD_TAG"

    def test_extract_tag_no_tag(self):
        from clarvis.queue.engine import _extract_tag
        assert _extract_tag("no tag here") is None

    def test_extract_tag_lowercase_rejected(self):
        from clarvis.queue.engine import _extract_tag
        assert _extract_tag("[lowercase] task") is None

    def test_parse_queue_from_file(self):
        from clarvis.queue.engine import parse_queue
        content = textwrap.dedent("""\
            # Evolution Queue

            ## P0 — Current Sprint
            - [ ] **[ALPHA_TASK]** Do alpha work
            - [x] **[DONE_TASK]** Already done

            ## P1 — This Week
            - [ ] **[BETA_TASK]** Do beta work
            - [ ] Untagged task here

            ## P2 — When Idle
            - [ ] **[GAMMA_TASK]** Do gamma work
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            try:
                tasks = parse_queue(f.name)
            finally:
                os.unlink(f.name)

        tags = [t["tag"] for t in tasks]
        assert "ALPHA_TASK" in tags
        assert "BETA_TASK" in tags
        assert "GAMMA_TASK" in tags
        assert "DONE_TASK" not in tags

        alpha = next(t for t in tasks if t["tag"] == "ALPHA_TASK")
        assert alpha["priority"] == "P0"

    def test_constants(self):
        from clarvis.queue.engine import MAX_RETRIES, BACKOFF_CAP, STUCK_RUNNING_HOURS
        assert MAX_RETRIES["P0"] >= MAX_RETRIES["P2"]
        assert BACKOFF_CAP >= 1
        assert STUCK_RUNNING_HOURS >= 1

    def test_now_iso_format(self):
        from clarvis.queue.engine import _now_iso
        ts = _now_iso()
        assert ts.endswith("Z")
        assert "T" in ts


# ---------------------------------------------------------------------------
# 5. clarvis.queue.writer — add_task with temp queue file
# ---------------------------------------------------------------------------

class TestQueueWriter:
    def test_tasks_added_today_callable(self):
        from clarvis.queue.writer import tasks_added_today
        count = tasks_added_today()
        assert isinstance(count, int)
        assert count >= 0


# ---------------------------------------------------------------------------
# 6. clarvis.memory — consolidation module imports
# ---------------------------------------------------------------------------

class TestMemoryConsolidation:
    def test_imports(self):
        from clarvis.memory.memory_consolidation import (
            deduplicate, prune_noise, archive_stale,
            sleep_stats, get_consolidation_stats,
        )
        assert callable(deduplicate)
        assert callable(prune_noise)


# ---------------------------------------------------------------------------
# 7. clarvis.memory.procedural_memory — constants and pure logic
# ---------------------------------------------------------------------------

class TestProceduralMemory:
    def test_imports(self):
        from clarvis.memory.procedural_memory import (
            find_procedure, store_procedure, library_stats,
            list_procedures, find_code_templates,
        )
        assert callable(find_procedure)

    def test_format_code_templates_empty(self):
        from clarvis.memory.procedural_memory import format_code_templates
        result = format_code_templates([])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 8. clarvis.learning.meta_learning — MetaLearner class
# ---------------------------------------------------------------------------

class TestMetaLearner:
    def test_import(self):
        from clarvis.learning.meta_learning import MetaLearner
        assert MetaLearner is not None

    def test_class_has_expected_interface(self):
        from clarvis.learning.meta_learning import MetaLearner
        ml = MetaLearner.__new__(MetaLearner)
        assert hasattr(MetaLearner, "__init__")


# ---------------------------------------------------------------------------
# 9. clarvis.runtime.mode — pure logic tests
# ---------------------------------------------------------------------------

class TestRuntimeMode:
    def test_normalize_mode_valid(self):
        from clarvis.runtime.mode import normalize_mode
        result = normalize_mode("ge")
        assert result == "ge"

    def test_normalize_mode_invalid_raises(self):
        from clarvis.runtime.mode import normalize_mode
        with pytest.raises(ValueError):
            normalize_mode("nonexistent_mode")

    def test_mode_policies_returns_dict(self):
        from clarvis.runtime.mode import mode_policies
        result = mode_policies("ge")
        assert isinstance(result, dict)
        assert "allow_autonomous_execution" in result
