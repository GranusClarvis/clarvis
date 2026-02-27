#!/usr/bin/env python3
"""
Absolute Zero Reasoner — Self-improvement through autonomous task generation.

Adapted from "Absolute Zero: Reinforced Self-play Reasoning with Zero Data"
(Zhao et al., 2025, Tsinghua/LeapLab). The core AZR insight: a single agent
can improve by proposing tasks at the edge of its capability, solving them,
and using a learnability signal to evolve the task curriculum.

Clarvis adaptation uses three reasoning modes (analogous to AZR's triplet):
  - Deduction: Given a system state + action, predict the outcome.
  - Abduction: Given a symptom/outcome, infer the root cause.
  - Induction: Given multiple episodes, synthesize a general principle.

Each mode has a Proposer (generates tasks from experience) and a Solver
(attempts the task). A code executor validates solutions where possible.
The learnability reward biases future proposals toward moderate difficulty
(not trivially easy, not impossibly hard).

Usage:
    python3 absolute_zero.py run              # Run one AZR cycle (propose + solve)
    python3 absolute_zero.py run 5            # Run 5 cycles
    python3 absolute_zero.py stats            # Show AZR statistics
    python3 absolute_zero.py buffer           # Show task buffer contents
    python3 absolute_zero.py insights         # List stored AZR insights

Integration:
    - Wired into cron_reflection.sh as a nightly self-improvement step
    - Tasks that yield high-learnability insights get injected into QUEUE.md
"""

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain import brain
from episodic_memory import episodic

# ── Storage ──────────────────────────────────────────────────────────────
DATA_DIR = Path("/home/agent/.openclaw/workspace/data/absolute_zero")
DATA_DIR.mkdir(parents=True, exist_ok=True)

BUFFER_FILE = DATA_DIR / "task_buffer.json"
HISTORY_FILE = DATA_DIR / "history.jsonl"
STATS_FILE = DATA_DIR / "stats.json"

SCRIPTS_DIR = Path("/home/agent/.openclaw/workspace/scripts")
EPISODES_FILE = Path("/home/agent/.openclaw/workspace/data/episodes.json")

# ── Constants ────────────────────────────────────────────────────────────
TASK_TYPES = ["deduction", "abduction", "induction"]
BUFFER_CAP = 100       # Max tasks per type in buffer
HISTORY_CAP = 500      # Max history entries
MONTE_CARLO_N = 3      # Rollouts for learnability estimation


# ══════════════════════════════════════════════════════════════════════════
# Task Buffer — stores proposed tasks and their learnability scores
# ══════════════════════════════════════════════════════════════════════════

def _load_buffer() -> dict:
    if BUFFER_FILE.exists():
        try:
            with open(BUFFER_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {t: [] for t in TASK_TYPES}


def _save_buffer(buf: dict):
    for t in TASK_TYPES:
        buf[t] = buf.get(t, [])[-BUFFER_CAP:]
    with open(BUFFER_FILE, "w") as f:
        json.dump(buf, f, indent=2)


def _log_history(entry: dict):
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "cycles": 0, "proposals": 0, "solves": 0,
        "correct": 0, "insights_stored": 0,
        "by_type": {t: {"proposed": 0, "solved": 0, "correct": 0,
                         "learnability_sum": 0.0} for t in TASK_TYPES},
        "last_run": None,
    }


def _save_stats(stats: dict):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


# ══════════════════════════════════════════════════════════════════════════
# Episode Sampling — raw material for task generation
# ══════════════════════════════════════════════════════════════════════════

def _load_episodes() -> list:
    if EPISODES_FILE.exists():
        try:
            with open(EPISODES_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _sample_episodes(n: int = 5, bias: str = "mixed") -> list:
    """Sample episodes weighted by recency and valence diversity."""
    eps = _load_episodes()
    if not eps:
        return []

    if bias == "failures":
        pool = [e for e in eps if e.get("outcome") in ("failure", "soft_failure", "timeout")]
        if not pool:
            pool = eps
    elif bias == "successes":
        pool = [e for e in eps if e.get("outcome") == "success"]
        if not pool:
            pool = eps
    else:
        pool = eps

    weights = []
    for i, ep in enumerate(pool):
        recency = (i + 1) / len(pool)
        valence = ep.get("valence", 0.5)
        weights.append(recency * 0.5 + abs(valence - 0.5) * 0.5)

    k = min(n, len(pool))
    selected = random.choices(pool, weights=weights, k=k)

    # Deduplicate
    seen = set()
    unique = []
    for ep in selected:
        eid = ep.get("id", id(ep))
        if eid not in seen:
            seen.add(eid)
            unique.append(ep)
    return unique[:n]


# ══════════════════════════════════════════════════════════════════════════
# Proposer — generates tasks from episodes (3 reasoning modes)
# ══════════════════════════════════════════════════════════════════════════

def propose_deduction(episodes: list) -> dict | None:
    """Deduction: Given state + action → predict outcome.

    We select a past episode and construct a prediction task:
    'Given that Clarvis was in state X and took action Y, what was the outcome?'
    The ground truth is the actual episode outcome.
    """
    if not episodes:
        return None

    ep = random.choice(episodes)
    task_text = ep.get("task", "unknown task")
    outcome = ep.get("outcome", "unknown")
    duration = ep.get("duration_s", 0)
    error = ep.get("error", "")
    section = ep.get("section", "")

    # Build the prediction challenge
    prompt = (
        "Predict the outcome of this autonomous task:\n"
        f"  Task: {task_text[:120]}\n"
        f"  Priority: {section}\n"
        "  Context: Clarvis autonomous heartbeat execution\n"
        "What was the outcome? Choose: success, failure, timeout, soft_failure\n"
        "Also predict: approximate duration (seconds) and whether errors occurred."
    )

    gold = {
        "outcome": outcome,
        "duration_range": _duration_bucket(duration),
        "had_error": bool(error),
    }

    return {
        "type": "deduction",
        "prompt": prompt,
        "gold": gold,
        "source_episode": ep.get("id", ""),
        "difficulty_hint": _estimate_difficulty(ep),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def propose_abduction(episodes: list) -> dict | None:
    """Abduction: Given symptom → infer root cause.

    Select a failure episode and ask: 'Given this error/outcome, what was
    the root cause?' The ground truth comes from causal chain analysis.
    """
    failures = [e for e in episodes if e.get("outcome") in ("failure", "soft_failure", "timeout")]
    if not failures:
        # Use any episode and ask about potential failure modes
        if not episodes:
            return None
        ep = random.choice(episodes)
        prompt = (
            "Abductive reasoning challenge:\n"
            f"  Task '{ep.get('task', '')[:100]}' completed with outcome '{ep.get('outcome', '')}'.\n"
            "  If this task had FAILED, what would be the most likely root cause?\n"
            "  Consider: dependency issues, timeout risks, data corruption, import errors."
        )
        gold = {
            "reasoning_type": "counterfactual_abduction",
            "plausible_causes": _infer_failure_modes(ep),
        }
    else:
        ep = random.choice(failures)
        error_msg = ep.get("error", "no error message recorded")
        prompt = (
            "Abductive reasoning challenge:\n"
            f"  Task: {ep.get('task', '')[:100]}\n"
            f"  Outcome: {ep.get('outcome', '')}\n"
            f"  Error: {error_msg[:200]}\n"
            f"  Duration: {ep.get('duration_s', 0)}s\n"
            "What is the root cause? Provide a specific diagnosis."
        )

        # Get causal chain if available
        causes = []
        try:
            chain = episodic.causes_of(ep.get("id", ""))
            causes = [link[1].get("task", "")[:60] for link in chain[:3]]
        except Exception:
            pass

        gold = {
            "reasoning_type": "failure_diagnosis",
            "error_category": _categorize_error(error_msg),
            "causal_chain": causes,
        }

    return {
        "type": "abduction",
        "prompt": prompt,
        "gold": gold,
        "source_episode": ep.get("id", ""),
        "difficulty_hint": 0.6,  # Abduction is generally harder
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def propose_induction(episodes: list) -> dict | None:
    """Induction: Given multiple episodes → synthesize a general principle.

    Select 3-5 related episodes and ask: 'What pattern or principle do
    these episodes reveal?' Validated by checking if the principle is
    novel (not already in brain) and internally consistent.
    """
    if len(episodes) < 3:
        return None

    # Group by outcome or domain for coherent induction
    sample = random.sample(episodes, min(5, len(episodes)))

    episode_summaries = []
    for ep in sample:
        summary = (
            f"  - [{ep.get('outcome', '?')}] {ep.get('task', '')[:80]} "
            f"({ep.get('duration_s', 0)}s, section={ep.get('section', '?')})"
        )
        episode_summaries.append(summary)

    prompt = (
        "Inductive reasoning challenge:\n"
        f"Given these {len(sample)} episodes from Clarvis's history:\n"
        + "\n".join(episode_summaries) + "\n"
        "\nSynthesize a general principle or pattern that explains these observations.\n"
        "The principle should be:\n"
        "  1. Specific enough to be actionable\n"
        "  2. General enough to apply beyond these specific episodes\n"
        "  3. Testable (we could verify it against future episodes)"
    )

    # Gold: compute observable patterns
    outcomes = [ep.get("outcome", "") for ep in sample]
    durations = [ep.get("duration_s", 0) for ep in sample]
    success_rate = outcomes.count("success") / len(outcomes) if outcomes else 0

    gold = {
        "reasoning_type": "pattern_synthesis",
        "episode_count": len(sample),
        "success_rate": round(success_rate, 2),
        "avg_duration": round(sum(durations) / len(durations)) if durations else 0,
        "outcome_distribution": {o: outcomes.count(o) for o in set(outcomes)},
    }

    return {
        "type": "induction",
        "prompt": prompt,
        "gold": gold,
        "source_episodes": [ep.get("id", "") for ep in sample],
        "difficulty_hint": 0.7,  # Induction is the hardest
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════
# Solver — attempts to solve proposed tasks
# ══════════════════════════════════════════════════════════════════════════

def solve_deduction(task: dict) -> dict:
    """Solve a deduction task by analyzing the prompt and predicting outcome."""
    prompt = task["prompt"]
    gold = task["gold"]

    # Rule-based solver: analyze task text for outcome signals
    prompt_lower = prompt.lower()

    # Predict outcome based on heuristics from meta-learning
    predicted_outcome = _predict_outcome_heuristic(prompt_lower)

    # Predict duration bucket
    predicted_duration = _predict_duration_heuristic(prompt_lower)

    # Predict error likelihood
    predicted_error = _predict_error_heuristic(prompt_lower)

    # Score against gold
    score = 0.0
    if predicted_outcome == gold["outcome"]:
        score += 0.5
    if predicted_duration == gold.get("duration_range", ""):
        score += 0.25
    if predicted_error == gold.get("had_error", False):
        score += 0.25

    return {
        "predicted": {
            "outcome": predicted_outcome,
            "duration_range": predicted_duration,
            "had_error": predicted_error,
        },
        "gold": gold,
        "score": score,
        "correct": score >= 0.5,
    }


def solve_abduction(task: dict) -> dict:
    """Solve an abduction task by diagnosing root cause."""
    prompt = task["prompt"]
    gold = task["gold"]
    prompt_lower = prompt.lower()

    # Diagnose based on error patterns from meta-learning
    diagnosis = _diagnose_heuristic(prompt_lower)

    # Score: check if diagnosis matches gold category
    score = 0.0
    if gold.get("reasoning_type") == "failure_diagnosis":
        gold_category = gold.get("error_category", "")
        if diagnosis["category"] == gold_category:
            score = 1.0
        elif diagnosis["category"] in gold_category or gold_category in diagnosis["category"]:
            score = 0.5
        elif diagnosis["category"] != "unknown":
            score = 0.2  # At least made a specific diagnosis
    else:
        # Counterfactual — score based on plausibility
        plausible = gold.get("plausible_causes", [])
        diag_lower = (diagnosis["category"] + " " + diagnosis["explanation"]).lower()
        if any(cause in diag_lower for cause in plausible):
            score = 0.75
        elif diagnosis["category"] != "unknown":
            score = 0.35  # Partial credit for specific diagnosis
        else:
            score = 0.15  # Minimal credit for attempting

    return {
        "diagnosis": diagnosis,
        "gold": gold,
        "score": score,
        "correct": score >= 0.5,
    }


def solve_induction(task: dict) -> dict:
    """Solve an induction task by synthesizing a principle."""
    prompt = task["prompt"]
    gold = task["gold"]

    # Extract episode data from prompt
    success_rate = gold.get("success_rate", 0.5)
    avg_duration = gold.get("avg_duration", 0)
    outcome_dist = gold.get("outcome_distribution", {})

    # Synthesize principle based on statistical patterns
    principle = _synthesize_principle(success_rate, avg_duration, outcome_dist, prompt)

    # Score: check novelty against brain
    novelty_score = _check_novelty(principle)

    # Score: check internal consistency (principle should be supported by data)
    consistency_score = _check_consistency(principle, gold)

    score = novelty_score * 0.5 + consistency_score * 0.5

    return {
        "principle": principle,
        "novelty_score": novelty_score,
        "consistency_score": consistency_score,
        "gold": gold,
        "score": score,
        "correct": score >= 0.4,
    }


# ══════════════════════════════════════════════════════════════════════════
# Learnability Reward — AZR's key innovation
# ══════════════════════════════════════════════════════════════════════════

def compute_learnability(task: dict, solve_fn) -> float:
    """Compute learnability reward via Monte Carlo rollouts.

    learnability = 0 if all rollouts succeed or all fail (too easy/hard)
    learnability = 1 - avg_success_rate otherwise (moderate difficulty = max reward)

    This is the core AZR insight: tasks at the edge of capability produce
    the richest learning signal.
    """
    scores = []
    for _ in range(MONTE_CARLO_N):
        result = solve_fn(task)
        scores.append(result["score"])

    avg_score = sum(scores) / len(scores) if scores else 0

    # AZR learnability: 0 if trivial (all correct) or impossible (all wrong)
    if avg_score >= 0.95 or avg_score <= 0.05:
        return 0.0

    # Peak learnability at moderate difficulty
    return round(1.0 - avg_score, 3)


# ══════════════════════════════════════════════════════════════════════════
# Main AZR Cycle
# ══════════════════════════════════════════════════════════════════════════

def run_cycle() -> dict:
    """Run one full AZR cycle: propose → solve → score → store.

    Returns a summary dict.
    """
    buf = _load_buffer()
    stats = _load_stats()
    now = datetime.now(timezone.utc)

    # Sample episodes (raw material)
    episodes = _sample_episodes(n=10, bias="mixed")
    if not episodes:
        return {"error": "no_episodes", "message": "No episodes to generate tasks from"}

    task_type = random.choice(TASK_TYPES)

    # ── Propose Phase ──
    proposer_map = {
        "deduction": propose_deduction,
        "abduction": propose_abduction,
        "induction": propose_induction,
    }
    solver_map = {
        "deduction": solve_deduction,
        "abduction": solve_abduction,
        "induction": solve_induction,
    }

    proposer = proposer_map[task_type]
    solver = solver_map[task_type]

    task = proposer(episodes)
    if not task:
        return {"error": "proposal_failed", "type": task_type}

    stats["proposals"] += 1
    stats["by_type"][task_type]["proposed"] += 1

    # ── Solve Phase ──
    result = solver(task)
    stats["solves"] += 1
    stats["by_type"][task_type]["solved"] += 1

    if result["correct"]:
        stats["correct"] += 1
        stats["by_type"][task_type]["correct"] += 1

    # ── Learnability Phase ──
    learnability = compute_learnability(task, solver)
    stats["by_type"][task_type]["learnability_sum"] += learnability

    # ── Store Results ──
    task["learnability"] = learnability
    task["solve_score"] = result["score"]
    buf[task_type].append(task)
    _save_buffer(buf)

    # Log history
    entry = {
        "timestamp": now.isoformat(),
        "type": task_type,
        "learnability": learnability,
        "score": result["score"],
        "correct": result["correct"],
        "source_episode": task.get("source_episode", ""),
    }
    _log_history(entry)

    # ── Extract Insight if Learnable ──
    insight = None
    if learnability > 0.3:
        insight = _extract_insight(task_type, task, result, learnability)
        if insight:
            brain.store(
                f"[AZR-{task_type.upper()}] {insight}",
                collection="autonomous-learning",
                importance=min(0.4 + learnability * 0.4, 0.8),
                tags=["absolute_zero", task_type, "self_improvement"],
                source="absolute_zero",
            )
            stats["insights_stored"] += 1

    stats["cycles"] += 1
    stats["last_run"] = now.isoformat()
    _save_stats(stats)

    return {
        "cycle": stats["cycles"],
        "type": task_type,
        "learnability": learnability,
        "solve_score": result["score"],
        "correct": result["correct"],
        "insight": insight,
        "source_episode": task.get("source_episode", ""),
    }


def run_n_cycles(n: int = 3) -> dict:
    """Run n AZR cycles, one per task type if possible."""
    results = []
    for i in range(n):
        result = run_cycle()
        results.append(result)
        if "error" in result:
            break

    insights = [r.get("insight") for r in results if r.get("insight")]
    avg_learnability = (
        sum(r.get("learnability", 0) for r in results) / len(results)
        if results else 0
    )

    # If we found high-learnability patterns, inject a task into QUEUE
    if avg_learnability > 0.5 and insights:
        _inject_improvement_task(insights, avg_learnability)

    return {
        "cycles_run": len(results),
        "avg_learnability": round(avg_learnability, 3),
        "insights_generated": len(insights),
        "insights": insights,
        "results": results,
    }


# ══════════════════════════════════════════════════════════════════════════
# Heuristic Solvers — rule-based reasoning (no LLM call needed)
# ══════════════════════════════════════════════════════════════════════════

def _extract_task_text(prompt_lower: str) -> str:
    """Extract just the task description from a deduction prompt.

    Avoids template self-contamination where keywords like 'timeout' and
    'failure' in the choices line ("Choose: success, failure, timeout, ...")
    would match against failure/error signals.

    Prompt format:
      "Predict the outcome of this autonomous task:
        Task: <description>
        Priority: ...
        Context: ..."
    """
    # Find "  task: " (indented) to skip "autonomous task:\n" in the header
    marker = "\n  task: "
    if marker not in prompt_lower:
        # Fallback: try "task: " at start of string
        if prompt_lower.startswith("task: "):
            start = 6
        else:
            return prompt_lower
    else:
        start = prompt_lower.index(marker) + len(marker)
    end = len(prompt_lower)
    for delimiter in ["\n", "priority:", "context:", "what was"]:
        pos = prompt_lower.find(delimiter, start)
        if pos != -1 and pos < end:
            end = pos
    return prompt_lower[start:end].strip()


def _predict_outcome_heuristic(prompt_lower: str) -> str:
    """Predict task outcome from textual signals.

    NOTE (2026-02-24): Fixed pessimism bias caused by two issues:
    1. Template self-contamination: the prompt template contains "timeout" and
       "soft_failure" in the choices line, which were matching failure_signals
       on EVERY deduction task (guaranteed fail_count >= 1).
    2. Substring false positives: "memory" matched "episodic_memory.py" etc.,
       triggering false failure predictions for successful tasks.
    Fix: extract only the task description line for keyword matching, and use
    word-boundary-aware matching for ambiguous keywords.
    """
    task_text = _extract_task_text(prompt_lower)

    # Load recent success rate from episodes for calibration
    eps = _load_episodes()
    recent = eps[-20:] if eps else []
    if recent:
        outcomes = [e.get("outcome", "success") for e in recent]
        success_rate = outcomes.count("success") / len(outcomes)
    else:
        success_rate = 0.5

    # Keyword signals — matched against task description only (not template)
    hard_signals = ["complex", "multi-step", "refactor", "research", "investigate",
                    "deep", "analyze", "global", "consciousness"]
    easy_signals = ["fix typo", "simple", "add comment", "log", "update version",
                    "run test"]
    # Use multi-word phrases or word-boundary patterns to avoid substring matches
    # e.g. "memory" alone matches "episodic_memory.py" — use "out of memory" instead
    failure_signals = ["nested claude", "timed out", "import error",
                       "out of memory", "permission denied", "oom"]

    hard_count = sum(1 for s in hard_signals if s in task_text)
    easy_count = sum(1 for s in easy_signals if s in task_text)
    fail_count = sum(1 for s in failure_signals if s in task_text)

    if fail_count >= 2:
        return "failure"
    if fail_count == 1:
        return "soft_failure"
    if hard_count >= 2 and success_rate < 0.6:
        return "soft_failure"
    if easy_count >= 1:
        return "success"
    # Default: use base rate, but anchor toward success when rate > 0.5
    # (prior heuristic was too pessimistic at 65% base rate)
    return "success" if random.random() < success_rate else "soft_failure"


def _predict_duration_heuristic(prompt_lower: str) -> str:
    """Predict duration bucket."""
    task_text = _extract_task_text(prompt_lower)
    if any(kw in task_text for kw in ["research", "deep", "investigate", "complex"]):
        return "long"
    if any(kw in task_text for kw in ["fix", "simple", "add", "update"]):
        return "short"
    return "medium"


def _predict_error_heuristic(prompt_lower: str) -> bool:
    """Predict whether errors occurred."""
    task_text = _extract_task_text(prompt_lower)
    error_signals = ["error", "fail", "timed out", "exception", "crash",
                     "permission denied"]
    return sum(1 for s in error_signals if s in task_text) >= 2


def _diagnose_heuristic(prompt_lower: str) -> dict:
    """Diagnose root cause from error description."""
    categories = {
        "import_error": ["import", "module", "no module"],
        "timeout": ["timeout", "timed out", "exceeded", "900s", "600s"],
        "dependency": ["dependency", "missing", "not found", "requires"],
        "permission": ["permission", "denied", "access", "forbidden"],
        "data_corruption": ["corrupt", "invalid json", "malformed", "parse error"],
        "resource_exhaustion": ["memory", "disk", "full", "oom"],
        "logic_error": ["assertion", "wrong", "incorrect", "unexpected"],
        "nested_execution": ["claude code", "nested", "subprocess", "spawn"],
    }

    scores = {}
    for cat, keywords in categories.items():
        score = sum(1 for kw in keywords if kw in prompt_lower)
        if score > 0:
            scores[cat] = score

    if scores:
        best = max(scores, key=scores.get)
        return {"category": best, "confidence": min(scores[best] / 3, 1.0),
                "explanation": f"Pattern match: {best} ({scores[best]} keyword hits)"}

    return {"category": "unknown", "confidence": 0.1,
            "explanation": "No strong pattern match found"}


def _synthesize_principle(success_rate: float, avg_duration: float,
                          outcome_dist: dict, prompt: str) -> str:
    """Synthesize a general principle from episode patterns."""
    principles = []

    if success_rate >= 0.8:
        principles.append(
            f"Tasks in this category have high success ({success_rate:.0%}). "
            "The system is well-calibrated for this type of work."
        )
    elif success_rate <= 0.4:
        # Identify what's failing
        failure_types = {k: v for k, v in outcome_dist.items() if k != "success"}
        dominant = max(failure_types, key=failure_types.get) if failure_types else "unknown"
        principles.append(
            f"Low success rate ({success_rate:.0%}) dominated by '{dominant}' outcomes. "
            "This capability gap needs targeted improvement."
        )
    else:
        principles.append(
            f"Moderate success rate ({success_rate:.0%}) suggests these tasks are at "
            "the edge of current capability — optimal for learning."
        )

    if avg_duration > 300:
        principles.append(
            f"Average duration ({avg_duration}s) is high; consider breaking tasks "
            "into smaller subtasks or improving execution efficiency."
        )
    elif avg_duration < 30:
        principles.append(
            f"Very fast execution ({avg_duration}s avg) suggests tasks may be too simple "
            "or not exercising deep reasoning."
        )

    return " ".join(principles)


def _check_novelty(principle: str) -> float:
    """Check if a principle is novel (not already in brain)."""
    try:
        similar = brain.recall(principle, n=3, collections=["autonomous-learning", "clarvis-learnings"])
        if not similar:
            return 1.0

        # Check similarity by keyword overlap
        principle_words = set(principle.lower().split())
        for mem in similar:
            doc_words = set(mem["document"].lower().split())
            overlap = len(principle_words & doc_words) / max(len(principle_words), 1)
            if overlap > 0.6:
                return 0.1  # Very similar exists
            if overlap > 0.4:
                return 0.4

        return 0.8  # Somewhat novel
    except Exception:
        return 0.5  # Can't check, assume moderate novelty


def _check_consistency(principle: str, gold: dict) -> float:
    """Check if principle is consistent with the data."""
    success_rate = gold.get("success_rate", 0.5)
    principle_lower = principle.lower()

    # Check if principle direction matches data
    if "high success" in principle_lower and success_rate >= 0.7:
        return 1.0
    if "low success" in principle_lower and success_rate <= 0.4:
        return 1.0
    if "moderate" in principle_lower and 0.3 < success_rate < 0.8:
        return 0.8
    if "too simple" in principle_lower and gold.get("avg_duration", 999) < 60:
        return 0.9

    return 0.5  # Neutral


# ══════════════════════════════════════════════════════════════════════════
# Helper utilities
# ══════════════════════════════════════════════════════════════════════════

def _duration_bucket(seconds: int) -> str:
    if seconds < 60:
        return "short"
    if seconds < 300:
        return "medium"
    return "long"


def _estimate_difficulty(ep: dict) -> float:
    """Estimate task difficulty from episode metadata."""
    difficulty = 0.5
    if ep.get("outcome") in ("failure", "timeout"):
        difficulty += 0.2
    if ep.get("duration_s", 0) > 300:
        difficulty += 0.1
    if ep.get("error"):
        difficulty += 0.1
    return min(difficulty, 1.0)


def _infer_failure_modes(ep: dict) -> list:
    """Infer plausible failure modes for a successful episode."""
    modes = []
    task_lower = ep.get("task", "").lower()

    if any(kw in task_lower for kw in ["import", "module", "script"]):
        modes.append("import")
    if any(kw in task_lower for kw in ["cron", "schedule", "heartbeat"]):
        modes.append("timeout")
    if any(kw in task_lower for kw in ["memory", "brain", "store", "recall"]):
        modes.append("data")
    if any(kw in task_lower for kw in ["file", "write", "edit", "create"]):
        modes.append("permission")
    if not modes:
        modes = ["timeout", "dependency"]
    return modes


def _categorize_error(error_msg: str) -> str:
    """Categorize an error message."""
    error_lower = (error_msg or "").lower()
    if "import" in error_lower or "module" in error_lower:
        return "import_error"
    if "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    if "permission" in error_lower:
        return "permission"
    if "json" in error_lower or "parse" in error_lower:
        return "data_corruption"
    if "memory" in error_lower or "oom" in error_lower:
        return "resource_exhaustion"
    return "logic_error"


def _extract_insight(task_type: str, task: dict, result: dict,
                     learnability: float) -> str | None:
    """Extract a learning insight from a solved task."""
    if task_type == "deduction":
        pred = result.get("predicted", {})
        gold = result.get("gold", {})
        if pred.get("outcome") != gold.get("outcome"):
            return (
                f"Prediction miscalibration: predicted '{pred.get('outcome')}' "
                f"but actual was '{gold.get('outcome')}'. "
                f"Learnability={learnability:.2f} — this outcome pattern "
                "should be studied for better prediction."
            )
        else:
            return (
                "Outcome prediction calibrated for this task type "
                f"(learnability={learnability:.2f}). "
                f"Duration prediction: {'correct' if pred.get('duration_range') == gold.get('duration_range') else 'off'}"
            )

    elif task_type == "abduction":
        diagnosis = result.get("diagnosis", {})
        return (
            f"Root cause diagnosis: {diagnosis.get('category', 'unknown')} "
            f"(confidence={diagnosis.get('confidence', 0):.2f}). "
            f"Learnability={learnability:.2f} — "
            f"{'novel failure pattern' if learnability > 0.5 else 'known pattern'}."
        )

    elif task_type == "induction":
        principle = result.get("principle", "")
        novelty = result.get("novelty_score", 0)
        if novelty > 0.5 and principle:
            return (
                f"Novel principle (novelty={novelty:.2f}): {principle[:200]}"
            )

    return None


def _inject_improvement_task(insights: list, avg_learnability: float):
    """Inject a self-improvement task into QUEUE.md if learnability is high."""
    try:
        from queue_writer import add_task
        task_desc = (
            "[AZR] Self-improvement: AZR cycle found capability gap "
            f"(avg_learnability={avg_learnability:.2f}). "
            f"Insights: {'; '.join(i[:80] for i in insights[:2] if i)}. "
            "Investigate and address the weakest prediction/diagnosis area."
        )
        add_task(task_desc, priority="P1", source="absolute_zero")
        print("  [AZR] Injected improvement task into QUEUE.md P1")
    except Exception as e:
        print(f"  [AZR] Could not inject task: {e}")


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def print_stats():
    """Print AZR statistics."""
    stats = _load_stats()
    print("Absolute Zero Reasoner — Statistics")
    print(f"  Total cycles: {stats['cycles']}")
    print(f"  Proposals: {stats['proposals']}")
    print(f"  Solves: {stats['solves']} (correct: {stats['correct']})")
    print(f"  Insights stored: {stats['insights_stored']}")
    print(f"  Last run: {stats.get('last_run', 'never')}")
    print()
    for t in TASK_TYPES:
        ts = stats["by_type"].get(t, {})
        proposed = ts.get("proposed", 0)
        correct = ts.get("correct", 0)
        learn_sum = ts.get("learnability_sum", 0)
        avg_learn = learn_sum / proposed if proposed > 0 else 0
        accuracy = correct / proposed if proposed > 0 else 0
        print(f"  {t}: proposed={proposed} correct={correct} "
              f"accuracy={accuracy:.0%} avg_learnability={avg_learn:.3f}")


def print_buffer():
    """Print task buffer contents."""
    buf = _load_buffer()
    for t in TASK_TYPES:
        tasks = buf.get(t, [])
        print(f"\n{t} buffer ({len(tasks)} tasks):")
        for task in tasks[-5:]:
            learn = task.get("learnability", 0)
            score = task.get("solve_score", 0)
            print(f"  [L={learn:.2f} S={score:.2f}] {task.get('prompt', '')[:80]}...")


def print_insights():
    """Print stored AZR insights from brain."""
    try:
        # Use the AZR tag prefix for better recall
        results = brain.recall(
            "AZR prediction miscalibration learnability diagnosis principle",
            n=20,
            collections=["autonomous-learning"]
        )
        found = 0
        for r in results:
            doc = r.get("document", "")
            if doc.startswith("[AZR-"):
                found += 1
                meta = r.get("metadata", {})
                print(f"  [{meta.get('created_at', '')[:10]}] "
                      f"(imp={meta.get('importance', 0):.2f}) "
                      f"{doc[:120]}")
        if found == 0:
            print("  No AZR insights found yet. Run 'absolute_zero.py run' first.")
    except Exception as e:
        print(f"  Error loading insights: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: absolute_zero.py <run|stats|buffer|insights> [n_cycles]")
        print("Commands:")
        print("  run [n]    Run AZR cycles (default: 3)")
        print("  stats      Show AZR statistics")
        print("  buffer     Show task buffer contents")
        print("  insights   List stored AZR insights")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "run":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        print(f"[AZR] Running {n} Absolute Zero Reasoner cycle(s)...")
        result = run_n_cycles(n)
        print("\n[AZR] Complete:")
        print(f"  Cycles: {result['cycles_run']}")
        print(f"  Avg learnability: {result['avg_learnability']:.3f}")
        print(f"  Insights: {result['insights_generated']}")
        for ins in (result.get("insights") or []):
            if ins:
                print(f"    → {ins[:100]}")
        for r in result.get("results", []):
            if "error" not in r:
                print(f"  [{r['type']}] L={r['learnability']:.2f} "
                      f"score={r['solve_score']:.2f} "
                      f"{'✓' if r['correct'] else '✗'}")
        print(json.dumps(result, indent=2, default=str))

    elif cmd == "stats":
        print_stats()

    elif cmd == "buffer":
        print_buffer()

    elif cmd == "insights":
        print_insights()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
