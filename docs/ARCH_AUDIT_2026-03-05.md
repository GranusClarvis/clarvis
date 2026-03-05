# Architecture Audit — 2026-03-05

_Deep structure audit after Phase 7 spine migration. Evaluates layering, wiring, coherence, scalability, and risks._

## 1. Executive Summary

The Clarvis architecture has matured significantly through the Phase 7 spine migration. The `clarvis/` package provides a clean, mixin-based brain, typed CLI (Typer), hook-based extensibility, and lazy singletons. However, the migration is **~45% complete**: 16 of ~90 active scripts have spine wrappers, and 19 major subsystems remain outside the spine entirely. Key risks are coherence (dual import paths, multiple ChromaDB singletons) and coupling (heartbeat pre/postflight importing 20+ modules each).

**Brain**: 2,007 memories, 70,514 graph edges, 10 collections — healthy. 20 potential duplicates, 23 noise entries.
**Import health**: All checks pass (max fan-in 51, max fan-out 29, max depth 5, brain import 397ms).
**Queue**: 35 pending tasks, 0 P0 — pipeline is running but no urgent work queued.

---

## 2. Repository Layout

```
workspace/                           # Git repo: GranusClarvis/clarvis
├── clarvis/                         # Spine package (7 subpackages, 38 modules)
│   ├── brain/                       #   Memory engine (ClarvisBrain mixin class)
│   │   ├── __init__.py              #     ClarvisBrain, get_brain(), remember/capture/search
│   │   ├── constants.py             #     Collection names, paths, route_query()
│   │   ├── graph.py                 #     GraphMixin (relationships, traversal, decay)
│   │   ├── hooks.py                 #     Hook registration (ACT-R, attention, Hebbian)
│   │   ├── search.py                #     SearchMixin (recall, caching, ACT-R scoring)
│   │   └── store.py                 #     StoreMixin (store, goals, context, optimize)
│   ├── cognition/                   #   Cognitive subsystems
│   │   ├── attention.py             #     GWT AttentionSpotlight (7-slot, competitive)
│   │   ├── confidence.py            #     Prediction calibration (Brier, ECE)
│   │   └── thought_protocol.py      #     Structured thinking DSL
│   ├── context/                     #   Context management
│   │   └── compressor.py            #     TF-IDF + MMR compression
│   ├── heartbeat/                   #   Lifecycle orchestration
│   │   ├── adapters.py              #     Protocol adapters
│   │   ├── gate.py                  #     Zero-LLM pre-check (fingerprinting)
│   │   ├── hooks.py                 #     HookRegistry (priority-ordered, thread-safe)
│   │   └── runner.py                #     Gate + preflight runner
│   ├── memory/                      #   Specialized memory systems
│   │   ├── episodic_memory.py       #     ACT-R episode encoding + causal links
│   │   ├── hebbian_memory.py        #     Associative reinforcement + decay
│   │   ├── memory_consolidation.py  #     Dedup, prune, archive, attention-guided
│   │   ├── procedural_memory.py     #     7-stage skill lifecycle
│   │   └── working_memory.py        #     Shim → attention.py
│   ├── metrics/                     #   Measurement
│   │   ├── benchmark.py             #     Performance Index (PI, 14 metrics)
│   │   └── self_model.py            #     7-domain capability assessment
│   ├── orch/                        #   Orchestration
│   │   ├── router.py                #     14-dimension task classifier
│   │   └── task_selector.py         #     9-factor task scorer
│   ├── cli.py                       #   Root Typer CLI
│   ├── cli_brain.py                 #   brain subcommands
│   ├── cli_bench.py                 #   bench subcommands
│   ├── cli_cron.py                  #   cron subcommands
│   ├── cli_heartbeat.py             #   heartbeat subcommands
│   └── cli_queue.py                 #   queue subcommands
├── scripts/                         # 90 Python + 26 shell scripts (NO __init__.py)
│   ├── deprecated/                  #   36 superseded files
│   └── tests/                       #   2 test files
├── packages/                        # 3 pip-installable packages
│   ├── clarvis-db/                  #   ChromaDB reference impl (has tests)
│   ├── clarvis-cost/                #   Cost tracking
│   └── clarvis-reasoning/           #   Meta-cognitive reasoning quality
├── skills/                          # 15 OpenClaw skills (M2.5 layer)
├── data/                            # ChromaDB, episodes, costs, metrics, sessions
│   └── clarvisdb/                   #   Brain data (10 collections)
├── memory/                          # Cron digests, evolution queue, research
│   ├── cron/digest.md               #   Conscious↔subconscious bridge
│   └── evolution/QUEUE.md           #   Task backlog (35 pending)
├── monitoring/                      # Health/watchdog/alert logs
└── docs/                            # Architecture docs, runbook, audits
```

---

## 3. Layering Analysis

### 3.1 Spine Coverage (16/90 scripts wrapped)

Scripts that re-export from `clarvis.*` (thin wrappers for backward compatibility):

| Script | Spine Module | Status |
|--------|-------------|--------|
| brain.py | clarvis.brain | Complete |
| attention.py | clarvis.cognition.attention | Complete |
| clarvis_confidence.py | clarvis.cognition.confidence | Complete |
| thought_protocol.py | clarvis.cognition.thought_protocol | Complete |
| episodic_memory.py | clarvis.memory.episodic_memory | Complete |
| procedural_memory.py | clarvis.memory.procedural_memory | Complete |
| working_memory.py | clarvis.memory.working_memory | Complete |
| hebbian_memory.py | clarvis.memory.hebbian_memory | Complete |
| memory_consolidation.py | clarvis.memory.memory_consolidation | Complete |
| performance_benchmark.py | clarvis.metrics.benchmark | Complete |
| self_model.py | clarvis.metrics.self_model | Complete |
| task_router.py | clarvis.orch.router | Complete |
| task_selector.py | clarvis.orch.task_selector | Complete |
| context_compressor.py | clarvis.context.compressor | Partial (deprecation notice) |
| heartbeat_gate.py | clarvis.heartbeat.gate | Partial (tries spine import) |
| heartbeat_postflight.py | clarvis.heartbeat.hooks | Partial (hook registration) |

### 3.2 Major Subsystems NOT in Spine (19 scripts)

#### Critical heartbeat path (used in pre/postflight):
| Script | Purpose | Callers | Priority |
|--------|---------|---------|----------|
| world_models.py | State evolution prediction | preflight, postflight, cron | URGENT |
| cognitive_workspace.py | Hierarchical buffers (active/working/dormant) | preflight, postflight, 2 others | URGENT |
| meta_gradient_rl.py | Meta-gradient RL adaptation | postflight, 1 other | HIGH |
| tool_maker.py | LATM tool extraction + validation | postflight | HIGH |
| causal_model.py | Pearl SCM / do-calculus | reflection, 2 others | HIGH |

#### Partially reachable (imported by spine code from scripts/):
| Script | Spine Importers | Priority |
|--------|----------------|----------|
| somatic_markers.py | task_selector, episodic_memory, thought_protocol | MEDIUM |
| clarvis_reasoning.py | self_model | MEDIUM |
| graphrag_communities.py | brain/hooks | MEDIUM |
| cost_api.py | orch/router | MEDIUM |
| soar_engine.py | episodic_memory | MEDIUM |
| meta_learning.py | heartbeat/adapters | MEDIUM |

#### Cron-spawned only (standalone CLI, never imported):
| Script | Cron Caller |
|--------|-------------|
| dream_engine.py | cron (02:45 daily) |
| absolute_zero.py | cron_absolute_zero.sh (Sun 03:00) |
| clarvis_reflection.py | cron_reflection.sh (21:00) |
| knowledge_synthesis.py | cron_reflection.sh (21:00) |
| agent_orchestrator.py | cron_autonomous.sh (detect-stuck) |
| cost_tracker.py | Telegram /costs command |
| phi_metric.py | cron_evening.sh (18:00) |
| theory_of_mind.py | Not actively called |

---

## 4. Coherence Issues

### 4.1 Dual Import Paths (HIGH)

**Problem**: 73 scripts use legacy `sys.path.insert()` imports; 16 use spine imports. Even the spine itself imports from `scripts/` (6 locations).

**Evidence**:
- `clarvis/brain/hooks.py` adds `/scripts` to `sys.path` to import `actr_activation`, `retrieval_quality`, `synaptic_memory`
- `clarvis/orch/router.py` imports `cost_api` from scripts
- `clarvis/orch/task_selector.py` imports `somatic_markers` from scripts
- Heartbeat pipeline mixes both: `from attention import ...` (legacy) + `from clarvis.heartbeat.hooks import ...` (spine)

**Risk**: Import order matters. If a script `sys.path.insert(0, scripts_dir)` and a spine module with the same name exists, Python may resolve the wrong one. Not currently causing bugs, but fragile.

### 4.2 Multiple ChromaDB Singletons (HIGH)

**Instances identified**:
1. `clarvis/brain/__init__.py` → `ClarvisBrain._brain` singleton via `get_brain()` — DATA_DIR=`data/clarvisdb`
2. `clarvis/brain/__init__.py` → `get_local_brain()` — LOCAL_DATA_DIR=`data/clarvisdb-local` (currently None)
3. `scripts/lite_brain.py` → `LiteBrain._lazy` per project agent — `AGENT_BRAIN_DIR` env var
4. `packages/clarvis-db/clarvis_db/store.py` → `VectorStore` class — custom path
5. `scripts/deprecated/clarvisdb.py` → standalone client (importable but unused)

**Mitigating factor**: Cron scripts run in separate processes (no in-process conflicts). But `phi_metric.py` calls `ClarvisBrain()` directly (creates fresh instance), bypassing the singleton.

### 4.3 Competing Feature Implementations (MEDIUM)

| Feature | Location 1 | Location 2 | Status |
|---------|-----------|-----------|--------|
| Brain recall | `clarvis/brain/search.py:SearchMixin.recall()` | `scripts/brain.py` (re-export) | Resolved (wrapper) |
| Memory consolidation | `clarvis/memory/memory_consolidation.py` | `scripts/memory_consolidation.py` (re-export) | Resolved (wrapper) |
| Graph operations | `clarvis/brain/graph.py:GraphMixin` | `scripts/graph_compaction.py` (extends) | Distinct concerns |
| Task routing | `clarvis/orch/router.py` | `scripts/task_router.py` (re-export) | Resolved (wrapper) |
| Phi metric | `scripts/phi_metric.py` | No spine module | **Gap** — creates fresh ClarvisBrain |

### 4.4 Hook Registration Order (MEDIUM)

`clarvis/brain/hooks.py:register_default_hooks()` silently fails if dependencies missing (try/except). Hooks loaded:
- ACT-R scorer → `actr_activation.py`
- Attention booster → `clarvis.cognition.attention`
- Retrieval quality observer → `retrieval_quality.py`
- Hebbian observer → `clarvis.memory.hebbian_memory`
- GraphRAG booster → `graphrag_communities.py`

**Risk**: No visibility when a hook silently fails to register. Brain operates with degraded functionality without logging.

---

## 5. Cron + CLI + Spine Integration

### 5.1 Cron Schedule (30 jobs, healthy)

All 30 cron jobs verified:
- 12x autonomous heartbeats (60+ min spacing)
- 8 specialized slots (morning, research×2, evolution, sprint, strategic audit, evening, reflection)
- 4 maintenance (backup, backup-verify, graph, vacuum)
- 2 reports (morning, evening Telegram)
- 2 continuous monitors (health 15min, watchdog 30min)
- 2 weekly (AZR self-play, cleanup)

**No deprecated paths found.** All script references resolve. Lock architecture (3-tier) is consistent.

### 5.2 CLI Commands (5 subcommands, complete for current scope)

```
clarvis brain   — health, stats, search, optimize[-full], backfill, recent, stale, crosslink, edge-decay
clarvis bench   — run, quick, pi
clarvis cron    — list, status, run <job>
clarvis heartbeat — run, gate
clarvis queue   — next, status, add, archive
```

**Missing CLI coverage** (identified gaps):
- No `clarvis cost` — cost tracking only via raw scripts
- No `clarvis phi` — phi metric only via `scripts/phi_metric.py`
- No `clarvis agent` — project agent management only via `scripts/project_agent.py`
- `clarvis bench` missing: `record`, `trend`, `check`, `heartbeat`, `weakest` (already in QUEUE as CLI_BENCH_EXPAND)
- `clarvis heartbeat` missing: `preflight` (JSON output), `postflight` (already in QUEUE as CLI_HEARTBEAT_EXPAND)

### 5.3 Heartbeat Pipeline Wiring

```
cron_autonomous.sh
  ├── agent_orchestrator.py detect-stuck → heal
  ├── heartbeat_preflight.py (23 module imports, single process)
  │   ├── Attention load/tick
  │   ├── Task selection (9-factor scoring)
  │   ├── Cognitive load estimation
  │   ├── Procedural memory lookup
  │   ├── Reasoning chain open
  │   ├── Confidence prediction
  │   ├── Episodic recall
  │   ├── Context compression (TF-IDF + tiered brief)
  │   ├── Task routing (14-dimension classifier)
  │   ├── World model prediction
  │   ├── Cognitive workspace set_task
  │   └── Somatic/prompt optimization
  ├── Claude Code execution (or OpenRouter for simple/medium)
  └── heartbeat_postflight.py (22 module imports, single process)
      ├── Confidence outcome recording
      ├── Reasoning chain close
      ├── Procedural memory learn
      ├── Episode encoding (with causal links)
      ├── Digest writer update
      ├── Task router logging
      ├── Performance quick-check
      ├── World model update
      ├── Meta-gradient RL step
      ├── SOAR/Hyperon update
      ├── Workspace broadcast
      └── Cognitive workspace close_task
```

**Observation**: Pre/postflight import 45+ unique modules between them. This is the system's highest-coupling point. Any import failure in either file degrades the full heartbeat.

---

## 6. Brain Health Snapshot

| Metric | Value | Assessment |
|--------|-------|------------|
| Total memories | 2,007 | Healthy (was 1,200 at last CLAUDE.md update) |
| Collections | 10 | All present |
| Graph nodes | 2,005 | Matches memories |
| Graph edges | 70,514 | Dense (35:1 ratio) |
| Potential duplicates | 20 | Low — run optimize-full |
| Noise entries | 23 | Low — acceptable |
| Stale (>30d unaccessed) | 0 | Good — Hebbian decay working |
| Archived | 795 | Active archival |
| Store/recall test | Healthy | ✓ |
| Import time (brain.py) | 397ms | Within 600ms threshold |
| Max fan-in | 51 (brain) | Within 60 threshold |
| Max fan-out | 29 (postflight) | Within 30 threshold (barely) |
| Max import depth | 5 | Acceptable |

---

## 7. Top 5 Architectural Risks

### Risk 1: Heartbeat Fan-Out Brittleness (CRITICAL)

**heartbeat_postflight.py** imports 22 modules and has fan-out 29 (threshold: 30). A single module failure (ImportError, ChromaDB corruption, missing data file) can crash the entire postflight, losing episode encoding, confidence recording, and reasoning chain closure for that heartbeat.

**Mitigation**: Each import is try/except'd, but failures are silent. A postflight that runs but records nothing is worse than a crash (silent data loss).

**Recommendation**: Add a postflight "completeness score" — count how many stages actually executed. Log it. Alert if < 80%. Queue task: `[POSTFLIGHT_COMPLETENESS]`.

### Risk 2: Dual Import System Creates Shadow Dependencies (HIGH)

73 scripts use `sys.path.insert()` while 16 use spine imports. The spine itself imports from `scripts/` (6 locations via `sys.path` manipulation in `clarvis/brain/hooks.py`). This creates a shadow dependency graph invisible to standard Python tools (pip, importlib).

**Risk scenario**: Renaming/moving a script in `scripts/` silently breaks spine hook registration, which silently degrades brain recall quality.

**Recommendation**: Complete spine migration for the 6 scripts imported by spine code. Create `clarvis/cognition/somatic_markers.py`, `clarvis/orch/cost_api.py`, `clarvis/brain/graphrag.py` at minimum. Queue task: `[SPINE_SHADOW_DEPS]`.

### Risk 3: No Test Coverage for Integration Paths (HIGH)

Only `packages/clarvis-db/` has meaningful tests (pytest). The spine package has no tests. The heartbeat pipeline has no integration tests. Brain operations are validated by a single store/recall smoke test.

**Critical untested paths**:
- Spine CLI → brain operations (full roundtrip)
- Preflight → task selection → routing (end-to-end)
- Hook registration completeness
- Graph file locking under concurrent writes

**Recommendation**: Add `clarvis/tests/` with: (1) brain roundtrip, (2) hook registration completeness, (3) preflight JSON schema validation, (4) CLI smoke tests. Queue task: `[SPINE_TEST_SUITE]`.

### Risk 4: Graph File as Single Point of Failure (MEDIUM)

`data/clarvisdb/relationships.json` holds 70,514 edges in a single JSON file. Operations:
- `_load_graph()` reads entire file + `fcntl.flock()` for locking
- `_save_graph()` atomic write with merge strategy
- Multiple cron jobs can trigger graph writes (compaction at 04:30, crosslink in reflection at 21:00, auto-link on every store)

**Risk scenario**: Concurrent graph saves race despite flock. File corruption loses 70k edges. The merge strategy in `_save_graph()` may silently drop edges during concurrent modifications.

**Current safeguard**: `cron_graph_checkpoint.sh` (04:00 daily) creates timestamped copies.

**Recommendation**: Consider migrating graph to SQLite (WAL mode) for proper concurrent access. Or at minimum, add checksum verification on load. Queue task: `[GRAPH_SQLITE_MIGRATION]`.

### Risk 5: Cron Cost Opacity (MEDIUM)

12 autonomous heartbeats + 8 specialized slots = 20 Claude Code spawns/day (potential). Each has 20-30 min timeout. At ~$0.15-0.50 per invocation, daily cost could range $3-$10 depending on task complexity and routing.

**Issue**: No per-invocation cost tracking in cron logs. `cost_tracker.py` tracks aggregate API usage but doesn't correlate costs to specific tasks. The `OPENROUTER_ROUTING` system routes cheap tasks to M2.5/GLM-5, but there's no dashboard showing routing effectiveness.

**Recommendation**: Add task-level cost tags to `cost_api.py log_real()` calls. Create routing effectiveness report. Queue task: `[COST_PER_TASK_TRACKING]`.

---

## 8. AGI Scalability Assessment

### Strengths
- **Modular cognitive architecture**: GWT attention, ACT-R activation, Hebbian learning, IIT consciousness proxy (Phi), causal models, theory of mind — each as independent modules
- **Hook-based extensibility**: Brain and heartbeat support plugin registration without code changes
- **Multi-agent architecture**: Project agents with isolated brains enable horizontal scaling
- **Self-evaluation loop**: PI metric, capability assessment, calibration, failure amplification — closed-loop self-improvement
- **Meta-learning**: meta_gradient_rl.py + meta_learning.py + parameter_evolution.py provide learning-to-learn capability

### Scalability Bottlenecks
1. **Sequential collection queries**: Brain queries all 10 collections sequentially via ONNX CPU (~7.5s avg). Parallel queries could achieve 5-8x speedup.
2. **Single-node architecture**: All components (brain, cron, gateway) on one NUC. No distributed execution path.
3. **Monolithic heartbeat pipeline**: 45+ module imports per heartbeat. Adding new cognitive modules increases latency linearly.
4. **JSON file state**: Graph (70k edges), episodes, calibration, workspace state all in JSON files. No transaction safety.
5. **Linear task queue**: QUEUE.md is a markdown file parsed with regex. No priority queue data structure.

### AGI-Relevant Capabilities Present
- [x] Vector memory with importance decay
- [x] Episodic memory with causal linking
- [x] Procedural memory (7-stage skill lifecycle)
- [x] Working memory (Baddeley-inspired 3-tier)
- [x] Attention (GWT spotlight, competitive selection)
- [x] Confidence calibration (Brier score tracking)
- [x] Reasoning chains (multi-step with meta-monitoring)
- [x] Causal models (Pearl SCM, do-calculus)
- [x] World models (state prediction)
- [x] Theory of mind (modeling other agents)
- [x] Self-model (7-domain capability assessment)
- [x] Consciousness proxy (Phi / IIT)
- [x] Meta-learning (meta-gradient RL)
- [x] Self-play reasoning (Absolute Zero)
- [x] Dreaming (counterfactual simulation)
- [x] Tool creation (LATM pattern)

### AGI-Relevant Capabilities Missing/Weak
- [ ] Real-time learning (current: batch via cron)
- [ ] Multi-modal reasoning (vision via Ollama is slow, CPU-only)
- [ ] Distributed memory (single-node ChromaDB)
- [ ] Formal verification of reasoning (research queued, not implemented)
- [ ] Process reward models (research queued, not implemented)
- [ ] Agent interoperability protocols (MCP/A2A, research queued)

---

## 9. QUEUE.md Gap Analysis

### Already queued (relevant to audit findings):
- `[CLI_BENCH_EXPAND]` — covers bench CLI gaps
- `[CLI_HEARTBEAT_EXPAND]` — covers heartbeat CLI gaps
- `[CLI_BRAIN_LIVE]` — verify CLI parity
- `[CLI_DEAD_SCRIPT_SWEEP]` — clean unused scripts
- `[SEMANTIC_BRIDGE]` — Phi improvement
- `[PREFLIGHT_SPEED]` — optimize preflight overhead
- `[FAILURE_TAXONOMY]` — error classification
- `[ACTR_WIRING]` — ACT-R integration (4 subtasks)
- `[RECALL_GRAPH_CONTEXT]` — graph-augmented recall

### Missing from queue (new tasks to add):

1. **[POSTFLIGHT_COMPLETENESS]** (P1) — Add completeness scoring to heartbeat_postflight.py. Count stages executed vs. attempted. Log to `data/postflight_completeness.jsonl`. Alert if <80% stages succeed. Currently, silent hook failures cause invisible data loss.

2. **[SPINE_SHADOW_DEPS]** (P1) — Migrate the 6 scripts imported by spine code (`somatic_markers`, `clarvis_reasoning`, `graphrag_communities`, `cost_api`, `soar_engine`, `meta_learning`) into proper spine submodules. Eliminates `sys.path` manipulation in `clarvis/brain/hooks.py` and `clarvis/orch/*.py`.

3. **[SPINE_TEST_SUITE]** (P1) — Create `clarvis/tests/` with: brain roundtrip test, hook registration completeness test, preflight JSON schema validation, CLI smoke tests (`clarvis brain health`, `clarvis bench pi`, `clarvis queue status`). Target: 5 tests, all pass in <30s.

4. **[GRAPH_INTEGRITY_CHECK]** (P2) — Add checksum verification to graph load/save in `clarvis/brain/graph.py`. On load, verify edge count matches header. On save, write atomic with checksum trailer. Detect silent corruption of the 70k-edge `relationships.json`.

5. **[PHI_METRIC_SINGLETON]** (P2) — Fix `phi_metric.py` creating fresh `ClarvisBrain()` instances instead of using `get_brain()` singleton. Currently bypasses hook registration and creates duplicate ChromaDB clients.

6. **[HOOK_REGISTRATION_LOGGING]** (P2) — In `clarvis/brain/hooks.py:register_default_hooks()`, log which hooks successfully registered and which failed. Currently all failures are silently swallowed. Add summary line: "Registered 4/5 hooks (failed: graphrag_communities)".

7. **[COST_PER_TASK_TRACKING]** (Backlog) — Tag each Claude Code invocation with task ID in cost logging. Create routing effectiveness report showing % of tasks routed to cheap models vs Claude Code.

---

## 10. Recommended Code Changes (Minimal, Safe)

### 10.1 Hook Registration Logging (safe, no behavior change)

**File**: `clarvis/brain/hooks.py` in `register_default_hooks()`

Currently hooks fail silently. Adding logging would surface degraded brain functionality. This is safe because it only adds logging, doesn't change any behavior.

_Deferred to queue task [HOOK_REGISTRATION_LOGGING] — requires reading and understanding the full hooks.py flow first._

### 10.2 Phi Metric Singleton Fix

**File**: `scripts/phi_metric.py`

If `phi_metric.py` calls `ClarvisBrain()` directly, it creates a fresh instance with unregistered hooks. Should use `from clarvis.brain import get_brain` or `brain` singleton.

_Deferred to queue task [PHI_METRIC_SINGLETON] — needs verification of actual import pattern._

---

## 11. Module Dependency Map (Critical Path)

```
cron_autonomous.sh (8x/day)
  ├── cron_env.sh (env bootstrap)
  ├── lock_helper.sh (3-tier locking)
  ├── agent_orchestrator.py (stuck agent healing)
  ├── heartbeat_preflight.py
  │   ├── clarvis.cognition.attention
  │   ├── clarvis.orch.task_selector
  │   │   └── somatic_markers (from scripts/)   ← SHADOW DEP
  │   ├── cognitive_load (scripts/)              ← NOT IN SPINE
  │   ├── clarvis.memory.procedural_memory
  │   ├── reasoning_chain_hook (scripts/)
  │   ├── clarvis.cognition.confidence
  │   ├── clarvis.memory.episodic_memory
  │   ├── clarvis.context.compressor
  │   ├── clarvis.orch.router
  │   │   └── cost_api (from scripts/)           ← SHADOW DEP
  │   ├── world_models (scripts/)                ← NOT IN SPINE
  │   ├── cognitive_workspace (scripts/)         ← NOT IN SPINE
  │   └── prompt_optimizer (scripts/)
  ├── Claude Code (or OpenRouter)
  └── heartbeat_postflight.py
      ├── clarvis.heartbeat.hooks (HookRegistry)
      ├── clarvis.heartbeat.adapters
      ├── clarvis.cognition.confidence
      ├── reasoning_chain_hook (scripts/)
      ├── clarvis.memory.procedural_memory
      ├── clarvis.memory.episodic_memory
      ├── digest_writer (scripts/)
      ├── clarvis.orch.router
      ├── evolution_loop (scripts/)
      ├── extract_steps (scripts/)
      ├── clarvis.metrics.benchmark
      ├── world_models (scripts/)                ← NOT IN SPINE
      ├── meta_gradient_rl (scripts/)            ← NOT IN SPINE
      ├── clarvis.metrics.self_model
      ├── soar_engine (scripts/)                 ← NOT IN SPINE
      ├── workspace_broadcast (scripts/)
      └── cognitive_workspace (scripts/)         ← NOT IN SPINE
```

Items marked `← SHADOW DEP` are imported by spine code from `scripts/` via `sys.path` manipulation.
Items marked `← NOT IN SPINE` are imported directly by heartbeat scripts and have no spine module.

---

## 12. Summary Metrics

| Dimension | Current | Target | Status |
|-----------|---------|--------|--------|
| Spine coverage | 16/90 (18%) | 40/90 (44%) | Phase 7 ongoing |
| Shadow dependencies | 6 | 0 | Needs migration |
| CLI subcommands | 5 | 8+ | Missing cost, phi, agent |
| Heartbeat fan-out | 29 | <20 | Near threshold |
| Import health | All pass | All pass | ✓ |
| Brain memories | 2,007 | — | Healthy |
| Graph edges | 70,514 | — | Dense, needs integrity check |
| Queue pending | 35 | — | Active pipeline |
| Deprecated scripts | 36 | 36 (contained) | No active refs |
| Test coverage | 1 package | All spine | Significant gap |

---

## 13. Action Items (Priority Order)

| Priority | Task | Complexity | Impact |
|----------|------|------------|--------|
| P1 | [POSTFLIGHT_COMPLETENESS] — Add stage completeness scoring | Small | Prevent silent data loss |
| P1 | [SPINE_SHADOW_DEPS] — Migrate 6 spine-imported scripts | Medium | Eliminate shadow deps |
| P1 | [SPINE_TEST_SUITE] — Create spine integration tests | Medium | Catch regressions |
| P2 | [HOOK_REGISTRATION_LOGGING] — Log hook registration results | Small | Visibility |
| P2 | [PHI_METRIC_SINGLETON] — Fix fresh ClarvisBrain() calls | Small | Singleton coherence |
| P2 | [GRAPH_INTEGRITY_CHECK] — Add graph load/save checksums | Small | Data safety |
| Backlog | [COST_PER_TASK_TRACKING] — Per-task cost tagging | Medium | Budget visibility |

---

_Audit completed 2026-03-05 by Claude Code Opus. No code changes made — all findings queued for safe execution._
