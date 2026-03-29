# Long-Function Decomposition Campaign — Complete Audit Report

**Date**: 2026-03-29
**Auditor**: Claude Code Opus (executive function)
**Scope**: Every file touched by the DECOMPOSE_LONG_FUNCTIONS refactor campaign across full git history

---

## Executive Summary

**12 commits** touched **33 unique files** across the decomposition campaign. After detailed audit:

| Metric | Count |
|--------|-------|
| Files with actual code decomposition | 17 |
| Files with comment-only changes | 16 |
| Files that were new (not decompositions) | 2 |
| Total functions decomposed | ~85 helpers extracted |
| **Verdict: Keep** | 74 |
| **Verdict: Partially recombine** | 8 |
| **Verdict: Revert/inline** | 1 |
| **Bugs found** | 1 (silent data-loss in brain search fallback) |

**Overall assessment**: The campaign was a net positive. The vast majority of decompositions improved clarity by breaking 100-350 line monoliths into well-named helpers with single responsibilities. A small number (~9) of extractions were over-fragmented (sub-20 line functions called from exactly one place). One critical bug was introduced during extraction.

---

## Prioritized Remediation Plan

### P0 — Bug Fix (Critical)

| File | Issue | Action |
|------|-------|--------|
| `clarvis/brain/search.py` | `_query_single_collection` lost the `query` parameter during extraction. Lines 339/345 pass `query_texts=[""]` instead of actual query. Text-search fallback is silently broken. | Add `query: str` param, pass through from `_dispatch_collection_queries`, replace `""` with `query` |

### P1 — Recombine Over-Fragmented Helpers

| File | Functions to Recombine | Rationale |
|------|----------------------|-----------|
| `clarvis/brain/search.py` | Merge `_apply_recency_scores` (18L) + `_sort_results` (23L) back into `_score_and_sort` | Single-caller sub-helpers; combined ~80L is within target |
| `clarvis/brain/search.py` | Inline `_finalize_recall` (17L) back into `recall()` | Was only 11 lines of inline code before extraction; adds indirection for no gain |
| `scripts/heartbeat_preflight.py` | Merge `_preflight_reasoning_chain` (~17L), `_preflight_routing` (~15L), `_preflight_compress_episodes` (~13L) back into their calling phases | Trivially small try/except wrappers called once each |
| `scripts/daily_brain_eval.py` | Merge `_score_usefulness` (9L), `_score_failures` (12L), `_score_trends` (13L), `_score_speed` (11L) back into `_assess_quality()` | Tightly coupled scoring pipeline; identical pattern; combined ~45L |
| `scripts/heartbeat_postflight.py` | Merge `_pf_prompt_optimization` (15L) + `_pf_prediction_resolve` (33L) into single `_pf_prompt_and_prediction` | Both small, consecutive, void-returning; reduces from 5 to 4 sub-functions |

### P2 — Minor Quality Improvements

| File | Issue | Action |
|------|-------|--------|
| `scripts/heartbeat_postflight.py` | `_mark_task_in_queue` shim: bare `except Exception: return False` swallows all errors silently | Add `log()` call in except clause |
| `scripts/heartbeat_preflight.py` | `_preflight_assemble_context` takes 16 positional arguments | Refactor to context-builder dataclass |
| `clarvis/cognition/context_relevance.py` | `_weighted_means()` uses over-abbreviated variable names (`sec_w`, `suc_sum`) | Expand to readable names |

---

## Detailed Audit by File

### Tier 1: Largest Decompositions (>100 lines reduced)

#### 1. `clarvis/brain/search.py` — `recall()` 348→81 lines
**Commits**: 7e133b7, f302f7a

| Helper Extracted | Lines | Quality | Verdict |
|-----------------|-------|---------|---------|
| `_resolve_recall_params` | 24 | Improved clarity | Keep |
| `_compute_temporal_cutoff` | 17 | Improved clarity | Keep |
| `_get_or_compute_embedding` | 31 | Improved clarity | Keep |
| `_query_single_collection` | 44 | **Fragmented + BUG** | Keep, fix bug |
| `_dispatch_collection_queries` | 39 | Neutral | Keep |
| `_supplement_chronological` | 26 | Improved clarity | Keep |
| `_score_and_sort` | 39 | Neutral | Keep |
| `_apply_recency_scores` | 18 | Fragmented | **Recombine** into `_score_and_sort` |
| `_sort_results` | 23 | Fragmented | **Recombine** into `_score_and_sort` |
| `_fire_recall_observers` | 23 | Improved clarity | Keep |
| `_finalize_recall` | 17 | Fragmented | **Revert** (inline back) |

**Bug**: `_query_single_collection` does not receive the `query` string. The `else` branch (no embedding) calls `col.query(query_texts=[""])` — silently broken text-search fallback.

---

#### 2. `scripts/heartbeat_preflight.py` — `run_preflight()` 1120→60 lines
**Commit**: 23b767e

| Helper Extracted | Lines | Quality | Verdict |
|-----------------|-------|---------|---------|
| `_check_lock_conflict` | 29 | Improved clarity | Keep |
| `_try_auto_split` | 28 | Improved clarity | Keep |
| `_check_candidate_gates` | 45 | Improved clarity | Keep |
| `_evaluate_candidates` | 26 | Improved clarity | Keep |
| `_preflight_attention` | 38 | Improved clarity | Keep |
| `_gather_candidates` | 27 | Neutral | Keep |
| `_preflight_select_task` | 65 | Improved clarity | Keep |
| `_make_preflight_result` | 16 | Improved clarity | Keep |
| `_preflight_load_sizing` | 35 | Neutral | Keep |
| `_preflight_procedural` | 53 | Neutral | Keep |
| `_preflight_reasoning_chain` | 17 | Fragmented | **Recombine** |
| `_preflight_confidence_world_model` | 35 | Neutral | Keep |
| `_preflight_confidence_tier` | 40 | Neutral | Keep |
| `_preflight_gwt_retrieval_gate` | 38 | Neutral | Keep |
| `_preflight_episodic` | 28 | Neutral | Keep |
| `_preflight_brain_bridge` | 55 | Neutral | Keep |
| `_preflight_introspection_synaptic` | 39 | Neutral | Keep |
| `_preflight_routing` | 15 | Fragmented | **Recombine** |
| `_preflight_compress_episodes` | 13 | Fragmented | **Recombine** |
| `_preflight_generate_brief` | 25 | Neutral | Keep |
| `_preflight_append_supplementary` | 56 | Neutral | Keep |
| `_preflight_insights_prompt_workspace` | 50 | Neutral | Keep |
| `_preflight_pruning_obligations_directives` | 46 | Improved clarity | Keep |
| `_preflight_assemble_context` | 30 | Improved clarity | Keep (fix signature) |

**Concerns**: 3 trivially small helpers; 16-argument function signature on `_preflight_assemble_context`.

---

#### 3. `clarvis/orch/task_selector.py` — `score_tasks()` 284→55 lines
**Commit**: 94dcab5

| Helper Extracted | Lines | Quality | Verdict |
|-----------------|-------|---------|---------|
| `_fetch_task_context` | 29 | Improved clarity | Keep |
| `_fetch_failure_lessons` | 16 | Improved clarity | Keep |
| `_is_cr_boost_active` | 10 | Improved clarity | Keep |
| `_keyword_boost` | 5 | Improved clarity (DRY) | Keep |
| `_compute_relevance` | 18 | Improved clarity | Keep |
| `_compute_task_boosts` | 50 | Neutral | Keep |
| `_score_single_task` | 52 | Improved clarity | Keep |
| `_apply_delivery_lock` | 13 | Improved clarity | Keep |
| `_enforce_p0_floor` | 13 | Improved clarity | Keep |
| `_apply_world_model_reranking` | 18 | Improved clarity | Keep |

All 10 extractions are keep. Clean pipeline decomposition.

---

#### 4. `scripts/self_representation.py` — `encode_self_state()` 230→18 lines
**Commit**: b7f294d

10 `_encode_<dimension>()` functions extracted + `_DIMENSION_ENCODERS` registry. Each returns `(score, detail_string)`. Main function is a 3-line loop.

**Quality**: Improved clarity — strongest decomposition in the entire campaign. Eliminated 10 repetitive try/except blocks. **Verdict**: Keep all.

---

#### 5. `scripts/generate_status_page.py` — `render_html()` 200→30 lines
**Commit**: 90c0a3a

| Helper Extracted | Lines | Quality | Verdict |
|-----------------|-------|---------|---------|
| `_render_css` | 72 | Improved clarity | Keep |
| `_render_summary_cards` | 30 | Improved clarity | Keep |
| `_render_architecture` | 28 | Improved clarity | Keep |
| `_render_performance_section` | 40 | Improved clarity | Keep |
| `_render_collections_table` | 14 | Improved clarity | Keep |

Clean decomposition; also eliminated ~40 `{{`/`}}` brace escaping instances in CSS.

---

### Tier 2: Medium Decompositions (50-100 lines reduced)

#### 6. `scripts/heartbeat_postflight.py`
**Commits**: 822afff, 2445384, db88727

| Decomposition | Before | After | Quality | Verdict |
|--------------|--------|-------|---------|---------|
| `_classify_error` → data-driven table | 140L | 94L | Improved clarity | Keep |
| `_pf_prompt_predict_cognitive` → 5 subs | 167L | 213L (+27%) | Mixed | **Partially recombine** 2 smallest |
| `_pf_finalize` → extract queue_update | 91L | 98L | Improved clarity | Keep |
| `_mark_task_in_queue` → shim | 43L | 9L | Improved clarity | Keep (add logging) |

---

#### 7. `clarvis/memory/episodic_memory.py`
**Commit**: 2445384

| Decomposition | Before | After | Quality | Verdict |
|--------------|--------|-------|---------|---------|
| `encode` → `encode` + `_post_encode` | 97L | 90L | Improved clarity | Keep |
| `synthesize` → 4 subs + orchestrator | 231L | 210L | Improved clarity | Keep |
| `main` CLI → 3 subs + dispatcher | 200L | 167L | Improved clarity | Keep |

All keep. Clean pipeline splits at natural semantic boundaries.

---

#### 8. `clarvis/context/assembly.py`
**Commit**: 9f4ec8c

| Decomposition | Before | After | Quality | Verdict |
|--------------|--------|-------|---------|---------|
| `build_decision_context` → 3 helpers | ~85L | ~25L | Improved clarity | Keep |
| `_build_wire_guidance` → 2 helpers + 2 constants | ~95L | ~10L | Improved clarity | Keep |
| `build_hierarchical_episodes` → 6 helpers + 2 constants | ~127L | ~40L | Improved clarity | Keep |
| `generate_tiered_brief` → 3 zone helpers | ~95L | ~15L | Improved clarity | Keep |
| `archive_completed` → 2 helpers | ~60L | ~20L | Improved clarity | Keep |

Most decomposed file by count. All keep — consistent pattern of extracting pure helpers and promoting static data to module-level constants.

---

#### 9. `clarvis/context/dycp.py`
**Commits**: 5af52c5, 9f4ec8c

| Decomposition | Before | After | Quality | Verdict |
|--------------|--------|-------|---------|---------|
| `dycp_prune_brief` → 3 helpers | ~95L | ~25L | Improved clarity | Keep |
| `_cross_section_dedup` (new feature) | — | 65L | N/A | Keep |

---

#### 10. `scripts/context_compressor.py`
**Commits**: 5af52c5, 9f4ec8c

| Decomposition | Before | After | Quality | Verdict |
|--------------|--------|-------|---------|---------|
| `compress_queue` → 2 helpers | ~82L | ~18L | Improved clarity | Keep |
| `compress_health` → 2 helpers | ~75L | ~37L | Neutral/Improved | Keep |

---

### Tier 3: Smaller Decompositions (<50 lines reduced)

#### 11. `clarvis/cognition/context_relevance.py` (commit 23b767e)
- `score_section_relevance` 85→26L: 3 helpers extracted. **Keep** (fix var names in `_weighted_means`).
- `aggregate_relevance` 110→18L: 3 helpers + 1 constant. **Keep**.

#### 12. `clarvis/heartbeat/gate.py` (commit 94dcab5)
- `check_gate` 107→30L: 2 helpers extracted. **Keep** — cleanest decomposition in audit.

#### 13. `scripts/heartbeat_gate.py` (commit 94dcab5)
- `check_gate` 75→26L: 2 helpers extracted. **Keep**.

#### 14. `scripts/daily_brain_eval.py` (commit b7f294d)
- `_run_retrieval_probe` → 3 helpers: **Keep**.
- `_assess_quality` → 4 `_score_*` helpers: **Recombine** (too granular).
- `run_full_eval` → 2 I/O helpers: **Keep**.

#### 15. `scripts/llm_brain_review.py` (commit b7f294d)
- `build_review_prompt` → 3 `_format_*` helpers + prompt template constant: **Keep all**.

#### 16. `scripts/reasoning_chain_hook.py` (commit fccf062)
- `open_chain` → `_classify_task_type` + `_open_reasoning_session`: **Keep** both.

#### 17. `scripts/performance_benchmark.py` (commits fccf062, f302f7a)
- 7 helpers extracted, notably `_evaluate_targets` and `_build_report` which eliminated genuine cross-function duplication. **Keep all**.

---

### Not Decompositions (Excluded)

| File | Commit | What Actually Happened |
|------|--------|----------------------|
| `scripts/brain.py` | fccf062 | Added 7-line deprecation warning (behavioral, not structural) |
| `scripts/research_novelty.py` | fccf062 | Entirely new file (554 lines) |
| `scripts/directive_engine.py` | 94dcab5 | New LLM fallback feature, not decomposition |
| 16 scripts in `scripts/` | 94dcab5 | Comment-only STATUS/BRIDGE annotations |

---

## Campaign Statistics

| Metric | Value |
|--------|-------|
| Commits audited | 12 |
| Files with actual decomposition | 17 |
| Total helpers extracted | ~85 |
| Largest monolith broken | `run_preflight()`: 1120→60 lines |
| Most aggressive file | `assembly.py`: 8 decompositions, ~20 helpers |
| Best decomposition | `self_representation.py`: 10 encoders + registry pattern |
| Worst decomposition | `_finalize_recall` in `search.py`: 11 lines wrapped for no gain |
| Bugs introduced | 1 (query parameter dropped in search fallback) |
| Net line count change | Roughly neutral (helpers + signatures offset monolith reduction) |

## Conclusion

The campaign successfully reduced cognitive load across the codebase's largest functions. The 1120-line `run_preflight`, 348-line `recall`, 284-line `score_tasks`, and 230-line `encode_self_state` are all dramatically more readable. The consistent pattern — extract pure helpers, promote static data to module constants, leave orchestration in parent — is sound.

**Immediate action needed**: Fix the `_query_single_collection` bug in `clarvis/brain/search.py` (P0). The 8 recombination items (P1) are quality-of-life improvements that can be batched into a single cleanup commit. The 3 minor quality issues (P2) are non-urgent.
