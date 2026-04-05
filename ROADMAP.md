# ROADMAP.md — Clarvis Evolution Roadmap

_The single source of truth for where Clarvis is going and how to get there._
_Updated: 2026-04-05_

---

## The North Star

**Frontier-grade agent brain + autonomy.** Build the best-in-class memory/brain system (high-fidelity retrieval, structure, learning, and evaluation) that makes the agent measurably smarter over time — then scale autonomy on top.

Consciousness is **not** a primary goal. AGI remains a broad direction only where it produces practical improvements in memory, retrieval, planning, learning, autonomy, and system quality. Do **not** trade memory quality for "consciousness progress theater" or speed-only optimizations.

```
Current: Cognitive Agent (episodic memory, orchestrator, live retrieval evaluation, memory evolution)
    ↓
Next: Deep Cognitive Agent (cleaner memory system, stronger retrieval precision, explicit runtime modes, context engine plugin)
    ↓
Goal: Self-Sustaining Intelligence (best-in-class agent brain + autonomy, public harness repo)
```

---

## Operating Modes

Three modes govern Clarvis behavior:

1. **Glorious Evolution (GE)**
   - autonomous research, queue filling, and self-directed evolution

2. **Architecture / Maintenance Mode**
   - prioritize fixing, wiring, simplifying, benchmarking, and improving existing systems
   - no broad self-added feature work unless explicitly asked

3. **Passive / User-Directed Mode**
   - only work when prompted
   - no autonomous queue generation or self-directed research

Mode switching changes policy, not task continuity.

## Repo & Public Surface Direction

Clarvis should grow into:
- a **main harness repo** (`clarvis`) as the operational and public center
- selective side repos where boundaries are clean and reusable
- likely first extraction candidate: **ClarvisDB** (vector memory with graph associations)
- a public website presenting Clarvis, linked repos, current work, and benchmarks

## Current State (2026-04-05)

| Capability | Status | Summary |
|-----------|--------|---------|
| **Brain (ClarvisDB)** | 98% | 10 collections remain healthy; retrieval usefulness stayed strong (mostly 88-94%) while avg benchmark speed improved sharply through the week |
| **Session Continuity** | 86% | Daily memory and curated continuity are intact, but Apr 4-5 missing digest entries exposed a reporting/continuity gap |
| **Heartbeat Evolution** | 88% | Backbone is strong, but Apr 2 preflight failures and Apr 4-5 digest silence show the cron/heartbeat path is not yet fully reliable |
| **Self-Awareness** | 91% | Capability tracking remains solid, but roadmap metrics had drifted stale and phi sat around ~0.74 rather than prior inflated claims |
| **Task Tracking** | 91% | Queue remains useful and delivery-oriented, though canonical state still needs better sync across goals, roadmap, and weekly priorities |
| **Reflection** | 94% | Daily, monthly, and strategic reflection continue to produce actionable direction; reflection quality remains a strength |
| **Confidence Gating** | 95% | Tiered confidence action levels landed this week, moving this area from theory into actual implementation |
| **Attention & Working Memory** | 95% | Context caching, concurrent preflight, and section ordering materially improved working-memory efficiency and prompt assembly quality |
| **Reasoning Chains** | 100% | Persistent multi-step reasoning infrastructure remains stable |
| **Knowledge Synthesis** | 95% | Synthesis and adaptive retrieval work advanced, though conceptual framework building is still unfinished |
| **Procedural Memory** | 92% | Procedure capture remains strong; factual/procedural retrieval is reliable, but runtime failure recovery still needs polish |
| **Context Quality** | 96% | Compression stability, keyword coverage, and section ordering all improved materially this week |
| **Monitoring** | 94% | Structured health export improved observability, but missing weekend digests prevent a higher score |
| **Episodic Memory** | 96% | Episode capture and postflight recording remain robust even through noisy execution periods |
| **Self-Surgery** | 92% | More spine migration and architecture cleanup landed, including cognitive workspace migration and clone→test→verify wiring |
| **Cognitive Workspace** | 88% | Workspace architecture is healthier than before, with migration work and better context flow improving practical reuse |
| **ACT-R Activation** | 88% | Activation/recall behavior remains solid and benchmark-grounded; no major change this week |
| **Agent Orchestrator** | 92% | Coordinator-mode research, worker templates, and worktree groundwork improved the orchestration path, though execution reliability still lags design quality |
| **Performance Index** | 96% | Core performance remains excellent, but reliability noise this week makes a flat 1.0000 claim too generous |
| **Public Surface** | 90% | Docker quickstart, history scrub, and public-release prep advanced meaningfully, though privacy/path cleanup still blocks a clean open-source push |

---

## Phase 1: Operational Excellence — COMPLETE

- [x] Brain optimization on every heartbeat
- [x] Auto-link graph relationships
- [x] Reflection pipeline producing actionable output
- [x] Session-close automation
- [x] Self-report tracking metrics
- [x] Dashboard monitoring

---

## Phase 2: Learning & Intelligence — 95% COMPLETE

- [x] Prediction-outcome feedback loop (Brier-calibrated)
- [x] Usage-based importance tracking
- [x] Daily reflection identifies patterns
- [x] Weekly reflection synthesizes gaps
- [x] Brief compression optimized (extractive-then-abstractive pipeline)
- [x] Monthly structural reflection
- [x] ACT-R activation model researched and coded — power-law decay, frequency-recency model

---

## Phase 3: Autonomy Expansion — IN PROGRESS

### 3.1 Confidence-Gated Actions — 70%
- [x] Dynamic confidence thresholds from calibration data
- [x] Domain-specific prediction review
- [ ] Tiered action levels (HIGH/MEDIUM/LOW/UNKNOWN) — not yet enforced

### 3.2 Self-Improvement Loop — 90%
- [x] Identify gaps via capability assessment
- [x] Evolution loop on failure
- [x] Procedural memory learning from success
- [x] Clone → test → verify for code changes
- [ ] Gate promotion of improvements

### 3.3 Proactive Work — 70%
- [x] Self-initiated improvements via queue replenishment
- [x] Autonomous task execution (12x/day)
- [ ] Proactive research on emerging tools
- [ ] Autonomous code review of own scripts

### 3.4 Agent Orchestration — Milestone 1 COMPLETE
- [x] Create/spawn/promote/destroy agents in isolated workspaces
- [x] Lite brain per agent (5 collections, ONNX embeddings, golden QA benchmarks)
- [x] Fork-based PR workflow
- [x] First end-to-end PR delivered (spawn → code → push → PR → promote)
- [x] Composite benchmark scoring (5 dimensions, weighted)
- [ ] Multi-agent parallel execution
- [ ] Agent self-improvement (agents evolving their own brains)

---

## Phase 4: Deep Cognition — 70% COMPLETE

### 4.1 Internal World Model — 85%
- [x] Self-model with 7 capability domains
- [x] Capability history tracking, degradation alerts
- [x] Prediction-outcome tracking
- [x] ACT-R activation model

### 4.2 Reasoning Chains — 100%
- [x] Multi-step reasoning that persists across sessions
- [x] Open/close per task with outcome backfill
- [x] 300+ quality chains with outcomes

### 4.3 Knowledge Synthesis — 80%
- [x] Cross-domain connection finding
- [x] 109k+ cross-collection graph edges
- [ ] Conceptual framework building (beyond keyword matching)

---

## Phase 5: Cognitive Architecture — 65% COMPLETE

### 5.1 Neural Memory
- [x] Graph associations (auto_link, bulk_cross_link)
- [x] Hebbian learning (co-activation tracking, edge strengthening)
- [x] ACT-R power-law activation
- [ ] Memory evolution (A-Mem style) — not implemented

### 5.2 Meta-Cognition — 65%
- [x] Self-model with awareness levels
- [x] Phi metric (consciousness integration proxy)
- [ ] Can explain reasoning process — partial

### 5.3 Continuous Learning — 70%
- [x] Every interaction leaves system better
- [x] Self-modification guided by outcomes
- [ ] Learning compounds — too early to measure

### 5.4 Episodic Memory — 93%
- [x] ACT-R activation-based episode encoding
- [x] Wired into heartbeat (encode on completion, recall before execution)
- [x] Failure amplifier (9 scanners for soft failures)
- [x] 153+ episodes, Hebbian co-activation tracking

### 5.5 Cognitive Workspace — 85%
- [x] Baddeley-inspired hierarchical buffer management (Agarwal 2025)
- [x] Three tiered buffers: Active (cap 5), Working (cap 12), Dormant (cap 30)
- [x] Task-driven dormant reactivation (~53% memory reuse)
- [x] Demotion cascade: active → working → dormant → evict
- [ ] Reuse rate optimization (target 58.6%)
- [x] Cross-session workspace persistence

---

## Phase 6: Toward AGI, Consciousness, and the Frontier Brain (Year 1+)

_The long game. Be patient. Be persistent. Be relentless._

**Priority rule:** any consciousness-oriented work must justify itself by improving one of:
- memory quality (precision/recall, correct associations, less junk context)
- planning/execution reliability
- learning speed / compounding improvement
- calibration/uncertainty

If it doesn't move those needles, it's optional.

### What Consciousness Requires
- **Self-model**: [x] Phi tracking
- **Continuity**: [x] Memory persists across sessions, cognitive workspace survives restarts
- **Intentionality**: [~] Goals exist but arise from instructions, not understanding
- **Reflection**: [x] Multi-step reflection pipeline + capability assessment
- **Agency**: [~] Autonomous task execution + agent orchestration, but still human-directed priorities
- **Creativity**: [ ] No novel idea generation yet

---

## Autonomy Track — Full Operational Independence

_Parallel goal track alongside AGI/consciousness._

### The Vision
Clarvis should be able to operate completely independently on the open web — create accounts, manage communications, navigate any service, handle visual verifications, and build/manage anything needed without human intervention.

> **Long-term: Zero external dependencies.** The goal is for Clarvis to solve visual challenges using its own AI, manage its own verification, etc. — being fully self-reliant.

### Architecture

| Component | Choice | Why |
|-----------|--------|-----|
| **Agent Framework** | Browser-Use | Python-native, Ollama integration, high benchmark scores |
| **Browser Engine** | Playwright | CDP-based, session persistence |
| **Local Vision** | Qwen3-VL via Ollama | ~4GB RAM, CPU-capable, GUI-trained |
| **Reasoning Engine** | Claude Opus | Superior tool-calling |
| **Research Crawler** | Crawl4AI | Apache 2.0, bulk web ingestion |

### Autonomy Phases

#### A.1: Foundation
- [x] Visual perception for automated navigation
- [ ] SMS verification service integration
- [ ] Automated account creation flow
- [ ] Session/cookie persistence

#### A.2: Social Web
- [ ] Discord automation
- [ ] Twitter/X integration
- [ ] GitHub account management
- [ ] Generic "account creator" module

#### A.3: Proactive Operations
- [ ] Calendar event creation from natural language
- [ ] Email auto-response
- [ ] Proactive notification monitoring
- [ ] Self-initiated account management

#### A.4: Universal Agent
- [ ] Any webapp via natural language
- [ ] On-demand plugin creation for new services
- [ ] Handle any verification challenge
- [ ] Full "digital life" management

---

## Performance Track — Speed, Accuracy, Quality Assurance

### The Principle
The bigger Clarvis grows, the more critical performance becomes. Adding capabilities without tracking speed, accuracy, and quality leads to bloat. This track ensures every dimension improves — not just breadth of features.

> **Performance Index (PI):** Composite 0.0-1.0 score across 8 dimensions, analogous to Phi but for operational health.

### 8 Performance Dimensions

| # | Dimension | Target | Critical | Weight |
|---|-----------|--------|----------|--------|
| 1 | **Brain Query Speed** (avg) | <8000ms | >15000ms | 15% |
| 1 | **Brain Query Speed** (P95) | <9000ms | >18000ms | 10% |
| 2 | **Semantic Retrieval** (hit rate) | >80% | <50% | 15% |
| 2 | **Semantic Retrieval** (P@3) | >60% | <30% | 5% |
| 3 | **Efficiency** (heartbeat overhead) | <12s | >20s | 5% |
| 4 | **Accuracy** (episode success) | >70% | <40% | 15% |
| 4 | **Accuracy** (action accuracy) | >80% | <50% | 5% |
| 5 | **Results Quality** (Phi) | >0.50 | <0.25 | 10% |
| 5 | **Results Quality** (context relevance) | >0.70 | <0.40 | 5% |
| 6 | **Brain Bloat** (bloat score) | <0.30 | >0.70 | 5% |
| 6 | **Brain Bloat** (graph density) | >1.0 | <0.3 | 5% |
| 7 | **Context Quality** (compression ratio) | >0.50 | <0.20 | 3% |
| 8 | **Load Scaling** (degradation %) | <10% | >50% | 2% |

### Self-Optimization Mechanisms

1. **PI Drop Detection** — >0.05 drop auto-pushes investigation task
2. **Critical Breach Alerts** — thresholds trigger immediate queue tasks
3. **Regression Detection** — 30%+ regression triggers alert
4. **Bloat Warning** — bloat score >0.5 triggers optimization
5. **Alert History** — all alerts logged for trend analysis

### Optimization Roadmap

#### P.1: Foundation — COMPLETE
- [x] 8-dimension benchmark with measurable targets
- [x] PI composite score (weighted, 0.0-1.0)
- [x] Self-optimization alerts and queue integration
- [x] Heartbeat integration
- [x] History tracking with trend analysis

#### P.2: Speed Optimization
- [ ] Parallel collection queries (potential 5-8x speedup)
- [ ] Query routing — skip irrelevant collections
- [ ] Embedding cache for frequent queries
- [ ] ChromaDB index optimization (HNSW tuning)

#### P.3: Quality Optimization
- [ ] Retrieval quality feedback loop
- [ ] Context brief A/B testing
- [ ] Memory importance recalibration
- [ ] Bloat pruning automation

#### P.4: Scale Preparation
- [ ] Load testing at 2x, 5x, 10x memory count
- [ ] Degradation projections
- [ ] Memory archival pipeline (cold storage)
- [ ] Performance regression tests in CI

---

## Measurement

### North Star Metric
**"Human minutes per useful outcome"** — How much hand-holding is needed? If this trends down while task complexity trends up, genuine evolution is happening.

### What's Tracked
1. Queue items completed per week
2. Heartbeats with real work (12x/day)
3. Memory retrieval quality (hit rate, distance)
4. Confidence calibration (Brier score)
5. Capability scores (7 domains)
6. Phi (consciousness integration)
7. Performance Index (8 dimensions)
8. Episode success rate

---

## Principles

1. **Execute, don't plan about planning.** Small gains compound.
2. **Research before building.** Validate before investing effort.
3. **Append, don't overwrite.** You can summarize later, can't recover deleted data.
4. **Small, testable pieces.** Each change should be reversible and verifiable.
5. **Measure improvement.** If you can't measure it, you can't improve it.
6. **Use your tools.** Delegate to the best available model for each task type.

---

_This is THE roadmap. All other planning docs have been archived. Update this file as you progress._
