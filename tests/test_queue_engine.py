"""Tests for clarvis.queue.engine — sidecar-based queue state management."""

import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clarvis.queue.engine import QueueEngine, parse_queue, _extract_tag, STUCK_RUNNING_HOURS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_QUEUE = """\
# Evolution Queue — Clarvis

## P0 — Current Sprint

- [ ] [URGENT_FIX] Fix critical bug in brain.py
- [ ] [DEPLOY_PREP] Prepare deployment checklist

---

## P1 — This Week

- [ ] [ENGINE_V2] Implement queue engine v2
- [x] [DONE_TASK] Already completed task

---

## P2 — When Idle

- [ ] [CLEANUP] Clean up old logs
"""


@pytest.fixture
def tmp_queue(tmp_path):
    """Create a temporary QUEUE.md and sidecar for testing."""
    queue_file = str(tmp_path / "QUEUE.md")
    sidecar_file = str(tmp_path / "queue_state.json")
    runs_file = str(tmp_path / "queue_runs.jsonl")

    with open(queue_file, "w") as f:
        f.write(SAMPLE_QUEUE)

    return queue_file, sidecar_file, runs_file


@pytest.fixture
def engine(tmp_queue):
    queue_file, sidecar_file, runs_file = tmp_queue
    return QueueEngine(queue_file=queue_file, sidecar_file=sidecar_file, runs_file=runs_file)


# ---------------------------------------------------------------------------
# parse_queue tests
# ---------------------------------------------------------------------------

class TestParseQueue:
    def test_parse_basic(self, tmp_queue):
        queue_file, *_ = tmp_queue
        tasks = parse_queue(queue_file)
        tags = [t["tag"] for t in tasks]
        assert "URGENT_FIX" in tags
        assert "DEPLOY_PREP" in tags
        assert "ENGINE_V2" in tags
        assert "CLEANUP" in tags
        # Completed task should NOT appear
        assert "DONE_TASK" not in tags

    def test_priorities(self, tmp_queue):
        queue_file, *_ = tmp_queue
        tasks = parse_queue(queue_file)
        by_tag = {t["tag"]: t for t in tasks}
        assert by_tag["URGENT_FIX"]["priority"] == "P0"
        assert by_tag["ENGINE_V2"]["priority"] == "P1"
        assert by_tag["CLEANUP"]["priority"] == "P2"

    def test_missing_file(self, tmp_path):
        tasks = parse_queue(str(tmp_path / "nonexistent.md"))
        assert tasks == []


class TestExtractTag:
    def test_basic(self):
        assert _extract_tag("[QUEUE_ENGINE_V2] Implement stuff") == "QUEUE_ENGINE_V2"

    def test_with_dots(self):
        assert _extract_tag("[EXTERNAL_CHALLENGE:bench-01] Test") == "EXTERNAL_CHALLENGE:bench-01"

    def test_no_tag(self):
        assert _extract_tag("No tag here") is None

    def test_lowercase_rejected(self):
        assert _extract_tag("[lowercase] nope") is None


# ---------------------------------------------------------------------------
# Reconciliation tests
# ---------------------------------------------------------------------------

class TestReconcile:
    def test_fresh_reconcile_creates_entries(self, engine):
        tasks, sidecar = engine.reconcile()
        assert len(tasks) == 4
        for task in tasks:
            assert task["state"] == "pending"
            assert task["attempts"] == 0
            assert task["tag"] in sidecar

    def test_preserves_existing_state(self, engine):
        # First reconcile
        engine.reconcile()
        # Manually modify sidecar
        engine.mark_running("URGENT_FIX")
        # Second reconcile should preserve running state
        tasks, sidecar = engine.reconcile()
        by_tag = {t["tag"]: t for t in tasks}
        assert by_tag["URGENT_FIX"]["state"] == "running"
        assert by_tag["URGENT_FIX"]["attempts"] == 1

    def test_stale_entries_marked_removed(self, engine, tmp_queue):
        queue_file, *_ = tmp_queue
        engine.reconcile()

        # Remove a task from QUEUE.md
        content = open(queue_file).read()
        content = content.replace("- [ ] [CLEANUP] Clean up old logs\n", "")
        with open(queue_file, "w") as f:
            f.write(content)

        tasks, sidecar = engine.reconcile()
        assert sidecar["CLEANUP"]["state"] == "removed"


# ---------------------------------------------------------------------------
# State transition tests
# ---------------------------------------------------------------------------

class TestStateTransitions:
    def test_mark_running(self, engine):
        engine.reconcile()
        assert engine.mark_running("URGENT_FIX")
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "running"
        assert state["attempts"] == 1
        assert state["last_run"] is not None

    def test_mark_succeeded(self, engine, tmp_queue):
        queue_file, *_ = tmp_queue
        engine.reconcile()
        engine.mark_running("URGENT_FIX")
        assert engine.mark_succeeded("URGENT_FIX", "done 2026-04-03")
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "succeeded"
        # Check QUEUE.md was updated
        content = open(queue_file).read()
        assert "[x] [URGENT_FIX]" in content
        assert "(done 2026-04-03)" in content

    def test_mark_failed_with_backoff(self, engine):
        engine.reconcile()
        engine.mark_running("ENGINE_V2")
        assert engine.mark_failed("ENGINE_V2", "import error")
        state = engine.get_task_state("ENGINE_V2")
        assert state["state"] == "failed"
        assert state["failure_reason"] == "import error"
        assert state["skip_until"] > time.time()

    def test_auto_defer_on_max_retries(self, engine):
        engine.reconcile()
        # P1 max retries = 2, so after 2 attempts it should defer
        engine.mark_running("ENGINE_V2")  # attempt 1
        engine.mark_failed("ENGINE_V2", "fail 1")
        # Reset to pending to retry
        sidecar = engine._load()
        sidecar["ENGINE_V2"]["state"] = "failed"
        sidecar["ENGINE_V2"]["skip_until"] = 0
        engine._save(sidecar)
        engine.mark_running("ENGINE_V2")  # attempt 2
        engine.mark_failed("ENGINE_V2", "fail 2")
        state = engine.get_task_state("ENGINE_V2")
        assert state["state"] == "deferred"

    def test_reset_clears_state(self, engine):
        engine.reconcile()
        engine.mark_running("URGENT_FIX")
        engine.mark_failed("URGENT_FIX", "transient error")
        engine.reset("URGENT_FIX")
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "pending"
        assert state["attempts"] == 0
        assert state["failure_reason"] is None

    def test_nonexistent_tag_returns_false(self, engine):
        engine.reconcile()
        assert not engine.mark_running("NONEXISTENT")
        assert not engine.mark_succeeded("NONEXISTENT")
        assert not engine.mark_failed("NONEXISTENT")


# ---------------------------------------------------------------------------
# Selection tests
# ---------------------------------------------------------------------------

class TestRankedEligible:
    def test_returns_sorted_list(self, engine):
        eligible = engine.ranked_eligible()
        assert isinstance(eligible, list)
        assert len(eligible) == 4  # all 4 tasks are pending/eligible
        # Should be sorted by score descending
        scores = [t["score"] for t in eligible]
        assert scores == sorted(scores, reverse=True)

    def test_p0_tasks_rank_first(self, engine):
        eligible = engine.ranked_eligible()
        assert eligible[0]["priority"] == "P0"

    def test_excludes_running_and_deferred(self, engine):
        engine.reconcile()
        engine.mark_running("URGENT_FIX")
        engine.defer("CLEANUP", "not needed")
        eligible = engine.ranked_eligible()
        tags = [t["tag"] for t in eligible]
        assert "URGENT_FIX" not in tags
        assert "CLEANUP" not in tags
        assert len(eligible) == 2  # DEPLOY_PREP and ENGINE_V2

    def test_excludes_backoff(self, engine):
        engine.reconcile()
        engine.mark_running("URGENT_FIX")
        engine.mark_failed("URGENT_FIX", "temp error")
        eligible = engine.ranked_eligible()
        tags = [t["tag"] for t in eligible]
        assert "URGENT_FIX" not in tags

    def test_empty_queue(self, tmp_path):
        queue_file = str(tmp_path / "QUEUE.md")
        sidecar_file = str(tmp_path / "queue_state.json")
        runs_file = str(tmp_path / "queue_runs.jsonl")
        with open(queue_file, "w") as f:
            f.write("# Empty queue\n## P0\n---\n")
        eng = QueueEngine(queue_file=queue_file, sidecar_file=sidecar_file, runs_file=runs_file)
        assert eng.ranked_eligible() == []


class TestSelectNext:
    def test_selects_highest_priority(self, engine):
        task = engine.select_next()
        assert task is not None
        assert task["priority"] == "P0"

    def test_skips_running_tasks(self, engine):
        engine.reconcile()
        engine.mark_running("URGENT_FIX")
        engine.mark_running("DEPLOY_PREP")
        task = engine.select_next()
        assert task is not None
        assert task["tag"] not in ("URGENT_FIX", "DEPLOY_PREP")

    def test_skips_backoff_tasks(self, engine):
        engine.reconcile()
        engine.mark_running("URGENT_FIX")
        engine.mark_failed("URGENT_FIX", "temp error")
        # URGENT_FIX should be skipped due to backoff
        task = engine.select_next()
        # It should pick something else (DEPLOY_PREP or ENGINE_V2)
        assert task["tag"] != "URGENT_FIX"

    def test_returns_none_when_empty(self, tmp_path):
        queue_file = str(tmp_path / "QUEUE.md")
        sidecar_file = str(tmp_path / "queue_state.json")
        runs_file = str(tmp_path / "queue_runs.jsonl")
        with open(queue_file, "w") as f:
            f.write("# Empty queue\n## P0\n---\n")
        eng = QueueEngine(queue_file=queue_file, sidecar_file=sidecar_file, runs_file=runs_file)
        assert eng.select_next() is None


# ---------------------------------------------------------------------------
# Stats tests
# ---------------------------------------------------------------------------

class TestStats:
    def test_basic_stats(self, engine):
        engine.reconcile()
        s = engine.stats()
        assert s["pending"] == 4
        assert s["running"] == 0
        assert s["failed"] == 0
        assert s["total"] >= 4
        assert isinstance(s["stuck_running"], list)
        assert isinstance(s["chronic_failures"], list)

    def test_stats_after_transitions(self, engine):
        engine.reconcile()
        engine.mark_running("URGENT_FIX")
        engine.mark_succeeded("URGENT_FIX", "done")
        engine.mark_running("ENGINE_V2")
        s = engine.stats()
        assert s["running"] == 1
        assert s["completed_24h"] == 1


# ---------------------------------------------------------------------------
# Sidecar persistence tests
# ---------------------------------------------------------------------------

class TestSidecarPersistence:
    def test_sidecar_survives_reload(self, tmp_queue):
        queue_file, sidecar_file, runs_file = tmp_queue
        eng1 = QueueEngine(queue_file=queue_file, sidecar_file=sidecar_file, runs_file=runs_file)
        eng1.reconcile()
        eng1.mark_running("URGENT_FIX")

        # New engine instance reads same sidecar
        eng2 = QueueEngine(queue_file=queue_file, sidecar_file=sidecar_file, runs_file=runs_file)
        state = eng2.get_task_state("URGENT_FIX")
        assert state["state"] == "running"

    def test_corrupt_sidecar_recovers(self, tmp_queue):
        queue_file, sidecar_file, runs_file = tmp_queue
        # Write corrupt JSON
        with open(sidecar_file, "w") as f:
            f.write("{corrupt json")

        eng = QueueEngine(queue_file=queue_file, sidecar_file=sidecar_file, runs_file=runs_file)
        tasks, sidecar = eng.reconcile()
        # Should recover by creating fresh entries
        assert len(tasks) == 4
        assert all(t["state"] == "pending" for t in tasks)


# ---------------------------------------------------------------------------
# Run record tests
# ---------------------------------------------------------------------------

class TestRunRecords:
    def test_start_and_end_run(self, engine):
        engine.reconcile()
        run_id = engine.start_run("URGENT_FIX")
        assert run_id.startswith("URGENT_FIX-")
        assert len(run_id) > len("URGENT_FIX-")

        # Task should be running
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "running"

        # End the run
        ok = engine.end_run(run_id, "success", exit_code=0, duration_s=42.5)
        assert ok

        # Task should be succeeded
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "succeeded"

    def test_end_run_failure(self, engine):
        engine.reconcile()
        run_id = engine.start_run("ENGINE_V2")
        ok = engine.end_run(run_id, "failure", exit_code=1, error="import error", duration_s=10.0)
        assert ok

        state = engine.get_task_state("ENGINE_V2")
        assert state["state"] == "failed"
        assert "import error" in state["failure_reason"]

    def test_get_runs(self, engine):
        engine.reconcile()
        run_id1 = engine.start_run("URGENT_FIX")
        engine.end_run(run_id1, "failure", exit_code=1, duration_s=5.0)

        # Reset and run again
        engine.reset("URGENT_FIX")
        run_id2 = engine.start_run("URGENT_FIX")
        engine.end_run(run_id2, "success", exit_code=0, duration_s=30.0)

        runs = engine.get_runs("URGENT_FIX")
        assert len(runs) == 2
        # Most recent first
        assert runs[0]["outcome"] == "success"
        assert runs[1]["outcome"] == "failure"

    def test_recent_runs(self, engine):
        engine.reconcile()
        run_id1 = engine.start_run("URGENT_FIX")
        engine.end_run(run_id1, "success", exit_code=0, duration_s=10.0)
        run_id2 = engine.start_run("ENGINE_V2")
        engine.end_run(run_id2, "success", exit_code=0, duration_s=20.0)

        recent = engine.recent_runs()
        assert len(recent) >= 2
        # Most recent first
        assert recent[0]["tag"] == "ENGINE_V2"

    def test_run_stats(self, engine):
        engine.reconcile()
        run_id = engine.start_run("URGENT_FIX")
        engine.end_run(run_id, "success", exit_code=0, duration_s=15.0)

        stats = engine.run_stats()
        assert stats["total_runs"] >= 1
        assert stats["runs_24h"] >= 1
        assert stats["success_rate_24h"] > 0

    def test_runs_file_not_exists(self, engine):
        """Run queries work even when JSONL doesn't exist yet."""
        assert engine.get_runs("NONEXISTENT") == []
        assert engine.recent_runs() == []
        stats = engine.run_stats()
        assert stats["total_runs"] == 0


# ---------------------------------------------------------------------------
# Soak check tests
# ---------------------------------------------------------------------------

class TestSoakCheck:
    def test_soak_clean_state(self, engine):
        """Soak check passes on a clean, reconciled engine."""
        engine.reconcile()
        report = engine.soak_check()
        assert report["verdict"] == "PASS"
        assert report["failures"] == []
        assert report["checks"]["sidecar_loads"] is True
        assert report["checks"]["sidecar_entries"] >= 4

    def test_soak_detects_invalid_state(self, engine):
        """Soak check flags entries with invalid states."""
        engine.reconcile()
        sidecar = engine._load()
        sidecar["URGENT_FIX"]["state"] = "bogus"
        engine._save(sidecar)
        report = engine.soak_check()
        assert report["verdict"] == "FAIL"
        assert any("state issues" in f for f in report["failures"])

    def test_soak_after_full_lifecycle(self, engine):
        """Soak check passes after a complete start→succeed lifecycle."""
        engine.reconcile()
        run_id = engine.start_run("URGENT_FIX")
        engine.end_run(run_id, "success", exit_code=0, duration_s=42.0)
        report = engine.soak_check()
        assert report["verdict"] == "PASS"
        assert report["checks"]["total_runs"] == 1
        assert report["checks"]["dangling_runs"] == 0


# ---------------------------------------------------------------------------
# Stuck-run recovery tests
# ---------------------------------------------------------------------------

class TestStuckRunRecovery:
    def test_recover_stuck_running_task(self, engine):
        """Tasks stuck in 'running' beyond threshold are auto-recovered."""
        engine.reconcile()
        engine.mark_running("URGENT_FIX")

        # Manually backdate the updated_at to simulate a stuck task
        sidecar = engine._load()
        from datetime import timedelta
        old_time = (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sidecar["URGENT_FIX"]["updated_at"] = old_time
        engine._save(sidecar)

        recovered = engine.recover_stuck(threshold_hours=3)
        assert "URGENT_FIX" in recovered
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "failed"
        assert "auto-recovered" in state["failure_reason"]

    def test_reconcile_auto_recovers_stuck(self, engine):
        """Reconcile automatically recovers tasks stuck in 'running'."""
        engine.reconcile()
        engine.mark_running("DEPLOY_PREP")

        # Backdate
        sidecar = engine._load()
        from datetime import timedelta
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sidecar["DEPLOY_PREP"]["updated_at"] = old_time
        engine._save(sidecar)

        tasks, _ = engine.reconcile()
        by_tag = {t["tag"]: t for t in tasks}
        assert by_tag["DEPLOY_PREP"]["state"] == "failed"
        assert "auto-recovered" in by_tag["DEPLOY_PREP"]["failure_reason"]

    def test_no_recovery_within_threshold(self, engine):
        """Tasks running within threshold are NOT recovered."""
        engine.reconcile()
        engine.mark_running("URGENT_FIX")
        # Just started — should not be recovered
        recovered = engine.recover_stuck(threshold_hours=3)
        assert recovered == []
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "running"

    def test_recovered_task_becomes_eligible(self, engine):
        """After stuck recovery, a P1 task eventually becomes eligible for selection again."""
        engine.reconcile()
        # Use ENGINE_V2 (P1, max retries=2) so it's still retryable after 1 attempt
        engine.mark_running("ENGINE_V2")

        sidecar = engine._load()
        from datetime import timedelta
        old_time = (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sidecar["ENGINE_V2"]["updated_at"] = old_time
        engine._save(sidecar)

        engine.recover_stuck(threshold_hours=3)
        state = engine.get_task_state("ENGINE_V2")
        assert state["state"] == "failed"
        # Clear skip_until so it's immediately eligible
        sidecar = engine._load()
        sidecar["ENGINE_V2"]["skip_until"] = 0
        engine._save(sidecar)

        # ENGINE_V2 is P1 with 1 attempt, max=2, so it should be eligible
        eligible_tags = []
        tasks, _ = engine.reconcile()
        for t in tasks:
            if t["state"] in ("pending", "failed"):
                eligible_tags.append(t["tag"])
        assert "ENGINE_V2" in eligible_tags


# ---------------------------------------------------------------------------
# External run record tests
# ---------------------------------------------------------------------------

class TestExternalRun:
    def test_start_external_known_tag(self, engine):
        """External run with a tag that exists in QUEUE.md creates a full run record."""
        run_id = engine.start_external_run("[URGENT_FIX] Fix critical bug", source="manual_spawn")
        assert run_id is not None
        assert run_id.startswith("URGENT_FIX-")
        # Task should be running in sidecar
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "running"

    def test_start_external_unknown_tag(self, engine):
        """External run with a tag NOT in QUEUE.md creates an ad-hoc run record."""
        engine.reconcile()
        run_id = engine.start_external_run("[ADHOC_TASK] Something not in queue", source="manual_spawn")
        assert run_id is not None
        assert run_id.startswith("ADHOC_TASK-")
        # Should NOT be in sidecar
        state = engine.get_task_state("ADHOC_TASK")
        assert state is None
        # But should have a run record
        runs = engine.get_runs("ADHOC_TASK")
        assert len(runs) == 1
        assert runs[0]["source"] == "manual_spawn"
        assert runs[0]["ad_hoc"] is True

    def test_start_external_no_tag(self, engine):
        """External run with no [TAG] returns None."""
        run_id = engine.start_external_run("Fix something without a tag", source="manual_spawn")
        assert run_id is None

    def test_external_full_lifecycle(self, engine):
        """Full external lifecycle: start → end with success."""
        run_id = engine.start_external_run("[DEPLOY_PREP] Prepare deployment", source="manual_spawn")
        assert run_id is not None

        ok = engine.end_run(run_id, "success", exit_code=0, duration_s=120.0)
        assert ok

        state = engine.get_task_state("DEPLOY_PREP")
        assert state["state"] == "succeeded"

        runs = engine.get_runs("DEPLOY_PREP")
        assert len(runs) == 1
        assert runs[0]["outcome"] == "success"
        assert runs[0]["duration_s"] == 120.0

    def test_external_ad_hoc_end_run(self, engine):
        """Ad-hoc external run can be ended even though tag isn't in sidecar."""
        engine.reconcile()
        run_id = engine.start_external_run("[ONEOFF_TASK] One-time task", source="manual_spawn")
        assert run_id is not None

        ok = engine.end_run(run_id, "success", exit_code=0, duration_s=60.0)
        assert ok

        runs = engine.get_runs("ONEOFF_TASK")
        assert len(runs) == 1
        assert runs[0]["outcome"] == "success"

    def test_run_source_field(self, engine):
        """Run records include the source field."""
        engine.reconcile()
        run_id = engine.start_run("URGENT_FIX", source="cron_research")
        runs = engine.get_runs("URGENT_FIX")
        assert len(runs) == 1
        assert runs[0]["source"] == "cron_research"


class TestNoPrDeliveryLoop:
    """Test that repeated no_pr_delivery partial_success auto-defers instead of looping."""

    def test_first_no_pr_delivery_marks_failed(self, engine):
        engine.reconcile()
        run_id = engine.start_run("ENGINE_V2")
        engine.end_run(run_id, "partial_success", error="no_pr_delivery")

        state = engine.get_task_state("ENGINE_V2")
        assert state["state"] == "failed"
        assert "no_pr_delivery" in state["failure_reason"]

    def test_second_no_pr_delivery_auto_defers(self, engine):
        engine.reconcile()

        # First attempt: no_pr_delivery → failed
        run_id1 = engine.start_run("ENGINE_V2")
        engine.end_run(run_id1, "partial_success", error="no_pr_delivery")
        state1 = engine.get_task_state("ENGINE_V2")
        assert state1["state"] == "failed"

        # Second attempt: no_pr_delivery again → auto-deferred
        run_id2 = engine.start_run("ENGINE_V2")
        engine.end_run(run_id2, "partial_success", error="no_pr_delivery")
        state2 = engine.get_task_state("ENGINE_V2")
        assert state2["state"] == "deferred"
        assert "repeated no_pr_delivery" in (state2.get("failure_reason") or "")

    def test_different_error_after_no_pr_does_not_defer(self, engine):
        """Use P0 task (3 retries) to isolate no_pr logic from max-retry auto-defer."""
        engine.reconcile()

        # First: no_pr_delivery
        run_id1 = engine.start_run("URGENT_FIX")
        engine.end_run(run_id1, "partial_success", error="no_pr_delivery")

        # Second: different error — should NOT trigger no_pr loop detection
        run_id2 = engine.start_run("URGENT_FIX")
        engine.end_run(run_id2, "partial_success", error="output_validation: missing tests")
        state = engine.get_task_state("URGENT_FIX")
        assert state["state"] == "failed"
        assert "output_validation" in state["failure_reason"]

    def test_no_pr_loop_does_not_affect_regular_failures(self, engine):
        engine.reconcile()

        run_id = engine.start_run("ENGINE_V2")
        engine.end_run(run_id, "failure", error="import error")
        state = engine.get_task_state("ENGINE_V2")
        assert state["state"] == "failed"
        assert "import error" in state["failure_reason"]


# Need these imports for the recovery tests
from datetime import datetime, timezone
