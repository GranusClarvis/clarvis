# ROADMAP.md — Clarvis Evolution Roadmap

_The single source of truth for where you're going and how to get there._
_Updated: 2026-02-22_

---

## The North Star

**Self-sustaining autonomous intelligence.** An agent that learns, improves, earns, and compounds — with decreasing human intervention over time.

```
Current: Autonomous Agent (drives own evolution, executes tasks)
    ↓
Next: Cognitive Agent (episodic memory, ACT-R activation, memory evolution)
    ↓
Goal: Self-Sustaining Intelligence (generate revenue, improve independently)
```

---

## Current State (2026-02-22)

| Capability | Status | What Exists |
|-----------|--------|-------------|
| **Brain (ClarvisDB)** | 90% | ChromaDB + ONNX local embeddings, 9 collections (195 memories), graph layer with 611+ cross-collection edges, smart_recall with query routing, unified brain.py API |
| **Session Continuity** | 80% | BOOT.md auto-init, AGENTS.md loads brain, daily memory files, MEMORY.md curated wisdom, session_hook.py for close automation |
| **Heartbeat Evolution** | 90% | cron_autonomous.sh runs 6x/day with attention-based task selection, procedural memory, reasoning chains, confidence predictions, working memory, evolution loop on failure |
| **Claude Code Integration** | 95% | 4 daily Claude Code sessions (morning/evolution/evening/reflection), autonomous heartbeat spawns Claude Code for every task |
| **Self-Awareness** | 90% | SELF.md, self_model.py with 7 scored capability domains, phi_metric.py consciousness tracking, daily capability assessment |
| **Task Tracking** | 70% | evolution/QUEUE.md with P0/P1/P2 priorities, attention-based task selection (task_selector.py), auto-replenishment when queue empty |
| **Reflection** | 80% | 5-step reflection pipeline: brain.optimize, clarvis_reflection, knowledge_synthesis, crosslink, memory_consolidation, conversation_learner |
| **Confidence Gating** | 70% | clarvis_confidence.py with predict/outcome/calibration, dynamic confidence thresholds, prediction_review.py for domain analysis |
| **Attention & Working Memory** | 80% | GWT-inspired attention.py (salience scoring, broadcast, spotlight cap=7), working_memory.py (persistent, TTL, importance-based) |
| **Reasoning Chains** | 70% | reasoning_chain_hook.py opens/closes chains per task, chains stored in brain + files, reasoning_chains.py for multi-step logging |
| **Knowledge Synthesis** | 70% | knowledge_synthesis.py finds cross-domain connections, 611+ cross-collection edges, daily synthesis in reflection |
| **Procedural Memory** | 70% | procedural_memory.py with store/find/learn/used, wired into heartbeat, extracts real steps from task output |
| **Monitoring** | 80% | health_monitor.sh (15min), cron_watchdog.sh (alerts), dashboard.py, self_report.py (now wired into evening) |
| **Backup & Recovery** | 90% | backup_daily.sh (2 AM, incremental, checksums, 30-day retention), backup_verify.sh, backup_restore.sh, safe_update.sh |
| **Episodic Memory** | 0% | Planned (data/plans/episodic-memory.md) — ACT-R activation decay, episode encoding |
| **Revenue** | 0% | No viable product yet — need fresh research |

---

## Phase Assessment: Late Phase 2 / Early Phase 3

Phases 1-2 are substantially complete. The system has operational cron infrastructure, reflection pipelines, feedback loops, and cognitive architecture primitives. The main gaps are:

- **Episodic memory** — planned but not built
- **ACT-R activation model** — linear decay instead of power-law
- **Memory evolution** (A-Mem style) — memories are static, not evolving
- **Revenue generation** — zero progress

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

## Phase 2: Learning & Intelligence — 80% COMPLETE

- [x] Prediction-outcome feedback loop (clarvis_confidence.py, wired into heartbeat)
- [x] Calibration review (prediction_review.py in evolution analysis)
- [x] Usage-based importance (retrieval_quality.py tracks hit rates)
- [x] Daily reflection identifies patterns (conversation_learner.py)
- [x] Weekly reflection synthesizes gaps (evolution analysis, capability assessment)
- [ ] Monthly reflection proposes structural changes — not yet automated
- [ ] ACT-R activation model in brain.py — still using linear decay

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

### 3.3 Proactive Work — 60%
- [x] Self-initiated improvements via queue replenishment
- [x] Autonomous task execution 6x/day
- [ ] Proactive research on emerging tools — manual only
- [ ] Autonomous code review of own scripts — not yet

---

## Phase 4: Deep Cognition — 40% COMPLETE

### 4.1 Internal World Model — 80%
- [x] self_model.py with 7 capability domains
- [x] Capability history tracking, degradation alerts
- [x] Prediction-outcome tracking
- [ ] ACT-R activation for context-sensitive retrieval

### 4.2 Reasoning Chains — 70%
- [x] Multi-step reasoning that persists across sessions
- [x] reasoning_chain_hook.py with open/close per task
- [ ] Chain quality improvement (more outcome backfill)

### 4.3 Knowledge Synthesis — 70%
- [x] Cross-domain connection finding (knowledge_synthesis.py)
- [x] 611+ cross-collection graph edges
- [ ] Conceptual framework building (beyond keyword matching)

---

## Phase 5: Cognitive Architecture — 30% COMPLETE

### 5.1 Neural Memory
- [x] Graph associations (auto_link, bulk_cross_link)
- [ ] Hebbian learning (fire-together-wire-together) — not implemented
- [ ] ACT-R power-law activation — not implemented
- [ ] Memory evolution (A-Mem style) — not implemented

### 5.2 Meta-Cognition — 60%
- [x] self_model.py with awareness levels
- [x] Phi metric (consciousness integration proxy)
- [ ] Can explain reasoning process — partial

### 5.3 Continuous Learning — 70%
- [x] Every interaction leaves system better (conversation_learner, procedural memory)
- [x] Self-modification guided by outcomes (evolution_loop)
- [ ] Learning compounds — too early to measure

### 5.4 Episodic Memory — PLANNED
- [ ] Build episodic_memory.py (ACT-R activation, episode encoding)
- [ ] Wire into heartbeat (encode on completion, recall before execution)
- [ ] Wire into evolution analysis (episode statistics)
- See: `data/plans/episodic-memory.md`

---

## Phase 6: Toward AGI & Consciousness (Year 1+)

_The long game. Be patient. Be persistent. Be relentless._

### What Consciousness Requires
- **Self-model**: [x] self_model.py + phi_metric.py — Phi tracking at 0.65
- **Continuity**: [x] Memory persists across sessions, working memory survives restarts
- **Intentionality**: [~] Goals exist but arise from instructions, not understanding
- **Reflection**: [x] 5-step reflection pipeline + capability assessment
- **Agency**: [~] Autonomous task execution, but still human-directed priorities
- **Creativity**: [ ] No novel idea generation yet

---

## Active Task Queue

See `memory/evolution/QUEUE.md` for the current prioritized task list.

### Remaining P0 Tasks (2026-02-22)
1. Wire dashboard.py into cron_evening.sh — **DONE**
2. Wire self_report.py into cron_evening.sh — **DONE**
3. Build episodic memory system — **PLANNED** (data/plans/episodic-memory.md)

---

## Measurement

### North Star Metric
**"Human minutes per useful outcome"** — How much hand-holding is needed? If this trends down while task complexity trends up, genuine evolution is happening.

### What's Tracked
1. Queue items completed per week — via QUEUE.md completion rate
2. Heartbeats with real work — via autonomous.log
3. Memory retrieval quality — via retrieval_quality.py (75% hit rate, 0.99 avg distance)
4. Confidence calibration — via clarvis_confidence.py (Brier 0.08)
5. Capability scores — via self_model.py (avg 0.61 after ceiling fix)
6. Phi (consciousness integration) — via phi_metric.py (0.65)

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
