"""Queue runnable view — structured eligible/blocked breakdown.

The evening review and watchdog both need to answer a specific question that
plain `parse_queue()` and `ranked_eligible()` only answer in isolation:

    QUEUE.md says N tasks are pending — why is the engine returning M < N
    eligible tasks (or 0)? Which filter is dropping each blocked task?

`runnable_view()` reconciles QUEUE.md with sidecar state and emits one record
per task with a single canonical `block_reason`:

    eligible       — engine will consider it on the next heartbeat
    in_progress    — already running (sidecar state=running)
    succeeded      — sidecar says succeeded but checkbox is still [ ]
    deferred       — auto-deferred (max retries exceeded or operator)
    backoff        — failed and within skip_until window
    max_retries    — failed and attempts >= MAX_RETRIES (will auto-defer next call)
    other          — any state we couldn't bucket cleanly

The downstream prompt can then say "X eligible / Y total — Z blocked by
backoff, W by in_progress, V by succeeded-but-unchecked" and the operator/
LLM auditor can act on a specific lever instead of re-running probes.

CLI:

    python3 -m clarvis.queue.runnable             # text report
    python3 -m clarvis.queue.runnable --json      # JSON
    python3 -m clarvis.queue.runnable --digest    # one-line summary
    python3 -m clarvis.queue.runnable --top 5     # top 5 eligible by score
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from clarvis.queue.engine import (
    QueueEngine,
    parse_queue,
    MAX_RETRIES,
    DEFAULT_MAX_RETRIES,
)


@dataclass
class TaskBucket:
    tag: str
    text: str
    priority: str
    state: str
    block_reason: str        # eligible|in_progress|succeeded|deferred|backoff|max_retries|other
    score: Optional[float] = None
    attempts: int = 0
    last_run: Optional[str] = None
    failure_reason: Optional[str] = None
    skip_until: int = 0
    is_project: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunnableView:
    in_queue_total: int
    eligible_count: int
    blocked_count: int
    counts_by_reason: dict = field(default_factory=dict)   # block_reason -> count
    counts_by_priority: dict = field(default_factory=dict) # P0/P1/P2 -> count (eligible only)
    project_lane: Optional[str] = None
    project_eligible: int = 0
    project_in_queue: int = 0
    eligible_top: list[dict] = field(default_factory=list)
    blocked_samples: dict = field(default_factory=dict)    # block_reason -> [TaskBucket dicts]
    severity: str = "ok"                                    # ok|warn|critical
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _is_project_task(text: str, lane: str) -> bool:
    """Mirror heartbeat_preflight._is_project_task for offline reporting."""
    if not lane:
        return False
    lu = lane.upper()
    tu = text.upper()
    return (f"PROJECT:{lu}" in tu) or (f"({lu})" in tu) or (f"[{lu}" in tu)


def _classify(task: dict, now_epoch: float) -> str:
    """Return a canonical block_reason for a reconciled task dict."""
    state = task.get("state", "pending")
    if state == "running":
        return "in_progress"
    if state == "succeeded":
        return "succeeded"
    if state == "deferred":
        return "deferred"
    if state == "removed":
        return "other"
    if state == "failed":
        attempts = task.get("attempts", 0)
        max_r = MAX_RETRIES.get(task.get("priority", "P1"), DEFAULT_MAX_RETRIES)
        if attempts >= max_r:
            return "max_retries"
        skip_until = task.get("skip_until", 0)
        if skip_until and now_epoch < skip_until:
            return "backoff"
        return "eligible"  # failed-but-retryable, not in backoff
    if state == "pending":
        skip_until = task.get("skip_until", 0)
        if skip_until and now_epoch < skip_until:
            return "backoff"
        return "eligible"
    return "other"


def _sev_rank(s: str) -> int:
    return {"ok": 0, "warn": 1, "critical": 2}.get(s, 0)


def runnable_view(
    top_n: int = 5,
    samples_per_reason: int = 3,
    engine: Optional[QueueEngine] = None,
) -> RunnableView:
    """Produce a structured view of the queue's runnable surface.

    `top_n`: how many top eligible tasks (by score) to surface.
    `samples_per_reason`: how many blocked-task examples to include per reason.
    `engine`: optional QueueEngine override (tests). Defaults to a fresh instance
              pointed at the module-level QUEUE_FILE/SIDECAR_FILE.
    """
    eng = engine or QueueEngine()
    md_tasks, _sidecar = eng.reconcile()
    in_queue_total = len(md_tasks)
    project_lane = os.environ.get("CLARVIS_PROJECT_LANE", "").strip() or None
    now_epoch = time.time()

    eligible_score_map = {t["tag"]: t["score"] for t in eng.ranked_eligible()}

    buckets: list[TaskBucket] = []
    for t in md_tasks:
        reason = _classify(t, now_epoch)
        score = eligible_score_map.get(t["tag"]) if reason == "eligible" else None
        buckets.append(TaskBucket(
            tag=t["tag"],
            text=t["text"],
            priority=t.get("priority", "P2"),
            state=t.get("state", "pending"),
            block_reason=reason,
            score=score,
            attempts=t.get("attempts", 0),
            last_run=t.get("last_run"),
            failure_reason=t.get("failure_reason"),
            skip_until=int(t.get("skip_until", 0) or 0),
            is_project=bool(project_lane and _is_project_task(t.get("text", ""), project_lane)),
        ))

    counts_by_reason: dict[str, int] = {}
    counts_by_priority: dict[str, int] = {}
    for b in buckets:
        counts_by_reason[b.block_reason] = counts_by_reason.get(b.block_reason, 0) + 1
        if b.block_reason == "eligible":
            counts_by_priority[b.priority] = counts_by_priority.get(b.priority, 0) + 1

    eligible = [b for b in buckets if b.block_reason == "eligible"]
    eligible.sort(key=lambda b: (b.score or 0.0), reverse=True)
    eligible_top = [b.to_dict() for b in eligible[: max(0, top_n)]]

    blocked_samples: dict[str, list[dict]] = {}
    for reason in ("in_progress", "succeeded", "deferred", "backoff", "max_retries", "other"):
        items = [b for b in buckets if b.block_reason == reason]
        if items:
            blocked_samples[reason] = [b.to_dict() for b in items[:samples_per_reason]]

    project_eligible = sum(1 for b in eligible if b.is_project)
    project_in_queue = sum(1 for b in buckets if b.is_project)

    findings: list[str] = []
    severity = "ok"

    if in_queue_total > 0 and len(eligible) == 0:
        severity = "critical"
        findings.append(
            f"all {in_queue_total} tasks blocked — nothing eligible to run"
        )
    elif in_queue_total > 0 and len(eligible) / in_queue_total < 0.20:
        severity = max(severity, "warn", key=_sev_rank)
        findings.append(
            f"only {len(eligible)}/{in_queue_total} ({len(eligible)/in_queue_total:.0%}) "
            f"of in-queue tasks are eligible"
        )

    succ_unchecked = counts_by_reason.get("succeeded", 0)
    if succ_unchecked >= 3:
        severity = max(severity, "warn", key=_sev_rank)
        findings.append(
            f"{succ_unchecked} task(s) succeeded but checkbox still [ ] — "
            f"sidecar/QUEUE.md drift; archive_completed may be stalled"
        )

    if project_lane and project_in_queue > 0 and project_eligible == 0:
        severity = max(severity, "warn", key=_sev_rank)
        findings.append(
            f"project lane={project_lane} has {project_in_queue} task(s) in queue "
            f"but 0 eligible — project slots will fall back to general"
        )

    stuck_in_progress = counts_by_reason.get("in_progress", 0)
    if stuck_in_progress >= 2:
        severity = max(severity, "warn", key=_sev_rank)
        findings.append(
            f"{stuck_in_progress} task(s) marked in_progress (running) — "
            f"check for stuck heartbeats or mark_succeeded misses"
        )

    return RunnableView(
        in_queue_total=in_queue_total,
        eligible_count=len(eligible),
        blocked_count=in_queue_total - len(eligible),
        counts_by_reason=counts_by_reason,
        counts_by_priority=counts_by_priority,
        project_lane=project_lane,
        project_eligible=project_eligible,
        project_in_queue=project_in_queue,
        eligible_top=eligible_top,
        blocked_samples=blocked_samples,
        severity=severity,
        findings=findings,
    )


def format_view(view: RunnableView) -> str:
    """Human-readable text rendering for prompts and logs."""
    lines = [
        "# Queue Runnable View",
        f"Severity: {view.severity.upper()}",
        f"In QUEUE.md (unchecked): {view.in_queue_total}",
        f"Eligible (engine):       {view.eligible_count}",
        f"Blocked:                 {view.blocked_count}",
    ]
    if view.project_lane:
        lines.append(
            f"Project lane: {view.project_lane} — "
            f"{view.project_eligible} eligible / {view.project_in_queue} in queue"
        )

    if view.counts_by_reason:
        lines.extend(["", "## Block reasons"])
        for reason in (
            "eligible", "in_progress", "succeeded", "deferred",
            "backoff", "max_retries", "other",
        ):
            n = view.counts_by_reason.get(reason, 0)
            if n:
                lines.append(f"  {reason:14s} {n:3d}")

    if view.counts_by_priority:
        lines.extend(["", "## Eligible by priority"])
        for p in ("P0", "P1", "P2"):
            n = view.counts_by_priority.get(p, 0)
            if n:
                lines.append(f"  {p:3s} {n}")

    if view.eligible_top:
        lines.extend(["", "## Top eligible (score, priority, tag)"])
        for t in view.eligible_top:
            score = t.get("score")
            score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "?"
            text = (t.get("text") or "")[:90]
            lines.append(f"  {score_str}  {t.get('priority','?'):3s}  [{t.get('tag','?')}]  {text}")

    if view.blocked_samples:
        lines.extend(["", "## Blocked samples"])
        for reason, items in view.blocked_samples.items():
            lines.append(f"  ## {reason} ({len(items)} shown)")
            for t in items:
                detail = []
                if t.get("attempts"):
                    detail.append(f"attempts={t['attempts']}")
                if t.get("failure_reason"):
                    detail.append(f"failure={(t['failure_reason'] or '')[:60]}")
                if t.get("skip_until"):
                    detail.append(f"skip_until={t['skip_until']}")
                tail = " ".join(detail)
                text = (t.get("text") or "")[:80]
                lines.append(f"    [{t.get('tag','?')}] {text}  {tail}")

    if view.findings:
        lines.extend(["", "## Findings"])
        for f in view.findings:
            lines.append(f"  - {f}")

    return "\n".join(lines) + "\n"


def digest_summary(view: RunnableView) -> str:
    """One-line summary for digest_writer / watchdog."""
    parts = [
        f"queue runnable [{view.severity}]: "
        f"{view.eligible_count}/{view.in_queue_total} eligible"
    ]
    if view.counts_by_reason:
        blockers = []
        for reason in ("in_progress", "succeeded", "deferred", "backoff", "max_retries"):
            n = view.counts_by_reason.get(reason, 0)
            if n:
                blockers.append(f"{n} {reason}")
        if blockers:
            parts.append(", ".join(blockers))
    if view.project_lane and view.project_in_queue:
        parts.append(
            f"lane={view.project_lane}: {view.project_eligible}/{view.project_in_queue}"
        )
    if view.findings:
        parts.append("findings: " + "; ".join(view.findings[:2]))
    return ". ".join(parts) + "."


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Queue runnable view (eligible vs blocked)")
    p.add_argument("--json", action="store_true", help="emit JSON")
    p.add_argument("--digest", action="store_true", help="emit one-line digest summary")
    p.add_argument("--top", type=int, default=5, help="how many top eligible tasks to show")
    p.add_argument("--samples", type=int, default=3,
                   help="how many blocked-task samples per reason")
    args = p.parse_args(argv)

    view = runnable_view(top_n=args.top, samples_per_reason=args.samples)
    if args.json:
        print(json.dumps(view.to_dict(), default=str))
    elif args.digest:
        print(digest_summary(view))
    else:
        print(format_view(view))
    return {"ok": 0, "warn": 1, "critical": 2}.get(view.severity, 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
