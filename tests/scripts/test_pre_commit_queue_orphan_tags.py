"""Tests for `scripts/hooks/pre_commit_queue_orphan_tags.py`.

Three acceptance cases per the [CLARVIS_PROC_QUEUE_ORPHAN_TAG_HOOK] contract:
  1. Tag inside a `- [ ]` row -> accept (no orphan).
  2. Tag inside a section-body prose paragraph -> reject (orphan).
  3. Tag inside `_italic prose_` -> reject (orphan).
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def hook():
    here = Path(__file__).resolve()
    scripts_dir = here.parent.parent.parent / "scripts"
    hooks_dir = scripts_dir / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    return importlib.import_module("pre_commit_queue_orphan_tags")


def test_tag_inside_task_row_is_accepted(hook):
    lines = [
        "## P0 — Current Sprint",
        "",
        "- [ ] **[BB_QA_TRUST_STRIP_MOBILE_HIT_TARGET_FIX]** Fix mobile.",
        "- [x] **[SWO_V2_COMPANION_BG_MATTE]** Done.",
        "- [~] **[CLARVIS_PROC_QUEUE_ORPHAN_TAG_HOOK]** Held.",
    ]
    orphans = hook.find_orphans(lines)
    assert orphans == [], f"expected no orphans, got {orphans}"


def test_tag_inside_prose_paragraph_is_rejected(hook):
    lines = [
        "## P1 — This Week",
        "",
        "We still need to ship [BB_QA_BET_PANEL_TOUCH_TARGET_AUDIT] before the demo.",
        "",
        "- [ ] **[BB_QA_DEEP_PASS_RERUN_AND_LOCKIN]** Rerun the deep pass.",
    ]
    orphans = hook.find_orphans(lines)
    assert len(orphans) == 1, f"expected exactly 1 orphan, got {orphans}"
    line_no, line, tags = orphans[0]
    assert line_no == 3
    assert tags == ["[BB_QA_BET_PANEL_TOUCH_TARGET_AUDIT]"]
    assert "ship" in line


def test_tag_inside_italic_prose_is_rejected(hook):
    lines = [
        "### BB QA fallout",
        "",
        "_Source: docs/qa/BB_DEEP_QA_TRIAGE_2026-05-13.md. Triage finding [BB_QA_HARNESS_ROUTE_LEVEL_HIT_TARGET_FAN_OUT_REPORT] remains open; cross-check against [SWO_V2_COMPANION_COZY_POLISH] follow-ups._",
        "",
        "- [ ] **[BB_QA_TRUST_STRIP_MOBILE_HIT_TARGET_FIX]** Real task row.",
    ]
    orphans = hook.find_orphans(lines)
    assert len(orphans) == 1, f"expected exactly 1 orphan line, got {orphans}"
    line_no, line, tags = orphans[0]
    assert line_no == 3
    assert line.lstrip().startswith("_")
    assert "[BB_QA_HARNESS_ROUTE_LEVEL_HIT_TARGET_FAN_OUT_REPORT]" in tags
    assert "[SWO_V2_COMPANION_COZY_POLISH]" in tags


def test_dry_run_cli_against_temp_file_returns_zero(hook, tmp_path):
    """Belt-and-braces: --dry-run on a file with orphans should exit 0 but print."""
    sample = tmp_path / "QUEUE.md"
    sample.write_text(
        "# Q\n\n"
        "_Source: doc.md. [BB_QA_FOO_BAR] is mentioned in prose._\n\n"
        "- [ ] **[BB_QA_BAZ_QUUX]** real row.\n",
        encoding="utf-8",
    )
    rc = hook.main(["--path", str(sample), "--dry-run"])
    assert rc == 0

    rc = hook.main(["--path", str(sample)])
    assert rc == 1  # default on --path with orphans: fail


def test_codefence_tags_are_ignored(hook):
    lines = [
        "Examples are not schedulable:",
        "```",
        "[BB_QA_EXAMPLE_TAG] should not count",
        "```",
        "- [ ] **[BB_QA_REAL]** task.",
    ]
    orphans = hook.find_orphans(lines)
    assert orphans == []


def test_script_compiles():
    """Acceptance (a): hook file passes `python3 -m py_compile`."""
    here = Path(__file__).resolve()
    script = here.parent.parent.parent / "scripts" / "hooks" / "pre_commit_queue_orphan_tags.py"
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
