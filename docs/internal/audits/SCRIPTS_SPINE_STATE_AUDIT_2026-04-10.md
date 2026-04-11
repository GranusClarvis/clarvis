# Scripts / Spine State Audit — 2026-04-10

## Executive Summary

The `clarvis/` spine and `scripts/` boundary is **structurally sound and well-enforced**. The migration from standalone packages to a unified spine is complete. The system is not perfect — there are minor legacy artifacts and ~31 scripts with substantial logic that *could* eventually migrate — but the architecture is coherent, the boundary is clear, and further cleanup is low-leverage relative to the current state.

**Verdict: Done enough. Focus effort elsewhere.**

---

## Current-State Verdict

| Dimension | Status | Evidence |
|-----------|--------|----------|
| Spine = importable library | **YES** | 125 modules, 13 subpackages, zero `sys.path` manipulation in spine |
| Scripts = entrypoints/wrappers | **YES (mostly)** | 20 bridge wrappers, 38 entrypoints, 32 shell orchestrators. 67 standalone scripts with domain logic — acceptable, not urgent |
| Package migration complete | **YES** | `packages/` directory cleared. `clarvis.brain`, `clarvis.orch.cost_*`, `clarvis.cognition.reasoning*`, `clarvis.queue` all live in spine |
| Import discipline | **GOOD** | 0 sys.path in spine. 3 in scripts (1 legacy `_paths.py`, 2 in subprocess/docs context). 7 spine modules use `_script_loader` cleanly |
| CLI architecture | **CLEAN** | 16 typer subcommands, all implementations present, lazy registration |
| Test coverage | **ADEQUATE** | 83 test files, 26 spine modules with dedicated tests. Core systems (brain, queue, metrics, heartbeat) covered |
| No duplicate logic | **CONFIRMED** | `search()`, `remember()`, `recall()` all delegate to single spine implementation. `lite_brain.py` is intentionally separate (project-agent isolation) |

---

## Healthy Areas (No Action Needed)

### 1. Brain Subsystem (`clarvis/brain/`, 22 modules)
Production-ready. ChromaDB + SQLite graph backend live since 2026-03-29. Full pipeline: store → search → graph → retrieval quality → secret redaction. ACT-R scoring, LLM reranking, RL-lite feedback all wired.

### 2. Cognition Subsystem (`clarvis/cognition/`, 13 modules)
Complete. GWT attention, confidence calibration, reasoning chains, metacognition, somatic markers, cognitive load regulation all implemented and production-wired via heartbeat hooks.

### 3. Context Subsystem (`clarvis/context/`, 10 modules)
Clean pipeline: compression → assembly → A/B testing → archival. Adaptive MMR, dynamic pruning, prompt optimization all in place.

### 4. Heartbeat Pipeline (`clarvis/heartbeat/` + `scripts/pipeline/`)
Well-designed split: spine provides hooks/gate/bridge; scripts provide batched preflight/postflight orchestration. The batching saves ~4.5s per heartbeat by consolidating 15+ subprocess calls.

### 5. Queue System (`clarvis/queue/`, 2 modules)
Successfully extracted from `orch/` to dedicated package (2026-04-04). Backward-compat shim in `orch/queue_engine.py` maintained. Sidecar state machine + QUEUE.md parser working.

### 6. Cron Shell Scripts (`scripts/cron/`, 23 files)
Excellent quality. All source `cron_env.sh`, all use `lock_helper.sh`, all emit dashboard events. Consistent pattern: lock → step → emit → capture → unlock.

### 7. Bridge/Wrapper Scripts (20 scripts)
Clean delegation pattern. Examples: `scripts/brain_mem/brain.py` → `clarvis.brain`, `scripts/infra/cost_tracker.py` → `clarvis.orch.cost_tracker`, `scripts/tools/prompt_builder.py` → `clarvis.context.prompt_builder`. All maintain backward-compatible CLI while spine holds the logic.

---

## Incomplete / Iffy Areas

### 1. Standalone Scripts with Substantial Logic (~31 scripts)
These contain real domain logic but work as scripts because they're tightly coupled to cron lifecycle, file I/O, and operational concerns. Not urgent to migrate.

**Strongest candidates for eventual spine migration** (stable, production-wired, reusable logic):
- `scripts/cognition/knowledge_synthesis.py` — cross-domain connection finding
- `scripts/brain_mem/retrieval_experiment.py` — query routing patterns
- `scripts/hooks/intra_linker.py` — graph edge density boosting
- `scripts/evolution/failure_amplifier.py` — soft failure detection

**Leave as scripts** (too operational, too cron-coupled, or experimental):
- `scripts/cognition/absolute_zero.py` — AZR self-play (research, cron-only)
- `scripts/cognition/dream_engine.py` — counterfactual dreaming (experimental)
- `scripts/cognition/world_models.py` — Ha & Schmidhuber models (research)
- `scripts/cognition/causal_model.py` — Pearl's causal inference (research, possibly dead)
- `scripts/hooks/hyperon_atomspace.py` — OpenCog Hyperon (research)

### 2. Misclassified Modules in Prior Audit
The SPINE_USAGE_AUDIT flagged 3 modules as "research prototype with zero callers" that are actually production-wired:
- `theory_of_mind.py` — wired via `session_hook.py`
- `automation_insights.py` — wired via `heartbeat_preflight.py`
- `hyperon_atomspace.py` — wired via `heartbeat_postflight.py`

These should be reclassified. Not urgent, but the prior audit document is misleading on this point.

### 3. Partial Spine Modules (3 modules, all low-priority)

| Module | Status | Impact |
|--------|--------|--------|
| `clarvis/learning/meta_learning.py` | Skeleton with 5 strategies documented, minimal implementation | Low — not wired into heartbeat |
| `clarvis/compat/contracts.py` | OpenClaw-only, Hermes/NanoClaw deferred | Low — no fork consumers yet |
| `clarvis/wiki/canonical.py` | ~80% complete, downstream integration minimal | Low — wiki is aspirational |

### 4. `__main__` Blocks in Spine Modules (32 modules)
Twenty-nine percent of spine modules have `if __name__ == "__main__"` blocks. These are mostly validation/testing harnesses, not CLI entrypoints, so this is acceptable. The canonical CLI lives in `clarvis/cli.py` with 16 subcommands. No action needed, but new spine modules should prefer adding CLI to `cli_*.py` files.

### 5. Legacy `_paths.py`
`scripts/_paths.py` exists as a centralized `sys.path` bootstrapper for old scripts. Only 1 script (`pr_factory.py`) still uses the legacy `sys.path.insert` pattern directly. Safe to keep but deprecated.

---

## Concrete Recommendations

### Do Now (if convenient, not urgent)
1. **Reconcile SPINE_USAGE_AUDIT.md** — update classifications for theory_of_mind, automation_insights, hyperon_atomspace. 15 minutes of doc editing.

### Do When Touching These Files Anyway
2. **Convert `pr_factory.py` sys.path usage** to `_script_loader` or direct spine imports.
3. **Verify `causal_model.py` and `world_models.py` cron wiring** — if no cron script calls them, mark as research-only or archive.

### Do in Next Quarter (if spine growth continues)
4. **Migrate `knowledge_synthesis.py`** to `clarvis/context/knowledge_synthesis.py` (it's already partially there as a shim).
5. **Migrate `intra_linker.py`** graph logic to `clarvis/brain/` (it operates on brain graph edges).
6. **Consolidate `retrieval_experiment.py`** query routing into `clarvis/brain/retrieval_gate.py` once stable.

### Do NOT Touch
- The 20 bridge/wrapper scripts — they're working, backward-compatible, and correctly placed.
- The cron shell scripts — excellent quality, no changes needed.
- The `_script_loader` mechanism — it's pragmatic and working.
- `lite_brain.py` — intentionally standalone for project-agent isolation.
- The 32 `__main__` blocks in spine — they're dev/test harnesses, not a problem.
- `clarvis/compat/` and `clarvis/learning/` stubs — wait for actual consumers.

---

## Architecture Strengths Worth Preserving

1. **Hook-based dependency inversion** — `brain.py` doesn't import cognition modules; they register hooks via `brain/hooks.py`. This prevents circular imports and keeps the brain subsystem independent.
2. **Mixin composition** — `ClarvisBrain = StoreMixin + GraphMixin + SearchMixin`. Clean, testable, composable.
3. **Sidecar pattern** — Queue engine manages state alongside QUEUE.md without two-phase commit complexity.
4. **Lazy CLI registration** — `cli.py` defers subcommand imports until invoked. Fast startup.
5. **`_script_loader`** — clean importlib-based cross-script loading without `sys.path` pollution.

---

## Quantitative Summary

| Metric | Value |
|--------|-------|
| Spine modules | 125 Python files across 13 subpackages |
| Spine LOC (est.) | ~50K |
| Scripts total | 177 files (145 Python, 32 shell) |
| Bridge/wrapper scripts | 20 (clean delegation to spine) |
| Entrypoint scripts | 38 (CLI/cron, properly operational) |
| Standalone scripts | 67 (domain logic, mostly acceptable as-is) |
| Legacy/deprecated | 2 (`_paths.py`, `task_router.py`) |
| sys.path in spine | 0 |
| sys.path in scripts | 3 (contained, non-problematic) |
| CLI subcommands | 16 (all implemented) |
| Test files | 83 (26 spine modules with dedicated coverage) |
| Orphaned tests | 0 |
| Duplicate logic | 0 (confirmed) |

---

## Final Verdict

The spine/scripts architecture is **genuinely clean, not just "much better than before."** The package migration is complete, the import discipline holds, the CLI is unified, and the boundary is well-enforced. The 67 standalone scripts with domain logic are a natural consequence of a system with 47 cron entries and complex operational lifecycle — not every piece of logic belongs in an importable library.

The remaining work is incremental refinement (4-6 module migrations over the next quarter), not structural repair. The highest-leverage structural task is already done.

**Status: COMPLETE. Move on to higher-value work.**
