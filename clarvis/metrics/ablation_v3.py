"""
CLR Outcome Ablation Harness v3 — LLM-judged blind comparison.

Unlike v2 which measures proxy metrics (section presence, char volume),
v3 generates context briefs WITH and WITHOUT each module, then has an LLM
blindly judge which brief would produce better task outcomes.

Key improvements over v2:
  - Judges actual outcome quality, not assembly proxies
  - 24 diverse test tasks across 6 categories (code, debug, research, maintenance, design, analysis)
  - Blind A/B comparison (randomized order, no module names revealed)
  - Per-category delta heatmap shows non-uniform module contributions
  - Cost-controlled: uses cheap model (Gemini Flash) for judging

Usage:
    python3 -m clarvis.metrics.ablation_v3                    # full sweep
    python3 -m clarvis.metrics.ablation_v3 --module episodic_recall
    python3 -m clarvis.metrics.ablation_v3 --dry-run          # show tasks, no LLM calls
    python3 -m clarvis.metrics.ablation_v3 --report           # show latest results
    python3 -m clarvis.metrics.ablation_v3 --offline          # deterministic scoring, no LLM
"""

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
RESULTS_FILE = os.path.join(WORKSPACE, "data/ablation_v3_results.json")
HISTORY_FILE = os.path.join(WORKSPACE, "data/ablation_v3_history.jsonl")
MAX_HISTORY = 100

# LLM judge config — cheap model for cost control
JUDGE_MODEL = os.environ.get(
    "CLARVIS_ABLATION_JUDGE_MODEL",
    "google/gemini-2.5-flash-preview",
)
JUDGE_TIMEOUT = 30  # seconds per judge call

ABLATABLE_MODULES = [
    "episodic_recall",
    "graph_expansion",
    "related_tasks",
    "decision_context",
    "reasoning_scaffold",
    "working_memory",
]

# ── 24 diverse test tasks across 6 categories ──────────────────────────

TASK_CATEGORIES = {
    "code_implementation": [
        "Add a retry decorator with exponential backoff to the brain search function, "
        "handling transient ChromaDB connection errors without masking permanent failures",
        "Implement a simple LRU cache for episodic memory recall that evicts entries "
        "older than 30 minutes and caps at 50 entries",
        "Write a Python function that merges two JSONL files by timestamp, deduplicating "
        "entries with matching chain_id fields",
        "Create a context manager that acquires a file lock with timeout and stale-lock "
        "detection, compatible with the existing /tmp/clarvis_*.lock pattern",
    ],
    "debugging": [
        "The heartbeat postflight silently drops episodes when reasoning_chain_id is None "
        "— diagnose the root cause and fix the episode encoding path",
        "Brain search returns duplicate results when the same memory exists in both "
        "clarvis-learnings and autonomous-learning collections — find and fix the dedup gap",
        "The cron_watchdog reports false positives for cron_autonomous.sh when the task "
        "runs longer than 20 minutes — identify the timeout logic flaw and correct it",
        "Context assembly produces empty briefs for tasks containing Unicode emoji in the "
        "task title — trace the encoding path and fix the failure point",
    ],
    "research_analysis": [
        "Analyze the trade-offs between Hebbian decay rates (0.01 vs 0.05 vs 0.10) for "
        "the access_log consolidation and recommend optimal parameters with justification",
        "Compare retrieval-augmented generation approaches for long-term memory: naive RAG "
        "vs CRAG (corrective RAG) vs iterative retrieval — which fits Clarvis best?",
        "Research how production agent systems handle context window exhaustion: summarize "
        "3 approaches (truncation, compression, hierarchical) with pros/cons for our case",
        "Evaluate whether graph-based memory expansion provides measurable retrieval quality "
        "improvement over flat vector search for procedural knowledge recall",
    ],
    "maintenance_ops": [
        "Rotate all JSONL files in data/ larger than 5MB: compress old entries to .gz, "
        "keep last 200 lines in the active file, verify no data loss",
        "Audit the 20+ cron jobs for overlapping lock files and execution windows — "
        "identify any race conditions and propose a fix",
        "Clean up orphaned ChromaDB collection directories in data/clarvisdb/ that have "
        "no corresponding collection registration, reclaiming disk space",
        "Update the backup_daily.sh script to include the new trajectory_eval/ directory "
        "and verify the incremental backup correctly handles JSONL append-only files",
    ],
    "architecture_design": [
        "Design a plugin interface for cognitive modules so new modules can be added "
        "without modifying heartbeat_preflight.py — define the protocol and registration",
        "Propose a migration path from the current monolithic preflight to a pipeline "
        "architecture where each cognitive stage is an independent process with IPC",
        "Design a cost-aware task routing policy that dynamically selects between Claude "
        "Code and OpenRouter models based on task complexity AND remaining daily budget",
        "Architect a session transcript system that captures full tool-use sequences for "
        "later replay and learning, with privacy controls and storage rotation",
    ],
    "metric_evaluation": [
        "Compute the information-theoretic redundancy between episodic_recall and "
        "graph_expansion outputs for the last 50 tasks — are they providing unique signal?",
        "Measure how context brief quality degrades as cognitive load increases from "
        "0.2 to 0.8 — plot the expected quality curve and identify the inflection point",
        "Evaluate whether the working_memory module improves task success rate for "
        "multi-step implementation tasks vs single-file changes",
        "Assess the precision/recall trade-off of the current attention salience scoring "
        "against a simple recency-only baseline for task prioritization",
    ],
}

# Flatten for iteration
ALL_TASKS = []
for category, tasks in TASK_CATEGORIES.items():
    for task in tasks:
        ALL_TASKS.append({"task": task, "category": category})


# ── Assembly with ablation ──────────────────────────────────────────────

def _apply_ablation(disabled_modules: list[str], assembly) -> tuple:
    """Apply ablation patches, return (original_budgets, original_suppress) for restore."""
    original_budgets = deepcopy(assembly.TIER_BUDGETS)
    original_hard_suppress = set(assembly.HARD_SUPPRESS)

    budget_key_map = {
        "episodic_recall": "episodes",
        "graph_expansion": None,
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

    return original_budgets, original_hard_suppress


def _restore_assembly(assembly, original_budgets, original_hard_suppress):
    """Restore assembly state after ablation."""
    assembly.TIER_BUDGETS = original_budgets
    assembly.HARD_SUPPRESS = frozenset(original_hard_suppress)


def _generate_brief(task_text: str, disabled_modules: list[str]) -> str:
    """Generate a context brief with specific modules disabled.

    Uses two ablation strategies:
    1. Budget zeroing + HARD_SUPPRESS (affects assembly generation)
    2. Post-hoc section stripping (catches sections not budget-gated)

    Strategy 2 is necessary because many assembly sections are generated
    regardless of budget settings. This ensures reliable ablation.
    """
    import clarvis.context.assembly as assembly

    original_budgets, original_suppress = _apply_ablation(disabled_modules, assembly)
    try:
        brief = assembly.generate_tiered_brief(task_text, tier="standard")
        # Post-hoc stripping for sections that aren't budget-gated
        if disabled_modules:
            brief = _strip_sections(brief, disabled_modules)
        return brief
    except Exception as e:
        return f"[ASSEMBLY ERROR: {e}]"
    finally:
        _restore_assembly(assembly, original_budgets, original_suppress)


# Section markers belonging to each module. Lines matching these headers
# (and following content until next header) are stripped during ablation.
_MODULE_SECTION_HEADERS = {
    "episodic_recall": ["EPISODIC", "EPISODE", "PAST TASK", "LESSON"],
    "graph_expansion": ["BRAIN CONTEXT", "KNOWLEDGE SYNTHESIS", "KNOWLEDGE"],
    "related_tasks": ["RELATED TASKS", "RECENT"],
    "decision_context": [
        "SUCCESS CRITERIA", "AVOID THESE FAILURE PATTERNS",
        "KEY TERMS", "CONSTRAINT", "OBLIGATION",
    ],
    "reasoning_scaffold": ["APPROACH", "REASONING", "STRATEGY", "CODE GENERATION TEMPLATES"],
    "working_memory": ["WORKING MEMORY", "GWT BROADCAST", "SPOTLIGHT"],
}


def _strip_sections(brief: str, disabled_modules: list[str]) -> str:
    """Remove sections belonging to disabled modules from the brief.

    Identifies section headers and strips them plus their content (until
    the next section header or separator '---').
    """
    # Collect all headers to strip
    strip_prefixes = []
    for module in disabled_modules:
        for header in _MODULE_SECTION_HEADERS.get(module, []):
            strip_prefixes.append(header.upper())

    if not strip_prefixes:
        return brief

    lines = brief.splitlines()
    result = []
    skipping = False

    for line in lines:
        stripped = line.strip().upper()

        # Check if this line is a section header we want to skip
        is_target_header = any(
            stripped.startswith(prefix) for prefix in strip_prefixes
        )

        if is_target_header:
            skipping = True
            continue

        # Check if this line starts a new section (end of skipped section)
        if skipping:
            # New section header or separator ends the skip
            is_new_section = (
                stripped == "---"
                or (stripped.endswith(":") and stripped == stripped.upper() and len(stripped) > 3)
                or stripped.startswith("CURRENT TASK")
            )
            if is_new_section:
                skipping = False
                # Include the separator if it's "---"
                if stripped != "---":
                    result.append(line)
            # else: still in skipped section, drop this line
            continue

        result.append(line)

    # Clean up consecutive separators
    cleaned = []
    for line in result:
        if line.strip() == "---" and cleaned and cleaned[-1].strip() == "---":
            continue
        cleaned.append(line)

    return "\n".join(cleaned)


# ── LLM Judge ──────────────────────────────────────────────────────────

JUDGE_PROMPT = """\
You are an expert evaluator judging context briefs for an AI coding agent.

TASK the agent must complete:
{task}

You will see two context briefs (A and B) that were prepared to help the agent \
complete this task. One may have certain cognitive modules disabled. You do NOT \
know which is which.

Judge which brief would lead to BETTER TASK OUTCOMES if given to an AI agent. \
Consider:
1. Relevant information coverage — does the brief contain information the agent needs?
2. Actionable guidance — does the brief provide concrete steps, constraints, or patterns?
3. Failure avoidance — does the brief warn about known pitfalls or past failures?
4. Focus — is the brief well-targeted to this specific task (not generic filler)?

BRIEF A:
---
{brief_a}
---

BRIEF B:
---
{brief_b}
---

Respond with EXACTLY one JSON object (no other text):
{{"winner": "A" or "B" or "TIE", "confidence": 1-5, "reason": "one sentence"}}
"""


def _get_api_key() -> str | None:
    """Get OpenRouter API key."""
    try:
        from clarvis.orch.cost_api import get_api_key
        return get_api_key()
    except Exception:
        auth_path = os.path.join(os.environ.get("OPENCLAW_HOME", os.path.expanduser("~/.openclaw")), "agents/main/agent/auth-profiles.json")
        try:
            with open(auth_path) as f:
                data = json.load(f)
            return data.get("profiles", {}).get("openrouter:default", {}).get("key")
        except Exception:
            return None


def _call_judge(task: str, brief_a: str, brief_b: str) -> dict[str, Any]:
    """Call LLM judge for blind A/B comparison.

    Returns: {"winner": "A"|"B"|"TIE", "confidence": 1-5, "reason": str}
    """
    api_key = _get_api_key()
    if not api_key:
        return {"winner": "TIE", "confidence": 0, "reason": "no API key available",
                "error": "no_api_key"}

    # Truncate briefs to avoid excessive cost (keep first 3000 chars each)
    max_brief = 3000
    brief_a_trunc = brief_a[:max_brief] + ("..." if len(brief_a) > max_brief else "")
    brief_b_trunc = brief_b[:max_brief] + ("..." if len(brief_b) > max_brief else "")

    prompt = JUDGE_PROMPT.format(
        task=task, brief_a=brief_a_trunc, brief_b=brief_b_trunc
    )

    payload = json.dumps({
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150,
        "temperature": 0.0,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=JUDGE_TIMEOUT) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"].strip()

        # Parse JSON from response (handle markdown code blocks)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        result = json.loads(content)
        # Normalize winner
        winner = str(result.get("winner", "TIE")).upper().strip()
        if winner not in ("A", "B", "TIE"):
            winner = "TIE"
        return {
            "winner": winner,
            "confidence": min(5, max(1, int(result.get("confidence", 3)))),
            "reason": str(result.get("reason", ""))[:200],
        }
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError) as e:
        return {"winner": "TIE", "confidence": 0, "reason": f"judge error: {e}",
                "error": str(e)}


# ── Deterministic (offline) scoring ─────────────────────────────────────

def _score_brief_deterministic(brief: str, task: str) -> float:
    """Score a brief without LLM, using heuristic signals.

    Returns 0.0-1.0 composite score based on:
    - Content volume (20%)
    - Section diversity (30%)
    - Task keyword overlap (30%)
    - Actionability markers (20%)
    """
    if not brief or brief.startswith("[ASSEMBLY ERROR"):
        return 0.0

    # Volume score
    chars = len(brief)
    if chars < 100:
        volume = 0.0
    elif chars < 500:
        volume = chars / 500
    elif chars <= 3000:
        volume = 1.0
    else:
        volume = max(0.5, 1.0 - (chars - 3000) / 5000)

    # Section diversity
    section_markers = [
        "EPISODIC", "BRAIN CONTEXT", "KNOWLEDGE", "RELATED TASKS",
        "SUCCESS CRITERIA", "FAILURE", "REASONING", "APPROACH",
        "WORKING MEMORY", "SPOTLIGHT", "PROCEDURE", "CONSTRAINT",
    ]
    brief_upper = brief.upper()
    sections_found = sum(1 for m in section_markers if m in brief_upper)
    diversity = min(1.0, sections_found / 6)

    # Task keyword overlap
    task_words = set(w.lower() for w in task.split() if len(w) > 3)
    brief_words = set(w.lower() for w in brief.split() if len(w) > 3)
    if task_words:
        overlap = len(task_words & brief_words) / len(task_words)
    else:
        overlap = 0.5

    # Actionability markers
    action_markers = [
        "must", "should", "avoid", "ensure", "step", "first",
        "then", "warning", "critical", "error", "fix", "pattern",
        "example", "previous", "learned", "constraint",
    ]
    brief_lower = brief.lower()
    action_hits = sum(1 for m in action_markers if m in brief_lower)
    actionability = min(1.0, action_hits / 5)

    return round(0.2 * volume + 0.3 * diversity + 0.3 * overlap + 0.2 * actionability, 4)


def _compare_briefs_deterministic(
    baseline_brief: str, ablated_brief: str, task: str
) -> tuple[str, int, str]:
    """Diff-based comparison of two briefs. More sensitive than independent scoring.

    Returns (winner: "baseline"|"ablated"|"tie", confidence: 1-5, reason: str)
    """
    if not baseline_brief and not ablated_brief:
        return "tie", 1, "both empty"

    # 1. Unique content analysis — what lines are in one but not the other?
    baseline_lines = set(l.strip() for l in baseline_brief.splitlines() if l.strip())
    ablated_lines = set(l.strip() for l in ablated_brief.splitlines() if l.strip())

    only_baseline = baseline_lines - ablated_lines
    only_ablated = ablated_lines - baseline_lines

    # 2. Score the unique content by task relevance
    task_words = set(w.lower() for w in task.split() if len(w) > 3)

    def _relevance_of_lines(lines: set[str]) -> float:
        if not lines or not task_words:
            return 0.0
        score = 0.0
        for line in lines:
            line_words = set(w.lower() for w in line.split() if len(w) > 3)
            overlap = len(task_words & line_words)
            # Bonus for actionable content
            action_words = {"avoid", "must", "should", "error", "failed", "lesson",
                            "pattern", "warning", "previous", "episode", "procedure"}
            action_bonus = len(action_words & line_words) * 0.5
            score += overlap + action_bonus
        return score

    baseline_relevance = _relevance_of_lines(only_baseline)
    ablated_relevance = _relevance_of_lines(only_ablated)

    # 3. Section presence comparison
    module_sections = {
        "EPISODIC": 2, "EPISODE": 2, "PAST TASK": 2, "LESSON": 2,
        "BRAIN CONTEXT": 2, "KNOWLEDGE": 2,
        "RELATED TASKS": 1, "QUEUE": 1,
        "SUCCESS CRITERIA": 2, "FAILURE": 2, "AVOID": 2, "CONSTRAINT": 2,
        "REASONING": 1, "APPROACH": 1, "STRATEGY": 1,
        "WORKING MEMORY": 1, "SPOTLIGHT": 1, "ATTENTION": 1,
    }

    baseline_upper = baseline_brief.upper()
    ablated_upper = ablated_brief.upper()

    baseline_section_score = sum(
        w for marker, w in module_sections.items() if marker in baseline_upper
    )
    ablated_section_score = sum(
        w for marker, w in module_sections.items() if marker in ablated_upper
    )

    section_delta = baseline_section_score - ablated_section_score

    # 4. Combine signals: unique content relevance + section presence
    # Positive = baseline better, negative = ablated better
    combined = (baseline_relevance - ablated_relevance) * 0.6 + section_delta * 0.4

    if combined > 0.5:
        confidence = min(5, int(combined) + 1)
        return "baseline", confidence, (
            f"baseline has {len(only_baseline)} unique lines "
            f"(relevance +{baseline_relevance - ablated_relevance:.1f})"
        )
    elif combined < -0.5:
        confidence = min(5, int(abs(combined)) + 1)
        return "ablated", confidence, (
            f"ablated has {len(only_ablated)} unique lines "
            f"(relevance +{ablated_relevance - baseline_relevance:.1f})"
        )
    else:
        return "tie", 1, f"briefs differ by {len(only_baseline) + len(only_ablated)} lines, similar quality"


# ── Core sweep logic ────────────────────────────────────────────────────

def run_ablation_v3(
    modules: list[str] | None = None,
    tasks: list[dict] | None = None,
    offline: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run v3 ablation sweep with LLM-judged blind comparison.

    For each module × task: generate baseline brief and ablated brief,
    randomly assign to A/B, have LLM judge winner.

    Args:
        modules: Which modules to ablate (default: all 6).
        tasks: Task list (default: ALL_TASKS, 24 tasks).
        offline: Use deterministic scoring instead of LLM judge.
        dry_run: Print plan without executing.

    Returns:
        Full results dict with per-module, per-category, and aggregate scores.
    """
    modules = modules or ABLATABLE_MODULES
    tasks = tasks or ALL_TASKS
    timestamp = datetime.now(timezone.utc).isoformat()

    if dry_run:
        print(f"[ablation-v3] DRY RUN — {len(tasks)} tasks × {len(modules)} modules "
              f"= {len(tasks) * len(modules)} comparisons")
        print(f"[ablation-v3] Judge model: {JUDGE_MODEL}")
        print(f"[ablation-v3] Mode: {'offline (deterministic)' if offline else 'LLM-judged'}")
        print(f"\nCategories:")
        for cat, cat_tasks in TASK_CATEGORIES.items():
            print(f"  {cat}: {len(cat_tasks)} tasks")
        print(f"\nModules: {', '.join(modules)}")
        return {"dry_run": True, "tasks": len(tasks), "modules": modules}

    t0 = time.time()

    # Per-module tracking
    module_results = {m: {
        "wins": 0, "losses": 0, "ties": 0,
        "total_confidence": 0,
        "category_wins": {},   # category → wins when baseline had this module
        "category_losses": {}, # category → losses
        "comparisons": [],
    } for m in modules}

    total_comparisons = len(tasks) * len(modules)
    done = 0

    for task_info in tasks:
        task_text = task_info["task"]
        category = task_info["category"]
        task_short = task_text[:60]

        # Generate baseline brief (all modules ON) — once per task
        baseline_brief = _generate_brief(task_text, [])

        for module in modules:
            done += 1
            # Generate ablated brief (this module OFF)
            ablated_brief = _generate_brief(task_text, [module])

            if offline:
                # Deterministic: diff-based comparison (more sensitive)
                winner_str, confidence, reason = _compare_briefs_deterministic(
                    baseline_brief, ablated_brief, task_text
                )
                if winner_str == "baseline":
                    winner_is_baseline = True
                elif winner_str == "ablated":
                    winner_is_baseline = False
                else:
                    winner_is_baseline = None

                comparison = {
                    "task": task_short,
                    "category": category,
                    "module": module,
                    "winner": winner_str,
                    "confidence": confidence,
                    "reason": reason,
                }
            else:
                # LLM judge: randomize A/B assignment
                baseline_is_a = random.random() < 0.5
                if baseline_is_a:
                    brief_a, brief_b = baseline_brief, ablated_brief
                else:
                    brief_a, brief_b = ablated_brief, baseline_brief

                judge_result = _call_judge(task_text, brief_a, brief_b)
                raw_winner = judge_result["winner"]

                # Map back: did baseline or ablated win?
                if raw_winner == "TIE":
                    winner_is_baseline = None
                elif raw_winner == "A":
                    winner_is_baseline = baseline_is_a
                else:  # B
                    winner_is_baseline = not baseline_is_a

                confidence = judge_result.get("confidence", 3)

                comparison = {
                    "task": task_short,
                    "category": category,
                    "module": module,
                    "raw_winner": raw_winner,
                    "baseline_is_a": baseline_is_a,
                    "winner": ("baseline" if winner_is_baseline is True
                               else "ablated" if winner_is_baseline is False
                               else "tie"),
                    "confidence": confidence,
                    "reason": judge_result.get("reason", ""),
                }

            # Accumulate results
            mr = module_results[module]
            mr["comparisons"].append(comparison)

            if winner_is_baseline is True:
                mr["wins"] += 1
                mr["category_wins"][category] = mr["category_wins"].get(category, 0) + 1
            elif winner_is_baseline is False:
                mr["losses"] += 1
                mr["category_losses"][category] = mr["category_losses"].get(category, 0) + 1
            else:
                mr["ties"] += 1
            mr["total_confidence"] += confidence

            if done % 10 == 0 or done == total_comparisons:
                elapsed = time.time() - t0
                print(f"[ablation-v3] {done}/{total_comparisons} "
                      f"({elapsed:.0f}s)", flush=True)

    # ── Compute module verdicts ─────────────────────────────────────────

    rankings = []
    for module in modules:
        mr = module_results[module]
        total = mr["wins"] + mr["losses"] + mr["ties"]
        win_rate = mr["wins"] / total if total > 0 else 0.5
        loss_rate = mr["losses"] / total if total > 0 else 0
        avg_conf = mr["total_confidence"] / total if total > 0 else 0

        # Net contribution score: win_rate - loss_rate, weighted by confidence
        # Positive = module helps, negative = module hurts
        net_score = (win_rate - loss_rate) * (avg_conf / 5)

        # Verdict thresholds
        if net_score > 0.15:
            verdict = "CRITICAL"
        elif net_score > 0.05:
            verdict = "HELPFUL"
        elif net_score < -0.05:
            verdict = "HARMFUL"
        else:
            verdict = "NEUTRAL"

        # Per-category breakdown
        category_deltas = {}
        for cat in TASK_CATEGORIES:
            cat_wins = mr["category_wins"].get(cat, 0)
            cat_losses = mr["category_losses"].get(cat, 0)
            cat_total = len(TASK_CATEGORIES[cat])
            if cat_total > 0:
                cat_net = (cat_wins - cat_losses) / cat_total
            else:
                cat_net = 0.0
            category_deltas[cat] = round(cat_net, 3)

        rankings.append({
            "module": module,
            "wins": mr["wins"],
            "losses": mr["losses"],
            "ties": mr["ties"],
            "win_rate": round(win_rate, 3),
            "net_score": round(net_score, 4),
            "avg_confidence": round(avg_conf, 2),
            "verdict": verdict,
            "category_deltas": category_deltas,
        })

    rankings.sort(key=lambda x: x["net_score"], reverse=True)

    # ── Check for non-uniform deltas ────────────────────────────────────

    uniformity_analysis = _analyze_uniformity(rankings)

    result = {
        "timestamp": timestamp,
        "schema_version": "3.0",
        "mode": "offline" if offline else "llm_judged",
        "judge_model": JUDGE_MODEL if not offline else "deterministic",
        "task_count": len(tasks),
        "module_count": len(modules),
        "total_comparisons": total_comparisons,
        "rankings": rankings,
        "uniformity_analysis": uniformity_analysis,
        "categories": list(TASK_CATEGORIES.keys()),
        "total_duration_s": round(time.time() - t0, 1),
    }

    _save_results(result)
    return result


def _analyze_uniformity(rankings: list[dict]) -> dict:
    """Analyze whether module contributions are uniform or task-type-dependent.

    If all modules show similar deltas across categories → uniform (possibly redundant).
    If deltas vary significantly by category → non-uniform (modules specialize).
    """
    categories = list(TASK_CATEGORIES.keys())

    # For each module, compute variance of category deltas
    module_variances = {}
    for r in rankings:
        deltas = [r["category_deltas"].get(c, 0) for c in categories]
        mean = sum(deltas) / len(deltas) if deltas else 0
        variance = sum((d - mean) ** 2 for d in deltas) / len(deltas) if deltas else 0
        module_variances[r["module"]] = round(variance, 6)

    avg_variance = (sum(module_variances.values()) / len(module_variances)
                    if module_variances else 0)

    # Cross-module: do different modules have different net scores?
    net_scores = [r["net_score"] for r in rankings]
    if len(net_scores) >= 2:
        net_mean = sum(net_scores) / len(net_scores)
        cross_module_variance = sum((s - net_mean) ** 2 for s in net_scores) / len(net_scores)
    else:
        cross_module_variance = 0.0

    # Find strongest category specializations
    specializations = []
    for r in rankings:
        for cat, delta in r["category_deltas"].items():
            if abs(delta) >= 0.25:
                specializations.append({
                    "module": r["module"],
                    "category": cat,
                    "delta": delta,
                    "direction": "STRONG" if delta > 0 else "WEAK",
                })

    specializations.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # Verdict
    if cross_module_variance > 0.01 or avg_variance > 0.01:
        pattern = "NON_UNIFORM"
        summary = ("Modules show differentiated contributions across task types. "
                   "No evidence of blanket redundancy.")
    elif all(r["verdict"] == "NEUTRAL" for r in rankings):
        pattern = "FLAT_NEUTRAL"
        summary = ("All modules show negligible impact. Either the test tasks "
                   "don't stress the modules, or assembly masks their contribution.")
    else:
        pattern = "UNIFORM"
        summary = ("Modules show similar contribution patterns across categories. "
                   "Possible redundancy between similarly-scoring modules.")

    return {
        "pattern": pattern,
        "summary": summary,
        "avg_category_variance": round(avg_variance, 6),
        "cross_module_variance": round(cross_module_variance, 6),
        "module_variances": module_variances,
        "specializations": specializations[:10],  # top 10
    }


# ── Persistence ─────────────────────────────────────────────────────────

def _save_results(result: dict):
    """Save latest result and append to history."""
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)

    with open(RESULTS_FILE, "w") as f:
        json.dump(result, f, indent=2)

    # History entry (compact)
    history_entry = {
        "timestamp": result["timestamp"],
        "schema_version": "3.0",
        "mode": result.get("mode"),
        "task_count": result["task_count"],
        "rankings": [
            {"module": r["module"], "net_score": r["net_score"],
             "verdict": r["verdict"], "win_rate": r["win_rate"]}
            for r in result["rankings"]
        ],
        "uniformity_pattern": result["uniformity_analysis"]["pattern"],
        "duration_s": result.get("total_duration_s"),
    }

    lines = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            lines = f.readlines()

    lines.append(json.dumps(history_entry) + "\n")
    if len(lines) > MAX_HISTORY:
        lines = lines[-MAX_HISTORY:]

    with open(HISTORY_FILE, "w") as f:
        f.writelines(lines)


# ── Report formatting ───────────────────────────────────────────────────

def print_report(result: dict | None = None):
    """Print human-readable v3 ablation report with heatmap."""
    if result is None:
        if not os.path.exists(RESULTS_FILE):
            print("No v3 ablation results found. Run a sweep first.")
            return
        with open(RESULTS_FILE) as f:
            result = json.load(f)

    print(f"\n{'='*72}")
    print(f"CLR Outcome Ablation v3 — {result['timestamp'][:19]}")
    print(f"{'='*72}")
    print(f"Mode: {result.get('mode', '?')}  |  Judge: {result.get('judge_model', '?')}")
    print(f"Tasks: {result['task_count']}  |  Modules: {result['module_count']}  |  "
          f"Comparisons: {result['total_comparisons']}  |  "
          f"Duration: {result.get('total_duration_s', '?')}s")

    # Module rankings
    rankings = result.get("rankings", [])
    if rankings:
        print(f"\n{'Module':<22} {'W':>3} {'L':>3} {'T':>3} "
              f"{'Win%':>6} {'Net':>7} {'Conf':>5} {'Verdict':<10}")
        print("-" * 66)
        for r in rankings:
            print(f"{r['module']:<22} {r['wins']:>3} {r['losses']:>3} {r['ties']:>3} "
                  f"{r['win_rate']:>5.1%} {r['net_score']:>+7.4f} "
                  f"{r['avg_confidence']:>5.2f} {r['verdict']:<10}")

    # Category heatmap
    categories = result.get("categories", list(TASK_CATEGORIES.keys()))
    if rankings and categories:
        # Abbreviate category names
        cat_abbr = {
            "code_implementation": "CODE",
            "debugging": "DEBUG",
            "research_analysis": "RSRCH",
            "maintenance_ops": "MAINT",
            "architecture_design": "ARCH",
            "metric_evaluation": "METR",
        }

        abbrs = [cat_abbr.get(c, c[:5].upper()) for c in categories]
        header = f"\n{'Module':<22} " + " ".join(f"{a:>6}" for a in abbrs)
        print(header)
        print("-" * (22 + 7 * len(categories)))

        for r in rankings:
            deltas = r.get("category_deltas", {})
            cells = []
            for cat in categories:
                d = deltas.get(cat, 0)
                if d > 0.25:
                    cells.append(f"{'++':>6}")
                elif d > 0:
                    cells.append(f"{'+':>6}")
                elif d < -0.25:
                    cells.append(f"{'--':>6}")
                elif d < 0:
                    cells.append(f"{'-':>6}")
                else:
                    cells.append(f"{'·':>6}")
            print(f"{r['module']:<22} " + " ".join(cells))

        print("\n  Legend: ++ strong help, + helps, · neutral, - hurts, -- strong hurt")

    # Uniformity analysis
    ua = result.get("uniformity_analysis", {})
    if ua:
        print(f"\nUniformity: {ua.get('pattern', '?')}")
        print(f"  {ua.get('summary', '')}")
        specs = ua.get("specializations", [])
        if specs:
            print(f"\n  Top specializations:")
            for s in specs[:5]:
                print(f"    {s['module']} → {s['category']}: "
                      f"{s['delta']:+.3f} ({s['direction']})")

    print()


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CLR Outcome Ablation Harness v3 — LLM-judged blind comparison"
    )
    parser.add_argument(
        "--module", type=str, default=None,
        help="Ablate a single module (default: all)",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Use deterministic scoring instead of LLM judge",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show plan without executing",
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
    result = run_ablation_v3(
        modules=modules,
        offline=args.offline,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print_report(result)


if __name__ == "__main__":
    main()
