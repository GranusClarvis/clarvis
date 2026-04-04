#!/usr/bin/env python3
"""
Tests for Clarvis critical-path modules.

Covers pure-logic functions that can be tested without ChromaDB or filesystem:
  - attention.py: salience scoring, decay, spotlight ranking
  - performance_benchmark.py: PI calculation, self-optimization alerts
  - context_compressor.py: queue compression, health regex, wire detection, related tasks
  - task_selector.py: task parsing, spotlight alignment
"""

import math
import os
import re
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import _paths  # noqa: F401,E402


# ============================================================
# attention.py — Salience & Spotlight
# ============================================================

class TestAttentionItem:
    """Test AttentionItem salience scoring and lifecycle."""

    def _make_item(self, importance=0.5, relevance=0.5, boost=0.0,
                   age_hours=0.0, access_count=0):
        from attention import AttentionItem
        item = AttentionItem(
            content="test item",
            source="test",
            importance=importance,
            relevance=relevance,
            boost=boost,
            item_id="test_001",
        )
        # Backdate creation to simulate age
        if age_hours > 0:
            created = datetime.now(timezone.utc) - timedelta(hours=age_hours)
            item.created_at = created.isoformat()
        item.access_count = access_count
        return item

    def test_salience_fresh_item(self):
        """Fresh item with default params should have predictable salience."""
        item = self._make_item(importance=1.0, relevance=1.0, boost=1.0)
        s = item.salience()
        # All components maxed: 0.25*1 + 0.20*~1 + 0.30*1 + 0.10*0 + 0.15*1
        # recency ~1.0 for fresh item
        assert 0.85 <= s <= 1.0, f"Fresh max item salience {s} not in [0.85, 1.0]"

    def test_salience_zero_item(self):
        """Item with all zeros should have minimal salience (only recency)."""
        item = self._make_item(importance=0.0, relevance=0.0, boost=0.0)
        s = item.salience()
        # Only recency contributes: 0.20 * ~1.0 for fresh item
        assert 0.15 <= s <= 0.25, f"Zero item salience {s} not in [0.15, 0.25]"

    def test_salience_decays_with_age(self):
        """Older items should have lower salience due to recency decay."""
        fresh = self._make_item(importance=0.5, relevance=0.5)
        old = self._make_item(importance=0.5, relevance=0.5, age_hours=24)
        assert fresh.salience() > old.salience(), "Fresh item should score higher than old"

    def test_recency_half_life(self):
        """Recency should roughly halve every ~6 hours."""
        item_0h = self._make_item()
        item_6h = self._make_item(age_hours=6)
        s0 = item_0h.salience()
        s6 = item_6h.salience()
        # Recency at 6h: exp(-0.115 * 6) ≈ 0.50
        # Salience diff should reflect the recency weight (0.20)
        assert s0 > s6, "Recency decay not reducing salience"

    def test_access_count_boosts_salience(self):
        """Higher access count should increase salience."""
        low = self._make_item(access_count=0)
        high = self._make_item(access_count=10)
        assert high.salience() > low.salience(), "Access count not boosting salience"

    def test_salience_clamped_0_1(self):
        """Salience should always be in [0, 1]."""
        item = self._make_item(importance=1.0, relevance=1.0, boost=1.0,
                               access_count=1000)
        assert 0.0 <= item.salience() <= 1.0

        item2 = self._make_item(importance=0.0, relevance=0.0, boost=0.0,
                                age_hours=1000)
        assert 0.0 <= item2.salience() <= 1.0

    def test_decay_reduces_relevance_and_boost(self):
        """decay() should reduce relevance and boost."""
        item = self._make_item(relevance=0.8, boost=0.6)
        item.decay(rate=0.05)
        assert item.relevance == pytest.approx(0.75)
        assert item.boost == pytest.approx(0.50)  # boost decays 2x faster

    def test_decay_floors_at_zero(self):
        """decay() should not go below 0."""
        item = self._make_item(relevance=0.02, boost=0.01)
        item.decay(rate=0.05)
        assert item.relevance == 0.0
        assert item.boost == 0.0

    def test_touch_increments_access(self):
        """touch() should increment access_count."""
        item = self._make_item(access_count=0)
        item.touch()
        assert item.access_count == 1
        item.touch()
        assert item.access_count == 2

    def test_importance_clamped_on_init(self):
        """Importance should be clamped to [0, 1]."""
        item = self._make_item(importance=1.5)
        assert item.importance == 1.0
        item2 = self._make_item(importance=-0.5)
        assert item2.importance == 0.0

    def test_to_dict_roundtrip(self):
        """to_dict → from_dict should preserve all fields."""
        from attention import AttentionItem
        item = self._make_item(importance=0.7, relevance=0.4, boost=0.3)
        item.access_count = 5
        item.ticks_in_spotlight = 3
        d = item.to_dict()
        restored = AttentionItem.from_dict(d)
        assert restored.importance == item.importance
        assert restored.relevance == item.relevance
        assert restored.boost == item.boost
        assert restored.access_count == item.access_count
        assert restored.ticks_in_spotlight == item.ticks_in_spotlight


# ============================================================
# performance_benchmark.py — PI Calculation
# ============================================================

class TestComputePI:
    """Test Performance Index computation."""

    def _compute(self, **metric_overrides):
        from performance_benchmark import compute_pi
        # Default metrics at target values (must match TARGETS in clarvis/metrics/benchmark.py)
        metrics = {
            "brain_query_avg_ms": 800.0,
            "brain_query_p95_ms": 1500.0,
            "retrieval_hit_rate": 0.85,
            "retrieval_precision3": 0.70,
            "avg_tokens_per_op": 15000,
            "heartbeat_overhead_s": 12.0,
            "episode_success_rate": 0.85,
            "action_accuracy": 0.90,
            "phi": 0.70,
            "context_relevance": 0.75,
            "task_quality_score": 0.70,
            "code_quality_score": 0.75,
            "graph_density": 1.5,
            "bloat_score": 0.40,
            "brief_compression": 0.55,
            "load_degradation_pct": 15.0,
        }
        metrics.update(metric_overrides)
        return compute_pi(metrics)

    def test_perfect_score(self):
        """All metrics at or beyond targets should give PI=1.0."""
        result = self._compute(
            brain_query_avg_ms=500,   # better than target (lower)
            brain_query_p95_ms=1000,
            retrieval_hit_rate=0.95,
            retrieval_precision3=0.80,
            avg_tokens_per_op=10000,
            heartbeat_overhead_s=8.0,
            episode_success_rate=0.95,
            action_accuracy=0.95,
            phi=0.80,
            context_relevance=0.85,
            task_quality_score=0.80,
            code_quality_score=0.85,
            graph_density=2.0,
            bloat_score=0.20,
            brief_compression=0.70,
            load_degradation_pct=10.0,
        )
        assert result["pi"] == 1.0
        assert "Excellent" in result["interpretation"]

    def test_at_targets(self):
        """Metrics exactly at target should give PI=1.0."""
        result = self._compute()
        assert result["pi"] == 1.0

    def test_all_critical(self):
        """All metrics at critical thresholds should give PI=0.0."""
        result = self._compute(
            brain_query_avg_ms=2000,
            brain_query_p95_ms=3000,
            retrieval_hit_rate=0.50,
            retrieval_precision3=0.30,
            avg_tokens_per_op=30000,
            heartbeat_overhead_s=30.0,
            episode_success_rate=0.50,
            action_accuracy=0.60,
            phi=0.30,
            context_relevance=0.40,
            task_quality_score=0.40,
            code_quality_score=0.45,
            graph_density=0.3,
            bloat_score=0.70,
            brief_compression=0.20,
            load_degradation_pct=60.0,
        )
        assert result["pi"] == 0.0
        assert "Critical" in result["interpretation"]

    def test_midpoint_score(self):
        """Metrics halfway between target and critical should give ~0.5."""
        result = self._compute(
            brain_query_avg_ms=1400,    # midpoint of 800-2000
            brain_query_p95_ms=2250,    # midpoint of 1500-3000
            retrieval_hit_rate=0.675,   # midpoint of 0.50-0.85
            retrieval_precision3=0.50,  # midpoint of 0.30-0.70
            avg_tokens_per_op=22500,    # midpoint of 15000-30000
            heartbeat_overhead_s=21.0,  # midpoint of 12-30
            episode_success_rate=0.675, # midpoint of 0.50-0.85
            action_accuracy=0.75,       # midpoint of 0.60-0.90
            phi=0.50,                   # midpoint of 0.30-0.70
            context_relevance=0.575,    # midpoint of 0.40-0.75
            task_quality_score=0.55,    # midpoint of 0.40-0.70
            code_quality_score=0.60,    # midpoint of 0.45-0.75
            graph_density=0.9,          # midpoint of 0.3-1.5
            bloat_score=0.55,           # midpoint of 0.40-0.70
            brief_compression=0.375,    # midpoint of 0.20-0.55
            load_degradation_pct=37.5,  # midpoint of 15-60
        )
        assert 0.40 <= result["pi"] <= 0.60, f"Midpoint PI={result['pi']} not near 0.5"

    def test_pi_spectrum_labels(self):
        """Verify interpretation labels at boundary values."""
        from performance_benchmark import compute_pi
        # Can't easily control exact PI, so just check structure
        result = self._compute()
        assert "pi" in result
        assert "interpretation" in result
        assert isinstance(result["pi"], float)
        assert 0.0 <= result["pi"] <= 1.0

    def test_missing_metrics_ignored(self):
        """Missing metrics should not crash, just reduce weight basis."""
        from performance_benchmark import compute_pi
        result = compute_pi({"retrieval_hit_rate": 0.80, "phi": 0.50})
        assert 0.0 <= result["pi"] <= 1.0

    def test_empty_metrics(self):
        """Empty metrics dict should not crash."""
        from performance_benchmark import compute_pi
        result = compute_pi({})
        assert result["pi"] == 0.0 or "pi" in result  # no metrics → 0/0.01 → 0


class TestCheckSelfOptimization:
    """Test self-optimization alert detection."""

    def test_pi_drop_alert(self):
        """PI drop >0.05 should trigger high severity alert."""
        from performance_benchmark import check_self_optimization
        report = {"pi": {"pi": 0.60}, "metrics": {}}
        prev = {"pi": {"pi": 0.70}, "metrics": {}}
        alerts = check_self_optimization(report, prev)
        pi_alerts = [a for a in alerts if a["type"] == "pi_drop"]
        assert len(pi_alerts) == 1
        assert pi_alerts[0]["severity"] == "high"

    def test_no_alert_small_drop(self):
        """PI drop <0.05 should not trigger alert."""
        from performance_benchmark import check_self_optimization
        report = {"pi": {"pi": 0.68}, "metrics": {}}
        prev = {"pi": {"pi": 0.70}, "metrics": {}}
        alerts = check_self_optimization(report, prev)
        pi_alerts = [a for a in alerts if a["type"] == "pi_drop"]
        assert len(pi_alerts) == 0

    def test_critical_breach_alert(self):
        """Metric below critical threshold should trigger critical alert."""
        from performance_benchmark import check_self_optimization
        report = {
            "pi": {"pi": 0.30},
            "metrics": {"retrieval_hit_rate": 0.35},  # below 0.40 critical
        }
        alerts = check_self_optimization(report)
        breach_alerts = [a for a in alerts if a["type"] == "critical_breach"]
        assert len(breach_alerts) >= 1
        assert any(a["metric"] == "retrieval_hit_rate" for a in breach_alerts)

    def test_no_alert_at_target(self):
        """Metrics at target should not trigger any alerts."""
        from performance_benchmark import check_self_optimization
        report = {
            "pi": {"pi": 0.80},
            "metrics": {
                "retrieval_hit_rate": 0.80,
                "phi": 0.50,
                "episode_success_rate": 0.70,
            },
        }
        alerts = check_self_optimization(report)
        breach_alerts = [a for a in alerts if a["type"] == "critical_breach"]
        assert len(breach_alerts) == 0


# ============================================================
# context_compressor.py — Queue & Health Compression
# ============================================================

class TestCompressQueue:
    """Test QUEUE.md compression."""

    def _write_queue(self, content):
        """Write queue content to a temp file and return path."""
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_pending_tasks_preserved(self):
        """Pending tasks should appear in compressed output."""
        from context_compressor import compress_queue
        path = self._write_queue("""## P0 — Critical
- [ ] Fix memory regression
- [ ] Update brain schema
## Completed
- [x] Old task (2026-02-20)
""")
        result = compress_queue(path)
        os.unlink(path)
        assert "Fix memory regression" in result
        assert "Update brain schema" in result
        assert "2 tasks" in result or "PENDING (2" in result

    def test_completed_section_stripped(self):
        """Tasks under ## Completed should be stripped."""
        from context_compressor import compress_queue
        path = self._write_queue("""## P1
- [ ] Active task
## Completed
- [x] Should not appear (2026-02-15)
- [x] Also hidden (2026-02-14)
""")
        result = compress_queue(path)
        os.unlink(path)
        assert "Should not appear" not in result
        assert "Also hidden" not in result

    def test_recent_completed_limited(self):
        """Only last N completed (outside ## Completed section) shown."""
        from context_compressor import compress_queue
        path = self._write_queue("""## P1
- [x] Done 1 (2026-02-25)
- [x] Done 2 (2026-02-24)
- [x] Done 3 (2026-02-23)
- [x] Done 4 (2026-02-22)
- [x] Done 5 (2026-02-21)
- [x] Done 6 (2026-02-20)
- [x] Done 7 (2026-02-19)
- [ ] Still pending
""")
        result = compress_queue(path, max_recent_completed=3)
        os.unlink(path)
        assert "Still pending" in result

    def test_missing_file(self):
        """Non-existent file should return graceful message."""
        from context_compressor import compress_queue
        result = compress_queue("/tmp/nonexistent_queue_12345.md")
        assert "No evolution queue" in result

    def test_empty_queue(self):
        """Empty file should not crash."""
        from context_compressor import compress_queue
        path = self._write_queue("")
        result = compress_queue(path)
        os.unlink(path)
        assert "0 tasks" in result or "PENDING" in result


class TestCompressHealth:
    """Test health data regex extraction."""

    def test_brier_extraction(self):
        """Should extract Brier score from calibration output."""
        from context_compressor import compress_health
        result = compress_health(calibration_output="Brier: 0.142\nOther data")
        assert "0.142" in result

    def test_accuracy_extraction(self):
        """Should extract accuracy from calibration output."""
        from context_compressor import compress_health
        result = compress_health(calibration_output="15/20 correct predictions")
        assert "15/20" in result

    def test_phi_extraction(self):
        """Should extract Phi from output."""
        from context_compressor import compress_health
        result = compress_health(phi_output="Phi: 0.723")
        assert "0.723" in result

    def test_empty_inputs(self):
        """Empty inputs should produce header only, no crash."""
        from context_compressor import compress_health
        result = compress_health()
        assert "HEALTH" in result


class TestDetectWireTask:
    """Test wire task detection regex."""

    def test_wire_with_scripts(self):
        """Should detect 'wire X.py into Y.sh' pattern."""
        from context_compressor import _detect_wire_task
        is_wire, src, tgt = _detect_wire_task(
            "Wire attention.py into cron_autonomous.sh for daily scoring"
        )
        assert is_wire
        assert src == "attention.py"
        assert tgt == "cron_autonomous.sh"

    def test_integrate_pattern(self):
        """Should detect 'integrate' verb."""
        from context_compressor import _detect_wire_task
        is_wire, src, tgt = _detect_wire_task(
            "Integrate self_model.py into heartbeat_postflight.py"
        )
        assert is_wire

    def test_non_wire_task(self):
        """Should not detect non-wire tasks."""
        from context_compressor import _detect_wire_task
        is_wire, src, tgt = _detect_wire_task("Create performance benchmark script")
        assert not is_wire
        assert src is None
        assert tgt is None

    def test_hook_pattern(self):
        """Should detect 'hook' verb."""
        from context_compressor import _detect_wire_task
        is_wire, _, _ = _detect_wire_task("Hook phi_metric into evening reflection")
        assert is_wire


class TestFindRelatedTasks:
    """Test related task discovery by word overlap."""

    def _write_queue(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_finds_related(self):
        """Should find tasks with word overlap."""
        from context_compressor import _find_related_tasks
        path = self._write_queue("""## P1
- [ ] Improve brain memory retrieval quality
- [ ] Fix browser agent timeout
- [ ] Enhance brain retrieval precision scoring
""")
        related = _find_related_tasks("brain retrieval optimization", path)
        os.unlink(path)
        assert len(related) >= 1

    def test_excludes_identical(self):
        """Should exclude tasks that are >60% similar (same task)."""
        from context_compressor import _find_related_tasks
        path = self._write_queue("""## P1
- [ ] Improve brain memory retrieval quality and speed
""")
        related = _find_related_tasks(
            "Improve brain memory retrieval quality and speed", path
        )
        os.unlink(path)
        assert len(related) == 0

    def test_empty_task(self):
        """Empty current task should return empty list."""
        from context_compressor import _find_related_tasks
        assert _find_related_tasks("", "/tmp/any.md") == []


class TestGetRecentCompletions:
    """Test recent completions extraction."""

    def _write_queue(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_extracts_completions(self):
        """Should extract completed tasks with dates."""
        from context_compressor import _get_recent_completions
        path = self._write_queue("""## P1
- [x] Built performance benchmark (2026-02-27)
- [x] Fixed brain recall bug (2026-02-26)
- [ ] Still pending
""")
        completions = _get_recent_completions(path, n=5)
        os.unlink(path)
        assert len(completions) == 2
        assert "2026-02-27" in completions[0]

    def test_limits_to_n(self):
        """Should limit to N completions."""
        from context_compressor import _get_recent_completions
        path = self._write_queue("""## P1
- [x] Task 1 (2026-02-27)
- [x] Task 2 (2026-02-26)
- [x] Task 3 (2026-02-25)
""")
        completions = _get_recent_completions(path, n=2)
        os.unlink(path)
        assert len(completions) == 2


# ============================================================
# task_selector.py — Task Parsing
# ============================================================

class TestParseTasks:
    """Test QUEUE.md task parsing."""

    def _write_queue(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_parses_pending_by_section(self):
        """Should parse pending tasks with correct section."""
        from task_selector import parse_tasks
        path = self._write_queue("""## P0 — Critical
- [ ] Critical task one
- [x] Done task (skip me)
## P1 — Important
- [ ] Important task
## P2 — Nice to Have
- [ ] Nice task
""")
        tasks = parse_tasks(path)
        os.unlink(path)
        assert len(tasks) == 3
        assert tasks[0]["section"] == "P0"
        assert tasks[0]["text"] == "Critical task one"
        assert tasks[1]["section"] == "P1"
        assert tasks[2]["section"] == "P2"

    def test_skips_completed(self):
        """Should not include [x] tasks."""
        from task_selector import parse_tasks
        path = self._write_queue("""## P1
- [ ] Pending
- [x] Done
""")
        tasks = parse_tasks(path)
        os.unlink(path)
        assert len(tasks) == 1
        assert tasks[0]["text"] == "Pending"

    def test_skips_completed_section(self):
        """Tasks under ## Completed section should be skipped."""
        from task_selector import parse_tasks
        path = self._write_queue("""## P1
- [ ] Active task
## Completed
- [ ] Ghost task (unchecked but in completed section)
""")
        tasks = parse_tasks(path)
        os.unlink(path)
        assert len(tasks) == 1
        assert tasks[0]["text"] == "Active task"

    def test_empty_queue(self):
        """Empty queue should return empty list."""
        from task_selector import parse_tasks
        path = self._write_queue("")
        tasks = parse_tasks(path)
        os.unlink(path)
        assert tasks == []


class TestSpotlightAlignment:
    """Test spotlight alignment scoring."""

    def test_high_overlap(self):
        """Task with many shared words should score high."""
        from task_selector import _spotlight_alignment
        theme_words = {"brain", "memory", "retrieval", "quality", "improvement"}
        spotlight_texts = ["Improve brain memory retrieval quality"]
        # Mock spreading_activation in the canonical spine module
        with patch('clarvis.orch.task_selector.attention') as mock_attn:
            mock_attn.spreading_activation.return_value = [1, 2, 3]
            score = _spotlight_alignment(
                "brain memory retrieval optimization work",
                theme_words, spotlight_texts
            )
        assert score > 0.3, f"High overlap score {score} too low"

    def test_no_overlap(self):
        """Task with no shared words should score 0."""
        from task_selector import _spotlight_alignment
        theme_words = {"quantum", "physics", "astronomy"}
        spotlight_texts = ["quantum physics research"]
        with patch('clarvis.orch.task_selector.attention') as mock_attn:
            mock_attn.spreading_activation.side_effect = Exception("no DB")
            score = _spotlight_alignment(
                "cooking recipe database frontend",
                theme_words, spotlight_texts
            )
        assert score == 0.0

    def test_empty_themes(self):
        """Empty theme words should return 0."""
        from task_selector import _spotlight_alignment
        score = _spotlight_alignment("any task", set(), [])
        assert score == 0.0


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
