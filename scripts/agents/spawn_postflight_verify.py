#!/usr/bin/env python3
"""Postflight verifier for `spawn_claude.sh` and the cron spawners.

For every QUEUE.md row that flipped from `- [ ]` (or absent) to
`- [x] [UNVERIFIED]` between pre-spawn and now, extract referenced artifact
paths, ls-check each on disk, and:
  * record a one-line JSON entry per missing artifact in
    `monitoring/spawn_artifact_holds.log`,
  * append a `[~] SPAWN_POSTFLIGHT_HELD: ARTIFACT_MISSING — <path>` annotation
    to the row in QUEUE.md,
  * exit non-zero if any holds were emitted (so calling cron scripts can log
    the failure).

Pre-state is supplied as a snapshot file (`--pre-state-file`) captured before
the spawn. The session id (`--session-id`) is recorded with each hold so the
operator can tie the hold back to its spawn run / cron origin.

Reuses the row-detection, path-extraction and active-lane bypass logic from
`scripts/hooks/pre_commit_queue_artifact_check.py` so this script and the
pre-commit hook stay aligned.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

DEFAULT_QUEUE_REL = "memory/evolution/QUEUE.md"
DEFAULT_HOLDS_LOG_REL = "monitoring/spawn_artifact_holds.log"
HOLD_ANNOTATION_RE = re.compile(
    r"\s*\[~\]\s*SPAWN_POSTFLIGHT_HELD:\s*(?:ARTIFACT_MISSING|NO_CONCRETE_ARTIFACT_PATH)"
)
TAG_RE = re.compile(r"\*\*\[([A-Z0-9_\-]+)\]\*\*")
NO_PATH_ANNOTATION = (
    "[~] SPAWN_POSTFLIGHT_HELD: NO_CONCRETE_ARTIFACT_PATH — row cites no "
    "on-disk path under docs/, monitoring/, memory/, scripts/, or tests/ — "
    "add a real file path before closing."
)


def _load_hook_module():
    """Import scripts/hooks/pre_commit_queue_artifact_check.py without
    polluting sys.path with the hooks dir (avoids name collisions)."""
    here = Path(__file__).resolve()
    hook_path = here.parent.parent / "hooks" / "pre_commit_queue_artifact_check.py"
    spec = importlib.util.spec_from_file_location(
        "pre_commit_queue_artifact_check", hook_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load hook module at {hook_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_HOOK = _load_hook_module()


def _extract_tag(line: str) -> str:
    m = TAG_RE.search(line)
    return m.group(1) if m else ""


def _newly_checked_rows(
    pre_lines: List[str], post_lines: List[str]
) -> List[Tuple[int, str]]:
    """Rows that are `[x] [UNVERIFIED]` in `post_lines` but were not the same
    `[x] [UNVERIFIED]` row in `pre_lines`.

    Reuses the hook's identity rule (trimmed-line equality) so the two
    artifact gates agree on what counts as 'unchanged'.
    """
    return _HOOK._newly_checked_rows(pre_lines, post_lines)


def verify(
    *,
    pre_lines: List[str],
    workspace: Path,
    queue_path: Path,
    holds_log_path: Path,
    session_id: str,
    now: datetime | None = None,
) -> Tuple[int, List[dict]]:
    """Compare pre vs current QUEUE.md, emit holds, annotate rows.

    Returns `(exit_code, holds)` where holds is the list of JSON-ready hold
    dicts emitted (one per missing-artifact row). Exit is 1 if any holds were
    emitted, 0 otherwise.
    """
    now = now or datetime.now(timezone.utc)
    if not queue_path.exists():
        return 0, []
    post_text = queue_path.read_text(encoding="utf-8")
    post_lines = post_text.splitlines()
    rows = _newly_checked_rows(pre_lines, post_lines)
    if not rows:
        return 0, []

    active_lanes = _HOOK._active_lanes_from_env()
    failures = _HOOK.check_rows(rows, workspace=workspace, active_lanes=active_lanes)
    if not failures:
        return 0, []

    holds: List[dict] = []
    annotated_post_lines = list(post_lines)
    for line_no, line, code, missing in failures:
        # Skip rows that already carry a postflight-held annotation — avoid
        # double-annotating across repeated postflight runs.
        if HOLD_ANNOTATION_RE.search(line):
            continue
        tag = _extract_tag(line)
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if code == _HOOK.NO_CONCRETE_ARTIFACT_PATH:
            holds.append(
                {
                    "ts": ts,
                    "session_id": session_id,
                    "tag": tag,
                    "row_line_no": line_no,
                    "reason": "NO_CONCRETE_ARTIFACT_PATH",
                    "missing_path": None,
                    "row_excerpt": line[:240],
                }
            )
            annotation_suffix = NO_PATH_ANNOTATION
        else:
            for missing_path in missing:
                holds.append(
                    {
                        "ts": ts,
                        "session_id": session_id,
                        "tag": tag,
                        "row_line_no": line_no,
                        "reason": "ARTIFACT_MISSING",
                        "missing_path": missing_path,
                        "row_excerpt": line[:240],
                    }
                )
            annotation_suffix = " ".join(
                f"[~] SPAWN_POSTFLIGHT_HELD: ARTIFACT_MISSING — {p}"
                for p in missing
            )
        idx = line_no - 1
        if 0 <= idx < len(annotated_post_lines):
            existing = annotated_post_lines[idx]
            annotated_post_lines[idx] = f"{existing.rstrip()} {annotation_suffix}"

    if not holds:
        return 0, []

    # Persist annotations.
    new_text = "\n".join(annotated_post_lines)
    if post_text.endswith("\n"):
        new_text += "\n"
    queue_path.write_text(new_text, encoding="utf-8")

    # Persist holds log.
    holds_log_path.parent.mkdir(parents=True, exist_ok=True)
    with holds_log_path.open("a", encoding="utf-8") as fh:
        for hold in holds:
            fh.write(json.dumps(hold, ensure_ascii=False) + "\n")

    return 1, holds


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spawn_postflight_verify",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pre-state-file",
        type=Path,
        required=True,
        help="Snapshot of QUEUE.md captured before the spawn.",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default="unknown",
        help="Spawn session id (recorded with each hold).",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace root (defaults to cwd). Artifact paths are resolved here.",
    )
    parser.add_argument(
        "--queue-file",
        type=Path,
        default=None,
        help=f"Path to QUEUE.md (defaults to <workspace>/{DEFAULT_QUEUE_REL}).",
    )
    parser.add_argument(
        "--holds-log",
        type=Path,
        default=None,
        help=(
            f"Path to spawn_artifact_holds.log (defaults to "
            f"<workspace>/{DEFAULT_HOLDS_LOG_REL})."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable summary on stderr.",
    )
    args = parser.parse_args(argv)

    workspace = args.workspace.resolve()
    queue_path = args.queue_file or (workspace / DEFAULT_QUEUE_REL)
    holds_log_path = args.holds_log or (workspace / DEFAULT_HOLDS_LOG_REL)

    if not args.pre_state_file.exists():
        if not args.quiet:
            print(
                f"spawn_postflight_verify: pre-state-file missing "
                f"({args.pre_state_file}), skipping",
                file=sys.stderr,
            )
        return 0

    pre_lines = args.pre_state_file.read_text(encoding="utf-8").splitlines()

    rc, holds = verify(
        pre_lines=pre_lines,
        workspace=workspace,
        queue_path=queue_path,
        holds_log_path=holds_log_path,
        session_id=args.session_id,
    )

    if holds and not args.quiet:
        print(
            f"spawn_postflight_verify: {len(holds)} artifact hold(s) "
            f"emitted for session {args.session_id}",
            file=sys.stderr,
        )
        for hold in holds:
            reason = hold.get("reason", "ARTIFACT_MISSING")
            missing = hold.get("missing_path") or "<none>"
            print(
                f"  HOLD tag={hold['tag']} reason={reason} "
                f"missing={missing} row_line={hold['row_line_no']}",
                file=sys.stderr,
            )
    return rc


if __name__ == "__main__":
    sys.exit(main())
