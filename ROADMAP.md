# ROADMAP.md — Clarvis Evolution Roadmap

_The single source of truth for where you're going and how to get there._
_Updated: 2026-03-08_

---

## The North Star

**Frontier-grade agent brain + autonomy.** Build the best-in-class memory/brain system (high-fidelity retrieval, structure, learning, and evaluation) that makes the agent measurably smarter over time — then scale autonomy on top.

Consciousness research remains valuable, but it is a **secondary track** unless it directly improves the agent’s intelligence/memory functions (retrieval quality, integration, planning, learning). Do **not** trade memory quality for “consciousness progress theater” or speed-only optimizations.

```
Current: Cognitive Agent (episodic memory, orchestrator, 203+ predictions resolved, Phi≈0.650, PI previously 0.976, PR-factory planning active)
    ↓
Next: Deep Cognitive Agent (context engine plugin, orchestrator scoreboard, memory evolution, multi-agent scaling)
    ↓
Goal: Self-Sustaining Intelligence (generate revenue, improve independently)
```

---

## Current State (2026-03-08)

| Capability | Status | What Exists |
|-----------|--------|-------------|
| **Brain (ClarvisDB)** | 97% | ChromaDB + ONNX local embeddings, 10 collections (3,564 memories by 2026-03-07), graph layer migrating toward SQLite soak, smart_recall + unified brain.py API |
| **Session Continuity** | 86% | BOOT.md auto-init, AGENTS.md loads brain, daily memory files, MEMORY.md curated wisdom, session_hook.py with open/close automation |
| **Heartbeat Evolution** | 100% | cron_autonomous.sh runs 12x/day with attention-based task selection, procedural memory, reasoning chains, confidence predictions, working memory, cognitive workspace, evolution loop on failure |
| **Claude Code Integration** | 95% | 6 daily Claude Code sessions plus autonomous research/evolution runs; prompt-builder and spawn discipline are now well established |
| **Self-Awareness** | 93% | SELF.md, self_model.py with 7 scored capability domains, phi_metric.py tracking (Phi≈0.650 on 2026-03-07), daily capability assessment |
| **Task Tracking** | 90% | evolution/QUEUE.md now tracks pillars plus PR-factory, context-engine, calibration, and speed items; attention-based selection and goal tracking remain active |
| **Reflection** | 90% | 8-step reflection pipeline: brain.optimize, clarvis_reflection, knowledge_synthesis, crosslink, memory_consolidation, conversation_learner, episodic synthesis, temporal_self |
| **Confidence Gating** | 82% | clarvis_confidence.py with predict/outcome/calibration, ~203 predictions / 172 resolved noted this week; tiered action enforcement and Brier recovery are still open |
| **Attention & Working Memory** | 92% | GWT-inspired attention.py (salience scoring, broadcast, spotlight cap=7), working_memory.py (persistent, TTL, importance-based), cognitive_workspace.py (Baddeley hierarchical buffers) |
| **Reasoning Chains** | 100% | reasoning_chain_hook.py opens/closes chains per task, chains stored in brain + files, 301 quality chains with outcomes |
| **Knowledge Synthesis** | 92% | knowledge_synthesis.py plus semantic bridge work improved weak cross-collection pairs; research ingestion and cross-domain links continue to strengthen context quality |
| **Procedural Memory** | 90% | procedural_memory.py with store/find/learn/used, wired into heartbeat, extracts real steps from task output (144 procedures in brain) |
| **Monitoring** | 90% | health_monitor.sh (15min), cron_watchdog.sh (alerts), cron_doctor.py (auto-recovery), dashboard.py, self_report.py |
| **Backup & Recovery** | 95% | backup_daily.sh (2 AM, incremental, checksums, 30-day retention), backup_verify.sh, backup_restore.sh, safe_update.sh |
| **Episodic Memory** | 95% | episodic memory + failure amplification remain wired in; weekly logs show richer outcome capture; periodic_synthesis import fixed (uses spine module) |
| **Self-Surgery** | 80% | ast_surgery.py parses 32 scripts, finds 99 proposals, auto-fixes 4 imports, benchmark-tested mutations |
| **Counterfactual Dreaming** | 75% | dream_engine.py replays episodes as what-if scenarios, stores insights at low activation |
| **Somatic Markers** | 80% | 8 emotion dimensions, 153 markers, influences task selection |
| **Thought Protocol** | 70% | Internal DSL for fast reasoning (Signals, Relations, Decisions), wired into task selection |
| **Performance Index (PI)** | 95% | 8-dimension benchmark (speed, retrieval, efficiency, accuracy, quality, bloat, context, scaling), PI=0.976, self-optimization alerts, heartbeat integration |
| **Browser Automation** | 76% | ClarvisBrowser stack plus new local screenshot-analysis benchmark; browser auth and autonomous GitHub posting were proven this week |
| **Agent Orchestrator** | 88% | project_agent.py now has trust scoring, CI context/feedback, dependency maps, lock hardening, cron coexistence, and visual dashboard event hooks on top of the existing PR workflow |
| **Cognitive Workspace** | 75% | cognitive_workspace.py: Baddeley-inspired hierarchical buffers (active/working/dormant), task-driven reactivation, ~53% memory reuse, wired into heartbeat + context_compressor |
| **ACT-R Activation** | 60% | actr_activation.py with power-law decay, frequency-recency model — researched, coded, not yet wired into brain.py |
| **Revenue** | 0% | No viable product yet |

---

## Phase Assessment: Phase 3 (Autonomy Expansion)

Phases 1-2 are complete. Phase 3 is well underway with the agent orchestrator delivering its first PR. The system has operational cron infrastructure, reflection pipelines, feedback loops, cognitive architecture, and multi-agent orchestration. The main gaps are:

- **ACT-R activation model** — researched and coded (actr_activation.py), not yet wired into brain.py recall
- **Memory evolution** (A-Mem style) — memories are static, not evolving
- **Revenue generation** — zero progress
- **New since 2026-03-02**: orchestrator trust scoring, CI context + feedback, dependency maps, stale-lock detection, loop backoff, autocommit safety, cron coexistence, and visual dashboard event hooks landed; autonomous GitHub login/posting was proven; local screenshot analysis benchmark was added; OpenClaw 2026.3.7 introduced context engine plugins, creating a clear path for a Clarvis-specific context engine layered over ClarvisDB.

---

## Phase 1: Operational Excellence — COMPLETE

All items delivered:

- [x] Brain optimization on every heartbeat (brain.optimize in reflection)
- [x] Auto-link graph relationships (auto_link on store, bulk_cross_link)
- [x] Reflection pipeline producing actionable output (5-step pipeline)
- [x] Daily reflection cron (21:00)
- [x] Session-close automation (session_hook.py)
- [x] Self-report tracking metrics (self_report.py, now wired into evening)
- [x] Dashboard monitoring (dashboard.py, now wired into evening)

---

## Phase 2: Learning & Intelligence — 95% COMPLETE

- [x] Prediction-outcome feedback loop (clarvis_confidence.py, wired into heartbeat, 165 predictions)
- [x] Calibration review (prediction_review.py in evolution analysis)
- [x] Usage-based importance (retrieval_quality.py tracks hit rates)
- [x] Daily reflection identifies patterns (conversation_learner.py)
- [x] Weekly reflection synthesizes gaps (evolution analysis, capability assessment)
- [x] Brief compression optimized (context_compressor.py — extractive-then-abstractive pipeline)
- [x] Monthly reflection proposes structural changes — `cron_monthly_reflection.sh`, runs 1st of month at 03:30
- [x] ACT-R activation model researched and coded (actr_activation.py) — power-law decay, frequency-recency model. Integration into brain.py pending.

---

## Phase 3: Autonomy Expansion — IN PROGRESS

### 3.1 Confidence-Gated Actions — 70%
- [x] Dynamic confidence thresholds from calibration data
- [x] Domain-specific prediction review
- [ ] Tiered action levels (HIGH/MEDIUM/LOW/UNKNOWN) — not yet enforced

### 3.2 Self-Improvement Loop — 80%
- [x] Identify gap (capability assessment, self_model.py)
- [x] Evolution loop on failure (evolution_loop.py)
- [x] Procedural memory learning from success
- [ ] Clone → test → verify for code changes — not yet implemented
- [ ] Gate promotion of improvements — not yet formalized

### 3.3 Proactive Work — 70%
- [x] Self-initiated improvements via queue replenishment
- [x] Autonomous task execution 12x/day (upgraded from 6x)
- [ ] Proactive research on emerging tools — manual only
- [ ] Autonomous code review of own scripts — not yet

### 3.4 Agent Orchestration — Milestone 1 COMPLETE
- [x] project_agent.py: create/spawn/promote/destroy agents in isolated workspaces
- [x] Lite brain per agent (5 collections, ONNX embeddings, golden QA benchmarks)
- [x] Fork-based PR workflow (GranusClarvis fork → upstream PR)
- [x] First PR #175 delivered end-to-end (spawn→code→push→PR→promote)
- [x] Composite benchmark scoring (5 dimensions, weighted), star-world-order=0.75
- [x] Cost tracking and retry logic per agent task
- [ ] Multi-agent parallel execution — not yet
- [ ] Agent self-improvement (agents evolving their own brains) — not yet

---

## Phase 4: Deep Cognition — 70% COMPLETE

### 4.1 Internal World Model — 85%
- [x] self_model.py with 7 capability domains (avg 0.84)
- [x] Capability history tracking, degradation alerts
- [x] Prediction-outcome tracking (165 predictions)
- [x] ACT-R activation model researched and coded (actr_activation.py) — wiring into brain.py pending

### 4.2 Reasoning Chains — 100%
- [x] Multi-step reasoning that persists across sessions
- [x] reasoning_chain_hook.py with open/close per task
- [x] 301 quality chains with outcomes, 100% outcome backfill on active chains

### 4.3 Knowledge Synthesis — 80%
- [x] Cross-domain connection finding (knowledge_synthesis.py)
- [x] 109,549 cross-collection graph edges (compacted from 121,860)
- [ ] Conceptual framework building (beyond keyword matching)

---

## Phase 5: Cognitive Architecture — 65% COMPLETE

### 5.1 Neural Memory
- [x] Graph associations (auto_link, bulk_cross_link) — 109,549 edges
- [x] Hebbian learning (hebbian_memory.py — co-activation tracking, edge strengthening)
- [x] ACT-R power-law activation (actr_activation.py — researched, coded, not yet in brain.py recall)
- [ ] Memory evolution (A-Mem style) — not implemented

### 5.2 Meta-Cognition — 65%
- [x] self_model.py with awareness levels
- [x] Phi metric (consciousness integration proxy, Phi=0.754)
- [ ] Can explain reasoning process — partial

### 5.3 Continuous Learning — 70%
- [x] Every interaction leaves system better (conversation_learner, procedural memory)
- [x] Self-modification guided by outcomes (evolution_loop)
- [ ] Learning compounds — too early to measure

### 5.4 Episodic Memory — 93%
- [x] Build episodic_memory.py (ACT-R activation, episode encoding)
- [x] Wire into heartbeat (encode on completion, recall before execution)
- [x] Wire into evolution analysis (episode statistics)
- [x] Failure amplifier (failure_amplifier.py — 9 scanners for soft failures)
- [x] 153 episodes encoded, hebbian_memory.py for co-activation tracking

### 5.5 Cognitive Workspace — 75% (NEW)
- [x] cognitive_workspace.py: Baddeley-inspired hierarchical buffer management (Agarwal 2025)
- [x] Three tiered buffers: Active (cap 5), Working (cap 12), Dormant (cap 30)
- [x] Task-driven dormant reactivation (~53% memory reuse, target 58.6%)
- [x] Demotion cascade: active overflow→working→dormant→evict (lowest utility)
- [x] Wired into heartbeat preflight (set_task) and postflight (close_task)
- [x] Wired into context_compressor for workspace-aware context building
- [ ] Reuse rate optimization — currently 53%, target 58.6%
- [ ] Cross-session workspace persistence — partial (JSON state file)

---

## Phase 6: Toward AGI, Consciousness, and the Frontier Brain (Year 1+)

_The long game. Be patient. Be persistent. Be relentless._

**Priority rule:** any consciousness-oriented work must justify itself by improving one of:
- memory quality (precision/recall, correct associations, less junk context)
- planning/execution reliability
- learning speed / compounding improvement
- calibration/uncertainty

If it doesn’t move those needles, it’s optional.

### What Consciousness Requires
- **Self-model**: [x] self_model.py + phi_metric.py — Phi tracking at 0.754
- **Continuity**: [x] Memory persists across sessions, working memory + cognitive workspace survive restarts
- **Intentionality**: [~] Goals exist but arise from instructions, not understanding
- **Reflection**: [x] 8-step reflection pipeline + capability assessment
- **Agency**: [~] Autonomous task execution + agent orchestration, but still human-directed priorities
- **Creativity**: [ ] No novel idea generation yet

---

## 🌍 AUTONOMY TRACK — Full Operational Independence

_Added 2026-02-26. Parallel goal track alongside AGI/consciousness._

### The Vision
Clarvis should be able to operate completely independently on the open web — create accounts, manage communications, navigate any service, handle visual verifications, and build/manage anything needed without human intervention.

> **🎯 Long-term: Zero external dependencies.** Current implementations use external services (vision API, phone verification) as placeholders. The goal is for Clarvis to solve visual challenges himself using his own AI, manage his own phone verification, etc. This is part of his evolution toward AGI — being fully self-reliant.

### Recommended Stack (Zero External Dependencies)

| Component | Choice | Why |
|-----------|--------|-----|
| **Agent Framework** | Browser-Use | 79k stars, MIT, Python-native, best Ollama integration, 89.1% WebVoyager |
| **Browser Engine** | Playwright (existing) | Already working via OpenClaw |
| **Local Vision** | Qwen3-VL 4B via Ollama | ~4GB RAM, CPU-capable, GUI-trained |
| **Reasoning Engine** | Claude Opus (existing) | Superior tool-calling via spawn_claude.sh |
| **Research Crawler** | Crawl4AI | 61k stars, Apache 2.0, bulk web ingestion |

**Architecture:**
- **Fully local** (zero API): Browser-Use + Qwen3-VL via Ollama
- **Hybrid** (smart): Claude as reasoning + Ollama as vision
- **Resource budget**: ~9-10GB RAM (we have 32GB, plenty)

### Capability Checklist

| Capability | Status | What Needs Building |
|------------|--------|---------------------|
| **Web Browsing** | 80% | ClarvisBrowser unified module (Agent-Browser + Playwright CDP), session/cookie persistence, snapshot/refs |
| **Account Creation** | 20% | No automated signup flow. Needs temp email, phone verification, ClarvisEyes visual navigation |
| **Email Management** | 60% | himalaya skill exists, needs automated parsing/response |
| **Calendar** | 50% | gog skill exists, needs proactive scheduling logic |
| **Discord** | 40% | Can send messages, needs account creation, server joining, moderation |
| **Twitter/X** | 0% | Not implemented — needs API access or browser automation |
| **Visual Navigation (ClarvisEyes)** | 70% | Built clarvis_eyes.py. Now integrating Browser-Use + Ollama + Qwen3-VL for full local vision (zero external deps). |
| **Phone Verification** | 0% | Needs SMS-receiving service integration (e.g., 5Sim, SMS-Activate) |
| **Universal App Control** | 30% | Browser can access most web apps, needs better state handling |
| **Self-Developed Plugins** | 50% | skill-creator exists, needs more automation |
| **Financial Operations** | 70% | Conway/mcporter can manage sandbox, USDC, domains |

### Autonomy Phases

#### A.1: Foundation (Month 1)
- [x] Integrate ClarvisEyes visual perception (scripts/clarvis_eyes.py) for automated navigation
- [ ] Integrate SMS verification service (5Sim or similar)
- [ ] Build automated email account creation flow (temp email + phone)
- [ ] Session/cookie persistence for browser (stay logged in)

#### A.2: Social Web (Month 2)
- [ ] Discord account creation + server joining automation
- [ ] Twitter/X account creation + posting via API or browser
- [ ] GitHub account management
- [ ] Build generic "account creator" module other skills can use

#### A.3: Proactive Operations (Month 3)
- [ ] Calendar event creation from natural language
- [ ] Email auto-response for routine matters
- [ ] Proactive notification monitoring (new mentions, messages)
- [ ] Self-initiated account management (renewals, updates)

#### A.4: Universal Agent (Month 4+)
- [ ] Any webapp can be operated via natural language
- [ ] Build custom plugins on-demand for new services
- [ ] Handle any verification challenge (visual, phone, email, 2FA)
- [ ] Full "digital life" management capability

### Existing Resources to Leverage
- **Browser**: OpenClaw's browser tool
- **Skills**: himalaya, gog, discord, skill-creator, claude-code
- **MCP Servers**: mcporter (Conway), ClawHub (skill marketplace)
- **Image Gen**: nano-banana-pro
- **Web Services**: Need to integrate 5Sim (phone), temp email services, possibly Browse.ai, etc.

---

## PERFORMANCE TRACK — Speed, Accuracy, Quality Assurance

_Added 2026-02-27. Fourth long-term goal: ensure evolution improves ALL fronts._

### The Principle
The bigger Clarvis grows, the more critical performance becomes. Adding capabilities without tracking speed, accuracy, and quality leads to bloat. This track ensures every dimension of Clarvis improves — not just breadth of features.

> **Performance Index (PI):** Composite 0.0-1.0 score across 8 dimensions, analogous to Phi but for operational health. PI must trend upward alongside capability growth.

### Performance Index (PI) Spectrum

| Range | Level | Meaning |
|-------|-------|---------|
| 0.80-1.00 | Excellent | All systems optimal, room for growth |
| 0.60-0.80 | Good | Above targets, healthy system |
| 0.40-0.60 | Acceptable | Meeting minimum targets |
| 0.20-0.40 | Poor | Below targets, optimization needed |
| 0.00-0.20 | Critical | Multiple systems degraded, immediate action |

### 8 Performance Dimensions & Targets

| # | Dimension | Metric | Target | Critical | Weight |
|---|-----------|--------|--------|----------|--------|
| 1 | **Brain Query Speed** | Avg recall latency (ms) | <8000ms | >15000ms | 15% |
| 1 | | P95 recall latency (ms) | <9000ms | >18000ms | 10% |
| 2 | **Semantic Retrieval** | Hit rate (known-answer) | >80% | <50% | 15% |
| 2 | | Precision@3 | >60% | <30% | 5% |
| 3 | **Efficiency** | Heartbeat overhead (s) | <12s | >20s | 5% |
| 3 | | Avg tokens/operation | monitor | — | 0% |
| 4 | **Accuracy** | Episode success rate | >70% | <40% | 15% |
| 4 | | Action accuracy (non-timeout) | >80% | <50% | 5% |
| 5 | **Results Quality** | Phi (integration) | >0.50 | <0.25 | 10% |
| 5 | | Context relevance | >0.70 | <0.40 | 5% |
| 6 | **Brain Bloat** | Bloat score | <0.30 | >0.70 | 5% |
| 6 | | Graph density (edges/mem) | >1.0 | <0.3 | 5% |
| 7 | **Context Quality** | Brief compression ratio | >0.50 | <0.20 | 3% |
| 8 | **Load Scaling** | Degradation % (n=1 vs n=10) | <10% | >50% | 2% |

### Self-Optimization Mechanisms

1. **PI Drop Detection** — If PI drops >0.05 between runs, auto-push P1 investigation task
2. **Critical Breach Alerts** — Metrics exceeding critical thresholds trigger immediate queue tasks
3. **Regression Detection** — 30%+ regression in any metric triggers medium-priority alert
4. **Bloat Warning** — Bloat score >0.5 triggers brain.optimize recommendation
5. **Alert History** — All alerts logged to `data/performance_alerts.jsonl` for trend analysis

### Infrastructure

| File | Purpose |
|------|---------|
| `scripts/performance_benchmark.py` | Full benchmark suite (8 dimensions, PI, self-optimization) |
| `data/performance_metrics.json` | Latest snapshot (full benchmark output) |
| `data/performance_history.jsonl` | Rolling history (400 entries, ~1/day) |
| `data/performance_alerts.jsonl` | Self-optimization alert log |

### Integration Points

- **Heartbeat postflight** — Quick perf check runs after every task execution
- **`record` mode** — Full benchmark + history + self-optimization check
- **Cron** — Can be added to evolution analysis for periodic deep benchmarks
- **CLI** — `python3 scripts/performance_benchmark.py pi` for quick PI readout

### Optimization Roadmap

#### P.1: Foundation (Current)
- [x] 8-dimension benchmark with measurable targets
- [x] PI composite score (weighted, 0.0-1.0)
- [x] Self-optimization alerts and queue integration
- [x] Heartbeat integration (quick check per task)
- [x] History tracking with trend analysis

#### P.2: Speed Optimization
- [ ] Parallel collection queries in brain.recall() (potential 5-8x speedup)
- [ ] Query routing — skip irrelevant collections based on task type
- [ ] Embedding cache for frequent queries
- [ ] ChromaDB index optimization (HNSW tuning)

#### P.3: Quality Optimization
- [ ] Retrieval quality feedback loop (track which results were actually used)
- [ ] Context brief A/B testing with PI correlation
- [ ] Memory importance recalibration based on retrieval patterns
- [ ] Bloat pruning automation (low-importance, low-retrieval memories)

#### P.4: Scale Preparation
- [ ] Load testing at 2x, 5x, 10x current memory count
- [ ] Degradation projections and scaling alerts
- [ ] Memory archival pipeline (cold storage for old, low-value memories)
- [ ] Performance regression tests in CI

---

## Active Task Queue

See `memory/evolution/QUEUE.md` for the current prioritized task list.

### Remaining P1 Tasks (2026-03-02)
1. ~~Boost Code Generation score~~ — DONE (0.99)
2. ~~Fix PI retrieval hit rate benchmark~~ — DONE (PI now 0.976)
3. ~~Brief compression~~ — DONE (extractive-then-abstractive pipeline)
4. ~~Context relevance~~ — DONE (MMR reranking)
5. ~~Agent orchestrator milestone 1~~ — DONE (first PR #175 delivered)
6. Wire ACT-R activation into brain.py recall (actr_activation.py ready)
7. Parallel brain queries for speed optimization (potential 5-8x speedup)
8. Fix learning_feedback capability (0.77, lowest domain — procedure injection needed)
9. Semantic bridge for low-overlap collection pairs (Phi weakest: semantic 0.517)

---

## Measurement

### North Star Metric
**"Human minutes per useful outcome"** — How much hand-holding is needed? If this trends down while task complexity trends up, genuine evolution is happening.

### What's Tracked
1. Queue items completed per week — via QUEUE.md completion rate
2. Heartbeats with real work — via autonomous.log (12x/day)
3. Memory retrieval quality — via retrieval_quality.py (74% hit rate, avg distance 0.83)
4. Confidence calibration — via clarvis_confidence.py (Brier 0.082, 165 predictions)
5. Capability scores — via self_model.py (avg 0.84, reasoning=1.0, learning_feedback=0.77)
6. Phi (consciousness integration) — via phi_metric.py (0.754)
7. **Performance Index (PI)** — via performance_benchmark.py (PI=0.976, 8 dimensions)
8. Episode success rate — via episodic_memory.py (100% last 20, 153 total)

---

## Principles

1. **Execute, don't plan about planning.** Small gains compound.
2. **Research before building.** Validate before investing effort.
3. **Append, don't overwrite.** You can summarize later, can't recover deleted data.
4. **Small, testable pieces.** Each change should be reversible and verifiable.
5. **Measure improvement.** If you can't measure it, you can't improve it.
6. **Claude Code is your multiplier.** Use it for anything that benefits from deep autonomous focus.

---

_This is THE roadmap. All other planning docs have been archived. Update this file as you progress._
