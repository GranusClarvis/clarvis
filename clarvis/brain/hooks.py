"""Default hook registration for brain recall/optimize pipeline.

External modules (hebbian, actr, attention, retrieval_quality, memory_consolidation,
synaptic) register as hooks rather than being imported directly by brain — this
breaks the circular SCC.

Call register_default_hooks(brain_instance) once after brain initialization to
wire up all available hooks. Missing modules are silently skipped.
"""

import logging
import os
import sys
import time

_log = logging.getLogger("clarvis.brain.hooks")

_SCRIPTS_DIR = os.path.join(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"), "scripts")


def _make_actr_scorer():
    """Create an ACT-R scorer hook: fn(results) -> mutates with _actr_score.

    Gated by CLARVIS_ACTR_RECALL=1 env var for A/B comparison.
    When disabled, raises RuntimeError so search.py falls through to
    the distance+importance fallback scorer.
    """
    import os
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    from actr_activation import actr_score

    def scorer(results):
        if os.environ.get("CLARVIS_ACTR_RECALL") != "1":
            raise RuntimeError("ACTR scoring disabled (set CLARVIS_ACTR_RECALL=1)")
        for r in results:
            boost = r["metadata"].get("_attention_boost", 0)
            r["_actr_score"] = actr_score(r) + boost * 0.15
    return scorer


def _make_attention_booster():
    """Create an attention boost hook: fn(results) -> mutates with _attention_boost."""
    from clarvis.cognition.attention import attention as attn

    def booster(results):
        spotlight_words = set()
        for s_item in attn.focus():
            spotlight_words.update(s_item["content"].lower().split())
        for result in results:
            doc_words = set(result["document"].lower().split())
            overlap = len(spotlight_words & doc_words)
            if overlap > 0:
                boost = min(0.3, overlap * 0.05)
                result["metadata"]["_attention_boost"] = boost
    return booster


def _make_retrieval_quality_observer():
    """Create a retrieval quality observer hook."""
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    from retrieval_quality import tracker

    def observer(query, results, *, caller=None, rate_limit_mono=0, last_mono=0):
        if caller and query:
            tracker.on_recall(query, results, caller=caller)
    return observer


def _make_hebbian_observer():
    """Create a hebbian learning observer hook (rate-limited)."""
    from clarvis.memory.hebbian_memory import hebbian

    def observer(query, results, *, caller=None, rate_limit_mono=0, last_mono=0):
        if (rate_limit_mono - last_mono) >= 5.0:
            hebbian.on_recall(query, results, caller=caller)
    return observer


def _make_synaptic_observer():
    """Create a synaptic memory observer hook (rate-limited)."""
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    from synaptic_memory import synaptic

    def observer(query, results, *, caller=None, rate_limit_mono=0, last_mono=0):
        if (rate_limit_mono - last_mono) >= 5.0:
            synaptic.on_recall(query, results, caller=caller)
    return observer


def _make_consolidation_hook():
    """Create an optimization hook for memory consolidation."""
    from clarvis.memory.memory_consolidation import deduplicate, prune_noise, archive_stale

    def hook(dry_run=False):
        dedup_result = deduplicate(dry_run=dry_run)
        noise_result = prune_noise(dry_run=dry_run)
        archive_result = archive_stale(dry_run=dry_run)
        return {
            "duplicates_removed": dedup_result.get("duplicates_removed", 0),
            "noise_pruned": noise_result.get("pruned", 0),
            "archived": archive_result.get("archived", 0),
        }
    return hook


def _make_graphrag_booster():
    """Create a GraphRAG community context booster.

    When CLARVIS_GRAPHRAG_BOOST=1, appends community context keywords to
    result metadata so downstream consumers see broader thematic context.
    No-op when disabled (default).
    """
    import os
    from clarvis.brain.graphrag import enhanced_local_search, COMMUNITIES_FILE, SUMMARIES_FILE

    def booster(results):
        if os.environ.get("CLARVIS_GRAPHRAG_BOOST") != "1":
            return
        if not os.path.exists(COMMUNITIES_FILE) or not os.path.exists(SUMMARIES_FILE):
            return
        if not results:
            return

        # Load community mappings once per call
        import json
        with open(COMMUNITIES_FILE, 'r') as f:
            communities = json.load(f)
        with open(SUMMARIES_FILE, 'r') as f:
            summaries = json.load(f)

        node_comms = communities.get("node_community", {})
        level = "C1"
        level_summaries = summaries.get("levels", {}).get(level, {})

        seen_comms = set()
        for result in results:
            rid = result.get("id", "")
            comm_info = node_comms.get(rid, {})
            comm_id = comm_info.get(level)
            if comm_id and comm_id not in seen_comms:
                seen_comms.add(comm_id)
                comm_data = level_summaries.get(comm_id)
                if comm_data:
                    result["metadata"]["_graphrag_community"] = comm_id
                    result["metadata"]["_graphrag_keywords"] = comm_data.get("keywords", [])[:6]
    return booster


# Registry of (name, factory, registration_method)
_HOOK_DEFS = [
    ("actr_scorer", _make_actr_scorer, "register_recall_scorer"),
    ("attention_booster", _make_attention_booster, "register_recall_booster"),
    ("graphrag_booster", _make_graphrag_booster, "register_recall_booster"),
    ("retrieval_quality", _make_retrieval_quality_observer, "register_recall_observer"),
    ("hebbian", _make_hebbian_observer, "register_recall_observer"),
    ("synaptic", _make_synaptic_observer, "register_recall_observer"),
    ("consolidation", _make_consolidation_hook, "register_optimize_hook"),
]


def register_default_hooks(brain_instance):
    """Register all available hooks with a brain instance.

    Silently skips any modules that aren't importable. Idempotent:
    checks _hooks_registered flag to avoid double registration.

    Returns:
        dict: {hook_name: True/False} for each hook attempted.
    """
    if getattr(brain_instance, '_hooks_registered', False):
        return {"status": "already_registered"}

    results = {}
    for name, factory, method_name in _HOOK_DEFS:
        try:
            fn = factory()
            getattr(brain_instance, method_name)(fn)
            results[name] = True
        except Exception as e:
            results[name] = False
            _log.debug("Hook '%s' failed to register: %s", name, e)

    registered = [n for n, ok in results.items() if ok]
    failed = [n for n, ok in results.items() if not ok]
    summary = f"Registered {len(registered)}/{len(results)} hooks"
    if failed:
        summary += f" (failed: {', '.join(failed)})"
    _log.info(summary)
    # Also print for cron visibility (stderr often captured in logs)
    print(f"[hooks] {summary}", file=sys.stderr)

    brain_instance._hooks_registered = True
    return results
