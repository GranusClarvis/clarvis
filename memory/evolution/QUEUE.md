# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint (2026-04-13)

- [x] [BCR_CRASH_FIX] _(completed 2026-04-13)_ — Fixed TypeError crash in `assembly.py:_format_recovery_lines` where `episode.get("error")` returned `None`. Added None-safety to `error`, `task`, and `lesson` fields. BCR recovered from 0.000 → 0.826 (target: 0.55).

### Today's Priorities (2026-04-13)
- [x] [BRAIN_STORE_RECALL_FIX] _(completed 2026-04-13)_ — Store/recall test now reports "healthy". Issue self-resolved (likely fixed by prior dedup probe fix). Verified: `brain health` confirms healthy round-trip.
- [x] [PHI_INTRA_DENSITY_BOOST] _(completed 2026-04-13)_ — Built `scripts/brain_mem/intra_density_boost.py`. Added 2663 intra-collection edges (cosine>0.6, cap 500/collection). Intra-density improved 0.376→0.402. Worst collections improved: learnings 0.280→0.290, autonomous-learning 0.287→0.368, memories 0.311→0.348.

## P1 — This Week

### Strategic Audit Structural Fixes (2026-04-11 audit)

### Fresh-Install / Isolation Validation

### Install Docs / Support Surface Consolidation (2026-04-07) — DEPRIORITIZED by audit 2026-04-11, move to P2 when reasoning work is complete
- [x] [RUNTIME_AUDIT_FINDINGS_REVIEW] _(completed 2026-04-13)_ → `docs/internal/audits/runtime_findings_review_20260413.md` — 3 fixed, 8 remaining issues classified by severity/type/confidence
- [x] [RUNTIME_HARDENING_PLAN] _(completed 2026-04-13)_ → `docs/internal/audits/runtime_hardening_plan_20260413.md` — 4 severity groups, validation matrix, rollback plans
- [x] [HEARTBEAT_GATE_WIRING_IN_AUTONOMOUS] _(completed 2026-04-13)_ — Gate pre-check wired after lock acquisition in `cron_autonomous.sh`. Skip-on-no-change, force-wake on gap/midnight/max-skips. Syntax verified.
- [x] [CLAUDE_MD_PATH_DRIFT_CLEANUP] _(completed 2026-04-13)_ — Fixed 10+ stale paths in CLAUDE.md: cost_tracker, budget_alert, spawn_claude, cron_env, health_monitor, cron_watchdog, cron_doctor, safe_update, script categories, Telegram commands.
- [x] [SIDECAR_PRUNING_SCHEDULE] _(completed 2026-04-13)_ — Wired `prune_sidecar(removed_days=30, succeeded_days=90)` into Sunday `cron_cleanup.sh`. Currently 247 entries, 0 eligible for pruning (all recent). Will auto-prune weekly.
- [x] [ACP_PROCESS_BASELINE_AUDIT] _(completed 2026-04-13)_ → `docs/internal/acp_process_baseline.md` — 6 orphan processes (~290MB, 9 days old) documented. Thresholds: >48h=CRITICAL, >500MB RSS=WARNING. Kill commands provided.
- [x] [REASONING_CHAIN_DEPTH_REMEDIATION] _(completed 2026-04-13)_ — Added `MIN_CHAIN_DEPTH` constants (P0/P1: 3, P2/default: 2), `validate_depth()` method, depth warnings in `complete()` and `close_chain()`. Tested: shallow chains now flagged.
- [x] [PERFECT_STATE_ACCEPTANCE_CRITERIA] _(completed 2026-04-13)_ → `docs/internal/perfect_state_acceptance_criteria.md` + `scripts/infra/acceptance_check.py` — 9 categories, 25+ checks, quick/full/JSON modes. Quick check: 9/9 PASS.
- [x] [WATCHDOG_CALIBRATION_MONITORING] _(completed 2026-04-13)_ — Wired `calibration_report` cron (Sun 06:45) into `cron_watchdog.sh` check + recheck loops. Now monitored with 170h window (weekly).

---

## P2 — When Idle

### Phi Recovery (0.620→0.65 target, added 2026-04-12)
- [x] [PHI_INTRA_DENSITY_BOOST] _(completed 2026-04-13)_ — See P0 entry above. 2663 intra-collection edges added, intra-density 0.376→0.402.
- [x] [PHI_DEDUP_101_CLEANUP] _(completed 2026-04-13)_ — Ran `clarvis brain optimize-full`: removed 163 duplicates, pruned 57 noise memories, decayed 1880. Brain reduced from 3058→2827 memories (cleaner, denser).
- [x] [BRAIN_STORE_RECALL_FIX] _(completed 2026-04-13)_ — See P0 entry. Store/recall healthy.

### Deep Cognition (Phase 4-5 gaps)
- [x] [COGNITION_CONCEPTUAL_FRAMEWORK] _(completed 2026-04-13)_ — Built `clarvis/cognition/conceptual_framework.py`. Semantic clustering of 1316 brain memories into 60 concepts (50 cross-domain) with 828 inter-concept edges. TF-IDF keyword extraction, greedy cosine clustering (threshold 0.6), concept graph with typed relations (similar/co-occurs/subsumes). API: `build_concepts()`, `find_concept()`, `concept_search()`, `concept_neighbors()`, `stats()`. Registered in cognition `__init__.py`. Updated canonical_state_refresh to report live concept stats.

### Calibration / Brier Score (weakest metric — all-time Brier=0.1148 vs target 0.1, 7-day=0.2400)
- [x] [BRIER_7D_REGRESSION_DIAGNOSIS] _(resolved 2026-04-13)_ — Regression self-corrected. Current: all-time Brier=0.083 (target <0.1), 7-day Brier=0.052 (excellent). Confidence bands now span 0.55-0.88 with good calibration. No fix needed.
- [x] [CALIBRATION_CONFIDENCE_BAND_AUDIT] _(completed 2026-04-13)_ — Replaced coarse global 0.825 threshold with per-domain accuracy ceilings. Added `_domain_accuracy()` to confidence.py. `predict()` now caps confidence at empirical domain accuracy + 5% margin (e.g., optimization 83%→88% ceiling, bug_fix 88%→93% ceiling). Domain penalty still applies for >10% failure rate domains. Weekly calibration report now shows per-domain accuracy table.
- [x] [CALIBRATION_BAND_GRANULARITY] _(completed 2026-04-13)_ — Low-confidence expression already implemented via `task_aware_confidence()` (floor 0.55 for novel tasks). Per-domain ceilings now further diversify confidence output. Combined with CALIBRATION_CONFIDENCE_BAND_AUDIT.
- [x] [REASONING_CHAIN_DEPTH_ENFORCEMENT] _(completed 2026-04-13)_ — Added post-chain rejection gate in `reasoning.py:complete()`. Shallow chains (below MIN_CHAIN_DEPTH for priority) are now: (1) logged to `data/reasoning_chains/shallow_rejections.jsonl` with full metadata, (2) excluded from brain storage to prevent polluting long-term memory. Deep chains still stored normally. Builds on REMEDIATION's `validate_depth()` + `MIN_CHAIN_DEPTH` constants.
- [x] [CRON_BRIER_CALIBRATION_REPORT] _(completed 2026-04-13)_ — Created `scripts/cron/calibration_report.py` + `cron_calibration_report.sh`. Reports: Brier (7d/30d/all-time/weighted), confidence band distribution + accuracy, per-domain accuracy & ceilings, confidence histogram, drift detection. Cron entry: Sun 06:45 UTC. First run: Brier=0.0827 (all-time), 0.0523 (7d), PASS.

### CLR Autonomy Dimension (critically low: 0.025)

### Adaptive RAG Pipeline
- [x] [RAG_PHASE1_GATE] _(completed 2026-04-13, retroactive)_ — All 4 phases implemented and wired: GATE (`clarvis/brain/retrieval_gate.py`, 3-tier NO/LIGHT/DEEP classification), EVAL (`retrieval_eval.py`, CRAG-style scoring + strip refinement), RETRY (adaptive recall with query rewriting), FEEDBACK (`retrieval_feedback.py`, RL-lite EMA loop wired into postflight). Full pipeline active in `heartbeat_preflight.py` since prior sessions.

### Cron Schedule Hygiene (non-Python)

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (currently 0.35, target 0.70)

### Cron / Non-Python (2026-04-09 evolution)

---

## Partial Items (tracked, not actively worked)

### External Challenges

- [ ] [EXTERNAL_CHALLENGE:bench-memory-01] Implement a memory consolidation quality test — Test whether brain.optimize_full() actually improves retrieval quality. Methodology: (1) baseline retrieval on 20 gold queries, (2) run optimize_full, (3) re-test same queries. Measure: nDCG change, l

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-07] Build a minimal theorem prover for propositional logic — Implement a resolution-based theorem prover for propositional logic: parse formulas (AND, OR, NOT, IMPLIES), convert to CNF, apply resolution rule until proven or saturated. Support: modus ponens, con

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-10] Implement A* search with multiple heuristics on a graph puzzle — Build A* search for the 15-puzzle (4x4 sliding tile puzzle). Implement 3 heuristics: Manhattan distance, linear conflict, and pattern database (3x3 corner). Compare: nodes expanded, solution length, t

- [ ] [EXTERNAL_CHALLENGE:synthesis-02] Implement contradiction detection across wiki pages — Build a contradiction detector: for each pair of wiki pages that share a tag, compare their Key Claims via embedding similarity. Flag pairs where claims are semantically similar but contain negation o

- [ ] [EXTERNAL_CHALLENGE:reasoning-depth-02] Implement analogical reasoning between brain memories — Build an analogy engine: given a source pair (A:B), find the best matching target pair (C:D) from brain memories. Use embedding offsets (B-A ≈ D-C) to detect structural analogies. Test on 10 analogy q

- [ ] [EXTERNAL_CHALLENGE:reasoning-depth-05] Implement argument mapping for wiki claims — Build an argument mapper: given a wiki page with Key Claims, extract the argument structure (premises → conclusion, supports/rebuts relations). Output a directed graph of arguments. Visualize as ASCII

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-09] Implement a regex engine from scratch (Thompson NFA) — Build a regex engine using Thompson's NFA construction: support concatenation, alternation (|), Kleene star (*), plus (+), optional (?), and character classes [a-z]. Convert regex to NFA, simulate NFA

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-04] Build a git-diff semantic analyzer that classifies changes — Create a tool that reads a git diff and classifies each hunk as: bugfix, feature, refactor, test, docs, or config. Use heuristics (file paths, changed line patterns, commit message) — no LLM calls. Te

- [ ] [EXTERNAL_CHALLENGE:bench-code-01] Write a property-based test suite for ClarvisDB graph operations — Use Hypothesis library to generate random graph operations (add_edge, remove_edge, traverse) and verify invariants: no orphan edges after cleanup, bidirectional consistency, cycle detection correctnes

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-05] Implement a bloom filter for fast duplicate detection in brain.store() — Add a Bloom filter as a fast pre-check before the expensive ChromaDB cosine similarity dedup in brain.store(). Tune false positive rate to <1%. Measure: (a) how many expensive dedup calls are avoided,

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-03] Implement incremental TF-IDF for streaming document indexing — Build an incremental TF-IDF index that can add documents one at a time without recomputing the entire corpus. Support search queries returning top-k results. Compare accuracy against sklearn's TfidfVe
- [ ] [EXTERNAL_CHALLENGE:coding-challenge-next] Pick and complete next coding challenge from benchmark suite.

---

## Research Sessions
