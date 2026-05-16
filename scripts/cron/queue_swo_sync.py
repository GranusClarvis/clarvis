#!/usr/bin/env python3
"""Sync SWO_TRACKER.md table rows into QUEUE.md (and archive completed ones).

System cron entry (Sunday 05:25 CET, between schedule audit at 05:24 and
cleanup at 05:30):

    25 5 * * 0 cd /home/agent/.openclaw/workspace && \\
        python3 scripts/cron/queue_swo_sync.py >> memory/cron/queue_swo_sync.log 2>&1

The heartbeat selector only sees ``- [ ]`` / ``- [x]`` task rows in
``memory/evolution/QUEUE.md``. SWO Track A/B items and security findings live
in ``memory/evolution/SWO_TRACKER.md`` and have historically drifted out of
QUEUE.md (see ``swo_blind_spot_audit_2026-05-14.md``). This job closes the
loop both ways:

  Forward:   tracker tagged ``P0``/``P1`` and not DONE   -> append to QUEUE.md
  Inverse:   tracker DONE / ``✅`` / MERGED               -> archive via
             ``clarvis.queue.writer.archive_completed()``

A "tag" is a bracketed token like ``[SWO_V2_PLAYER_SPRITE_ALIASING]``. The
script only considers tags found inside markdown table rows in the tracker.
It also considers the cozy-polish bullet sub-list (``"Cozy polish follow-ups
(filed in QUEUE.md ..."``) so the per-tag follow-ups are not missed even
though they are not in a table.

Usage:
    python3 scripts/cron/queue_swo_sync.py            # apply (idempotent)
    python3 scripts/cron/queue_swo_sync.py --dry-run  # print diff only
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_WORKSPACE = Path(
    os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
)

DEFAULT_TRACKER = _WORKSPACE / "memory" / "evolution" / "SWO_TRACKER.md"
DEFAULT_QUEUE = _WORKSPACE / "memory" / "evolution" / "QUEUE.md"

# Section the script appends to when QUEUE.md is missing a tracker tag.
APPEND_HEADING_RE = re.compile(
    r"^####\s+V2\s+—\s+De-Slop Polish.*$", re.IGNORECASE
)
APPEND_HEADING_FALLBACK_RE = re.compile(
    r"^###\s+Star Sanctuary\s*—.*$", re.IGNORECASE
)

# Bracketed tag — uppercase identifier with optional digits and underscores.
# Excludes things like ``[ ]``, ``[x]``, ``[UNVERIFIED]`` (the gate marker is
# always followed by a space in QUEUE rows so excluding it from the tag set
# would over-match; we filter known non-task labels below).
_TAG_RE = re.compile(r"\[([A-Z][A-Z0-9_]{2,})\]")

# Tags we never treat as task tags even when they appear in brackets.
_TAG_BLOCKLIST = {
    "UNVERIFIED", "DONE", "MERGED", "OPEN", "CLOSED", "HOLD", "TODO",
    "FIXED", "NEW", "P0", "P1", "P2", "P3",
    "HIGH", "MED", "LOW", "CRIT",
    "BANNER", "RESET", "DEFERRED",
}

# Status tokens we treat as "completed" when checking the inverse path.
_DONE_TOKENS = ("DONE", "MERGED", "FIXED", "✅", "RESOLVED", "CLOSED", "SHIPPED")

# Tokens whose presence on a row excludes it from the actionable set.
# (Operator-gated rows are not autonomous-eligible; DEFERRED is by design out.)
_EXCLUDE_TOKENS = ("DEFERRED", "FROZEN", "OPERATOR", "⏸", "ARCHIVAL", "RETIRED")


@dataclass(frozen=True)
class TrackerRow:
    """A single actionable row extracted from SWO_TRACKER.md."""
    tag: str
    priority: str
    title: str          # whatever text we have for the row (post-tag)
    status: str         # raw status cell text (may be empty)
    is_done: bool
    source_line: int


def _row_is_done(status_text: str, title_text: str) -> bool:
    blob = f"{status_text} {title_text}".upper()
    return any(t.upper() in blob for t in _DONE_TOKENS)


def _row_priority(cells: list[str]) -> str | None:
    """Pick a priority token from any of the cells.

    Returns None when no explicit ``P0``/``P1``/``P2``/``P3`` token is
    present. The script only treats P0/P1 rows as actionable, so a missing
    priority cell means "skip this row" (intentional: section-level priority
    headings live above tables in tracker prose and we don't infer them).
    """
    joined = " ".join(cells).upper()
    for tok in ("P0", "P1", "P2", "P3"):
        if re.search(rf"\b{tok}\b", joined):
            return tok
    return None


def _extract_tags(text: str) -> list[str]:
    tags = []
    for m in _TAG_RE.finditer(text):
        tag = m.group(1)
        if tag in _TAG_BLOCKLIST:
            continue
        tags.append(tag)
    return tags


def _strip_md(text: str) -> str:
    """Light markdown strip for clean-er title text."""
    return text.replace("`", "").replace("**", "").strip()


def parse_tracker(text: str) -> list[TrackerRow]:
    """Parse SWO_TRACKER.md into a list of TrackerRow objects.

    We treat every markdown table row that contains at least one valid tag
    as a candidate. The cozy-polish bullet sub-list is also picked up because
    each bullet starts with a tag and includes ``(P1)`` / ``(P2)`` markers.
    """
    rows: list[TrackerRow] = []
    seen_tags: set[str] = set()

    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        # Skip separator rows like ``|---|---|---|``
        if re.match(r"^\|\s*-+\s*\|", stripped):
            continue
        # Skip strikethrough rows (``~~[TAG]~~`` -> retired).
        if "~~" in stripped:
            continue

        cells: list[str] | None = None
        if stripped.startswith("|") and stripped.count("|") >= 3:
            # Markdown table row
            cells = [c.strip() for c in stripped.strip("|").split("|")]
        elif stripped.startswith("- ") and "[SWO_" in stripped:
            # Bullet sub-list (e.g. cozy-polish follow-ups).
            cells = [stripped[2:]]
        else:
            continue

        tags = _extract_tags(" ".join(cells))
        if not tags:
            continue

        # The first valid tag is treated as the row's primary tag.
        primary = tags[0]
        if primary in seen_tags:
            continue
        seen_tags.add(primary)

        status_text = cells[-1] if len(cells) > 1 else ""
        title_text = " ".join(c for c in cells if c)

        # Exclude rows whose status cell clearly says deferred/frozen/operator-gated.
        # We only look at the status (last cell) to avoid false positives from
        # body text — e.g. "operator's local hour" inside an acceptance summary
        # is not an operator-gated row.
        status_upper = status_text.upper()
        if any(tok.upper() in status_upper for tok in _EXCLUDE_TOKENS):
            continue

        priority = _row_priority(cells)
        is_done = _row_is_done(status_text, title_text)

        rows.append(
            TrackerRow(
                tag=primary,
                priority=priority or "",
                title=_strip_md(title_text),
                status=_strip_md(status_text),
                is_done=is_done,
                source_line=line_no,
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# QUEUE.md inspection                                                          #
# --------------------------------------------------------------------------- #

_TASK_ROW_RE = re.compile(r"^\s*-\s+\[[ xX~\-]\]\s")


def queue_task_tags(queue_text: str) -> set[str]:
    """Return the set of tags present as a *primary* tag in a QUEUE.md task row.

    A primary tag is the first ``[FOO_BAR]`` token on a task row. We avoid
    counting cross-references (a CLARVIS task body mentioning ``[SWO_V2_*]``
    as an example should not look like that tag is already queued).
    """
    out: set[str] = set()
    for line in queue_text.splitlines():
        if not _TASK_ROW_RE.match(line):
            continue
        # Skip the leading checkbox + optional ``[UNVERIFIED]`` gate marker
        # before grabbing the first tag.
        body = _TASK_ROW_RE.sub("", line, count=1)
        body = re.sub(r"^(\[UNVERIFIED\]|\[UNVERIFIED_\d+\])\s+", "", body)
        tags = _extract_tags(body)
        if tags:
            out.add(tags[0])
    return out


def queue_open_rows_by_tag(queue_text: str) -> dict[str, int]:
    """Return ``{tag: line_no}`` for every open ``- [ ]`` row (1-indexed)."""
    out: dict[str, int] = {}
    for idx, line in enumerate(queue_text.splitlines(), start=1):
        if not re.match(r"^\s*-\s+\[\s\]\s", line):
            continue
        body = re.sub(r"^\s*-\s+\[\s\]\s", "", line, count=1)
        body = re.sub(r"^(\[UNVERIFIED\]|\[UNVERIFIED_\d+\])\s+", "", body)
        tags = _extract_tags(body)
        if tags and tags[0] not in out:
            out[tags[0]] = idx
    return out


# --------------------------------------------------------------------------- #
# Diff + apply                                                                 #
# --------------------------------------------------------------------------- #

@dataclass
class SyncPlan:
    to_append: list[TrackerRow]
    to_archive: list[tuple[str, int]]   # (tag, line_no in queue)

    def is_noop(self) -> bool:
        return not self.to_append and not self.to_archive


def build_plan(tracker_rows: list[TrackerRow], queue_text: str) -> SyncPlan:
    queued = queue_task_tags(queue_text)
    open_by_tag = queue_open_rows_by_tag(queue_text)

    append: list[TrackerRow] = []
    archive: list[tuple[str, int]] = []

    for row in tracker_rows:
        if row.is_done:
            # Inverse: if the tracker says done, we want the queue row archived.
            if row.tag in open_by_tag:
                archive.append((row.tag, open_by_tag[row.tag]))
            continue
        # Forward: actionable tracker row that's not yet visible to QUEUE.md.
        # Include P0/P1 (primary heartbeat-eligible) and P2 (cozy-polish style
        # followups the tracker explicitly tagged P1/P2). Skip rows with no
        # explicit priority — they're usually section headers or PR-list rows.
        if row.priority not in ("P0", "P1", "P2"):
            continue
        if row.tag in queued:
            continue
        append.append(row)

    return SyncPlan(to_append=append, to_archive=archive)


def _format_append_line(row: TrackerRow) -> str:
    """Format a tracker row as a QUEUE.md task line."""
    return (
        f"- [ ] [UNVERIFIED] **[{row.tag}]** ({row.priority}, from SWO_TRACKER.md) "
        f"{row.title} (PROJECT:SWO) (auto-synced)"
    )


def _find_insertion_index(queue_lines: list[str]) -> int:
    """Pick a sensible insertion index in QUEUE.md.

    Prefer the De-Slop Polish (Track B) subheading; fall back to the Star
    Sanctuary section; fall back to end-of-file.
    """
    for primary_re in (APPEND_HEADING_RE, APPEND_HEADING_FALLBACK_RE):
        for idx, line in enumerate(queue_lines):
            if primary_re.match(line):
                # Insert just before the next top-level heading or section break.
                for j in range(idx + 1, len(queue_lines)):
                    nxt = queue_lines[j]
                    if nxt.startswith("## ") or nxt.startswith("### ") or nxt.startswith("#### "):
                        return j
                return len(queue_lines)
    return len(queue_lines)


def apply_plan(plan: SyncPlan, queue_path: Path) -> tuple[int, int]:
    """Apply the plan to QUEUE.md (forward path) + archive completed rows.

    Returns ``(appended, archived)`` counts.
    """
    appended = 0
    archived = 0

    # Forward path: append new rows.
    if plan.to_append:
        queue_lines = queue_path.read_text(encoding="utf-8").splitlines()
        insert_at = _find_insertion_index(queue_lines)
        new_lines = [_format_append_line(r) for r in plan.to_append]
        # Insert with a blank line on either side for cleanliness.
        prefix = [""] if insert_at > 0 and queue_lines[insert_at - 1] != "" else []
        suffix = [""]
        queue_lines = (
            queue_lines[:insert_at]
            + prefix
            + new_lines
            + suffix
            + queue_lines[insert_at:]
        )
        queue_path.write_text("\n".join(queue_lines) + "\n", encoding="utf-8")
        appended = len(new_lines)

    # Inverse path: flip [ ] -> [x] for done tracker tags, then archive.
    if plan.to_archive:
        text = queue_path.read_text(encoding="utf-8")
        out_lines: list[str] = []
        archive_tags = {tag for tag, _ in plan.to_archive}
        for line in text.splitlines():
            m = re.match(r"^(\s*)- \[ \] (.*)$", line)
            if m and any(f"[{tag}]" in m.group(2) for tag in archive_tags):
                out_lines.append(
                    f"{m.group(1)}- [x] {m.group(2)} (auto-synced from SWO_TRACKER DONE)"
                )
            else:
                out_lines.append(line)
        queue_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        try:
            from clarvis.queue.writer import archive_completed
            archived = archive_completed()
        except Exception as e:  # pragma: no cover — defensive
            print(f"[queue_swo_sync] archive_completed failed: {e}", file=sys.stderr)
            archived = 0

    return appended, archived


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def _render_diff(plan: SyncPlan) -> str:
    parts: list[str] = []
    parts.append(
        f"[queue_swo_sync] forward: {len(plan.to_append)} tracker rows missing"
        f" from QUEUE.md"
    )
    for row in plan.to_append:
        parts.append(f"  + [{row.tag}] ({row.priority}) {row.title[:80]}")
    parts.append(
        f"[queue_swo_sync] inverse: {len(plan.to_archive)} queue rows whose"
        f" tracker is DONE"
    )
    for tag, ln in plan.to_archive:
        parts.append(f"  ✓ [{tag}] queue line {ln} -> archive")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync SWO_TRACKER -> QUEUE.md")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the diff, do not write.")
    parser.add_argument("--tracker", type=Path, default=DEFAULT_TRACKER)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    args = parser.parse_args(argv)

    if not args.tracker.exists():
        print(f"[queue_swo_sync] tracker not found: {args.tracker}", file=sys.stderr)
        return 2
    if not args.queue.exists():
        print(f"[queue_swo_sync] queue not found: {args.queue}", file=sys.stderr)
        return 2

    tracker_rows = parse_tracker(args.tracker.read_text(encoding="utf-8"))
    queue_text = args.queue.read_text(encoding="utf-8")
    plan = build_plan(tracker_rows, queue_text)

    print(_render_diff(plan))

    if args.dry_run or plan.is_noop():
        return 0

    appended, archived = apply_plan(plan, args.queue)
    print(f"[queue_swo_sync] wrote: appended={appended} archived={archived}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
