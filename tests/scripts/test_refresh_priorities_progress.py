"""Regression tests for compute_queue_progress active-scope filtering.

The legacy implementation counted every checkbox in QUEUE.md, including those in
retired/deferred/archive subsections and in non-priority top-level blocks
(``## NEW ITEMS``, ``## Partial Items``, ``## Research Sessions``). That
inflated ``brain.get_goals()`` progress with historical debris. The current
implementation restricts counting to active P0/P1/P2 task scopes only.
"""

from clarvis._script_loader import load as _load_script

refresh_priorities = _load_script("refresh_priorities", "hooks")
compute_queue_progress = refresh_priorities.compute_queue_progress


def test_active_p0_p1_p2_counted():
    text = """# Queue

## P0 — Current Sprint

### Bugs

- [ ] open p0 task
- [x] done p0 task

## P1 — This Week

### Active feature

- [~] partial p1 task
- [ ] open p1 task

## P2 — When Idle

### Misc

- [ ] open p2 task
"""
    result = compute_queue_progress(text)
    assert result["done"] == 1
    assert result["partial"] == 1
    assert result["open"] == 3
    assert result["total"] == 5
    assert result["progress"] == int((1 + 0.5) / 5 * 100)


def test_retired_subsection_excluded():
    text = """## P1 — This Week

### Active feature

- [ ] active item

#### Retired / Deferred Items

- [ ] retired item should not count
- [x] retired done should not count
- [~] retired partial should not count

### Another active feature

- [x] another done
"""
    result = compute_queue_progress(text)
    assert result["done"] == 1
    assert result["partial"] == 0
    assert result["open"] == 1
    assert result["total"] == 2


def test_deferred_and_archive_subsections_excluded():
    text = """## P2 — When Idle

### Active

- [ ] live p2

### Sanctuary Asset Batches — RETIRED 2026-04-25, V3 mapping DEFERRED 2026-04-26

- [ ] retired-archive item

### Phase 13 Follow-ups (P2, archived)

- [ ] archived item

### Resumed active work

- [ ] resumes here
"""
    result = compute_queue_progress(text)
    assert result["open"] == 2
    assert result["total"] == 2


def test_top_level_non_priority_blocks_excluded():
    text = """## P0 — Current Sprint

- [ ] active p0

## NEW ITEMS (2026-04-15 evolution scan)

- [ ] new triage item
- [x] new done item

## Partial Items (tracked, not actively worked)

- [~] partial tracked

## Research Sessions

- [ ] reference link
"""
    result = compute_queue_progress(text)
    assert result["done"] == 0
    assert result["partial"] == 0
    assert result["open"] == 1
    assert result["total"] == 1


def test_strikethrough_items_skipped():
    text = """## P1 — This Week

### Active

- [x] ~~[SWO_RETIRED_FEATURE]~~ → DONE retired in place
- [ ] real open item
- [x] real done item
"""
    result = compute_queue_progress(text)
    assert result["done"] == 1
    assert result["open"] == 1
    assert result["total"] == 2


def test_empty_queue_returns_zero_progress():
    result = compute_queue_progress("")
    assert result == {
        "progress": 0,
        "done": 0,
        "partial": 0,
        "open": 0,
        "total": 0,
        "ratio_done": 0.0,
        "ratio_active": 0.0,
    }


def test_mixed_active_retired_inflation_regression():
    """Regression: with mixed active + retired, progress must reflect active only.

    Legacy bug: 1 active-open + 5 retired-done would show progress=83% (5/6).
    Fixed: progress=0% (0 of 1 active items done).
    """
    text = """## P1 — This Week

### Active work

- [ ] one active open task

#### Retired / Deferred Items

- [x] historical done 1
- [x] historical done 2
- [x] historical done 3
- [x] historical done 4
- [x] historical done 5
"""
    result = compute_queue_progress(text)
    assert result["total"] == 1
    assert result["done"] == 0
    assert result["open"] == 1
    assert result["progress"] == 0


def test_real_queue_sample_does_not_count_retired():
    """End-to-end style: feed the actual QUEUE.md and assert that retired
    items in the well-known ``#### Retired / Deferred Items`` block under P1
    are not counted. We don't pin exact totals (the file moves), but we
    assert the count is strictly less than a naive whole-file count."""
    from pathlib import Path

    queue_path = (
        Path(__file__).resolve().parent.parent.parent
        / "memory"
        / "evolution"
        / "QUEUE.md"
    )
    if not queue_path.exists():
        return  # skip silently — environment without workspace data

    text = queue_path.read_text()
    scoped = compute_queue_progress(text)

    import re

    naive_total = sum(
        1 for line in text.splitlines() if re.match(r"^\s*- \[[ ~x]\]", line)
    )
    assert scoped["total"] < naive_total, (
        f"active-scope total ({scoped['total']}) must be strictly less than "
        f"naive whole-file total ({naive_total})"
    )
