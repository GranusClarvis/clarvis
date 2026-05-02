"""Queue verification record producer.

Writes sidecar verification records at
``data/audit/queue_verifications/<tag>.json`` when a heartbeat task completes
with at least one of three evidence types:

  (a) a test invocation that exited 0 (selftest_result["pytest_exit"] == 0)
  (b) a ``git diff --stat`` (or porcelain) showing a file the queue body
      claimed
  (c) an explicit operator-typed ``--verified`` flag on
      ``clarvis queue mark-done``

Without one of these signals, no record is written. This is the producer
half of the ``CLARVIS_QUEUE_UNVERIFIED_GUARD=block`` contract enforced by
``clarvis.queue.writer.archive_completed`` — paired with
``[QUEUE_UNVERIFIED_ARCHIVE_GUARD]``.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

# Match path-like tokens: backticked paths or bare paths with a known extension.
_PATH_RX = re.compile(
    r"`([^`\s]+\.[A-Za-z0-9]+)`"
    r"|(?<![\w/])([A-Za-z_][\w./-]*\.(?:py|sh|md|json|yaml|yml|toml|ts|tsx|js|jsx|css|html|sql|txt))"
)


def _extract_claimed_paths(text: str) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _PATH_RX.finditer(text):
        path = m.group(1) or m.group(2)
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out


def collect_evidence(
    *,
    selftest_result: Optional[dict] = None,
    task_diff_stat: Optional[str] = None,
    task_porcelain: Optional[str] = None,
    queue_body: Optional[str] = None,
    operator_verified: bool = False,
) -> list[str]:
    """Return a list of evidence strings; empty list means no evidence."""
    evidence: list[str] = []

    # (a) test invocation that exited 0
    if selftest_result and selftest_result.get("pytest_exit") == 0:
        summary = (selftest_result.get("pytest_summary") or "").strip()
        if summary:
            evidence.append(f"pytest exit 0: {summary}")
        else:
            evidence.append("pytest exit 0")

    # (b) git diff --stat (or porcelain) showing a claimed file
    if queue_body and (task_diff_stat or task_porcelain):
        diff_blob = "\n".join(filter(None, (task_diff_stat, task_porcelain)))
        for path in _extract_claimed_paths(queue_body):
            if path in diff_blob:
                evidence.append(f"git diff includes {path}")

    # (c) operator-typed --verified flag
    if operator_verified:
        evidence.append("operator --verified flag")

    return evidence


def write_verification_record(
    tag: str,
    *,
    selftest_result: Optional[dict] = None,
    task_diff_stat: Optional[str] = None,
    task_porcelain: Optional[str] = None,
    queue_body: Optional[str] = None,
    operator_verified: bool = False,
    workspace: Optional[str] = None,
    now: Optional[str] = None,
) -> Optional[dict]:
    """Write the sidecar record IFF at least one evidence type is present.

    Returns the record dict on success, or ``None`` if no evidence (skip).
    """
    if not tag:
        return None

    evidence = collect_evidence(
        selftest_result=selftest_result,
        task_diff_stat=task_diff_stat,
        task_porcelain=task_porcelain,
        queue_body=queue_body,
        operator_verified=operator_verified,
    )

    if not evidence:
        return None

    if workspace is None:
        workspace = os.environ.get(
            "CLARVIS_WORKSPACE",
            os.path.expanduser("~/.openclaw/workspace"),
        )

    verification_dir = os.path.join(
        workspace, "data", "audit", "queue_verifications"
    )
    os.makedirs(verification_dir, exist_ok=True)

    record = {
        "tag": tag,
        "verified_at": now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence": evidence,
    }

    out_path = os.path.join(verification_dir, f"{tag}.json")
    with open(out_path, "w") as f:
        json.dump(record, f, indent=2)

    return record
