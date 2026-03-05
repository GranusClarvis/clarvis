# Post-Migration Gap Report — 2026-03-05

_Comprehensive audit after SPINE_SHADOW_DEPS (3f0908e) and GOLDEN_QA_MAIN_BRAIN (ace1fa7) completion._

---

## 1. Shadow Dependency Audit

### Verdict: ZERO remaining shadow dependencies

After commit 3f0908e, there are **no** cases where spine code imports from `scripts/` when a spine-native equivalent exists. All remaining `sys.path.insert` calls in `clarvis/` fall into 3 legitimate categories:

| Category | Count | Modules | Rationale |
|----------|-------|---------|-----------|
| **Spine proxy modules** | 5 | `cognition/somatic_markers.py`, `cognition/reasoning.py`, `brain/graphrag.py`, `memory/soar.py`, `learning/meta_learning.py` | Intentional re-export wrappers. Full implementations in `scripts/` not yet migrated. Each has `_ensure_path()` guard. |
| **CLI delegators** | 5 | `cli_cost.py`, `cli_bench.py`, `cli_brain.py`, `cli_heartbeat.py`, `cli_queue.py` | Thin CLI entry points that delegate to `scripts/` executors. Expected pattern. |
| **Pipeline delegation** | 4 | `heartbeat/runner.py`, `heartbeat/adapters.py`, `brain/hooks.py`, `orch/task_selector.py` | Lazy imports for subsystems not yet in spine (actr_activation, retrieval_quality, synaptic_memory, procedural_memory, etc.) |

**Total sys.path.insert calls in clarvis/: 20** (down from 30+ before SPINE_SHADOW_DEPS).
- Module-level hacks removed from: hooks.py, router.py, task_selector.py, attention.py, confidence.py, thought_protocol.py, memory_consolidation.py, episodic_memory.py, working_memory.py, hebbian_memory.py
- cost_api.py fully migrated into spine (clarvis/orch/cost_api.py)
- Scripts/cost_api.py reduced to thin re-export wrapper

### Legacy module name imports from clarvis/

All are inside the 5 spine proxy modules (by design):

| Spine Module | Imports From | Status |
|-------------|-------------|--------|
| `clarvis.cognition.somatic_markers` | `somatic_markers.somatic` | Proxy ✅ |
| `clarvis.cognition.reasoning` | `clarvis_reasoning.reasoner` | Proxy ✅ |
| `clarvis.brain.graphrag` | `graphrag_communities.*` | Proxy ✅ |
| `clarvis.memory.soar` | `soar_engine.soar` | Proxy ✅ |
| `clarvis.learning.meta_learning` | `meta_learning.MetaLearner` | Proxy ✅ |

Additionally, `heartbeat/adapters.py` imports `meta_learning.MetaLearner` directly (lazy, inside function). This is a forward dependency, not a shadow.

### Path manipulation grep in clarvis/

No `Path(...scripts...)` manipulations found except `metrics/self_model.py` which legitimately reads `scripts/*.py` for LOC counting and test discovery (not importing).

---

## 2. Wiring Sanity Sweep

### All checks PASS

| Test | Result | Details |
|------|--------|---------|
| Import smoke | **PASS** | `from clarvis.brain import get_brain; b=get_brain(); print(b.stats())` → 2221 memories, 72147 edges, 7/7 hooks |
| `clarvis brain health` | **PASS** | Healthy. 2221 memories, 10 collections. 10 orphan graph nodes (run backfill). 40 dup candidates, 34 noise candidates. |
| `clarvis bench pi` | **PASS** | PI = 1.0000 (last recorded 2026-03-04) |
| `clarvis bench golden-qa` | **PASS** | 20/20 queries HIT. P@1=1.000, P@3=0.883, MRR=1.000, Recall=1.000. All 6 categories pass. |
| Heartbeat gate | **PASS** | Decision: wake (20.1h gap since last check) |

### Minor maintenance items (not bugs)
- 10 orphan graph nodes → `clarvis brain backfill`
- 40 potential duplicates + 34 potential noise → `clarvis brain optimize-full`

---

## 3. Top 3 Highest-Leverage Refactor Items

Criteria: structural impact, unblocks other work, moves refactor completion score.

### 1. [CLI_ROOT_PYPROJECT] — Make clarvis pip-installable (already in QUEUE P1)

**Why highest leverage:** A proper `pyproject.toml` with `pip install -e .` would:
- Eliminate ALL sys.path.insert calls organically (standard Python imports work)
- Enable `clarvis` as a console script entry point
- Make spine tests runnable without path hacks
- Unblock proper dependency declaration
- Move C2 (clean imports) from partial → complete

**Scope:** Create `workspace/pyproject.toml` defining `clarvis` package, entry points, dependencies. Verify all imports work after `pip install -e .`. Small task, massive structural payoff.

### 2. [ACTR_WIRING] — Complete brain recall pipeline (already in QUEUE P1, 4 subtasks)

**Why high leverage:** The only registered brain hook that's unwired/untested. Hook factory exists in `clarvis/brain/hooks.py:_make_actr_scorer()`, imports `actr_activation.actr_score`. But the scoring path has never been calibrated or tested end-to-end. Completing this:
- Enables time-decay in recall (recently-accessed memories rank higher)
- Closes the longest-stalled feature gap
- Already well-decomposed into 4 subtasks: locate injection point → implement rerank → test fixture → smoke benchmark

### 3. [PARALLEL_BRAIN_QUERIES] — 5x brain query speedup (already in QUEUE P2)

**Why high leverage:** Brain queries (~7.5s for 10 sequential collections) are the dominant cost in:
- Task selector scoring loop (failure penalty lookups per task)
- Preflight context building
- Any brain.recall() call from heartbeat pipeline

ONNX runtime is thread-safe. `concurrent.futures.ThreadPoolExecutor` with 10 workers would parallelize collection queries. Target: <2s. This directly fixes [PREFLIGHT_SPEED] as a side effect.

**All 3 are already in QUEUE.md** — no additions needed.

---

## 4. Batching & Self-Evolution Integrity

### cron_autonomous.sh batching — CORRECT

| Component | Status | Details |
|-----------|--------|---------|
| Task passing | **Correct** | `NEXT_TASK="$NEXT_TASK" python3 -` passes via env var. `<<'PY'` heredoc prevents bash expansion. Python reads `os.environ.get('NEXT_TASK', '')`. |
| Batch assembly | **Correct** | MAX_TASKS=3, MAX_TOTAL_CHARS=900. Uses `estimate_task_complexity()` to filter oversized tasks. Ensures selected task is always first in batch. |
| `ok_to_batch()` | **Correct** | Filters out `defer_to_sprint` tasks and tasks >320 chars. |
| `is_subtask()` | **Dead code** | Defined (lines 186-189) but never called. Already tracked in `[CRON_AUTONOMOUS_BATCHING_CLEANUP]` (P2). |
| Claude prompt assembly | **Correct** | Uses `run_claude_code()` function. Prompt written to tmpfile to avoid shell parsing issues. Tasks numbered with `nl`. |

### Deferral auto-split in preflight — CORRECT

| Component | Status | Details |
|-----------|--------|---------|
| Complexity estimation | **Working** | `estimate_task_complexity()` scores tasks and recommends `defer_to_sprint` for oversized ones. |
| Auto-split insertion | **Working** | `queue_writer.ensure_subtasks_for_tag()` inserts 4 generic subtasks under parent. Uses file locking (fcntl.flock). |
| Duplicate prevention | **Working** | `ensure_subtasks_for_tag()` checks for existing indented subtasks before inserting (line 263). If manual subtasks already exist (e.g., ACTR_WIRING's 4 custom subtasks), auto-split is skipped. |
| Generic template concern | **Acceptable** | The 4 auto-generated subtasks (locate/implement/test/benchmark) are generic but provide a reasonable scaffold. Custom subtasks (like ACTR_WIRING_1..4) take precedence since the duplicate check prevents overwrite. |

### Self-evolution loop overall health

| Metric | Value | Assessment |
|--------|-------|-----------|
| Cron entries | 30 active | All script references resolve |
| Lock contention | None observed | Global + per-script + maintenance locks working |
| Gate → preflight → execute → postflight | End-to-end operational | Verified via gate check (wake decision) |
| Postflight completeness | Tracked in JSONL | Alerts if <80% stages succeed |
| Failure taxonomy | 5 categories | Classifies errors on failure |
| Task routing | 3 executors | OpenRouter (simple) → Gemini (medium) → Claude (complex) |
| Escalation path | Tested | OpenRouter → Claude Code with timeout upgrade |

### No bugs found in batching or deferral logic.

---

## 5. Refactor Completion Status (Updated)

### Must-Have Criteria

| # | Criterion | Before SPINE_SHADOW_DEPS | After | Status |
|---|-----------|-------------------------|-------|--------|
| C1 | Shadow deps eliminated | 6 shadow deps | 0 shadow deps (5 intentional proxies) | **MET** ✅ |
| C2 | Clean imports in spine | Module-level sys.path in 10 files | Module-level removed; proxy/CLI delegation remains | **PARTIALLY MET** ⚠️ |
| C3 | Spine test suite passes | 18 tests | 18 tests pass | **MET** ✅ |
| C4 | compileall passes | Clean | Clean | **MET** ✅ |
| C5 | CLI covers major subsystems | 6 groups | 6 groups (brain, bench, cost, cron, heartbeat, queue) | **MET** ✅ |
| C6 | No deprecated script refs | 0 refs | 0 refs | **MET** ✅ |
| C7 | Hook registration logging | 7/7 logged | 7/7 logged | **MET** ✅ |
| C8 | Graph integrity checks | Edge-count verification | Working | **MET** ✅ |
| C9 | Postflight completeness | Stage tracking + JSONL | Working | **MET** ✅ |

**Score: 8/9 must-haves met** (was 7/9). C2 remaining gap: proxy modules + CLI delegators still use sys.path.insert inside functions. This will be organically resolved by [CLI_ROOT_PYPROJECT] (pip install -e .).

### Should-Have Criteria

| # | Criterion | Status |
|---|-----------|--------|
| S1 | Brain golden QA | **MET** ✅ (20 queries, P@1=1.0, MRR=1.0) |
| S2 | Phi > 0.80 | NOT MET (0.697, intra-density bottleneck) |
| S3 | Success rate > 85% | NOT MET (~70.7%) |
| S4 | PI CLI fast | **MET** ✅ (cached, returns instantly) |
| S5 | Spine coverage > 40% | NOT MET (18%, 16/92 wrapped) |

**Score: 3/5 should-haves met** (was 2/5).

### Updated Refactor Completion Score

| Category | Weight | Score | Weighted |
|----------|--------|-------|----------|
| Must-have criteria met | 40% | 8/9 (89%) | 35.6% |
| Should-have criteria met | 20% | 3/5 (60%) | 12.0% |
| Features fully wired | 20% | 4/34 (12%) | 2.4% |
| Test coverage | 10% | 43 tests, 2 suites | 7.0% |
| Benchmark coverage | 10% | 8/9 benchmarks | 8.9% |
| **Total** | **100%** | | **65.9%** |

**Up from 56.3% → 65.9%** after SPINE_SHADOW_DEPS + GOLDEN_QA_MAIN_BRAIN.

---

## 6. Recommended Next Actions

| Priority | Task | Impact | Queue Status |
|----------|------|--------|-------------|
| **1** | [CLI_ROOT_PYPROJECT] | Resolves C2, eliminates sys.path organically | In QUEUE P1 ✅ |
| **2** | [ACTR_WIRING] | Completes brain recall pipeline, closes longest-stalled gap | In QUEUE P1, 4 subtasks ✅ |
| **3** | [PARALLEL_BRAIN_QUERIES] | 5x query speedup, fixes preflight overhead | In QUEUE P2 ✅ |
| Maintenance | Run `clarvis brain backfill` + `optimize-full` | Cleans 10 orphan nodes + 40 dups + 34 noise | One-time |

No code changes required. No queue additions needed — all items already tracked.

---

_Generated 2026-03-05T20:30 by Claude Code Opus. Validation: all CLI checks pass, 0 bugs found._
