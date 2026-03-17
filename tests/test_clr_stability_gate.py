from __future__ import annotations

from clarvis.metrics.clr import evaluate_clr_stability


def _entry(clr: float, i: int) -> dict:
    return {
        "timestamp": f"2026-03-{i + 1:02d}T00:00:00+00:00",
        "clr": clr,
    }


def test_clr_stability_passes_for_stable_window():
    entries = [_entry(0.52 + (i % 3) * 0.005, i) for i in range(14)]
    gate = evaluate_clr_stability(entries=entries, min_runs=14, max_stddev=0.05, max_regression=0.1)
    assert gate["pass"] is True
    assert gate["failures"] == []
    assert gate["stats"]["runs"] == 14


def test_clr_stability_fails_on_insufficient_runs():
    entries = [_entry(0.5, i) for i in range(5)]
    gate = evaluate_clr_stability(entries=entries, min_runs=14)
    assert gate["pass"] is False
    assert any("insufficient_runs" in f for f in gate["failures"])


def test_clr_stability_fails_on_high_volatility():
    entries = [_entry(0.2 if i % 2 == 0 else 0.8, i) for i in range(14)]
    gate = evaluate_clr_stability(entries=entries, min_runs=14, max_stddev=0.1)
    assert gate["pass"] is False
    assert any("stddev>" in f for f in gate["failures"])
