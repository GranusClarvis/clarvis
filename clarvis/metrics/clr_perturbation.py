"""
CLR Perturbation / Ablation Harness.

Deterministic harness that toggles context-assembly modules on/off, runs CLR,
and records score deltas + failure modes.  Answers: "Does module X actually
help, and by how much?"

Toggleable modules:
  - episodic_recall    → episodic hints in brief
  - graph_expansion    → brain knowledge / graph-expanded context
  - related_tasks      → related pending tasks from QUEUE.md
  - decision_context   → success criteria, failure avoidance, constraints
  - reasoning_scaffold → reasoning chain scaffold in brief
  - working_memory     → cognitive workspace / spotlight items

Usage:
    python3 clarvis/metrics/clr_perturbation.py           # full ablation sweep
    python3 clarvis/metrics/clr_perturbation.py --module episodic_recall
    python3 clarvis/metrics/clr_perturbation.py --report   # show latest results
"""

import json
import os
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
RESULTS_FILE = os.path.join(WORKSPACE, "data/clr_perturbation_results.json")
HISTORY_FILE = os.path.join(WORKSPACE, "data/clr_perturbation_history.jsonl")
MAX_HISTORY = 200

# Modules that can be ablated and how to disable them.
# Each entry maps to a budget key or assembly function.
ABLATABLE_MODULES = [
    "episodic_recall",
    "graph_expansion",
    "related_tasks",
    "decision_context",
    "reasoning_scaffold",
    "working_memory",
]

# Reference task for deterministic evaluation
REFERENCE_TASKS = [
    "[BENCHMARK] Fix context relevance scoring in assembly.py",
    "[BENCHMARK] Add cross-collection bridge memories for Phi improvement",
    "[BENCHMARK] Wire retrieval evaluation into heartbeat postflight",
]


def _run_clr_with_ablation(disabled_modules: list[str]) -> dict[str, Any]:
    """Run CLR benchmark with specific modules disabled.

    Patches assembly budgets to zero out disabled modules, then runs CLR.
    Returns the full CLR result dict.
    """
    import clarvis.context.assembly as assembly
    from clarvis.metrics.clr import compute_clr

    # Save original budgets
    original_budgets = deepcopy(assembly.TIER_BUDGETS)
    original_hard_suppress = set(assembly.HARD_SUPPRESS)

    try:
        # Patch budgets to disable requested modules
        budget_key_map = {
            "episodic_recall": "episodes",
            "graph_expansion": None,  # handled via knowledge_hints suppression
            "related_tasks": "related_tasks",
            "decision_context": "decision_context",
            "reasoning_scaffold": "reasoning_scaffold",
            "working_memory": "spotlight",
        }

        for module in disabled_modules:
            budget_key = budget_key_map.get(module)
            if budget_key:
                for tier in assembly.TIER_BUDGETS:
                    if budget_key in assembly.TIER_BUDGETS[tier]:
                        assembly.TIER_BUDGETS[tier][budget_key] = 0

        # For graph_expansion, we suppress knowledge hints at the section level
        if "graph_expansion" in disabled_modules:
            assembly.HARD_SUPPRESS = frozenset(
                original_hard_suppress | {"brain_context", "knowledge"}
            )

        result = compute_clr()
        return result

    finally:
        # Restore original state
        assembly.TIER_BUDGETS = original_budgets
        assembly.HARD_SUPPRESS = frozenset(original_hard_suppress)


def run_ablation_sweep(modules: list[str] | None = None) -> dict[str, Any]:
    """Run full ablation sweep: baseline + each module disabled individually.

    Returns:
        {
            "timestamp": ...,
            "baseline": { CLR result },
            "ablations": {
                "module_name": {
                    "clr": float,
                    "delta": float,  # negative = module helps
                    "dimensions": { dim: { score, delta } },
                    "disabled": ["module_name"],
                },
                ...
            },
            "rankings": [  # sorted by impact (most helpful first)
                { "module": ..., "delta": ..., "verdict": ... },
            ],
        }
    """
    modules = modules or ABLATABLE_MODULES
    timestamp = datetime.now(timezone.utc).isoformat()

    print(f"[perturbation] Running baseline CLR...", flush=True)
    t0 = time.time()
    baseline = _run_clr_with_ablation([])
    baseline_clr = baseline.get("clr", 0.0)
    baseline_dims = baseline.get("dimensions", {})
    print(f"[perturbation] Baseline CLR = {baseline_clr:.4f} ({time.time()-t0:.1f}s)")

    ablations = {}
    for module in modules:
        print(f"[perturbation] Ablating: {module}...", flush=True)
        t1 = time.time()
        try:
            result = _run_clr_with_ablation([module])
            ablated_clr = result.get("clr", 0.0)
            ablated_dims = result.get("dimensions", {})

            delta = ablated_clr - baseline_clr

            # Per-dimension deltas
            dim_deltas = {}
            for dim_name, dim_data in baseline_dims.items():
                base_score = dim_data.get("score", 0.0)
                abl_score = ablated_dims.get(dim_name, {}).get("score", 0.0)
                dim_deltas[dim_name] = {
                    "baseline": round(base_score, 4),
                    "ablated": round(abl_score, 4),
                    "delta": round(abl_score - base_score, 4),
                }

            ablations[module] = {
                "clr": round(ablated_clr, 4),
                "delta": round(delta, 4),
                "dimensions": dim_deltas,
                "disabled": [module],
                "duration_s": round(time.time() - t1, 1),
            }
            print(
                f"[perturbation]   {module}: CLR={ablated_clr:.4f} "
                f"delta={delta:+.4f} ({time.time()-t1:.1f}s)"
            )
        except Exception as e:
            ablations[module] = {
                "clr": 0.0,
                "delta": -baseline_clr,
                "error": str(e),
                "disabled": [module],
            }
            print(f"[perturbation]   {module}: ERROR — {e}")

    # Rank modules by impact (most negative delta = most helpful)
    rankings = []
    for module, data in ablations.items():
        delta = data.get("delta", 0.0)
        if delta < -0.02:
            verdict = "CRITICAL"  # removing it hurts significantly
        elif delta < -0.005:
            verdict = "HELPFUL"
        elif delta > 0.01:
            verdict = "HARMFUL"  # removing it helps — module is hurting CLR
        else:
            verdict = "NEUTRAL"

        rankings.append({
            "module": module,
            "delta": delta,
            "verdict": verdict,
        })

    rankings.sort(key=lambda x: x["delta"])

    result = {
        "timestamp": timestamp,
        "schema_version": "1.0",
        "baseline": {
            "clr": round(baseline_clr, 4),
            "dimensions": {
                k: round(v.get("score", 0.0), 4) for k, v in baseline_dims.items()
            },
        },
        "ablations": ablations,
        "rankings": rankings,
        "total_duration_s": round(time.time() - t0, 1),
    }

    # Persist
    _save_results(result)
    return result


def _save_results(result: dict):
    """Save latest result and append to history."""
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)

    with open(RESULTS_FILE, "w") as f:
        json.dump(result, f, indent=2)

    # Append to history (capped)
    history_line = json.dumps({
        "timestamp": result["timestamp"],
        "baseline_clr": result["baseline"]["clr"],
        "rankings": result["rankings"],
        "total_duration_s": result.get("total_duration_s"),
    })

    lines = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            lines = f.readlines()

    lines.append(history_line + "\n")
    if len(lines) > MAX_HISTORY:
        lines = lines[-MAX_HISTORY:]

    with open(HISTORY_FILE, "w") as f:
        f.writelines(lines)


def print_report(result: dict | None = None):
    """Print a human-readable ablation report."""
    if result is None:
        if not os.path.exists(RESULTS_FILE):
            print("No perturbation results found. Run a sweep first.")
            return
        with open(RESULTS_FILE) as f:
            result = json.load(f)

    print(f"\n{'='*60}")
    print(f"CLR Perturbation Report — {result['timestamp'][:19]}")
    print(f"{'='*60}")
    print(f"\nBaseline CLR: {result['baseline']['clr']:.4f}")
    print(f"Duration: {result.get('total_duration_s', '?')}s")

    print(f"\n{'Module':<22} {'CLR':>7} {'Delta':>8} {'Verdict':<10}")
    print("-" * 50)
    for r in result.get("rankings", []):
        module = r["module"]
        delta = r["delta"]
        verdict = r["verdict"]
        abl = result.get("ablations", {}).get(module, {})
        clr = abl.get("clr", 0.0)
        print(f"{module:<22} {clr:>7.4f} {delta:>+8.4f} {verdict:<10}")

    # Show per-dimension breakdown for most impactful module
    rankings = result.get("rankings", [])
    if rankings:
        most_impactful = rankings[0]["module"]
        dims = result.get("ablations", {}).get(most_impactful, {}).get("dimensions", {})
        if dims:
            print(f"\nDimension breakdown for most impactful: {most_impactful}")
            print(f"  {'Dimension':<25} {'Base':>7} {'Ablated':>8} {'Delta':>8}")
            print("  " + "-" * 50)
            for dim, dd in dims.items():
                print(
                    f"  {dim:<25} {dd['baseline']:>7.4f} "
                    f"{dd['ablated']:>8.4f} {dd['delta']:>+8.4f}"
                )

    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CLR Perturbation / Ablation Harness")
    parser.add_argument(
        "--module", type=str, default=None,
        help="Ablate a single module (default: all)",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Print latest report without running",
    )
    args = parser.parse_args()

    if args.report:
        print_report()
        return

    modules = [args.module] if args.module else None
    result = run_ablation_sweep(modules)
    print_report(result)


if __name__ == "__main__":
    main()
