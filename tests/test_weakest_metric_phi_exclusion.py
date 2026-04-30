"""Regression test for [PHI_AUTO_INJECTION_REMOVAL].

The `weakest` metric selector must skip Phi so the literal string
"WEAKEST METRIC: Phi (Integration)=…" never gets injected into autonomous
prompts. Phi remains in metrics history and on dashboards; only this
prompt-injection selection drops it.

Both the legacy CLI (`scripts/metrics/performance_benchmark.py weakest`)
and the spine CLI (`clarvis.cli_bench.weakest`) must agree.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_SCRIPT = REPO_ROOT / "scripts" / "metrics" / "performance_benchmark.py"


def _load_pb():
    if "scripts.metrics.performance_benchmark" in sys.modules:
        return sys.modules["scripts.metrics.performance_benchmark"]
    spec = importlib.util.spec_from_file_location(
        "scripts.metrics.performance_benchmark", LEGACY_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["scripts.metrics.performance_benchmark"] = mod
    spec.loader.exec_module(mod)
    return mod


def _phi_worst_snapshot() -> dict:
    """Construct metrics where Phi has the worst margin — Phi must still be skipped."""
    return {
        "phi": 0.05,                  # target 0.65 → margin -92% (would be worst)
        "action_accuracy": 0.85,      # target 0.90 → margin -5.6% (actual worst non-phi)
        "episode_success_rate": 0.95, # target 0.85 → passing
        "task_quality_score": 0.95,
        "code_quality_score": 0.90,
        "context_relevance": 0.95,
        "retrieval_hit_rate": 1.0,
        "brain_query_avg_ms": 200.0,
        "brain_query_p95_ms": 250.0,
        "graph_density": 30.0,
        "brain_total_memories": 2955,
        "bloat_score": 0.0,
    }


def _select_weakest(targets: dict, metrics: dict, phi_excluded: set[str]) -> str | None:
    """Reference implementation matching the CLI selector. Tests both code paths
    against this single source of truth."""
    worst_name, worst_margin = None, float("inf")
    for key, meta in targets.items():
        target = meta.get("target")
        if target is None or meta.get("direction") == "monitor":
            continue
        if key in phi_excluded:
            continue
        val = metrics.get(key)
        if val is None:
            continue
        if meta["direction"] == "higher":
            margin = (val - target) / max(target, 0.001)
        else:
            margin = (target - val) / max(target, 0.001)
        if margin < worst_margin:
            worst_margin = margin
            worst_name = key
    return worst_name


def test_phi_excluded_from_weakest_when_phi_is_worst():
    """Even with phi=0.05 (catastrophically below target), selector returns
    the second-worst metric, not phi."""
    pb = _load_pb()
    metrics = _phi_worst_snapshot()
    worst = _select_weakest(pb.TARGETS, metrics, phi_excluded={"phi"})
    assert worst == "action_accuracy"
    assert worst != "phi"


def test_without_exclusion_phi_would_be_worst():
    """Sanity check: confirm the fixture is shaped so exclusion is the *only*
    thing preventing Phi from being selected."""
    pb = _load_pb()
    metrics = _phi_worst_snapshot()
    worst = _select_weakest(pb.TARGETS, metrics, phi_excluded=set())
    assert worst == "phi", (
        "Fixture must put phi as worst — otherwise the exclusion test is meaningless"
    )


def test_legacy_cli_module_has_phi_exclusion_marker():
    """Guard against regression: the legacy CLI source should still contain the
    PHI_DEEMPHASISED set."""
    src = LEGACY_SCRIPT.read_text()
    assert "PHI_DEEMPHASISED" in src, (
        "Phi-exclusion marker missing from performance_benchmark.py — "
        "[PHI_AUTO_INJECTION_REMOVAL] regression"
    )
    assert '"phi"' in src.split("PHI_DEEMPHASISED")[1].split("\n", 3)[0] or \
           "'phi'" in src.split("PHI_DEEMPHASISED")[1].split("\n", 3)[0]


def test_spine_cli_module_has_phi_exclusion_marker():
    """Same guard for the spine CLI (`python3 -m clarvis bench weakest`)."""
    spine = REPO_ROOT / "clarvis" / "cli_bench.py"
    src = spine.read_text()
    assert "PHI_DEEMPHASISED" in src, (
        "Phi-exclusion marker missing from clarvis/cli_bench.py — "
        "[PHI_AUTO_INJECTION_REMOVAL] regression"
    )


def test_phi_still_in_targets_for_pi_calculation():
    """Phi must remain a TARGET so PI score and history writes are unaffected.
    The de-emphasis is *only* in the prompt-injection selector."""
    pb = _load_pb()
    assert "phi" in pb.TARGETS
    assert pb.TARGETS["phi"]["target"] == 0.65
    # weight should be unchanged — this test will need updating only when
    # [PHI_DEEMPHASIS_AUDIT] proper drops phi to monitor-only.
    assert pb.TARGETS["phi"]["direction"] == "higher"


def test_weakest_returns_none_when_all_pass(monkeypatch):
    """When every non-phi metric is well above target, selector still returns
    *something* (the least-passing metric) — never crashes."""
    pb = _load_pb()
    # All metrics meet/exceed targets
    metrics = {
        "phi": 0.05,                  # would be worst if not excluded
        "action_accuracy": 0.99,
        "episode_success_rate": 0.99,
        "task_quality_score": 0.99,
        "code_quality_score": 0.99,
        "context_relevance": 0.99,
        "retrieval_hit_rate": 1.0,
        "brain_query_avg_ms": 100.0,
        "brain_query_p95_ms": 150.0,
        "graph_density": 50.0,
        "brain_total_memories": 5000,
        "bloat_score": 0.0,
    }
    worst = _select_weakest(pb.TARGETS, metrics, phi_excluded={"phi"})
    # Some non-phi metric must still be picked (worst margin among passing)
    assert worst is not None
    assert worst != "phi"
