"""
ClarvisReasoning — Meta-cognitive reasoning quality assessment.

Pure functions for evaluating reasoning chains:
- Step quality checking (shallow, circular, unsupported, hedging)
- Coherence measurement between consecutive steps
- Session-level quality scoring and grading
- Calibration tracking via Brier score
- Multi-session diagnostics

Usage:
    from clarvis_reasoning import check_step_quality, evaluate_session, diagnose_sessions

    flags = check_step_quality("My thought", evidence=[], confidence=0.9, previous_thoughts=[])
    result = evaluate_session(steps, sub_problems, predicted, actual)
    report = diagnose_sessions(sessions)
"""

from clarvis_reasoning.metacognition import (
    check_step_quality,
    compute_coherence,
    evaluate_session,
    brier_score,
    diagnose_sessions,
    GRADE_GOOD,
    GRADE_ADEQUATE,
    GRADE_SHALLOW,
)

__version__ = "1.0.0"
__all__ = [
    "check_step_quality",
    "compute_coherence",
    "evaluate_session",
    "brier_score",
    "diagnose_sessions",
    "GRADE_GOOD",
    "GRADE_ADEQUATE",
    "GRADE_SHALLOW",
]
