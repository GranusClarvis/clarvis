"""Clarvis cognition — attention, confidence, thought protocol, context relevance, self-assessment,
cognitive load monitoring, and GWT workspace broadcast.

Split into:
  - attention.py: GWT spotlight, salience scoring, codelet competition, attention schema (AST)
  - confidence.py: prediction tracking, Bayesian calibration, Brier scoring
  - thought_protocol.py: ThoughtScript DSL, signal vectors, decision frames
  - context_relevance.py: section relevance scoring, Jaccard overlap, episode-level tracking
  - intrinsic_assessment.py: performance evaluation, failure patterns, autocurriculum
  - cognitive_load.py: homeostatic load regulation, task complexity estimation
  - workspace_broadcast.py: GWT-3 LIDA cycle (collect, coalesce, compete, broadcast)
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
from .attention import (  # noqa: F401
    AttentionSpotlight, AttentionCodelet, CodeletCompetition,
    AttentionSchema, AttentionItem,
    get_attention, get_codelet_competition, get_attention_schema,
)
from .intrinsic_assessment import (  # noqa: F401
    assess_recent, detect_failure_patterns, generate_autocurriculum,
    inject_autocurriculum, full_assessment,
)
from .cognitive_load import (  # noqa: F401
    compute_load, should_defer_task, estimate_task_complexity, log_sizing,
    measure_failure_rate, measure_queue_velocity, measure_cron_times,
    measure_capability_degradation, record_load, get_history,
)
from .workspace_broadcast import (  # noqa: F401
    WorkspaceBroadcast, Codelet, Coalition, get_workspace,
)
from .obligations import (  # noqa: F401
    ObligationTracker, seed_defaults, run_verification,
)
