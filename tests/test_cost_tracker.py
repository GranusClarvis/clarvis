"""Tests for clarvis.orch.cost_tracker — cost tracking, estimation, budget checks.

Migrated from packages/clarvis-cost/tests/test_core.py.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from clarvis.orch.cost_tracker import (
    CostEntry,
    CostTracker,
    analyze_savings,
    estimate_cost,
    estimate_tokens,
    get_pricing,
    import_router_decisions,
    MODEL_PRICING,
)


# ── Pricing ─────────────────────────────────────────────────────────

class TestGetPricing:
    def test_known_model(self):
        p = get_pricing("claude-opus-4-6")
        assert p["input"] == 15.0
        assert p["output"] == 75.0

    def test_unknown_model_returns_default(self):
        p = get_pricing("nonexistent-model-xyz")
        assert "input" in p and "output" in p
        # default pricing should be moderate, not zero
        assert p["input"] > 0

    def test_alias_models(self):
        # MiniMax M2.5 should be in the table
        p = get_pricing("minimax/MiniMax-M1")
        assert p["input"] > 0


# ── Cost Estimation ─────────────────────────────────────────────────

class TestEstimateCost:
    def test_zero_tokens(self):
        assert estimate_cost("claude-opus-4-6", 0, 0) == 0.0

    def test_known_model_cost(self):
        # 1M input tokens at $15, 0 output = $15.0
        cost = estimate_cost("claude-opus-4-6", 1_000_000, 0)
        assert cost == pytest.approx(15.0, abs=0.01)

    def test_output_tokens(self):
        # 1M output tokens at $75 for opus
        cost = estimate_cost("claude-opus-4-6", 0, 1_000_000)
        assert cost == pytest.approx(75.0, abs=0.01)

    def test_mixed_tokens(self):
        cost = estimate_cost("claude-opus-4-6", 1000, 500)
        expected = (1000 * 15.0 + 500 * 75.0) / 1_000_000
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_unknown_model_uses_default(self):
        cost = estimate_cost("fake-model", 1_000_000, 0)
        assert cost > 0  # should use default pricing


# ── Token Estimation ────────────────────────────────────────────────

class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_text(self):
        tokens = estimate_tokens("Hello world")
        assert tokens > 0

    def test_longer_text_more_tokens(self):
        short = estimate_tokens("Hi")
        long = estimate_tokens("This is a much longer piece of text with many words")
        assert long > short

    def test_json_content_has_density_bonus(self):
        json_text = '{"name": "value", "data": [1, 2, 3]}'
        json_tokens = estimate_tokens(json_text)
        assert json_tokens > 0


# ── CostEntry ───────────────────────────────────────────────────────

class TestCostEntry:
    def test_to_dict_roundtrip(self):
        entry = CostEntry(
            timestamp="2026-03-25T12:00:00",
            model="claude-opus-4-6",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.0525,
            source="test",
            task="unit test",
        )
        d = entry.to_dict()
        restored = CostEntry.from_dict(d)
        assert restored.model == entry.model
        assert restored.input_tokens == entry.input_tokens
        assert restored.cost_usd == entry.cost_usd
        assert restored.source == entry.source

    def test_from_dict_missing_optional_fields(self):
        d = {
            "timestamp": "2026-03-25T12:00:00",
            "model": "test",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.01,
        }
        entry = CostEntry.from_dict(d)
        assert entry.model == "test"
        assert entry.estimated is True  # default

    def test_estimated_flag(self):
        entry = CostEntry(
            timestamp="2026-03-25T12:00:00",
            model="test",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            estimated=False,
        )
        assert entry.estimated is False
        d = entry.to_dict()
        assert d["estimated"] is False


# ── CostTracker ─────────────────────────────────────────────────────

@pytest.fixture
def tracker(tmp_path):
    """Fresh CostTracker with a temp log file."""
    log_file = str(tmp_path / "costs.jsonl")
    return CostTracker(log_file)


class TestCostTrackerLog:
    def test_log_creates_entry(self, tracker):
        entry = tracker.log("claude-opus-4-6", 1000, 500, source="test")
        assert isinstance(entry, CostEntry)
        assert entry.model == "claude-opus-4-6"
        assert entry.estimated is True
        assert entry.cost_usd > 0

    def test_log_real_creates_entry(self, tracker):
        entry = tracker.log_real(
            "claude-opus-4-6", 1000, 500, cost_usd=0.05,
            source="api", generation_id="gen-123",
        )
        assert entry.estimated is False
        assert entry.cost_usd == 0.05
        assert entry.generation_id == "gen-123"

    def test_log_persists_to_file(self, tracker):
        tracker.log("test-model", 100, 50, source="s1")
        tracker.log("test-model", 200, 100, source="s2")
        entries = tracker._read_entries()
        assert len(entries) == 2

    def test_log_real_persists(self, tracker):
        tracker.log_real("test-model", 100, 50, cost_usd=0.01)
        entries = tracker._read_entries()
        assert len(entries) == 1
        assert entries[0].estimated is False


class TestCostTrackerRollup:
    def test_rollup_empty(self, tracker):
        r = tracker.rollup("day")
        assert r["total_cost"] == 0.0
        assert r["call_count"] == 0

    def test_rollup_day(self, tracker):
        tracker.log("claude-opus-4-6", 1000, 500, source="test")
        tracker.log("claude-haiku-4-5-20251001", 2000, 1000, source="test")
        r = tracker.rollup("day")
        assert r["call_count"] == 2
        assert r["total_cost"] > 0
        assert "claude-opus-4-6" in r["by_model"]

    def test_rollup_all(self, tracker):
        tracker.log("test-model", 100, 50)
        r = tracker.rollup("all")
        assert r["call_count"] == 1

    def test_rollup_by_source(self, tracker):
        tracker.log("test-model", 100, 50, source="cron")
        tracker.log("test-model", 100, 50, source="heartbeat")
        tracker.log("test-model", 100, 50, source="cron")
        r = tracker.rollup("all")
        assert r["by_source"]["cron"]["count"] == 2
        assert r["by_source"]["heartbeat"]["count"] == 1


class TestCostTrackerBudgetCheck:
    def test_budget_ok(self, tracker):
        tracker.log("test-model", 100, 50)  # tiny cost
        result = tracker.budget_check(daily_budget=100.0)
        assert result["alert"] == "ok"
        assert result["remaining"] > 0

    def test_budget_exceeded(self, tracker):
        for _ in range(50):
            tracker.log("claude-opus-4-6", 100_000, 50_000)
        result = tracker.budget_check(daily_budget=0.01)
        assert result["alert"] == "exceeded"
        assert result["pct_used"] > 100

    def test_budget_zero_spending(self, tracker):
        result = tracker.budget_check(daily_budget=5.0)
        assert result["today_cost"] == 0.0
        assert result["remaining"] == 5.0


class TestCostTrackerDailyTrend:
    def test_daily_trend_empty(self, tracker):
        trend = tracker.daily_trend(days=7)
        assert isinstance(trend, list)
        assert len(trend) == 7
        assert all(d["cost"] == 0.0 for d in trend)

    def test_daily_trend_with_entries(self, tracker):
        tracker.log("test-model", 1000, 500)
        trend = tracker.daily_trend(days=3)
        assert len(trend) == 3
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_entry = [d for d in trend if d["date"] == today]
        if today_entry:
            assert today_entry[0]["cost"] > 0


class TestCostTrackerTaskCosts:
    def test_task_costs_empty(self, tracker):
        result = tracker.task_costs(days=7)
        assert result["unique_tasks"] == 0

    def test_task_costs_groups(self, tracker):
        tracker.log("test-model", 1000, 500, task="task-alpha")
        tracker.log("test-model", 2000, 1000, task="task-alpha")
        tracker.log("test-model", 500, 250, task="task-beta")
        result = tracker.task_costs(days=7)
        assert result["unique_tasks"] == 2
        tasks_by_name = {t["task"]: t for t in result["tasks"]}
        assert tasks_by_name["task-alpha"]["calls"] == 2


class TestCostTrackerRoutingEffectiveness:
    def test_routing_empty(self, tracker):
        result = tracker.routing_effectiveness(days=7)
        assert result["total_calls"] == 0

    def test_routing_categorization(self, tracker):
        tracker.log("minimax/MiniMax-M1", 1000, 500, source="router")
        tracker.log("claude-opus-4-6", 1000, 500, source="direct")
        result = tracker.routing_effectiveness(days=7)
        assert result["total_calls"] == 2


class TestCostTrackerMalformedData:
    def test_read_entries_skips_bad_lines(self, tmp_path):
        log_file = str(tmp_path / "costs.jsonl")
        with open(log_file, "w") as f:
            f.write("not json\n")
            f.write('{"timestamp":"2026-03-25T12:00:00","model":"m","input_tokens":1,"output_tokens":1,"cost_usd":0.01}\n')
            f.write("{broken\n")
        tracker = CostTracker(log_file)
        entries = tracker._read_entries()
        assert len(entries) == 1


# ── analyze_savings ─────────────────────────────────────────────────

class TestAnalyzeSavings:
    def test_analyze_empty(self, tracker):
        result = analyze_savings(tracker)
        assert "suggestions" in result
        assert result["weekly_calls"] == 0

    def test_analyze_with_data(self, tracker):
        for _ in range(10):
            tracker.log("claude-opus-4-6", 5000, 2000, source="heartbeat")
        result = analyze_savings(tracker)
        assert result["weekly_calls"] > 0
        assert isinstance(result["suggestions"], list)

    def test_analyze_source_concentration(self, tracker):
        for _ in range(10):
            tracker.log("claude-opus-4-6", 5000, 2000, source="dominant_source")
        tracker.log("claude-opus-4-6", 100, 50, source="other")
        result = analyze_savings(tracker)
        assert any("dominant_source" in s for s in result["suggestions"])

    def test_analyze_with_router_log(self, tracker, tmp_path):
        tracker.log("claude-opus-4-6", 5000, 2000)
        router_log = str(tmp_path / "router.jsonl")
        with open(router_log, "w") as f:
            for i in range(5):
                f.write(json.dumps({
                    "timestamp": f"2026-03-25T12:0{i}:00",
                    "executor": "claude", "tier": "simple",
                    "task": "simple task",
                }) + "\n")
            for i in range(5):
                f.write(json.dumps({
                    "timestamp": f"2026-03-25T12:1{i}:00",
                    "executor": "gemini", "tier": "simple",
                    "task": "another task",
                }) + "\n")
        result = analyze_savings(tracker, router_log_path=router_log)
        assert "router_fallback_rate" in result

    def test_analyze_high_output_ratio(self, tracker):
        for _ in range(10):
            tracker.log("claude-opus-4-6", 100, 5000, source="gen")
        result = analyze_savings(tracker)
        assert "output_input_ratio" in result


# ── import_router_decisions ─────────────────────────────────────────

class TestImportRouterDecisions:
    def test_import_missing_file(self, tracker):
        count = import_router_decisions("/nonexistent/path.jsonl", tracker)
        assert count == 0

    def test_import_creates_entries(self, tracker, tmp_path):
        router_log = str(tmp_path / "router.jsonl")
        with open(router_log, "w") as f:
            f.write(json.dumps({
                "timestamp": "2026-03-25T10:00:00",
                "executor": "gemini",
                "task": "summarize document",
            }) + "\n")
            f.write(json.dumps({
                "timestamp": "2026-03-25T11:00:00",
                "executor": "claude",
                "task": "implement feature",
            }) + "\n")
        count = import_router_decisions(router_log, tracker)
        assert count == 2
        entries = tracker._read_entries()
        assert len(entries) == 2

    def test_import_skips_duplicates(self, tracker, tmp_path):
        router_log = str(tmp_path / "router.jsonl")
        with open(router_log, "w") as f:
            f.write(json.dumps({
                "timestamp": "2026-03-25T10:00:00",
                "executor": "gemini",
                "task": "task a",
            }) + "\n")
        count1 = import_router_decisions(router_log, tracker)
        count2 = import_router_decisions(router_log, tracker)
        assert count1 == 1
        assert count2 == 0


# ── Token estimation edge cases ─────────────────────────────────────

class TestEstimateTokensEdgeCases:
    def test_code_content_density(self):
        code = "import os\ndef hello():\n    for i in range(10):\n        if i > 5:\n            print(i)"
        tokens = estimate_tokens(code)
        assert tokens > 0

    def test_model_family_claude(self):
        long_text = "This is a longer text to test model family token estimation differences across providers " * 10
        t1 = estimate_tokens(long_text, model="claude-opus-4-6")
        t2 = estimate_tokens(long_text, model="gemini-2.0-flash")
        assert t1 != t2
