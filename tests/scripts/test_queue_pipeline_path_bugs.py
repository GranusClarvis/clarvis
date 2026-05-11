#!/usr/bin/env python3
"""Regression tests for queue-pipeline path bugs found in the
2026-05-11 autonomous-evolution audit.

Symptom: heartbeat preflight repeatedly skipped tasks with
`verification: missing files: ...` even though the referenced files
existed under the workspace root. Root cause: heartbeat_preflight.py
moved from `scripts/` to `scripts/pipeline/` but `WORKSPACE`,
`QUEUE_FILE`, and `_SLOT_STATE_FILE` still used a single `..` for
relativity — resolving to `scripts/` instead of the workspace root.
A parallel postflight bug had two `data/...` files writing to
`scripts/data/` for the same reason.
"""

import importlib
import os
import re
import sys
import unittest


def _abs(path):
    return os.path.abspath(path)


class TestPreflightWorkspacePath(unittest.TestCase):
    def setUp(self):
        # Forget any cached version of the module so we re-evaluate the
        # module-level constants under controlled conditions.
        sys.modules.pop("heartbeat_preflight", None)
        # Make sure CLARVIS_WORKSPACE is not set so the default path
        # branch is exercised.
        self._old_ws = os.environ.pop("CLARVIS_WORKSPACE", None)
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "pipeline"))

    def tearDown(self):
        if self._old_ws is not None:
            os.environ["CLARVIS_WORKSPACE"] = self._old_ws

    def test_workspace_resolves_to_repo_root_not_scripts(self):
        """Default WORKSPACE must resolve to repo root, never `scripts/`."""
        m = importlib.import_module("heartbeat_preflight")
        ws = _abs(m.WORKSPACE)
        # Workspace root should contain `clarvis/` and `memory/` directories.
        self.assertTrue(os.path.isdir(os.path.join(ws, "clarvis")),
                        f"clarvis/ not found under WORKSPACE={ws}")
        self.assertTrue(os.path.isdir(os.path.join(ws, "memory", "evolution")),
                        f"memory/evolution/ not found under WORKSPACE={ws}")
        # And it must not be the scripts/ dir (the bug condition).
        self.assertFalse(ws.endswith(os.sep + "scripts"),
                         f"WORKSPACE wrongly resolved to {ws}")

    def test_queue_file_points_at_real_file(self):
        m = importlib.import_module("heartbeat_preflight")
        self.assertTrue(os.path.exists(m.QUEUE_FILE),
                        f"QUEUE_FILE does not exist: {m.QUEUE_FILE}")
        self.assertTrue(m.QUEUE_FILE.endswith(os.path.join("memory", "evolution", "QUEUE.md")))

    def test_slot_state_file_under_canonical_data_dir(self):
        m = importlib.import_module("heartbeat_preflight")
        self.assertTrue(m._SLOT_STATE_FILE.endswith(os.path.join("data", "project_lane_slot.json")))
        # The parent (data/) must be the canonical workspace data dir.
        parent = os.path.dirname(m._SLOT_STATE_FILE)
        self.assertTrue(os.path.isdir(parent),
                        f"slot file parent must exist: {parent}")
        self.assertNotIn(os.sep + "scripts" + os.sep + "data", parent,
                         f"slot file leaking to scripts/data/: {parent}")

    def test_clarvis_workspace_env_branch_present(self):
        """Source-level assertion: WORKSPACE consults CLARVIS_WORKSPACE.

        We do NOT actually flip the env var inside this process because
        the script_loader caches _SCRIPTS at import time, and re-importing
        heartbeat_preflight with a fake workspace would break unrelated
        tests in the same pytest run (the loader would try to load
        scripts from the fake workspace path).
        """
        src = open(
            os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "pipeline", "heartbeat_preflight.py")
        ).read()
        self.assertIn('os.environ.get(\n    "CLARVIS_WORKSPACE"', src)


class TestVerifyTaskFilePathChecks(unittest.TestCase):
    """The verification gate must successfully find files that
    actually exist under the workspace root.
    """

    def setUp(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "pipeline"))
        sys.modules.pop("heartbeat_preflight", None)
        self._old_ws = os.environ.pop("CLARVIS_WORKSPACE", None)

    def tearDown(self):
        if self._old_ws is not None:
            os.environ["CLARVIS_WORKSPACE"] = self._old_ws

    def test_existing_file_refs_are_recognized(self):
        m = importlib.import_module("heartbeat_preflight")
        # Pick two files we know exist.
        task = (
            "[FAKE_TAG] Update clarvis/queue/writer.py and "
            "scripts/pipeline/heartbeat_preflight.py to do X"
        )
        v = m._verify_task_executable(task)
        self.assertEqual(v["missing_files"], [],
                         f"existing files reported missing: {v}")
        self.assertFalse(v["hard_fail"], f"hard_fail=True for valid refs: {v}")

    def test_missing_file_triggers_soft_note(self):
        m = importlib.import_module("heartbeat_preflight")
        task = "[FAKE] Create scripts/never/exists/zzz.py"
        v = m._verify_task_executable(task)
        self.assertEqual(v["missing_files"], ["scripts/never/exists/zzz.py"])
        # Single missing file is a soft warning, not a hard fail.
        self.assertFalse(v["hard_fail"])


if __name__ == "__main__":
    unittest.main()
