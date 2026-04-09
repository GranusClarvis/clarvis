"""Clarvis context — compression, assembly, GC, and context building."""
from .compressor import (  # noqa: F401
    tfidf_extract, mmr_rerank, compress_text,
    compress_queue, compress_episodes, get_latest_scores,
    generate_tiered_brief as _simple_tiered_brief,
    prune_stale, snip_middle, graduated_compact,
    compress_health, generate_context_brief,
)
from .prompt_builder import (  # noqa: F401
    get_context_brief, build_prompt, write_prompt_file,
)
from .prompt_optimizer import (  # noqa: F401
    select_variant, record_outcome, get_report as get_optimizer_report,
    get_ab_summary,
)
from .budgets import (  # noqa: F401
    TIER_BUDGETS, get_adjusted_budgets, load_relevance_weights,
    load_section_relevance_weights,
)
from .dycp import (  # noqa: F401
    dycp_prune_brief, should_suppress_section, rerank_knowledge_hints,
)
from .assembly import (  # noqa: F401
    generate_tiered_brief,
    build_decision_context, build_wire_guidance, build_reasoning_scaffold,
    get_failure_patterns, get_workspace_context, get_spotlight_items,
    find_related_tasks, get_recent_completions, get_recommended_procedures,
    build_hierarchical_episodes,
)
from .knowledge_synthesis import synthesize_knowledge  # noqa: F401
from .gc import gc, archive_completed, rotate_logs  # noqa: F401
from .adaptive_mmr import (  # noqa: F401
    get_adaptive_lambda, classify_mmr_category, update_lambdas,
    BASE_LAMBDAS,
)
