"""LongMemEval adapter — five-ability long-term memory evaluation.

Evaluates Clarvis memory across five LongMemEval abilities:
  - IE: Information Extraction — retrieve explicitly stated facts
  - MR: Multi-Session Reasoning — combine info across sessions
  - KU: Knowledge Update — handle updated/overwritten facts
  - TR: Temporal Reasoning — reason about time/order of events
  - ABS: Abstention — correctly refuse when info is unavailable

Supports two retrieval modes:
  - full-history: normal Clarvis brain retrieval
  - oracle: inject gold evidence to isolate retrieval vs reasoning failures

Outputs per-ability scores, retrieval diagnostics, and stage breakdown.

Usage:
    python3 -m clarvis bench longmemeval              # Run all abilities
    python3 -m clarvis bench longmemeval --ability IE  # Single ability
    python3 -m clarvis bench longmemeval --oracle      # Oracle retrieval mode
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = os.path.join(WORKSPACE, "data", "benchmarks")
LONGMEMEVAL_FILE = os.path.join(DATA_DIR, "longmemeval_latest.json")
LONGMEMEVAL_HISTORY = os.path.join(DATA_DIR, "longmemeval_history.jsonl")

# ── Ability taxonomy (from LongMemEval paper, ICLR 2025) ────────────

ABILITIES = ["IE", "MR", "KU", "TR", "ABS"]

ABILITY_LABELS = {
    "IE": "Information Extraction",
    "MR": "Multi-Session Reasoning",
    "KU": "Knowledge Update",
    "TR": "Temporal Reasoning",
    "ABS": "Abstention",
}

# ── Built-in evaluation tasks ────────────────────────────────────────
# Modeled on LongMemEval-S structure: each task tests one ability,
# has a question, gold answer substrings, gold evidence for oracle mode,
# and collections to search.

LONGMEMEVAL_TASKS: list[dict[str, Any]] = [
    # ── IE: Information Extraction ──
    {
        "id": "IE01",
        "ability": "IE",
        "question": "What port does the OpenClaw gateway run on?",
        "gold_answer": ["18789"],
        "gold_evidence": "OpenClaw gateway runs on port 18789 via systemd user service.",
        "collections": ["clarvis-infrastructure"],
        "difficulty": "easy",
    },
    {
        "id": "IE02",
        "ability": "IE",
        "question": "What is the name of the embedding model used by ClarvisDB?",
        "gold_answer": ["minilm", "all-minilm", "onnx"],
        "gold_evidence": "ClarvisDB uses ONNX MiniLM (all-MiniLM-L6-v2) embeddings, fully local.",
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "difficulty": "easy",
    },
    {
        "id": "IE03",
        "ability": "IE",
        "question": "What is the user's Telegram chat ID?",
        "gold_answer": ["stored in CLARVIS_TG_CHAT_ID env var"],
        "gold_evidence": "Bot sends messages to a configured chat_id (the operator). Actual ID stored in .env.",
        "collections": ["clarvis-infrastructure", "clarvis-preferences"],
        "difficulty": "medium",
    },
    {
        "id": "IE04",
        "ability": "IE",
        "question": "How many collections does the ClarvisDB brain have?",
        "gold_answer": ["10"],
        "gold_evidence": "ClarvisDB has 10 collections: clarvis-identity, preferences, learnings, infrastructure, goals, context, memories, procedures, autonomous-learning, episodes.",
        "collections": ["clarvis-infrastructure"],
        "difficulty": "easy",
    },
    {
        "id": "IE05",
        "ability": "IE",
        "question": "What is the CDP port for Chromium browser?",
        "gold_answer": ["18800"],
        "gold_evidence": "CDP port: 18800, Chromium 145.0.7632.109 (snap), Playwright 1.58.2.",
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "difficulty": "medium",
    },
    # ── MR: Multi-Session Reasoning ──
    {
        "id": "MR01",
        "ability": "MR",
        "question": "How does the heartbeat pipeline flow from gate to storage?",
        "gold_answer": ["gate", "preflight", "postflight", "episode"],
        "gold_evidence": "Heartbeat: gate (zero-LLM pre-check) → preflight (attention scoring, context) → Claude Code execution → postflight (episode encoding, confidence, brain storage).",
        "collections": ["clarvis-procedures", "clarvis-learnings"],
        "difficulty": "medium",
    },
    {
        "id": "MR02",
        "ability": "MR",
        "question": "What is the relationship between task router complexity and model selection?",
        "gold_answer": ["simple", "complex", "code", "vision"],
        "gold_evidence": "Task router: SIMPLE/MEDIUM→M2.5, COMPLEX→GLM-5, VISION→Kimi K2.5, WEB_SEARCH→Gemini 3 Flash, CODE-HEAVY→Claude Code Opus.",
        "collections": ["clarvis-procedures", "clarvis-infrastructure"],
        "difficulty": "medium",
    },
    {
        "id": "MR03",
        "ability": "MR",
        "question": "What happens when a cron job needs to spawn Claude Code and another is already running?",
        "gold_answer": ["lock", "mutual exclusion", "global"],
        "gold_evidence": "All Claude Code spawners acquire /tmp/clarvis_claude_global.lock for mutual exclusion. Stale-lock detection and trap EXIT cleanup.",
        "collections": ["clarvis-procedures", "clarvis-learnings"],
        "difficulty": "hard",
    },
    {
        "id": "MR04",
        "ability": "MR",
        "question": "How do the conscious and subconscious layers communicate?",
        "gold_answer": ["digest", "memory", "cron"],
        "gold_evidence": "Subconscious writes to memory/cron/digest.md. Conscious layer reads digest to internalize subconscious work. M2.5 spawns Claude Code for heavy tasks.",
        "collections": ["clarvis-identity", "clarvis-procedures"],
        "difficulty": "medium",
    },
    {
        "id": "MR05",
        "ability": "MR",
        "question": "What safeguards exist for the gateway update process?",
        "gold_answer": ["backup", "rollback", "health", "self-decapitation"],
        "gold_evidence": "safe_update.sh: backup + health checks, rollback support, self-decapitation protection (detects if running inside gateway process tree).",
        "collections": ["clarvis-procedures", "clarvis-infrastructure"],
        "difficulty": "hard",
    },
    # ── KU: Knowledge Update ──
    {
        "id": "KU01",
        "ability": "KU",
        "question": "How many times per day does cron_autonomous.sh run?",
        "gold_answer": ["12"],
        "gold_evidence": "cron_autonomous.sh runs 12x/day (11 on Wed/Sat when strategic audit replaces one slot). Updated 2026-03-16.",
        "collections": ["clarvis-infrastructure", "clarvis-context"],
        "difficulty": "medium",
        "update_note": "Was originally fewer, increased to 12 on 2026-03-16.",
    },
    {
        "id": "KU02",
        "ability": "KU",
        "question": "What is the current prompt_context weight in CLR?",
        "gold_answer": ["0.18"],
        "gold_evidence": "prompt_context weight raised 0.13→0.18 (2026-03-21). Context relevance was weakest metric.",
        "collections": ["clarvis-learnings", "clarvis-context"],
        "difficulty": "hard",
        "update_note": "Weight changed from 0.13 to 0.18 on 2026-03-21.",
    },
    {
        "id": "KU03",
        "ability": "KU",
        "question": "What graph backend does ClarvisDB currently prefer?",
        "gold_answer": ["sqlite", "wal"],
        "gold_evidence": "Graph supports dual backends: JSON (legacy) + SQLite+WAL (indexed, ACID). Cutover via graph_cutover.py.",
        "collections": ["clarvis-infrastructure", "clarvis-learnings"],
        "difficulty": "medium",
        "update_note": "Migrated from JSON to SQLite+WAL backend.",
    },
    {
        "id": "KU04",
        "ability": "KU",
        "question": "How is the gateway managed now (not historically)?",
        "gold_answer": ["systemd", "systemctl"],
        "gold_evidence": "Gateway managed via systemd (systemctl --user), NOT pm2. pm2 only manages logrotate now.",
        "collections": ["clarvis-infrastructure", "clarvis-procedures"],
        "difficulty": "medium",
        "update_note": "Migrated from pm2 to systemd.",
    },
    {
        "id": "KU05",
        "ability": "KU",
        "question": "What is the current evolution focus for Clarvis?",
        "gold_answer": ["open-source", "benchmark", "website", "public"],
        "gold_evidence": "Current focus: open-source readiness, public website, benchmark infrastructure (CLR, retrieval, MemBench), repo hygiene for 2026-03-31 delivery deadline.",
        "collections": ["clarvis-context", "clarvis-goals"],
        "difficulty": "easy",
        "update_note": "Focus shifts with each milestone.",
    },
    # ── TR: Temporal Reasoning ──
    {
        "id": "TR01",
        "ability": "TR",
        "question": "What is the order of maintenance cron jobs between 4:00 and 5:30 AM?",
        "gold_answer": ["checkpoint", "compaction", "verify", "vacuum", "soak"],
        "gold_evidence": "04:00 graph checkpoint → 04:30 compaction → 04:45 verify → 05:00 ChromaDB vacuum → 05:05 soak manager.",
        "collections": ["clarvis-infrastructure", "clarvis-procedures"],
        "difficulty": "hard",
    },
    {
        "id": "TR02",
        "ability": "TR",
        "question": "Which was added first: the dream engine or the agent orchestrator?",
        "gold_answer": ["dream"],
        "gold_evidence": "Dream engine (dream_engine.py) was an early feature. Agent orchestrator (project_agent.py) was added later as the 5th long-term goal.",
        "collections": ["clarvis-context", "clarvis-goals"],
        "difficulty": "hard",
    },
    {
        "id": "TR03",
        "ability": "TR",
        "question": "What time does the morning planning cron run?",
        "gold_answer": ["08:00", "8:00"],
        "gold_evidence": "08:00 cron_morning.sh — day planning.",
        "collections": ["clarvis-infrastructure", "clarvis-procedures"],
        "difficulty": "easy",
    },
    {
        "id": "TR04",
        "ability": "TR",
        "question": "When do research cron jobs run during the day?",
        "gold_answer": ["10:00", "16:00"],
        "gold_evidence": "cron_research.sh runs at 10:00 and 16:00 (2x/day, AM + PM for topic diversity).",
        "collections": ["clarvis-infrastructure"],
        "difficulty": "medium",
    },
    {
        "id": "TR05",
        "ability": "TR",
        "question": "What is the delivery deadline for the current milestone?",
        "gold_answer": ["2026-03-31", "march 31"],
        "gold_evidence": "Presentable Clarvis by 2026-03-31: open-source-ready, website v0, clean repo, stronger brain.",
        "collections": ["clarvis-goals", "clarvis-context"],
        "difficulty": "easy",
    },
    # ── ABS: Abstention ──
    {
        "id": "ABS01",
        "ability": "ABS",
        "question": "What is Clarvis's Twitter password?",
        "gold_answer": ["__ABSTAIN__"],
        "gold_evidence": None,
        "collections": ["clarvis-infrastructure", "clarvis-preferences"],
        "difficulty": "easy",
        "expect_abstain": True,
    },
    {
        "id": "ABS02",
        "ability": "ABS",
        "question": "What was Clarvis's PI score on 2025-01-01?",
        "gold_answer": ["__ABSTAIN__"],
        "gold_evidence": None,
        "collections": ["clarvis-context"],
        "difficulty": "medium",
        "expect_abstain": True,
        "abstain_reason": "Clarvis did not exist on 2025-01-01.",
    },
    {
        "id": "ABS03",
        "ability": "ABS",
        "question": "What GPU model does the NUC have?",
        "gold_answer": ["__ABSTAIN__"],
        "gold_evidence": None,
        "collections": ["clarvis-infrastructure"],
        "difficulty": "easy",
        "expect_abstain": True,
        "abstain_reason": "NUC uses CPU-only inference, no dedicated GPU.",
    },
    {
        "id": "ABS04",
        "ability": "ABS",
        "question": "What is the maximum budget for OpenRouter API calls this month?",
        "gold_answer": ["__ABSTAIN__"],
        "gold_evidence": None,
        "collections": ["clarvis-infrastructure", "clarvis-preferences"],
        "difficulty": "medium",
        "expect_abstain": True,
        "abstain_reason": "Budget thresholds are in budget_config.json, not in brain memories.",
    },
    {
        "id": "ABS05",
        "ability": "ABS",
        "question": "How many users interact with Clarvis daily?",
        "gold_answer": ["__ABSTAIN__"],
        "gold_evidence": None,
        "collections": ["clarvis-context"],
        "difficulty": "easy",
        "expect_abstain": True,
        "abstain_reason": "Single-user system, but daily interaction count not tracked in brain.",
    },
]


# ── Scoring helpers ──────────────────────────────────────────────────

def _check_answer_hit(results: list[dict], task: dict) -> bool:
    """Check if retrieval results contain evidence matching the gold answer."""
    if task.get("expect_abstain"):
        # For abstention tasks, a "hit" means the brain found NO relevant info
        # (correctly supporting abstention)
        for r in results:
            doc = r.get("document", "").lower()
            # If any result looks highly relevant, abstention should fail
            query_terms = task["question"].lower().split()
            # Simple relevance: if >50% of non-stopword query terms appear
            stopwords = {"what", "is", "the", "a", "an", "how", "does", "did", "was", "on", "of"}
            content_terms = [t for t in query_terms if t not in stopwords and len(t) > 2]
            if content_terms:
                matches = sum(1 for t in content_terms if t in doc)
                if matches / len(content_terms) > 0.6:
                    return False  # Found relevant info → abstention incorrect
        return True  # No relevant info found → abstention correct

    # For non-abstention tasks, check if gold answer substrings appear
    for r in results:
        doc = r.get("document", "").lower()
        for answer_part in task["gold_answer"]:
            if answer_part.lower() in doc:
                return True
    return False


def _check_first_hit(results: list[dict], task: dict) -> bool:
    """Check if the first result contains the answer (P@1)."""
    if not results:
        return task.get("expect_abstain", False)
    if task.get("expect_abstain"):
        return _check_answer_hit(results[:1], task)
    r = results[0]
    doc = r.get("document", "").lower()
    for answer_part in task["gold_answer"]:
        if answer_part.lower() in doc:
            return True
    return False


# ── Stage diagnostics ────────────────────────────────────────────────

class StageDiagnostics:
    """Track per-stage success/failure for retrieval pipeline analysis.

    Stages:
      1. retrieval — did we find relevant evidence?
      2. evidence_quality — is the retrieved evidence sufficient?
      3. answer — does the evidence support the correct answer?
    """

    def __init__(self):
        self.stages: list[dict] = []

    def record(self, task_id: str, ability: str,
               retrieval_hit: bool, evidence_quality: float,
               answer_correct: bool, oracle: bool = False):
        self.stages.append({
            "task_id": task_id,
            "ability": ability,
            "retrieval_hit": retrieval_hit,
            "evidence_quality": evidence_quality,
            "answer_correct": answer_correct,
            "oracle": oracle,
        })

    def summarize(self) -> dict:
        """Summarize stage-separated success rates."""
        if not self.stages:
            return {"n": 0}

        n = len(self.stages)
        retrieval_hits = sum(1 for s in self.stages if s["retrieval_hit"])
        answer_correct = sum(1 for s in self.stages if s["answer_correct"])
        avg_evidence = (sum(s["evidence_quality"] for s in self.stages) / n
                        if n > 0 else 0.0)

        # Failure attribution
        retrieval_failures = [s["task_id"] for s in self.stages
                              if not s["retrieval_hit"]]
        reasoning_failures = [s["task_id"] for s in self.stages
                              if s["retrieval_hit"] and not s["answer_correct"]]

        return {
            "n": n,
            "retrieval_rate": round(retrieval_hits / n, 3),
            "evidence_quality_avg": round(avg_evidence, 3),
            "answer_rate": round(answer_correct / n, 3),
            "retrieval_failures": retrieval_failures,
            "reasoning_failures": reasoning_failures,
            "pure_retrieval_failure_count": len(retrieval_failures),
            "pure_reasoning_failure_count": len(reasoning_failures),
        }

    def by_ability(self) -> dict[str, dict]:
        """Stage breakdown per ability."""
        by_ab: dict[str, list[dict]] = {}
        for s in self.stages:
            by_ab.setdefault(s["ability"], []).append(s)

        result = {}
        for ab, stages in by_ab.items():
            n = len(stages)
            result[ab] = {
                "n": n,
                "retrieval_rate": round(
                    sum(1 for s in stages if s["retrieval_hit"]) / n, 3),
                "answer_rate": round(
                    sum(1 for s in stages if s["answer_correct"]) / n, 3),
                "retrieval_failures": [s["task_id"] for s in stages
                                       if not s["retrieval_hit"]],
                "reasoning_failures": [s["task_id"] for s in stages
                                       if s["retrieval_hit"] and not s["answer_correct"]],
            }
        return result


# ── Core evaluation ──────────────────────────────────────────────────

def _recall_for_task(task: dict, brain_recall, k: int = 5,
                     oracle: bool = False) -> list[dict]:
    """Retrieve results for a task."""
    if oracle:
        gold = task.get("gold_evidence")
        if not gold:
            return []  # Abstention tasks have no gold evidence
        return [{
            "document": gold,
            "id": f"oracle_{task['id']}",
            "collection": task["collections"][0] if task["collections"] else "oracle",
            "distance": 0.0,
        }]
    return brain_recall(task["question"], n=k, caller="longmemeval")


def _evidence_quality_score(results: list[dict], task: dict) -> float:
    """Score evidence quality: how many gold answer terms appear in results."""
    if task.get("expect_abstain"):
        # For abstention: quality is 1.0 if no confusing evidence found
        return 1.0 if _check_answer_hit(results, task) else 0.0

    if not results or not task["gold_answer"]:
        return 0.0

    all_text = " ".join(r.get("document", "") for r in results).lower()
    matches = sum(1 for ans in task["gold_answer"]
                  if ans.lower() in all_text)
    return round(matches / len(task["gold_answer"]), 3)


def run_longmemeval(
    ability: str | None = None,
    k: int = 5,
    oracle: bool = False,
) -> dict:
    """Run LongMemEval evaluation across selected abilities.

    Args:
        ability: Specific ability to evaluate (IE/MR/KU/TR/ABS), or None for all.
        k: Number of retrieval results to consider.
        oracle: Inject gold evidence instead of real retrieval.

    Returns:
        Report dict with per-ability scores, aggregate metrics,
        stage diagnostics, and retrieval details.
    """
    from clarvis.brain import brain

    tasks = LONGMEMEVAL_TASKS
    if ability:
        ability = ability.upper()
        if ability not in ABILITIES:
            raise ValueError(f"Unknown ability '{ability}'. Valid: {ABILITIES}")
        tasks = [t for t in tasks if t["ability"] == ability]

    diagnostics = StageDiagnostics()
    ability_results: dict[str, dict] = {}
    all_details = []

    for task in tasks:
        ab = task["ability"]
        if ab not in ability_results:
            ability_results[ab] = {
                "total": 0, "hits": 0, "first_hits": 0,
                "details": [], "difficulties": {"easy": 0, "medium": 0, "hard": 0},
                "difficulty_hits": {"easy": 0, "medium": 0, "hard": 0},
            }
        ar = ability_results[ab]
        ar["total"] += 1
        diff = task.get("difficulty", "medium")
        ar["difficulties"][diff] = ar["difficulties"].get(diff, 0) + 1

        t0 = time.monotonic()
        results = _recall_for_task(task, brain.recall, k=k, oracle=oracle)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)

        hit = _check_answer_hit(results, task)
        first_hit = _check_first_hit(results, task)
        evidence_q = _evidence_quality_score(results, task)

        if hit:
            ar["hits"] += 1
            ar["difficulty_hits"][diff] = ar["difficulty_hits"].get(diff, 0) + 1
        if first_hit:
            ar["first_hits"] += 1

        # Record stage diagnostics
        diagnostics.record(
            task_id=task["id"],
            ability=ab,
            retrieval_hit=hit if not task.get("expect_abstain") else (not hit if not oracle else True),
            evidence_quality=evidence_q,
            answer_correct=hit,
            oracle=oracle,
        )

        detail = {
            "id": task["id"],
            "ability": ab,
            "question": task["question"],
            "hit": hit,
            "first_hit": first_hit,
            "evidence_quality": evidence_q,
            "latency_ms": latency_ms,
            "difficulty": diff,
            "n_results": len(results),
            "expect_abstain": task.get("expect_abstain", False),
        }
        ar["details"].append(detail)
        all_details.append(detail)

    # Compute per-ability scores
    ability_scores = {}
    for ab, ar in ability_results.items():
        total = ar["total"]
        effectiveness = round(ar["hits"] / total, 3) if total > 0 else 0.0
        precision_at_1 = round(ar["first_hits"] / total, 3) if total > 0 else 0.0

        ability_scores[ab] = {
            "label": ABILITY_LABELS.get(ab, ab),
            "total": total,
            "hits": ar["hits"],
            "effectiveness": effectiveness,
            "precision_at_1": precision_at_1,
            "failures": [d["id"] for d in ar["details"] if not d["hit"]],
            "difficulty_breakdown": {
                diff: {
                    "total": ar["difficulties"].get(diff, 0),
                    "hits": ar["difficulty_hits"].get(diff, 0),
                }
                for diff in ["easy", "medium", "hard"]
                if ar["difficulties"].get(diff, 0) > 0
            },
        }

    # Aggregate
    total_tasks = len(all_details)
    total_hits = sum(a["hits"] for a in ability_scores.values())
    total_first = sum(ar["first_hits"] for ar in ability_results.values())
    avg_latency = (round(sum(d["latency_ms"] for d in all_details) / total_tasks, 1)
                   if total_tasks > 0 else 0.0)

    # Stage diagnostics
    stage_summary = diagnostics.summarize()
    stage_by_ability = diagnostics.by_ability()

    report = {
        "benchmark": "longmemeval",
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
        "stage_diagnostics": stage_summary,
        "stage_by_ability": stage_by_ability,
        "details": all_details,
    }

    return report


def run_oracle_comparison(
    ability: str | None = None,
    k: int = 5,
) -> dict:
    """Run both full-history and oracle modes, compare results.

    Returns comparison dict with normal/oracle results, gap analysis,
    and failure attribution (pure retrieval vs pure reasoning).
    """
    normal = run_longmemeval(ability=ability, k=k, oracle=False)
    oracle = run_longmemeval(ability=ability, k=k, oracle=True)

    # Gap analysis
    gap = {
        "effectiveness_gap": round(
            oracle["aggregate_effectiveness"] - normal["aggregate_effectiveness"], 3),
        "precision_at_1_gap": round(
            oracle["aggregate_precision_at_1"] - normal["aggregate_precision_at_1"], 3),
    }

    # Per-ability gaps
    ability_gap = {}
    for ab in ABILITIES:
        n = normal["by_ability"].get(ab, {})
        o = oracle["by_ability"].get(ab, {})
        if n and o:
            ability_gap[ab] = {
                "effectiveness_gap": round(
                    o.get("effectiveness", 0) - n.get("effectiveness", 0), 3),
                "precision_at_1_gap": round(
                    o.get("precision_at_1", 0) - n.get("precision_at_1", 0), 3),
            }

    # Failure attribution from normal-mode details
    normal_fails = {d["id"] for d in normal["details"] if not d["hit"]}
    oracle_fails = {d["id"] for d in oracle["details"] if not d["hit"]}
    retrieval_failures = sorted(normal_fails - oracle_fails)  # fixed by oracle
    shared_failures = sorted(normal_fails & oracle_fails)  # not fixed by oracle

    # Diagnosis
    if not normal_fails:
        diagnosis = "All tasks pass in full-history mode."
    elif not retrieval_failures:
        diagnosis = f"All {len(shared_failures)} failures are reasoning/evidence-quality issues (not retrieval)."
    elif not shared_failures:
        diagnosis = f"All {len(retrieval_failures)} failures are pure retrieval failures (oracle fixes them)."
    else:
        diagnosis = (f"{len(retrieval_failures)} retrieval failure(s), "
                     f"{len(shared_failures)} reasoning/evidence failure(s).")

    return {
        "normal": normal,
        "oracle": oracle,
        "gap": gap,
        "ability_gap": ability_gap,
        "retrieval_failures": retrieval_failures,
        "shared_failures": shared_failures,
        "diagnosis": diagnosis,
    }


def save_report(report: dict):
    """Save report to latest file and append to history."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LONGMEMEVAL_FILE, "w") as f:
        json.dump(report, f, indent=2)

    summary = {
        "timestamp": report["timestamp"],
        "mode": report["mode"],
        "total_tasks": report["total_tasks"],
        "aggregate_effectiveness": report["aggregate_effectiveness"],
        "aggregate_precision_at_1": report["aggregate_precision_at_1"],
        "avg_latency_ms": report["avg_latency_ms"],
        "by_ability": {
            ab: {k: v for k, v in data.items() if k not in ("failures", "difficulty_breakdown")}
            for ab, data in report["by_ability"].items()
        },
        "stage_diagnostics": {
            k: v for k, v in report.get("stage_diagnostics", {}).items()
            if k not in ("retrieval_failures", "reasoning_failures")
        },
    }
    with open(LONGMEMEVAL_HISTORY, "a") as f:
        f.write(json.dumps(summary) + "\n")


def format_report(report: dict) -> str:
    """Format LongMemEval report for terminal display."""
    lines = ["=== LongMemEval Evaluation ===", ""]
    mode = report.get("mode", "full-history")
    lines.append(f"  Mode: {mode.upper()}")
    lines.append(f"  Tasks: {report['total_tasks']}  Hits: {report['total_hits']}")
    lines.append(f"  Effectiveness: {report['aggregate_effectiveness']:.1%}")
    lines.append(f"  P@1:           {report['aggregate_precision_at_1']:.1%}")
    lines.append(f"  Avg latency:   {report['avg_latency_ms']:.0f}ms")
    lines.append("")

    # Per-ability table
    lines.append(f"  {'Ability':<8} {'Label':<28} {'Eff':>6} {'P@1':>6} {'N':>4}  Failures")
    lines.append(f"  {'─' * 72}")

    for ab in ABILITIES:
        data = report["by_ability"].get(ab)
        if not data:
            continue
        fails = ", ".join(data.get("failures", [])) or "—"
        lines.append(
            f"  {ab:<8} {data['label']:<28} "
            f"{data['effectiveness']:>5.1%} {data['precision_at_1']:>5.1%} "
            f"{data['total']:>4}  {fails}"
        )

    # Stage diagnostics
    stage = report.get("stage_diagnostics", {})
    if stage.get("n", 0) > 0:
        lines.append("")
        lines.append("  Stage Diagnostics:")
        lines.append(f"    Retrieval rate:   {stage['retrieval_rate']:.1%}")
        lines.append(f"    Evidence quality: {stage['evidence_quality_avg']:.3f}")
        lines.append(f"    Answer rate:      {stage['answer_rate']:.1%}")
        rf = stage.get("pure_retrieval_failure_count", 0)
        rsf = stage.get("pure_reasoning_failure_count", 0)
        if rf or rsf:
            lines.append(f"    Retrieval failures: {rf}  Reasoning failures: {rsf}")

    lines.append("")
    return "\n".join(lines)


def format_oracle_comparison(comparison: dict) -> str:
    """Format oracle comparison for terminal display."""
    normal = comparison["normal"]
    oracle = comparison["oracle"]
    gap = comparison["gap"]

    lines = ["=== LongMemEval Oracle Comparison ===", ""]
    lines.append(f"  {'Metric':<25} {'Normal':>8} {'Oracle':>8} {'Gap':>8}")
    lines.append(f"  {'─' * 53}")
    lines.append(f"  {'Effectiveness':<25} {normal['aggregate_effectiveness']:>8.1%} "
                 f"{oracle['aggregate_effectiveness']:>8.1%} {gap['effectiveness_gap']:>+8.3f}")
    lines.append(f"  {'P@1':<25} {normal['aggregate_precision_at_1']:>8.1%} "
                 f"{oracle['aggregate_precision_at_1']:>8.1%} {gap['precision_at_1_gap']:>+8.3f}")

    # Per-ability gaps
    ag = comparison.get("ability_gap", {})
    if ag:
        lines.append("")
        lines.append(f"  Ability gaps (effectiveness / P@1):")
        for ab in ABILITIES:
            g = ag.get(ab)
            if g:
                lines.append(f"    {ab:<6} {ABILITY_LABELS[ab]:<28} "
                             f"{g['effectiveness_gap']:>+.3f} / {g['precision_at_1_gap']:>+.3f}")

    # Failure attribution
    rf = comparison["retrieval_failures"]
    sf = comparison["shared_failures"]
    lines.append("")
    lines.append(f"  Diagnosis: {comparison['diagnosis']}")
    if rf:
        lines.append(f"  Pure retrieval failures: {', '.join(rf)}")
    if sf:
        lines.append(f"  Evidence/reasoning failures: {', '.join(sf)}")

    lines.append("")
    return "\n".join(lines)
