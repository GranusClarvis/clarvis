# Brain Write Surface Audit — 2026-04-08

Full audit of every code path that writes to ClarvisDB (ChromaDB brain, graph, goals, context).

## Executive Summary

- **82+ distinct write call sites** across `clarvis/`, `scripts/`, and `tests/`
- **Write-time dedup guard** (L2 < 0.30) protects all `brain.store()` calls without explicit `memory_id`
- **2 paths fixed** in this audit (episodic_memory, reasoning_chains) — both upgraded from unbounded auto-ID to deterministic `memory_id` upserts
- **Previous fixes confirmed intact**: workspace_broadcast, attention, self_model, dream_engine all use fixed IDs or have store calls removed
- **No remaining high-risk spam sources found**

## Write API Methods

| Method | Dedup? | Notes |
|--------|--------|-------|
| `brain.store(text, ..., memory_id=None)` | **YES** — L2 < 0.30 guard when `memory_id` is None; upsert when `memory_id` provided | Core write. 65+ call sites |
| `remember(text, importance)` | **YES** via `store()` | Also runs conflict detection pre-store |
| `capture(text)` | **YES** via `remember()` | Importance gate ≥ 0.6 |
| `propose() → commit()` | **YES** via `store()` | Two-stage gate: utility evaluation then commit |
| `evolve_memory()` | **YES** via `store()` | Creates new entry + supersedes old |
| `brain.revise()` | **YES** via `store()` | Creates new + marks old superseded |
| `brain.set_goal(name, progress)` | **UPSERT** by goal_name | Capped at 25 active goals |
| `brain.set_context(text)` | **UPSERT** always ID=`"current"` | Idempotent singleton |
| `brain.update_memory()` | N/A (in-place) | Metadata patch, no new entry |
| `brain.reconsolidate()` | N/A (in-place) | Within 300s lability window |
| `brain.delete_memory()` | N/A (removal) | Soft or hard delete |
| `brain.supersede_duplicates()` | N/A (bulk retire) | CLI-only |
| `brain.add_relationship()` | Deduped on (from, to, type) | Graph edge, not memory |
| `brain.bulk_cross_link()` / `bulk_intra_link()` | Internal dedup | Batch graph ops |

## Writer Path Classification

### SAFE — Fixed-ID Upsert (no growth possible)

| File | Method | memory_id Pattern | Notes |
|------|--------|-------------------|-------|
| `clarvis/metrics/self_model.py:164` | store | `self-model-world-{date}` | 1/day max |
| `clarvis/metrics/self_model.py:192` | store | `self-model-awareness-current` | Singleton |
| `clarvis/metrics/self_model.py:1452` | store | `self-model-capability-{date}` | 1/day max |
| `scripts/metrics/self_representation.py:783` | store | `self-rep-current` | Singleton |
| `scripts/cognition/dream_engine.py:473` | store | `dream_{ep_id}_{template}` | Per episode+template |
| `scripts/cognition/dream_engine.py:509` | store | `dream_session_{session_id}` | Per session |
| `scripts/wiki_brain_sync.py:281` | store | `wiki_{slug}` | Per wiki page |
| `clarvis/learning/meta_learning.py:735` | store | `meta_strategy_{date}` | 1/day |
| `clarvis/learning/meta_learning.py:748` | store | `meta_alert_{date}` | 1/day |
| `clarvis/learning/meta_learning.py:773` | store | `meta_speed_{date}` | 1/day |
| `scripts/hooks/refresh_priorities.py:134` | store | (fixed ID) | Singleton |

### SAFE — Bounded Episodic (write-time dedup + low frequency)

| File | Method | Frequency | Dedup |
|------|--------|-----------|-------|
| `clarvis/heartbeat/brain_bridge.py:238` | store | Per heartbeat task (~12/day) | L2 < 0.30 |
| `clarvis/heartbeat/brain_store.py:43` | store | Per failure (rare) | L2 < 0.30 |
| `clarvis/cognition/confidence.py:161` | store | Per prediction | L2 < 0.30, importance=0.4 |
| `clarvis/cognition/confidence.py:199` | store | Per outcome | L2 < 0.30, importance=0.6 |
| `clarvis/cognition/confidence.py:768` | store | Per recalibration (weekly) | L2 < 0.30 |
| `scripts/cognition/dream_engine.py:612` | store | Per rethink category (capped 5) | Pre-recall check L2 < 0.5 |
| `scripts/evolution/evolution_loop.py:118` | store | Per failure (rare) | L2 < 0.30 |
| `scripts/evolution/evolution_loop.py:230` | store | Per fix success (rare) | L2 < 0.30 |
| `scripts/evolution/failure_amplifier.py:405` | store | Per soft failure batch | L2 < 0.30 |
| `scripts/evolution/meta_gradient_rl.py:770` | store | Via meta_learning (daily ID) | Fixed daily ID |
| `scripts/cognition/clarvis_reflection.py:45` | store | Per reflection (1/day) | L2 < 0.30 |
| `scripts/cognition/prediction_review.py:228` | store | Per review cycle | L2 < 0.30 |
| `scripts/cognition/knowledge_synthesis.py:167` | store | Per synthesis | L2 < 0.30 |
| `scripts/cognition/conversation_learner.py:673,835` | store | Per conversation | L2 < 0.30 |
| `scripts/cognition/world_models.py:977` | store | Per world update | L2 < 0.30 |
| `scripts/cognition/causal_model.py:799,814` | store | Per causal insight | L2 < 0.30 |
| `scripts/cognition/theory_of_mind.py:707` | store | Per ToM mining run | L2 < 0.30 |
| `scripts/cognition/absolute_zero.py:539` | store | Per AZR session (weekly) | L2 < 0.30 |
| `scripts/hooks/session_hook.py:113,121` | store | Per session close | L2 < 0.30 |
| `scripts/hooks/temporal_self.py:253` | store | Per temporal update | L2 < 0.30 |
| `scripts/hooks/goal_hygiene.py:287` | store | Per hygiene run | L2 < 0.30 |
| `scripts/metrics/brain_effectiveness.py:262` | store | Per effectiveness check | L2 < 0.30 |
| `scripts/metrics/self_report.py:124` | store | Per self-report | L2 < 0.30 |
| `scripts/tools/ast_surgery.py:720` | store | Per AST learning | L2 < 0.30 |
| `scripts/tools/context_compressor.py:1305` | store | Per archival event | L2 < 0.30 |
| `scripts/tools/browser_agent.py:856` | remember | Per browse capture | Via remember() |
| `clarvis/adapters/openclaw.py:13` | remember | Per OpenClaw call | Via remember() |

### SAFE — Context / Goals (idempotent upsert)

| File | Method | Notes |
|------|--------|-------|
| `clarvis/cognition/workspace_broadcast.py:407` | set_context | GWT broadcast (store removed) |
| `clarvis/cognition/attention.py:298` | set_context | Attention broadcast (store removed) |
| `scripts/hooks/session_hook.py:43,148` | set_context | Session open/close |
| `clarvis/memory/episodic_memory.py:915-953` | set_goal | Auto-goals from episodes; name-deduped, capped 25 |
| `scripts/hooks/goal_tracker.py:317` | set_goal | Progress updates (upsert by name) |

### FIXED IN THIS AUDIT

| File | Issue | Fix |
|------|-------|-----|
| `clarvis/memory/episodic_memory.py:507` | `brain.store()` without `memory_id` — every episode created a new brain entry | Added `memory_id=f"episode_{episode['id']}"` for upsert |
| `clarvis/cognition/reasoning_chains.py:47` | Chain header stored with auto-ID — reruns create duplicates | Added `memory_id=f"rc_{chain_id}"` |
| `clarvis/cognition/reasoning_chains.py:79` | Per-step store with auto-ID | Added `memory_id=f"rc_{chain_id}_s{step_num}"` |
| `clarvis/cognition/reasoning_chains.py:100` | Outcome store with auto-ID | Added `memory_id=f"rc_{chain_id}_outcome"` |

### PREVIOUSLY FIXED (confirmed still intact)

| File | What was removed/fixed |
|------|----------------------|
| `clarvis/cognition/workspace_broadcast.py` | `brain.store()` removed (was creating 158+ identical GWT entries) |
| `clarvis/cognition/attention.py` | `brain.store()` removed (was creating unbounded attention snapshots) |
| `clarvis/metrics/self_model.py` | All 3 stores upgraded to daily/singleton fixed IDs |
| `scripts/metrics/self_representation.py` | Upgraded to `memory_id="self-rep-current"` singleton |
| `scripts/cognition/dream_engine.py` | All stores use deterministic episode+template IDs |

### TEST-ONLY (no production risk)

| File | Notes |
|------|-------|
| `tests/test_write_time_dedup.py` | 17 tests covering dedup guard, upsert, fingerprint |
| `tests/test_clarvis_brain.py` | Core brain unit tests |
| `tests/clarvis/test_memory_evolution.py` | Evolution/recall success tests |
| `tests/clarvis/test_brain_roundtrip.py` | Roundtrip integration tests |
| `tests/clarvis/test_chaos_recovery.py` | Chaos resilience tests |

### ACCEPTABLE RISK — Low frequency, dedup-protected

| File | Why acceptable |
|------|---------------|
| `clarvis/cognition/confidence.py` | Per-prediction stores at importance 0.4-0.7; write-time dedup blocks reruns; predictions are distinct events |
| `scripts/evolution/failure_amplifier.py` | Runs once per amplification cycle; dedup blocks near-identical failures |
| `scripts/evolution/evolution_loop.py` | Only on actual failure/fix events; rare in practice |
| `clarvis/heartbeat/brain_bridge.py` | One store per heartbeat task; dedup blocks repeated tasks |
| `clarvis/memory/procedural_memory.py` | Procedure consolidation; infrequent |
| `clarvis/memory/soar.py` | Impasse resolution; infrequent |
| `clarvis/context/gc.py` | Context GC events; rare |

### CLI / MANUAL (user-initiated, no automation risk)

| File | Notes |
|------|-------|
| `clarvis/cli_brain.py` | All CLI operations: revise, update-meta, delete, supersede, link |
| `scripts/brain_mem/brain.py` | Legacy CLI brain commands |

### AGENT / PROJECT (isolated brains)

| File | Notes |
|------|-------|
| `scripts/agents/project_agent.py` | Writes to project agent's isolated ChromaDB (not main brain) |
| `scripts/agents/pr_factory.py` | Writes to lite_brain (project-scoped collections) |
| `scripts/brain_mem/lite_brain.py` | Project-agent lite brain with 5 collections |

## Graph Write Paths

| File | Method | Notes |
|------|--------|-------|
| `clarvis/memory/hebbian_memory.py:650` | add_relationship | Co-activation edges; deduped on (from, to, type) |
| `scripts/wiki_brain_sync.py:296-355` | add_relationship (6x) | Wiki entity/cross-link/temporal edges; bounded by wiki page entity count |
| `scripts/cognition/knowledge_synthesis.py:182` | add_relationship | Cross-domain links; per-synthesis |
| `scripts/hooks/intra_linker.py:189` | add_relationship | Intra-collection edges |
| `clarvis/brain/memory_evolution.py:144` | add_relationship | Evolution tracking edges |
| `clarvis/cli_brain.py:277,291` | bulk_cross/intra_link | CLI-initiated batch linking |
| `clarvis/metrics/phi.py:517,546` | bulk_cross_link | Auto-triggered when phi drops |

## Maintenance / Decay Paths

| File | Method | Notes |
|------|--------|-------|
| `brain.decay_importance()` | Exponential decay on unused memories | Safe; only reduces importance |
| `brain.prune_low_importance()` | Deletes below threshold (0.12) | Preserves genesis/critical/identity tags |
| `brain.optimize()` | Runs decay + prune + hooks | Called by maintenance cron |
| `brain.archive_stale_goals()` | Archives 0% goals older than 7d | Reduces goal count |
| `graph.decay_edges()` | Exponential decay on edge weights | Prunes below 0.02 |

## Tests Added

4 new tests in `tests/test_write_time_dedup.py`:
- `TestEpisodicMemoryUpsert::test_episode_store_uses_episode_id` — verifies re-encoding upserts
- `TestEpisodicMemoryUpsert::test_different_episodes_stored_separately` — verifies distinct episodes stay separate
- `TestReasoningChainUpsert::test_chain_header_upserts` — verifies chain reruns upsert
- `TestReasoningChainUpsert::test_chain_steps_have_unique_ids` — verifies step-level IDs

All 17 dedup tests pass.

## Remaining Recommendations

1. **Monitor confidence.py growth** — prediction stores use auto-IDs with dedup guard, but distinct predictions won't collide. If the collection grows past ~500 entries, consider adding periodic archival.
2. **Consider memory_id for brain_bridge.py** — postflight outcome stores could use a task-based ID to prevent re-heartbeat duplication. Current dedup guard is sufficient but explicit IDs would be more robust.
3. **Episodic goal auto-creation** (episodic_memory.py:915-953) is safe (name-based upsert, 25-goal cap) but could benefit from a quality gate to avoid creating low-value goals from trivial episodes.
