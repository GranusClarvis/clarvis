"""Episode encoding and trajectory scoring for heartbeat postflight.

Canonical module: extracted from heartbeat_postflight.py §5 and §5.01.
"""

import time


def _confidence_band(confidence):
    """Bucket a numeric confidence into low|medium|high.

    Returns None if confidence is not a finite float in [0, 1].
    """
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= c <= 1.0):
        return None
    if c < 0.5:
        return "low"
    if c < 0.8:
        return "medium"
    return "high"


def _derive_calibration(conf_outcome_result, log):
    """Derive (calibration_score, confidence_band) from a conf_outcome() return.

    Brier-style score: 1.0 - (confidence - int(correct))**2.
    Returns (None, None, reason) where reason is a short string when skipped.
    """
    if conf_outcome_result is None:
        return None, None, "conf_outcome=None"
    if not isinstance(conf_outcome_result, dict):
        return None, None, f"conf_outcome bad type ({type(conf_outcome_result).__name__})"
    confidence = conf_outcome_result.get("confidence")
    correct = conf_outcome_result.get("correct")
    if confidence is None or correct is None:
        return None, None, "conf_outcome missing confidence/correct"
    try:
        c = float(confidence)
        truth = 1.0 if bool(correct) else 0.0
        cal = round(1.0 - (c - truth) ** 2, 4)
    except (TypeError, ValueError) as e:
        return None, None, f"calibration calc error: {e}"
    band = _confidence_band(c)
    return cal, band, None


def episode_encode(task, task_section, best_salience, task_status, task_duration,
                   error_type, output_text, preflight_data, _pf_errors,
                   *, EpisodicMemory=None, record_trajectory_event=None, log=None,
                   conf_outcome_result=None):
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
        conf_outcome_result: Optional dict returned by
            clarvis.cognition.confidence.outcome() — used to derive
            calibration_score and confidence_band on the episode.

    Returns:
        Dict of stage timings.
    """
    if log is None:
        log = lambda msg: None  # noqa: E731
    timings = {}

    cal_score, conf_band, skip_reason = _derive_calibration(conf_outcome_result, log)
    if skip_reason:
        log(f"Calibration field skipped: {skip_reason}")

    # === 5. EPISODIC MEMORY: Encode episode ===
    t5 = time.monotonic()
    if EpisodicMemory:
        try:
            em = EpisodicMemory()
            error_msg = output_text[-200:] if task_status != "success" and output_text else None
            em.encode(task, task_section, best_salience, task_status,
                      duration_s=task_duration, error_msg=error_msg,
                      failure_type=error_type,
                      output_text=output_text[-2000:] if output_text else None,
                      calibration_score=cal_score,
                      confidence_band=conf_band)
            latest_ep = em.episodes[-1] if em.episodes else {}
            causal_n = latest_ep.get("causal_links_created", 0)
            causal_info = f", causal_links={causal_n}" if causal_n else ""
            cal_info = ""
            if cal_score is not None:
                cal_info = f", cal={cal_score:.3f}/{conf_band}"
            log(f"Encoded episode ({task_status}, {task_duration}s"
                f"{', type=' + error_type if error_type else ''}{causal_info}{cal_info})")
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
