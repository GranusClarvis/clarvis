#!/usr/bin/env python3
"""
Phi (Φ) Metric — Integrated Information for Clarvis Brain

CLI wrapper — canonical logic lives in clarvis.metrics.phi (spine module).

Usage:
    python phi_metric.py              # Current Phi + breakdown
    python phi_metric.py history      # Show Phi history
    python phi_metric.py record       # Compute and record current Phi
    python phi_metric.py trend        # Analyze Phi trend over time
    python phi_metric.py act          # Record + act on Phi (feedback loop)
    python phi_metric.py decompose    # Full per-collection decomposition
"""

import json
import sys
import os

# Ensure clarvis package is importable
_workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
# Also keep scripts/ on path for legacy imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import everything from canonical spine module
from clarvis.metrics.phi import (  # noqa: E402, F401
    # Constants
    PHI_HISTORY_FILE, PHI_DECOMPOSITION_FILE, LEGACY_PREFIX_MAP,
    # Core computation
    compute_phi, record_phi, get_history, trend_analysis,
    act_on_phi, decompose_phi,
    # Component functions (for direct use)
    intra_collection_density, cross_collection_integration,
    semantic_cross_collection, collection_reachability,
)

# Re-export ALL_COLLECTIONS for callers that import it from here
try:
    from clarvis.brain import ALL_COLLECTIONS  # noqa: F401
except ImportError:
    from brain import ALL_COLLECTIONS  # noqa: F401


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "compute"

    if cmd == "compute":
        result = compute_phi()
        print(f"Φ (Phi) = {result['phi']}")
        print("\nComponents:")
        for k, v in result["components"].items():
            bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
            print(f"  {k:35s} {bar} {v:.4f}")
        print("\nIntra-collection density:")
        for col, d in result["details"]["intra_density_per_collection"].items():
            print(f"  {col:35s} {d:.4f}")
        print("\nSemantic cross-collection pairs:")
        for pair, sim in result["details"]["semantic_pairs"].items():
            print(f"  {pair:60s} {sim:.4f}")
        print("\nRaw:")
        print(f"  Total memories: {result['raw']['total_memories']}")
        print(f"  Total edges:    {result['raw']['total_edges']}")
        print(f"  Cross-collection edges: {result['raw']['cross_collection_edges']}")
        print(f"  Same-collection edges:  {result['raw']['same_collection_edges']}")
        print(f"\n{result['interpretation']}")

    elif cmd == "record":
        result = record_phi()
        print(f"Φ = {result['phi']} — recorded to {PHI_HISTORY_FILE}")
        print(result["interpretation"])

    elif cmd == "history":
        history = get_history()
        if not history:
            print("No history yet. Run 'phi_metric.py record' to start tracking.")
        else:
            print(f"Phi History ({len(history)} measurements):")
            for h in history:
                ts = h["timestamp"][:19]
                phi = h["phi"]
                bar = "█" * int(phi * 20) + "░" * (20 - int(phi * 20))
                print(f"  {ts}  {bar}  Φ={phi:.4f}  (mem={h['total_memories']}, edges={h['total_edges']})")
            trend = trend_analysis()
            print(f"\nTrend: {trend['trend']} (Δ={trend.get('delta', 'n/a')})")

    elif cmd == "trend":
        trend = trend_analysis()
        print(json.dumps(trend, indent=2))

    elif cmd == "act":
        result = record_phi()
        print(f"Phi = {result['phi']}")
        actions = act_on_phi(result)
        print(f"Actions: {json.dumps(actions, indent=2)}")

    elif cmd == "decompose":
        decomp = decompose_phi()
        print(f"Φ (Phi) = {decomp['phi']}")
        print("\nIntra-density per collection:")
        for col, d in sorted(decomp["intra_density_per_collection"].items()):
            bar = "█" * int(d * 100) + "░" * (10 - min(10, int(d * 100)))
            print(f"  {col:35s} {bar} {d:.4f}")
        print("\nCross-connectivity per pair (edge counts):")
        for pair, count in sorted(decomp["cross_connectivity_per_pair"].items(), key=lambda x: -x[1]):
            print(f"  {pair:60s} {count}")
        print("\nSemantic overlap per pair:")
        for pair, sim in sorted(decomp["semantic_overlap_per_pair"].items(), key=lambda x: -x[1]):
            print(f"  {pair:60s} {sim:.4f}")
        print(f"\nWritten to {PHI_DECOMPOSITION_FILE}")

    else:
        print("Usage: phi_metric.py [compute|record|history|trend|act|decompose]")
        sys.exit(1)
