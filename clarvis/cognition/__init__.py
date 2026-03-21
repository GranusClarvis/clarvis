"""Clarvis cognition — attention, confidence, thought protocol, context relevance, self-assessment.

Split into:
  - attention.py: GWT spotlight, salience scoring, codelet competition, attention schema (AST)
  - confidence.py: prediction tracking, Bayesian calibration, Brier scoring
  - thought_protocol.py: ThoughtScript DSL, signal vectors, decision frames
  - context_relevance.py: section relevance scoring, Jaccard overlap, episode-level tracking
  - intrinsic_assessment.py: performance evaluation, failure patterns, autocurriculum
"""

from .confidence import (
    predict,
    outcome,
    calibration,
    dynamic_confidence,
    recalibrate,
)
from .context_relevance import (
    score_section_relevance,
    record_relevance,
    aggregate_relevance,
    get_suppressed_sections,
    refresh_weights,
)
