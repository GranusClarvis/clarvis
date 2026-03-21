"""Clarvis context — compression, assembly, GC, and context building."""
from .compressor import (  # noqa: F401
    tfidf_extract, mmr_rerank, compress_text,
    compress_queue, compress_episodes, get_latest_scores,
    generate_tiered_brief as _simple_tiered_brief,
)
from .assembly import (  # noqa: F401
    generate_tiered_brief, rerank_knowledge_hints,
    build_decision_context, build_wire_guidance, build_reasoning_scaffold,
    get_failure_patterns, get_workspace_context, get_spotlight_items,
    find_related_tasks, get_recent_completions, get_recommended_procedures,
    build_hierarchical_episodes,
    TIER_BUDGETS,
)
from .knowledge_synthesis import synthesize_knowledge  # noqa: F401
from .gc import gc, archive_completed, rotate_logs  # noqa: F401
from .adaptive_mmr import (  # noqa: F401
    get_adaptive_lambda, classify_mmr_category, update_lambdas,
    BASE_LAMBDAS,
)
