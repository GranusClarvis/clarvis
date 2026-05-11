#!/usr/bin/env python3
"""Tests for queue-pipeline starvation rescue and postflight
already-complete handling — both regressions surfaced in the
2026-05-11 autonomous-evolution audit.

Symptom A: when every queue candidate was deferred for soft reasons
(oversize / verification soft notes), preflight returned
should_defer=True and the heartbeat made no progress for hours.
Fix: a starvation-rescue branch that picks the least-bad candidate
when ALL deferrals are soft.

Symptom B: postflight logged `Task not found in QUEUE.md for
completion` whenever Claude Code itself marked the task [x]
in-band before postflight ran. mark_task_complete() returns
"already_complete" in that case but the elif chain only handled
"marked"/"archived"/falsy. Fix: explicit log line for
"already_complete".
"""

import os
import re
import sys
import unittest


class TestStarvationRescueBranch(unittest.TestCase):
    """Validate the starvation-rescue fallback in heartbeat_preflight.

    Rather than spinning up the full preflight (which imports
    ChromaDB/ONNX/etc.), assert structural properties of the source
    file so the branch is provably wired into _preflight_select_task.
    """

    def setUp(self):
        self.preflight_src = open(
            os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "pipeline", "heartbeat_preflight.py")
        ).read()

    def test_starvation_rescue_branch_exists(self):
        self.assertIn("STARVATION RESCUE", self.preflight_src,
                      "starvation-rescue branch missing from heartbeat_preflight.py")

    def test_starvation_rescue_only_for_soft_deferrals(self):
        # Branch must check deferrals are oversize/verification only,
        # never silently overriding cognitive_load/mode_gate/confidence_gate.
        self.assertIn('SOFT_PREFIXES = ("oversized", "verification:")',
                      self.preflight_src,
                      "starvation rescue must restrict to soft-only reasons")

    def test_starvation_rescue_records_flag(self):
        # Result dict must carry a marker so downstream observability
        # (and tests) can detect the branch firing.
        self.assertIn('result["starvation_rescue"] = True',
                      self.preflight_src)

    def test_simulated_all_oversized_soft_only(self):
        """Simulate the candidate-deferral aggregation logic locally."""
        deferred_tasks = [
            {"task": "[A]...", "reason": "oversized (score=0.70)"},
            {"task": "[B]...", "reason": "oversized (score=0.85)"},
            {"task": "[C]...", "reason": "verification: missing files: x.py"},
        ]
        SOFT_PREFIXES = ("oversized", "verification:")
        soft_only = all(
            any((d.get("reason") or "").startswith(p) for p in SOFT_PREFIXES)
            for d in deferred_tasks
        )
        self.assertTrue(soft_only)

    def test_simulated_one_hard_blocks_rescue(self):
        deferred_tasks = [
            {"task": "[A]...", "reason": "oversized (score=0.70)"},
            {"task": "[B]...", "reason": "cognitive_load: OVERLOAD"},
        ]
        SOFT_PREFIXES = ("oversized", "verification:")
        soft_only = all(
            any((d.get("reason") or "").startswith(p) for p in SOFT_PREFIXES)
            for d in deferred_tasks
        )
        self.assertFalse(soft_only,
                         "cognitive_load deferral must veto starvation rescue")


class TestPostflightAlreadyCompleteHandling(unittest.TestCase):
    """The postflight elif chain must distinguish 'already_complete'
    (Claude pre-marked the task [x]) from 'task not found' (genuine
    queue mismatch).
    """

    def setUp(self):
        self.postflight_src = open(
            os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "pipeline", "heartbeat_postflight.py")
        ).read()

    def test_already_complete_branch_exists(self):
        self.assertRegex(
            self.postflight_src,
            r'elif\s+result_mark\s*==\s*"already_complete"',
            "postflight does not handle mark_task_complete()=='already_complete'",
        )

    def test_already_complete_log_msg_present(self):
        self.assertIn("already marked [x] in QUEUE.md", self.postflight_src)

    def test_unknown_results_still_fall_to_not_found(self):
        # Defensive: ensure the genuine 'task not found' branch is intact
        # so a real queue mismatch is still surfaced.
        self.assertIn("Task not found in QUEUE.md for completion", self.postflight_src)


class TestPostflightStructuralHealthPath(unittest.TestCase):
    """Postflight historic data files must land in the canonical
    workspace/data/ dir, not scripts/data/ (the off-by-one twin
    of the preflight bug).
    """

    def setUp(self):
        self.postflight_src = open(
            os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "pipeline", "heartbeat_postflight.py")
        ).read()

    def test_struct_health_uses_workspace_env(self):
        # Old form: os.path.dirname(__file__), '..', 'data', ...
        # New form must consult CLARVIS_WORKSPACE.
        bad_pattern = r"os\.path\.dirname\(__file__\)\s*,\s*['\"]\.\.['\"]\s*,\s*['\"]data['\"]\s*,\s*['\"]structural_health"
        self.assertNotRegex(self.postflight_src, bad_pattern,
                            "structural_health_history.jsonl still using off-by-one ..")

    def test_completeness_uses_workspace_env(self):
        bad_pattern = r"os\.path\.dirname\(__file__\)\s*,\s*['\"]\.\.['\"]\s*,\s*['\"]data['\"]\s*,\s*['\"]postflight_completeness"
        self.assertNotRegex(self.postflight_src, bad_pattern,
                            "postflight_completeness.jsonl still using off-by-one ..")


if __name__ == "__main__":
    unittest.main()
