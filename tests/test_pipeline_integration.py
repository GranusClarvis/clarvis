"""Tests for Phase 7 — pipeline integration, router, graph decay, hooks.

Tests the heartbeat pipeline flow: gate -> preflight context -> (mock task) -> postflight hooks.
Also covers spine router, edge decay, and meta-learning hook registration.

Uses mocks/fixtures to avoid heavy runtime (no real ChromaDB or LLM calls).
"""

import json
import math
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import _paths  # noqa: F401,E402


# ===========================================================================
# 1. Spine Router (clarvis.orch.router)
# ===========================================================================

class TestOrchRouter:
    """Test task router in spine package."""

    def test_import_from_spine(self):
        from clarvis.orch.router import classify_task, log_decision, get_stats
        assert callable(classify_task)
        assert callable(log_decision)
        assert callable(get_stats)

    def test_init_exports(self):
        from clarvis.orch import classify_task, get_stats
        assert callable(classify_task)

    def test_classify_simple(self):
        from clarvis.orch.router import classify_task
        result = classify_task("check status")
        assert result["tier"] == "simple"
        assert result["executor"] == "gemini"

    def test_classify_complex(self):
        from clarvis.orch.router import classify_task
        result = classify_task("implement a new authentication module")
        assert result["tier"] == "complex"
        assert result["executor"] == "claude"

    def test_classify_vision(self):
        from clarvis.orch.router import classify_task
        result = classify_task("analyze this screenshot")
        assert result["tier"] == "vision"
        assert result["executor"] == "openrouter"

    def test_classify_web_search(self):
        from clarvis.orch.router import classify_task
        result = classify_task("search the web for latest news")
        assert result["tier"] == "web_search"

    def test_classify_returns_all_fields(self):
        from clarvis.orch.router import classify_task
        result = classify_task("analyze memory performance and optimize queries")
        assert "tier" in result
        assert "score" in result
        assert "executor" in result
        assert "dimensions" in result
        assert "reason" in result

    def test_score_dimension(self):
        from clarvis.orch.router import score_dimension
        dim = {"positive": ["code", "implement"], "negative": ["check"]}
        assert score_dimension("implement new code", dim) > 0
        assert score_dimension("check status", dim) < 0
        assert score_dimension("hello world", dim) == 0.0

    def test_log_decision_writes(self, tmp_path):
        from clarvis.orch import router
        orig = router.ROUTER_LOG
        router.ROUTER_LOG = str(tmp_path / "test_decisions.jsonl")
        try:
            classification = {"tier": "simple", "score": 0.1, "reason": "test"}
            router.log_decision("test task", classification, "gemini", "success")
            assert os.path.exists(router.ROUTER_LOG)
            with open(router.ROUTER_LOG) as f:
                entry = json.loads(f.readline())
            assert entry["task"] == "test task"
            assert entry["tier"] == "simple"
        finally:
            router.ROUTER_LOG = orig

    def test_scripts_wrapper_still_works(self):
        """Backward-compat: scripts/task_router.py still provides classify_task."""
        import importlib
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import task_router
            importlib.reload(task_router)
        result = task_router.classify_task("check health")
        assert result["tier"] == "simple"


# ===========================================================================
# 2. Hebbian Edge Decay (clarvis.brain.graph)
# ===========================================================================

class TestEdgeDecay:
    """Test age-based Hebbian edge decay in graph mixin."""

    def _make_brain_stub(self, tmp_path, edges):
        """Create a minimal brain-like object with graph operations."""
        from clarvis.brain.graph import GraphMixin

        class StubBrain(GraphMixin):
            def __init__(self, graph_file):
                self.graph_file = graph_file
                self.collections = {}
                self.graph = {"nodes": {}, "edges": edges}
                self._sqlite_store = None

        graph_file = str(tmp_path / "test_graph.json")
        stub = StubBrain(graph_file)
        return stub

    def test_no_hebbian_edges(self, tmp_path):
        edges = [{"from": "a", "to": "b", "type": "cross_collection", "created_at": "2026-01-01T00:00:00+00:00"}]
        brain = self._make_brain_stub(tmp_path, edges)
        result = brain.decay_edges(dry_run=True)
        assert result["decayed"] == 0
        assert result["pruned"] == 0
        assert result["total_before"] == 1
        assert result["total_after"] == 1

    def test_fresh_edge_no_prune(self, tmp_path):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        edges = [{"from": "a", "to": "b", "type": "hebbian_association", "created_at": now, "weight": 1.0}]
        brain = self._make_brain_stub(tmp_path, edges)
        result = brain.decay_edges(dry_run=True)
        assert result["decayed"] == 1
        assert result["pruned"] == 0
        assert result["avg_weight"] > 0.9  # nearly 1.0 (just created)

    def test_old_edge_pruned(self, tmp_path):
        # Edge created 365 days ago with weight 0.01 — should be pruned
        edges = [{"from": "a", "to": "b", "type": "hebbian_association",
                  "created_at": "2025-03-01T00:00:00+00:00", "weight": 0.01}]
        brain = self._make_brain_stub(tmp_path, edges)
        result = brain.decay_edges(half_life_days=30, prune_below=0.001, dry_run=True)
        assert result["pruned"] == 1

    def test_decay_formula_correctness(self, tmp_path):
        """Verify exponential decay: w * 2^(-age/half_life)."""
        # Edge exactly 30 days old with weight 1.0, half_life=30 → expected ~0.5
        from datetime import datetime, timezone, timedelta
        created = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        edges = [{"from": "a", "to": "b", "type": "hebbian_association",
                  "created_at": created, "weight": 1.0}]
        brain = self._make_brain_stub(tmp_path, edges)
        result = brain.decay_edges(half_life_days=30, prune_below=0.001, dry_run=True)
        assert result["decayed"] == 1
        assert 0.4 < result["avg_weight"] < 0.6  # ~0.5

    def test_dry_run_no_modification(self, tmp_path):
        from datetime import datetime, timezone, timedelta
        created = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        edges = [{"from": "a", "to": "b", "type": "hebbian_association",
                  "created_at": created, "weight": 0.5}]
        brain = self._make_brain_stub(tmp_path, edges)
        brain.decay_edges(dry_run=True)
        # Original weight should be unchanged
        assert brain.graph["edges"][0]["weight"] == 0.5

    def test_actual_write(self, tmp_path):
        from datetime import datetime, timezone, timedelta
        created = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        edges = [{"from": "a", "to": "b", "type": "hebbian_association",
                  "created_at": created, "weight": 1.0}]
        brain = self._make_brain_stub(tmp_path, edges)
        result = brain.decay_edges(half_life_days=30, dry_run=False)
        assert result["decayed"] == 1
        # Weight should now be updated in the graph
        new_weight = brain.graph["edges"][0]["weight"]
        assert 0.4 < new_weight < 0.6
        assert "last_decay" in brain.graph["edges"][0]
        # File should exist on disk
        assert os.path.exists(brain.graph_file)


# ===========================================================================
# 3. GraphRAG Booster Hook (clarvis.brain.hooks)
# ===========================================================================

class TestGraphRAGBooster:
    """Test GraphRAG recall booster hook."""

    def test_booster_noop_when_disabled(self):
        from clarvis.brain.hooks import _make_graphrag_booster
        booster = _make_graphrag_booster()
        results = [{"id": "test_1", "document": "hello", "metadata": {}}]
        # Should not raise, should not modify (env not set)
        os.environ.pop("CLARVIS_GRAPHRAG_BOOST", None)
        booster(results)
        assert "_graphrag_community" not in results[0]["metadata"]

    def test_booster_noop_on_empty_results(self):
        from clarvis.brain.hooks import _make_graphrag_booster
        booster = _make_graphrag_booster()
        os.environ["CLARVIS_GRAPHRAG_BOOST"] = "1"
        try:
            booster([])  # should not raise
        finally:
            os.environ.pop("CLARVIS_GRAPHRAG_BOOST", None)


# ===========================================================================
# 4. Heartbeat Pipeline Integration (gate → hooks → postflight)
# ===========================================================================

class TestPipelineIntegration:
    """Test full pipeline flow: gate decision → hook registration → hook execution."""

    def test_gate_produces_wake_or_skip(self, tmp_path):
        from clarvis.heartbeat import gate as gate_mod
        orig = gate_mod.STATE_FILE
        gate_mod.STATE_FILE = str(tmp_path / "test_state.json")
        try:
            decision, reason, changes = gate_mod.check_gate()
            assert decision in ("wake", "skip")
        finally:
            gate_mod.STATE_FILE = orig

    def test_hook_registry_lifecycle(self):
        """Register → run → clear lifecycle."""
        from clarvis.heartbeat.hooks import HookRegistry, HookPhase
        reg = HookRegistry()

        call_log = []
        reg.register(HookPhase.POSTFLIGHT, "test_hook_a", lambda ctx: call_log.append("a"), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "test_hook_b", lambda ctx: call_log.append("b"), priority=20)

        results = reg.run(HookPhase.POSTFLIGHT, {"exit_code": 0})
        assert "test_hook_a" in results
        assert "test_hook_b" in results
        assert call_log == ["a", "b"]  # priority order

        reg.clear()
        assert reg.hooks_for(HookPhase.POSTFLIGHT) == []

    def test_hook_failure_isolation(self):
        """One failing hook should not block subsequent hooks."""
        from clarvis.heartbeat.hooks import HookRegistry, HookPhase
        reg = HookRegistry()

        def bad_hook(ctx):
            raise RuntimeError("boom")

        call_log = []
        reg.register(HookPhase.POSTFLIGHT, "bad", bad_hook, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "good", lambda ctx: call_log.append("ok"), priority=20)

        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert "error" in results["bad"]
        assert call_log == ["ok"]  # good hook still ran

    def test_adapter_registration(self):
        """Adapters register hooks in correct order."""
        from clarvis.heartbeat.hooks import HookRegistry, HookPhase, registry
        # Clear and re-register
        registry.clear()
        from clarvis.heartbeat.adapters import register_all
        register_all()

        hooks = registry.hooks_for(HookPhase.POSTFLIGHT)
        names = [name for name, _ in hooks]
        assert "procedural_record" in names
        assert "periodic_synthesis" in names
        assert "perf_benchmark" in names
        assert "meta_learning" in names

        # meta_learning should be last (priority 90)
        priorities = {name: prio for name, prio in hooks}
        assert priorities["meta_learning"] == 90
        assert priorities["procedural_record"] < priorities["meta_learning"]

    def test_full_pipeline_mock(self, tmp_path):
        """Simulate gate → context → postflight with mocked hooks."""
        from clarvis.heartbeat.hooks import HookRegistry, HookPhase

        reg = HookRegistry()
        pipeline_log = []

        # Simulate gate
        gate_result = ("wake", "test", ["test_change"])
        pipeline_log.append(f"gate: {gate_result[0]}")

        # Simulate preflight context
        context = {
            "task": "test task",
            "exit_code": 0,
            "output_text": "task completed successfully",
            "task_status": "success",
            "task_duration": 10.0,
        }
        pipeline_log.append(f"context: {context['task']}")

        # Register mock postflight hooks
        reg.register(HookPhase.POSTFLIGHT, "mock_episodic",
                     lambda ctx: {"action": "recorded_episode"}, priority=30)
        reg.register(HookPhase.POSTFLIGHT, "mock_metrics",
                     lambda ctx: {"brain_query_avg_ms": 42}, priority=60)

        # Run postflight
        results = reg.run(HookPhase.POSTFLIGHT, context)
        pipeline_log.append(f"postflight: {len(results)} hooks ran")

        assert len(pipeline_log) == 3
        assert results["mock_episodic"]["result"]["action"] == "recorded_episode"
        assert results["mock_metrics"]["result"]["brain_query_avg_ms"] == 42

    def test_meta_learning_daily_rate_limit(self, tmp_path):
        """Meta-learning hook should skip if already ran today."""
        from clarvis.heartbeat import adapters
        orig_marker = adapters._META_LEARNING_MARKER
        adapters._META_LEARNING_MARKER = str(tmp_path / ".last_postflight_run")

        # Write today's date to marker
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        os.makedirs(os.path.dirname(adapters._META_LEARNING_MARKER), exist_ok=True)
        with open(adapters._META_LEARNING_MARKER, "w") as f:
            f.write(today)

        try:
            result = adapters._meta_learning_analyze({})
            assert result["action"] == "skip"
            assert result["reason"] == "already_ran_today"
        finally:
            adapters._META_LEARNING_MARKER = orig_marker


# ===========================================================================
# 5. Edge Decay CLI (clarvis brain edge-decay)
# ===========================================================================

class TestEdgeDecayCLI:
    """Test that edge-decay CLI command is registered."""

    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "clarvis", "brain", "edge-decay", "--help"],
            capture_output=True, text=True,
            cwd=os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")),
        )
        assert result.returncode == 0
        assert "half-life" in result.stdout or "Decay" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
