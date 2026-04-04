"""CLR-Benchmark — external task-based memory evaluation framework.

Separated from CLR-Internal (clr.py) which measures Clarvis architecture health.
CLR-Benchmark evaluates memory-enabled assistants on external tasks using
dataset adapters (LongMemEval, MemBench, BEAM) with a shared ability taxonomy.

This module:
  - Aggregates results from individual benchmark adapters
  - Produces unified per-ability scores across benchmarks
  - Generates stage-separated failure reports
  - Compares normal vs oracle retrieval modes

CLR-Internal (clr.py): Clarvis operational health composite (7 dimensions).
CLR-Benchmark (this file): External task benchmark framework (ability taxonomy).

Usage:
    python3 -m clarvis metrics clr-benchmark          # Run all adapters
    python3 -m clarvis metrics clr-benchmark --quick   # LongMemEval + MemBench only
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = os.path.join(WORKSPACE, "data", "benchmarks")
CLR_BENCH_FILE = os.path.join(DATA_DIR, "clr_benchmark_latest.json")
CLR_BENCH_HISTORY = os.path.join(DATA_DIR, "clr_benchmark_history.jsonl")

CLR_BENCHMARK_VERSION = "1.0"

# ── Unified ability taxonomy ─────────────────────────────────────────
# Maps external benchmark abilities to a shared taxonomy.

ABILITY_TAXONOMY = {
    # Core retrieval
    "information_extraction": {
        "label": "Information Extraction",
        "description": "Retrieve explicitly stated facts from memory",
        "sources": {"longmemeval": "IE", "membench": "participation-factual"},
    },
    "multi_session_reasoning": {
        "label": "Multi-Session Reasoning",
        "description": "Combine information across multiple sessions",
        "sources": {"longmemeval": "MR"},
    },
    "knowledge_update": {
        "label": "Knowledge Update",
        "description": "Handle updated or overwritten facts correctly",
        "sources": {"longmemeval": "KU"},
    },
    "temporal_reasoning": {
        "label": "Temporal Reasoning",
        "description": "Reason about time and order of events",
        "sources": {"longmemeval": "TR"},
    },
    "abstention": {
        "label": "Abstention",
        "description": "Correctly refuse when information is unavailable",
        "sources": {"longmemeval": "ABS"},
    },
    # MemBench-specific
    "reflective_memory": {
        "label": "Reflective Memory",
        "description": "Infer preferences and tendencies from interactions",
        "sources": {"membench": "participation-reflective"},
    },
    "observation_factual": {
        "label": "Observation (Factual)",
        "description": "Store facts from observed/ingested data",
        "sources": {"membench": "observation-factual"},
    },
    "observation_reflective": {
        "label": "Observation (Reflective)",
        "description": "Infer patterns from passively observed data",
        "sources": {"membench": "observation-reflective"},
    },
    # Advanced abilities (v1.1 — added for BEAM coverage gaps)
    "contradiction_resolution": {
        "label": "Contradiction Resolution",
        "description": "Detect and resolve conflicting facts across sessions",
        "sources": {"beam": "contradiction"},
    },
    "event_ordering": {
        "label": "Event Ordering",
        "description": "Reconstruct correct temporal sequence of events",
        "sources": {"beam": "EO"},
    },
    "persistent_instruction": {
        "label": "Persistent Instruction",
        "description": "Follow instructions given in earlier sessions across later sessions",
        "sources": {"beam": "PI"},
    },
    "summarization": {
        "label": "Summarization",
        "description": "Accurately compress multi-source information into concise summaries",
        "sources": {"beam": "SUM"},
    },
    "cross_domain_robustness": {
        "label": "Cross-Domain Robustness",
        "description": "Retrieve and link facts across different knowledge domains",
        "sources": {"beam": "XD"},
    },
}


# ── Stage breakdown ──────────────────────────────────────────────────

FAILURE_STAGES = [
    "retrieval",        # Did we find relevant evidence?
    "evidence_quality", # Is retrieved evidence sufficient?
    "reasoning",        # Did we reason correctly over evidence?
    "answer",           # Is the final answer correct?
]


def _map_membench_to_abilities(membench_report: dict) -> dict[str, dict]:
    """Map MemBench quadrant scores to unified abilities."""
    mapped = {}
    quadrant_map = {
        "participation-factual": "information_extraction",
        "participation-reflective": "reflective_memory",
        "observation-factual": "observation_factual",
        "observation-reflective": "observation_reflective",
    }
    for quadrant, ability_key in quadrant_map.items():
        qs = membench_report.get("by_quadrant", {}).get(quadrant)
        if qs:
            mapped[ability_key] = {
                "source": "membench",
                "source_key": quadrant,
                "effectiveness": qs.get("effectiveness", 0.0),
                "precision_at_1": qs.get("recall", 0.0),
                "n": qs.get("total", 0),
                "failures": qs.get("failures", []),
            }
    return mapped


def _map_longmemeval_to_abilities(lme_report: dict) -> dict[str, dict]:
    """Map LongMemEval ability scores to unified abilities."""
    mapped = {}
    ability_map = {
        "IE": "information_extraction",
        "MR": "multi_session_reasoning",
        "KU": "knowledge_update",
        "TR": "temporal_reasoning",
        "ABS": "abstention",
    }
    for lme_key, ability_key in ability_map.items():
        data = lme_report.get("by_ability", {}).get(lme_key)
        if data:
            mapped[ability_key] = {
                "source": "longmemeval",
                "source_key": lme_key,
                "effectiveness": data.get("effectiveness", 0.0),
                "precision_at_1": data.get("precision_at_1", 0.0),
                "n": data.get("total", 0),
                "failures": data.get("failures", []),
            }
    return mapped


def _map_beam_to_abilities(beam_report: dict) -> dict[str, dict]:
    """Map BEAM subset ability scores to unified abilities."""
    mapped = {}
    ability_map = {
        "CR": "contradiction_resolution",
        "EO": "event_ordering",
        "PI": "persistent_instruction",
        "SUM": "summarization",
        "XD": "cross_domain_robustness",
    }
    for beam_key, ability_key in ability_map.items():
        data = beam_report.get("by_ability", {}).get(beam_key)
        if data:
            mapped[ability_key] = {
                "source": "beam",
                "source_key": beam_key,
                "effectiveness": data.get("effectiveness", 0.0),
                "precision_at_1": data.get("precision_at_1", 0.0),
                "n": data.get("total", 0),
                "failures": data.get("failures", []),
            }
    return mapped


def compute_clr_benchmark(
    run_longmemeval: bool = True,
    run_membench: bool = True,
    run_beam: bool = False,
    oracle: bool = False,
) -> dict:
    """Compute CLR-Benchmark by running available adapters and aggregating.

    Args:
        run_longmemeval: Include LongMemEval adapter.
        run_membench: Include MemBench adapter.
        run_beam: Include BEAM subset adapter.
        oracle: Use oracle retrieval mode.

    Returns:
        Unified benchmark report with per-ability scores, stage diagnostics,
        and aggregate metrics.
    """
    adapter_reports = {}
    all_ability_scores: dict[str, list[dict]] = {}

    # Run LongMemEval
    if run_longmemeval:
        try:
            from clarvis.metrics.longmemeval import run_longmemeval as _run_lme
            lme = _run_lme(oracle=oracle)
            adapter_reports["longmemeval"] = {
                "effectiveness": lme["aggregate_effectiveness"],
                "precision_at_1": lme["aggregate_precision_at_1"],
                "total_tasks": lme["total_tasks"],
                "total_hits": lme["total_hits"],
                "stage_diagnostics": lme.get("stage_diagnostics", {}),
            }
            for ability_key, scores in _map_longmemeval_to_abilities(lme).items():
                all_ability_scores.setdefault(ability_key, []).append(scores)
        except Exception as e:
            adapter_reports["longmemeval"] = {"error": str(e)}

    # Run MemBench
    if run_membench:
        try:
            from clarvis.metrics.membench import run_membench as _run_mb
            mb = _run_mb(oracle=oracle)
            adapter_reports["membench"] = {
                "effectiveness": mb["aggregate_effectiveness"],
                "precision_at_1": mb["aggregate_recall"],
                "total_tasks": mb["total_tasks"],
                "total_hits": mb["total_hits"],
            }
            for ability_key, scores in _map_membench_to_abilities(mb).items():
                all_ability_scores.setdefault(ability_key, []).append(scores)
        except Exception as e:
            adapter_reports["membench"] = {"error": str(e)}

    # Run BEAM subset
    if run_beam:
        try:
            from clarvis.metrics.beam import run_beam as _run_beam
            beam = _run_beam(oracle=oracle)
            adapter_reports["beam"] = {
                "effectiveness": beam["aggregate_effectiveness"],
                "precision_at_1": beam["aggregate_precision_at_1"],
                "total_tasks": beam["total_tasks"],
                "total_hits": beam["total_hits"],
            }
            for ability_key, scores in _map_beam_to_abilities(beam).items():
                all_ability_scores.setdefault(ability_key, []).append(scores)
        except Exception as e:
            adapter_reports["beam"] = {"error": str(e)}

    # Merge abilities — when multiple sources cover the same ability, average
    unified_abilities = {}
    for ability_key, sources in all_ability_scores.items():
        taxonomy = ABILITY_TAXONOMY.get(ability_key, {})
        eff_values = [s["effectiveness"] for s in sources]
        p1_values = [s["precision_at_1"] for s in sources]
        total_n = sum(s["n"] for s in sources)
        all_failures = []
        for s in sources:
            all_failures.extend(s.get("failures", []))

        unified_abilities[ability_key] = {
            "label": taxonomy.get("label", ability_key),
            "effectiveness": round(sum(eff_values) / len(eff_values), 3),
            "precision_at_1": round(sum(p1_values) / len(p1_values), 3),
            "n": total_n,
            "source_count": len(sources),
            "sources": [s["source"] for s in sources],
            "failures": all_failures,
        }

    # Aggregate
    if unified_abilities:
        # Weighted by task count
        total_n = sum(a["n"] for a in unified_abilities.values())
        if total_n > 0:
            agg_eff = sum(a["effectiveness"] * a["n"] for a in unified_abilities.values()) / total_n
            agg_p1 = sum(a["precision_at_1"] * a["n"] for a in unified_abilities.values()) / total_n
        else:
            agg_eff = agg_p1 = 0.0
    else:
        agg_eff = agg_p1 = 0.0
        total_n = 0

    # Stage diagnostics (from LongMemEval if available)
    stage = adapter_reports.get("longmemeval", {}).get("stage_diagnostics", {})

    report = {
        "benchmark": "clr-benchmark",
        "version": CLR_BENCHMARK_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "oracle" if oracle else "full-history",
        "aggregate_effectiveness": round(agg_eff, 3),
        "aggregate_precision_at_1": round(agg_p1, 3),
        "total_tasks": total_n,
        "abilities_evaluated": len(unified_abilities),
        "abilities_total": len(ABILITY_TAXONOMY),
        "by_ability": unified_abilities,
        "adapter_reports": adapter_reports,
        "stage_diagnostics": stage,
    }

    return report


def save_report(report: dict):
    """Save CLR-Benchmark report to latest file and history."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CLR_BENCH_FILE, "w") as f:
        json.dump(report, f, indent=2)

    summary = {
        "timestamp": report["timestamp"],
        "mode": report["mode"],
        "aggregate_effectiveness": report["aggregate_effectiveness"],
        "aggregate_precision_at_1": report["aggregate_precision_at_1"],
        "total_tasks": report["total_tasks"],
        "abilities_evaluated": report["abilities_evaluated"],
        "adapter_reports": {
            k: {kk: vv for kk, vv in v.items() if kk != "stage_diagnostics"}
            for k, v in report["adapter_reports"].items()
        },
    }
    with open(CLR_BENCH_HISTORY, "a") as f:
        f.write(json.dumps(summary) + "\n")


def format_report(report: dict) -> str:
    """Format CLR-Benchmark report for terminal display."""
    lines = ["=== CLR-Benchmark — External Task Evaluation ===", ""]
    lines.append(f"  Version: {report.get('version', '?')}")
    lines.append(f"  Mode:    {report.get('mode', 'full-history').upper()}")
    lines.append(f"  Tasks:   {report['total_tasks']}")
    lines.append(f"  Abilities evaluated: {report['abilities_evaluated']}/{report['abilities_total']}")
    lines.append(f"  Effectiveness: {report['aggregate_effectiveness']:.1%}")
    lines.append(f"  P@1:           {report['aggregate_precision_at_1']:.1%}")
    lines.append("")

    # Adapter summary
    lines.append("  Adapter Results:")
    for adapter, data in report.get("adapter_reports", {}).items():
        if "error" in data:
            lines.append(f"    {adapter:<15} ERROR: {data['error']}")
        else:
            lines.append(f"    {adapter:<15} eff={data.get('effectiveness', 0):.1%} "
                         f"p@1={data.get('precision_at_1', 0):.1%} "
                         f"n={data.get('total_tasks', 0)}")
    lines.append("")

    # Per-ability table
    lines.append(f"  {'Ability':<28} {'Eff':>6} {'P@1':>6} {'N':>4} {'Src':>4}  Failures")
    lines.append(f"  {'─' * 70}")

    for key in ABILITY_TAXONOMY:
        data = report["by_ability"].get(key)
        if not data:
            lines.append(f"  {ABILITY_TAXONOMY[key]['label']:<28} {'—':>6} {'—':>6} {'0':>4} {'0':>4}  (not evaluated)")
            continue
        fails = ", ".join(data.get("failures", [])[:5]) or "—"
        if len(data.get("failures", [])) > 5:
            fails += f" (+{len(data['failures']) - 5})"
        lines.append(
            f"  {data['label']:<28} {data['effectiveness']:>5.1%} "
            f"{data['precision_at_1']:>5.1%} {data['n']:>4} "
            f"{data['source_count']:>4}  {fails}"
        )

    # Stage diagnostics
    stage = report.get("stage_diagnostics", {})
    if stage.get("n", 0) > 0:
        lines.append("")
        lines.append("  Stage Diagnostics (from LongMemEval):")
        lines.append(f"    Retrieval rate:   {stage.get('retrieval_rate', 0):.1%}")
        lines.append(f"    Evidence quality: {stage.get('evidence_quality_avg', 0):.3f}")
        lines.append(f"    Answer rate:      {stage.get('answer_rate', 0):.1%}")

    lines.append("")
    return "\n".join(lines)
