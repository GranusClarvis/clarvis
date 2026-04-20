"""Tests for cost_dashboard.py — unified cost dashboard."""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

# Ensure workspace is resolvable
os.environ.setdefault(
    "CLARVIS_WORKSPACE",
    os.path.join(os.path.dirname(__file__), ".."),
)

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "infra"))

import cost_dashboard as cd
from clarvis.orch.cost_tracker import CostTracker


@pytest.fixture
def tmp_cost_log(tmp_path):
    log = tmp_path / "costs.jsonl"
    now = datetime.now(timezone.utc)
    entries = [
        {
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "model": "claude-code",
            "input_tokens": 5000,
            "output_tokens": 1000,
            "cost_usd": 0.15,
            "source": "cron_autonomous",
            "task": "test task anthropic",
            "duration_s": 60.0,
            "estimated": False,
        },
        {
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "model": "claude-code",
            "input_tokens": 3000,
            "output_tokens": 500,
            "cost_usd": 0.08,
            "source": "spawn_claude",
            "task": "test task anthropic 2",
            "duration_s": 30.0,
            "estimated": True,
        },
        {
            "timestamp": now.isoformat(),
            "model": "minimax/minimax-m2.5",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cost_usd": 0.001,
            "source": "task_router",
            "task": "test openrouter task",
            "duration_s": 5.0,
            "estimated": False,
        },
    ]
    with open(log, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return str(log)


def test_is_anthropic():
    assert cd._is_anthropic("claude-code")
    assert cd._is_anthropic("claude-opus-4-6")
    assert cd._is_anthropic("anthropic/claude-sonnet-4-6")
    assert not cd._is_anthropic("minimax/minimax-m2.5")
    assert not cd._is_anthropic("glm-5")


def test_classify(tmp_cost_log):
    with patch.object(cd, "COST_LOG", tmp_cost_log):
        entries = cd._load_entries(1)
        classified = cd._classify(entries)
        assert len(classified["anthropic"]) == 2
        assert len(classified["openrouter"]) == 1


def test_provider_stats(tmp_cost_log):
    with patch.object(cd, "COST_LOG", tmp_cost_log):
        entries = cd._load_entries(1)
        classified = cd._classify(entries)
        stats = cd._provider_stats(classified["anthropic"])
        assert stats["calls"] == 2
        assert stats["real_count"] == 1
        assert stats["estimated_count"] == 1
        assert stats["total_cost"] == round(0.15 + 0.08, 4)


def test_build_dashboard(tmp_cost_log):
    with patch.object(cd, "COST_LOG", tmp_cost_log), \
         patch.object(cd, "fetch_usage", side_effect=RuntimeError("401")):
        dash = cd.build_dashboard(1)
        assert dash["unified"]["total_calls"] == 3
        assert dash["unified"]["real_entries"] == 2
        assert dash["anthropic"]["calls"] == 2
        assert dash["openrouter"]["calls"] == 1
        assert dash["openrouter_live"] is None
        assert len(dash["trend_7d"]) == 1


def test_build_dashboard_with_live_api(tmp_cost_log):
    mock_live = {"daily": 0.5, "weekly": 2.0, "monthly": 8.0,
                 "total": 20.0, "limit": 100.0, "remaining": 80.0,
                 "is_free_tier": False}
    with patch.object(cd, "COST_LOG", tmp_cost_log), \
         patch.object(cd, "fetch_usage", return_value=mock_live):
        dash = cd.build_dashboard(1)
        assert dash["openrouter_live"] == mock_live


def test_daily_trend_by_provider(tmp_cost_log):
    with patch.object(cd, "COST_LOG", tmp_cost_log):
        entries = cd._load_entries(1)
        trend = cd._daily_trend_by_provider(entries, 1)
        assert len(trend) == 1
        today = trend[0]
        assert today["anthropic"] > 0
        assert today["openrouter"] > 0
        assert abs(today["total"] - (today["anthropic"] + today["openrouter"])) < 0.001
