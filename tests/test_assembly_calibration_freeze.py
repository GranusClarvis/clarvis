"""Assembly calibration freeze tests — prevent regressions from fork merges.

These tests pin the tuned constants in clarvis/context/assembly.py that were
calibrated using 14-day per-section relevance data (2026-03-15). Any fork
merge that changes these values will break these tests, forcing an explicit
review of whether the new values are backed by evidence.

If you need to update a constant: update the test AND add a comment in
assembly.py explaining why the new value is better (link data/evidence).
"""

import pytest


# ---------------------------------------------------------------------------
# §1  DyCP threshold freeze — these control what gets pruned
# ---------------------------------------------------------------------------

def test_dycp_min_containment_frozen():
    from clarvis.context.assembly import DYCP_MIN_CONTAINMENT
    assert DYCP_MIN_CONTAINMENT == 0.08, (
        f"DYCP_MIN_CONTAINMENT changed to {DYCP_MIN_CONTAINMENT} — "
        "raised to 0.08 on 2026-03-18 (stricter task-overlap threshold)."
    )


def test_dycp_historical_floor_frozen():
    from clarvis.context.assembly import DYCP_HISTORICAL_FLOOR
    assert DYCP_HISTORICAL_FLOOR == 0.15, (
        f"DYCP_HISTORICAL_FLOOR changed to {DYCP_HISTORICAL_FLOOR} — "
        "lowered to 0.15 on 2026-03-19: 0.20 was pruning moderately useful sections."
    )


def test_dycp_zero_overlap_ceiling_frozen():
    from clarvis.context.assembly import DYCP_ZERO_OVERLAP_CEILING
    assert DYCP_ZERO_OVERLAP_CEILING == 0.15, (
        f"DYCP_ZERO_OVERLAP_CEILING changed to {DYCP_ZERO_OVERLAP_CEILING} — "
        "lowered to 0.15 on 2026-03-19: borderline sections (0.15-0.20) are useful."
    )


# ---------------------------------------------------------------------------
# §2  Default-suppress list freeze — sections suppressed before generation
# ---------------------------------------------------------------------------

EXPECTED_HARD_SUPPRESS = frozenset({
    "meta_gradient",
    "brain_goals",
    "metrics",
    "synaptic",
})

EXPECTED_DEFAULT_SUPPRESS = frozenset({
    "world_model",
    "gwt_broadcast",
    "introspection",
})


def test_hard_suppress_set_frozen():
    from clarvis.context.assembly import HARD_SUPPRESS
    assert HARD_SUPPRESS == EXPECTED_HARD_SUPPRESS, (
        f"HARD_SUPPRESS changed.\n"
        f"  Added: {HARD_SUPPRESS - EXPECTED_HARD_SUPPRESS}\n"
        f"  Removed: {EXPECTED_HARD_SUPPRESS - HARD_SUPPRESS}\n"
        "Bottom-5 noise sections (mean<0.12) — update with evidence only."
    )


def test_default_suppress_set_frozen():
    from clarvis.context.assembly import DYCP_DEFAULT_SUPPRESS
    assert DYCP_DEFAULT_SUPPRESS == EXPECTED_DEFAULT_SUPPRESS, (
        f"DYCP_DEFAULT_SUPPRESS changed.\n"
        f"  Added: {DYCP_DEFAULT_SUPPRESS - EXPECTED_DEFAULT_SUPPRESS}\n"
        f"  Removed: {EXPECTED_DEFAULT_SUPPRESS - DYCP_DEFAULT_SUPPRESS}\n"
        "Soft-suppressed (mean 0.12-0.13) — update with evidence only."
    )


def test_default_suppress_containment_override_frozen():
    from clarvis.context.assembly import DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE
    assert DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE == 0.10


# ---------------------------------------------------------------------------
# §3  Protected sections freeze — these must never be pruned
# ---------------------------------------------------------------------------

EXPECTED_PROTECTED = frozenset({
    "decision_context", "reasoning", "knowledge", "related_tasks",
    "episodes", "completions",
})


def test_protected_sections_frozen():
    from clarvis.context.assembly import DYCP_PROTECTED_SECTIONS
    assert DYCP_PROTECTED_SECTIONS == EXPECTED_PROTECTED, (
        f"DYCP_PROTECTED_SECTIONS changed.\n"
        f"  Added: {DYCP_PROTECTED_SECTIONS - EXPECTED_PROTECTED}\n"
        f"  Removed: {EXPECTED_PROTECTED - DYCP_PROTECTED_SECTIONS}\n"
        "Protected sections must never be pruned — change with extreme care."
    )


# ---------------------------------------------------------------------------
# §4  Budget structure freeze — tier allocations
# ---------------------------------------------------------------------------

def test_tier_budgets_keys_stable():
    from clarvis.context.assembly import TIER_BUDGETS
    assert set(TIER_BUDGETS.keys()) == {"minimal", "standard", "full"}


def test_standard_tier_total_frozen():
    from clarvis.context.assembly import TIER_BUDGETS
    assert TIER_BUDGETS["standard"]["total"] == 600


def test_full_tier_total_frozen():
    from clarvis.context.assembly import TIER_BUDGETS
    assert TIER_BUDGETS["full"]["total"] == 1000


def test_budget_section_keys_stable():
    """All tiers have the same section keys."""
    from clarvis.context.assembly import TIER_BUDGETS
    keys = None
    for tier, budget in TIER_BUDGETS.items():
        tier_keys = set(budget.keys())
        if keys is None:
            keys = tier_keys
        else:
            assert tier_keys == keys, f"Tier '{tier}' has different keys: {tier_keys ^ keys}"


def test_standard_tier_allocations_frozen():
    """Pin the standard tier allocations that were tuned for context quality."""
    from clarvis.context.assembly import TIER_BUDGETS
    std = TIER_BUDGETS["standard"]
    expected = {
        "total": 600,
        "decision_context": 140,   # +40 from merged metrics (2026-03-18)
        "spotlight": 80,
        "related_tasks": 60,
        "completions": 30,         # reduced 2026-03-24
        "episodes": 80,            # increased 2026-03-24
        "reasoning_scaffold": 40,
    }
    assert std == expected, (
        f"Standard tier budget changed — retuned 2026-03-18.\n"
        f"Diff: {set(std.items()) ^ set(expected.items())}"
    )


# ---------------------------------------------------------------------------
# §5  Budget adjustment parameters freeze
# ---------------------------------------------------------------------------

def test_budget_floor_ceiling_frozen():
    from clarvis.context.budgets import BUDGET_FLOOR, BUDGET_CEILING
    assert BUDGET_FLOOR == 0.4, f"BUDGET_FLOOR={BUDGET_FLOOR}, expected 0.4"
    assert BUDGET_CEILING == 1.4, f"BUDGET_CEILING={BUDGET_CEILING}, expected 1.4"


def test_adaptive_thresholds_frozen():
    """Pin the adaptive section cap thresholds (2026-03-19)."""
    from clarvis.context.budgets import ADAPTIVE_HIGH_THRESHOLD, ADAPTIVE_MID_THRESHOLD
    assert ADAPTIVE_HIGH_THRESHOLD == 0.25, (
        f"ADAPTIVE_HIGH_THRESHOLD={ADAPTIVE_HIGH_THRESHOLD} — "
        "sections with mean ≥0.25 get full budget."
    )
    assert ADAPTIVE_MID_THRESHOLD == 0.12, (
        f"ADAPTIVE_MID_THRESHOLD={ADAPTIVE_MID_THRESHOLD} — "
        "sections with mean 0.12-0.25 get 50% budget, <0.12 get zero."
    )


def test_min_episodes_for_adjustment_frozen():
    from clarvis.context.budgets import MIN_EPISODES_FOR_ADJUSTMENT
    assert MIN_EPISODES_FOR_ADJUSTMENT == 5


# ---------------------------------------------------------------------------
# §6  Behavioral invariants — assembly logic contracts
# ---------------------------------------------------------------------------

def test_protected_sections_never_suppressed():
    """should_suppress_section returns False for all protected sections."""
    from clarvis.context.assembly import (
        should_suppress_section, DYCP_PROTECTED_SECTIONS
    )
    for section in DYCP_PROTECTED_SECTIONS:
        assert should_suppress_section(section, "any task text") is False


def test_suppressed_sections_return_true_without_task(monkeypatch):
    """Default-suppressed sections are suppressed when no task context given.

    Uses monkeypatch to ensure _compute_dynamic_suppress returns the static
    constants, since earlier tests may load context_relevance data that changes
    the dynamic computation.
    """
    import clarvis.context.dycp as dycp_mod
    from clarvis.context.dycp import (
        should_suppress_section, DYCP_DEFAULT_SUPPRESS, HARD_SUPPRESS
    )
    monkeypatch.setattr(dycp_mod, "_compute_dynamic_suppress",
                        lambda: (HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS))
    for section in DYCP_DEFAULT_SUPPRESS:
        assert should_suppress_section(section, "") is True
    for section in HARD_SUPPRESS:
        assert should_suppress_section(section, "") is True


def test_hard_suppress_ignores_task_containment(monkeypatch):
    """Hard-suppressed sections are always suppressed, even with matching task."""
    import clarvis.context.dycp as dycp_mod
    from clarvis.context.dycp import (
        should_suppress_section, HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS
    )
    monkeypatch.setattr(dycp_mod, "_compute_dynamic_suppress",
                        lambda: (HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS))
    # Use a task that contains the section name words — should still suppress
    for section in HARD_SUPPRESS:
        task = f"fix the {section.replace('_', ' ')} system completely"
        assert should_suppress_section(section, task) is True


def test_generate_tiered_brief_returns_string():
    """generate_tiered_brief returns a non-empty string for basic input."""
    from clarvis.context.assembly import generate_tiered_brief
    result = generate_tiered_brief("test task", tier="minimal")
    assert isinstance(result, str)


def test_budget_to_sections_covers_all_budget_keys():
    """Every non-total budget key has a section mapping."""
    from clarvis.context.budgets import BUDGET_TO_SECTIONS as _BUDGET_TO_SECTIONS, TIER_BUDGETS
    budget_keys = {k for k in TIER_BUDGETS["standard"] if k != "total"}
    mapped_keys = set(_BUDGET_TO_SECTIONS.keys())
    assert budget_keys == mapped_keys, (
        f"Budget/section mapping mismatch: "
        f"unmapped={budget_keys - mapped_keys}, orphan={mapped_keys - budget_keys}"
    )
