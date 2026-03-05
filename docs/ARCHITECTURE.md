# Clarvis Architecture

_Updated 2026-03-04. Reflects post-Phase 7 spine reality._

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
clarvis/
├── __init__.py                  # Package root, version
├── __main__.py                  # python3 -m clarvis
├── cli.py                       # Unified CLI (lazy subcommand loading)
├── cli_brain.py                 # clarvis brain health|stats|optimize-full|backfill
├── cli_bench.py                 # clarvis bench run|profile|compare
├── cli_cron.py                  # clarvis cron autonomous|morning|evolution|...
├── cli_heartbeat.py             # clarvis heartbeat gate|preflight|full
├── cli_queue.py                 # clarvis queue next|list|mark-complete
│
├── brain/                       # Layer 0: Core data (ChromaDB + graph)
│   ├── __init__.py              # ClarvisBrain (mixin composition), singletons
│   ├── constants.py             # Paths, collection names, query routing
│   ├── graph.py                 # GraphMixin: relationships, traversal, edge decay
│   ├── search.py                # SearchMixin: recall, embedding cache, parallel query
│   ├── store.py                 # StoreMixin: storage, stats, reconsolidation
│   └── hooks.py                 # Hook registration (recall scorers/boosters/observers)
│
├── memory/                      # Layer 1: Memory systems
│   ├── episodic_memory.py       # ACT-R episode encoding
│   ├── procedural_memory.py     # Skill chains
│   ├── working_memory.py        # Task-focused buffer with decay
│   ├── hebbian_memory.py        # Co-occurrence learning
│   └── memory_consolidation.py  # REM consolidation, spaced repetition
│
├── cognition/                   # Layer 2: Cognitive processes
│   ├── attention.py             # GWT spotlight, salience, codelets
│   ├── confidence.py            # Prediction tracking, Bayesian calibration
│   └── thought_protocol.py      # ThoughtScript DSL, signal vectors
│
├── context/                     # Layer 2: Context management
│   └── compressor.py            # TF-IDF, MMR reranking, tiered compression
│
├── metrics/                     # Layer 2: Observability
│   ├── benchmark.py             # Performance Index (PI), 8 dimensions
│   └── self_model.py            # 7 capability domains, self-assessment
│
├── heartbeat/                   # Layer 3: Lifecycle orchestration
│   ├── gate.py                  # Zero-LLM pre-check
│   ├── hooks.py                 # HookRegistry + HookPhase
│   ├── runner.py                # Gate execution wrapper
│   └── adapters.py              # Postflight hook adapters (7 hooks)
│
└── orch/                        # Layer 3: Task routing + orchestration
    ├── router.py                # Task classification + OpenRouter model routing
    └── task_selector.py         # Attention-based queue scoring
```

### `scripts/` — CLI Wrappers + Cron Orchestrators

Scripts are **thin wrappers** that delegate to `clarvis.*` spine modules, plus Bash cron orchestrators.

- **Thin wrappers**: `brain.py`, `task_selector.py`, `task_router.py`, etc. — import from spine, keep CLI `main()`.
- **Cron orchestrators**: `cron_autonomous.sh`, `cron_morning.sh`, etc. — spawn Claude Code via `spawn_claude.sh`.
- **Heartbeat pipeline**: `heartbeat_gate.py` → `heartbeat_preflight.py` → Claude Code → `heartbeat_postflight.py`.
- **Deprecated**: `scripts/deprecated/` — old modules, not imported, not tested.

### `packages/` — Standalone Python Packages

- `clarvis-db` — ChromaDB vector memory with Hebbian learning (has tests)
- `clarvis-cost` — Cost tracking (estimated + real API)
- `clarvis-reasoning` — Meta-cognitive reasoning quality assessment

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

The relationship graph supports dual backends, controlled by `CLARVIS_GRAPH_BACKEND` env var:
- **JSON** (default): `data/clarvisdb/relationships.json` — loaded into memory, O(n) traversal
- **SQLite+WAL**: `data/clarvisdb/graph.db` — indexed (B-tree), ACID, hot-backup, O(log n) traversal

When `CLARVIS_GRAPH_BACKEND=sqlite`: reads use SQLite indices, writes dual-write to both JSON and SQLite. Key files:
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

**pytest**: configured via `pyproject.toml` — `testpaths = ["tests", "packages"]`, `norecursedirs` excludes scripts/, data/, etc.

---

## Key Patterns

- **Mixin composition**: `ClarvisBrain(StoreMixin, GraphMixin, SearchMixin)` — avoids circular imports.
- **Lazy CLI loading**: Subcommands register on first access for fast startup.
- **Thin wrapper convention**: `scripts/*.py` import from `clarvis.*`, preserve CLI entrypoints for cron.
- **Global lock**: All Claude Code spawners acquire `/tmp/clarvis_claude_global.lock`.
- **Cron env bootstrap**: All cron scripts source `scripts/cron_env.sh`.
