#!/usr/bin/env python3
"""Pre-commit hook: reject orphan finding-style tags in memory/evolution/QUEUE.md.

Finding-style tags (`[BB_QA_*]`, `[SWO_V2_*]`, `[CLARVIS_*]`, `[BB_*]`, `[SWO_*]`)
must live inside a `- [ ]` / `- [x]` / `- [~]` / `- [-]` list-item row. The heartbeat
selector only reads list-item rows; orphan tags buried in section-body prose are
invisible to scheduling.

Modes
-----
- Default (pre-commit): if `memory/evolution/QUEUE.md` is in the staged diff,
  compare the staged blob against `HEAD` and fail (exit 1) on any *new* orphan
  tag introduced by the commit. Pre-existing orphans are tolerated so a fresh
  install does not block every commit.
- `--dry-run` / `--all`: scan the working-tree copy and print every orphan tag
  (exit 0). Used for retro-cleanup and the install-time audit.
- `--path PATH`: scan an arbitrary file (used by tests).

Install
-------
Symlink `.git/hooks/pre-commit` → this file (the `clarvis hooks install` CLI
shared with `pre_commit_queue_artifact_check.py` wires it up automatically).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

TARGET = "memory/evolution/QUEUE.md"

TAG_RE = re.compile(
    r"\[(?:BB_QA_[A-Z0-9_]+"
    r"|SWO_V2_[A-Z0-9_]+"
    r"|CLARVIS_[A-Z0-9_]+"
    r"|BB_[A-Z0-9_]+"
    r"|SWO_[A-Z0-9_]+)\]"
)

LIST_ITEM_RE = re.compile(r"^\s*-\s*\[[ xX~\-]\]\s")

CODE_FENCE_RE = re.compile(r"^\s*```")

Orphan = Tuple[int, str, List[str]]


def find_orphans(lines: Iterable[str]) -> List[Orphan]:
    """Return `[(line_no_1based, line, [tags]), ...]` for every line that
    contains a finding-style tag yet is not a `- [ ]` / `- [x]` task row.

    Lines inside fenced code blocks are skipped — example code is not
    schedulable text.
    """
    orphans: List[Orphan] = []
    in_code_fence = False
    for idx, raw in enumerate(lines, 1):
        line = raw.rstrip("\n")
        if CODE_FENCE_RE.match(line):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        tags = TAG_RE.findall(line)
        if not tags:
            continue
        if LIST_ITEM_RE.match(line):
            continue
        orphans.append((idx, line, tags))
    return orphans


def _run_git(args: List[str]) -> str:
    return subprocess.check_output(
        ["git", *args], stderr=subprocess.DEVNULL
    ).decode("utf-8", errors="replace")


def _is_queue_staged() -> bool:
    try:
        out = _run_git(["diff", "--cached", "--name-only"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return TARGET in out.splitlines()


def _read_blob(ref: str) -> List[str] | None:
    try:
        out = _run_git(["show", f"{ref}:{TARGET}"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.splitlines()


def _new_orphans(head_lines: List[str] | None, staged_lines: List[str]) -> List[Orphan]:
    """Return staged orphans whose (tag-set, normalized-text) pair is *not*
    already an orphan in HEAD. Anything pre-existing is tolerated."""
    staged = find_orphans(staged_lines)
    if head_lines is None:
        return staged
    head_keys = {
        (tuple(sorted(tags)), line.strip())
        for _, line, tags in find_orphans(head_lines)
    }
    return [
        (i, line, tags)
        for i, line, tags in staged
        if (tuple(sorted(tags)), line.strip()) not in head_keys
    ]


def _print_orphans(orphans: List[Orphan], stream=sys.stderr) -> None:
    for i, line, tags in orphans:
        snippet = line if len(line) <= 160 else line[:157] + "..."
        print(f"  L{i}: tags={tags} -> {snippet}", file=stream)


def _resolve_workspace_target() -> Path:
    cwd_target = Path(TARGET)
    if cwd_target.exists():
        return cwd_target
    # Fallback: walk up from this file (scripts/hooks/pre_commit_queue_orphan_tags.py)
    here = Path(__file__).resolve()
    root = here.parent.parent.parent
    return root / TARGET


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pre_commit_queue_orphan_tags",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Scan an arbitrary file (overrides hook + dry-run modes).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan the working-tree copy and report orphans without failing.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Pre-commit mode but compare against an empty baseline — every "
            "orphan in the staged file fails. Use after a retro-cleanup pass."
        ),
    )
    args = parser.parse_args(argv)

    if args.path is not None:
        lines = args.path.read_text(encoding="utf-8").splitlines()
        orphans = find_orphans(lines)
        if not orphans:
            return 0
        print(
            f"queue-orphan-tags: {len(orphans)} orphan tag line(s) in {args.path}",
            file=sys.stderr,
        )
        _print_orphans(orphans)
        return 0 if args.dry_run else 1

    if args.dry_run:
        target = _resolve_workspace_target()
        if not target.exists():
            print(f"queue-orphan-tags: {target} not found", file=sys.stderr)
            return 0
        lines = target.read_text(encoding="utf-8").splitlines()
        orphans = find_orphans(lines)
        print(
            f"queue-orphan-tags: dry-run found {len(orphans)} orphan tag line(s) in {target}",
            file=sys.stderr,
        )
        _print_orphans(orphans)
        return 0

    # Pre-commit mode.
    if not _is_queue_staged():
        return 0
    staged_lines = _read_blob(":0")  # index
    if staged_lines is None:
        return 0
    head_lines = None if args.all else _read_blob("HEAD")

    new_orphans = _new_orphans(head_lines, staged_lines)
    if not new_orphans:
        return 0

    print(
        f"queue-orphan-tags: {len(new_orphans)} NEW orphan tag line(s) introduced "
        f"in {TARGET} (compared to HEAD):",
        file=sys.stderr,
    )
    _print_orphans(new_orphans)
    print(
        "\nFinding-style tags must live inside a `- [ ]` / `- [x]` row so the "
        "heartbeat selector can see them. Either move the tag into a task row "
        "or strip the brackets to make it free prose.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
