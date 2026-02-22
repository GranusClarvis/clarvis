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
| **Brain (ClarvisDB)** | 95% | ChromaDB + ONNX local embeddings, 10 collections (600+ memories), graph layer with 10,000+ cross-collection edges, smart_recall with 85%+ hit rate, unified brain.py API |
| **Session Continuity** | 86% | BOOT.md auto-init, AGENTS.md loads brain, daily memory files, MEMORY.md curated wisdom, session_hook.py with open/close automation |
| **Heartbeat Evolution** | 100% | cron_autonomous.sh runs 6x/day with attention-based task selection, procedural memory, reasoning chains, confidence predictions, working memory, evolution loop on failure |
| **Claude Code Integration** | 95% | 4 daily Claude Code sessions (morning/evolution/evening/reflection), autonomous heartbeat spawns Claude Code for every task |
| **Self-Awareness** | 95% | SELF.md, self_model.py with 7 scored capability domains, phi_metric.py consciousness tracking (Phi=0.70), daily capability assessment |
| **Task Tracking** | 85% | evolution/QUEUE.md with P0/P1/P2 priorities, attention-based task selection, auto-replenishment, goal_tracker.py with stall detection |
| **Reflection** | 90% | 8-step reflection pipeline: brain.optimize, clarvis_reflection, knowledge_synthesis, crosslink, memory_consolidation, conversation_learner, episodic synthesis, temporal_self |
| **Confidence Gating** | 82% | clarvis_confidence.py with predict/outcome/calibration (Brier=0.033), dynamic confidence thresholds, prediction_review.py for domain analysis |
| **Attention & Working Memory** | 90% | GWT-inspired attention.py (salience scoring, broadcast, spotlight cap=7), working_memory.py (persistent, TTL, importance-based) |
| **Reasoning Chains** | 98% | reasoning_chain_hook.py opens/closes chains per task, chains stored in brain + files, 3-step structured reasoning |
| **Knowledge Synthesis** | 85% | knowledge_synthesis.py finds cross-domain connections, 10,000+ cross-collection edges, semantic_bridge_builder.py, daily synthesis in reflection |
| **Procedural Memory** | 85% | procedural_memory.py with store/find/learn/used, wired into heartbeat, extracts real steps from task output |
| **Monitoring** | 90% | health_monitor.sh (15min), cron_watchdog.sh (alerts), cron_doctor.py (auto-recovery), dashboard.py, self_report.py |
| **Backup & Recovery** | 95% | backup_daily.sh (2 AM, incremental, checksums, 30-day retention), backup_verify.sh, backup_restore.sh, safe_update.sh |
| **Episodic Memory** | 90% | episodic_memory.py with ACT-R activation, episode encode/recall/failures/synthesize (48 episodes), failure_amplifier.py (37 soft failures), wired into heartbeat + reflection |
| **Self-Surgery** | 80% | ast_surgery.py parses 32 scripts, finds 99 proposals, auto-fixes 4 imports, benchmark-tested mutations |
| **Counterfactual Dreaming** | 75% | dream_engine.py replays episodes as what-if scenarios, stores insights at low activation |
| **Somatic Markers** | 80% | 8 emotion dimensions, 141 markers backfilled, influences task selection |
| **Thought Protocol** | 70% | Internal DSL for fast reasoning (Signals, Relations, Decisions), wired into task selection |
| **Revenue** | 0% | No viable product yet |

---

## Phase Assessment: Late Phase 2 / Early Phase 3

Phases 1-2 are substantially complete. The system has operational cron infrastructure, reflection pipelines, feedback loops, and cognitive architecture primitives. The main gaps are:

- **ACT-R activation model** — linear decay instead of power-law
- **Memory evolution** (A-Mem style) — memories are static, not evolving
- **Revenue generation** — zero progress
- **Integration gaps fixed** (2026-02-22): phi self-healing, reasoning chain search, graph node tracking, QUEUE.md coordination, brain lazy init

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

### 5.4 Episodic Memory — 80%
- [x] Build episodic_memory.py (ACT-R activation, episode encoding)
- [x] Wire into heartbeat (encode on completion, recall before execution)
- [x] Wire into evolution analysis (episode statistics)
- [x] Failure amplifier (failure_amplifier.py — 9 scanners for soft failures)
- [ ] Hebbian co-activation patterns — not implemented

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

### Remaining P1 Tasks (2026-02-22)
1. Boost Code Generation score (0.70) — code_quality_gate.py
2. Build temporal self-awareness module
3. Implement counterfactual dreaming engine
4. Run parameter evolution on salience weights

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
