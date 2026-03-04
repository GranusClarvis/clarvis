# Phase 5 — Scalability Assessment & Next Steps

_Written 2026-03-04 after Phase 4 landed (parallel brain recall, spine heartbeat gate/runner, spine context compressor, global cron lock, 31 tests)._

---

## 1. Scalability Risk Re-Assessment (Post-Phase 4)

### Risk 1: Sequential Brain Queries

| Metric | Before Phase 4 | After Phase 4 |
|--------|---------------|---------------|
| Query architecture | Sequential loop over 10 collections | ThreadPoolExecutor, up to 10 workers |
| Avg recall latency | ~7,441 ms | ~2,092 ms (72% reduction) |
| Caching | None | 3-layer: embedding (60s TTL), result (30s TTL), collection (60s TTL) |
| Stats caching | None | 30s TTL stats cache |

**Status: LARGELY MITIGATED.**

**Remaining risk:** Cache is TTL-only (no event-driven invalidation). Cold starts still hit full sequential ONNX embedding computation. No pre-warming on service boot.

**Next mitigation:**
1. Pre-warm top-N frequent queries on first `get_brain()` call.
2. Persistent embedding cache (SQLite or pickle) that survives restarts.
3. Background refresh: expired cache entries trigger async re-query instead of blocking.

---

### Risk 2: Heavy Scripts Outside Spine

| Metric | Before Phase 4 | After Phase 4 |
|--------|---------------|---------------|
| Spine modules | brain/ only | brain/ + heartbeat/ + context/ + memory/ + cognition/ |
| Spine LOC | ~1,200 | ~10,134 (18 files) |
| Scripts LOC | ~46,800 | ~36,700 (core logic migrated) |
| Stub packages | metrics/, orch/ empty | Still empty |

**Status: PARTIALLY MITIGATED.** Core cognitive loop (brain → heartbeat → context) is in spine. But 82% of business logic still in scripts/.

**Remaining risk:** `metrics/` and `orch/` are empty stubs. Key modules still in scripts/:
- **Hook dependencies** (not in spine): `actr_activation.py`, `retrieval_quality.py`, `synaptic_memory.py`
- **Metrics** (not in spine): `self_model.py` (1,631L), `phi_metric.py` (688L), `performance_benchmark.py` (1,535L)
- **Orchestration** (not in spine): `task_router.py` (564L), `task_selector.py` (435L), `agent_orchestrator.py` (763L)

**Next mitigation:**
1. Populate `clarvis/metrics/` with self_model + performance_benchmark.
2. Populate `clarvis/orch/` with task_selector + task_router.
3. Migrate hook dependencies (actr_activation, retrieval_quality, synaptic_memory) to `clarvis/brain/hooks/` or `clarvis/cognition/`.

---

### Risk 3: Test Coverage Gaps

| Metric | Before Phase 4 | After Phase 4 |
|--------|---------------|---------------|
| Total tests | 656 | 687+ |
| Spine module coverage | 4/5 (80%) | 5/5 (100%) |
| Phase 4 tests | — | 31 (gate, compressor, search perf) |
| Integration tests | None | Partial (cron wrap-mode) |

**Status: LARGELY MITIGATED.** All spine modules have test classes. 687+ total tests.

**Remaining risk:**
- No end-to-end pipeline test (gate → preflight → execute → postflight).
- No load/stress tests for concurrent brain access.
- `clarvis/metrics/` and `clarvis/orch/` stubs have zero tests.
- No mutation testing or branch coverage measurement.

**Next mitigation:**
1. Add pipeline integration test (mock Claude Code execution).
2. Add concurrent access test (multiple threads hitting brain.recall simultaneously).
3. Tests for metrics/ and orch/ as they get populated.

---

### Risk 4: Graph Density Growth

| Metric | Baseline (CLAUDE.md) | Current (2026-03-04) |
|--------|---------------------|---------------------|
| Nodes | ~1,200 | 2,186 |
| Edges | ~47,000 | 61,610 |
| Density | ~39.2 edges/node | 28.18 edges/node |
| Cross-collection | Unknown | 17,768 (28.8%) |
| Hebbian edges | Unknown | 42,872 (69.6%) |

**Status: MODERATE RISK.** Density actually decreased (nodes grew faster than edges). But absolute edge count is high and Hebbian edges dominate at 69.6%.

**Remaining risk:**
- Hebbian co-recall edges grow on every `brain.recall()` — O(n²) per query results.
- No ceiling on edge count per node.
- Graph file load time grows linearly with edge count (JSON parse ~61k edges).
- No edge decay mechanism (edges never expire).

**Next mitigation:**
1. Hebbian edge decay: age-based weight reduction, prune edges below threshold.
2. Per-node edge cap (e.g., 50 max per node, evict lowest-weight).
3. Binary graph format (msgpack or SQLite) instead of JSON for faster load.
4. Graph density alert in health_monitor if edges/node exceeds threshold.

---

### Risk 5: Duplicated Lock/Env Logic Across Cron

| Metric | Before Phase 4 | After Phase 4 |
|--------|---------------|---------------|
| Lock types | 2 (local + maintenance) | 3 (added global Claude lock) |
| Scripts with local lock | 16 | 16 |
| Scripts with global lock | 0 | 8 |
| Duplicated lock lines | ~144 | ~309 (grew — global lock added via copy-paste) |

**Status: HIGH RISK (worsened).** Phase 4 added the global Claude lock correctly, but by copy-pasting 15 lines into 8 scripts. Total duplicated lock logic grew from 144 to 309 lines.

**Remaining risk:**
- Any lock bug requires editing 16+ files.
- Inconsistent timeout values if one script gets updated but not others.
- No centralized lock monitoring or metrics.
- `trap EXIT` handlers vary slightly across scripts.

**Next mitigation:**
1. Extract `scripts/lock_helper.sh` with `acquire_local_lock()`, `acquire_global_lock()`, `acquire_maintenance_lock()` functions.
2. All cron scripts source `lock_helper.sh` and call functions instead of inline lock code.
3. Add lock status reporting to `clarvis cron status`.

---

## 2. Spine Coherence Verification

### Architecture Check

| Layer | Status | Notes |
|-------|--------|-------|
| `clarvis/` is canonical | **YES** | Brain, heartbeat, memory, cognition, context — all canonical |
| `scripts/` are thin wrappers | **YES** | `scripts/brain.py` re-exports from `clarvis.brain` |
| CLI delegates to spine | **YES** | cli_brain → clarvis.brain, cli_heartbeat → clarvis.heartbeat |
| No circular imports | **YES** | Hook-based DI pattern prevents cycles |
| Stubs acknowledged | **YES** | metrics/, orch/ intentionally empty |

### Module Status Matrix

| Spine Module | Files | LOC | Tests | Canonical? |
|-------------|-------|-----|-------|-----------|
| brain/ | 6 | 1,181 | 80 | Yes |
| heartbeat/ | 5 | 676 | 48 | Yes |
| memory/ | 5 | 5,114 | 261 | Yes |
| cognition/ | 3 | 2,812 | 171 | Yes |
| context/ | 2 | 351 | 12 | Yes |
| metrics/ | 1 | 0 | 0 | Stub |
| orch/ | 1 | 0 | 0 | Stub |
| CLI | 6 | ~800 | 9 | Yes |

### Identified Issues (Non-Regressions)

1. **working_memory.py is a shim** — delegates to `clarvis.cognition.attention`. This is intentional (backward compat), not a regression.
2. **heartbeat/runner.py uses importlib** to load scripts/ modules for preflight/postflight. This is the correct delegation pattern (heavy cognitive imports stay in scripts/).
3. **brain/hooks.py imports from scripts/** — `actr_activation`, `retrieval_quality`, `synaptic_memory`. These are hook registrations via lazy import, not tight coupling. Will resolve when those modules migrate to spine.

**Verdict: No regressions. Spine is coherent.**

---

## 3. Proposed Next 10 Queue Tasks (P0/P1)

### P0 — Next 3 Heartbeats

#### 1. [CRON_LOCK_HELPER] Extract shared lock functions
Extract `scripts/lock_helper.sh` from the 309 lines of duplicated lock logic. Functions: `acquire_local_lock <name>`, `acquire_global_lock`, `acquire_maintenance_lock`, `release_all_locks`. Update all 16 cron scripts to source and use it. **Eliminates highest active duplication risk.**

#### 2. [METRICS_SELF_MODEL] Populate `clarvis/metrics/` — self_model
Move `scripts/self_model.py` core classes (CapabilityDomain, SelfModel) into `clarvis/metrics/self_model.py`. Leave scripts/self_model.py as thin re-export wrapper. Wire into heartbeat postflight via adapter hook. **Fills the largest empty stub.**

#### 3. [ORCH_TASK_SELECTOR] Populate `clarvis/orch/` — task_selector
Move `scripts/task_selector.py` scoring logic into `clarvis/orch/task_selector.py`. Export `select_task()`, `score_candidates()`, `apply_novelty_boost()`. Thin wrapper in scripts/. **Fills the second empty stub with the most impactful module.**

### P1 — This Week

#### 4. [METRICS_PERF_BENCHMARK] Move performance_benchmark to spine
Move core PI computation (8-dimension scoring, composite calculation, self-optimization triggers) from `scripts/performance_benchmark.py` (1,535L) into `clarvis/metrics/benchmark.py`. Keep CLI in scripts as wrapper. **Enables `clarvis bench` to use spine directly.**

#### 5. [ORCH_TASK_ROUTER] Move task_router to spine
Move `scripts/task_router.py` complexity scoring and model routing into `clarvis/orch/router.py`. Export `classify_task()`, `route_to_model()`, `get_tier_config()`. **Completes orch/ with the two most-used orchestration modules.**

#### 6. [GRAPHRAG_RECALL_BOOST] Wire graphrag_communities into brain.recall()
Add optional 1-hop graph community expansion to `brain.recall()`. After ChromaDB vector search, check if results fall within detected communities and boost intra-community neighbors. Use existing `graphrag_communities.py` community detection. **Directly improves retrieval quality — the primary PI dimension (weight 0.18).**

#### 7. [HEBBIAN_EDGE_DECAY] Add age-based Hebbian edge pruning
In `clarvis/brain/graph.py`, add `decay_hebbian_edges(max_age_days=90, min_weight=0.1)`. Prune Hebbian edges older than threshold with weight below minimum. Call from graph_compaction.py during 04:30 maintenance window. **Controls the 42,872 Hebbian edges (69.6% of graph) before they become unmanageable.**

#### 8. [META_LEARNING_WIRE] Wire meta_learning into reflection pipeline
Add `meta_learning.py analyze` results to `cron_reflection.sh` output. Store strategy effectiveness scores in brain. Feed learning speed metrics into task_selector scoring. **Closes the feedback loop: "learn how to learn" data actually influences task selection.**

#### 9. [PIPELINE_INTEGRATION_TEST] End-to-end heartbeat pipeline test
Create `tests/test_pipeline_integration.py`: mock Claude Code execution, run gate → preflight → (mock execute) → postflight. Verify episode encoding, brain storage, confidence updates, and procedure extraction all fire. **The single biggest test coverage gap.**

#### 10. [ACTR_RECALL_WIRING] Wire ACT-R activation into recall scoring
Complete the long-stalled ACT-R wiring: `actr_activation.py` power-law decay scoring as a re-ranking factor in `brain.recall()`. The hook registration exists in `clarvis/brain/hooks.py` but the actual scoring path needs testing and calibration. **Oldest stalled item — memories accessed recently should get retrieval boost.**

---

## 4. Scalability Scorecard

| Risk | Pre-Phase4 | Post-Phase4 | Target | Gap |
|------|-----------|-------------|--------|-----|
| Brain query latency | HIGH | **LOW** | <2s avg | Close (2.09s) |
| Scripts outside spine | HIGH | **MEDIUM** | <30% LOC in scripts/ | 82% still in scripts/ |
| Test coverage | MEDIUM | **LOW** | 100% spine + integration | Missing pipeline test |
| Graph density | MEDIUM | **MEDIUM** | <30 edges/node, edge decay | 28.18, no decay |
| Lock duplication | MEDIUM | **HIGH** | Zero duplication | 309 lines duplicated |

---

## 5. Decision Points for Inverse

### 1. Cron cutover timeline
The `clarvis cron run <job>` wrapper exists and `cron_reflection.sh` is piloting (7-day soak ends 2026-03-11). **Decision needed:** After soak, should we cut over all 12 cron scripts at once, or one-per-week? Risk of batch cutover is low (wrappers call the same scripts), but a staged approach catches edge cases.

### 2. Sub-package absorption
`clarvis-db`, `clarvis-cost`, and `clarvis-reasoning` are separate pip packages. The spine (`clarvis/`) could absorb their CLIs into `clarvis db|cost|reasoning` subcommands. **Decision needed:** Should these remain independent packages or merge into the unified `clarvis` package? Independent = cleaner boundaries; merged = one install, one CLI.

---

## 6. AGI-Readiness Assessment

### What's Working (Scalable Foundations)
- **Parallel brain** with caching — handles 10-collection queries in ~2s
- **Hook-based DI** — new cognitive modules plug in without import cycles
- **Spine package** — clean separation of canonical code from legacy wrappers
- **Heartbeat pipeline** — gate → preflight → execute → postflight, fully in spine
- **687+ tests** — comprehensive coverage of all spine modules

### What's Missing (AGI Scaling Blockers)
1. **No feedback loop closure** — meta_learning analyzes but doesn't influence task selection
2. **No graph-enhanced retrieval** — GraphRAG communities exist but aren't used in recall
3. **No edge lifecycle** — Hebbian edges grow forever, no decay
4. **No metrics spine** — self_model, phi, performance_benchmark still standalone scripts
5. **No orchestration spine** — task routing and multi-agent coordination still ad-hoc
6. **No pipeline integration test** — can't verify full cognitive loop without manual testing

### Priority Order for AGI Scaling
```
1. CRON_LOCK_HELPER      — eliminate operational risk (lock bugs = silent failures)
2. METRICS_SELF_MODEL     — self-awareness in spine (prerequisite for self-improvement)
3. ORCH_TASK_SELECTOR     — task selection in spine (prerequisite for autonomy)
4. GRAPHRAG_RECALL_BOOST  — retrieval quality (directly measured by PI)
5. HEBBIAN_EDGE_DECAY     — graph sustainability (prevent unbounded growth)
6. META_LEARNING_WIRE     — close feedback loop (learn-from-learning)
7. ACTR_RECALL_WIRING     — memory access patterns (temporal relevance)
8. PIPELINE_INTEGRATION   — confidence in the full loop
9. METRICS_PERF_BENCHMARK — metrics in spine (unified measurement)
10. ORCH_TASK_ROUTER      — routing in spine (unified orchestration)
```

---

_Phase 5 assessment complete. All 5 risks re-evaluated, spine verified coherent, 10 concrete next tasks proposed._
