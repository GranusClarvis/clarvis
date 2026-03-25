"""Tests for clarvis_cost.optimizer — caching, budget planning, waste detection."""

import json
import time

import pytest

from clarvis_cost.optimizer import (
    ContextBudgetPlanner,
    PromptCache,
    compression_ratio_report,
    detect_prompt_waste,
)


# ── PromptCache ─────────────────────────────────────────────────────

@pytest.fixture
def cache(tmp_path):
    return PromptCache(str(tmp_path / "cache.json"), ttl_seconds=60)


class TestPromptCache:
    def test_put_and_get(self, cache):
        cache.put("What is 2+2?", "gpt", "4", input_tokens=10)
        result = cache.get("What is 2+2?", "gpt")
        assert result == "4"

    def test_miss_returns_none(self, cache):
        assert cache.get("unknown prompt", "gpt") is None

    def test_different_models_different_keys(self, cache):
        cache.put("prompt", "model-a", "answer-a", input_tokens=5)
        cache.put("prompt", "model-b", "answer-b", input_tokens=5)
        assert cache.get("prompt", "model-a") == "answer-a"
        assert cache.get("prompt", "model-b") == "answer-b"

    def test_stats(self, cache):
        cache.put("p1", "m", "r1", input_tokens=100)
        cache.put("p2", "m", "r2", input_tokens=200)
        cache.get("p1", "m")  # hit
        cache.get("p1", "m")  # hit
        s = cache.stats()
        assert s["entries"] == 2
        assert s["total_hits"] >= 2
        assert s["tokens_saved_by_cache"] >= 100

    def test_ttl_expiry(self, tmp_path):
        cache = PromptCache(str(tmp_path / "cache.json"), ttl_seconds=1)
        cache.put("prompt", "model", "response", input_tokens=10)
        assert cache.get("prompt", "model") == "response"
        time.sleep(1.5)
        assert cache.get("prompt", "model") is None


# ── ContextBudgetPlanner ────────────────────────────────────────────

class TestContextBudgetPlanner:
    def test_allocate_under_budget(self):
        planner = ContextBudgetPlanner(max_context=200_000)
        components = {
            "system_prompt": "You are a helpful assistant.",
            "task": "Summarize this document.",
        }
        result = planner.allocate(components)
        assert "system_prompt" in result
        assert "task" in result
        assert "_total" in result
        assert result["_total"]["utilization_pct"] < 100

    def test_allocate_empty_components(self):
        planner = ContextBudgetPlanner(max_context=200_000)
        result = planner.allocate({})
        assert "_total" in result

    def test_over_budget_detection(self):
        planner = ContextBudgetPlanner(max_context=100)  # tiny context
        # Default budget for unknown component is 2000 tokens;
        # need text that estimates > 2000 tokens (~7600+ chars at 3.8 chars/token)
        big_text = "word " * 5000
        result = planner.allocate({"big": big_text})
        assert result["big"]["over_budget"] is True
        assert result["big"]["action"] in ("trim", "compress", "compress_aggressively")


# ── detect_prompt_waste ─────────────────────────────────────────────

class TestDetectPromptWaste:
    def test_clean_prompt(self):
        result = detect_prompt_waste("This is a clean prompt with no waste.")
        assert result["estimated_waste_tokens"] == 0
        assert len(result["issues"]) == 0

    def test_repeated_lines(self):
        prompt = ("Do this task now please.\n" * 10)
        result = detect_prompt_waste(prompt)
        assert result["estimated_waste_tokens"] > 0
        assert any("duplicate" in i.lower() for i in result["issues"])

    def test_excessive_blank_lines(self):
        prompt = "Start\n\n\n\n\n\n\nEnd"
        result = detect_prompt_waste(prompt)
        assert any("blank" in i.lower() for i in result["issues"])

    def test_long_lines(self):
        prompt = "x" * 3000
        result = detect_prompt_waste(prompt)
        assert any("long" in i.lower() for i in result["issues"])


# ── compression_ratio_report ────────────────────────────────────────

class TestCompressionRatioReport:
    def test_perfect_compression(self):
        result = compression_ratio_report("a" * 1000, "")
        assert result["reduction_pct"] == 100.0

    def test_no_compression(self):
        text = "hello world"
        result = compression_ratio_report(text, text)
        assert result["reduction_pct"] == 0.0
        assert result["tokens_saved"] == 0

    def test_partial_compression(self):
        raw = "word " * 100
        compressed = "word " * 30
        result = compression_ratio_report(raw, compressed)
        assert 0 < result["reduction_pct"] < 100
        assert result["tokens_saved"] > 0
        assert result["raw_tokens"] > result["compressed_tokens"]
