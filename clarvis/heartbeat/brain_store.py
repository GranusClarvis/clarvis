"""Brain storage for heartbeat postflight — failure lessons and outcome recording.

Canonical module: extracted from heartbeat_postflight.py §2.5 and §2.7.
"""

import json
import os
import re
import time


def store_failure_lesson(task, exit_code, output_text, error_type,
                         *, brain_mod=None, mem_evo_find_contradictions=None,
                         mem_evo_evolve=None, log=None):
    """Store a failure lesson in brain and run contradiction checks.

    Args:
        task: Task description.
        exit_code: Process exit code.
        output_text: Raw output text.
        error_type: Classified error type.
        brain_mod: Brain instance (or None to auto-import).
        mem_evo_find_contradictions: Contradiction finder callable.
        mem_evo_evolve: Memory evolution callable.
        log: Logging callable.
    """
    if log is None:
        log = lambda msg: None  # noqa: E731

    error_snippet = output_text[-300:] if output_text else "no output"
    error_snippet = re.sub(r'[^a-zA-Z0-9 _.,:;=+\-/()@#%\n]', '', error_snippet)[:250]
    lesson = (f"FAILURE LESSON [{error_type}]: Attempted '{task[:100]}' "
              f"— exit {exit_code}. Error: {error_snippet}")

    if brain_mod is None:
        try:
            from clarvis.brain import brain as brain_mod
        except ImportError:
            pass
    if not brain_mod:
        return

    brain_mod.store(lesson, collection="clarvis-learnings", importance=0.8,
                    tags=["failure", "lesson", f"error_type:{error_type}"],
                    source="postflight_failure")
    log("Stored failure lesson in brain")

    if mem_evo_find_contradictions and mem_evo_evolve:
        try:
            contras = mem_evo_find_contradictions(
                brain_mod, lesson, "clarvis-learnings", threshold=0.4, top_n=3)
            for c in contras[:2]:
                evo = mem_evo_evolve(brain_mod, c["id"], c["collection"],
                                     lesson, reason="contradiction")
                if evo.get("evolved"):
                    log(f"MEMORY EVOLUTION: Evolved {c['id']} → {evo['new_id']} "
                        f"(contradiction: {c['contradiction_signal'][:3]})")
        except Exception as e:
            log(f"Contradiction check failed (non-fatal): {e}")


def brain_store(task, task_status, exit_code, output_text, error_type,
                task_duration, _pf_errors, retry_file,
                *, brain_record_outcome=None, brain_update_context=None,
                mem_evo_find_contradictions=None, mem_evo_evolve=None, log=None):
    """§2.5 Failure lessons + §2.7 Brain bridge outcome recording.

    Args:
        task: Task description.
        task_status: "success" or "failure".
        exit_code: Process exit code.
        output_text: Raw output text.
        error_type: Classified error type.
        task_duration: Duration in seconds.
        _pf_errors: List to append error labels to.
        retry_file: Path to retry tracking JSON file.
        brain_record_outcome: Brain bridge recorder callable.
        brain_update_context: Brain bridge context updater callable.
        mem_evo_find_contradictions: Contradiction finder callable.
        mem_evo_evolve: Memory evolution callable.
        log: Logging callable.

    Returns:
        Dict of stage timings.
    """
    if log is None:
        log = lambda msg: None  # noqa: E731
    timings = {}

    t25 = time.monotonic()
    if task_status == "failure" and exit_code != 0 and exit_code != 124:
        try:
            store_failure_lesson(task, exit_code, output_text, error_type,
                                 mem_evo_find_contradictions=mem_evo_find_contradictions,
                                 mem_evo_evolve=mem_evo_evolve, log=log)
            # Generate follow-up if not too many prior failures
            retry_data = {}
            if os.path.exists(retry_file):
                try:
                    with open(retry_file) as rf:
                        retry_data = json.load(rf)
                except Exception:
                    pass
            task_key = task[:80]
            if retry_data.get(task_key, 0) < 2:
                try:
                    from clarvis.queue.writer import add_task
                    followup = (f"Investigate failure: '{task[:80]}' failed with "
                                f"exit {exit_code}. Check logs and fix root cause.")
                    if add_task(followup, priority="P1", source="reasoning_failure"):
                        log("Generated follow-up investigation task")
                except ImportError:
                    pass
            else:
                log(f"Skipped follow-up task — {task_key[:40]}... "
                    f"failed {retry_data.get(task_key, 0)}+ times")
        except Exception as e:
            log(f"Failure lesson recording failed: {e}")
            _pf_errors.append("failure_lessons")
    timings["failure_lessons"] = round(time.monotonic() - t25, 3)

    t27 = time.monotonic()
    if brain_record_outcome:
        try:
            mem_id = brain_record_outcome(task, task_status, output_text, task_duration)
            if mem_id:
                log(f"Brain bridge: recorded {task_status} outcome → {mem_id}")
        except Exception as e:
            log(f"Brain bridge outcome recording failed: {e}")
            _pf_errors.append("brain_bridge")
    if brain_update_context:
        try:
            brain_update_context(task, task_status)
            log("Brain bridge: context updated")
        except Exception as e:
            log(f"Brain bridge context update failed: {e}")
            _pf_errors.append("brain_bridge_ctx")
    timings["brain_bridge"] = round(time.monotonic() - t27, 3)

    return timings
