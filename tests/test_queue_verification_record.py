"""Regression tests for the queue verification record producer.

Covers the [QUEUE_VERIFICATION_RECORD_PRODUCER] hook (added 2026-05-02)
that pairs with [QUEUE_UNVERIFIED_ARCHIVE_GUARD]. The producer writes
``data/audit/queue_verifications/<tag>.json`` IFF the postflight observed
at least one of:

  (a) a test invocation that exited 0
  (b) a ``git diff --stat`` showing a file the queue body claimed
  (c) an explicit operator-typed ``--verified`` flag

Without any of those signals, no sidecar is written.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clarvis.queue.verification import (
    collect_evidence,
    write_verification_record,
)


@pytest.fixture
def tmp_ws(tmp_path):
    (tmp_path / "data" / "audit" / "queue_verifications").mkdir(parents=True)
    return tmp_path


def _record_path(ws, tag):
    return ws / "data" / "audit" / "queue_verifications" / f"{tag}.json"


# ---------------------------------------------------------------------------
# Evidence path (a): test invocation that exited 0
# ---------------------------------------------------------------------------
def test_pytest_exit_zero_writes_record(tmp_ws):
    rec = write_verification_record(
        "EVIDENCE_PYTEST",
        selftest_result={"pytest_exit": 0, "pytest_summary": "5 passed in 1.2s"},
        workspace=str(tmp_ws),
        now="2026-05-02T10:00:00Z",
    )
    assert rec is not None
    assert rec["tag"] == "EVIDENCE_PYTEST"
    assert rec["verified_at"] == "2026-05-02T10:00:00Z"
    assert any("pytest exit 0" in e for e in rec["evidence"])

    on_disk = json.loads(_record_path(tmp_ws, "EVIDENCE_PYTEST").read_text())
    assert on_disk == rec


def test_pytest_nonzero_does_not_count_as_evidence(tmp_ws):
    rec = write_verification_record(
        "EVIDENCE_PYTEST_FAIL",
        selftest_result={"pytest_exit": 1, "pytest_summary": "1 failed"},
        workspace=str(tmp_ws),
    )
    assert rec is None
    assert not _record_path(tmp_ws, "EVIDENCE_PYTEST_FAIL").exists()


# ---------------------------------------------------------------------------
# Evidence path (b): git diff --stat showing claimed file
# ---------------------------------------------------------------------------
def test_git_diff_with_claimed_file_writes_record(tmp_ws):
    queue_body = (
        "**[BB_THEME_TOKENS]** Wire `apps/web/src/theme.ts` into the layout. "
        "Add `tests/test_theme_tokens.py`."
    )
    diff_stat = (
        " apps/web/src/theme.ts        | 14 ++++++++++++++\n"
        " tests/test_theme_tokens.py    |  9 +++++++++\n"
        " 2 files changed, 23 insertions(+)\n"
    )
    rec = write_verification_record(
        "BB_THEME_TOKENS",
        task_diff_stat=diff_stat,
        queue_body=queue_body,
        workspace=str(tmp_ws),
    )
    assert rec is not None
    assert any("apps/web/src/theme.ts" in e for e in rec["evidence"])
    assert any("tests/test_theme_tokens.py" in e for e in rec["evidence"])


def test_git_diff_without_claimed_file_does_not_count(tmp_ws):
    queue_body = "**[NO_MATCH]** Edit `scripts/foo.py`."
    diff_stat = " unrelated/other.py | 2 ++\n"
    rec = write_verification_record(
        "NO_MATCH",
        task_diff_stat=diff_stat,
        queue_body=queue_body,
        workspace=str(tmp_ws),
    )
    assert rec is None


def test_porcelain_can_provide_evidence_alongside_diff(tmp_ws):
    queue_body = "Touch `data/audit/foo.json` per spec."
    porcelain = " M data/audit/foo.json"
    rec = write_verification_record(
        "TAG_PORCELAIN",
        task_porcelain=porcelain,
        queue_body=queue_body,
        workspace=str(tmp_ws),
    )
    assert rec is not None
    assert any("data/audit/foo.json" in e for e in rec["evidence"])


# ---------------------------------------------------------------------------
# Evidence path (c): operator-typed --verified flag
# ---------------------------------------------------------------------------
def test_operator_verified_flag_writes_record(tmp_ws):
    rec = write_verification_record(
        "OPERATOR_VERIFIED",
        operator_verified=True,
        workspace=str(tmp_ws),
    )
    assert rec is not None
    assert any("--verified" in e for e in rec["evidence"])


# ---------------------------------------------------------------------------
# No-evidence skip path
# ---------------------------------------------------------------------------
def test_no_evidence_skips_write(tmp_ws):
    rec = write_verification_record(
        "NO_EVIDENCE",
        selftest_result={"pytest_exit": -1},
        task_diff_stat="",
        task_porcelain="",
        queue_body="No paths in this body.",
        operator_verified=False,
        workspace=str(tmp_ws),
    )
    assert rec is None
    assert not _record_path(tmp_ws, "NO_EVIDENCE").exists()


def test_empty_tag_skips_write(tmp_ws):
    rec = write_verification_record(
        "",
        operator_verified=True,
        workspace=str(tmp_ws),
    )
    assert rec is None


# ---------------------------------------------------------------------------
# Multi-evidence aggregation
# ---------------------------------------------------------------------------
def test_multiple_evidence_types_aggregate(tmp_ws):
    queue_body = "Touch `tests/test_thing.py`."
    rec = write_verification_record(
        "MULTI_EVIDENCE",
        selftest_result={"pytest_exit": 0, "pytest_summary": "12 passed"},
        task_diff_stat=" tests/test_thing.py | 2 ++\n",
        queue_body=queue_body,
        operator_verified=True,
        workspace=str(tmp_ws),
    )
    assert rec is not None
    # Three evidence entries: pytest, git diff, operator flag.
    assert len(rec["evidence"]) >= 3


# ---------------------------------------------------------------------------
# collect_evidence() pure-function check
# ---------------------------------------------------------------------------
def test_collect_evidence_returns_empty_list_with_no_signals():
    assert collect_evidence() == []


def test_collect_evidence_pytest_only():
    ev = collect_evidence(selftest_result={"pytest_exit": 0})
    assert ev == ["pytest exit 0"]
