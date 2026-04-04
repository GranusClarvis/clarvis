# Clarvis — Launch Packet

> **Note (2026-04-03):** The `packages/` directory (clarvis-db, clarvis-cost, clarvis-reasoning) has been
> consolidated into the `clarvis/` spine module. References to standalone packages below are historical.
> See `clarvis/brain/`, `clarvis/orch/cost_tracker.py`, `clarvis/cognition/metacognition.py`.


## What Is Clarvis?

Clarvis is a **dual-layer cognitive agent system** — an AI that runs autonomously on a dedicated server, continuously learning, reasoning, and evolving.

- **Conscious layer**: MiniMax M2.5 via OpenClaw gateway for direct chat (Telegram/Discord)
- **Subconscious layer**: Claude Code Opus via system crontab for autonomous evolution, research, reflection, and maintenance — 20+ scheduled jobs per day

The subconscious works while the conscious rests. Results surface through a shared memory digest that the conscious layer reads on wake.

## Repository Map

```
clarvis/                     # Spine — core Python package
├── brain/                   # ClarvisDB: ChromaDB + ONNX vector memory
│   ├── retrieval_gate.py    # 3-tier brain query policy (NO/LIGHT/DEEP)
│   └── ...                  # search, remember, capture, health
├── context/                 # Context assembly + compression
│   └── assembly.py          # Attention-optimal tiered brief generation
├── cognition/               # GWT attention, somatic markers, reasoning
├── runtime/                 # Operating mode control-plane (ge/architecture/passive)
├── heartbeat/               # Gate → preflight → execute → postflight pipeline
├── metrics/                 # CLR benchmark, trajectory eval, performance index
├── adapters/                # Host extraction boundary (OpenClaw adapter)
├── compat/                  # Contract checks for adapter compatibility
└── cli.py                   # Unified CLI: `python3 -m clarvis <cmd>`

scripts/                     # 130+ operational scripts
├── cron_autonomous.sh       # Main evolution executor (12x/day)
├── heartbeat_preflight.py   # Attention scoring, task selection, context
├── heartbeat_postflight.py  # Episode encoding, confidence, brain storage
├── brain.py                 # Legacy brain API (still used by cron)
├── episodic_memory.py       # Episode storage + temporal retrieval
├── self_model.py            # 7-domain self-awareness model
├── phi_metric.py            # IIT consciousness proxy (Phi)
└── ...                      # 120+ more (cognitive, maintenance, cron)

packages/                    # Installable Python packages
├── clarvis-db/              # ChromaDB vector memory + Hebbian learning
├── clarvis-cost/            # Cost tracking (estimated + real API)
└── clarvis-reasoning/       # Meta-cognitive reasoning quality

data/                        # Runtime data (ChromaDB, episodes, costs)
memory/                      # Daily logs, cron digests, evolution queue
tests/                       # Smoke, integration, and unit tests
```

## Current Capabilities

| Capability | Status | Details |
|---|---|---|
| **Vector memory** | Production | 10 ChromaDB collections, 3800+ memories, ONNX MiniLM embeddings |
| **Graph memory** | Production | 138k+ edges, SQLite+WAL backend (JSON retained as archival snapshot only) |
| **Episodic memory** | Production | Temporal recall, confidence tracking, dream consolidation |
| **Attention (GWT)** | Production | Global Workspace Theory salience scoring, spotlight |
| **Operating modes** | Production | GE (full autonomy) / Architecture (improve-only) / Passive (user-only) |
| **Heartbeat pipeline** | Production | Gate → preflight → execute → postflight, 12x/day |
| **Self-model** | Production | 7 capability domains, calibrated confidence |
| **Retrieval gate** | Production | 3-tier brain query policy (saves ~270ms avg per skipped query) |
| **Agent orchestration** | Beta | Spawn project agents in isolated workspaces |
| **Browser integration** | Beta | Agent-Browser + Playwright CDP, session persistence |
| **Cost tracking** | Production | Real API usage via OpenRouter, budget alerts |
| **Performance Index** | Production | 8-dimension composite score, weekly benchmarks |

## Usage

### Quick Start
```bash
# Brain operations
python3 -m clarvis brain health        # Health report
python3 -m clarvis brain search "query" # Search memories

# Mode control
python3 -m clarvis mode show           # Current operating mode
python3 -m clarvis mode set passive    # Switch to user-directed mode

# Benchmarks
python3 -m clarvis bench clr           # Run CLR benchmark
python3 -m clarvis bench trajectory    # Run trajectory eval

# Heartbeat
python3 -m clarvis heartbeat gate      # Pre-check (wake/skip)
python3 -m clarvis heartbeat run       # Full preflight + task selection
```

### For Developers
```bash
# Run tests
cd tests && python3 -m pytest -x       # Core tests
python3 -m pytest tests/test_open_source_smoke.py  # Readiness checks
python3 -m pytest tests/test_fork_merge_smoke.py   # Integration checks

# Python API
from clarvis.brain import search, remember, capture
from clarvis.runtime.mode import get_mode, set_mode, mode_policies
from clarvis.context.assembly import generate_tiered_brief
```

## Known Limitations

1. **Hardcoded paths**: Many files reference `$CLARVIS_WORKSPACE` — most use env var fallback (`CLARVIS_WORKSPACE`) but not all
2. **Single-host**: Designed for a dedicated NUC server with systemd — Docker available but not primary deployment
3. **CPU-only embeddings**: ONNX MiniLM on CPU, ~270ms avg per brain query (optimized with parallel collection queries)
4. **Telegram integration**: Bot token and chat ID need env var migration for public release
5. **Personal identity**: Some docs contain operator-specific identity data
6. **CI**: GitHub Actions CI exists (Gitleaks, Ruff, pytest on Python 3.10/3.12, Docker build), but coverage is minimal

## Architecture Principles

- **Improve existing over new**: Fix and wire before building features
- **Honest readiness**: Tests that flag what's NOT ready, not just what passes
- **Mode-governed autonomy**: Operating modes constrain what the system can do autonomously
- **Extraction boundary**: Adapter pattern isolates host-specific logic (currently OpenClaw-only)
- **Brain query policy**: Explicit policy for when to query memory vs stay lean

## Links

- **Repository**: `GranusClarvis/clarvis` (GitHub)
- **Gap Audit**: `docs/OPEN_SOURCE_GAP_AUDIT.md` — what blocks public release
- **Roadmap**: `ROADMAP.md` — 6-phase evolution plan
- **Architecture**: `SELF.md` — system diagram + safe self-modification protocol
