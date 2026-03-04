"""Tests for Phase 4 spine migrations — heartbeat gate, context compressor, brain search.

Tests are designed to run without ChromaDB where possible (pure Python logic).
Tests that need ChromaDB are marked with pytest.mark.slow.
"""

import os
import sys
import json
import time
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# ===========================================================================
# 1. Heartbeat Gate (clarvis.heartbeat.gate)
# ===========================================================================

class TestHeartbeatGate:
    """Test the spine heartbeat gate module (pure Python, no DB)."""

    def test_import(self):
        from clarvis.heartbeat.gate import check_gate, run_gate, load_state, save_state
        assert callable(check_gate)
        assert callable(run_gate)

    def test_check_gate_returns_tuple(self):
        from clarvis.heartbeat.gate import check_gate
        result = check_gate()
        assert isinstance(result, tuple)
        assert len(result) == 3
        decision, reason, changes = result
        assert decision in ("wake", "skip")
        assert isinstance(reason, str)
        assert isinstance(changes, list)

    def test_load_save_state(self, tmp_path):
        from clarvis.heartbeat import gate as gate_mod
        orig_state_file = gate_mod.STATE_FILE
        gate_mod.STATE_FILE = str(tmp_path / "test_state.json")
        try:
            # Fresh state
            state = gate_mod.load_state()
            assert state == {}

            # Save and reload
            gate_mod.save_state({"test": True, "count": 42})
            state = gate_mod.load_state()
            assert state["test"] is True
            assert state["count"] == 42
        finally:
            gate_mod.STATE_FILE = orig_state_file

    def test_first_run_forces_wake(self, tmp_path):
        from clarvis.heartbeat import gate as gate_mod
        orig_state_file = gate_mod.STATE_FILE
        gate_mod.STATE_FILE = str(tmp_path / "test_state.json")
        try:
            decision, reason, changes = gate_mod.check_gate()
            assert decision == "wake"
            assert "first_run" in changes or "First run" in reason
        finally:
            gate_mod.STATE_FILE = orig_state_file

    def test_file_fingerprint(self, tmp_path):
        from clarvis.heartbeat.gate import _file_fingerprint
        # Non-existent file
        assert _file_fingerprint(str(tmp_path / "nope.txt")) is None

        # Create a file
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        fp = _file_fingerprint(str(f))
        assert fp is not None
        assert "mtime" in fp
        assert "size" in fp
        assert fp["size"] == 11
        assert "head_hash" in fp

    def test_dir_fingerprint(self, tmp_path):
        from clarvis.heartbeat.gate import _dir_fingerprint
        # Empty dir
        fp = _dir_fingerprint(str(tmp_path))
        assert fp is not None
        assert fp["file_count"] == 0

        # Add a file
        (tmp_path / "a.txt").write_text("x")
        fp = _dir_fingerprint(str(tmp_path))
        assert fp["file_count"] == 1
        assert fp["latest_mtime"] > 0

    def test_run_gate_updates_state(self, tmp_path):
        from clarvis.heartbeat import gate as gate_mod
        orig_state_file = gate_mod.STATE_FILE
        gate_mod.STATE_FILE = str(tmp_path / "test_state.json")
        try:
            decision, output = gate_mod.run_gate()
            assert decision in ("wake", "skip")
            assert "decision" in output
            assert "reason" in output

            # State should now be saved
            state = gate_mod.load_state()
            assert "last_check_time" in state
            assert "last_check_day" in state
        finally:
            gate_mod.STATE_FILE = orig_state_file

    def test_spine_init_exports(self):
        """Verify heartbeat __init__ exports gate functions."""
        from clarvis.heartbeat import check_gate, run_gate, load_state, save_state
        assert callable(check_gate)


# ===========================================================================
# 2. Context Compressor (clarvis.context.compressor)
# ===========================================================================

class TestContextCompressor:
    """Test the spine context compressor (pure Python, no DB)."""

    def test_import(self):
        from clarvis.context.compressor import (
            tfidf_extract, mmr_rerank, compress_text,
            compress_queue, compress_episodes, generate_tiered_brief,
        )
        assert callable(tfidf_extract)
        assert callable(mmr_rerank)

    def test_tfidf_extract_short_text(self):
        from clarvis.context.compressor import tfidf_extract
        short = "Hello world"
        assert tfidf_extract(short) == short  # too short to compress

    def test_tfidf_extract_compresses(self):
        from clarvis.context.compressor import tfidf_extract
        text = "\n".join([f"This is sentence number {i} about topic {i % 3}." for i in range(30)])
        result = tfidf_extract(text, ratio=0.3)
        assert len(result) < len(text)

    def test_compress_text_returns_tuple(self):
        from clarvis.context.compressor import compress_text
        text = "\n".join([f"Line {i}: important data about system metrics and performance." for i in range(30)])
        compressed, stats = compress_text(text, ratio=0.3)
        assert isinstance(compressed, str)
        assert isinstance(stats, dict)
        assert "input_chars" in stats
        assert "output_chars" in stats
        assert stats["output_chars"] <= stats["input_chars"]

    def test_compress_text_short_passthrough(self):
        from clarvis.context.compressor import compress_text
        short = "Short text"
        result, stats = compress_text(short)
        assert result == short
        assert stats["ratio"] == 1.0

    def test_mmr_rerank_empty(self):
        from clarvis.context.compressor import mmr_rerank
        assert mmr_rerank([], "query") == []

    def test_mmr_rerank_single(self):
        from clarvis.context.compressor import mmr_rerank
        items = [{"document": "hello", "distance": 0.5}]
        result = mmr_rerank(items, "hello")
        assert len(result) == 1

    def test_mmr_rerank_diversity(self):
        from clarvis.context.compressor import mmr_rerank
        items = [
            {"document": "apple banana cherry", "distance": 0.1},
            {"document": "apple banana date", "distance": 0.2},
            {"document": "elephant frog giraffe", "distance": 0.3},
        ]
        result = mmr_rerank(items, "apple banana", lambda_param=0.5)
        assert len(result) == 3
        # First should be most relevant (closest distance)
        assert result[0]["document"] == "apple banana cherry"

    def test_compress_queue_file_missing(self, tmp_path):
        from clarvis.context.compressor import compress_queue
        result = compress_queue(queue_file=str(tmp_path / "nonexistent.md"))
        assert "No evolution queue" in result

    def test_compress_queue_with_file(self, tmp_path):
        from clarvis.context.compressor import compress_queue
        queue = tmp_path / "QUEUE.md"
        queue.write_text("""## P0 — Do Next
- [ ] Task A
- [ ] Task B
- [x] Task C (2026-03-01 UTC)
- [x] Task D (2026-03-02 UTC)
""")
        result = compress_queue(queue_file=str(queue))
        assert "Task A" in result
        assert "Task B" in result
        assert "PENDING" in result

    def test_compress_episodes(self):
        from clarvis.context.compressor import compress_episodes
        episodes = [
            {"outcome": "success", "task": "Fix bug", "lesson": "Test first", "valence": 0.8},
            {"outcome": "failure", "task": "Deploy", "lesson": "Check deps"},
        ]
        result = compress_episodes(episodes)
        assert "EPISODIC" in result
        assert "success" in result
        assert "failure" in result

    def test_compress_episodes_empty(self):
        from clarvis.context.compressor import compress_episodes
        assert compress_episodes([]) == ""

    def test_generate_tiered_brief_minimal(self):
        from clarvis.context.compressor import generate_tiered_brief
        brief = generate_tiered_brief("Test task", tier="minimal")
        assert "Test task" in brief
        # Minimal should not include queue
        assert "PENDING" not in brief

    def test_generate_tiered_brief_standard(self):
        from clarvis.context.compressor import generate_tiered_brief
        brief = generate_tiered_brief("Test task", tier="standard")
        assert "Test task" in brief

    def test_spine_init_exports(self):
        """Verify context __init__ exports compressor functions."""
        from clarvis.context import tfidf_extract, compress_text, mmr_rerank
        assert callable(tfidf_extract)

    def test_tokenize(self):
        from clarvis.context.compressor import _tokenize
        tokens = _tokenize("Hello World, this is a test of tokenization!")
        assert "hello" in tokens
        assert "tokenization" in tokens
        assert "this" not in tokens  # stopword

    def test_jaccard_similarity(self):
        from clarvis.context.compressor import _jaccard_similarity
        assert _jaccard_similarity(["a", "b", "c"], ["a", "b", "c"]) == 1.0
        assert _jaccard_similarity(["a", "b"], ["c", "d"]) == 0.0
        assert _jaccard_similarity([], []) == 0.0


# ===========================================================================
# 3. Brain Search Performance (clarvis.brain.search)
# ===========================================================================

class TestBrainSearchOptimizations:
    """Test brain search optimizations (result cache, parallel queries)."""

    @pytest.mark.slow
    def test_recall_cache_hit(self):
        """Repeated identical queries should hit the result cache."""
        from clarvis.brain import brain
        # First call — cold
        t0 = time.monotonic()
        r1 = brain.recall("test cache query", n=3)
        cold_ms = (time.monotonic() - t0) * 1000

        # Second call — should hit cache (< 1ms)
        t0 = time.monotonic()
        r2 = brain.recall("test cache query", n=3)
        hot_ms = (time.monotonic() - t0) * 1000

        assert hot_ms < cold_ms  # Cache should be faster
        assert len(r1) == len(r2)  # Same results

    @pytest.mark.slow
    def test_recall_returns_results(self):
        """Basic recall should return a list of result dicts."""
        from clarvis.brain import brain
        results = brain.recall("clarvis identity", n=3)
        assert isinstance(results, list)
        if results:
            assert "document" in results[0]
            assert "collection" in results[0]

    @pytest.mark.slow
    def test_recall_from_date_parallel(self):
        """recall_from_date should work (now parallelized)."""
        from clarvis.brain import brain
        results = brain.recall_from_date("2026-01-01", n=5)
        assert isinstance(results, list)


# ===========================================================================
# 4. Integration: Cron Wrap-Mode Smoke Test
# ===========================================================================

class TestCronWrapMode:
    """Integration tests for cron script interactions with spine."""

    def test_gate_check_sh_compatible(self):
        """The gate module output is JSON-parseable (same format as script)."""
        from clarvis.heartbeat.gate import run_gate
        decision, output = run_gate()
        # Verify output matches the JSON format cron_autonomous.sh expects
        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        assert "decision" in parsed
        assert "reason" in parsed
        assert "changes" in parsed

    def test_context_compressor_queue_format(self):
        """compress_queue output matches format expected by preflight."""
        from clarvis.context.compressor import compress_queue
        result = compress_queue()
        assert isinstance(result, str)
        # Should contain the expected section markers
        assert "QUEUE" in result or "No evolution" in result

    def test_heartbeat_runner_importable(self):
        """The heartbeat runner module imports without error."""
        from clarvis.heartbeat.runner import run_gate_check
        assert callable(run_gate_check)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not slow"])
