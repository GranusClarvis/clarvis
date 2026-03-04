# Structure & Integrity Audit — 2026-03-04

Post-spine migration audit. Brutally honest assessment of system integrity, scalability, and gaps.

## TL;DR

The clarvis/ spine migration is **structurally sound** — all 16 modules compile, 610/610 tests pass, CLI works, and the brain holds 2,136 memories across 10 collections with 53,856 graph edges. But only **18% of business logic** (10,139 LOC) lives in the canonical `clarvis/` package. The remaining **82% (46,808 LOC)** still lives in `scripts/` as independent scripts with their own `__main__` blocks, direct `sys.path` hacks, and no package imports. The spine is a skeleton, not a body. The cron pipeline still calls `python3 scripts/X.py` everywhere — it doesn't know the spine exists.

**Verdict: Good bones. Not yet scalable. Migration is ~20% done.**

---

## 1. Repo Structure Audit

### Intended Boundaries

| Directory | Purpose | Boundary Rule |
|-----------|---------|---------------|
| `clarvis/` | Canonical library — importable package | Business logic lives here. No `if __name__` blocks. No `sys.path` hacks. |
| `scripts/` | Entrypoints + thin wrappers | CLI wrappers, cron shell scripts. Delegates to `clarvis.*`. No business logic. |
| `docs/` | Architecture, runbooks, procedures | Human-readable. Versioned with code. |
| `memory/` | Runtime state — evolution queue, cron digests, daily logs | Git-tracked state files. Not code. |
| `data/` | Persistent data — ChromaDB, episodes, calibration, benchmarks | .gitignored runtime data. |
| `tests/` | Test suite | Tests `clarvis/` package, not `scripts/`. |
| `packages/` | Standalone pip packages (`clarvis-db`, `clarvis-cost`, `clarvis-reasoning`) | May be absorbed into `clarvis/` eventually. |

### Violations Found

| Violation | Severity | Files | Recommendation |
|-----------|----------|-------|----------------|
| **Business logic in scripts/** | HIGH | 94 of 103 .py files contain original logic, not wrappers | Migrate in waves (see §6) |
| **No `[project.scripts]` in pyproject.toml** | MEDIUM | `pyproject.toml` missing `clarvis = "clarvis.cli:main"` | Add it — `clarvis` binary should be on PATH |
| **sys.path hacks everywhere** | MEDIUM | Every script starts with `sys.path.insert(0, ...)` | Spine migration eliminates this pattern |
| **scripts/ has 1.77M bytes vs clarvis/ 10K lines** | INFO | 4.6:1 ratio (scripts:clarvis) | Target: invert this ratio over 3 months |

### What's Correctly Placed

- `clarvis/brain/` — full ClarvisBrain implementation (store, search, graph, hooks, constants)
- `clarvis/memory/` — episodic, procedural, Hebbian, consolidation, working memory
- `clarvis/cognition/` — attention (GWT), confidence, thought protocol
- `clarvis/heartbeat/` — hook registry + adapters
- `clarvis/cli_*.py` — Typer CLI modules (brain, bench, heartbeat, queue)

---

## 2. Feature Integrity Audit

### Legend
- **WIRED**: Imported and exercised by heartbeat/cron pipeline
- **CLI-ONLY**: Has `__main__` block but never imported by pipeline
- **UNWIRED**: Built but not called from anywhere
- **BROKEN**: Import or runtime error

### Core Brain & Memory

| Feature | Module | Location | Status | Notes |
|---------|--------|----------|--------|-------|
| Brain store/recall | `ClarvisBrain` | `clarvis/brain/` | WIRED | 2,136 memories, 53,856 edges. Central dependency. |
| Graph relationships | `GraphMixin` | `clarvis/brain/graph.py` | WIRED | Atomic writes with fcntl. |
| Brain hooks | `register_default_hooks` | `clarvis/brain/hooks.py` | WIRED | 6 hook factories (ACT-R, attention, Hebbian, etc.) |
| Episodic memory | `EpisodicMemory` | `clarvis/memory/episodic_memory.py` | WIRED | 500-episode cap, causal DAG, ACT-R activation. |
| Procedural memory | `ProceduralMemory` | `clarvis/memory/procedural_memory.py` | WIRED | Skill lifecycle, 10 code templates, CLI. |
| Hebbian memory | `HebbianMemory` | `clarvis/memory/hebbian_memory.py` | WIRED | Co-activation, EWC Fisher importance. |
| Memory consolidation | Consolidation pipeline | `clarvis/memory/memory_consolidation.py` | WIRED | Dedup, merge, decay, archive, GWT integration. |
| Working memory | GWT delegation | `clarvis/memory/working_memory.py` | WIRED | Thin wrapper over attention.py. |
| Synaptic memory | Memristor-inspired SQLite | `scripts/synaptic_memory.py` | CLI-ONLY | Referenced in cron but not imported by heartbeat. |
| ACT-R activation | Power-law decay | `scripts/actr_activation.py` | UNWIRED | Stalled since Phase 2. In QUEUE.md as [ACTR_WIRING]. |

### Cognition & Consciousness

| Feature | Module | Location | Status | Notes |
|---------|--------|----------|--------|-------|
| Attention (GWT) | Global Workspace | `clarvis/cognition/attention.py` | WIRED | 7±2 spotlight, salience scoring, broadcast. |
| Confidence tracking | Bayesian calibration | `clarvis/cognition/confidence.py` | WIRED | Predictions, Brier scoring, JSONL persistence. |
| Thought protocol | ThoughtScript DSL | `clarvis/cognition/thought_protocol.py` | WIRED | Signals, relations, decision frames. |
| Somatic markers | Valence signals | `scripts/somatic_markers.py` | WIRED | Imported in heartbeat_preflight. |
| SOAR engine | Impasse resolution | `scripts/soar_engine.py` | WIRED | Imported in heartbeat_postflight. |
| World models | Ha & Schmidhuber | `scripts/world_models.py` | WIRED | Prediction (preflight) + adaptation (postflight). |
| Causal models | SCM + counterfactuals | `scripts/causal_model.py` | WIRED | Used by dream_engine + clarvis_reasoning. |
| Theory of Mind | User modeling | `scripts/theory_of_mind.py` | WIRED | session_hook.py observes user sessions. |
| Cognitive workspace | Baddeley model | `scripts/cognitive_workspace.py` | WIRED | Preflight set_task, postflight close_task. |
| Phi metric (IIT) | Consciousness proxy | `scripts/phi_metric.py` | CLI-ONLY | Cron-spawned but not heartbeat-integrated. |
| Self-model | 7 capability domains | `scripts/self_model.py` | CLI-ONLY | 67KB — largest script. Cron-spawned. |

### Self-Improvement & Evolution

| Feature | Module | Location | Status | Notes |
|---------|--------|----------|--------|-------|
| Meta-gradient RL | Policy gradient | `scripts/meta_gradient_rl.py` | WIRED | Postflight adapt(). |
| Hyperon Atomspace | Symbolic reasoning | `scripts/hyperon_atomspace.py` | WIRED | Postflight integration. |
| Parameter evolution | MCMC optimization | `scripts/parameter_evolution.py` | WIRED | evolution_preflight.py. |
| Absolute Zero (AZR) | Self-play reasoning | `scripts/absolute_zero.py` | **UNWIRED** | CLI-only. Never called from pipeline. |
| Meta-learning | Strategy analysis | `scripts/meta_learning.py` | **UNWIRED** | CLI-only. Referenced in docstrings only. |
| Failure amplifier | Stress testing | `scripts/failure_amplifier.py` | **UNWIRED** | CLI-only. Performance comments only. |
| GraphRAG communities | Community detection | `scripts/graphrag_communities.py` | **UNWIRED** | CLI-only. Not imported. |
| Conversation learner | Pattern analysis | `scripts/conversation_learner.py` | **UNWIRED** | CLI-only. Not integrated. |

### Heartbeat Pipeline

| Feature | Module | Location | Status | Notes |
|---------|--------|----------|--------|-------|
| Gate (zero-LLM) | Pre-check | `scripts/heartbeat_gate.py` | WIRED | Exit 0=WAKE, 1=SKIP. Works via CLI. |
| Preflight | Task selection + context | `scripts/heartbeat_preflight.py` | WIRED | 35KB. Batched subprocess replacement. |
| Postflight | Episode + recording | `scripts/heartbeat_postflight.py` | WIRED | 55KB. Batched subprocess replacement. |
| Hook registry | Priority execution | `clarvis/heartbeat/hooks.py` | WIRED | 10-90 priority bands, fault isolation. |
| Adapters | Subsystem bridges | `clarvis/heartbeat/adapters.py` | WIRED | Procedural, consolidation, metrics. |

### Infrastructure & Tools

| Feature | Module | Location | Status | Notes |
|---------|--------|----------|--------|-------|
| Performance benchmark | 8-dimension PI | `scripts/performance_benchmark.py` | WIRED | Quick check in postflight. CLI works. |
| Task router | Complexity-based | `scripts/task_router.py` | WIRED | Cron-called. M2.5/GLM-5/Claude routing. |
| Project agent | Multi-project orchestrator | `scripts/project_agent.py` | WIRED | spawn→PR→promote pipeline. |
| Browser agent | Playwright CDP | `scripts/browser_agent.py` | CLI-ONLY | Manual invocation only. |
| Clarvis Browser | Unified browser API | `scripts/clarvis_browser.py` | CLI-ONLY | Agent-Browser + Playwright. |
| Local vision | Qwen3-VL (Ollama) | `scripts/local_vision_test.py` | CLI-ONLY | On-demand only. |
| Dream engine | Counterfactual | `scripts/dream_engine.py` | WIRED | Cron 02:45 standalone. |
| Cost tracking | OpenRouter usage | `scripts/cost_tracker.py` | WIRED | CLI + Telegram reports. |

### Summary: 5 Unwired Features That Matter for AGI

1. **Absolute Zero (AZR)** — Self-play reasoning generates unbounded tasks. Critical for autonomous curriculum learning. Should be a cron job or heartbeat mode.
2. **Meta-learning** — Learn HOW to learn. Strategy effectiveness data exists but is never analyzed automatically.
3. **GraphRAG communities** — Community detection would improve brain retrieval quality. Should feed into brain.recall().
4. **Failure amplifier** — Stress-testing for bias discovery. Should run after successful heartbeats to probe edge cases.
5. **ACT-R activation wiring** — Power-law decay scoring for recall. The longest-stalled queue item.

---

## 3. CLI Audit

### Sanity Checks

```
$ python3 -m compileall -q clarvis     → PASS (no errors)
$ python3 -m clarvis --help            → PASS (4 subcommands)
$ python3 -m clarvis brain stats       → PASS (2,136 memories)
$ python3 -m clarvis bench pi          → PASS (PI: N/A — no recent benchmark data)
$ python3 -m clarvis heartbeat gate    → PASS (WAKE decision)
$ python3 -m clarvis queue status      → PASS (40 pending)
```

### Current Commands (4 subgroups, 18 commands)

| Subgroup | Commands | Delegates To |
|----------|----------|--------------|
| `brain` | health, stats, search, optimize, optimize-full, backfill, recent, stale, crosslink | `clarvis.brain` (canonical) |
| `bench` | run, quick, pi | `scripts/performance_benchmark.py` (not yet in clarvis/) |
| `heartbeat` | run, gate | `scripts/heartbeat_gate.py` + `scripts/heartbeat_preflight.py` |
| `queue` | next, status, add, archive | Parses `memory/evolution/QUEUE.md` directly |

### Delegation Correctness

- `brain` — **CORRECT**: Delegates to `clarvis.brain.*`. Canonical source.
- `bench` — **INDIRECT**: CLI is in `clarvis/cli_bench.py` but calls `scripts/performance_benchmark.py` via sys.path. The benchmark logic is NOT in `clarvis/metrics/` yet.
- `heartbeat` — **INDIRECT**: CLI calls `scripts/heartbeat_gate.py` and `scripts/heartbeat_preflight.py` via sys.path.
- `queue` — **CORRECT**: Self-contained queue parser in `clarvis/cli_queue.py`.

### Bug Found

```python
# clarvis/heartbeat/__init__.py exports:
from .hooks import registry, HookPhase

# But HookRegistry class is NOT exported. This import fails:
from clarvis.heartbeat import HookRegistry  # ImportError
```

Fix: Add `HookRegistry` to the `__init__.py` exports.

### Missing Subcommands (prioritized)

| Priority | Subcommand | Purpose | Queue Task |
|----------|-----------|---------|------------|
| P0 | `clarvis cron list` | Parse crontab, show schedule | [CLI_CRON_STUB] — already queued |
| P0 | `clarvis cron status` | Last run times from logs | [CLI_CRON_STUB] — already queued |
| P1 | `clarvis bench record` | Full benchmark + record | [CLI_BENCH_EXPAND] — already queued |
| P1 | `clarvis bench trend` | Show trend over N days | [CLI_BENCH_EXPAND] — already queued |
| P1 | `clarvis heartbeat preflight` | Run preflight only, JSON output | [CLI_HEARTBEAT_EXPAND] — already queued |
| P1 | `clarvis heartbeat postflight` | Accept exit-code + output args | [CLI_HEARTBEAT_EXPAND] — already queued |
| P2 | `clarvis cost daily` | Today's API spend | Not queued |
| P2 | `clarvis cost budget` | Budget status | Not queued |
| P2 | `clarvis phi` | Integrated information score | Not queued |
| P2 | `clarvis self-model` | 7-domain capability scores | Not queued |

### pyproject.toml Gap

```toml
# MISSING from pyproject.toml:
[project.scripts]
clarvis = "clarvis.cli:main"
```

Without this, `clarvis` binary is not on PATH after `pip install -e .`. Must invoke as `python3 -m clarvis`. Queue task [CLI_CONSOLE_SCRIPT] covers this.

---

## 4. BOOT/AGENTS Drift Audit

### Critical Issues

| File | Line | Issue | Severity |
|------|------|-------|----------|
| `BOOT.md` | 12 | `from clarvis_memory import clarvis_context` — module is deprecated | **HIGH** — import fails on gateway startup |
| `SELF.md` | 20, 51, 119-126 | PM2 references — should be systemd | **HIGH** — wrong restart procedure |
| `SELF.md` | 43 | "42 memories, 7 collections" — actually 2,136 memories, 10 collections | MEDIUM — stale numbers |
| `AGENTS.md` | 32 | References `BOOTSTRAP.md` — doesn't exist | LOW — confusing but non-breaking |

### Correctly Updated Files

- `HEARTBEAT.md` — Pipeline description matches current code
- `MEMORY.md` — Up to date
- `ROADMAP.md` — Comprehensive, tracks spine migration
- `docs/RUNBOOK.md` — Correctly says "systemd, NOT pm2"

### Recommended Fixes

1. **BOOT.md** (line 12): Replace `from clarvis_memory import clarvis_context` with:
   ```python
   from clarvis.brain import brain, search, remember, capture
   ```
   Remove the `clarvis_context()` call (line 17) — brain.stats() is sufficient.

2. **SELF.md**: Replace all PM2 references with systemd equivalents. Update stats to say "2000+ memories, 10 collections" (or make it dynamic).

3. **AGENTS.md** (line 32): Remove BOOTSTRAP.md reference or update to BOOT.md.

---

## 5. Tests & Gates

### Current Coverage

| Suite | Files | Tests | Pass Rate | What It Tests |
|-------|-------|-------|-----------|---------------|
| `tests/` | 6 files | 610 | **100%** | Brain, memory, cognition, heartbeat, critical paths |
| `scripts/tests/` | 2 files | 61 | — | Smoke imports, project agent |
| `packages/clarvis-db/tests/` | 1 file | 25 | — | Hebbian + synaptic engines |
| `packages/clarvis-cost/tests/` | 0 | 0 | — | **No tests** |
| `packages/clarvis-reasoning/tests/` | 0 | 0 | — | **No tests** |

**Total: 696 test functions, 610 verified passing (workspace/tests/).**

### Gaps

1. **No CLI tests** — `python3 -m clarvis brain stats` works but isn't tested. Queue task [CLI_TESTS] exists.
2. **No integration tests** — heartbeat pipeline (gate→preflight→postflight) is only tested via mocks, never end-to-end.
3. **No import graph validation** — circular imports could silently break. `scripts/import_health.py` exists but isn't in CI.
4. **No compileall gate** — `python3 -m compileall -q clarvis` passes now but nothing prevents regressions.
5. **Packages without tests** — `clarvis-cost` and `clarvis-reasoning` have zero tests.

### Proposed "Scalability Gate Suite"

Minimal CI/pre-commit checks that prevent regressions during spine migration:

```bash
# Gate 1: Compile check (catches syntax errors)
python3 -m compileall -q clarvis scripts/

# Gate 2: Import graph health (catches circular imports)
python3 scripts/import_health.py --check

# Gate 3: Spine smoke test (catches broken re-exports)
python3 -c "from clarvis.brain import brain; print(brain.stats()['total_memories'])"
python3 -m clarvis brain stats > /dev/null
python3 -m clarvis queue status > /dev/null

# Gate 4: Full test suite
python3 -m pytest tests/ -q --tb=short

# Gate 5: Cron pilot soak (post-migration)
# After migrating a cron job to `clarvis cron run X`, soak for 7 days
# Monitor: exit codes, runtime, output match vs old script
```

---

## 6. Queue Alignment

### Already Queued (confirmed present in QUEUE.md)

All major gaps identified in this audit are already captured:

| Gap | Queue Task | Priority |
|-----|-----------|----------|
| `[project.scripts]` missing | [CLI_CONSOLE_SCRIPT] + [CLI_ROOT_PYPROJECT] | P3 (Pillar 3) |
| CLI tests missing | [CLI_TESTS] | P3 |
| Cron CLI stub | [CLI_CRON_STUB] + [CLI_CRON_SUBCOMMAND] | P3 |
| bench/heartbeat CLI expand | [CLI_BENCH_EXPAND] + [CLI_HEARTBEAT_EXPAND] | P3 |
| BOOT.md drift | [CLI_BOOT_DRIFT] | P3 |
| ACT-R wiring stalled | [ACTR_WIRING] | Non-Code |
| Dead code audit | [DEAD_CODE_AUDIT] | P0 |
| Docs structure | [DOCS_STRUCTURE] | P0 |
| Deprecation warnings | [CLI_DEPRECATION_WARNINGS] | P3 |

### Missing from Queue — New Tasks to Add

| Task | Priority | Rationale |
|------|----------|-----------|
| [HEARTBEAT_INIT_EXPORT_FIX] Fix `clarvis/heartbeat/__init__.py` — add `HookRegistry` to exports | P0 | Import bug found during audit |
| [BOOT_MD_FIX] Fix BOOT.md deprecated import (`clarvis_memory` → `clarvis.brain`) | P0 | Gateway startup uses deprecated import |
| [SELF_MD_UPDATE] Update SELF.md: PM2→systemd, fix stale brain stats | P1 | Wrong restart procedures |
| [SCALABILITY_GATE] Create `scripts/gate_check.sh` — compileall + import_health + smoke + pytest | P1 | No regression prevention exists |
| [UNWIRED_AZR] Wire `absolute_zero.py` into cron (weekly self-play session) | P2 | Built but never exercised |
| [UNWIRED_META_LEARNING] Wire `meta_learning.py` into postflight or weekly cron | P2 | Learning strategy analysis never runs |
| [UNWIRED_GRAPHRAG] Wire `graphrag_communities.py` into brain.recall() or periodic cron | P2 | Community detection would improve retrieval |
| [CLI_COST_SUBCOMMAND] Add `clarvis cost daily/budget` subcommands | P2 | Cost tracking not in CLI |

---

## 7. Scalability Assessment

### Is this "perfect scalable structure"?

**No, but it's the right foundation.** Here's what's missing:

#### What Works

1. **Package layout is correct** — `clarvis/` has proper `__init__.py` hierarchy, Typer CLI, lazy imports.
2. **Brain is canonical** — `clarvis/brain/` is the single source of truth. All scripts delegate.
3. **Memory subsystems are canonical** — episodic, procedural, Hebbian, consolidation all live in `clarvis/memory/`.
4. **Cognition is canonical** — attention, confidence, thought protocol in `clarvis/cognition/`.
5. **Tests are comprehensive** — 610 tests, all passing, covering the spine modules.
6. **Hook architecture is clean** — priority-ordered, fault-isolated, phase-based.

#### What's Missing for True Scalability

| Gap | Impact | Effort |
|-----|--------|--------|
| **82% of logic still in scripts/** | Can't import, test, or compose these modules cleanly | Large (3-6 months) |
| **No `pip install -e .`** | Can't use `clarvis` command outside workspace | Small (1 task) |
| **No CI/CD gates** | Regressions possible on every change | Medium (1 week) |
| **3 empty spine packages** (context/, metrics/, orch/) | Next migration targets | Medium (2-4 weeks each) |
| **Cron still calls scripts/ directly** | Spine bypass — cron doesn't use `python3 -m clarvis` | Medium (gradual migration) |
| **No type hints / mypy** | Refactoring confidence limited | Large (ongoing) |

#### Migration Priority Order

```
Phase 1 (NOW):  Fix bugs found in audit (heartbeat export, BOOT.md)
Phase 2 (NEXT): clarvis/metrics/ ← phi_metric, performance_benchmark, self_model
Phase 3:        clarvis/context/ ← context_compressor, cognitive_workspace
Phase 4:        clarvis/orch/    ← task_router, project_agent, agent_orchestrator
Phase 5:        Cron migration   ← cron scripts call `python3 -m clarvis` instead of scripts/
Phase 6:        scripts/ becomes thin wrappers only (like brain.py is today)
```

---

## 8. Questions for Inverse

1. **Package absorption**: Should `clarvis-db`, `clarvis-cost`, `clarvis-reasoning` (in `packages/`) be absorbed into the main `clarvis` package as submodules? This would eliminate 3 separate `pyproject.toml` files and unify the import surface. Or do you want them to remain standalone for potential external use?

2. **Cron migration timeline**: The cron pipeline calls `python3 scripts/X.py` everywhere. Migrating to `python3 -m clarvis cron run X` requires a 7-day soak per job. Do you want to start this now (starting with low-risk jobs like `cron_reflection.sh`), or wait until more spine modules exist?

3. **scripts/ end state**: When migration is complete, should `scripts/` contain ONLY shell scripts and thin Python wrappers (like today's `brain.py`)? Or should some scripts remain as standalone entrypoints (e.g., `heartbeat_preflight.py` which is 35KB of orchestration logic)?

4. **CI gates**: Should we implement the scalability gate suite (compileall + import_health + smoke + pytest) as a pre-commit hook, a cron check, or a GitHub Actions workflow? Pre-commit is fastest feedback but adds latency to every commit.

5. **Unwired features**: The 5 unwired capabilities (AZR, meta-learning, GraphRAG communities, failure amplifier, conversation learner) represent ~150KB of code that's never automatically exercised. Should we prioritize wiring them into the heartbeat/cron pipeline, or are some of these experimental R&D that should stay CLI-only for now?

---

## Appendix A: File Counts

| Location | Python Files | Shell Scripts | LOC (Python) |
|----------|-------------|---------------|-------------|
| `clarvis/` | 20 | 0 | 10,139 |
| `scripts/` (active) | 103 | 18 | 46,808 |
| `scripts/deprecated/` | 28 | 7 | 5,762 |
| `tests/` | 6 | 0 | ~3,000 |
| `scripts/tests/` | 2 | 0 | ~500 |
| `packages/` | ~15 | 0 | ~3,000 |
| **Total** | **~174** | **25** | **~69,209** |

## Appendix B: Import Health (All Spine Modules)

```
[PASS] clarvis.brain
[PASS] clarvis.cli_bench
[PASS] clarvis.cli_brain
[PASS] clarvis.cli_heartbeat
[PASS] clarvis.cli_queue
[PASS] clarvis.cognition.attention
[PASS] clarvis.cognition.confidence
[PASS] clarvis.cognition.thought_protocol
[PASS] clarvis.context              (empty)
[BUG ] clarvis.heartbeat            (HookRegistry not exported)
[PASS] clarvis.memory.episodic_memory
[PASS] clarvis.memory.hebbian_memory
[PASS] clarvis.memory.memory_consolidation
[PASS] clarvis.memory.procedural_memory
[PASS] clarvis.memory.working_memory
[PASS] clarvis.metrics              (empty)
[PASS] clarvis.orch                 (empty)
```

## Appendix C: Test Results

```
$ python3 -m pytest tests/ -q --tb=no
610 passed in 141.79s
```
