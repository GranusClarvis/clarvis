# Phase 3: Architecture & Design Review

**Date**: 2026-04-08
**Reviewer**: Claude Code Opus (autonomous)
**Scope**: Subsystem boundaries, spine cohesion, duplication, data growth, hook safety, consolidation design, queue state machine
**Method**: 7-stream parallel investigation (value audit, duplication map, import assessment, data growth, hook chain audit, consolidation deep-dive, queue state machine)

---

## Executive Summary

Clarvis has **strong architectural foundations** in its core subsystems — the brain, queue engine, and hook systems are well-designed and production-ready. However, the codebase suffers from three systemic architectural problems:

1. **The spine migration is only 16% complete.** 60 scripts still use `sys.path.insert()` hacks, 15 cron jobs depend on legacy imports, and 31 scripts are dead code. The "modern spine" coexists uneasily with the legacy script layer.

2. **Two cognitive modules are decorative** (Dream Engine, Thought Protocol) — they compute and store data that nothing reads. Two more are partially decorative (Theory of Mind, Workspace Broadcast).

3. **Competing implementations exist for self-representation** — `clarvis/metrics/self_model.py` (1,575L, capability scoring) vs `scripts/metrics/self_representation.py` (987L, latent vectors). Both are actively called. They will diverge.

The system's cleanup infrastructure is excellent (JSONL caps, log rotation, chain archival), but **synaptic weights grow unbounded** (104 MB, no decay) — the single most urgent data risk.

### Severity Distribution

| Severity | Count | Key Items |
|----------|-------|-----------|
| CRITICAL | 2 | Competing self-model implementations; synaptic unbounded growth |
| HIGH | 6 | 2 decorative modules; no hook timeouts; merge_clusters() no undo; 60 legacy imports; lock timeout missing |
| MEDIUM | 8 | 2 partial modules; hebbian growth; stale backups; sidecar growth; NFS risk; consolidation parallelism; daily cap boundary |
| LOW | 5 | Naming clarity; election logging; run record rotation; salience threshold docs; coactivation cap |

---

## 3.1 Value Audit — Write-Only Subsystems

**Question**: For each cognitive module, is its output consumed by any downstream system?

### Results

| Module | Lines | Verdict | Evidence |
|--------|-------|---------|----------|
| Somatic Markers | 463 | **ACTIVE** | `task_selector.py` reads bias (10% of final score) |
| World Models | ~400 | **ACTIVE** | `task_selector.py` reads predictions (15% reranking weight) |
| Intrinsic Assessment | ~300 | **ACTIVE** | `heartbeat/adapters.py` calls `full_assessment()` in consolidation hooks |
| Cognitive Load | ~200 | **ACTIVE** | `heartbeat_preflight.py` uses `should_defer_task()` for overload prevention |
| Context Relevance | ~500 | **ACTIVE** | `heartbeat_postflight.py` scores every task; feeds MMR ranking |
| Confidence Tracker | ~400 | **ACTIVE** | Preflight predicts, postflight records outcome — continuous feedback loop |
| Workspace Broadcast | 545 | **PARTIAL** | GWT cycle runs, updates brain context, but many receivers report "skipped" |
| Theory of Mind | ~400 | **PARTIAL** | Registered as session hook but actual consumption unverified |
| **Dream Engine** | ~500 | **DECORATIVE** | Stores insights in brain; nothing queries them. CLI-only invocation. |
| **Thought Protocol** | 952 | **DECORATIVE** | Imported by task_selector but **never called**. Logs DSL frames to disk; nothing reads them. |

### Findings

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| F3.1a | Dream Engine is write-only — produces counterfactual insights stored in brain but no consumer queries or acts on them | HIGH | `scripts/cognition/dream_engine.py` |
| F3.1b | Thought Protocol is write-only — imported but never called in task_selector; DSL frames logged but unused | HIGH | `clarvis/cognition/thought_protocol.py:952L`, `clarvis/orch/task_selector.py:36` (import exists, no call) |
| F3.1c | Workspace Broadcast receivers frequently report "skipped" — GWT cycle runs but downstream impact unclear | MEDIUM | `clarvis/cognition/workspace_broadcast.py` |
| F3.1d | Theory of Mind registered as hook but consumption path unverified | MEDIUM | `scripts/cognition/theory_of_mind.py`, `scripts/hooks/session_hook.py` |

### Recommendations

1. **Dream Engine**: Either wire its output to task selection (e.g., counterfactual risk penalties) or mark as experimental and exclude from cron. Currently wastes ~500 lines and LLM tokens per invocation with zero downstream effect.
2. **Thought Protocol**: Remove the dead import from `task_selector.py`. Consider deprecating the module or wiring ThoughtScript frames into reasoning chain logging.
3. **Workspace Broadcast**: Investigate why receivers skip. If the GWT cycle isn't influencing behavior, simplify to a direct brain-context update.

---

## 3.2 Duplication Audit — Spine vs Scripts

**Question**: Where do `clarvis/` and `scripts/` have overlapping implementations, and what's the divergence risk?

### Bridge Stubs (Safe — Pure Re-exports)

15 scripts in `scripts/` are thin wrappers that re-export from `clarvis/`. They exist for backward compatibility:

| Script | Spine Counterpart | Lines | Status |
|--------|-------------------|-------|--------|
| `brain_mem/working_memory.py` | `clarvis/memory/working_memory.py` | 13 | Delete when callers migrated |
| `brain_mem/procedural_memory.py` | `clarvis/memory/procedural_memory.py` | 18 | Delete when callers migrated |
| `brain_mem/synaptic_memory.py` | `clarvis/memory/synaptic_memory.py` | 14 | Delete when callers migrated |
| `brain_mem/hebbian_memory.py` | `clarvis/memory/hebbian_memory.py` | 13 | Delete when callers migrated |
| `brain_mem/memory_consolidation.py` | `clarvis/memory/memory_consolidation.py` | 20 | Delete when callers migrated |
| `brain_mem/cognitive_workspace.py` | `clarvis/memory/cognitive_workspace.py` | 86 | Delete when callers migrated |
| `brain_mem/episodic_memory.py` | `clarvis/memory/episodic_memory.py` | 19 | Delete when callers migrated |
| `metrics/self_model.py` | `clarvis/metrics/self_model.py` | 70 | Delete when callers migrated |
| `metrics/clr_benchmark.py` | `clarvis/metrics/clr_benchmark.py` | 69 | Delete when callers migrated |
| `metrics/phi_metric.py` | `clarvis/metrics/phi.py` | 116 | Delete when callers migrated |
| `infra/cost_api.py` | `clarvis/orch/cost_api.py` | 53 | Delete when callers migrated |
| `infra/cost_tracker.py` | `clarvis/orch/cost_tracker.py` | 200 | Delete when callers migrated |
| `evolution/queue_writer.py` | `clarvis/orch/queue_writer.py` | 62 | Marked DEPRECATED 2026-04-04 |
| `evolution/task_selector.py` | `clarvis/orch/task_selector.py` | 99 | Delete when callers migrated |

**Total bridge stub LOC**: ~852 lines of pure delegation code.

### Parallel Implementations (Dangerous — Independent Logic)

| # | Finding | Severity | Details |
|---|---------|----------|---------|
| F3.2a | **Competing self-representation systems** — `clarvis/metrics/self_model.py` (1,575L, capability scoring, 7-domain HOT/GWT model) vs `scripts/metrics/self_representation.py` (987L, VanRullen & Kanai latent vectors). Both actively called: self_model by CLI/metrics, self_representation by heartbeat_postflight and workspace_broadcast. ~40% conceptual overlap. **Already diverging.** | **CRITICAL** | `clarvis/metrics/self_model.py`, `scripts/metrics/self_representation.py` |
| F3.2b | Knowledge synthesis name collision — `clarvis/context/knowledge_synthesis.py` (201L, query-time) vs `scripts/cognition/knowledge_synthesis.py` (256L, batch reflection). Different purposes but identical names cause confusion. | LOW | Both files |

### Recommendations

1. **Self-representation**: Make an architectural decision — capability scoring (self_model) or latent vectors (self_representation). Merge the winner into spine, deprecate the loser. Current state has two systems tracking the same phenomenon with different math and different data files.
2. **Knowledge synthesis**: Rename the script to `knowledge_synthesis_batch.py` to prevent confusion. No code change needed.
3. **Bridge stubs**: Safe to delete in batches as callers are migrated. Each stub documents its known callers — use those lists for migration.

---

## 3.3 Import Modernization Assessment

**Question**: How many scripts use legacy imports, and what's the migration status?

### Distribution

| Category | Count | % | Description |
|----------|-------|---|-------------|
| CRON-ACTIVE | 22 | 18% | Legacy imports, called by cron (must not break) |
| SCRIPT-ACTIVE | 38 | 30% | Legacy imports, called by other scripts |
| BRIDGE-STUB | 13 | 10% | Re-exports from clarvis/ |
| ALREADY-MODERN | 20 | 16% | Uses `from clarvis.` imports |
| DEAD CODE | 31 | 25% | No callers found |
| UTILITY | 1 | 1% | `_paths.py` helper |

### Findings

| # | Finding | Severity | Details |
|---|---------|----------|---------|
| F3.3a | 60 scripts (48%) still use `sys.path.insert()` — the "modern spine" serves only 16% of the codebase | HIGH | All `scripts/` subdirectories |
| F3.3b | 15 cron jobs depend on legacy imports — removing sys.path would break the entire autonomous layer | HIGH | See cron job list below |
| F3.3c | 31 scripts have zero callers — dead code occupying ~4,000+ lines | MEDIUM | See dead code list in detailed findings |

### Highest-Risk Cron Dependencies

These scripts are called by multiple cron jobs and use legacy imports:

| Script | Cron Jobs | Risk |
|--------|-----------|------|
| `tools/daily_memory_log.py` | autonomous, evening, morning | 3 callers |
| `tools/digest_writer.py` | evening, morning, reflection, monthly | 4 callers |
| `metrics/performance_benchmark.py` | cron_env, pi_refresh | 2 callers |
| `hooks/session_hook.py` | morning, reflection | 2 callers |
| `cognition/absolute_zero.py` | absolute_zero, reflection | 2 callers |
| `brain_mem/brain.py` | research, strategic_audit | 2 callers |

### Migration Roadmap

1. **Phase 1 (immediate)**: Delete 31 dead scripts — zero risk, reclaims ~4,000+ lines
2. **Phase 2 (maintain)**: Keep 13 bridge stubs during transition
3. **Phase 3 (migrate)**: Convert 60 legacy scripts, starting with the 6 multi-cron-caller scripts above
4. **Phase 4 (cleanup)**: Delete bridge stubs, remove `_paths.py`

**Effort estimate**: ~30-45 min/script × 60 scripts = 30-45 hours. Highly parallelizable.

---

## 3.4 Data Growth Projection

**Question**: Which data stores grow unboundedly? What are the scale risks?

### Current State: 642 MB Total

| Data Store | Current Size | Growth Type | Cleanup Mechanism | Risk |
|------------|-------------|-------------|-------------------|------|
| graph.db (SQLite) | 76 MB | Bounded | Edge decay (30-day half-life), degree pruning | LOW |
| **synaptic/synapses.db** | **104 MB** | **UNBOUNDED** | **NONE** | **CRITICAL** |
| chroma.sqlite3 | 64 MB | Bounded | Collection caps, dedup | LOW |
| hebbian/coactivation.json | 6.8 MB | Unbounded | Not explicitly covered | MEDIUM |
| hebbian/access_log.jsonl | 5.4 MB | Bounded | Capped at 5,000 lines | LOW |
| reasoning_chains/ | 6.3 MB | Bounded | 14-day archive, 90-day delete | LOW |
| memory/ | 13.5 MB | Bounded | Compress after 3 days, delete .gz after 90 | LOW |
| monitoring/ | 748 KB | Bounded | Rotate at 500 KB, keep 2 copies | LOW |
| archived/backups | 36 MB | Static | None (dead weight) | MEDIUM |
| All JSONL files | ~2.5 MB | Bounded | Explicit caps in cleanup_policy.py | LOW |

### Findings

| # | Finding | Severity | Details |
|---|---------|----------|---------|
| F3.4a | **Synaptic weights grow unbounded** — 104 MB (279,515 synapses), ~8-12 MB/week, no decay/pruning/archival mechanism exists anywhere in codebase. At 10x scale → 1+ GB. | **CRITICAL** | `data/synaptic/synapses.db` |
| F3.4b | Hebbian coactivation.json not explicitly covered by cleanup policy — auto-discovered only because >500 KB | MEDIUM | `data/hebbian/coactivation.json` (6.8 MB) |
| F3.4c | 36 MB of stale backups from pre-SQLite migration (2026-03-03) — recoverable space | MEDIUM | `data/archived/` |

### Scale Projections

| Scale | Total Estimate | Bottleneck | Verdict |
|-------|---------------|------------|---------|
| 2x | ~1.3 GB | Synaptic (208 MB) | Manageable |
| 5x | ~3.2 GB | Synaptic (520 MB) | Concerning |
| 10x | ~6.4 GB | Synaptic (1+ GB) | **Unsustainable** |

### Recommendations

1. **P0**: Implement synaptic weight decay — age-based exponential decay (30-day half-life, matching graph edges), prune below 0.02 weight. Run weekly in cron.
2. **P1**: Add `data/hebbian/coactivation.json` to explicit JSONL_TRIM with 5,000-line cap.
3. **P2**: Delete stale backups in `data/archived/` (reclaim 36 MB).

### Strength: Cleanup Infrastructure

The cleanup policy system (`scripts/infra/cleanup_policy.py`) is **excellent** — it provides explicit JSONL caps, log rotation, and lifecycle management for most data files. The gap is specifically synaptic weights, which were never integrated.

---

## 3.5 Hook Chain Audit

**Question**: Are hook systems safe? What happens when a hook throws?

### Architecture

Two independent hook systems:

| System | Location | Design | Hooks |
|--------|----------|--------|-------|
| **Brain hooks** | `clarvis/brain/hooks.py` | List-based, factory pattern, lazy registration | 7 hooks (scorers, boosters, observers, optimize) |
| **Heartbeat hooks** | `clarvis/heartbeat/hooks.py` | Priority-ordered registry, phase-based | 9 hooks (POSTFLIGHT, BRAIN_PRE_STORE) |

### Exception Safety: SAFE

Both systems wrap each hook in `try/except`. If hook N throws, hooks N+1..M still run:

- **Brain scorers**: First success stops; if all fail, fallback to distance-based sorting
- **Brain boosters**: Each wrapped independently; failure skips that booster
- **Brain observers**: Run in background `ThreadPoolExecutor` on deep copies — fully isolated
- **Heartbeat hooks**: Each wrapped; error recorded in results dict; chain continues
- **Secret redaction** (BRAIN_PRE_STORE): Intentionally mutates `context["text"]` — this is correct behavior

### Findings

| # | Finding | Severity | Details |
|---|---------|----------|---------|
| F3.5a | **No timeout on hook execution** — a hung hook blocks `recall()` (brain) or heartbeat postflight indefinitely | HIGH | `clarvis/brain/search.py:437-529`, `clarvis/heartbeat/hooks.py:77-98` |
| F3.5b | Consolidation hook can mutate brain during parallel recall — no read-lock prevents concurrent access | MEDIUM | `clarvis/brain/store.py:816-821` |
| F3.5c | No circuit breaker for repeatedly failing hooks — a hook that fails 100x keeps being called | MEDIUM | Both hook systems |

### Strengths

- **Dependency inversion** breaks circular imports — hooks are lazily registered, not imported at module load time
- **Observer isolation** via deep copy + background threads is well-designed
- **Rate limiting** on expensive observers (hebbian, synaptic: 5s throttle)
- **Priority ordering** in heartbeat hooks is deterministic and tested

### Recommendations

1. Add per-hook timeout (500ms for brain hooks, 10s for heartbeat hooks)
2. Add circuit breaker: disable hook after 3 consecutive failures, with manual re-enable
3. Consider read-lock in `recall()` to prevent consolidation during active queries

---

## 3.6 Consolidation Deep-Dive

**Question**: Is the consolidation system safe? Can it accidentally delete important memories?

### Architecture: 8-Phase Pipeline (1,937 lines)

```
run_consolidation()
  ├─ 1. deduplicate()          — 100-char prefix match, keep highest importance
  ├─ 2. prune_noise()          — Regex patterns (Prediction:, World model:, etc.)
  ├─ 3. enhanced_decay()       — Time-decay + access boost (floor 0.5 if access > 3)
  ├─ 4. archive_stale()        — 30+ days unaccessed + importance < 0.3 → JSON archive
  ├─ 5. enforce_memory_caps()  — Per-collection hard caps (total ~7,500)
  ├─ 6. attention_guided_decay() — Salience modulates decay rate
  ├─ 7. attention_guided_prune() — 4-condition conjunction (very conservative)
  └─ 8. gwt_broadcast_survivors() — Top 3 surviving memories → attention spotlight
```

### Safety Assessment

| Operation | Risk | Undo Available? | Protection |
|-----------|------|----------------|------------|
| deduplicate() | Moderate | NO | 100-char prefix is narrow |
| prune_noise() | Moderate | NO | "critical"/"genesis" tags immune |
| enhanced_decay() | Low | N/A (no delete) | Access boost prevents value loss |
| archive_stale() | Safe | YES (JSON archive) | Recoverable |
| enforce_memory_caps() | Moderate | YES (archived) | Protected tags; scoring formula |
| attention_guided_decay() | Safe | N/A (no delete) | Respects salience |
| attention_guided_prune() | Low | NO | 4-way AND (rarely fires) |
| **merge_clusters()** | **HIGH** | **NO** | **Deletes originals permanently** |

### Findings

| # | Finding | Severity | Details |
|---|---------|----------|---------|
| F3.6a | **`merge_clusters()` deletes originals with no undo** — merges 3+ semantically similar memories (distance < 0.80) into one synthesized text. Originals are permanently deleted, not archived. Can lose nuanced knowledge. | HIGH | `clarvis/memory/memory_consolidation.py:207-305` |
| F3.6b | No pre-consolidation snapshot — if process crashes mid-pipeline, memory state is partially modified | MEDIUM | `memory_consolidation.py:1625` (`run_consolidation()`) |
| F3.6c | Consolidation previously hung for 22 hours (exhausted NPROC limit) — timeout watchdog added but root cause may recur | MEDIUM | `scripts/cron/cron_reflection.sh:17` (comment) |

### Strengths

- **Dry-run mode**: All functions support `dry_run=True` — excellent for preview
- **Three-tier dedup**: Write-time embedding check (store.py) → prefix match → cluster merge
- **Protected tags**: "critical", "genesis", "identity" are immune to all pruning
- **Access-based boosting**: Frequently-used memories get importance floor of 0.5
- **Collection caps** were tuned based on real data loss incident (raised 2026-03-13)
- **Complexity is justified**: 8 strategies each serve a distinct purpose; no obvious redundancy

### Recommendations

1. **Archive originals before `merge_clusters()` deletion** — write to archive JSON, then delete. Cost: ~20 lines of code.
2. **Add pre-consolidation snapshot** — dump affected collection IDs before starting; restore on crash.
3. **Add "explain" logging** — for each deleted memory, log why (scores, which phase deleted it).

---

## 3.7 Queue Engine State Machine

**Question**: Is the state machine complete? Are there stuck states or race conditions?

### State Machine: 6 States

```
pending → running → succeeded → removed
                  → failed → (retry) → running
                           → deferred (max retries exceeded)
```

### Design Assessment: **Sound**

- **Stuck-state recovery**: 3-hour timeout auto-recovers stuck `running` → `failed`
- **Backoff**: Exponential, capped at 2 hours
- **Priority-dependent retries**: P0=3, P1=2, P2=1
- **Scoring**: `0.50×priority + 0.35×idle_time - 0.15×failure_penalty`
- **Reconciliation**: Every `select_next()` merges QUEUE.md with sidecar JSON
- **Atomic writes**: Sidecar uses tmpfile + `os.rename()`

### Findings

| # | Finding | Severity | Details |
|---|---------|----------|---------|
| F3.7a | **No lock timeout** — `fcntl.flock(LOCK_EX)` blocks indefinitely if lock is held by crashed process | HIGH | `clarvis/orch/queue_engine.py:170-180` |
| F3.7b | Sidecar entries never pruned — `removed` and `succeeded` entries accumulate forever | MEDIUM | `queue_engine.py` sidecar management |
| F3.7c | Daily task cap uses wall-clock time, not UTC date — boundary race at midnight | MEDIUM | `clarvis/orch/queue_writer.py` |
| F3.7d | `select_next()` returns None with no debug logging explaining why | LOW | `queue_engine.py` |

### Strengths

- **QUEUE.md + sidecar design** is correct — human-readable markdown for operators, machine-managed JSON for state
- **Parsing is robust** — line-by-line regex, graceful skipping of malformed entries
- **fcntl locking** protects concurrent access (when it works)
- **Deferred annotation** in QUEUE.md makes stuck tasks visible to operators
- **Run records** in append-only JSONL are corruption-resistant

### Recommendations

1. Add 30-second lock timeout with fallback (skip selection rather than hang)
2. Weekly sidecar pruning: delete `removed` entries >30 days, `succeeded` >90 days
3. Use UTC date for daily cap boundary

---

## Cross-Cutting Architectural Assessment

### What Architecture Is Strong

1. **Brain core (ChromaDB + SQLite graph)** — Well-designed dual-store with clean separation. Singleton lifecycle, lazy initialization, hook-based extensibility. The SQLite cutover is complete and working.

2. **Cleanup infrastructure** — `cleanup_policy.py` + `data_lifecycle.py` provide comprehensive rotation, archival, and caps for most data. Systematic and well-maintained.

3. **Hook system design** — Two well-separated registries with dependency inversion, exception isolation, and priority ordering. Observer isolation via deep copy + background threads is particularly good.

4. **Queue engine** — Sound state machine with stuck-state recovery, exponential backoff, and reconciliation. The QUEUE.md + sidecar pattern balances human readability with machine reliability.

5. **Consolidation safety** — Multiple protection mechanisms (protected tags, access boosting, salience resistance, dry-run mode). Collection caps were empirically tuned after a real data loss incident.

### What Architecture Is Weak

1. **Spine migration stall** — Only 16% of scripts use modern imports. The codebase has two import styles, two module namespaces, and 15 bridge stubs. This creates maintenance drag, confusion for new code, and a large surface area for divergence.

2. **Decorative cognitive modules** — Dream Engine (500L) and Thought Protocol (952L) produce no downstream effects. They add complexity, consume LLM tokens, and create a false impression of sophistication. Theory of Mind and Workspace Broadcast are partially in this category.

3. **Competing self-representation** — Two systems (self_model.py, self_representation.py) track the same phenomenon with different algorithms, different data stores, and different callers. This is the highest-divergence-risk duplication in the codebase.

4. **Synaptic weight growth** — The only major data store without any cleanup mechanism. At current growth rate (~10 MB/week), this becomes a scaling wall within months.

5. **No hook timeouts** — A hung hook can freeze the entire recall path or heartbeat postflight indefinitely. No circuit breaker prevents repeatedly-failing hooks from degrading performance.

### Where Consolidation/Refactor Is Most Needed

**Priority 1: Architectural decisions needed**
- Resolve self_model vs self_representation (pick one, deprecate the other)
- Decide fate of Dream Engine and Thought Protocol (wire in or deprecate)

**Priority 2: Migration completion**
- Delete 31 dead scripts (immediate, zero risk)
- Migrate 6 highest-impact cron-called scripts to spine imports
- Delete bridge stubs as callers migrate

**Priority 3: Safety gaps**
- Implement synaptic weight decay
- Add lock timeouts to queue engine
- Archive originals before merge_clusters() deletion
- Add hook execution timeouts

---

## Summary of All Findings

| # | Finding | Severity | Section |
|---|---------|----------|---------|
| F3.1a | Dream Engine is write-only (decorative) | HIGH | 3.1 |
| F3.1b | Thought Protocol is write-only (decorative) | HIGH | 3.1 |
| F3.1c | Workspace Broadcast receivers frequently skip | MEDIUM | 3.1 |
| F3.1d | Theory of Mind consumption unverified | MEDIUM | 3.1 |
| F3.2a | Competing self-model implementations (self_model vs self_representation) | CRITICAL | 3.2 |
| F3.2b | Knowledge synthesis name collision | LOW | 3.2 |
| F3.3a | 60 scripts (48%) still use sys.path.insert() | HIGH | 3.3 |
| F3.3b | 15 cron jobs depend on legacy imports | HIGH | 3.3 |
| F3.3c | 31 dead scripts with zero callers | MEDIUM | 3.3 |
| F3.4a | Synaptic weights grow unbounded (104 MB, no decay) | CRITICAL | 3.4 |
| F3.4b | Hebbian coactivation.json not in cleanup policy | MEDIUM | 3.4 |
| F3.4c | 36 MB stale backups from pre-migration | MEDIUM | 3.4 |
| F3.5a | No timeout on hook execution | HIGH | 3.5 |
| F3.5b | Consolidation can mutate brain during parallel recall | MEDIUM | 3.5 |
| F3.5c | No circuit breaker for failing hooks | MEDIUM | 3.5 |
| F3.6a | merge_clusters() deletes originals with no undo | HIGH | 3.6 |
| F3.6b | No pre-consolidation snapshot | MEDIUM | 3.6 |
| F3.6c | Consolidation previously hung for 22 hours | MEDIUM | 3.6 |
| F3.7a | No lock timeout in queue engine (deadlock risk) | HIGH | 3.7 |
| F3.7b | Sidecar entries never pruned | MEDIUM | 3.7 |
| F3.7c | Daily task cap midnight boundary race | MEDIUM | 3.7 |
| F3.7d | No debug logging when select_next() returns None | LOW | 3.7 |

**Totals**: 2 CRITICAL, 6 HIGH, 10 MEDIUM, 2 LOW
