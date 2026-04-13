# Clarvis Architecture

_Updated 2026-04-13._

---

## Overview

Clarvis is a dual-layer cognitive agent: a **conscious layer** (MiniMax M2.5 via OpenClaw gateway) for direct chat, and a **subconscious layer** (Claude Code Opus via system crontab) for autonomous evolution.

```
User ←→ Telegram/Discord
           ↕
    OpenClaw Gateway (port 18789)
    ├── Conscious layer: MiniMax M2.5 (direct chat)
    └── Spawns Claude Code for heavy tasks
           ↕
    System Crontab (20+ entries)
    └── Subconscious layer: Claude Code Opus (autonomous evolution)
           ↕
    ClarvisDB (ChromaDB + ONNX MiniLM, fully local)
```

---

## Package Layout

### `clarvis/` — Spine Package (canonical)

The spine is the single source of truth for all core logic. All `scripts/` wrappers delegate here.

```
clarvis/                          # 125 .py files, 14 subpackages
├── __init__.py, __main__.py      # Package root + entry point
├── cli.py                        # Unified CLI (lazy subcommand loading)
├── cli_brain.py, cli_bench.py, cli_cron.py, cli_heartbeat.py,
│   cli_queue.py, cli_wiki.py, cli_cost.py, cli_maintenance.py  # CLI modules
├── _script_loader.py             # importlib-based script loader (no sys.path hacks)
│
├── brain/          (19 files)    # Layer 0: ChromaDB + graph (mixin composition)
├── memory/         (9 files)     # Layer 1: Episodic, procedural, working, Hebbian, consolidation
├── cognition/      (13 files)    # Layer 2: Attention, confidence, reasoning, obligations, SOAR
├── context/        (10 files)    # Layer 2: Compression, assembly, prompt building/optimization
├── metrics/        (18 files)    # Layer 2: PI benchmark, CLR, ablation, self-model
├── heartbeat/      (10 files)    # Layer 3: Gate, hooks, runner, adapters
├── orch/           (11 files)    # Layer 3: Cost tracking, queue engine v2, task routing
├── queue/          (3 files)     # Queue state machine
├── wiki/           (2 files)     # Canonical page model, retrieval
├── runtime/        (2 files)     # Execution monitor
├── learning/       (2 files)     # Meta-learning from episodes
├── adapters/       (3 files)     # External integrations
└── compat/         (2 files)     # Backwards compatibility shims
```

### `scripts/` — Operational Entry Points (~104 .py files, 10 subdirectories)

All scripts import from `clarvis.*` for library code. Cross-script imports use `clarvis._script_loader.load()`.

```
scripts/
├── agents/       (4 files)     # project_agent, agent_orchestrator, pr_factory, agent_lifecycle
├── brain_mem/    (10 files)    # brain.py (CLI), brain_hygiene, graph_compaction, retrieval tools
├── cognition/    (11 files)    # absolute_zero, dream_engine, causal_model, reflection, etc.
├── cron/         (1 file)      # cron_doctor.py (25 .sh launchers live alongside)
├── evolution/    (13 files)    # evolution_loop, research_to_queue, task_selector, etc.
├── hooks/        (12 files)    # session_hook, temporal_self, goal_*, canonical_state, etc.
├── infra/        (9 files)     # backup, health, install, cost_checkpoint, graph_cutover
├── metrics/      (14 files)    # dashboard, benchmarks, brain_eval, self_report, etc.
├── pipeline/     (5 files)     # heartbeat_preflight, postflight, evolution_preflight
├── tools/        (11 files)    # context_compressor, tool_maker, ast_surgery, browser_agent
├── wiki/         (13 files)    # wiki_ingest, query, compile, lint, sync, eval, hooks
└── _paths.py                   # Legacy path utility (used only by test infrastructure)
```

- **Cron orchestrators**: `cron_autonomous.sh`, `cron_morning.sh`, etc. — spawn Claude Code via `spawn_claude.sh`.
- **Heartbeat pipeline**: `heartbeat_preflight.py` → Claude Code → `heartbeat_postflight.py`.

### `tests/` — Test Suite

```
tests/
├── test_cli.py                  # CLI command smoke tests
├── test_clarvis_brain.py        # Brain store/search/graph/hooks
├── test_clarvis_cognition.py    # Attention, confidence, thought protocol
├── test_clarvis_heartbeat.py    # Gate, hooks, adapters
├── test_clarvis_memory.py       # Episodic, procedural, working memory
├── test_critical_paths.py       # End-to-end user-facing workflows
├── test_hook_order.py           # Hook registration + execution order
├── test_pipeline_integration.py # Router, edge decay, graphrag, pipeline flow
└── test_spine_phase4.py         # Phase 4 migration validation
```

---

## Layer Dependency Rules

```
Layer 0: clarvis.brain       → external only (chromadb, onnxruntime)
Layer 1: clarvis.memory      → brain
Layer 2: clarvis.cognition   → brain, memory
Layer 2: clarvis.context     → brain, memory, cognition
Layer 2: clarvis.metrics     → brain, memory
Layer 3: clarvis.heartbeat   → all lower layers
Layer 3: clarvis.orch        → all lower layers

FORBIDDEN:
  brain  → memory, cognition, context, heartbeat, orch
  memory → cognition, context, heartbeat, orch
  Lower layers never import upper layers.
```

**Dependency inversion**: Brain provides a hook registry (`register_recall_scorer`, `register_recall_booster`, `register_recall_observer`, `register_optimize_hook`). External modules (ACT-R, attention, Hebbian, GraphRAG) register hooks instead of being imported by brain.

---

## Heartbeat Pipeline

```
heartbeat_gate.py          Zero-LLM pre-check (file fingerprint → WAKE/SKIP)
        ↓
heartbeat_preflight.py     Attention scoring, task selection, context assembly
        ↓
Claude Code Opus           Executes selected task (600-1800s timeout)
        ↓
heartbeat_postflight.py    Episode encoding, hook dispatch (7 registered hooks):
                             1. procedural_record (pri 30)
                             2. procedural_injection_track (pri 35)
                             3. periodic_synthesis (pri 50)
                             4. perf_benchmark (pri 60)
                             5. latency_budget (pri 62)
                             6. structural_health (pri 65)
                             7. meta_learning (pri 90, daily)
```

---

## ClarvisDB Brain

ChromaDB + ONNX MiniLM embeddings, fully local. 10 collections:

| Collection | Purpose |
|------------|---------|
| clarvis-identity | Who Clarvis is |
| clarvis-preferences | User/agent preferences |
| clarvis-learnings | Lessons, insights |
| clarvis-infrastructure | System config, hosts, ports |
| clarvis-goals | Active objectives |
| clarvis-context | Current working context |
| clarvis-memories | General memories |
| clarvis-procedures | Step-by-step procedures |
| autonomous-learning | Auto-acquired knowledge |
| clarvis-episodes | Episodic task records |

### Graph Storage

The relationship graph uses SQLite+WAL as its sole runtime backend (`data/clarvisdb/graph.db`). Indexed (B-tree), ACID, hot-backup, O(log n) traversal. JSON graph file retained as archival snapshot only. Key files:
- `clarvis/brain/graph.py` — `GraphMixin` with dual-write logic
- `clarvis/brain/graph_store_sqlite.py` — `GraphStoreSQLite` (schema, CRUD, decay, import/export)
- `scripts/graph_migrate_to_sqlite.py` — migration tool (`--safe` for snapshot+verify)
- `scripts/graph_cutover.py` — cutover/rollback CLI

See `RUNBOOK.md` for migration, cutover, and rollback procedures.

Graph: 85k+ edges (Hebbian + cross-collection + intra-similar). Recall pipeline: vector search → hook scoring (ACT-R) → hook boosting (attention) → observer notification (retrieval quality).

---

## Gates & Validation

**`scripts/gate_check.sh`** — pre-merge gate (8 checks):
1. `compileall` (scripts/ + clarvis/)
2. `import_health --quick`
3. Spine smoke test (`clarvis --help`, `clarvis brain stats`)
4. `pytest` (clarvis-db)
5. `pytest` (test_cli.py)
6. `pytest` (test_pipeline_integration.py)
7. `clarvis queue status`
8. `clarvis cron list`

**pytest**: configured via `pyproject.toml` — `testpaths = ["tests"]`, `norecursedirs` excludes scripts/, data/, etc.

---

## Key Patterns

- **Mixin composition**: `ClarvisBrain(StoreMixin, GraphMixin, SearchMixin)` — avoids circular imports.
- **Lazy CLI loading**: Subcommands register on first access for fast startup.
- **Thin wrapper convention**: `scripts/*.py` import from `clarvis.*`, preserve CLI entrypoints for cron.
- **Global lock**: All Claude Code spawners acquire `/tmp/clarvis_claude_global.lock`.
- **Cron env bootstrap**: All cron scripts source `scripts/cron_env.sh`.
