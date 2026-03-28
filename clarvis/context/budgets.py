"""
Context budget allocation — tiered token budgets with adaptive relevance scaling.

Manages the per-section token budgets used by the brief generator.
Budget categories map to context_relevance section names and are scaled
based on rolling 14-day relevance data.
"""

import logging

logger = logging.getLogger(__name__)

# Mapping from budget keys to context_relevance section names.
# Each budget key controls a region of the brief; the section names are
# what context_relevance.py tracks at the per-section level.
# Note: brain_goals, metrics folded into decision_context; synaptic folded
# into spotlight (2026-03-18) — all had mean relevance < 0.12 as standalone.
BUDGET_TO_SECTIONS = {
    "decision_context": ["decision_context", "failure_avoidance", "meta_gradient",
                         "brain_goals", "metrics"],
    "spotlight": ["working_memory", "attention", "gwt_broadcast", "brain_context",
                  "synaptic"],
    "related_tasks": ["related_tasks"],
    "completions": ["completions"],
    "episodes": ["episodes"],
    "reasoning_scaffold": ["reasoning"],
}

# Relevance-based budget adjustment parameters
MIN_EPISODES_FOR_ADJUSTMENT = 5  # need enough data before adjusting
BUDGET_FLOOR = 0.4   # minimum 40% of base budget (legacy, used as fallback)
BUDGET_CEILING = 1.4  # maximum 140% of base budget (legacy, used as fallback)

# Adaptive section cap thresholds — tiered budget allocation based on
# rolling 14-day mean relevance score per budget category.
# Replaces smooth linear interpolation with aggressive stepped scaling.
# Evidence: last 30 episodes show clear tier separation (2026-03-19).
ADAPTIVE_HIGH_THRESHOLD = 0.25   # mean ≥ 0.25 → 100% budget
ADAPTIVE_MID_THRESHOLD = 0.12    # mean 0.12-0.25 → 50% budget
# mean < 0.12 → 0% budget (hard-pruned)

# Token budgets per tier (attention-optimal allocation)
TIER_BUDGETS = {
    "minimal": {
        "total": 200,
        "decision_context": 0,
        "spotlight": 0,
        "related_tasks": 0,
        "completions": 0,
        "episodes": 0,
        "reasoning_scaffold": 0,
    },
    "standard": {
        "total": 600,
        "decision_context": 140,   # +40 from merged metrics
        "spotlight": 80,
        "related_tasks": 60,
        "completions": 30,
        "episodes": 80,            # +20: hierarchical episodes need room
        "reasoning_scaffold": 40,
    },
    "full": {
        "total": 1000,
        "decision_context": 230,   # +80 from merged metrics
        "spotlight": 120,
        "related_tasks": 100,
        "completions": 50,
        "episodes": 150,           # +30: hierarchical episodes need room
        "reasoning_scaffold": 60,
    },
}

RECENCY_BOOST_EPISODES = 5  # last N episodes get up to 3x weight in budget adjustment


def load_relevance_weights(min_episodes=MIN_EPISODES_FOR_ADJUSTMENT, days=14):
    """Load per-section relevance scores and convert to adaptive budget scaling factors.

    Reads aggregated context_relevance data and maps per-section mean scores
    to budget category scaling factors using tiered thresholds:
      - mean ≥ ADAPTIVE_HIGH_THRESHOLD (0.25): scale=1.0 (full budget)
      - ADAPTIVE_MID_THRESHOLD ≤ mean < ADAPTIVE_HIGH_THRESHOLD: scale=0.5 (half budget)
      - mean < ADAPTIVE_MID_THRESHOLD (0.12): scale=0.0 (hard-pruned)

    Uses exponential recency weighting so the last 5 episodes have ~3x
    influence — budget adjustments respond within 1-2 heartbeat cycles
    instead of waiting for the full 14-day window to rotate.

    Returns:
        Dict mapping budget keys to scaling factors, or empty dict if
        insufficient episode data exists.
    """
    try:
        from clarvis.cognition.context_relevance import aggregate_relevance
        agg = aggregate_relevance(days=days, recency_boost=RECENCY_BOOST_EPISODES)
    except Exception:
        logger.debug("Failed to load relevance weights", exc_info=True)
        return {}

    if agg.get("episodes", 0) < min_episodes:
        return {}

    per_section = agg.get("per_section_mean", {})
    if not per_section:
        return {}

    # Import here to avoid circular dependency
    from .dycp import _compute_dynamic_suppress

    weights = {}
    for budget_key, section_names in BUDGET_TO_SECTIONS.items():
        # Exclude dynamically hard-suppressed sections from averaging —
        # they're already suppressed at generation time and shouldn't drag
        # down the budget of the category they were folded into (e.g.,
        # meta_gradient=0.058 shouldn't penalize decision_context=0.300).
        dynamic_hard, _ = _compute_dynamic_suppress()
        active_scores = [
            per_section[s] for s in section_names
            if s in per_section and s not in dynamic_hard
        ]
        if not active_scores:
            continue
        mean_score = sum(active_scores) / len(active_scores)
        # Tiered adaptive scaling (replaces linear interpolation 2026-03-19)
        if mean_score >= ADAPTIVE_HIGH_THRESHOLD:
            scale = 1.0
        elif mean_score >= ADAPTIVE_MID_THRESHOLD:
            scale = 0.5
        else:
            scale = 0.0
        weights[budget_key] = scale

    return weights


# Per-section relevance weights for fine-grained char budget scaling inside
# the brief builders.  These map individual section names (e.g. "episodes",
# "reasoning", "working_memory") to a continuous 0.0–1.5 scale factor.
# Unlike load_relevance_weights() which bins into 0/0.5/1.0 per *category*,
# this uses smooth scaling so high-value sections expand and low-value ones
# shrink proportionally.

# Sections whose relevance consistently matters more than their raw score
# suggests.  These get a floor so they're never fully pruned.
_HIGH_VALUE_SECTIONS = frozenset([
    "episodes", "reasoning", "decision_context", "failure_avoidance",
])
_HIGH_VALUE_FLOOR = 0.6   # never scale below 60% for these

# Sections that are informational/low-signal — allowed to compress to zero.
_LOW_VALUE_SECTIONS = frozenset([
    "metrics", "completions", "synaptic",
])
_LOW_VALUE_CEILING = 0.8  # cap at 80% even if raw score is high


def load_section_relevance_weights(min_episodes=MIN_EPISODES_FOR_ADJUSTMENT, days=14):
    """Load per-section relevance scores as continuous scaling factors.

    Unlike load_relevance_weights() which returns category-level tiered scales,
    this returns per-section continuous weights suitable for scaling individual
    char budgets inside the brief builders.

    Scaling formula:
      - Raw mean score is normalised into [0, 1.5] range via:
        scale = min(1.5, max(0, score / 0.20))
        (0.20 is the median expected section relevance)
      - High-value sections get a floor of 0.6
      - Low-value sections get a ceiling of 0.8

    Returns:
        Dict mapping section names to float scaling factors, or empty dict
        if insufficient episode data exists.
    """
    try:
        from clarvis.cognition.context_relevance import aggregate_relevance
        agg = aggregate_relevance(days=days, recency_boost=RECENCY_BOOST_EPISODES)
    except Exception:
        logger.debug("Failed to load section relevance weights", exc_info=True)
        return {}

    if agg.get("episodes", 0) < min_episodes:
        return {}

    per_section = agg.get("per_section_mean", {})
    if not per_section:
        return {}

    median_expected = 0.20  # normalisation anchor
    weights = {}
    for section, score in per_section.items():
        scale = min(1.5, max(0.0, score / median_expected))
        if section in _HIGH_VALUE_SECTIONS:
            scale = max(scale, _HIGH_VALUE_FLOOR)
        elif section in _LOW_VALUE_SECTIONS:
            scale = min(scale, _LOW_VALUE_CEILING)
        weights[section] = round(scale, 3)

    return weights


def get_adjusted_budgets(tier="standard"):
    """Get tier budgets adjusted by adaptive relevance-based caps.

    Uses tiered scaling from load_relevance_weights():
      - High relevance (≥0.25): full budget
      - Mid relevance (0.12-0.25): 50% budget
      - Low relevance (<0.12): 0 tokens (hard-pruned from brief)

    When CLR's context_relevance sub-score is below 0.5 (raw < 0.25),
    high-relevance sections get a 20% boost to improve brief quality.

    Tokens freed by pruned/halved sections are redistributed to full-budget
    sections proportionally, keeping total token budget constant.

    Falls back to static TIER_BUDGETS when no relevance data exists.
    """
    base = TIER_BUDGETS.get(tier, TIER_BUDGETS["standard"]).copy()
    weights = load_relevance_weights()

    if not weights:
        return base

    # Check CLR context_relevance score for adaptive boost
    clr_boost = 1.0
    try:
        from clarvis.metrics.clr import get_latest_context_relevance
        cr = get_latest_context_relevance()
        cr_score = cr.get("score")
        if cr_score is not None and cr_score < 0.5:
            # Context relevance is weak — boost high-relevance sections by 20%
            # to increase signal density in the brief.
            clr_boost = 1.2
    except Exception:
        logger.debug("Failed to load CLR context_relevance", exc_info=True)

    total_base = sum(v for k, v in base.items() if k != "total" and v > 0)
    if total_base == 0:
        return base

    adjusted = {"total": base["total"]}
    for key, value in base.items():
        if key == "total" or value == 0:
            adjusted[key] = value
            continue
        scale = weights.get(key, 1.0)  # default 1.0 = keep full if no data
        # Apply CLR boost only to full-budget (high-relevance) sections
        if scale >= 1.0 and clr_boost > 1.0:
            scale *= clr_boost
        adjusted[key] = round(value * scale)

    # Redistribute freed tokens to full-budget sections (scale=1.0)
    total_adjusted = sum(v for k, v in adjusted.items() if k != "total")
    freed = total_base - total_adjusted
    if freed > 0:
        full_keys = [k for k in adjusted if k != "total" and weights.get(k, 1.0) >= 1.0 and adjusted[k] > 0]
        if full_keys:
            full_total = sum(adjusted[k] for k in full_keys)
            for k in full_keys:
                share = adjusted[k] / full_total if full_total > 0 else 1.0 / len(full_keys)
                adjusted[k] += round(freed * share)

    return adjusted
