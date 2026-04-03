"""Clarvis memory layer — episodic, procedural, hebbian, working, consolidation."""

from .episodic_memory import EpisodicMemory  # noqa: F401
from .hebbian_memory import HebbianMemory  # noqa: F401
from .procedural_memory import (  # noqa: F401
    find_procedure, store_procedure, record_use, learn_from_task,
    learn_from_failures, retire_stale, compose_procedures, library_stats,
    list_procedures, find_code_templates, format_code_templates,
)
from .memory_consolidation import (  # noqa: F401
    deduplicate, merge_clusters, enhanced_decay, prune_noise,
    archive_stale, enforce_memory_caps, run_consolidation,
    sleep_consolidate, sleep_stats, get_consolidation_stats,
    attention_guided_prune, attention_guided_decay,
    gwt_broadcast_survivors, salience_report,
    measure_retrieval_quality, retrieval_error_report,
)
