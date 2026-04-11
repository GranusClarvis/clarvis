# Spine Architecture Review — 2026-04-10

_Post-wiki-refactor whole-system review of `clarvis/` spine: subsystem boundaries, layout, growth patterns, mislocated modules, dead code, scaling risks, and alignment with runtime behavior._

---

## Executive Summary

The spine is **well-architected** overall. 14 subpackages, ~54k lines, clear layering (brain → memory/cognition → context → heartbeat → orch/queue). Dependency inversion via hooks and registries prevents circular imports. The main issues are: oversized modules, dead/experimental code, a monolithic brain `__init__.py`, and a few mislocated concerns.

**Recommended actions** (prioritized):

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 1 | Purge dead modules (soar, synaptic_memory, metacognition) | Reduces surface area by ~2.8k lines | Small |
| 2 | Split brain/__init__.py (723 lines — too much logic for an init) | Cleaner imports, faster startup | Medium |
| 3 | Move `research_config.py` into a subpackage | Mislocated at spine root | Small |
| 4 | Add deprecation warnings to orch/queue_engine.py shim | Prevents stale callers | Small |
| 5 | Consolidate oversized modules (memory_consolidation 2k, self_model 1.6k) | Maintainability | Medium |
| 6 | Mark experimental metrics modules explicitly | Prevents confusion | Small |
| 7 | Consider extracting PR intake from orch/ | orch/ scope creep | Medium |

---

## 1. Subpackage Boundaries — Assessment

### 1.1 Well-Bounded Subsystems (no action needed)

| Package | Lines | Purpose | Verdict |
|---------|-------|---------|---------|
| `brain/` | ~5.5k | ChromaDB + graph + search + store | Core, well-split via mixins |
| `heartbeat/` | ~3.5k | Gate → preflight → execute → postflight | Clean pipeline, hook-based |
| `queue/` | ~1.4k | Evolution queue engine + writer | Recently extracted from orch, clean |
| `runtime/` | ~0.5k | Operating mode control | Small, focused |
| `wiki/` | ~1.0k | Knowledge canonicalization | New, well-scoped |
| `adapters/` | ~0.5k | Host extraction boundary | Thin, correct |
| `compat/` | ~0.4k | Host compatibility contracts | Thin, correct |

### 1.2 Subsystems Needing Attention

**`cognition/` (13 modules, ~10k lines)** — Largest subpackage by module count. Contains genuinely distinct concerns:
- Core cognitive: attention, confidence, context_relevance, cognitive_load
- Reasoning: reasoning.py, reasoning_chains.py, thought_protocol.py
- Social/affective: somatic_markers.py, obligations.py
- Meta: metacognition.py (DEAD — zero external imports), intrinsic_assessment.py
- Broadcasting: workspace_broadcast.py

**Recommendation**: No split needed yet — the cognitive metaphor holds. But `metacognition.py` should be deleted (dead code) and `obligations.py` (797 lines) should be reviewed for scope creep.

**`memory/` (9 modules, ~8.5k lines)** — Contains two dead modules:
- `soar.py` (827 lines) — SOAR architecture, not exported, no external imports
- `synaptic_memory.py` (1010 lines) — not exported, no external imports

**Recommendation**: Delete both. That's 1.8k lines of dead code.

**`metrics/` (17 modules, ~9k lines)** — Split between production and experimental:
- Production (in `__init__.py`): phi, quality, self_model, benchmark, code_validation, memory_audit
- Experimental (NOT exported): clr, clr_benchmark, clr_reports, clr_perturbation, ablation_v3, beam, longmemeval, membench, trajectory, evidence_scoring, cot_evaluator

**Recommendation**: Mark experimental modules with a `_experimental_` prefix or move to `metrics/experimental/` subdir. 11 of 17 modules are not part of the public API.

**`orch/` (11 modules, ~5k lines)** — Contains task orchestration, cost tracking, AND PR triage:
- Core orch: router.py, task_selector.py, scoreboard.py
- Cost: cost_tracker.py, cost_api.py, cost_optimizer.py
- PR: pr_intake.py (828 lines), pr_indexes.py, pr_rules.py
- Legacy shim: queue_engine.py (re-exports from queue/)

**Recommendation**: PR intake is a distinct concern (~1.5k lines across 3 files). Consider `clarvis/pr/` if it grows further. Add deprecation warning to queue_engine.py.

**`context/` (9 modules, ~4.5k lines)** — Well-bounded but `assembly.py` at 1570 lines is the largest single module. Contains: prompt building, compression, budgets, MMR, DYCP, knowledge synthesis, GC.

**Recommendation**: `assembly.py` is doing too much. Consider splitting the brief-generation logic from the assembly orchestration.

**`learning/` (1 module, 1149 lines)** — Single-file subpackage containing `meta_learning.py`. A full subpackage for one file is overhead.

**Recommendation**: If no additional learning modules are planned within 2 months, inline into `cognition/` or collapse to `clarvis/meta_learning.py`.

### 1.3 Spine Root Issues

The `clarvis/` root contains:
- 17 `cli_*.py` files — correct location, lazy-loaded
- `research_config.py` (160 lines) — **mislocated**. This is runtime configuration for research pipelines, not a CLI or core module.
- `_script_loader.py` (35 lines) — correct, infrastructure utility

**Recommendation**: Move `research_config.py` into `clarvis/orch/research_config.py` or `clarvis/context/research_config.py` (it configures research context assembly).

---

## 2. brain/__init__.py — Monolith Risk

At 723 lines, `brain/__init__.py` is the largest init file and contains the full `ClarvisBrain` class definition (not just re-exports). This is the main architectural smell in the spine.

The class uses mixin composition: `ClarvisBrain(StoreMixin, GraphMixin, SearchMixin)` — the mixins are properly split into separate files. But the init still holds:
- Class definition with hook registries
- Lazy singleton `get_brain()` / module-level `brain` instance
- Convenience functions (`search`, `remember`, `capture`, etc.)
- Collection routing setup

**Recommendation**: Extract the class definition into `brain/core.py`, keep `__init__.py` as a thin re-export layer (~50 lines). This is the single highest-value refactor.

---

## 3. Dead Code Inventory

| Module | Lines | Status | Evidence |
|--------|-------|--------|----------|
| `memory/soar.py` | 827 | Dead | Not in `__init__`, zero grep hits for `from clarvis.memory.soar` |
| `memory/synaptic_memory.py` | 1010 | Dead | Not in `__init__`, zero grep hits |
| `cognition/metacognition.py` | 669 | Dead | Not in `__init__`, zero external imports |
| `orch/queue_engine.py` | ~50 | Shim | Re-exports from `queue/engine`, no deprecation warning |

**Total dead code: ~2,556 lines** (4.7% of spine).

Note: The QUEUE.md already has a `[DEAD_CODE_PURGE]` task targeting scripts/. This review covers only spine dead code.

---

## 4. Oversized Modules

Modules over 1000 lines that may benefit from decomposition:

| Module | Lines | Recommendation |
|--------|-------|----------------|
| `memory/memory_consolidation.py` | 2008 | Split: dedup, merge, prune, archive into separate files |
| `metrics/self_model.py` | 1575 | Split: model definition vs. measurement vs. reporting |
| `context/assembly.py` | 1570 | Split: brief generation vs. assembly orchestration |
| `memory/episodic_memory.py` | 1308 | Acceptable — single coherent class |
| `cognition/attention.py` | 1263 | Acceptable — GWT is inherently complex |
| `brain/search.py` | 1246 | Acceptable — search pipeline is linear |
| `queue/engine.py` | 1149 | Acceptable — state machine logic |
| `learning/meta_learning.py` | 1149 | Review if it grows further |

---

## 5. Growth Patterns & Scaling Risks

### 5.1 Healthy Patterns
- **Hook-based decoupling**: brain hooks, heartbeat registry, retrieval hooks — prevents tight coupling as new features are added
- **Lazy imports**: CLI modules use lazy registration, brain uses lazy singleton
- **Script loader**: `_script_loader.py` prevents sys.path mutation for script-to-script imports
- **Mixin composition**: brain mixins keep the class manageable despite complexity

### 5.2 Risks
- **cognition/ sprawl**: 13 modules, some barely related (obligations vs. attention vs. workspace_broadcast). If more cognitive modules are added, consider sub-subpackages.
- **metrics/ experimental sprawl**: 11 of 17 modules are experimental adapters. Without namespace separation, it's unclear what's production vs. research.
- **CLI file count**: 17 cli_*.py files at the root. If this grows past ~20, consider a `clarvis/cli/` subpackage.
- **Single-file subpackages**: `learning/` (1 file) and `queue/` (2 files) have subpackage overhead for minimal content.

---

## 6. Alignment with Runtime Behavior

### What's actually used at runtime (cron/heartbeat path):
1. `heartbeat/` (gate, adapters, brain_bridge, hooks) — ✅ well-aligned
2. `brain/` (search, store, graph) — ✅ core, always loaded
3. `cognition/attention.py` — ✅ GWT scoring in preflight
4. `context/assembly.py`, `compressor.py` — ✅ context building
5. `memory/episodic_memory.py`, `cognitive_workspace.py` — ✅ episode recall
6. `orch/task_selector.py`, `queue/engine.py` — ✅ task selection
7. `metrics/benchmark.py`, `quality.py` — ✅ postflight metrics

### What's NOT used at runtime:
- `metrics/clr*.py`, `beam.py`, `longmemeval.py`, `membench.py` — benchmark-only (cron)
- `memory/soar.py`, `synaptic_memory.py` — dead
- `cognition/metacognition.py` — dead
- `learning/meta_learning.py` — cron-only (not heartbeat path)
- `compat/`, `adapters/` — install/bootstrap only

Runtime alignment is **good**. The hot path (heartbeat) touches the right modules.

---

## 7. Concrete Action Plan

### Immediate (this sprint)
1. **Delete** `memory/soar.py`, `memory/synaptic_memory.py`, `cognition/metacognition.py`
2. **Add deprecation warning** to `orch/queue_engine.py`
3. **Move** `research_config.py` → `orch/research_config.py`

### Next sprint
4. **Extract** `brain/core.py` from `brain/__init__.py` (class definition → core.py, init becomes re-exports)
5. **Create** `metrics/experimental/` for non-production benchmark adapters
6. **Split** `memory/memory_consolidation.py` into focused modules

### Backlog
7. **Review** `orch/pr_*.py` extraction into `clarvis/pr/` if PR features grow
8. **Review** `learning/` — inline if no new modules added by 2026-06
9. **Split** `context/assembly.py` when it next needs modification

---

_Review performed by spine architecture analysis, 2026-04-10. All findings verified against current codebase._
