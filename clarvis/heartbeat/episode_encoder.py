"""Episode encoding and trajectory scoring for heartbeat postflight.

Canonical module: extracted from heartbeat_postflight.py §5 and §5.01.
"""

import time


def episode_encode(task, task_section, best_salience, task_status, task_duration,
                   error_type, output_text, preflight_data, _pf_errors,
                   *, EpisodicMemory=None, record_trajectory_event=None, log=None):
    """§5 Episode encoding + §5.01 Trajectory scoring.

    Args:
        task: Task description string.
        task_section: Section of the queue the task came from.
        best_salience: Best salience score from attention.
        task_status: "success" or "failure".
        task_duration: Duration in seconds.
        error_type: Classified error type (or None).
        output_text: Raw output text from the executor.
        preflight_data: Dict from preflight JSON.
        _pf_errors: List to append error labels to.
        EpisodicMemory: EpisodicMemory class (or None to skip).
        record_trajectory_event: Trajectory scorer callable (or None to skip).
        log: Logging callable.

    Returns:
        Dict of stage timings.
    """
    if log is None:
        log = lambda msg: None  # noqa: E731
    timings = {}

    # === 5. EPISODIC MEMORY: Encode episode ===
    t5 = time.monotonic()
    if EpisodicMemory:
        try:
            em = EpisodicMemory()
            error_msg = output_text[-200:] if task_status != "success" else None
            em.encode(task, task_section, best_salience, task_status,
                      duration_s=task_duration, error_msg=error_msg,
                      failure_type=error_type)
            latest_ep = em.episodes[-1] if em.episodes else {}
            causal_n = latest_ep.get("causal_links_created", 0)
            causal_info = f", causal_links={causal_n}" if causal_n else ""
            log(f"Encoded episode ({task_status}, {task_duration}s"
                f"{', type=' + error_type if error_type else ''}{causal_info})")
        except Exception as e:
            log(f"Episodic encoding failed: {e}")
            _pf_errors.append("episodic")
    timings["episodic"] = round(time.monotonic() - t5, 3)

    # === 5.01 TRAJECTORY SCORING ===
    t501 = time.monotonic()
    if record_trajectory_event:
        try:
            traj_event = {
                "task": task[:200],
                "task_outcome": task_status,
                "duration_s": task_duration,
                "retrieval_verdict": preflight_data.get("retrieval_verdict", "SKIPPED"),
                "code_validation_errors": 0,
                "tool_call_count": None,
                "error_type": error_type,
                "task_section": task_section,
            }
            scored = record_trajectory_event(traj_event)
            log(f"TRAJECTORY: score={scored['trajectory_score']:.3f} "
                f"(completion={scored['trajectory_components']['completion']:.2f}, "
                f"efficiency={scored['trajectory_components']['efficiency']:.2f}, "
                f"retrieval={scored['trajectory_components']['retrieval_alignment']:.2f})")
        except Exception as e:
            log(f"Trajectory scoring failed (non-fatal): {e}")
    timings["trajectory"] = round(time.monotonic() - t501, 3)

    return timings
