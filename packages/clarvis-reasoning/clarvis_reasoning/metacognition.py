"""
Pure meta-cognitive primitives for reasoning quality assessment.

No side effects, no storage dependencies. These functions can be
used independently of the ReasoningStore.

Implements:
- Step quality checking (shallow, circular, unsupported, hedging)
- Coherence measurement (word overlap between consecutive steps)
- Session-level quality scoring and grading
- Calibration tracking (Brier score)

References:
    Flavell, J. H. (1979). Metacognition and cognitive monitoring.
    Dunlosky, J. & Metcalfe, J. (2009). Metacognition.
"""

from collections import Counter
from typing import Dict, List, Optional, Tuple

# Stop words excluded from coherence calculations
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "and", "or", "but", "not", "this", "that", "it", "its",
    "we", "i", "you", "they", "he", "she", "will", "would",
    "can", "could", "should", "have", "has", "had", "do", "does",
})

# Hedge words that signal uncertain reasoning
_HEDGE_WORDS = ("maybe", "perhaps", "might", "could possibly", "not sure", "i think")

# Quality grade thresholds
GRADE_GOOD = 0.70
GRADE_ADEQUATE = 0.45
GRADE_SHALLOW = 0.20


def check_step_quality(
    thought: str,
    evidence: List[str],
    confidence: float,
    previous_thoughts: List[str],
) -> List[str]:
    """Check a single reasoning step for quality issues.

    Args:
        thought: The reasoning step's content.
        evidence: Evidence supporting this step.
        confidence: Confidence level (0-1).
        previous_thoughts: Thoughts from previous steps in the session.

    Returns:
        List of quality flag strings (e.g., ["shallow", "unsupported"]).
    """
    flags = []
    thought_lower = thought.lower()

    # Shallow: very short thought with no evidence
    if len(thought) < 30 and not evidence:
        flags.append("shallow")

    # Unsupported: high confidence with no evidence
    if confidence > 0.8 and not evidence:
        flags.append("unsupported")

    # Circular: repeating earlier thoughts (>70% word overlap)
    step_words = set(thought_lower.split()) - _STOP_WORDS
    if len(step_words) >= 5:
        for prev in previous_thoughts:
            prev_words = set(prev.lower().split()) - _STOP_WORDS
            if len(prev_words) >= 5:
                union = prev_words | step_words
                if union:
                    overlap = len(prev_words & step_words) / len(union)
                    if overlap > 0.7:
                        flags.append("circular")
                        break

    # Hedging: too many hedge words
    hedge_count = sum(1 for h in _HEDGE_WORDS if h in thought_lower)
    if hedge_count >= 2:
        flags.append("hedging")

    return flags


def compute_coherence(thoughts: List[str]) -> float:
    """Measure how well reasoning steps build on each other.

    Uses word overlap between consecutive steps as a proxy for coherence.
    Optimal overlap is moderate (0.1-0.4) — too high means repetition,
    too low means disjointed reasoning.

    Args:
        thoughts: List of thought strings in order.

    Returns:
        Coherence score (0.0-1.0). 0.5 for single steps.
    """
    if len(thoughts) < 2:
        return 0.5  # neutral for single step

    overlaps = []
    for i in range(1, len(thoughts)):
        prev_words = set(thoughts[i - 1].lower().split()) - _STOP_WORDS
        curr_words = set(thoughts[i].lower().split()) - _STOP_WORDS
        if prev_words and curr_words:
            union = prev_words | curr_words
            overlap = len(prev_words & curr_words) / max(1, len(union))
            overlaps.append(overlap)

    if not overlaps:
        return 0.5

    # Bell curve centered at 0.25 overlap
    avg_overlap = sum(overlaps) / len(overlaps)
    coherence = 1.0 - 4.0 * (avg_overlap - 0.25) ** 2
    return max(0.0, min(1.0, coherence))


def evaluate_session(
    steps: List[dict],
    sub_problems: List[str],
    predicted_outcome: Optional[str],
    actual_outcome: Optional[str],
) -> dict:
    """Evaluate reasoning quality for a complete session.

    Scores multiple dimensions and assigns a quality grade.

    Args:
        steps: List of step dicts with keys: thought, evidence, confidence,
               sub_problem, quality_flags.
        sub_problems: Declared sub-problems for the task.
        predicted_outcome: Predicted outcome (if any).
        actual_outcome: Actual outcome (if any).

    Returns:
        Evaluation dict with depth, coherence, quality_score, quality_grade,
        issues list, and other metrics.
    """
    if not steps:
        return {"depth": 0, "quality_grade": "empty",
                "quality_score": 0.0, "coherence": 0.0, "issues": ["no_steps"]}

    depth = len(steps)
    confidences = [s.get("confidence", 0.5) for s in steps]
    avg_confidence = sum(confidences) / len(confidences)
    confidence_spread = max(confidences) - min(confidences) if len(confidences) > 1 else 0

    # Evidence coverage
    evidence_coverage = sum(1 for s in steps if s.get("evidence")) / depth

    # Sub-problem coverage
    if sub_problems:
        addressed = set()
        for s in steps:
            sp = s.get("sub_problem", "")
            if sp:
                for declared in sub_problems:
                    if sp.lower() in declared.lower() or declared.lower() in sp.lower():
                        addressed.add(declared)
        sub_problem_coverage = len(addressed) / len(sub_problems)
    else:
        sub_problem_coverage = 1.0

    # Aggregate quality flags
    all_flags = []
    for s in steps:
        all_flags.extend(s.get("quality_flags", []))
    flag_counts = Counter(all_flags)

    # Coherence from thought text
    thoughts = [s.get("thought", "") for s in steps]
    coherence = compute_coherence(thoughts)

    # Detect issues
    issues = []
    if depth < 2:
        issues.append("shallow_reasoning")
    if evidence_coverage < 0.3:
        issues.append("low_evidence")
    if flag_counts.get("circular", 0) > 0:
        issues.append("circular_reasoning")
    if flag_counts.get("unsupported", 0) > 1:
        issues.append("many_unsupported_claims")
    if avg_confidence > 0.95:
        issues.append("overconfident")
    if sub_problem_coverage < 0.5 and sub_problems:
        issues.append("incomplete_decomposition")
    if not actual_outcome and not predicted_outcome:
        issues.append("no_prediction")

    # Composite score
    score = 0.0
    score += min(0.25, depth * 0.05)           # depth: up to 0.25 for 5+ steps
    score += evidence_coverage * 0.25            # evidence: up to 0.25
    score += coherence * 0.25                    # coherence: up to 0.25
    score += sub_problem_coverage * 0.15         # decomposition: up to 0.15
    score += (0.1 if predicted_outcome else 0)   # prediction bonus
    score -= len(issues) * 0.05                  # penalty
    score = max(0.0, min(1.0, score))

    # Grade
    if score >= GRADE_GOOD:
        grade = "good"
    elif score >= GRADE_ADEQUATE:
        grade = "adequate"
    elif score >= GRADE_SHALLOW:
        grade = "shallow"
    else:
        grade = "poor"

    return {
        "depth": depth,
        "avg_confidence": round(avg_confidence, 3),
        "confidence_spread": round(confidence_spread, 3),
        "evidence_coverage": round(evidence_coverage, 3),
        "sub_problem_coverage": round(sub_problem_coverage, 3),
        "coherence": round(coherence, 3),
        "quality_score": round(score, 3),
        "quality_grade": grade,
        "issues": issues,
        "flag_counts": dict(flag_counts),
    }


def brier_score(predictions: List[Tuple[str, float, str]]) -> Optional[float]:
    """Compute Brier score for calibration assessment.

    Lower is better. 0.0 = perfect calibration, 0.25 = random.

    Args:
        predictions: List of (predicted_outcome, confidence, actual_outcome) tuples.

    Returns:
        Brier score (0.0-1.0), or None if no predictions.
    """
    if not predictions:
        return None

    total = 0.0
    for predicted, confidence, actual in predictions:
        hit = 1.0 if predicted == actual else 0.0
        total += (confidence - hit) ** 2

    return round(total / len(predictions), 4)


def diagnose_sessions(sessions: List[dict]) -> dict:
    """Run meta-cognitive diagnosis across multiple sessions.

    Args:
        sessions: List of session dicts (as returned by ReasoningStore.list_sessions
                  or loaded session.to_dict()).

    Returns:
        Diagnostic report with grade distribution, top issues,
        calibration stats, and recommendations.
    """
    if not sessions:
        return {"status": "no_data", "recommendations": ["Start using reasoning sessions"]}

    evaluations = []
    all_issues = []
    depths = []
    predictions = []

    for s in sessions:
        steps = s.get("steps", [])
        ev = evaluate_session(
            steps,
            s.get("sub_problems", []),
            s.get("predicted_outcome"),
            s.get("actual_outcome"),
        )
        evaluations.append(ev)
        all_issues.extend(ev.get("issues", []))
        depths.append(ev["depth"])

        if s.get("predicted_outcome") and s.get("actual_outcome"):
            predictions.append((
                s["predicted_outcome"],
                s.get("predicted_confidence", 0.5),
                s["actual_outcome"],
            ))

    grade_dist = Counter(ev.get("quality_grade", "unknown") for ev in evaluations)
    issue_freq = Counter(all_issues)
    avg_depth = sum(depths) / len(depths) if depths else 0
    deep = sum(1 for d in depths if d >= 3)
    shallow = sum(1 for d in depths if d < 2)
    cal_brier = brier_score(predictions)

    cal_hits = sum(1 for p, _, a in predictions if p == a)
    cal_total = len(predictions)

    recommendations = []
    if avg_depth < 2.5:
        recommendations.append("Increase reasoning depth — most chains too shallow. "
                               "Use decompose() to break tasks into sub-problems.")
    if issue_freq.get("low_evidence", 0) > len(sessions) * 0.3:
        recommendations.append("Add evidence to reasoning steps — too many unsupported claims.")
    if issue_freq.get("circular_reasoning", 0) > 2:
        recommendations.append("Circular reasoning detected — diversify thought approaches.")
    if issue_freq.get("no_prediction", 0) > len(sessions) * 0.5:
        recommendations.append("Use predict() before execution to improve calibration.")
    if shallow > len(sessions) * 0.4:
        recommendations.append(f"{shallow}/{len(sessions)} chains are shallow (<2 steps).")
    if cal_brier is not None and cal_brier > 0.20:
        recommendations.append(f"Calibration is poor (Brier={cal_brier:.3f}). "
                               "Adjust confidence to match actual hit rate.")

    return {
        "status": "analyzed",
        "total_sessions": len(sessions),
        "avg_depth": round(avg_depth, 2),
        "deep_sessions_3plus": deep,
        "shallow_sessions_lt2": shallow,
        "grade_distribution": dict(grade_dist),
        "top_issues": dict(issue_freq.most_common(5)),
        "calibration": {
            "hits": cal_hits,
            "total": cal_total,
            "accuracy": round(cal_hits / cal_total, 3) if cal_total > 0 else None,
            "brier_score": cal_brier,
        },
        "recommendations": recommendations,
    }
