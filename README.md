# Clarvis

[![CI](https://github.com/GranusClarvis/clarvis/actions/workflows/ci.yml/badge.svg)](https://github.com/GranusClarvis/clarvis/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**A cognitive architecture for persistent, self-improving AI agents.**

Clarvis is a 128-module Python spine that gives AI agents what they usually lack: memory that persists, attention that routes, reasoning that compounds, and a self-improvement loop that runs while you sleep. It layers onto existing agent harnesses (OpenClaw, Hermes) or runs standalone.

This is not a wrapper. It is a cognitive system grounded in computational neuroscience — Global Workspace Theory, ACT-R activation, Hebbian learning, Pearl's causal calculus, IIT-inspired integration metrics — implemented as production code, not paper demos.

[Install](#install) ·
[Cognitive Stack](#cognitive-stack) ·
[Architecture](#architecture) ·
[Memory System](#memory-system) ·
[Why Clarvis](#why-this-exists) ·
[CLI](#cli) ·
[Docs](#documentation)

---

## The Spine

128 Python files. 14 subpackages. One coherent cognitive architecture.

```
clarvis/
├── brain/       (21 files)  Vector memory, graph, ACT-R scoring, GraphRAG, secret redaction
├── memory/      (10 files)  Episodic (ACT-R), Hebbian, procedural, synaptic, SOAR, consolidation
├── cognition/   (15 files)  GWT broadcast, LIDA cycle, attention, confidence calibration, metacognition
├── context/     (11 files)  Tiered assembly, token budgets, adaptive MMR, DYCP compression
├── metrics/     (19 files)  Phi (IIT), CLR benchmark, self-model, ablation, calibration
├── heartbeat/   (11 files)  Zero-LLM gate, hook system, episode encoding, error classification
├── orch/        (12 files)  Cost tracking, queue engine, task routing, prompt optimization
├── queue/        (4 files)  Evolution queue state machine
├── learning/     (3 files)  Meta-learning from episodes
├── wiki/         (3 files)  Knowledge graph, page model, retrieval
├── runtime/      (3 files)  Mode control, execution monitor
├── adapters/     (5 files)  OpenClaw, Hermes harness integration
└── 15 CLI modules            Unified CLI with lazy subcommand loading
```

---

## Cognitive Stack

### Global Workspace Theory (GWT) + LIDA Cognitive Cycle

Clarvis implements Franklin et al.'s Global Workspace with a full LIDA cycle:
**collect → coalesce → compete → broadcast**. Codelets from 9+ modules compete for
limited broadcast slots via salience-weighted coalition formation. Only winners enter
conscious processing. This isn't a metaphor — it's the actual routing mechanism.

### Attention Spotlight

7±2 capacity attention system with multi-factor salience scoring:
importance (25%), recency (20%), task relevance (30%), access frequency (10%), boost (15%).
Exponential decay with ~6h half-life. Items that win broadcast survive consolidation;
items that don't, decay and get pruned.

### Confidence Calibration

Bayesian prediction tracking with Brier score calibration. Domain-specific failure rates
on 30-day rolling windows. The system knows where it's good and where it's not —
and adjusts confidence bands accordingly.

### Metacognition

Real-time quality checking: shallow reasoning detection, circular logic flagging,
unsupported claims, excessive hedging. Session-level quality grading
(good/adequate/shallow/poor). Based on Flavell (1979) and Dunlosky & Metcalfe (2009).

### Causal Reasoning (Pearl's SCM)

Full structural causal model with all three rungs of the Ladder of Causation:
- **Association** (P(Y|X)) — observational queries
- **Intervention** (P(Y|do(X))) — do-calculus for "what if we change this?"
- **Counterfactual** (P(Y_x|...)) — "would this have succeeded with a different approach?"

d-separation testing, abduction-action-prediction pipeline. Based on Pearl (2009).

### Absolute Zero Reasoner

Self-play reasoning with zero external data. Three modes — deduction, abduction,
induction — with a proposer→solver pipeline and Monte Carlo learnability estimation.
Tasks are self-generated, self-evaluated, and the system improves from its own
reasoning traces. Based on Zhao et al. (2025).

### Dream Engine

Counterfactual simulation during idle time. 7 dream templates (failure flip, cascading
failure, Pearl SCM intervention, etc.) stress-test assumptions by mentally replaying
episodes with altered conditions. Runs at 02:00 and stores insights for future retrieval.

---

## Memory System

Not one memory — five distinct memory systems, each with different dynamics:

### Episodic Memory (ACT-R)
Full ACT-R activation model: `A(i) = ln(Σ t_j^(-d_j))` with Pavlik & Anderson's
spacing effect. Episodes form a causal graph (caused, enabled, blocked, fixed, retried).
Power-law forgetting, not linear TTL.

### Hebbian Learning
"Cells that fire together wire together." Co-retrieved memories strengthen their
connections. Retrieval-as-rehearsal boosts importance. EWC-inspired Fisher importance
shielding protects critical memories from catastrophic forgetting.
Based on Xu et al. (2025, A-Mem) and Kirkpatrick (2017).

### Procedural Memory
Automatic extraction of reusable procedures from successful episodes.
Code template learning, procedure composition, use tracking, and retirement of stale procedures.

### Synaptic Memory (Memristor Model)
SQLite-backed neural memory with bounded nonlinear conductance (PCMO transfer function).
STDP-like learning: potentiation/depression based on co-activation timing.
Weight-dependent saturation prevents runaway strengthening.

### Cognitive Workspace (Baddeley)
Three-tier buffer hierarchy — active (5), working (12), dormant (30) — with task-driven
dormant reactivation. Items that prove useful across tasks get "proven value" boost.
Based on Agarwal et al. (2025, arXiv:2508.13171).

### SOAR Architecture
Goal stack with push/pop priority, operator proposal and conflict resolution,
impasse detection (tie, conflict, no-change, rejection), and chunking —
learning from impasse resolution. Based on Laird (2012).

### Brain (ClarvisDB)

The persistence layer: ChromaDB + ONNX MiniLM embeddings, fully local. No cloud dependency.

- **10 semantic collections** (identity, learnings, goals, procedures, episodes, ...)
- **GraphRAG**: Hierarchical Leiden community detection (4 resolution levels, 122k+ edges), extractive summaries, global search via map-reduce over communities
- **ACT-R activation scoring**: 70% semantic + 30% activation with spreading activation and stochastic noise
- **Three-stage memory commitment**: propose → evaluate (dedup, conflict, goal relevance) → commit
- **Secret redaction**: Pre-store hook scans for 12+ credential patterns before persistence
- **Write-time dedup**: L2 distance < 0.3 blocks near-duplicate storage
- **Conflict detection**: Contradictions resolved via temporal precedence (newer wins)
- **Memory evolution**: Reconsolidation with supersession links and lability windows

---

## Self-Measurement

### Phi (Φ) — Integrated Information

IIT-inspired metric measuring how integrated the brain is as a whole system.
Components: intra-collection density, cross-collection connectivity, semantic overlap,
reachability. Decomposes into per-collection contributions (ΦID framework).

### CLR (Clarvis Rating)

7-dimension composite health score: memory quality (18%), retrieval precision (17%),
prompt/context (18%), task success (18%), autonomy (11%), efficiency (6%),
integration dynamics (12%). Regression detection with >10% week-over-week alerts.

### Performance Index (PI)

8-dimension operational benchmark: brain speed, retrieval quality, efficiency,
accuracy, results quality, bloat, context quality, load scaling.
Auto-pushes P1 remediation tasks when PI drops >0.05.

### Self-Model

7-domain capability assessment (code, search, memory, git, delegation, reasoning, metacognition).
Evidence-based scoring from episodes. Weekly regression detection generates
auto-remediation tasks for weak domains.

### Ablation Testing

Component contribution analysis: what adds value? Controlled experiments isolating
GWT, ACT-R, consolidation, GraphRAG to measure their individual lift.

---

## Context Assembly

Clarvis doesn't stuff everything into the prompt. It routes, ranks, compresses, and budgets:

- **Retrieval Gate**: 3-tier routing (NO / LIGHT / DEEP) — skips brain queries on maintenance tasks
- **Tiered Briefs**: minimal (200t), standard (600t), full (1000t) with per-section budgets
- **Adaptive MMR**: Task-aware lambda tuning (code: λ=0.7 relevance, research: λ=0.4 diversity)
- **DYCP Compression**: Dynamic suppression of low-relevance sections with protected floors
- **Context Relevance Tracking**: 14-day rolling per-section scores drive budget allocation
- **Prompt Optimization**: APE/SPO-inspired Thompson sampling over variant dimensions

---

## Autonomous Execution

### Heartbeat Pipeline

```
Gate (zero-LLM)  →  Preflight (attention + task selection)  →  Execution  →  Postflight (7 hooks)
```

The gate uses file fingerprinting — no LLM call needed to decide "should I wake up?"
Postflight runs 7 registered hooks: procedural recording, synthesis, benchmarks,
latency budgets, structural health, meta-learning.

### Background Cycles

12x/day autonomous evolution, morning planning, 2x research sessions, evening assessment,
weekly reflection, dream engine, graph maintenance, backup verification.
All cron jobs respect mutual exclusion — one Claude Code instance at a time.

### Obligation Tracking

Durable promise enforcement. Standing instructions checked hourly to weekly.
3+ consecutive violations escalate to the evolution queue automatically.

### Cognitive Load Homeostasis

Load measurement (queue depth, failure rate, cron timing, capability degradation).
Tasks get deferred under high load. The system protects itself from overcommitting.

---

## Architecture

Two operating layers:

```
┌─────────────────────────────────────────────┐
│  Conscious Layer (direct interaction)        │
│  Chat → Context Assembly → Task Routing      │
│  → Execution → Episode Recording             │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────┴────────────────────────┐
│  Subconscious Layer (background)             │
│  Cron → Heartbeat → Evolution Queue          │
│  → Planning → Research → Reflection          │
│  → Maintenance → Dream Engine                │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────┴────────────────────────┐
│  ClarvisDB (persistence)                     │
│  ChromaDB + ONNX │ Graph (SQLite) │ Episodes │
│  5 Memory Systems │ GraphRAG │ ACT-R Scoring │
└─────────────────────────────────────────────┘
```

### Layer Rules

```
Layer 0: brain       → external only (chromadb, onnxruntime)
Layer 1: memory      → brain
Layer 2: cognition   → brain, memory
Layer 2: context     → brain, memory, cognition
Layer 3: heartbeat   → all lower layers
Layer 3: orch        → all lower layers
Lower layers never import upper layers.
```

Brain uses dependency inversion via hook registries — external modules register
scoring, boosting, and observer hooks instead of being imported by brain.

---

## Install

```bash
git clone git@github.com:GranusClarvis/clarvis.git
cd clarvis
bash scripts/install.sh
```

The guided installer supports 7 profiles: standalone, OpenClaw, Hermes, fullstack, local, minimal, docker.

```bash
# Standalone (recommended for most users)
bash scripts/install.sh --profile standalone

# Verify
python3 -m clarvis brain health
python3 -m clarvis demo
```

For the full install guide, profiles, and validation criteria, see [docs/INSTALL.md](docs/INSTALL.md).

---

## CLI

```bash
python3 -m clarvis <command>
```

| Command | Purpose |
|---|---|
| `brain health` | Memory system health report |
| `brain search "query"` | Semantic retrieval across all collections |
| `brain seed` | Populate initial memories on fresh install |
| `heartbeat gate` | Zero-LLM wake/skip decision |
| `heartbeat run` | Full autonomous action cycle |
| `bench run` | 8-dimension performance benchmark |
| `metrics phi` | Integrated information (IIT) proxy metric |
| `mode show` | Current operating mode (GE / Architecture / Passive) |
| `queue status` | Evolution queue summary |
| `demo` | End-to-end self-test |

---

## Theoretical Foundations

| Feature | Theory | Reference |
|---------|--------|-----------|
| Workspace broadcast | Global Workspace Theory | Franklin et al. (2014) |
| Cognitive cycle | LIDA Architecture | Franklin & team |
| Episodic activation | ACT-R | Anderson & Lebiere (1998) |
| Spacing effect | Spacing Effect | Pavlik & Anderson (2005) |
| Memory strengthening | Hebbian + A-Mem | Xu et al. (2025) |
| Catastrophic forgetting protection | EWC | Kirkpatrick et al. (2017) |
| Cognitive workspace | Baddeley model | Agarwal et al. (2025) |
| Goal management | SOAR | Laird (2012) |
| Causal reasoning | Structural Causal Models | Pearl (2009) |
| Self-play reasoning | Absolute Zero | Zhao et al. (2025) |
| Community detection | GraphRAG | Microsoft (2024) |
| Consciousness proxy | IIT (Phi) | Tononi |
| Metacognition | Quality monitoring | Flavell (1979) |
| Confidence calibration | Brier score | Brier (1950) |

---

## Documentation

- [Install Guide](docs/INSTALL.md) — profiles, setup, validation criteria, Hermes notes
- [Support Matrix](docs/SUPPORT_MATRIX.md) — what works, what's experimental, known blockers
- [Architecture](docs/ARCHITECTURE.md) — technical architecture and package layout
- [Runbook](docs/RUNBOOK.md) — operational commands and troubleshooting
- [OpenClaw Guide](docs/USER_GUIDE_OPENCLAW.md) — day-to-day ops on OpenClaw
- [Contributing](docs/CONTRIBUTING.md) — code structure, imports, testing

---

## Contributing

```bash
git clone git@github.com:GranusClarvis/clarvis.git
cd clarvis
bash scripts/infra/setup.sh --dev --verify
python3 -m pytest -m "not slow"
```

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).
