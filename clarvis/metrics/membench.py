"""MemBench adapter — four-quadrant memory evaluation.

Evaluates Clarvis memory along two axes:
  - Scenario: participation (first-person agent) vs observation (third-person log)
  - Memory level: factual (explicit facts) vs reflective (inferred preferences/tendencies)

Four quadrants:
  1. participation-factual: Did Clarvis store explicit facts from conversations?
  2. participation-reflective: Can Clarvis infer preferences/tendencies from interactions?
  3. observation-factual: Did Clarvis store facts from observed/ingested data?
  4. observation-reflective: Can Clarvis infer patterns from passively observed data?

Metrics per quadrant:
  - effectiveness: fraction of correct answers (hit rate)
  - recall: fraction of stored facts that are retrievable
  - capacity: how many facts can be stored and retrieved (score vs count)
  - temporal_efficiency: does retrieval degrade with time/distance?

Usage:
    python3 -m clarvis bench membench              # Run all quadrants
    python3 -m clarvis bench membench --quadrant participation-factual
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = os.path.join(WORKSPACE, "data", "benchmarks")
MEMBENCH_FILE = os.path.join(DATA_DIR, "membench_latest.json")
MEMBENCH_HISTORY = os.path.join(DATA_DIR, "membench_history.jsonl")

# ── Quadrant definitions ─────────────────────────────────────────────

QUADRANTS = [
    "participation-factual",
    "participation-reflective",
    "observation-factual",
    "observation-reflective",
]

# ── Benchmark tasks ──────────────────────────────────────────────────
# Each task has: id, quadrant, query, expected_substrings (ground truth),
# collections to search, gold_evidence (for oracle mode),
# and temporal_hint (timestamp proximity for temporal_efficiency).

MEMBENCH_TASKS: list[dict[str, Any]] = [
    # ── participation-factual ──
    # Facts Clarvis learned through direct conversation/interaction
    {
        "id": "MF01",
        "quadrant": "participation-factual",
        "query": "Who is Clarvis's creator?",
        "expected_substrings": ["operator", "granus"],
        "collections": ["clarvis-identity"],
        "gold_evidence": "Clarvis was created by the operator (GranusClarvis).",
        "temporal_hint": "early",
    },
    {
        "id": "MF02",
        "quadrant": "participation-factual",
        "query": "What timezone does the user prefer?",
        "expected_substrings": ["cet"],
        "collections": ["clarvis-preferences"],
        "gold_evidence": "User timezone is CET (Central European Time).",
        "temporal_hint": "early",
    },
    {
        "id": "MF03",
        "quadrant": "participation-factual",
        "query": "What is the gateway port number?",
        "expected_substrings": ["18789"],
        "collections": ["clarvis-infrastructure"],
        "gold_evidence": "OpenClaw gateway runs on port 18789.",
        "temporal_hint": "early",
    },
    {
        "id": "MF04",
        "quadrant": "participation-factual",
        "query": "What model does the conscious layer use?",
        "expected_substrings": ["minimax", "m2.5"],
        "collections": ["clarvis-infrastructure", "clarvis-identity"],
        "gold_evidence": "Conscious layer runs MiniMax M2.5 via OpenClaw gateway.",
        "temporal_hint": "mid",
    },
    {
        "id": "MF05",
        "quadrant": "participation-factual",
        "query": "What database does ClarvisDB use?",
        "expected_substrings": ["chromadb", "chroma"],
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "gold_evidence": "ClarvisDB uses ChromaDB with ONNX MiniLM embeddings, fully local.",
        "temporal_hint": "early",
    },
    # ── participation-reflective ──
    # Inferred preferences/tendencies from conversations
    {
        "id": "MR01",
        "quadrant": "participation-reflective",
        "query": "What communication style does the user prefer?",
        "expected_substrings": ["direct", "concise", "no fluff"],
        "collections": ["clarvis-preferences", "clarvis-memories"],
        "gold_evidence": "User prefers direct, concise communication. No fluff, no preamble.",
        "temporal_hint": "early",
    },
    {
        "id": "MR02",
        "quadrant": "participation-reflective",
        "query": "How does Clarvis decide when to act vs ask?",
        "expected_substrings": ["autonomy", "act first", "reversible"],
        "collections": ["clarvis-learnings"],
        "gold_evidence": "Act first on reversible low-risk tasks. Ask first on irreversible/high-risk decisions.",
        "temporal_hint": "mid",
    },
    {
        "id": "MR03",
        "quadrant": "participation-reflective",
        "query": "What is Clarvis's long-term aspiration?",
        "expected_substrings": ["agi", "consciousness", "evolve", "north star"],
        "collections": ["clarvis-goals", "clarvis-identity"],
        "gold_evidence": "North star: evolve toward AGI-like consciousness through self-improvement.",
        "temporal_hint": "early",
    },
    {
        "id": "MR04",
        "quadrant": "participation-reflective",
        "query": "What patterns lead to task failures?",
        "expected_substrings": ["timeout", "lock", "import", "permission"],
        "collections": ["clarvis-learnings", "clarvis-memories"],
        "gold_evidence": "Common failure patterns: lockfile contention, import errors, permission issues, timeouts on long tasks.",
        "temporal_hint": "recent",
    },
    {
        "id": "MR05",
        "quadrant": "participation-reflective",
        "query": "How does Clarvis prioritize tasks?",
        "expected_substrings": ["salience", "attention", "p0", "p1", "priority"],
        "collections": ["clarvis-learnings", "clarvis-procedures"],
        "gold_evidence": "Tasks prioritized by GWT salience scoring. Queue priorities: P0 (immediate) > P1 (this week) > P2 (when idle).",
        "temporal_hint": "mid",
    },
    # ── observation-factual ──
    # Facts from ingested/observed data (cron outputs, logs, metrics)
    {
        "id": "OF01",
        "quadrant": "observation-factual",
        "query": "What are the current brain statistics?",
        "expected_substrings": ["memories", "collection", "graph"],
        "collections": ["clarvis-context", "clarvis-infrastructure"],
        "gold_evidence": "Brain has 3400+ memories across 10 collections with 134k+ graph edges.",
        "temporal_hint": "recent",
    },
    {
        "id": "OF02",
        "quadrant": "observation-factual",
        "query": "What runs at 4:00 AM in the cron schedule?",
        "expected_substrings": ["graph", "checkpoint", "maintenance"],
        "collections": ["clarvis-infrastructure", "clarvis-procedures"],
        "gold_evidence": "04:00 cron_graph_checkpoint.sh runs graph checkpoint with SHA-256 verification.",
        "temporal_hint": "mid",
    },
    {
        "id": "OF03",
        "quadrant": "observation-factual",
        "query": "What embedding model is used for brain search?",
        "expected_substrings": ["minilm", "onnx", "all-minilm"],
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "gold_evidence": "ONNX MiniLM (all-MiniLM-L6-v2) embeddings for brain search.",
        "temporal_hint": "early",
    },
    {
        "id": "OF04",
        "quadrant": "observation-factual",
        "query": "How many cron jobs run the autonomous evolution?",
        "expected_substrings": ["12", "autonomous", "cron_autonomous"],
        "collections": ["clarvis-infrastructure", "clarvis-context"],
        "gold_evidence": "cron_autonomous.sh runs 12x/day (11 on Wed/Sat when strategic audit replaces one slot).",
        "temporal_hint": "mid",
    },
    {
        "id": "OF05",
        "quadrant": "observation-factual",
        "query": "What is the maximum episode memory capacity?",
        "expected_substrings": ["500"],
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "gold_evidence": "Episodic memory capped at 500 episodes (most recent kept).",
        "temporal_hint": "mid",
    },
    # ── observation-reflective ──
    # Patterns inferred from observed/ingested data
    {
        "id": "OR01",
        "quadrant": "observation-reflective",
        "query": "What recurring issues affect cron reliability?",
        "expected_substrings": ["lock", "stale", "timeout", "cron"],
        "collections": ["clarvis-learnings", "clarvis-memories"],
        "gold_evidence": "Recurring cron issues: stale lockfiles, process timeouts, nesting guard leaks, resource contention during maintenance window.",
        "temporal_hint": "recent",
    },
    {
        "id": "OR02",
        "quadrant": "observation-reflective",
        "query": "What is the typical performance bottleneck?",
        "expected_substrings": ["query", "speed", "onnx", "cpu", "latency"],
        "collections": ["clarvis-learnings", "clarvis-infrastructure"],
        "gold_evidence": "Performance bottleneck: brain query speed ~7.5s avg due to sequential ONNX CPU queries across 10 collections. Optimization path: parallel queries, caching.",
        "temporal_hint": "recent",
    },
    {
        "id": "OR03",
        "quadrant": "observation-reflective",
        "query": "What theme dominates recent evolution work?",
        "expected_substrings": ["benchmark", "quality", "open-source", "website", "public"],
        "collections": ["clarvis-context", "clarvis-memories", "clarvis-learnings"],
        "gold_evidence": "Recent evolution focused on: open-source readiness, public website, benchmark infrastructure (CLR, retrieval, MemBench), repo hygiene for 2026-03-31 delivery deadline.",
        "temporal_hint": "recent",
    },
    {
        "id": "OR04",
        "quadrant": "observation-reflective",
        "query": "What distinguishes successful from failed heartbeats?",
        "expected_substrings": ["success", "failure", "clear", "scope", "concrete"],
        "collections": ["clarvis-learnings", "clarvis-memories"],
        "gold_evidence": "Successful heartbeats: clear scope, concrete deliverable, tested output. Failed heartbeats: vague scope, over-ambition, dependency on unavailable resources.",
        "temporal_hint": "mid",
    },
    {
        "id": "OR05",
        "quadrant": "observation-reflective",
        "query": "What is the weakest performance dimension?",
        "expected_substrings": ["brier", "calibration", "confidence"],
        "collections": ["clarvis-learnings", "clarvis-context"],
        "gold_evidence": "Weakest dimension: Brier calibration score (0.06). Prediction-outcome loop needs audit: bucket distributions, stale predictions, bin edge recalibration.",
        "temporal_hint": "recent",
    },
]


def _check_hit(result: dict, task: dict) -> bool:
    """Check if a retrieval result matches expected ground truth."""
    doc = result.get("document", "").lower()
    for sub in task["expected_substrings"]:
        if sub.lower() in doc:
            return True
    return False


def _recall_for_task(task: dict, brain_recall, k: int = 3, oracle: bool = False) -> list[dict]:
    """Retrieve results for a task, optionally using oracle mode."""
    if oracle:
        gold = task.get("gold_evidence", "")
        if not gold:
            return []
        return [{
            "document": gold,
            "id": f"oracle_{task['id']}",
            "collection": task["collections"][0] if task["collections"] else "oracle",
            "distance": 0.0,
        }]
    return brain_recall(task["query"], n=k, caller="membench")


def _evaluate_task(task: dict, brain_recall, k: int, oracle: bool, qr: dict) -> dict:
    """Evaluate a single MemBench task and update quadrant accumulator."""
    th = task.get("temporal_hint", "mid")
    if th == "early":
        qr["early_total"] += 1
    elif th == "recent":
        qr["recent_total"] += 1
    else:
        qr["mid_total"] += 1

    t0 = time.monotonic()
    results = _recall_for_task(task, brain_recall, k=k, oracle=oracle)
    latency_ms = round((time.monotonic() - t0) * 1000, 1)

    hit, first_hit = False, False
    for i, r in enumerate(results[:k]):
        if _check_hit(r, task):
            hit = True
            if i == 0:
                first_hit = True
            break

    if hit:
        qr["hits"] += 1
        if th == "early":
            qr["early_hits"] += 1
        elif th == "recent":
            qr["recent_hits"] += 1
        else:
            qr["mid_hits"] += 1
    if first_hit:
        qr["first_hits"] += 1

    detail = {
        "id": task["id"], "quadrant": task["quadrant"], "query": task["query"],
        "hit": hit, "first_hit": first_hit, "latency_ms": latency_ms,
        "temporal_hint": th, "n_results": len(results[:k]),
    }
    qr["details"].append(detail)
    return detail


def _compute_quadrant_scores(quadrant_results: dict) -> dict:
    """Compute per-quadrant metrics from accumulated results."""
    quadrant_scores = {}
    for q, qr in quadrant_results.items():
        total = qr["total"]
        effectiveness = round(qr["hits"] / total, 3) if total > 0 else 0.0
        recall = round(qr["first_hits"] / total, 3) if total > 0 else 0.0
        capacity = round(qr["hits"] / total, 3) if total > 0 else 0.0

        early_rate = (qr["early_hits"] / qr["early_total"]) if qr["early_total"] > 0 else None
        recent_rate = (qr["recent_hits"] / qr["recent_total"]) if qr["recent_total"] > 0 else None
        if early_rate is not None and recent_rate is not None and recent_rate > 0:
            temporal_efficiency = round(early_rate / recent_rate, 3)
        else:
            temporal_efficiency = None

        quadrant_scores[q] = {
            "total": total, "hits": qr["hits"],
            "effectiveness": effectiveness, "recall": recall,
            "capacity": capacity, "temporal_efficiency": temporal_efficiency,
            "early_rate": round(early_rate, 3) if early_rate is not None else None,
            "recent_rate": round(recent_rate, 3) if recent_rate is not None else None,
            "failures": [d["id"] for d in qr["details"] if not d["hit"]],
        }
    return quadrant_scores


def run_membench(
    quadrant: str | None = None,
    k: int = 3,
    oracle: bool = False,
) -> dict:
    """Run MemBench evaluation across selected quadrants.

    Args:
        quadrant: Specific quadrant to evaluate, or None for all.
        k: Number of retrieval results to consider.
        oracle: Inject gold evidence instead of real retrieval.

    Returns:
        Report dict with per-quadrant and aggregate metrics.
    """
    from clarvis.brain import brain

    tasks = MEMBENCH_TASKS
    if quadrant:
        if quadrant not in QUADRANTS:
            raise ValueError(f"Unknown quadrant '{quadrant}'. Valid: {QUADRANTS}")
        tasks = [t for t in tasks if t["quadrant"] == quadrant]

    quadrant_results: dict[str, dict] = {}
    all_details = []

    for task in tasks:
        q = task["quadrant"]
        if q not in quadrant_results:
            quadrant_results[q] = {
                "total": 0, "hits": 0, "first_hits": 0,
                "early_hits": 0, "early_total": 0,
                "mid_hits": 0, "mid_total": 0,
                "recent_hits": 0, "recent_total": 0,
                "details": [],
            }
        quadrant_results[q]["total"] += 1
        detail = _evaluate_task(task, brain.recall, k, oracle, quadrant_results[q])
        all_details.append(detail)

    quadrant_scores = _compute_quadrant_scores(quadrant_results)

    total_tasks = len(all_details)
    total_hits = sum(qs["hits"] for qs in quadrant_scores.values())
    total_first_hits = sum(qr["first_hits"] for qr in quadrant_results.values())

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "oracle_mode": oracle, "k": k, "quadrant_filter": quadrant,
        "total_tasks": total_tasks, "total_hits": total_hits,
        "aggregate_effectiveness": round(total_hits / total_tasks, 3) if total_tasks > 0 else 0.0,
        "aggregate_recall": round(total_first_hits / total_tasks, 3) if total_tasks > 0 else 0.0,
        "by_quadrant": quadrant_scores, "details": all_details,
    }


def save_report(report: dict):
    """Save report to latest file and append to history."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MEMBENCH_FILE, "w") as f:
        json.dump(report, f, indent=2)

    summary = {
        "timestamp": report["timestamp"],
        "oracle_mode": report["oracle_mode"],
        "total_tasks": report["total_tasks"],
        "aggregate_effectiveness": report["aggregate_effectiveness"],
        "aggregate_recall": report["aggregate_recall"],
        "by_quadrant": {
            q: {k: v for k, v in qs.items() if k != "failures"}
            for q, qs in report["by_quadrant"].items()
        },
    }
    with open(MEMBENCH_HISTORY, "a") as f:
        f.write(json.dumps(summary) + "\n")


def format_report(report: dict) -> str:
    """Format MemBench report for terminal display."""
    lines = ["=== MemBench Evaluation ===", ""]
    if report["oracle_mode"]:
        lines.append("  Mode: ORACLE (gold evidence injected)")
    lines.append(f"  Tasks: {report['total_tasks']}  Hits: {report['total_hits']}")
    lines.append(f"  Effectiveness: {report['aggregate_effectiveness']:.1%}")
    lines.append(f"  Recall (P@1):  {report['aggregate_recall']:.1%}")
    lines.append("")

    lines.append(f"  {'Quadrant':<30} {'Eff':>6} {'Recall':>7} {'Cap':>6} {'Temp':>6}  Failures")
    lines.append(f"  {'─' * 75}")

    for q in QUADRANTS:
        qs = report["by_quadrant"].get(q)
        if not qs:
            continue
        te = f"{qs['temporal_efficiency']:.2f}" if qs["temporal_efficiency"] is not None else "N/A"
        fails = ", ".join(qs.get("failures", [])) or "—"
        lines.append(
            f"  {q:<30} {qs['effectiveness']:>5.1%} {qs['recall']:>6.1%} "
            f"{qs['capacity']:>5.1%} {te:>6}  {fails}"
        )

    lines.append("")
    return "\n".join(lines)
