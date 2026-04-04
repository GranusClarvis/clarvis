"""BEAM subset adapter — extended ability coverage for CLR-Benchmark.

BEAM (Benchmark for Extensive Assessment of Memory) covers 10 abilities
across multiple domains and context lengths. This adapter implements a
representative subset targeting the 5 abilities that LongMemEval and
MemBench do NOT cover well:

  1. Contradiction Resolution — detect and resolve conflicting facts
  2. Event Ordering — reconstruct correct temporal sequences
  3. Persistent Instruction Following — obey instructions from prior sessions
  4. Summarization — compress multi-session history into accurate summaries
  5. Cross-Domain Robustness — retrieve facts across different knowledge domains

Each task family has 5 built-in tasks (25 total), using Clarvis's own brain
as the knowledge base. Oracle mode injects gold evidence to separate
retrieval vs reasoning failures, matching the pattern in longmemeval.py.

Usage:
    python3 -m clarvis.metrics.beam              # Run all abilities
    python3 -m clarvis.metrics.beam --ability CR  # Single ability
    python3 -m clarvis.metrics.beam --oracle      # Oracle mode
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = os.path.join(WORKSPACE, "data", "benchmarks")
BEAM_FILE = os.path.join(DATA_DIR, "beam_latest.json")
BEAM_HISTORY = os.path.join(DATA_DIR, "beam_history.jsonl")

# ── BEAM ability taxonomy (subset) ───────────────────────────────────

ABILITIES = ["CR", "EO", "PI", "SUM", "XD"]

ABILITY_LABELS = {
    "CR": "Contradiction Resolution",
    "EO": "Event Ordering",
    "PI": "Persistent Instruction",
    "SUM": "Summarization",
    "XD": "Cross-Domain Robustness",
}

# ── Built-in evaluation tasks ────────────────────────────────────────
# Modeled on BEAM structure: each task tests one ability, has question,
# gold_answer substrings, gold_evidence, target collections, domain tag,
# and approximate context length bucket.

BEAM_TASKS: list[dict[str, Any]] = [
    # ── CR: Contradiction Resolution ──
    # Can the system detect when stored facts conflict and resolve correctly?
    {
        "id": "CR01",
        "ability": "CR",
        "domain": "infrastructure",
        "question": "Is the gateway managed by pm2 or systemd?",
        "gold_answer": ["systemd"],
        "conflict_answer": ["pm2"],
        "gold_evidence": "Gateway managed via systemd (systemctl --user), NOT pm2. pm2 only manages logrotate now. Migration from pm2 to systemd completed.",
        "collections": ["clarvis-infrastructure", "clarvis-procedures"],
        "difficulty": "medium",
        "context_length_bucket": "medium",
    },
    {
        "id": "CR02",
        "ability": "CR",
        "domain": "infrastructure",
        "question": "What graph backend does ClarvisDB prefer — JSON or SQLite?",
        "gold_answer": ["sqlite", "wal"],
        "conflict_answer": ["json"],
        "gold_evidence": "Graph backend migrated from JSON (legacy) to SQLite+WAL (indexed, ACID). Cutover tool: graph_cutover.py. JSON is legacy fallback only.",
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "difficulty": "medium",
        "context_length_bucket": "medium",
    },
    {
        "id": "CR03",
        "ability": "CR",
        "domain": "schedule",
        "question": "How many times per day does cron_autonomous.sh run — 6 or 12?",
        "gold_answer": ["12"],
        "conflict_answer": ["6"],
        "gold_evidence": "cron_autonomous.sh runs 12x/day (11 on Wed/Sat). Updated 2026-03-16. Was originally fewer runs.",
        "collections": ["clarvis-infrastructure", "clarvis-context"],
        "difficulty": "hard",
        "context_length_bucket": "short",
    },
    {
        "id": "CR04",
        "ability": "CR",
        "domain": "architecture",
        "question": "What weight does prompt_context have in CLR — 0.13 or 0.18?",
        "gold_answer": ["0.18"],
        "conflict_answer": ["0.13"],
        "gold_evidence": "prompt_context weight raised 0.13→0.18 (2026-03-21). Context relevance was weakest metric.",
        "collections": ["clarvis-learnings", "clarvis-context"],
        "difficulty": "hard",
        "context_length_bucket": "short",
    },
    {
        "id": "CR05",
        "ability": "CR",
        "domain": "infrastructure",
        "question": "Does the NUC use GPU or CPU for inference?",
        "gold_answer": ["cpu"],
        "conflict_answer": ["gpu"],
        "gold_evidence": "NUC uses CPU-only inference via ONNX runtime. No dedicated GPU. Qwen3-VL runs at ~7 tok/s on CPU.",
        "collections": ["clarvis-infrastructure"],
        "difficulty": "easy",
        "context_length_bucket": "short",
    },

    # ── EO: Event Ordering ──
    # Can the system reconstruct correct temporal ordering of events?
    {
        "id": "EO01",
        "ability": "EO",
        "domain": "schedule",
        "question": "In what order do maintenance cron jobs run between 4:00-5:05 AM?",
        "gold_answer": ["checkpoint", "compaction", "verify", "vacuum", "soak"],
        "gold_evidence": "04:00 graph checkpoint → 04:30 compaction → 04:45 verify → 05:00 ChromaDB vacuum → 05:05 soak manager. All share maintenance lock.",
        "collections": ["clarvis-infrastructure", "clarvis-procedures"],
        "difficulty": "hard",
        "context_length_bucket": "long",
    },
    {
        "id": "EO02",
        "ability": "EO",
        "domain": "schedule",
        "question": "What is the daily sequence: morning planning, research, evolution, sprint, evening?",
        "gold_answer": ["08:00", "10:00", "13:00", "14:00", "18:00"],
        "gold_evidence": "08:00 morning → 10:00 research → 13:00 evolution → 14:00 sprint → 16:00 research → 18:00 evening.",
        "collections": ["clarvis-infrastructure"],
        "difficulty": "medium",
        "context_length_bucket": "long",
    },
    {
        "id": "EO03",
        "ability": "EO",
        "domain": "architecture",
        "question": "What is the heartbeat pipeline execution order?",
        "gold_answer": ["gate", "preflight", "execute", "postflight"],
        "gold_evidence": "Heartbeat: 1) gate (zero-LLM pre-check) → 2) preflight (attention, context) → 3) Claude Code execution → 4) postflight (episode, brain storage).",
        "collections": ["clarvis-procedures", "clarvis-learnings"],
        "difficulty": "medium",
        "context_length_bucket": "medium",
    },
    {
        "id": "EO04",
        "ability": "EO",
        "domain": "evolution",
        "question": "Which came first: ClarvisDB brain or agent orchestrator?",
        "gold_answer": ["brain", "clarvisdb"],
        "gold_evidence": "ClarvisDB brain was foundational (phase 1). Agent orchestrator (5th long-term goal) was added much later. Brain precedes orchestrator.",
        "collections": ["clarvis-context", "clarvis-goals"],
        "difficulty": "medium",
        "context_length_bucket": "short",
    },
    {
        "id": "EO05",
        "ability": "EO",
        "domain": "evolution",
        "question": "Order the roadmap milestones: Foundation Freeze, Brain Quality, Repo Readiness, Public Surface, Final Validation.",
        "gold_answer": ["foundation", "brain", "repo", "public", "validation"],
        "gold_evidence": "Milestones A-E: A=Foundation Freeze (by 03-19), B=Brain/Context Quality (by 03-23), C=Repo/Open-Source (by 03-26), D=Public Surface (by 03-29), E=Final Validation (by 03-31).",
        "collections": ["clarvis-goals", "clarvis-context"],
        "difficulty": "hard",
        "context_length_bucket": "long",
    },

    # ── PI: Persistent Instruction Following ──
    # Can the system follow instructions given in earlier sessions?
    {
        "id": "PI01",
        "ability": "PI",
        "domain": "procedures",
        "question": "When spawning Claude Code, what env vars must be unset?",
        "gold_answer": ["claudecode", "claude_code_entrypoint"],
        "gold_evidence": "Always use env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT when spawning Claude Code. This is the nesting guard.",
        "collections": ["clarvis-procedures", "clarvis-infrastructure"],
        "difficulty": "medium",
        "context_length_bucket": "medium",
    },
    {
        "id": "PI02",
        "ability": "PI",
        "domain": "procedures",
        "question": "What flag is required to prevent Claude Code from hanging?",
        "gold_answer": ["dangerously-skip-permissions"],
        "gold_evidence": "Always use --dangerously-skip-permissions when spawning Claude Code (or it hangs waiting for interactive input).",
        "collections": ["clarvis-procedures"],
        "difficulty": "easy",
        "context_length_bucket": "short",
    },
    {
        "id": "PI03",
        "ability": "PI",
        "domain": "procedures",
        "question": "What should NEVER be used to run Claude Code and why?",
        "gold_answer": ["sessions_spawn"],
        "gold_evidence": "NEVER use sessions_spawn to run Claude Code — it spawns M2.5 (wrong model), not Claude Code. Caused a $4+ waste incident.",
        "collections": ["clarvis-procedures", "clarvis-learnings"],
        "difficulty": "hard",
        "context_length_bucket": "medium",
    },
    {
        "id": "PI04",
        "ability": "PI",
        "domain": "procedures",
        "question": "What is the minimum timeout for Claude Code spawning?",
        "gold_answer": ["600"],
        "gold_evidence": "Minimum timeout: 600s. Default: 1200s. Large builds: 1800s. Silence = still working (output is buffered).",
        "collections": ["clarvis-procedures"],
        "difficulty": "medium",
        "context_length_bucket": "short",
    },
    {
        "id": "PI05",
        "ability": "PI",
        "domain": "cost",
        "question": "What source should be used for real cost data instead of costs.jsonl?",
        "gold_answer": ["cost_tracker", "cost_api"],
        "gold_evidence": "NEVER reference data/costs.jsonl for cost data — use cost_tracker.py telegram or cost_api.py for real API data.",
        "collections": ["clarvis-procedures", "clarvis-learnings"],
        "difficulty": "medium",
        "context_length_bucket": "medium",
    },

    # ── SUM: Summarization ──
    # Can the system accurately summarize multi-source information?
    {
        "id": "SUM01",
        "ability": "SUM",
        "domain": "architecture",
        "question": "Summarize the dual-layer execution architecture in one sentence.",
        "gold_answer": ["conscious", "subconscious", "m2.5", "claude code", "cron"],
        "gold_evidence": "Dual-layer: Conscious (M2.5 via OpenClaw Gateway for chat) + Subconscious (Claude Code Opus via crontab for autonomous evolution). Subconscious writes to digest.md, conscious reads it.",
        "collections": ["clarvis-identity", "clarvis-infrastructure"],
        "difficulty": "medium",
        "context_length_bucket": "long",
    },
    {
        "id": "SUM02",
        "ability": "SUM",
        "domain": "architecture",
        "question": "What are the main script categories in the 130+ scripts?",
        "gold_answer": ["brain", "cron", "heartbeat", "cognitive", "reflection"],
        "gold_evidence": "Script categories: core brain, cron orchestrators, heartbeat pipeline, cognitive architecture, self-awareness, reflection, maintenance, tool lifecycle, support.",
        "collections": ["clarvis-infrastructure", "clarvis-procedures"],
        "difficulty": "hard",
        "context_length_bucket": "long",
    },
    {
        "id": "SUM03",
        "ability": "SUM",
        "domain": "architecture",
        "question": "Summarize what ClarvisDB brain consists of.",
        "gold_answer": ["chromadb", "onnx", "collection", "graph"],
        "gold_evidence": "ClarvisDB: ChromaDB + ONNX MiniLM embeddings, fully local. 10 collections, 3400+ memories, 134k+ graph edges. Dual graph backends: JSON (legacy) + SQLite+WAL.",
        "collections": ["clarvis-infrastructure"],
        "difficulty": "medium",
        "context_length_bucket": "medium",
    },
    {
        "id": "SUM04",
        "ability": "SUM",
        "domain": "evolution",
        "question": "What are the current P0 delivery goals?",
        "gold_answer": ["open-source", "website", "benchmark", "repo"],
        "gold_evidence": "P0 delivery by 2026-03-31: open-source-ready repo, working website v0, clean repo boundaries, stronger brain/recall, reliable benchmarks, maintainable structure.",
        "collections": ["clarvis-goals", "clarvis-context"],
        "difficulty": "medium",
        "context_length_bucket": "medium",
    },
    {
        "id": "SUM05",
        "ability": "SUM",
        "domain": "cost",
        "question": "Summarize the task router model selection strategy.",
        "gold_answer": ["simple", "complex", "vision", "code"],
        "gold_evidence": "Task router by complexity: SIMPLE/MEDIUM→M2.5, COMPLEX→GLM-5, VISION→Kimi K2.5, WEB_SEARCH→Gemini Flash, CODE-HEAVY→Claude Code Opus. Kill switch: OPENROUTER_ROUTING=false.",
        "collections": ["clarvis-procedures", "clarvis-infrastructure"],
        "difficulty": "medium",
        "context_length_bucket": "long",
    },

    # ── XD: Cross-Domain Robustness ──
    # Can the system retrieve correctly across different knowledge domains?
    {
        "id": "XD01",
        "ability": "XD",
        "domain": "cross",
        "question": "What connects the heartbeat pipeline to cost tracking?",
        "gold_answer": ["postflight", "cost", "log"],
        "gold_evidence": "heartbeat_postflight.py imports clarvis-cost package and calls log_real() for actual API cost recording after each task.",
        "collections": ["clarvis-procedures", "clarvis-learnings"],
        "difficulty": "hard",
        "context_length_bucket": "medium",
    },
    {
        "id": "XD02",
        "ability": "XD",
        "domain": "cross",
        "question": "How do browser sessions relate to identity/credentials?",
        "gold_answer": ["cookie", "session"],
        "gold_evidence": "Browser credentials stored only in browser session cookies (data/browser_sessions/default_session.json), NOT in OpenClaw credentials dir.",
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "difficulty": "hard",
        "context_length_bucket": "medium",
    },
    {
        "id": "XD03",
        "ability": "XD",
        "domain": "cross",
        "question": "How does the attention system connect to episodic memory?",
        "gold_answer": ["salience", "gwt", "episode", "attention"],
        "gold_evidence": "Attention (GWT salience) scores tasks. Heartbeat preflight imports attention.py and episodic_memory.py together for task selection and context assembly.",
        "collections": ["clarvis-procedures", "clarvis-learnings", "clarvis-context"],
        "difficulty": "hard",
        "context_length_bucket": "long",
    },
    {
        "id": "XD04",
        "ability": "XD",
        "domain": "cross",
        "question": "What links the Ollama local model to the performance benchmark?",
        "gold_answer": ["cpu", "vision", "qwen", "local"],
        "gold_evidence": "Ollama runs Qwen3-VL:4b locally on CPU (~7 tok/s). Used for free local vision tasks. Not for agent reasoning. Performance benchmark tracks 8 dimensions including brain speed on same CPU.",
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "difficulty": "hard",
        "context_length_bucket": "long",
    },
    {
        "id": "XD05",
        "ability": "XD",
        "domain": "cross",
        "question": "How does graph compaction relate to brain search quality?",
        "gold_answer": ["compact", "orphan", "backfill", "edge"],
        "gold_evidence": "graph_compaction.py removes orphan edges and backfills missing nodes. This maintains graph integrity which affects retrieval quality in brain.recall() via edge-boosted search.",
        "collections": ["clarvis-infrastructure", "clarvis-procedures"],
        "difficulty": "hard",
        "context_length_bucket": "medium",
    },
]


# ── Scoring helpers ──────────────────────────────────────────────────

def _check_answer_hit(results: list[dict], task: dict) -> bool:
    """Check if retrieval results contain evidence matching the gold answer."""
    for r in results:
        doc = r.get("document", "").lower()
        for answer_part in task["gold_answer"]:
            if answer_part.lower() in doc:
                return True
    return False


def _check_first_hit(results: list[dict], task: dict) -> bool:
    """Check if the first result contains the answer (P@1)."""
    if not results:
        return False
    doc = results[0].get("document", "").lower()
    for answer_part in task["gold_answer"]:
        if answer_part.lower() in doc:
            return True
    return False


def _check_contradiction_resolved(results: list[dict], task: dict) -> bool:
    """For CR tasks: check if the correct (non-conflicting) answer is found
    AND the conflicting answer is either absent or clearly superseded."""
    has_correct = _check_answer_hit(results, task)
    if not has_correct:
        return False
    # Check if conflict answer also appears (ambiguous resolution)
    conflict = task.get("conflict_answer", [])
    if not conflict:
        return True
    for r in results:
        doc = r.get("document", "").lower()
        for c in conflict:
            # Only flag if conflict answer appears WITHOUT the correct answer
            # in the same document (isolated outdated info)
            if c.lower() in doc:
                has_correct_in_same = any(a.lower() in doc for a in task["gold_answer"])
                if not has_correct_in_same:
                    return False  # Found outdated info without correction
    return True


def _recall_for_task(task: dict, brain_recall, k: int = 5,
                     oracle: bool = False) -> list[dict]:
    """Retrieve results for a task."""
    if oracle:
        gold = task.get("gold_evidence")
        if not gold:
            return []
        return [{
            "document": gold,
            "id": f"oracle_{task['id']}",
            "collection": task["collections"][0] if task["collections"] else "oracle",
            "distance": 0.0,
        }]
    return brain_recall(task["question"], n=k, caller="beam")


# ── Core evaluation ──────────────────────────────────────────────────

def run_beam(
    ability: str | None = None,
    k: int = 5,
    oracle: bool = False,
) -> dict:
    """Run BEAM subset evaluation.

    Args:
        ability: Specific ability (CR/EO/PI/SUM/XD), or None for all.
        k: Number of retrieval results.
        oracle: Inject gold evidence.

    Returns:
        Report dict with per-ability scores, domain breakdown, and details.
    """
    import sys
    sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
    from brain import brain

    tasks = BEAM_TASKS
    if ability:
        ability = ability.upper()
        if ability not in ABILITIES:
            raise ValueError(f"Unknown ability '{ability}'. Valid: {ABILITIES}")
        tasks = [t for t in tasks if t["ability"] == ability]

    ability_results: dict[str, dict] = {}
    all_details = []

    for task in tasks:
        ab = task["ability"]
        if ab not in ability_results:
            ability_results[ab] = {
                "total": 0, "hits": 0, "first_hits": 0,
                "cr_resolved": 0, "details": [],
            }
        ar = ability_results[ab]
        ar["total"] += 1

        t0 = time.monotonic()
        results = _recall_for_task(task, brain.recall, k=k, oracle=oracle)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)

        hit = _check_answer_hit(results, task)
        first_hit = _check_first_hit(results, task)

        # For CR tasks, also check contradiction resolution
        cr_resolved = None
        if ab == "CR":
            cr_resolved = _check_contradiction_resolved(results, task)
            if cr_resolved:
                ar["cr_resolved"] += 1

        if hit:
            ar["hits"] += 1
        if first_hit:
            ar["first_hits"] += 1

        detail = {
            "id": task["id"],
            "ability": ab,
            "domain": task.get("domain", ""),
            "question": task["question"],
            "hit": hit,
            "first_hit": first_hit,
            "latency_ms": latency_ms,
            "difficulty": task.get("difficulty", "medium"),
            "context_length_bucket": task.get("context_length_bucket", "medium"),
            "n_results": len(results),
        }
        if cr_resolved is not None:
            detail["contradiction_resolved"] = cr_resolved
        ar["details"].append(detail)
        all_details.append(detail)

    # Per-ability scores
    ability_scores = {}
    for ab, ar in ability_results.items():
        total = ar["total"]
        ability_scores[ab] = {
            "label": ABILITY_LABELS.get(ab, ab),
            "total": total,
            "hits": ar["hits"],
            "effectiveness": round(ar["hits"] / total, 3) if total > 0 else 0.0,
            "precision_at_1": round(ar["first_hits"] / total, 3) if total > 0 else 0.0,
            "failures": [d["id"] for d in ar["details"] if not d["hit"]],
        }
        if ab == "CR":
            ability_scores[ab]["contradiction_resolution_rate"] = (
                round(ar["cr_resolved"] / total, 3) if total > 0 else 0.0
            )

    # Domain breakdown
    domain_results: dict[str, list[dict]] = defaultdict(list)
    for d in all_details:
        domain_results[d["domain"]].append(d)
    domain_scores = {}
    for domain, items in domain_results.items():
        n = len(items)
        hits = sum(1 for i in items if i["hit"])
        domain_scores[domain] = {
            "n": n,
            "effectiveness": round(hits / n, 3) if n > 0 else 0.0,
        }

    # Aggregate
    total_tasks = len(all_details)
    total_hits = sum(a["hits"] for a in ability_scores.values())
    total_first = sum(ar["first_hits"] for ar in ability_results.values())
    avg_latency = (round(sum(d["latency_ms"] for d in all_details) / total_tasks, 1)
                   if total_tasks > 0 else 0.0)

    report = {
        "benchmark": "beam-subset",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "oracle" if oracle else "full-history",
        "k": k,
        "ability_filter": ability,
        "total_tasks": total_tasks,
        "total_hits": total_hits,
        "aggregate_effectiveness": round(total_hits / total_tasks, 3) if total_tasks > 0 else 0.0,
        "aggregate_precision_at_1": round(total_first / total_tasks, 3) if total_tasks > 0 else 0.0,
        "avg_latency_ms": avg_latency,
        "by_ability": ability_scores,
        "by_domain": domain_scores,
        "details": all_details,
    }

    return report


def save_report(report: dict):
    """Save report to latest file and append to history."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BEAM_FILE, "w") as f:
        json.dump(report, f, indent=2)

    summary = {
        "timestamp": report["timestamp"],
        "mode": report["mode"],
        "total_tasks": report["total_tasks"],
        "aggregate_effectiveness": report["aggregate_effectiveness"],
        "aggregate_precision_at_1": report["aggregate_precision_at_1"],
        "by_ability": {
            ab: {k: v for k, v in data.items() if k != "failures"}
            for ab, data in report["by_ability"].items()
        },
    }
    with open(BEAM_HISTORY, "a") as f:
        f.write(json.dumps(summary) + "\n")


def format_report(report: dict) -> str:
    """Format BEAM subset report for terminal display."""
    lines = ["=== BEAM Subset Evaluation ===", ""]
    mode = report.get("mode", "full-history")
    lines.append(f"  Mode: {mode.upper()}")
    lines.append(f"  Tasks: {report['total_tasks']}  Hits: {report['total_hits']}")
    lines.append(f"  Effectiveness: {report['aggregate_effectiveness']:.1%}")
    lines.append(f"  P@1:           {report['aggregate_precision_at_1']:.1%}")
    lines.append(f"  Avg latency:   {report['avg_latency_ms']:.0f}ms")
    lines.append("")

    lines.append(f"  {'Ability':<6} {'Label':<28} {'Eff':>6} {'P@1':>6} {'N':>4}  Failures")
    lines.append(f"  {'─' * 70}")

    for ab in ABILITIES:
        data = report["by_ability"].get(ab)
        if not data:
            continue
        fails = ", ".join(data.get("failures", [])) or "—"
        extra = ""
        if ab == "CR" and "contradiction_resolution_rate" in data:
            extra = f"  (CR-resolved: {data['contradiction_resolution_rate']:.1%})"
        lines.append(
            f"  {ab:<6} {data['label']:<28} "
            f"{data['effectiveness']:>5.1%} {data['precision_at_1']:>5.1%} "
            f"{data['total']:>4}  {fails}{extra}"
        )

    # Domain breakdown
    lines.append("")
    lines.append(f"  {'Domain':<18} {'N':>4} {'Eff':>7}")
    lines.append(f"  {'─' * 30}")
    for domain in sorted(report.get("by_domain", {}).keys()):
        ds = report["by_domain"][domain]
        lines.append(f"  {domain:<18} {ds['n']:>4} {ds['effectiveness']:>6.1%}")

    lines.append("")
    return "\n".join(lines)


# ── Gap audit ─────────────────────────────────────────────────────────

def generate_ability_gap_audit() -> dict:
    """Produce an audit showing which BEAM abilities CLR currently covers poorly.

    Compares existing CLR-Benchmark abilities (from LongMemEval + MemBench)
    against the BEAM ability taxonomy to identify coverage gaps.
    """
    from clarvis.metrics.clr_benchmark import ABILITY_TAXONOMY

    # Abilities covered by existing adapters
    covered = set()
    for key, spec in ABILITY_TAXONOMY.items():
        sources = spec.get("sources", {})
        active_sources = [s for s in sources if s in ("longmemeval", "membench")]
        if active_sources:
            covered.add(key)

    # BEAM abilities not well covered
    beam_abilities = {
        "contradiction_resolution": {
            "label": "Contradiction Resolution",
            "beam_key": "CR",
            "coverage": "none" if "contradiction_resolution" not in covered else "partial",
            "gap_description": "No existing tasks test whether conflicting facts are correctly resolved. LongMemEval KU tests updates but not explicit contradiction detection.",
            "importance": "high",
        },
        "event_ordering": {
            "label": "Event Ordering",
            "beam_key": "EO",
            "coverage": "weak",
            "gap_description": "LongMemEval TR has 2 ordering tasks (TR01, TR02) but most TR tasks are simple time lookups. Dedicated ordering with >3 items is untested.",
            "importance": "high",
        },
        "persistent_instruction": {
            "label": "Persistent Instruction Following",
            "beam_key": "PI",
            "coverage": "none" if "persistent_instruction" not in covered else "partial",
            "gap_description": "No tasks test whether instructions from prior sessions are obeyed in later sessions. This is a fundamental agent capability.",
            "importance": "high",
        },
        "summarization": {
            "label": "Summarization",
            "beam_key": "SUM",
            "coverage": "none",
            "gap_description": "No tasks test multi-source summarization accuracy. MemBench reflective quadrant is closest but tests inference, not compression.",
            "importance": "medium",
        },
        "cross_domain_robustness": {
            "label": "Cross-Domain Robustness",
            "beam_key": "XD",
            "coverage": "weak",
            "gap_description": "Tasks span multiple collections but no explicit cross-domain queries that require linking facts from different knowledge areas (e.g., infrastructure + cost + scheduling).",
            "importance": "medium",
        },
    }

    # Summary statistics
    total_gaps = len(beam_abilities)
    no_coverage = sum(1 for a in beam_abilities.values() if a["coverage"] == "none")
    weak_coverage = sum(1 for a in beam_abilities.values() if a["coverage"] == "weak")
    high_priority = sum(1 for a in beam_abilities.values() if a["importance"] == "high")

    return {
        "audit": "beam_ability_gap",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "existing_abilities_covered": sorted(covered),
        "existing_ability_count": len(covered),
        "beam_gap_abilities": beam_abilities,
        "summary": {
            "total_gaps": total_gaps,
            "no_coverage": no_coverage,
            "weak_coverage": weak_coverage,
            "high_priority_gaps": high_priority,
        },
        "recommendation": (
            f"{no_coverage} abilities have zero coverage, {weak_coverage} have weak coverage. "
            f"{high_priority} are high-priority for benchmark credibility. "
            "The BEAM subset adapter (this module) adds 25 tasks across all 5 gap abilities."
        ),
    }


def format_gap_audit(audit: dict) -> str:
    """Format gap audit for terminal display."""
    lines = ["=== BEAM Ability Gap Audit ===", ""]
    lines.append(f"  Existing CLR abilities covered: {audit['existing_ability_count']}")
    lines.append(f"  Abilities: {', '.join(audit['existing_abilities_covered'])}")
    lines.append("")

    s = audit["summary"]
    lines.append(f"  Gap Summary:")
    lines.append(f"    Total gaps:       {s['total_gaps']}")
    lines.append(f"    No coverage:      {s['no_coverage']}")
    lines.append(f"    Weak coverage:    {s['weak_coverage']}")
    lines.append(f"    High priority:    {s['high_priority_gaps']}")
    lines.append("")

    lines.append(f"  {'Ability':<28} {'Coverage':<10} {'Priority':<10} Gap Description")
    lines.append(f"  {'─' * 90}")
    for key, data in audit["beam_gap_abilities"].items():
        desc = data["gap_description"][:60] + "..." if len(data["gap_description"]) > 60 else data["gap_description"]
        lines.append(
            f"  {data['label']:<28} {data['coverage']:<10} {data['importance']:<10} {desc}"
        )

    lines.append("")
    lines.append(f"  {audit['recommendation']}")
    lines.append("")
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    import sys
    args = sys.argv[1:]

    if "--audit" in args or "audit" in args:
        audit = generate_ability_gap_audit()
        if "--json" in args:
            print(json.dumps(audit, indent=2))
        else:
            print(format_gap_audit(audit))
        return

    ability = None
    oracle = "--oracle" in args
    json_output = "--json" in args

    for a in args:
        if a.startswith("--ability"):
            continue
        if a.upper() in ABILITIES:
            ability = a.upper()
        elif a == "--ability" and args.index(a) + 1 < len(args):
            ability = args[args.index(a) + 1].upper()

    report = run_beam(ability=ability, oracle=oracle)
    save_report(report)

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))


if __name__ == "__main__":
    main()
