"""Lane autofill — auto-spawn refill tasks when active project lanes go empty.

Task: `[QUEUE_LANE_MINIMUM_AUTOFILL]`. When `lane_health` reports `in_queue == 0`
for an active project lane, do not just warn — also auto-spawn a
`[<LANE>_LANE_REFILL]` task that asks Claude Code to: (a) read the lane's status
doc (`memory/cron/<lane_lower>_phase*_status_*.md`, latest), (b) read the
lane's section header in QUEUE.md, (c) propose 2-3 concrete next-step items
with acceptance contracts, (d) write them to QUEUE.md.

Idempotent: if the previous refill task is still pending in QUEUE.md, this
scan does not stack a duplicate.

Wired into `scripts/cron/cron_report_morning.sh` after the lane-health
rendering block (already calls `runnable_view()`).
"""
from __future__ import annotations

import os
import re
from typing import Optional

from clarvis.queue.runnable import runnable_view
from clarvis.queue.writer import add_task, QUEUE_FILE


def _refill_tag(lane: str) -> str:
    return f"{lane.upper()}_LANE_REFILL"


def _refill_task_text(lane: str) -> str:
    """Compose the refill task body for a lane."""
    lane_u = lane.upper()
    lane_l = lane.lower()
    return (
        f"**[{_refill_tag(lane_u)}]** Lane `{lane_u}` is empty (in_queue==0) "
        f"but is in the active project set. Refill it: (a) read the latest "
        f"`memory/cron/{lane_l}_phase*_status_*.md` (or `memory/evolution/"
        f"{lane_l}_phase*_status_*.md`) for current phase context; (b) read "
        f"the `### {lane_u}` (or equivalent) section header in QUEUE.md for "
        f"lane conventions; (c) propose 2-3 concrete next-step items with "
        f"explicit acceptance contracts (file paths, test names, exit "
        f"conditions), each tagged `[{lane_u}_*]`; (d) write them to "
        f"QUEUE.md under the lane's section. Do not stack tasks beyond the "
        f"P1 cap. (PROJECT:{lane_u})"
    )


def _refill_already_pending(lane: str, queue_path: str = QUEUE_FILE) -> bool:
    """Return True if a `[<LANE>_LANE_REFILL]` is unchecked in QUEUE.md.

    Idempotency guard: a prior autofill scan may have already filed a refill
    that Claude Code has not yet picked up. Don't stack duplicates.
    """
    try:
        with open(queue_path) as f:
            content = f.read()
    except FileNotFoundError:
        return False
    tag = _refill_tag(lane)
    pattern = re.compile(
        r"^- \[ \].*\[" + re.escape(tag) + r"\]",
        re.MULTILINE,
    )
    return bool(pattern.search(content))


def autofill_empty_lanes(
    queue_path: str = QUEUE_FILE,
    source: str = "lane_autofill",
    priority: str = "P1",
) -> list[str]:
    """Run a single autofill scan. Return list of lanes that got a refill task.

    Acceptance contract (from QUEUE.md `[QUEUE_LANE_MINIMUM_AUTOFILL]`):
      - When both lanes are saturated, no autofill task spawns.
      - When one is empty, exactly one `[<LANE>_LANE_REFILL]` lands per scan.
      - Idempotent — does not stack if the previous refill is still pending.
    """
    view = runnable_view()
    spawned: list[str] = []
    for lh in view.lane_health:
        # `lane_health` is a list of dicts after `to_dict()`.
        in_q = lh.get("in_queue", 0)
        lane = lh.get("lane", "")
        if not lane:
            continue
        if in_q != 0:
            continue
        if _refill_already_pending(lane, queue_path=queue_path):
            continue
        task_text = _refill_task_text(lane)
        added = add_task(task_text, priority=priority, source=source)
        if added:
            spawned.append(lane.upper())
    return spawned


def main(argv=None) -> int:
    """CLI entry point. Prints lanes that got a refill task; exit 0 always.

    The morning report wires this in via subprocess; cron should never let
    autofill failure crash the report. Errors print to stderr and exit 0.
    """
    import sys
    try:
        spawned = autofill_empty_lanes()
    except Exception as e:  # noqa: BLE001 — never break the morning report
        print(f"[lane_autofill] error: {e}", file=sys.stderr)
        return 0
    if spawned:
        print(f"[lane_autofill] spawned refill tasks for: {', '.join(spawned)}")
    else:
        print("[lane_autofill] no empty lanes; nothing to spawn")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
