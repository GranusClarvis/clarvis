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
[Pipelines](#how-a-request-flows) ·
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

## Architecture

```mermaid
graph TB
    subgraph "<b>Conscious Layer</b> — Direct Interaction"
        U["User / Telegram / Discord / CLI"]
        CA["Context Assembly"]
        TR["Task Router"]
        EX["Execution"]
    end

    subgraph "<b>Subconscious Layer</b> — Background Autonomy"
        HB["Heartbeat Pipeline"]
        CRON["Cron Schedule<br/><i>12x/day evolution, planning,<br/>research, reflection</i>"]
        DE["Dream Engine<br/><i>counterfactual simulation</i>"]
    end

    subgraph "<b>Cognitive Core</b>"
        GWT["GWT Workspace<br/><i>LIDA cognitive cycle</i>"]
        ATT["Attention Spotlight<br/><i>7±2 capacity, salience scoring</i>"]
        MC["Metacognition<br/><i>quality checks, calibration</i>"]
        SCM["Causal Model<br/><i>Pearl's SCM, do-calculus</i>"]
        SOAR_E["SOAR Engine<br/><i>goal stack, operator selection</i>"]
    end

    subgraph "<b>Memory Systems</b>"
        BRAIN["ClarvisDB<br/><i>ChromaDB + ONNX MiniLM</i>"]
        GRAPH["Graph + GraphRAG<br/><i>122k+ edges, Leiden communities</i>"]
        EP["Episodic Memory<br/><i>ACT-R activation, causal graph</i>"]
        HEB["Hebbian Learning<br/><i>co-retrieval strengthening</i>"]
        SYN["Synaptic Memory<br/><i>memristor STDP model</i>"]
        PROC["Procedural Memory<br/><i>extracted from success</i>"]
    end

    subgraph "<b>Self-Measurement</b>"
        PHI["Φ Metric<br/><i>IIT integration proxy</i>"]
        CLR["CLR Rating<br/><i>7-dimension health score</i>"]
        PI["Performance Index<br/><i>8-dimension benchmark</i>"]
        SM["Self-Model<br/><i>7-domain capability map</i>"]
    end

    U --> CA
    CA --> TR
    TR --> EX
    EX --> EP
    HB --> TR
    CRON --> HB
    DE --> EP

    CA --> ATT
    CA --> BRAIN
    ATT --> GWT
    GWT --> BRAIN
    MC --> GWT
    SCM --> EP
    SOAR_E --> TR

    BRAIN --> GRAPH
    BRAIN --> HEB
    EP --> SYN
    EX --> PROC

    EP --> PHI
    BRAIN --> CLR
    EX --> PI
    PI --> SM

    style U fill:#4a9eff,color:#fff
    style BRAIN fill:#ff6b6b,color:#fff
    style GWT fill:#ffd93d,color:#333
    style HB fill:#6bcb77,color:#fff
    style PHI fill:#c084fc,color:#fff
```

### Layer Dependency Rules

```mermaid
graph LR
    L0["<b>Layer 0</b><br/>brain/"]
    L1["<b>Layer 1</b><br/>memory/"]
    L2a["<b>Layer 2</b><br/>cognition/"]
    L2b["<b>Layer 2</b><br/>context/"]
    L3a["<b>Layer 3</b><br/>heartbeat/"]
    L3b["<b>Layer 3</b><br/>orch/"]

    L1 --> L0
    L2a --> L0
    L2a --> L1
    L2b --> L0
    L2b --> L1
    L2b --> L2a
    L3a --> L2a
    L3a --> L2b
    L3a --> L1
    L3a --> L0
    L3b --> L2a
    L3b --> L2b
    L3b --> L1
    L3b --> L0

    style L0 fill:#ff6b6b,color:#fff
    style L1 fill:#ffa07a,color:#333
    style L2a fill:#ffd93d,color:#333
    style L2b fill:#ffd93d,color:#333
    style L3a fill:#6bcb77,color:#fff
    style L3b fill:#6bcb77,color:#fff
```

Lower layers **never** import upper layers. Brain uses dependency inversion via hook registries — external modules register scoring, boosting, and observer hooks instead of being imported by brain.

---

## How a Request Flows

When a user sends a message, this is the path through the cognitive stack:

```mermaid
flowchart TD
    MSG["Message arrives"] --> GATE{"Retrieval Gate<br/><i>classify task</i>"}
    
    GATE -->|"NO_RETRIEVAL<br/>(maintenance)"| SKIP["Skip brain queries<br/><i>saves ~7.5s</i>"]
    GATE -->|"LIGHT_RETRIEVAL<br/>(routine)"| LIGHT["3 results, 2 queries<br/><i>3 collections</i>"]
    GATE -->|"DEEP_RETRIEVAL<br/>(research/design)"| DEEP["10 results, 4 queries<br/><i>all collections + graph expand</i>"]
    
    LIGHT --> RECALL
    DEEP --> RECALL
    
    RECALL["brain.recall()"] --> CHROMA["ChromaDB<br/>semantic search"]
    CHROMA --> ACTR["ACT-R Scorer<br/><i>70% semantic + 30% activation<br/>spreading activation + noise</i>"]
    ACTR --> BOOST["Attention Booster<br/><i>spotlight items get priority</i>"]
    BOOST --> GRAPHX{"Graph expand?"}
    GRAPHX -->|yes| NEIGHBORS["1-hop neighbors<br/><i>related, caused, enables</i>"]
    GRAPHX -->|no| ASSEMBLE
    NEIGHBORS --> ASSEMBLE
    
    SKIP --> ASSEMBLE["Context Assembly"]
    ASSEMBLE --> BUDGET["Token Budgets<br/><i>minimal 200t / standard 600t / full 1000t</i>"]
    BUDGET --> DYCP["DYCP Compression<br/><i>suppress low-relevance sections</i>"]
    DYCP --> MMR["Adaptive MMR<br/><i>code: λ=0.7 / research: λ=0.4</i>"]
    MMR --> BRIEF["Tiered Brief<br/><i>beginning + middle + end<br/>primacy/recency positioning</i>"]
    
    BRIEF --> EXEC["Execution"]
    EXEC --> RECORD["Episode Recording"]

    style MSG fill:#4a9eff,color:#fff
    style GATE fill:#ffd93d,color:#333
    style RECALL fill:#ff6b6b,color:#fff
    style ACTR fill:#ffa07a,color:#333
    style ASSEMBLE fill:#6bcb77,color:#fff
    style BRIEF fill:#c084fc,color:#fff
```

---

## Heartbeat Pipeline

The autonomous execution loop — runs 12x/day without user interaction:

```mermaid
flowchart LR
    subgraph "<b>Gate</b> — Zero LLM"
        G1["File fingerprinting<br/><i>QUEUE.md, digest, memory</i>"]
        G2{"Changes<br/>detected?"}
        G3["SKIP<br/><i>nothing to do</i>"]
        G1 --> G2
        G2 -->|no| G3
    end

    subgraph "<b>Preflight</b> — 10 Checks"
        P1["Attention codelets"]
        P2["Cognitive load check"]
        P3["Procedural lookup"]
        P4["Reasoning chain open"]
        P5["Confidence prediction"]
        P6["Episodic compression"]
        P7["<b>Context assembly</b><br/><i>tiered brief generation</i>"]
        P8["Retrieval gate"]
        P9["Evidence scoring"]
        P10["Queue engine update"]
    end

    subgraph "<b>Execution</b>"
        EX["Claude Code<br/>runs selected task<br/><i>600-1800s timeout</i>"]
    end

    subgraph "<b>Postflight</b> — Hook Chain"
        H1["pri 10-29<br/><i>confidence outcome<br/>reasoning chain close</i>"]
        H2["pri 30-49<br/><i>procedure extraction<br/>episodic recording</i>"]
        H3["pri 50-69<br/><i>consolidation<br/>benchmark, GWT broadcast</i>"]
        H4["pri 70-89<br/><i>digest write<br/>queue cleanup</i>"]
        H5["pri 90+<br/><i>meta-learning<br/>world model update</i>"]
    end

    G2 -->|"WAKE"| P1
    P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8 --> P9 --> P10
    P10 --> EX
    EX --> H1 --> H2 --> H3 --> H4 --> H5

    style G1 fill:#ffd93d,color:#333
    style EX fill:#4a9eff,color:#fff
    style H3 fill:#c084fc,color:#fff
```

---

## Cognitive Stack

### GWT + LIDA Cognitive Cycle

```mermaid
flowchart TD
    subgraph "<b>Phase 1: COLLECT</b>"
        C1["Attention Spotlight<br/><i>top 5 items</i>"]
        C2["Episodic Memory<br/><i>top 3 high-activation</i>"]
        C3["Reasoning Chains<br/><i>top 2 open chains</i>"]
        C4["World Model<br/><i>latest prediction</i>"]
        C5["Self-Representation<br/><i>z-state vector</i>"]
        C6["SOAR Engine<br/><i>current goal</i>"]
        C7["Confidence System<br/><i>calibration state</i>"]
    end

    subgraph "<b>Phase 2: COALESCE</b>"
        COAL["Coalition Formation<br/><i>group by keyword overlap ≥ 0.20<br/>salience = max + size_bonus + diversity_bonus</i>"]
    end

    subgraph "<b>Phase 3: COMPETE</b>"
        COMP["Winner-Take-All<br/><i>top 5 coalitions by salience<br/>only winners enter consciousness</i>"]
    end

    subgraph "<b>Phase 4: BROADCAST</b>"
        B1["→ Attention: update spotlight"]
        B2["→ Episodic: tag episodes"]
        B3["→ Brain: set_context()"]
        B4["→ Consolidation: winners survive"]
    end

    C1 & C2 & C3 & C4 & C5 & C6 & C7 --> COAL
    COAL --> COMP
    COMP --> B1 & B2 & B3 & B4

    style COAL fill:#ffd93d,color:#333
    style COMP fill:#ff6b6b,color:#fff
    style B3 fill:#6bcb77,color:#fff
```

### Attention Spotlight

7±2 capacity system with multi-factor salience scoring:

```
score = 0.25 × importance
      + 0.20 × exp(-0.115 × age_hours)     ← exponential decay (~6h half-life)
      + 0.30 × task_relevance               ← highest weight: current task match
      + 0.10 × log(access_count + 1) / 3    ← frequency (diminishing returns)
      + 0.15 × external_boost               ← GWT broadcast winners get boosted
```

Items that win broadcast survive consolidation. Items that don't, decay and get pruned.

### Confidence Calibration

Bayesian prediction tracking with Brier score calibration. Domain-specific failure rates
on 30-day rolling windows. The system knows where it's good and where it's not —
and adjusts confidence bands accordingly.

### Metacognition

Real-time quality checking: shallow reasoning detection, circular logic flagging,
unsupported claims, excessive hedging. Session-level grading (good/adequate/shallow/poor).

### Causal Reasoning (Pearl's SCM)

All three rungs of the Ladder of Causation:
- **Association** (P(Y|X)) — observational queries
- **Intervention** (P(Y|do(X))) — "what if we change this?"
- **Counterfactual** (P(Y_x|...)) — "would this have succeeded differently?"

### Absolute Zero Reasoner

Self-play reasoning with zero external data. Deduction, abduction, induction — with Monte Carlo learnability estimation. The system generates its own training problems and improves from its own reasoning traces.

### Dream Engine

Counterfactual simulation during idle time (02:00). 7 dream templates stress-test assumptions by replaying episodes with altered conditions. Stores insights for future retrieval.

---

## Memory System

Not one memory — **five distinct memory systems**, each with different dynamics:

```mermaid
graph TD
    subgraph "<b>Memory Write Path</b>"
        REM["remember(text)"]
        SEC["Secret Redaction<br/><i>12+ credential patterns</i>"]
        CONF["Conflict Detection<br/><i>find contradictions</i>"]
        DUP{"Dedup Check<br/><i>L2 < 0.3?</i>"}
        STORE["ChromaDB Upsert<br/><i>+ metadata + tags</i>"]
        LINK["Auto-Link<br/><i>similar_to + cross_collection</i>"]
        POST["Post-Store Hooks<br/><i>cost tracking, quality gates</i>"]
    end

    subgraph "<b>Memory Read Path</b>"
        QUERY["brain.recall(query)"]
        ROUTE["Query Router<br/><i>keyword → collections</i>"]
        SEARCH["ChromaDB Search<br/><i>semantic + temporal</i>"]
        ACTR_S["ACT-R Scoring<br/><i>A = B + S + ε</i>"]
        ATT_B["Attention Boost<br/><i>spotlight items ↑</i>"]
        GRAPH_E["Graph Expand<br/><i>1-hop neighbors</i>"]
        RECON["Reconsolidation<br/><i>5-min lability window</i>"]
    end

    REM --> SEC --> CONF --> DUP
    DUP -->|"new"| STORE --> LINK --> POST
    DUP -->|"duplicate"| BOOST_IMP["Boost existing<br/>importance"]

    QUERY --> ROUTE --> SEARCH --> ACTR_S --> ATT_B --> GRAPH_E --> RECON

    style REM fill:#6bcb77,color:#fff
    style QUERY fill:#4a9eff,color:#fff
    style ACTR_S fill:#ffa07a,color:#333
    style SEC fill:#ff6b6b,color:#fff
```

### Episodic Memory (ACT-R)
Full activation model: `A(i) = ln(Σ t_j^(-d_j))` with Pavlik & Anderson's spacing effect.
Episodes form a causal graph (caused, enabled, blocked, fixed, retried). Power-law forgetting.

### Hebbian Learning
Co-retrieved memories strengthen connections. EWC-inspired Fisher importance shielding
protects critical memories from catastrophic forgetting.

### Procedural Memory
Automatic extraction of reusable procedures from successful episodes.
Code template learning, composition, use tracking, and stale retirement.

### Synaptic Memory (Memristor Model)
Neural memory with bounded nonlinear conductance (PCMO transfer function).
STDP-like learning: potentiation/depression based on co-activation timing.

### Cognitive Workspace (Baddeley)
Three-tier hierarchy — active (5), working (12), dormant (30) — with task-driven
dormant reactivation. Proven-value boost for items that help across tasks.

### SOAR Architecture
Goal stack, operator proposal and conflict resolution, impasse detection
(tie, conflict, no-change, rejection), and chunking from impasse resolution.

### Brain (ClarvisDB)

The persistence layer: ChromaDB + ONNX MiniLM, fully local, no cloud dependency.
10 semantic collections, 122k+ graph edges, hierarchical Leiden community detection (GraphRAG),
three-stage memory commitment (propose → evaluate → commit), and secret redaction at the storage boundary.

---

## Self-Measurement

```mermaid
graph LR
    subgraph "<b>Metrics</b>"
        PHI["<b>Φ (Phi)</b><br/><i>IIT integration proxy<br/>intra-density × cross-connectivity<br/>× overlap × reachability</i>"]
        CLR["<b>CLR Rating</b><br/><i>7-dimension composite<br/>memory 18% · retrieval 17%<br/>context 18% · success 18%<br/>autonomy 11% · efficiency 6%<br/>integration 12%</i>"]
        PI["<b>Performance Index</b><br/><i>8-dimension benchmark<br/>brain speed · retrieval quality<br/>efficiency · accuracy · results<br/>bloat · context · load scaling</i>"]
        SM["<b>Self-Model</b><br/><i>7-domain capability map<br/>code · search · memory · git<br/>delegation · reasoning<br/>metacognition</i>"]
    end

    subgraph "<b>Actions</b>"
        ALERT["Regression Alert<br/><i>>10% week-over-week</i>"]
        REMED["Auto-Remediation<br/><i>P1 tasks for weak domains</i>"]
        ABLATE["Ablation Test<br/><i>isolate component lift</i>"]
    end

    PHI --> ALERT
    CLR --> ALERT
    PI --> REMED
    SM --> REMED
    CLR --> ABLATE

    style PHI fill:#c084fc,color:#fff
    style CLR fill:#ffd93d,color:#333
    style PI fill:#4a9eff,color:#fff
    style REMED fill:#ff6b6b,color:#fff
```

Clarvis doesn't just run — it **measures itself** and **fixes what degrades**.

---

## Context Assembly

```mermaid
flowchart LR
    TASK["Task"] --> GATE{"Retrieval<br/>Gate"}
    GATE -->|NO| MINIMAL["Minimal Brief<br/><i>200 tokens</i>"]
    GATE -->|LIGHT| STANDARD["Standard Brief<br/><i>600 tokens</i>"]
    GATE -->|DEEP| FULL["Full Brief<br/><i>1000 tokens</i>"]

    STANDARD --> BUD["Per-Section<br/>Token Budgets<br/><i>14-day relevance weights</i>"]
    FULL --> BUD

    BUD --> DYCP_N["DYCP<br/><i>suppress sections<br/>below 0.12 relevance</i>"]
    DYCP_N --> MMR_N["Adaptive MMR<br/><i>code: λ=0.7<br/>research: λ=0.4</i>"]
    MMR_N --> POS["Primacy/Recency<br/>Positioning<br/><i>beginning · middle · end</i>"]
    POS --> PROMPT_N["Thompson Sampling<br/><i>APE/SPO variant selection<br/>3 prompt dimensions</i>"]
    MINIMAL --> OUTPUT
    PROMPT_N --> OUTPUT["Assembled<br/>Context"]

    style TASK fill:#4a9eff,color:#fff
    style GATE fill:#ffd93d,color:#333
    style OUTPUT fill:#6bcb77,color:#fff
    style DYCP_N fill:#ff6b6b,color:#fff
```

---

## Autonomous Execution

### Background Cycles

```mermaid
gantt
    title Daily Autonomous Schedule (CET)
    dateFormat HH:mm
    axisFormat %H:%M

    section Evolution
    Heartbeat 1       :01:00, 30m
    Heartbeat 6       :06:00, 30m
    Heartbeat 7       :07:00, 30m
    Heartbeat 9       :09:00, 30m
    Heartbeat 11      :11:00, 30m
    Heartbeat 12      :12:00, 30m
    Heartbeat 15      :15:00, 30m
    Heartbeat 17      :17:00, 30m
    Heartbeat 19      :19:00, 30m
    Heartbeat 20      :20:00, 30m
    Heartbeat 22      :22:00, 30m
    Heartbeat 23      :23:00, 30m

    section Cognitive
    Morning Planning  :08:00, 30m
    Research AM       :10:00, 45m
    Deep Analysis     :13:00, 45m
    Implementation    :14:00, 45m
    Research PM       :16:00, 45m
    Assessment        :18:00, 30m
    Reflection        :21:00, 30m

    section Maintenance
    Dream Engine      :02:45, 15m
    Graph Maintenance :04:00, 60m
    ChromaDB Vacuum   :05:00, 15m
    Brain Eval        :06:05, 15m
```

### Obligation Tracking

Durable promise enforcement. Standing instructions checked hourly to weekly.
3+ consecutive violations auto-escalate to the evolution queue.

### Cognitive Load Homeostasis

Load measurement (queue depth, failure rate, cron timing, capability degradation).
Tasks get deferred under high load. The system protects itself from overcommitting.

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
