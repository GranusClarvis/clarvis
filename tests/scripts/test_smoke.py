"""
Smoke tests for critical Clarvis pipeline scripts.

Run: python3 -m pytest scripts/tests/test_smoke.py -v
"""
import sys
import time
import importlib
import pytest

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

# ── Critical pipeline scripts that must always import cleanly ──

CRITICAL_SCRIPTS = [
    "heartbeat_gate", "heartbeat_preflight", "heartbeat_postflight",
    "attention", "context_compressor", "prompt_builder",
    "episodic_memory", "procedural_memory", "working_memory", "hebbian_memory",
    "phi_metric", "dream_engine", "queue_writer", "task_router",
    "brain_bridge", "brain_introspect",
    "self_model", "self_report", "self_representation",
    "clarvis_reasoning", "clarvis_confidence", "clarvis_reflection",
    "somatic_markers", "reasoning_chain_hook", "reasoning_chains",
    "actr_activation", "soar_engine", "workspace_broadcast",
]

COGNITIVE_SCRIPTS = [
    "absolute_zero", "causal_model", "cognitive_load",
    "evolution_loop", "evolution_preflight", "failure_amplifier",
    "goal_tracker", "graph_compaction", "graphrag_communities",
    "hyperon_atomspace", "intra_linker", "knowledge_synthesis",
    "memory_consolidation", "meta_learning", "parameter_evolution",
    "performance_benchmark", "prediction_review",
    "retrieval_benchmark", "retrieval_experiment", "retrieval_quality",
    "temporal_self", "theory_of_mind",
    "thought_protocol", "world_models",
]


@pytest.mark.parametrize("module_name", CRITICAL_SCRIPTS)
def test_critical_import(module_name):
    """Critical pipeline scripts must import without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None


@pytest.mark.parametrize("module_name", COGNITIVE_SCRIPTS)
def test_cognitive_import(module_name):
    """Cognitive architecture scripts must import without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None


# ── Brain API smoke tests ──

class TestBrainAPI:
    @pytest.fixture(autouse=True, scope="class")
    def brain_instance(self):
        from brain import brain
        TestBrainAPI._brain = brain
        yield brain

    def test_stats(self):
        s = self._brain.stats()
        assert "total_memories" in s
        assert s["total_memories"] > 0

    def test_health_check(self):
        result = self._brain.health_check()
        assert isinstance(result, dict)
        assert result["status"] == "healthy"

    def test_recall_returns_list(self):
        r = self._brain.recall("test", n=2)
        assert isinstance(r, list)

    def test_store_roundtrip(self):
        self._brain.store(
            "smoke test temporary memory",
            importance=0.01,
            source="smoke_test",
        )
        r = self._brain.recall("smoke test temporary", n=1)
        assert len(r) > 0


# ── Latency guardrails ──

class TestLatency:
    def test_brain_import_under_2s(self):
        """Brain lazy import should be fast (no ChromaDB init)."""
        t0 = time.time()
        importlib.import_module("brain")
        elapsed = time.time() - t0
        # Reimport is cached so this is near-zero; first import ~400ms
        assert elapsed < 2.0

    def test_single_recall_under_5s(self):
        from brain import brain
        t0 = time.time()
        brain.recall("latency test", collections=["clarvis-learnings"], n=3)
        elapsed = time.time() - t0
        assert elapsed < 5.0, f"Single recall took {elapsed:.1f}s (limit 5s)"

    def test_stats_warm_under_1s(self):
        from brain import brain
        brain.stats()  # warm up
        t0 = time.time()
        brain.stats()
        elapsed = time.time() - t0
        assert elapsed < 1.0, f"Warm stats took {elapsed:.1f}s (limit 1s)"


# ── GWT Broadcast cycle smoke test ──

class TestBroadcastCycle:
    """Smoke test that workspace_broadcast + self_representation integrate correctly."""

    def test_broadcast_imports(self):
        """Both modules import and key classes/functions exist."""
        from workspace_broadcast import WorkspaceBroadcast, Codelet, Coalition
        from self_representation import encode_self_state, broadcast_self_state
        assert WorkspaceBroadcast is not None
        assert encode_self_state is not None
        assert broadcast_self_state is not None

    def test_self_state_has_z_dims(self):
        """encode_self_state() returns dict with 'z' containing latent dims, not 'summary'/'mode'."""
        from self_representation import encode_self_state
        state = encode_self_state()
        assert isinstance(state, dict)
        assert "z" in state
        z = state["z"]
        assert isinstance(z, dict)
        assert len(z) > 0
        # Must NOT have the old keys that workspace_broadcast previously expected
        assert "summary" not in state, "state should not have top-level 'summary' key"
        assert "mode" not in state, "state should not have top-level 'mode' key"
        # Dims should be floats in [0,1]
        for dim, val in z.items():
            assert 0.0 <= val <= 1.0, f"{dim}={val} out of range"

    def test_collect_self_codelet(self):
        """WorkspaceBroadcast.collect() produces a self_model codelet without error."""
        from workspace_broadcast import WorkspaceBroadcast
        ws = WorkspaceBroadcast()
        codelets = ws.collect()
        # At least some codelets collected (self_model may or may not be present
        # depending on other module availability, but no crash)
        assert isinstance(codelets, list)
        # If self_model codelet exists, verify it has the new format
        self_codelets = [c for c in codelets if c.source == "self_model"]
        for c in self_codelets:
            assert "Self-state:" in c.content
            # Must NOT contain old "mode=unknown" pattern from broken code
            assert "mode=unknown" not in c.content
