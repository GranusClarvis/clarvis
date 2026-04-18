"""Tests for health_monitor.sh queue section regex — must only match canonical ## P0/P1 sections."""

import re


def _count_queue_caps(text: str) -> dict:
    """Replicates the Python snippet embedded in health_monitor.sh."""
    in_p0 = in_p1 = False
    p0 = p1 = 0
    for line in text.splitlines():
        if re.match(r"^## P0 —", line):
            in_p0, in_p1 = True, False
        elif re.match(r"^## P1 —", line):
            in_p0, in_p1 = False, True
        elif re.match(r"^## ", line):
            in_p0, in_p1 = False, False
        elif re.match(r"^\s*- \[ \] ", line):
            if in_p0:
                p0 += 1
            elif in_p1:
                p1 += 1
    return {"p0": p0, "p1": p1}


def test_canonical_sections_counted():
    queue = """\
## P0 — Current Sprint (2026-04-15)
- [ ] Task A
- [ ] Task B
- [x] Done task

## P1 — This Week
- [ ] Task C

## P2 — When Idle
- [ ] Task D
"""
    counts = _count_queue_caps(queue)
    assert counts["p0"] == 2, f"Expected P0=2, got {counts['p0']}"
    assert counts["p1"] == 1, f"Expected P1=1, got {counts['p1']}"


def test_p1_candidate_not_counted_as_p1():
    """A heading like '## P1 Candidate' must NOT activate the P1 counter."""
    queue = """\
## P0 — Current Sprint
- [ ] Real P0

## P1 — This Week
- [ ] Real P1

## P1 Candidate
- [ ] Should NOT count as P1

## P2 — When Idle
- [ ] P2 item
"""
    counts = _count_queue_caps(queue)
    assert counts["p0"] == 1
    assert counts["p1"] == 1, f"P1 Candidate items leaked into P1 count: {counts['p1']}"


def test_p0_prefixed_heading_not_counted():
    """'## P0-Extended' should not activate P0 counter."""
    queue = """\
## P0 — Current Sprint
- [ ] Real P0

## P0-Extended Review
- [ ] Should NOT count

## P1 — This Week
- [ ] Real P1
"""
    counts = _count_queue_caps(queue)
    assert counts["p0"] == 1
    assert counts["p1"] == 1


def test_subsections_within_p1_still_counted():
    """### subsections under ## P1 should still count their items."""
    queue = """\
## P1 — This Week

### Maintenance
- [ ] Task A

### Audit Follow-ups
- [ ] Task B
- [ ] Task C
"""
    counts = _count_queue_caps(queue)
    assert counts["p1"] == 3


def test_empty_queue():
    counts = _count_queue_caps("# Evolution Queue\n\nNothing here.\n")
    assert counts == {"p0": 0, "p1": 0}
