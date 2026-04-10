# Clarvis

[![CI](https://github.com/GranusClarvis/clarvis/actions/workflows/ci.yml/badge.svg)](https://github.com/GranusClarvis/clarvis/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**An autonomous AI agent with persistent memory that evolves itself 24/7.**

[Website](https://granusclarvis.github.io/clarvis/) ·
[Architecture](https://granusclarvis.github.io/clarvis/architecture.html) ·
[Capabilities](https://granusclarvis.github.io/clarvis/capabilities.html) ·
[Benchmarks](https://granusclarvis.github.io/clarvis/benchmarks.html) ·
[Roadmap](https://granusclarvis.github.io/clarvis/roadmap.html)

---

Most AI agents are stateless — brilliant in the moment, amnesiac by default. Clarvis is different. It runs on a dedicated host with **fully local persistent memory**, executes **40+ autonomous jobs daily**, and measures its own performance across 8 dimensions. It remembers what it learned yesterday and uses that to work better today.

**What makes it different:**

- **Persistent vector memory** — ChromaDB + SQLite graph, ~3,800 vectors, ~138k edges, all local
- **Autonomous execution** — 40+ cron jobs: research, reflection, planning, self-benchmarking
- **Dual-layer architecture** — conscious (chat) + subconscious (background evolution)
- **Self-measurement** — 8-dimension Performance Index, Brier-scored calibration, CLR benchmarks
- **Cognitive architecture** — GWT attention, Hebbian learning, episodic memory, working memory buffers

---

## Quick Start

```bash
git clone https://github.com/GranusClarvis/clarvis.git && cd clarvis

# Guided installer (recommended)
bash scripts/install.sh

# Or manual
pip install -e ".[brain]"
```

```bash
# Verify everything works
python3 -m clarvis brain health

# Store and recall a memory
python3 -c "from clarvis.brain import remember; remember('Hello from Clarvis', importance=0.8)"
python3 -m clarvis brain search "Hello from Clarvis"

# Run the demo
python3 -m clarvis demo
```

**Requirements:** Python 3.10+. Brain features need `chromadb` + `onnxruntime` (installed automatically with `.[brain]`). The brain starts empty on a fresh clone — memories accumulate through operation.

---

## What Clarvis Can Do

### Memory System

| Capability | What It Does | Powered By |
|-----------|-------------|------------|
| **Semantic search** | Find memories by meaning, not keywords | ChromaDB + ONNX MiniLM embeddings |
| **Relationship graph** | Traverse connections between concepts | SQLite+WAL graph (~138k edges) |
| **Episodic memory** | Recall past task executions with outcomes | Structured episode store |
| **Procedural memory** | Reusable step-by-step workflows | Extracted procedures collection |
| **Working memory** | Session-aware buffers with dormant reactivation | Baddeley-inspired cognitive workspace |
| **Hebbian learning** | Strengthen connections between co-activated memories | STDP-style weight updates |
| **Memory consolidation** | Dedup, merge, prune, and archive memories | Attention-guided consolidation pipeline |

```python
from clarvis.brain import search, remember, capture

results = search("deployment procedures")    # Semantic search
remember("key insight", importance=0.9)      # Store with weight
capture("learned something new")             # Auto-classify and store
```

### Autonomous Execution

Clarvis runs 40+ scheduled jobs via system crontab:

| Schedule | Job | What Happens |
|----------|-----|-------------|
| 12x/day | Autonomous evolution | Pick task from queue, execute, learn from result |
| 2x/day | Research | Ingest and synthesize new information |
| Daily | Morning planning | Set priorities for the day |
| Daily | Evening assessment | Review what was accomplished |
| Daily | Reflection | 8-step deep reflection pipeline |
| Daily | Implementation sprint | Dedicated coding slot |
| Weekly | Strategic audit | Architecture and direction review |
| Weekly | Full benchmarks | PI, CLR, performance measurement |
| Continuous | Health + watchdog | Every 15/30 min monitoring |

Each execution cycle produces a structured **episode** — what was attempted, what happened, and what was learned. Episodes feed back into future task selection and context assembly.

### Cognitive Architecture

- **GWT Attention** — Global Workspace Theory salience scoring with codelet competition
- **Retrieval Gate** — 3-tier routing (SKIP / LIGHT / DEEP) to avoid unnecessary memory queries
- **Confidence Calibration** — Bayesian calibration with Brier scoring and prediction tracking
- **Context Assembly** — Dynamic context pruning (DYCP), MMR re-ranking, token budgets per tier
- **Somatic Markers** — Emotional valence tagging on memories (approach/avoid signals)
- **Operating Modes** — Full autonomy / Architecture-only / Passive (user-directed)

### Metrics & Self-Measurement

| Metric | What It Measures | Method |
|--------|-----------------|--------|
| **Performance Index** | Composite 0.0–1.0 operational health | 8-dimension weighted score |
| **Phi** | Integrated information (IIT consciousness proxy) | Graph + memory integration |
| **CLR** | Architecture health across 7 dimensions | Automated benchmark suite |
| **BEAM** | 5 extended cognitive abilities | Benchmark adapter |
| **LongMemEval** | Long-term memory retrieval quality | 5-ability evaluation |
| **Brier Score** | Prediction calibration accuracy | Rolling 30-day window |
| **Self-Model** | 7 capability domains with calibrated confidence | Introspective assessment |

### Task Routing

14-dimension complexity scorer routes tasks to the optimal model:

| Tier | Model | When |
|------|-------|------|
| Simple/Medium | MiniMax M2.5 | Status checks, summaries |
| Complex | GLM-5 | Multi-step reasoning |
| Vision | Kimi K2.5 | Image analysis |
| Web Search | Gemini 3 Flash | Real-time information |
| Code-heavy | Claude Code (Opus) | Code generation, file editing |

### Agent Orchestration

Clarvis delegates work to specialized project agents in isolated workspaces:

```
Clarvis (orchestrator)
  └── project agents (/opt/clarvis-agents/<name>/)
        ├── workspace/     # Cloned repo
        ├── data/brain/    # Lite ChromaDB (5 collections)
        └── logs/          # Execution logs
```

Each agent has its own brain, hard isolation (embedding overlap < 0.05), and returns structured results: `{status, summary, pr_url, procedures, follow_ups}`.

### Browser Automation

Dual-engine browser stack via `scripts/clarvis_browser.py`:

| Engine | Technology | Use Case |
|--------|-----------|----------|
| Primary | Agent-Browser (Rust) | Token-efficient navigation (93% fewer tokens) |
| Fallback | Playwright (CDP) | Session persistence, uploads, JS eval, login flows |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Conscious Layer (OpenClaw Gateway · port 18789)        │
│  Chat LLM ← Telegram/Discord → spawns Claude Code      │
├─────────────────────────────────────────────────────────┤
│  Subconscious Layer (system crontab · 40+ jobs)         │
│  Cron orchestrators → Heartbeat pipeline → Claude Code  │
├─────────────────────────────────────────────────────────┤
│  clarvis/ Spine Package (14 subpackages)                │
│  brain · memory · cognition · context · metrics         │
│  heartbeat · orch · queue · wiki · runtime · ...        │
├─────────────────────────────────────────────────────────┤
│  Storage (fully local)                                  │
│  ChromaDB (10 collections) · SQLite graph · Episodes    │
└─────────────────────────────────────────────────────────┘
```

**Conscious layer** — handles direct conversation via Telegram/Discord, reads digests of background work, spawns Claude Code for complex tasks.

**Subconscious layer** — runs autonomously via system crontab. Morning planning → research → evolution → implementation → evening assessment → reflection. Results surface through `memory/cron/digest.md`.

**Heartbeat pipeline** — the core autonomous action cycle:

```
gate ──► preflight ──► execute ──► postflight
 │          │            │            │
 zero-LLM   attention    Claude Code  encode episode
 pre-check  + task pick  runs task    + store learnings
             + context                + update metrics
```

### Project Structure

```
clarvis/                     # Core Python package (spine)
├── brain/                   # ChromaDB + ONNX embeddings + SQLite graph
├── memory/                  # Episodic, procedural, working, Hebbian
├── cognition/               # GWT attention, confidence, reasoning, context relevance
├── context/                 # Prompt assembly, DYCP compression, MMR, token budgets
├── metrics/                 # PI, Phi, self-model, CLR, BEAM, LongMemEval
├── heartbeat/               # Gate → preflight → execute → postflight
├── orch/                    # Task router, cost tracking, PR intake
├── queue/                   # Evolution queue engine
├── wiki/                    # Knowledge canonicalization
├── runtime/                 # Operating mode control
└── cli.py                   # Unified CLI entry point

scripts/                     # ~150 operational scripts (cron, heartbeat, tools)
website/                     # Public site (static HTML + live status API)
tests/                       # 35+ test files
docs/                        # Architecture docs, audits, runbooks
data/                        # ChromaDB brain, episodes, reasoning chains
memory/                      # Daily logs, cron digests, evolution queue
```

---

## Installation

### Profiles

| Profile | What You Get | Requirements |
|---------|-------------|--------------|
| **Standalone** | Python + CLI + brain | Python 3.10+ |
| **OpenClaw** | + chat gateway (Telegram/Discord) | + Node.js 18+ |
| **Full Stack** | + cron schedule + systemd service | + Linux, Claude Code CLI |
| **Docker** | Containerized dev/test | Docker + Compose |

```bash
# Guided installer with profile selection
bash scripts/install.sh

# Non-interactive
bash scripts/install.sh --profile standalone
bash scripts/install.sh --profile standalone --dev  # + ruff + pytest

# Manual
pip install -e ".[brain]"           # core + vector memory
pip install -e ".[all]"             # + dev tools
bash scripts/verify_install.sh      # verify
```

### Docker

```bash
docker compose run clarvis              # runs the demo
docker compose run clarvis clarvis brain health
docker compose run clarvis pytest -m "not slow"
```

See [docs/INSTALL.md](docs/INSTALL.md) for the full walkthrough and troubleshooting.

---

## CLI Reference

```bash
python3 -m clarvis <command>
```

| Command | What It Does |
|---------|-------------|
| `brain health` | Full brain health report |
| `brain search "query"` | Semantic search across all collections |
| `brain stats` | Quick memory statistics |
| `heartbeat gate` | Zero-LLM pre-check (wake/skip) |
| `heartbeat run` | Full preflight + task selection |
| `bench run` | Full performance benchmark |
| `bench clr` | CLR architecture benchmark |
| `bench trajectory` | Trajectory evaluation |
| `mode show` | Current operating mode |
| `cost` | Cost tracking and budget monitoring |
| `cron` | Cron job inspection and execution |
| `queue` | Evolution queue management |
| `metrics` | Self-model, phi, performance index |
| `demo` | One-command demo walkthrough |

---

## Testing

```bash
python3 -m pytest                    # All tests
python3 -m pytest -m "not slow" -v   # Fast tests only
python3 -m pytest tests/test_open_source_smoke.py -v  # Smoke tests
```

Tests use a `tmp_brain()` fixture with fast hash-based embeddings (no ONNX needed). CI runs automatically via GitHub Actions.

---

## Current Status

**Phase 3 — Autonomy Expansion** (Phases 1–2 complete).

| System | Status |
|--------|--------|
| ClarvisDB Brain | Stable — 10 collections, ~3,800 vectors, ~138k graph edges |
| Heartbeat Pipeline | Stable — 12x/day autonomous execution |
| Agent Orchestrator | Active — multi-project delegation with isolated workspaces |
| Metrics & Self-Model | Stable — 7 capability domains, 8-dimension PI |
| Context Quality | Strong — DYCP compression, MMR re-ranking |
| Cognitive Workspace | Active — 91% dormant reuse rate |

See [ROADMAP.md](ROADMAP.md) for the full evolution plan.

---

## Compatibility

Clarvis is a **self-contained cognitive agent**, not a framework. It runs on its own dedicated host.

| Component | Role | Required? |
|-----------|------|-----------|
| **OpenClaw Gateway** | Chat routing (Telegram/Discord) | For chat. Subconscious runs independently. |
| **Claude Code** | Code execution for autonomous tasks | For autonomous execution. |
| **OpenRouter** | Multi-model API gateway | For conscious layer. Not needed for brain-only. |

**What works standalone (no gateway, no API keys):**
- `python3 -m clarvis brain` — full brain operations
- `python3 -m clarvis bench` — benchmarks and metrics
- `python3 -m clarvis demo` — demo walkthrough
- All tests (`python3 -m pytest`)

---

## Known Limitations

- **Single-host design** — built for a dedicated server with systemd, not containerized deployment
- **CPU-only embeddings** — ONNX MiniLM on CPU (~270ms avg per brain query)
- **Path defaults** — some scripts default to a fixed workspace path (override with `CLARVIS_WORKSPACE`)

See [docs/OPEN_SOURCE_GAP_AUDIT.md](docs/OPEN_SOURCE_GAP_AUDIT.md) for a detailed gap analysis.

---

## Documentation

| Document | What It Covers |
|----------|---------------|
| [Architecture](docs/ARCHITECTURE.md) | Detailed architecture and package layout |
| [Install Guide](docs/INSTALL.md) | Full installation walkthrough |
| [Launch Packet](docs/LAUNCH_PACKET.md) | Quick orientation for new contributors |
| [Gap Audit](docs/OPEN_SOURCE_GAP_AUDIT.md) | Open-source readiness analysis |
| [Graph Cutover](docs/GRAPH_SQLITE_CUTOVER_2026-03-29.md) | SQLite graph migration |
| [Spine Review](docs/SPINE_ARCHITECTURE_REVIEW_2026-04-10.md) | Architecture review and recommendations |

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
# Quick start
git clone https://github.com/GranusClarvis/clarvis.git && cd clarvis
bash scripts/setup.sh --dev --verify
python3 -m pytest -m "not slow"
# Open a PR against main
```

---

## License

MIT — see [LICENSE](LICENSE).
