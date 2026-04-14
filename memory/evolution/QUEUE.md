# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint (2026-04-14)


### Today's Priorities (2026-04-14)
- [x] **PRIORITY 1: [PHI_INTRA_DENSITY_BOOST]** Boost intra-collection density — 1,127 edges added across learnings/memories/episodes/identity/goals/context/autonomous-learning (2026-04-14). Total intra_similar edges now 19,309.
- [x] **PRIORITY 2: [REFLECTION 2026-04-13] Script merge** — Audited 2026-04-14: no function overlap found between merge candidates. retrieval_quality.py is already a bridge (18 lines). Only retrieval_benchmark.py is actively called (cron_evening.sh). Others (retrieval_experiment, prediction_resolver/review, meta_gradient_rl, parameter_evolution) are dormant — no active shell callers. Low-value merge; recommend deletion audit instead.
- [ ] **PRIORITY 3: [REFLECTION 2026-04-13] Capability gap experiment** — Deep self-analysis: identify most limiting capability gap, design targeted experiment.

## P1 — This Week

### Phi Recovery — Intra-Collection Density (weakest Phi sub-component: 0.38)
- [x] [REFLECTION 2026-04-13] Simplify or merge overlapping scripts — audited 2026-04-14: no function overlap. Most candidates are dormant (no active callers). See P0 Script merge item for details.
- [ ] [REFLECTION 2026-04-13] Deep self-analysis: What capability gap is most limiting? Design an experiment to address it
- [x] [PHI_INTRA_DENSITY_BOOST] Boost intra-collection density — done 2026-04-14 via intra_density_boost.py (threshold=0.6, cap=500/collection). 1,127 new edges added.

### Reasoning Chain Depth (capability score: 0.80, Phase 4.2 gap)

### Conceptual Framework Activation (Phase 4.3 gap — "beyond keyword matching")

### Cron Reliability (non-Python)

### Intelligence & Learning Goal (active goal: 58%)

### Strategic Audit Structural Fixes (2026-04-11 audit)

### Fresh-Install / Isolation Validation

### Install Docs / Support Surface Consolidation (2026-04-07) — DEPRIORITIZED by audit 2026-04-11, move to P2 when reasoning work is complete

---

## P2 — When Idle

### Phi Recovery (0.620→0.65 target, added 2026-04-12)

### Deep Cognition (Phase 4-5 gaps)

### Calibration / Brier Score (weakest metric — all-time Brier=0.1148 vs target 0.1, 7-day=0.2400)

### CLR Autonomy Dimension (critically low: 0.025)

### Adaptive RAG Pipeline

### Cron Schedule Hygiene (non-Python)

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (currently 0.35, target 0.70)

### Cron / Non-Python (2026-04-09 evolution)

---

## Partial Items (tracked, not actively worked)

### External Challenges

- [x] [EXTERNAL_CHALLENGE:reasoning-depth-01] Multi-step logical deduction: CSP solver with AC-3 + backtracking implemented (2026-04-14). 3 puzzles (easy/3, medium/7, hard/12 constraints), 19 tests pass. Files: scripts/reasoning/csp_solver.py, tests/test_csp_solver.py














---

## Research Sessions
