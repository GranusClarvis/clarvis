"""Phi metric regression harness.

Snapshots current phi subcomponent scores and fails if any regress >5%
from the recorded baseline. Guards against silent regressions from
graph compaction or hygiene passes.
"""

import json
import os
import pytest

from clarvis.metrics.phi import compute_phi

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
BASELINE_FILE = os.path.join(_WS, "data", "phi_regression_baseline.json")
DECOMPOSITION_FILE = os.path.join(_WS, "data", "phi_decomposition.json")
REGRESSION_THRESHOLD = 0.05

COMPONENT_KEYS = [
    "intra_collection_density",
    "cross_collection_connectivity",
    "semantic_cross_collection",
    "collection_reachability",
]


def _load_baseline():
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE) as f:
            return json.load(f)
    return None


def _save_baseline(result):
    os.makedirs(os.path.dirname(BASELINE_FILE), exist_ok=True)
    baseline = {
        "phi": result["phi"],
        "components": result["components"],
        "timestamp": result["timestamp"],
    }
    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)
    return baseline


def _safe_compute_phi():
    try:
        return compute_phi()
    except Exception as e:
        if "Error finding id" in str(e) or "chromadb" in type(e).__module__:
            pytest.skip(f"ChromaDB transient error (concurrent access): {e}")
        raise


@pytest.mark.slow
class TestPhiMetricRegression:
    """Regression tests for Phi metric subcomponents."""

    def test_compute_phi_returns_valid_structure(self):
        result = _safe_compute_phi()
        assert isinstance(result, dict)
        assert "phi" in result
        assert "components" in result
        assert "raw" in result
        assert "interpretation" in result
        for key in COMPONENT_KEYS:
            assert key in result["components"]

    def test_phi_score_in_valid_range(self):
        result = _safe_compute_phi()
        assert 0.0 <= result["phi"] <= 1.0

    def test_components_in_valid_range(self):
        result = _safe_compute_phi()
        for key in COMPONENT_KEYS:
            score = result["components"][key]
            assert 0.0 <= score <= 1.0, f"{key} = {score} out of [0, 1]"

    def test_raw_counts_non_negative(self):
        result = _safe_compute_phi()
        for key in ("total_memories", "total_edges", "cross_collection_edges", "same_collection_edges"):
            assert result["raw"][key] >= 0, f"raw.{key} is negative"

    def test_no_regression_from_baseline(self):
        """Fail if any component drops >5% from the saved baseline."""
        baseline = _load_baseline()
        result = _safe_compute_phi()

        if baseline is None:
            _save_baseline(result)
            pytest.skip("No baseline existed — created one. Re-run to check regression.")

        regressions = []
        for key in COMPONENT_KEYS:
            current = result["components"][key]
            base = baseline["components"].get(key, 0)
            if base > 0 and (base - current) > REGRESSION_THRESHOLD:
                regressions.append(
                    f"{key}: {base:.4f} -> {current:.4f} (delta={current - base:+.4f})"
                )

        phi_delta = result["phi"] - baseline["phi"]
        if baseline["phi"] > 0 and (baseline["phi"] - result["phi"]) > REGRESSION_THRESHOLD:
            regressions.append(
                f"phi: {baseline['phi']:.4f} -> {result['phi']:.4f} (delta={phi_delta:+.4f})"
            )

        if not regressions:
            _save_baseline(result)

        assert not regressions, (
            f"Phi regression detected (threshold={REGRESSION_THRESHOLD}):\n"
            + "\n".join(f"  - {r}" for r in regressions)
        )


@pytest.mark.slow
class TestPhiDecomposition:
    """Verify decomposition file is fresh and structurally valid."""

    def test_decomposition_file_exists(self):
        assert os.path.exists(DECOMPOSITION_FILE), (
            f"Phi decomposition file missing: {DECOMPOSITION_FILE}"
        )

    def test_decomposition_has_required_keys(self):
        if not os.path.exists(DECOMPOSITION_FILE):
            pytest.skip("No decomposition file")
        with open(DECOMPOSITION_FILE) as f:
            data = json.load(f)
        for key in ("phi", "components", "timestamp"):
            assert key in data, f"Missing key: {key}"
