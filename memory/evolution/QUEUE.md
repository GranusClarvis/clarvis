# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint (2026-04-12)

- [ ] [PHI_REACHABILITY_WEIGHT_DEPLOY] **(Audit 2026-04-11, flagged 3 consecutive audits, failed 2026-04-11 attempt)** Deploy the already-coded Phi reachability weight change (0.25→0.10) in `clarvis/metrics/phi.py`. The fix exists in code comments but was never applied to actual scoring — all 64 historical values use old weights. Reachability is permanently 1.0, inflating Phi by ~35%. Apply the weight, recalculate baseline, update any threshold alerts.
- [x] [CALIBRATION_LOW_CONFIDENCE_EXPRESSION] _(2026-04-12)_ Added `task_aware_confidence()` to `clarvis/cognition/confidence.py` — adjusts base confidence using episode count, procedure match, research/exploratory flags, and text novelty markers. Wired into `heartbeat_preflight.py` §7. Novel tasks now emit 0.55-0.75 instead of 0.85+. Added `_task_aware` flag to `predict()` to prevent underconfidence boost from overriding intentional low signals.
- [x] [COGNITIVE_STACK_AB_TEST] _(2026-04-12)_ 10-task A/B test: 9/10 byte-identical (modules dormant for novel tasks), 1 code task showed +0.615 delta. Full=0.519, Ablated=0.458. Verdict: architecture is correctly designed (on-demand activation), not overhead. Results in `data/cognitive_stack_ab_test.json`, notes in `memory/research/runs/`.
- [x] [ISOLATION_GUARD_SELFTEST_FIX] _(2026-04-12)_ Replaced subshell stdout-capture pattern with subprocess exit-code checks. Added test 5 (auth dir). All 5 tests pass.

## P1 — This Week

### Strategic Audit Structural Fixes (2026-04-11 audit)
- [x] [COGNITIVE_STACK_AB_TEST] _(2026-04-12)_ Done — see P0. 9/10 identical, modules activate on-demand.
- [ ] [DEAD_SCRIPT_PURGE] **(Audit 2026-04-11, rescoped 2026-04-12)** Original claim of 88 unused scripts was incorrect — thorough reference analysis (crontab, imports, script_loader, spine, tests, docs) found ALL scripts in priority dirs (wiki/13, infra/27, hooks/13, cognition/12) have ≥1 external reference. Rescope: identify scripts whose ONLY references are in docs/archive (not code/cron), and target those. `collect_test_artifacts.sh` is the clearest candidate (archive-only ref).
- [ ] [LLM_BRAIN_REVIEW 2026-04-09] [LLM_BRAIN_REVIEW] Add temporal indexing or a recency-boosted retrieval path for queries containing time signals ('last 24 hours', 'recently', 'today') — e.g., filter by metadata timestamp before semantic ranking — Temporal queries (Probe 6) consistently return zero relevant results. An agent that cannot recall what it did yesterday has a fundamental operational gap.

### Fresh-Install / Isolation Validation
- [ ] [E2E_OPENCLAW_LOCAL_BASELINE] Run a truly fresh isolated OpenClaw install in `/tmp` or equivalent, wired to the local LLM only. Validate gateway boot, health, local-model chat round-trip, profile/config bootstrap, and produce a clear PASS/FAIL baseline specifically for “can Clarvis be installed on top of this as a new user would do it?”.
- [ ] [E2E_HERMES_FRESH_ISOLATED] Run a truly fresh isolated Hermes install in `/tmp` or equivalent, with isolated venv/config/session dirs and the local LLM only. Validate install, main entry points, config bootstrap, session persistence, basic chat loop, and identify the exact supported invocation path (`hermes` vs `run_agent.py`) with no hand-wavy workarounds.
- [ ] [E2E_CLARVIS_ON_OPENCLAW_FRESH] Starting from a fresh isolated OpenClaw install already wired to the local LLM, install Clarvis using the public install script exactly as a user would. Then run full end-to-end validation of core Clarvis features and document friction, failures, unsupported paths, and required manual steps.
- [ ] [E2E_CLARVIS_ON_HERMES_FRESH] Starting from a fresh isolated Hermes install already wired to the local LLM, install Clarvis using the public install script exactly as a user would. Then run full end-to-end validation of core Clarvis features and document friction, failures, unsupported paths, and required manual steps.
- [ ] [ADOPTION_MATRIX_LOCAL_HARNESS] Produce a single adoption matrix for fresh installs: OpenClaw base, Hermes base, Clarvis-on-OpenClaw, Clarvis-on-Hermes. For each, record local-LLM-only status, exact invocation path, install friction, first-run success, end-to-end feature coverage, and whether the path is honestly claimable for users.

### Install Docs / Support Surface Consolidation (2026-04-07) — DEPRIORITIZED by audit 2026-04-11, move to P2 when reasoning work is complete
- [x] [INSTALL_MD_TIGHTENING] _(2026-04-12)_ Removed stale sub-packages note and references (packages consolidated into spine), dropped runtime troubleshooting (gateway issues) in favor of cross-link to runtime guides, cleaned up uninstall command. INSTALL.md is now install-only.
- [ ] [INSTALL_MATRIX_PROMOTION] Promote `docs/INSTALL_MATRIX.md` as the source of truth for validation criteria. Make sure README/install docs link to it whenever claims are made about harness support or fresh-install readiness.
- [ ] [OPENCLAW_RUNTIME_GUIDE_SCOPE] Refocus `docs/USER_GUIDE_OPENCLAW.md` into a runtime/operator guide only: usage, autonomy, commands, troubleshooting, and runtime expectations. Strip install duplication.
- [ ] [HERMES_RUNTIME_GUIDE_SCOPE] Refocus `docs/USER_GUIDE_HERMES.md` into a runtime/operator guide only, and add a prominent support-status banner at the top if Hermes remains partial/experimental.
- [ ] [INSTALL_DOC_CROSS_LINKING] Add intentional cross-links between README, INSTALL, SUPPORT_MATRIX, INSTALL_MATRIX, friction report, and harness runtime guides so users can move from marketing surface → install path → validation reality without confusion.
- [ ] [INSTALL_CLAIM_DISCIPLINE] Audit all public claims in README/docs/site about install ease, harness support, and local-only operation. Every claim must map to a tested path or be downgraded in wording.
- [ ] [INSTALL_DOCS_PRUNE] _(Blocked: prerequisite tasks INSTALL_MD_TIGHTENING, INSTALL_MATRIX_PROMOTION, etc. not done yet)_ Remove or archive redundant install-related content once the new stack is in place. Goal: fewer docs, clearer roles, lower drift.
- [ ] [RELEASE_VALIDATION_SUMMARY_DOC] Add a single `docs/validation/RELEASE_VALIDATION_SUMMARY.md` summarizing what was tested, what passed, what partially passed, and what can be claimed publicly at the current release.

---

## P2 — When Idle

### Deep Cognition (Phase 4-5 gaps)
- [ ] [COGNITION_GATE_PROMOTION] Gate promotion of self-improvements — require benchmark delta before accepting code changes.
- [ ] [COGNITION_CONCEPTUAL_FRAMEWORK] Knowledge synthesis beyond keyword matching — conceptual framework building.

### Calibration / Brier Score (weakest metric — all-time Brier=0.1148 vs target 0.1, 7-day=0.2400)
- [ ] [BRIER_7D_REGRESSION_DIAGNOSIS] Diagnose why 7-day Brier (0.2400) is 2x worse than all-time (0.1148). Analyze `data/calibration/predictions.jsonl` for recent mispredictions — identify which task types or confidence bands are miscalibrated. Fix the confidence estimator or recalibration logic.
- [ ] [CALIBRATION_CONFIDENCE_BAND_AUDIT] Audit confidence bands in heartbeat preflight — current threshold (0.825) may be too coarse. Implement per-domain confidence adjustments based on historical accuracy by task type (research vs code vs maintenance).
- [ ] [CALIBRATION_BAND_GRANULARITY] _(Updated 2026-04-10: actual distribution is 0.78-0.91 across 10 distinct values, not "only 0.8 and 0.9" — recalibration is working. Real gap: no values below 0.78 even for novel tasks. Merge with CALIBRATION_LOW_CONFIDENCE_EXPRESSION.)_ Add low-confidence expression (0.65-0.75) for novel/exploratory tasks. Update `heartbeat_preflight.py` and `clarvis/cognition/confidence.py`.
- [x] [CALIBRATION_LOW_CONFIDENCE_EXPRESSION] _(2026-04-12)_ Done — see P0. `task_aware_confidence()` in spine, wired into preflight.
- [ ] [REASONING_CHAIN_DEPTH_ENFORCEMENT] Reasoning chains capability is weakest at 0.80. Audit `clarvis/cognition/reasoning.py` and `reasoning_chains.py` for single-step chains — enforce minimum 3-step reasoning for P0/P1 tasks. Add a post-chain quality gate that rejects chains with fewer than 2 meaningful steps and logs the rejection reason.
- [ ] [CRON_BRIER_CALIBRATION_REPORT] Non-Python: add a weekly cron entry (Sun ~06:45) that runs a shell script computing Brier score (7-day and all-time), confidence band distribution, and failure-rate-by-type — writes a one-page calibration report to `memory/cron/calibration_report.md`. Wire into digest so the conscious layer sees calibration drift early.

### CLR Autonomy Dimension (critically low: 0.025)

### Adaptive RAG Pipeline
- [ ] [RAG_PHASE1_GATE] Implement GATE phase of adaptive RAG — query classification before retrieval. Design: `docs/ADAPTIVE_RAG_PLAN.md`.

### Cron Schedule Hygiene (non-Python)

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (currently 0.35, target 0.70)

### Cron / Non-Python (2026-04-09 evolution)

---

## Partial Items (tracked, not actively worked)

### External Challenges

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
