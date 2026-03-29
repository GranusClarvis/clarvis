"""
CLR Perturbation / Ablation Harness.

Deterministic harness that toggles context-assembly modules on/off,
runs assembly and CLR, and records score deltas + failure modes.
Answers: "Does module X actually help, and by how much?"

v2 (2026-03-29): Fixed fundamental flaw where ablation patched assembly
budgets but CLR measured historical metrics unaffected by budget changes.
Now measures assembly output quality directly AND runs CLR for system-level
delta.  Added multi-component ablation for interaction effects.

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
    python3 clarvis/metrics/clr_perturbation.py --pairs    # multi-component ablation
    python3 clarvis/metrics/clr_perturbation.py --report   # show latest results
"""

import json
import os
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
RESULTS_FILE = os.path.join(WORKSPACE, "data/clr_perturbation_results.json")
HISTORY_FILE = os.path.join(WORKSPACE, "data/clr_perturbation_history.jsonl")
MAX_HISTORY = 200

# Modules that can be ablated and how to disable them.
ABLATABLE_MODULES = [
    "episodic_recall",
    "graph_expansion",
    "related_tasks",
    "decision_context",
    "reasoning_scaffold",
    "working_memory",
]

# Harder reference tasks that stress multiple cognitive modules.
# Each task needs brain context, episodic recall, reasoning, AND task context
# to produce a quality brief.  Easy tasks mask module contributions.
REFERENCE_TASKS = [
    # Requires: episodic recall (past failures), decision context (constraints),
    # reasoning scaffold (multi-step), graph expansion (architecture knowledge)
    "[BENCHMARK] Diagnose why CLR ablation shows zero delta across all modules — "
    "trace the measurement path from assembly budgets through CLR dimensions",

    # Requires: working memory (recent changes), related tasks (queue context),
    # episodic recall (past regressions), graph expansion (code relationships)
    "[BENCHMARK] Refactor heartbeat postflight to use reasoning chains for "
    "episode quality scoring instead of binary success/fail, preserving "
    "backward compatibility with existing episode format",

    # Requires: all modules — complex cross-cutting change
    "[BENCHMARK] Design and implement adaptive context assembly that uses "
    "per-section relevance feedback to dynamically allocate token budgets "
    "across episodic, knowledge, and reasoning sections",

    # Requires: graph expansion (brain architecture), decision context (Phi formula),
    # reasoning scaffold (mathematical reasoning)
    "[BENCHMARK] Fix Phi metric inflation by implementing proper graph sampling "
    "that accounts for hub nodes skewing degree-based density scores",
]


def _measure_assembly_quality(disabled_modules: list[str]) -> dict[str, Any]:
    """Measure context assembly output quality with specific modules disabled.

    This is the assembly-sensitive measurement that the ablation actually tests.
    Unlike compute_clr() which reads historical metrics, this runs the assembly
    pipeline and measures the output.

    Returns dict with section_count, total_chars, section_presence, and a
    normalized quality score.
    """
    import clarvis.context.assembly as assembly
    from clarvis.context.budgets import TIER_BUDGETS as ORIGINAL_BUDGETS

    original_budgets = deepcopy(assembly.TIER_BUDGETS)
    original_hard_suppress = set(assembly.HARD_SUPPRESS)

    try:
        _apply_ablation(disabled_modules, assembly)

        results = {}
        for task in REFERENCE_TASKS:
            try:
                brief = assembly.generate_tiered_brief(task, tier="standard")
            except Exception as e:
                brief = f"ERROR: {e}"

            # Measure what's in the brief
            sections_present = set()
            section_markers = {
                "episodic_recall": ["EPISODIC", "episode", "past task", "lesson"],
                "graph_expansion": ["BRAIN CONTEXT", "KNOWLEDGE", "brain search"],
                "related_tasks": ["RELATED TASKS", "QUEUE", "pending"],
                "decision_context": ["SUCCESS CRITERIA", "FAILURE", "AVOID",
                                     "CONSTRAINT", "OBLIGATION"],
                "reasoning_scaffold": ["REASONING", "APPROACH", "STRATEGY",
                                       "multi-step"],
                "working_memory": ["WORKING MEMORY", "GWT BROADCAST",
                                   "ATTENTION", "SPOTLIGHT"],
            }

            brief_upper = brief.upper()
            for module, markers in section_markers.items():
                for marker in markers:
                    if marker.upper() in brief_upper:
                        sections_present.add(module)
                        break

            results[task[:60]] = {
                "total_chars": len(brief),
                "sections_present": sorted(sections_present),
                "section_count": len(sections_present),
            }

        # Aggregate across tasks
        all_chars = [r["total_chars"] for r in results.values()]
        all_section_counts = [r["section_count"] for r in results.values()]

        avg_chars = sum(all_chars) / len(all_chars) if all_chars else 0
        avg_sections = (sum(all_section_counts) / len(all_section_counts)
                        if all_section_counts else 0)

        # Quality score: combination of content volume and section diversity
        # More sections present = more modules contributing = better assembly
        max_sections = len(ABLATABLE_MODULES)
        diversity_score = avg_sections / max_sections if max_sections > 0 else 0

        # Volume score: brief should be substantial (>500 chars) but not bloated
        if avg_chars < 100:
            volume_score = 0.0
        elif avg_chars < 500:
            volume_score = avg_chars / 500
        elif avg_chars <= 3000:
            volume_score = 1.0
        else:
            volume_score = max(0.5, 1.0 - (avg_chars - 3000) / 5000)

        # Composite: 60% diversity (are sections present?), 40% volume
        quality = 0.6 * diversity_score + 0.4 * volume_score

        return {
            "quality": round(quality, 4),
            "diversity_score": round(diversity_score, 4),
            "volume_score": round(volume_score, 4),
            "avg_chars": round(avg_chars),
            "avg_sections": round(avg_sections, 2),
            "per_task": results,
        }

    finally:
        assembly.TIER_BUDGETS = original_budgets
        assembly.HARD_SUPPRESS = frozenset(original_hard_suppress)


def _apply_ablation(disabled_modules: list[str], assembly):
    """Apply ablation patches to assembly module state."""
    budget_key_map = {
        "episodic_recall": "episodes",
        "graph_expansion": None,  # handled via HARD_SUPPRESS
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

    if "graph_expansion" in disabled_modules:
        assembly.HARD_SUPPRESS = frozenset(
            set(assembly.HARD_SUPPRESS) | {"brain_context", "knowledge"}
        )


def _run_clr_with_ablation(disabled_modules: list[str]) -> dict[str, Any]:
    """Run CLR benchmark with specific modules disabled.

    Note: CLR dimensions mostly read historical data (episodes, brain stats)
    that are NOT affected by budget changes.  The assembly_quality measurement
    captures the actual ablation effect.  CLR is included for completeness
    and to detect any indirect effects.
    """
    import clarvis.context.assembly as assembly
    from clarvis.metrics.clr import compute_clr

    original_budgets = deepcopy(assembly.TIER_BUDGETS)
    original_hard_suppress = set(assembly.HARD_SUPPRESS)

    try:
        _apply_ablation(disabled_modules, assembly)
        result = compute_clr()
        return result
    finally:
        assembly.TIER_BUDGETS = original_budgets
        assembly.HARD_SUPPRESS = frozenset(original_hard_suppress)


def run_ablation_sweep(
    modules: list[str] | None = None,
    include_pairs: bool = False,
) -> dict[str, Any]:
    """Run ablation sweep: baseline + each module disabled, optionally pairs.

    Args:
        modules: Which modules to ablate (default: all).
        include_pairs: If True, also test all 2-module combinations to
            find interaction effects (modules that are only important
            when another is also present).

    Returns:
        {
            "timestamp": ...,
            "baseline": { clr, assembly_quality },
            "ablations": { module_or_pair: { ... } },
            "interaction_effects": [ ... ],  # only if include_pairs
            "rankings": [ { module, delta, verdict } ],
        }
    """
    modules = modules or ABLATABLE_MODULES
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- Baseline ---
    print("[perturbation] Running baseline...", flush=True)
    t0 = time.time()
    baseline_clr = _run_clr_with_ablation([])
    baseline_aq = _measure_assembly_quality([])
    baseline_clr_score = baseline_clr.get("clr", 0.0)
    baseline_aq_score = baseline_aq.get("quality", 0.0)
    baseline_dims = baseline_clr.get("dimensions", {})
    print(
        f"[perturbation] Baseline: CLR={baseline_clr_score:.4f}, "
        f"assembly_quality={baseline_aq_score:.4f} ({time.time()-t0:.1f}s)"
    )

    ablations = {}

    # --- Single-module ablations ---
    for module in modules:
        print(f"[perturbation] Ablating: {module}...", flush=True)
        t1 = time.time()
        try:
            result_clr = _run_clr_with_ablation([module])
            result_aq = _measure_assembly_quality([module])

            ablated_clr = result_clr.get("clr", 0.0)
            ablated_aq = result_aq.get("quality", 0.0)
            clr_delta = ablated_clr - baseline_clr_score
            aq_delta = ablated_aq - baseline_aq_score

            # Per-dimension CLR deltas
            dim_deltas = {}
            for dim_name, dim_data in baseline_dims.items():
                base_score = dim_data.get("score", 0.0)
                abl_score = (result_clr.get("dimensions", {})
                             .get(dim_name, {}).get("score", 0.0))
                dim_deltas[dim_name] = {
                    "baseline": round(base_score, 4),
                    "ablated": round(abl_score, 4),
                    "delta": round(abl_score - base_score, 4),
                }

            ablations[module] = {
                "clr": round(ablated_clr, 4),
                "clr_delta": round(clr_delta, 4),
                "assembly_quality": round(ablated_aq, 4),
                "aq_delta": round(aq_delta, 4),
                "assembly_details": {
                    "diversity": result_aq.get("diversity_score", 0),
                    "volume": result_aq.get("volume_score", 0),
                    "avg_chars": result_aq.get("avg_chars", 0),
                    "avg_sections": result_aq.get("avg_sections", 0),
                },
                "dimensions": dim_deltas,
                "disabled": [module],
                "duration_s": round(time.time() - t1, 1),
            }
            print(
                f"[perturbation]   {module}: CLR={ablated_clr:.4f} "
                f"(Δ{clr_delta:+.4f}), AQ={ablated_aq:.4f} "
                f"(Δ{aq_delta:+.4f}) ({time.time()-t1:.1f}s)"
            )
        except Exception as e:
            ablations[module] = {
                "clr": 0.0,
                "clr_delta": -baseline_clr_score,
                "assembly_quality": 0.0,
                "aq_delta": -baseline_aq_score,
                "error": str(e),
                "disabled": [module],
            }
            print(f"[perturbation]   {module}: ERROR — {e}")

    # --- Multi-component (pair) ablations ---
    interaction_effects = []
    if include_pairs and len(modules) >= 2:
        print(f"\n[perturbation] Running pair ablations...", flush=True)
        for pair in combinations(modules, 2):
            pair_key = "+".join(pair)
            print(f"[perturbation] Ablating pair: {pair_key}...", flush=True)
            t2 = time.time()
            try:
                result_aq = _measure_assembly_quality(list(pair))
                pair_aq = result_aq.get("quality", 0.0)
                pair_delta = pair_aq - baseline_aq_score

                # Expected delta = sum of individual deltas (additive model)
                ind_delta_a = ablations.get(pair[0], {}).get("aq_delta", 0.0)
                ind_delta_b = ablations.get(pair[1], {}).get("aq_delta", 0.0)
                expected_delta = ind_delta_a + ind_delta_b
                # Interaction = actual - expected. Negative = synergy (pair
                # hurts more than sum of parts). Positive = redundancy.
                interaction = pair_delta - expected_delta

                ablations[pair_key] = {
                    "assembly_quality": round(pair_aq, 4),
                    "aq_delta": round(pair_delta, 4),
                    "expected_delta": round(expected_delta, 4),
                    "interaction": round(interaction, 4),
                    "assembly_details": {
                        "diversity": result_aq.get("diversity_score", 0),
                        "volume": result_aq.get("volume_score", 0),
                        "avg_chars": result_aq.get("avg_chars", 0),
                        "avg_sections": result_aq.get("avg_sections", 0),
                    },
                    "disabled": list(pair),
                    "duration_s": round(time.time() - t2, 1),
                }

                if abs(interaction) > 0.01:
                    kind = "SYNERGY" if interaction < 0 else "REDUNDANCY"
                    interaction_effects.append({
                        "pair": pair_key,
                        "interaction": round(interaction, 4),
                        "kind": kind,
                        "pair_delta": round(pair_delta, 4),
                        "expected_delta": round(expected_delta, 4),
                    })

                print(
                    f"[perturbation]   {pair_key}: AQ={pair_aq:.4f} "
                    f"(Δ{pair_delta:+.4f}, interaction={interaction:+.4f}) "
                    f"({time.time()-t2:.1f}s)"
                )
            except Exception as e:
                ablations[pair_key] = {
                    "assembly_quality": 0.0,
                    "aq_delta": -baseline_aq_score,
                    "error": str(e),
                    "disabled": list(pair),
                }
                print(f"[perturbation]   {pair_key}: ERROR — {e}")

    # --- Rankings (by assembly quality delta, which is the real signal) ---
    rankings = []
    for module in modules:
        data = ablations.get(module, {})
        aq_delta = data.get("aq_delta", 0.0)
        clr_delta = data.get("clr_delta", 0.0)

        # Verdict based on assembly quality delta (the real signal)
        if aq_delta < -0.05:
            verdict = "CRITICAL"
        elif aq_delta < -0.02:
            verdict = "HELPFUL"
        elif aq_delta > 0.02:
            verdict = "HARMFUL"
        else:
            verdict = "NEUTRAL"

        rankings.append({
            "module": module,
            "aq_delta": round(aq_delta, 4),
            "clr_delta": round(clr_delta, 4),
            "verdict": verdict,
        })

    rankings.sort(key=lambda x: x["aq_delta"])

    # Sort interaction effects by magnitude
    interaction_effects.sort(key=lambda x: abs(x["interaction"]), reverse=True)

    result = {
        "timestamp": timestamp,
        "schema_version": "2.0",
        "baseline": {
            "clr": round(baseline_clr_score, 4),
            "assembly_quality": round(baseline_aq_score, 4),
            "assembly_details": {
                "diversity": baseline_aq.get("diversity_score", 0),
                "volume": baseline_aq.get("volume_score", 0),
                "avg_chars": baseline_aq.get("avg_chars", 0),
                "avg_sections": baseline_aq.get("avg_sections", 0),
            },
            "dimensions": {
                k: round(v.get("score", 0.0), 4)
                for k, v in baseline_dims.items()
            },
        },
        "ablations": ablations,
        "rankings": rankings,
        "interaction_effects": interaction_effects,
        "reference_tasks": REFERENCE_TASKS,
        "total_duration_s": round(time.time() - t0, 1),
    }

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
        "schema_version": result.get("schema_version", "1.0"),
        "baseline_clr": result["baseline"]["clr"],
        "baseline_aq": result["baseline"].get("assembly_quality"),
        "rankings": result["rankings"],
        "interaction_effects": result.get("interaction_effects", []),
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

    v = result.get("schema_version", "1.0")
    print(f"\n{'='*65}")
    print(f"CLR Perturbation Report v{v} — {result['timestamp'][:19]}")
    print(f"{'='*65}")

    baseline = result.get("baseline", {})
    print(f"\nBaseline: CLR={baseline.get('clr', '?'):.4f}"
          f"  AQ={baseline.get('assembly_quality', '?'):.4f}"
          f"  (sections={baseline.get('assembly_details', {}).get('avg_sections', '?')},"
          f" chars={baseline.get('assembly_details', {}).get('avg_chars', '?')})")
    print(f"Duration: {result.get('total_duration_s', '?')}s")

    # Single-module rankings
    rankings = result.get("rankings", [])
    if rankings:
        # Check for v2 format
        has_aq = "aq_delta" in rankings[0]
        if has_aq:
            print(f"\n{'Module':<22} {'AQ':>7} {'AQ Δ':>8} {'CLR Δ':>8} {'Verdict':<10}")
            print("-" * 58)
            for r in rankings:
                module = r["module"]
                abl = result.get("ablations", {}).get(module, {})
                aq = abl.get("assembly_quality", 0.0)
                print(f"{module:<22} {aq:>7.4f} {r['aq_delta']:>+8.4f} "
                      f"{r.get('clr_delta', 0):>+8.4f} {r['verdict']:<10}")
        else:
            # Legacy v1 format
            print(f"\n{'Module':<22} {'CLR':>7} {'Delta':>8} {'Verdict':<10}")
            print("-" * 50)
            for r in rankings:
                module = r["module"]
                abl = result.get("ablations", {}).get(module, {})
                clr = abl.get("clr", 0.0)
                delta = r.get("delta", r.get("aq_delta", 0.0))
                print(f"{module:<22} {clr:>7.4f} {delta:>+8.4f} {r['verdict']:<10}")

    # Interaction effects
    interactions = result.get("interaction_effects", [])
    if interactions:
        print(f"\nInteraction Effects (2-module ablation):")
        print(f"  {'Pair':<40} {'Actual Δ':>9} {'Expected Δ':>10} {'Interaction':>12} {'Kind':<10}")
        print("  " + "-" * 83)
        for ie in interactions:
            print(f"  {ie['pair']:<40} {ie['pair_delta']:>+9.4f} "
                  f"{ie['expected_delta']:>+10.4f} "
                  f"{ie['interaction']:>+12.4f} {ie['kind']:<10}")
    elif result.get("schema_version") == "2.0":
        print("\nNo significant interaction effects detected.")

    # Assembly detail for most impactful single-module ablation
    if rankings:
        most = rankings[0]["module"]
        abl = result.get("ablations", {}).get(most, {})
        ad = abl.get("assembly_details", {})
        if ad:
            print(f"\nMost impactful ablation detail: {most}")
            print(f"  diversity={ad.get('diversity', '?'):.4f}  "
                  f"volume={ad.get('volume', '?'):.4f}  "
                  f"avg_sections={ad.get('avg_sections', '?')}  "
                  f"avg_chars={ad.get('avg_chars', '?')}")

    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CLR Perturbation / Ablation Harness v2")
    parser.add_argument(
        "--module", type=str, default=None,
        help="Ablate a single module (default: all)",
    )
    parser.add_argument(
        "--pairs", action="store_true",
        help="Also run 2-module combination ablations for interaction effects",
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
    result = run_ablation_sweep(modules, include_pairs=args.pairs)
    print_report(result)


if __name__ == "__main__":
    main()
