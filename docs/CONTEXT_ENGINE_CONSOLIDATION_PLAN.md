# Context Engine Consolidation Plan

_Function-by-function diff of `scripts/context_compressor.py` vs `clarvis/context/assembly.py` + `clarvis/context/compressor.py`._
_Produced: 2026-03-23. Phase 3 of `SPINE_CLEANUP_PLAN.md`._

---

## Summary

Three files implement the context engine:

| File | Role | Functions | Lines |
|------|------|-----------|-------|
| `scripts/context_compressor.py` | Legacy monolith — compression, assembly, GC | 24 | ~1400 |
| `clarvis/context/compressor.py` | Spine — compression primitives | ~12 | ~390 |
| `clarvis/context/assembly.py` | Spine — advanced assembly, DyCP, semantic ranking | 34 | ~1900 |

**Runtime authority** lives in both places today: `heartbeat_preflight.py` imports `generate_tiered_brief` from the **legacy** script, but also imports `dycp_prune_brief` from **assembly.py**. The legacy `generate_tiered_brief` itself delegates to assembly.py for `build_reasoning_scaffold` and `rerank_knowledge_hints`. This split authority is the main risk.

---

## Function-by-Function Diff

### Category 1: Exact Duplicates (safe to remove from legacy)

These exist identically in both `scripts/context_compressor.py` and `clarvis/context/compressor.py`:

| Function | Legacy line | Spine location | Notes |
|----------|------------|----------------|-------|
| `_tokenize` | 59 | compressor.py:40 | Identical |
| `_jaccard_similarity` | 64 | compressor.py:45 | Identical |
| `_split_sentences` | 153 | compressor.py:55 | Identical |
| `tfidf_extract` | 169 | compressor.py:128 | Identical |
| `compress_text` | 243 | compressor.py:181 | Identical |
| `compress_queue` | 283 | compressor.py:215 | Identical |
| `compress_episodes` | 468 | compressor.py:284 | **Different signatures** — legacy takes `(similar_text, failure_text)`, spine takes `(episodes_list, max_items)`. Both are used. |
| `get_latest_scores` | 506 | compressor.py:309 | Identical |
| `mmr_rerank` | 74 | compressor.py:70 | Spine version slightly cleaner but functionally identical |

**Action**: After migrating callers, these can be removed from legacy. `compress_episodes` needs signature reconciliation first.

### Category 2: Legacy Functions with Spine Equivalents (evolved)

These exist in both, but the spine version is more advanced:

| Legacy function | Legacy line | Spine equivalent | Spine file | Difference |
|----------------|------------|------------------|------------|------------|
| `_build_decision_context` | 641 | `build_decision_context` | assembly.py:571 | Spine version has richer extraction, vocabulary enrichment, CLR-driven constraints. **Spine is authoritative.** |
| `_get_failure_patterns` | 705 | `get_failure_patterns` | assembly.py:536 | Spine adds task-similarity filtering. **Spine is authoritative.** |
| `_detect_wire_task` | 750 | `_detect_wire_task` | assembly.py:443 | Functionally identical. |
| `_build_wire_guidance` | 786 | `build_wire_guidance` | assembly.py:476 | Spine version has richer target-specific guidance. **Spine is authoritative.** |
| `_build_reasoning_scaffold` | 914 | `build_reasoning_scaffold` | assembly.py:822 | Legacy already delegates to spine with fallback. **Spine is authoritative.** |
| `_get_workspace_context` | 940 | `get_workspace_context` | assembly.py:833 | Nearly identical. |
| `_get_spotlight_items` | 957 | `get_spotlight_items` | assembly.py:849 | Spine version adds dedup. **Spine is authoritative.** |
| `_find_related_tasks` | 1002 | `find_related_tasks` | assembly.py:1189 | Spine version uses semantic similarity + embeddings + dependency extraction + enrichment. **Spine is far more advanced.** |
| `_get_recent_completions` | 1044 | `get_recent_completions` | assembly.py:1547 | Nearly identical. |
| `generate_tiered_brief` | 1070 | `generate_tiered_brief` | assembly.py:1892 | **Both are runtime-active.** Legacy is called by heartbeat_preflight. Spine version has DyCP, adaptive budgets, hierarchical episodes, semantic reranking, procedure recommendations. **Spine is far more advanced but not yet wired as the heartbeat entrypoint.** |
| `TIER_BUDGETS` | 607 | `TIER_BUDGETS` | assembly.py:180 | Spine version has different allocations (merged metrics into decision_context, larger episode budgets). **Spine is authoritative.** |

### Category 3: Unique to Legacy (no spine equivalent)

| Function | Legacy line | Purpose | Migration plan |
|----------|------------|---------|----------------|
| `compress_health` | 379 | Compress multi-line health script output to key=value | Move to `clarvis/context/compressor.py` — it's a pure compression function |
| `generate_context_brief` | 545 | Simple queue+scores brief (v1, pre-tiered) | **Candidate for removal** — superseded by `generate_tiered_brief(tier="minimal")`. Only used by `performance_benchmark.py` and `heartbeat_preflight.py` (which also imports the tiered version). |
| `archive_completed` | 1222 | Move old completed QUEUE.md tasks to archive | Move to `clarvis/context/compressor.py` or a new `clarvis/context/gc.py` — it's a maintenance utility, not assembly |
| `rotate_logs` | 1307 | Rotate oversized cron logs, gzip old memory files | Same as above — maintenance utility |
| `gc` | 1380 | CLI entry: `archive_completed` + `rotate_logs` | Same — maintenance/CLI |

### Category 4: Unique to Spine (no legacy equivalent)

Assembly.py has 15+ functions with no legacy counterpart. These are all net-new capabilities:

- `_compute_dynamic_suppress`, `load_relevance_weights`, `get_adjusted_budgets`, `should_suppress_section` — adaptive budget system
- `_dycp_task_containment_fast`, `_dycp_task_containment`, `_load_historical_section_means`, `dycp_prune_brief` — Dynamic Context Pruning
- `_classify_task_type` — task type classification for scaffold selection
- `_parse_queue_tasks`, `_extract_actionable_context`, `_enrich_task`, `_cosine_similarity`, `_extract_shared_artifacts`, `_format_related_task`, `_semantic_rank`, `_word_overlap_rank`, `_extract_task_dependencies` — semantic task matching
- `_get_similar_failure_lessons`, `build_hierarchical_episodes`, `rerank_episodes_by_task` — episode hierarchy
- `get_recommended_procedures` — procedure recommendation
- `_extract_task_keywords`, `rerank_knowledge_hints` — knowledge reranking

---

## Active Callers (Runtime Authority Map)

| Caller | Imports from legacy | Imports from spine | Notes |
|--------|--------------------|--------------------|-------|
| `heartbeat_preflight.py` | `generate_context_brief`, `generate_tiered_brief`, `compress_episodes` | `dycp_prune_brief` (assembly) | **Primary runtime path.** Legacy `generate_tiered_brief` is the entrypoint, but it delegates to assembly for scaffold + knowledge reranking. |
| `evolution_preflight.py` | `compress_queue`, `compress_health` | — | Only uses compression primitives |
| `prompt_builder.py` | `compress_queue` | — | Only uses compression primitive |
| `brain_bridge.py` | `mmr_rerank` | `get_adaptive_lambda` (adaptive_mmr) | Mixed |
| `performance_benchmark.py` | `generate_tiered_brief`, `compress_text`, `compress_queue`, `get_latest_scores` | — | Uses legacy for benchmarking |
| `brief_benchmark.py` | `generate_tiered_brief` | — | Benchmarks the legacy entrypoint |
| `clarvis/adapters/openclaw.py` | — | `generate_tiered_brief` (assembly) | Uses spine directly |
| `clarvis/metrics/quality.py` | — | `generate_tiered_brief` (compressor) | Uses spine directly |

---

## Safe Migration Order

### Wave 1: Move unique legacy utilities to spine (no caller changes)

1. Move `compress_health` → `clarvis/context/compressor.py`
2. Move `archive_completed`, `rotate_logs`, `gc` → new `clarvis/context/gc.py`
3. Update legacy to import from spine (thin wrapper)
4. **Test**: `python3 -c "from clarvis.context.compressor import compress_health"` + existing tests

### Wave 2: Reconcile `compress_episodes` signature

1. The legacy signature `(similar_text, failure_text)` is used by `heartbeat_preflight.py`
2. The spine signature `(episodes_list, max_items)` is used by `clarvis/metrics/quality.py`
3. **Decision needed**: Keep both signatures (overloaded) or standardize. Recommend: add the text-based signature to spine as `compress_episodes_text()`, keep list-based as `compress_episodes()`.

### Wave 3: Switch heartbeat_preflight to spine `generate_tiered_brief`

This is the **highest-risk, highest-value** migration:

1. Assembly.py's `generate_tiered_brief` is strictly superior (DyCP, adaptive budgets, hierarchical episodes, semantic reranking, procedures)
2. **Precondition**: Verify assembly.py's version produces equivalent or better output for the same inputs
3. **Steps**:
   a. Add a shadow-run: call both, log diff stats (size, section count) for 5-10 heartbeats
   b. If diffs are acceptable, switch `heartbeat_preflight.py` to import from `clarvis.context.assembly`
   c. Remove `generate_context_brief` (v1) from legacy — it's fully superseded
4. **Rollback**: Revert the import line in `heartbeat_preflight.py`

### Wave 4: Convert legacy to thin wrapper

After Waves 1-3, the legacy script should only contain:
- Re-exports from `clarvis.context.compressor` and `clarvis.context.assembly`
- The CLI `__main__` block (for `python3 context_compressor.py brief/queue/health/gc`)

### Wave 5: Deprecate and remove legacy

1. Update all remaining callers to import from `clarvis.context.*`
2. Add deprecation warning to legacy imports
3. After 1 week with no legacy import hits in logs, delete the file

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Heartbeat breaks during Wave 3 | Shadow-run comparison first; single-line rollback |
| `compress_episodes` signature mismatch | Create separate functions, don't overload |
| Legacy CLI (`gc`, `brief`) stops working | Keep `__main__` block in legacy as thin wrapper |
| Tests reference legacy directly | `test_critical_paths.py` tests legacy functions — update imports after Wave 4 |
| Cron jobs call `context_compressor.py gc` directly | Keep CLI working via wrapper until cron entrypoints migrate |

---

## Do Not Touch (until this plan completes)

- `clarvis/context/assembly.py` — active spine authority for advanced assembly
- `clarvis/context/compressor.py` — active spine authority for compression primitives
- `heartbeat_preflight.py` imports — change only in Wave 3 with shadow-run validation
- `TIER_BUDGETS` in either file — spine version is authoritative, legacy version is active

---

_This plan is a prerequisite for `LEGACY_IMPORT_MIGRATION_PHASE1` and `LEGACY_SCRIPT_WRAPPER_REDUCTION`._
