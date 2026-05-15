#!/usr/bin/env python3
"""Pre-commit hook: reject `[x] [UNVERIFIED]` closures whose referenced
artifacts do not exist on disk.

Rationale
---------
The closure path bypasses `clarvis.queue.writer.archive_completed()` whenever
an evolution-scan Claude flips a row from `- [ ]` to `- [x] [UNVERIFIED]` via
a direct `Edit` on `memory/evolution/QUEUE.md`. The writer's artifact-existence
guard never runs, so prose-only "shipped" closures slip through. This hook
moves the guard to `git commit` so the bypass is no longer possible.

Behaviour
---------
- Compare the staged copy of `memory/evolution/QUEUE.md` against `HEAD` and
  consider every row that is `[x] [UNVERIFIED]` in the staged version but was
  *not* the same `[x] [UNVERIFIED]` row in HEAD ("newly checked").
- For each newly-checked row, regex-extract paths matching:
    docs/**/*.md
    monitoring/**/*.md
    memory/**/*.md
    scripts/**/*.py | scripts/**/*.sh
    tests/**/*.py
  Paths inside backticks are the primary source; bare paths matching the
  patterns also count.
- `ls`-check each path. Any missing path -> exit 1 (reject the commit) with a
  human-readable failure summary.
- Rows containing a `(PROJECT:X)` marker matching a lane listed in the
  `CLARVIS_ACTIVE_PROJECT_LANES` env var (comma- or space-separated) are
  exempt — active project lanes own their own delivery cadence.

Modes
-----
- Default (pre-commit): diff staged vs HEAD; exit 1 on missing artifacts.
- `--dry-run`: scan the working-tree QUEUE.md *without* comparing to HEAD,
  print every artifact-missing newly-checked row, exit 0.
- `--path PATH`: scan an arbitrary file (used by tests). Combine with
  `--head HEAD_PATH` to compare against a baseline file.

Install
-------
The `clarvis hooks install` CLI symlinks `.git/hooks/pre-commit` to this
script. Fresh `git init` clones get it wired up automatically via
`scripts/infra/setup.sh`.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Set, Tuple

TARGET = "memory/evolution/QUEUE.md"

# Rows that are `[x] [UNVERIFIED]`.
CLOSED_UNVERIFIED_RE = re.compile(
    r"^\s*-\s*\[[xX]\]\s*\[UNVERIFIED\]"
)

# Paths in QUEUE rows are typically backtick-wrapped (`scripts/foo.py`).
BACKTICK_PATH_RE = re.compile(r"`([^`\n]+)`")

# Project marker, e.g. (PROJECT:CLARVIS), (PROJECT:SWO).
PROJECT_MARKER_RE = re.compile(r"\(PROJECT:([A-Z0-9_\-]+)\)")

# Path patterns we care about — anchored at the start of the candidate string.
ARTIFACT_PATH_PATTERNS = [
    re.compile(r"^docs/.+\.md$"),
    re.compile(r"^monitoring/.+\.md$"),
    re.compile(r"^memory/.+\.md$"),
    re.compile(r"^scripts/.+\.(py|sh)$"),
    re.compile(r"^tests/.+\.py$"),
]


def _extract_paths(line: str) -> List[str]:
    """Return artifact paths referenced in `line`.

    Primary source is backtick-wrapped paths; we also accept bare path
    matches as a fallback so the hook stays useful when authors forget the
    backticks.
    """
    candidates: List[str] = []
    # Backtick-wrapped first.
    for match in BACKTICK_PATH_RE.findall(line):
        # Strip leading "./" if present.
        cleaned = match.strip().lstrip("./")
        candidates.append(cleaned)
    # Bare candidates: split on whitespace and punctuation that wouldn't
    # appear inside a path.
    for token in re.split(r"[\s,;()\[\]<>]+", line):
        token = token.strip().strip(".,;:`*_").lstrip("./")
        if token and ("/" in token):
            candidates.append(token)

    paths: List[str] = []
    seen: Set[str] = set()
    for cand in candidates:
        # Strip trailing colon, comma, period if any survived.
        cand = cand.rstrip(":.,;")
        # Skip glob patterns and template placeholders — they are not concrete
        # paths to ls-check (e.g. `monitoring/*.md`, `foo_<YYYY-MM-DD>.md`).
        if any(c in cand for c in "*?<>{}[]"):
            continue
        if not any(pat.match(cand) for pat in ARTIFACT_PATH_PATTERNS):
            continue
        if cand in seen:
            continue
        seen.add(cand)
        paths.append(cand)
    return paths


def _row_project_tags(line: str) -> Set[str]:
    return {f"PROJECT:{m}" for m in PROJECT_MARKER_RE.findall(line)}


def _active_lanes_from_env(env: dict | None = None) -> Set[str]:
    env = env if env is not None else os.environ
    raw = env.get("CLARVIS_ACTIVE_PROJECT_LANES", "")
    if not raw:
        return set()
    parts = re.split(r"[\s,]+", raw.strip())
    return {p for p in parts if p}


def _newly_checked_rows(
    head_lines: List[str] | None, staged_lines: List[str]
) -> List[Tuple[int, str]]:
    """Return `[(line_no_1based, line), ...]` for staged rows that are
    `[x] [UNVERIFIED]` but were not the same `[x] [UNVERIFIED]` row in HEAD.

    Row identity uses the trimmed line so that whitespace-only diffs are
    treated as unchanged.
    """
    head_unverified: Set[str] = set()
    if head_lines is not None:
        for raw in head_lines:
            line = raw.rstrip("\n")
            if CLOSED_UNVERIFIED_RE.match(line):
                head_unverified.add(line.strip())

    out: List[Tuple[int, str]] = []
    for idx, raw in enumerate(staged_lines, 1):
        line = raw.rstrip("\n")
        if not CLOSED_UNVERIFIED_RE.match(line):
            continue
        if line.strip() in head_unverified:
            continue
        out.append((idx, line))
    return out


def check_rows(
    rows: Iterable[Tuple[int, str]],
    *,
    workspace: Path,
    active_lanes: Set[str],
) -> List[Tuple[int, str, List[str]]]:
    """Return `[(line_no, line, missing_paths), ...]` for rows that reference
    at least one artifact that does not exist on disk *and* are not exempt
    via a matching active project lane."""
    failures: List[Tuple[int, str, List[str]]] = []
    for line_no, line in rows:
        row_tags = _row_project_tags(line)
        if active_lanes and (row_tags & active_lanes):
            # Active project lane bypass.
            continue
        paths = _extract_paths(line)
        if not paths:
            # No referenced artifacts -> nothing to verify, accept.
            continue
        missing = [p for p in paths if not (workspace / p).exists()]
        if missing:
            failures.append((line_no, line, missing))
    return failures


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


def _resolve_workspace() -> Path:
    cwd = Path.cwd()
    if (cwd / TARGET).exists():
        return cwd
    # Walk up from this file (scripts/hooks/pre_commit_queue_artifact_check.py).
    here = Path(__file__).resolve()
    root = here.parent.parent.parent
    return root


def _print_failures(
    failures: List[Tuple[int, str, List[str]]], stream=sys.stderr
) -> None:
    for line_no, line, missing in failures:
        snippet = line if len(line) <= 200 else line[:197] + "..."
        print(f"  L{line_no}: {snippet}", file=stream)
        for path in missing:
            print(f"      MISSING: {path}", file=stream)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pre_commit_queue_artifact_check",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Scan an arbitrary staged file (overrides hook mode).",
    )
    parser.add_argument(
        "--head",
        type=Path,
        default=None,
        help="Baseline file to diff against when --path is given.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace root used to ls-check artifact paths. Defaults to cwd.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan the working-tree QUEUE.md (no diff). Print but never fail.",
    )
    args = parser.parse_args(argv)

    active_lanes = _active_lanes_from_env()

    if args.path is not None:
        staged_lines = args.path.read_text(encoding="utf-8").splitlines()
        head_lines = (
            args.head.read_text(encoding="utf-8").splitlines()
            if args.head is not None
            else None
        )
        workspace = args.workspace if args.workspace is not None else Path.cwd()
        rows = _newly_checked_rows(head_lines, staged_lines)
        failures = check_rows(rows, workspace=workspace, active_lanes=active_lanes)
        if not failures:
            return 0
        print(
            f"queue-artifact-check: {len(failures)} newly-checked row(s) reference "
            f"missing artifacts in {args.path}:",
            file=sys.stderr,
        )
        _print_failures(failures)
        return 0 if args.dry_run else 1

    if args.dry_run:
        workspace = args.workspace if args.workspace is not None else _resolve_workspace()
        target = workspace / TARGET
        if not target.exists():
            print(f"queue-artifact-check: {target} not found", file=sys.stderr)
            return 0
        staged_lines = target.read_text(encoding="utf-8").splitlines()
        rows = _newly_checked_rows(None, staged_lines)
        failures = check_rows(rows, workspace=workspace, active_lanes=active_lanes)
        print(
            f"queue-artifact-check: dry-run found {len(failures)} artifact-missing "
            f"newly-checked row(s) in {target}",
            file=sys.stderr,
        )
        _print_failures(failures)
        return 0

    # Pre-commit mode.
    if not _is_queue_staged():
        return 0
    staged_lines = _read_blob(":0")  # index
    if staged_lines is None:
        return 0
    head_lines = _read_blob("HEAD")
    workspace = args.workspace if args.workspace is not None else _resolve_workspace()

    rows = _newly_checked_rows(head_lines, staged_lines)
    failures = check_rows(rows, workspace=workspace, active_lanes=active_lanes)
    if not failures:
        return 0

    print(
        f"queue-artifact-check: {len(failures)} newly-checked `[x] [UNVERIFIED]` "
        f"row(s) in {TARGET} reference artifact(s) that do not exist on disk:",
        file=sys.stderr,
    )
    _print_failures(failures)
    print(
        "\nClosure rows must point at concrete, on-disk artifacts (file paths "
        "under docs/, monitoring/, memory/, scripts/, tests/). Either ship the "
        "artifact, fix the path, or move the work into the appropriate active "
        "project lane (CLARVIS_ACTIVE_PROJECT_LANES).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
