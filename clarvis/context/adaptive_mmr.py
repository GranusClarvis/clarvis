"""Adaptive MMR Lambda — task-category-aware lambda tuning for MMR reranking.

Maps task types to 3 MMR categories with different lambda values:
  - code (lambda=0.7): implementation, bugfix, testing, refactoring, optimization
    → Precise context needed; favors relevance over diversity
  - research (lambda=0.4): research, analysis, survey
    → Broad context needed; favors diversity over relevance
  - maintenance (lambda=0.6): general, cleanup, cron, infrastructure
    → Balanced default

When enough per-category episode data exists (from context_relevance.jsonl),
lambda is nudged toward the empirically better value within bounded range.

Usage:
    from clarvis.context.adaptive_mmr import get_adaptive_lambda, classify_mmr_category

    category = classify_mmr_category("Implement new feature X")  # → "code"
    lam = get_adaptive_lambda("Implement new feature X")         # → ~0.7
"""

import json
import os
from datetime import datetime, timezone, timedelta

_WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
RELEVANCE_FILE = os.path.join(_WORKSPACE, "data", "retrieval_quality", "context_relevance.jsonl")
LAMBDA_STATE_FILE = os.path.join(_WORKSPACE, "data", "retrieval_quality", "adaptive_mmr_state.json")

# --- Base lambdas per category ---
BASE_LAMBDAS = {
    "code": 0.7,       # high relevance, low diversity
    "research": 0.4,   # high diversity, low relevance
    "maintenance": 0.6, # balanced
}

# Bounds for adaptive adjustment
LAMBDA_MIN = 0.25
LAMBDA_MAX = 0.85

# How aggressively to nudge lambda (per update step)
NUDGE_STEP = 0.03

# Minimum episodes per category before we start adjusting
MIN_EPISODES_FOR_ADAPT = 5

# Target context relevance score
TARGET_RELEVANCE = 0.90

# Task-type → MMR category mapping
_CODE_KEYWORDS = frozenset([
    "implement", "build", "create", "add", "wire", "code",
    "fix", "bug", "error", "broken", "failing", "bugfix",
    "test", "pytest", "coverage", "testing",
    "refactor", "extract", "rename", "migrate",
    "optimize", "speed", "perf", "benchmark",
])

_RESEARCH_KEYWORDS = frozenset([
    "research", "survey", "review", "read", "analyze", "analysis",
    "explore", "investigate", "compare", "evaluate", "assess",
    "paper", "arxiv", "literature",
])

_MAINTENANCE_KEYWORDS = frozenset([
    "maintain", "cron", "backup", "health", "monitor", "watchdog",
    "cleanup", "rotate", "compact", "vacuum", "archive",
    "digest", "report", "status",
])


def classify_mmr_category(task_text: str) -> str:
    """Classify a task into an MMR category: code, research, or maintenance.

    Uses keyword matching against the task text. Falls back to 'maintenance'
    (the balanced default) when no keywords match.
    """
    if not task_text:
        return "maintenance"

    task_lower = task_text.lower()
    words = set(task_lower.split())

    # Count keyword hits per category
    code_hits = len(words & _CODE_KEYWORDS)
    research_hits = len(words & _RESEARCH_KEYWORDS)
    maintenance_hits = len(words & _MAINTENANCE_KEYWORDS)

    # Also check substring matches for compound words
    for kw in _CODE_KEYWORDS:
        if kw in task_lower and kw not in words:
            code_hits += 1
    for kw in _RESEARCH_KEYWORDS:
        if kw in task_lower and kw not in words:
            research_hits += 1
    for kw in _MAINTENANCE_KEYWORDS:
        if kw in task_lower and kw not in words:
            maintenance_hits += 1

    # Pick the category with most hits
    if code_hits == 0 and research_hits == 0 and maintenance_hits == 0:
        return "maintenance"  # default fallback

    if research_hits > code_hits and research_hits >= maintenance_hits:
        return "research"
    if code_hits >= research_hits and code_hits >= maintenance_hits:
        return "code"
    return "maintenance"


def _load_state() -> dict:
    """Load the adaptive lambda state (persisted per-category adjustments)."""
    if not os.path.exists(LAMBDA_STATE_FILE):
        return {}
    try:
        with open(LAMBDA_STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    """Persist the adaptive lambda state (atomic write)."""
    os.makedirs(os.path.dirname(LAMBDA_STATE_FILE), exist_ok=True)
    tmp = LAMBDA_STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, LAMBDA_STATE_FILE)


def _aggregate_per_category(days: int = 7) -> dict[str, dict]:
    """Aggregate context_relevance scores grouped by MMR category.

    Returns: {category: {"mean": float, "count": int}}
    """
    if not os.path.exists(RELEVANCE_FILE):
        return {}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    category_scores: dict[str, list[float]] = {}

    try:
        with open(RELEVANCE_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                ts = entry.get("ts", "")
                if ts < cutoff:
                    continue

                overall = entry.get("overall")
                if overall is None:
                    continue

                # Determine category from task text in the entry
                task_text = entry.get("task", "")
                cat = entry.get("mmr_category", classify_mmr_category(task_text))
                category_scores.setdefault(cat, []).append(overall)
    except OSError:
        return {}

    return {
        cat: {"mean": sum(scores) / len(scores), "count": len(scores)}
        for cat, scores in category_scores.items()
    }


def update_lambdas(days: int = 7) -> dict[str, float]:
    """Update adaptive lambda values based on recent episode relevance data.

    For each category with enough episodes:
    - If mean relevance < TARGET: nudge lambda down (more diversity)
    - If mean relevance >= TARGET: nudge lambda up (more precision)
    - Clamp within [LAMBDA_MIN, LAMBDA_MAX]

    Returns the updated lambda dict: {category: lambda_value}
    """
    state = _load_state()
    per_cat = _aggregate_per_category(days=days)

    result = {}
    for cat, base in BASE_LAMBDAS.items():
        current = state.get(cat, {}).get("lambda", base)
        cat_data = per_cat.get(cat, {})

        if cat_data.get("count", 0) >= MIN_EPISODES_FOR_ADAPT:
            mean_rel = cat_data["mean"]
            if mean_rel < TARGET_RELEVANCE:
                # Below target → more diversity might help (lower lambda)
                current = max(LAMBDA_MIN, current - NUDGE_STEP)
            else:
                # At or above target → more precision is safe (raise lambda)
                current = min(LAMBDA_MAX, current + NUDGE_STEP)

        result[cat] = round(current, 3)
        state[cat] = {
            "lambda": result[cat],
            "base": base,
            "episodes": cat_data.get("count", 0),
            "mean_relevance": round(cat_data.get("mean", 0.0), 4),
            "updated": datetime.now(timezone.utc).isoformat(),
        }

    _save_state(state)
    return result


def get_adaptive_lambda(task_text: str, update: bool = False) -> float:
    """Get the adaptive MMR lambda for a task.

    Args:
        task_text: The task description string.
        update: If True, run update_lambdas() first (use in postflight, not preflight).

    Returns:
        float lambda value in [LAMBDA_MIN, LAMBDA_MAX].
    """
    if update:
        lambdas = update_lambdas()
    else:
        state = _load_state()
        lambdas = {cat: state.get(cat, {}).get("lambda", base)
                   for cat, base in BASE_LAMBDAS.items()}

    category = classify_mmr_category(task_text)
    return lambdas.get(category, BASE_LAMBDAS.get(category, 0.5))
