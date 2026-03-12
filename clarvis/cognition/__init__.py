"""Clarvis cognition — attention, confidence, thought protocol, context relevance.

Split into:
  - attention.py: GWT spotlight, salience scoring, codelet competition, attention schema (AST)
  - confidence.py: prediction tracking, Bayesian calibration, Brier scoring
  - thought_protocol.py: ThoughtScript DSL, signal vectors, decision frames
  - context_relevance.py: section relevance scoring, Jaccard overlap, episode-level tracking
"""

from .confidence import (
    predict,
    outcome,
    calibration,
    dynamic_confidence,
)
from .context_relevance import (
    score_section_relevance,
    record_relevance,
    aggregate_relevance,
)
