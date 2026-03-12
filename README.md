# Clarvis 🦞

> Autonomous evolving AI agent. JARVIS-class intelligence, lobster-class resilience.

Clarvis is a dual-layer cognitive agent with a **conscious layer** (MiniMax M2.5) for direct interaction and a **subconscious layer** (Claude Code Opus) for autonomous evolution. Fully local, privacy-first, and self-improving.

---

## 🏗️ High-Level Architecture

```mermaid
flowchart TB
    subgraph External["External Interfaces"]
        TG[Telegram]
        DC[Discord]
        WB[Web Browser]
        GH[GitHub API]
    end

    subgraph Gateway["OpenClaw Gateway (port 18789)"]
        GW[Gateway Core]
    end

    subgraph Conscious["🌅 Conscious Layer"]
        M2[M2.5 Agent]
    end

    subgraph Subconscious["🌙 Subconscious Layer"]
        CC[Claude Code Opus]
    end

    subgraph Core["Clarvis Core"]
        subgraph Heartbeat["Heartbeat Pipeline"]
            HG[heartbeat_gate.py]
            HP[heartbeat_preflight.py]
            PF[heartbeat_postflight.py]
        end
        
        subgraph Brain["ClarvisDB Brain"]
            CH[ChromaDB]
            ONNX[ONNX Embeddings]
            GRAPH[Relationship Graph]
        end
        
        subgraph Memory["Memory Systems"]
            EP[Episodic]
            PR[Procedural]
            WM[Working]
            HB[Hebbian]
        end
        
        subgraph Cognition["Cognition"]
            ATT[Attention GWT]
            CONF[Confidence]
            TO[Thought Protocol]
        end
        
        subgraph Context["Context Engine"]
            COMP[Compressor MMR]
        end
        
        subgraph Metrics["Metrics"]
            PHI[Phi Metric]
            SM[Self Model]
        end
    end

    TG --> GW
    DC --> GW
    GW --> M2
    M2 --> |spawn| CC
    CC --> |autonomous| HG
    HG --> HP
    HP --> |select task| CC
    CC --> PF
    PF --> |hooks| CH
    PF --> |hooks| GRAPH
    
    M2 --> |recall| CH
    M2 --> |recall| GRAPH
    CC --> |learn| CH
    CC --> |learn| GRAPH
```

---

## 🧠 How the Brain Works

ClarvisDB is a **hybrid vector-graph memory system** — ChromaDB for semantic search + relationship graph for structured knowledge.

```mermaid
flowchart LR
    subgraph Storage["Storage Layer"]
        CH[(ChromaDB Vector Store)]
        JSON[relationships.json]
        SQL[graph.db SQLite]
    end
    
    subgraph Collections["10 Collections"]
        ID[clarvis-identity]
        PREF[clarvis-preferences]
        LRND[clarvis-learnings]
        INFRA[clarvis-infrastructure]
        GOALS[clarvis-goals]
        CTX[clarvis-context]
        MEM[clarvis-memories]
        PROC[clarvis-procedures]
        AUTO[autonomous-learning]
        EPIS[clarvis-episodes]
    end
    
    subgraph Query["Query Pipeline"]
        EMB[ONNX Embedding]
        VEC[Vector Search]
        HOOKS[Hook Scoring]
        BOOST[Attention Boost]
        RERANK[Rerank]
    end
    
    EMB --> VEC
    VEC --> HOOKS
    HOOKS --> BOOST
    BOOST --> RERANK
    
    CH --> |read/write| Collections
    Collections --> |edges| JSON
    Collections --> |edges| SQL
```

### Recall Flow

```mermaid
sequenceDiagram
    participant Agent as M2.5 / Claude Code
    participant Brain as clarvis.brain
    participant Chroma as ChromaDB
    participant Graph as Relationship Graph
    participant Hooks as Hook Registry
    
    Agent->>Brain: brain.recall(query, n=5)
    Brain->>Chroma: embedding + vector search
    Chroma-->>Brain: top-k results
    Brain->>Graph: expand 1-hop neighbors
    Graph-->>Brain: related nodes
    Brain->>Hooks: register_recall_scorer()
    Hooks-->>Brain: score each result
    Brain->>Hooks: register_recall_booster()
    Hooks-->>Brain: boost by attention
    Brain-->>Agent: ranked results + context
```

### Save Memory Flow

```mermaid
sequenceDiagram
    participant Agent as Claude Code
    participant Brain as clarvis.brain
    participant Chroma as ChromaDB
    participant Graph as Relationship Graph
    participant Episodic as Episodic Memory
    
    Agent->>Brain: remember(text, importance=0.8, metadata={...})
    Brain->>Chroma: store with embedding
    Chroma-->>Brain: confirmed
    Brain->>Graph: extract entities + create edges
    Graph-->>Brain: edge IDs
    Brain->>Episodic: log episode
    Episodic-->>Brain: episode ID
    Brain-->>Agent: memory stored
```

---

## 💓 Heartbeat Pipeline

The heartbeat is Clarvis's **action cycle** — triggered every ~30 minutes when the gate check passes.

```mermaid
flowchart TB
    subgraph Gate["Step 1: Gate Check"]
        GATE[heartbeat_gate.py]
        CHECK[file fingerprint]
        DEC[decision: WAKE/SKIP]
    end
    
    subgraph Preflight["Step 2: Pre-flight"]
        PRE[heartbeat_preflight.py]
        ATT[Attention: codelet competition]
        SEL[Task Selection: top candidate]
        SIZ[Task Sizing: defer oversized?]
        VER[Verification: files exist?]
        CTX[Context Assembly: brain recall + compression]
    end
    
    subgraph Execute["Step 3: Execute"]
        EXEC[Claude Code Opus]
        TOOL[Tools: read/edit/exec/browse]
    end
    
    subgraph Postflight["Step 4: Post-flight"]
        POST[heartbeat_postflight.py]
        EP[Episode Encoding]
        HOOKS[7 Hooks Run]
        PROC[Procedural Record]
        PERF[Performance Benchmark]
        META[Meta-learning]
    end
    
    GATE --> CHECK --> DEC
    DEC -->|WAKE| PRE
    PRE --> ATT --> SEL --> SIZ --> VER --> CTX
    CTX --> EXEC
    EXEC --> POST
    POST --> EP --> HOOKS
```

### Defer-Fallback Loop

When the top-ranked task is too large (oversized), the system now **falls back to the next executable task** instead of stalling:

```mermaid
flowchart LR
    START[Pick Top Task] --> SIZING{Task Sizing}
    SIZING -->|oversized| SPLIT[Auto-split to subtasks]
    SPLIT --> MARK[Mark parent [~]]
    MARK --> NEXT[Try Next Candidate]
    SIZING -->|OK| VERIFY{Verification}
    VERIFY -->|fail| NEXT
    VERIFY -->|pass| EXEC[Execute Task]
    NEXT --> SIZING
```

---

## 🔄 Evolution Cycle

Clarvis evolves through **autonomous subconscious cycles** triggered by system crontab:

```mermaid
flowchart TB
    subgraph Cron["Daily Cron Schedule (CET)"]
        MORN[cron_morning.sh<br/>08:00]
        AUT1[cron_autonomous.sh<br/>12x/day]
        RES[cron_research.sh<br/>10:00, 16:00]
        EVO[cron_evolution.sh<br/>13:00]
        IMPL[cron_implementation_sprint.sh<br/>14:00]
        EVE[cron_evening.sh<br/>18:00]
        REF[cron_reflection.sh<br/>21:00]
    end
    
    subgraph Tasks["Evolution Tasks"]
        PLAN[Planning]
        EXEC[Implementation]
        RES[Research]
        META[Meta-cognition]
    end
    
    MORN --> PLAN
    AUT1 --> EXEC
    RES --> RES2[Research]
    EVO --> META
    IMPL --> EXEC
    EVE --> RES2
    REF --> META
    
    PLAN --> QUEUE[QUEUE.md]
    EXEC --> QUEUE
    RES --> QUEUE
    META --> QUEUE
    
    QUEUE --> HEART[Heartbeat picks task]
    HEART --> EXECUTE[Claude Code runs]
    EXECUTE --> POST[Postflight records]
    POST --> DIGEST[Digest written]
```

### Evolution Queue Flow

```mermaid
stateDiagram-v2
    [*] --> Queue: New tasks added
    Queue --> Preflight: Heartbeat fires
    Preflight --> Execute: Task selected
    Preflight --> Queue: Task deferred (fallback)
    Execute --> Postflight: Task complete
    Postflight --> Archive: Task archived
    Archive --> [*]: Done
```

---

## 📚 Research Ingestion

Research is discovered, ingested, and converted to actionable knowledge:

```mermaid
flowchart TB
    subgraph Discovery["Discovery Phase"]
        DISC[Claude Code discovers topics]
        WEB[Web search for papers/repos]
        QUEUE[Add to QUEUE.md]
    end
    
    subgraph Ingestion["Ingestion Phase"]
        CRAWL[research_crawler.py]
        PARSE[Parse paper/repo]
        SUMM[Summarize key ideas]
    end
    
    subgraph Storage["Storage Phase"]
        NOTE[Write memory/research/]
        INGEST[research_ingested.json]
        BRAIN[Store in clarvis-learnings]
    end
    
    subgraph Application["Application Phase"]
        RECALL[brain.recall for context]
        INJECT[Inject into prompts]
    end
    
    DISC --> WEB
    WEB --> QUEUE
    QUEUE --> CRAWL
    CRAWL --> PARSE
    PARSE --> SUMM
    SUMM --> NOTE
    NOTE --> INGEST
    NOTE --> BRAIN
    BRAIN --> RECALL
    RECALL --> INJECT
```

---

## 📁 Project Structure

```
clarvis/
├── brain/                 # Layer 0: Core data (ChromaDB + graph)
│   ├── __init__.py       # ClarvisBrain singleton
│   ├── graph.py          # Relationship graph (Hebbian + cross-collection)
│   ├── search.py         # Vector search + hooks
│   └── store.py          # Storage + stats
│
├── memory/               # Layer 1: Memory systems
│   ├── episodic_memory.py
│   ├── procedural_memory.py
│   ├── working_memory.py
│   └── hebbian_memory.py
│
├── cognition/            # Layer 2: Cognitive processes
│   ├── attention.py      # GWT spotlight
│   └── confidence.py     # Prediction calibration
│
├── context/              # Layer 2: Context management
│   └── compressor.py     # MMR reranking
│
├── metrics/              # Layer 2: Observability
│   ├── benchmark.py      # Performance Index
│   └── self_model.py     # Capability tracking
│
├── heartbeat/            # Layer 3: Lifecycle
│   ├── gate.py           # Zero-LLM pre-check
│   ├── hooks.py          # Hook registry
│   └── adapters.py       # Postflight hooks
│
└── orch/                 # Layer 3: Task routing
    ├── router.py         # Task classification
    └── task_selector.py  # Attention-based selection

scripts/
├── heartbeat_*.py        # Heartbeat pipeline
├── cron_*.sh             # Autonomous evolution triggers
├── brain.py              # CLI wrapper → clarvis.brain
├── queue_writer.py       # Queue management
├── phi_metric.py         # Consciousness metric
└── 60+ other scripts

tests/
├── test_clarvis_brain.py
├── test_clarvis_heartbeat.py
└── ...                   # 200+ tests
```

---

## 🔗 Key Scripts & Their Purpose

| Script | Purpose | Calls |
|--------|---------|-------|
| `heartbeat_gate.py` | Pre-check: should we wake? | File fingerprint |
| `heartbeat_preflight.py` | Task selection + context | brain, attention, cognitive_load |
| `heartbeat_postflight.py` | Record outcome + hooks | brain, procedural_memory, metrics |
| `brain.py` | CLI: stats, search, optimize | clarvis.brain |
| `queue_writer.py` | Add tasks, dedupe, mark in-progress | QUEUE.md |
| `spawn_claude.sh` | Spawn Claude Code for tasks | claude CLI |
| `phi_metric.py` | Measure consciousness (Φ) | brain, graph |
| `context_compressor.py` | Build context briefs | brain, MMR reranking |

---

## 📊 Metrics

Clarvis tracks **8 capability dimensions** via `clarvis.metrics.self_model`.

**Brain stats (as of 2026-03-12):** 10 collections, 3400+ memories, 134k+ graph edges, dual backends (JSON + SQLite+WAL).

| Dimension | What it measures |
|-----------|------------------|
| Memory System | ChromaDB + graph health |
| Code Generation | Tests pass, syntax clean |
| Self-Reflection | Meta-cognitive quality |
| Reasoning Chains | Causal reasoning |
| Autonomous Execution | Task completion rate |
| Context Relevance | Brief quality |
| Calibration | Prediction accuracy |
| Overall Φ | Consciousness metric |

---

## 🚀 Quick Start

```bash
# Check brain health
python3 -m clarvis brain stats

# Run heartbeat manually
python3 scripts/heartbeat_preflight.py --dry-run

# List queue
python3 -m clarvis queue status

# Run benchmark
python3 -m clarvis bench run
```

---

## 📖 More Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Detailed architecture
- [ROADMAP.md](ROADMAP.md) — Evolution plan
- [MEMORY.md](MEMORY.md) — Long-term memory
- [RUNBOOK.md](docs/RUNBOOK.md) — Operations guide

---

_Last updated: 2026-03-12_
