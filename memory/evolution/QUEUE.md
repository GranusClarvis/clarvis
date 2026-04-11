# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint (2026-04-11)

- [x] [REASONING_CAPABILITY_SPRINT] Deliberate reasoning practice — execute seeded reasoning-depth challenges. (2026-04-11: Implemented Socratic self-questioning layer — socratic_challenge() + step_with_socratic() on ReasoningSession. 8 assumption trigger patterns, evidence gap detection, confidence calibration challenges, logical disconnection detection. Integrated into deliberate_practice(). Executed reasoning-depth-03 formally: quality=GOOD, score=0.953, 6 steps, 100% evidence coverage.)

## P1 — This Week

### Strategic Audit Structural Fixes (2026-04-08 audit)
- [ ] [LLM_BRAIN_REVIEW 2026-04-09] [LLM_BRAIN_REVIEW] Add temporal indexing or a recency-boosted retrieval path for queries containing time signals ('last 24 hours', 'recently', 'today') — e.g., filter by metadata timestamp before semantic ranking — Temporal queries (Probe 6) consistently return zero relevant results. An agent that cannot recall what it did yesterday has a fundamental operational gap.
- [x] [REASONING_CAPABILITY_SPRINT] Dedicate 2+ evolution cycles to reasoning chain improvements, deliberate practice on hard problems, or synthesis loop implementation. (2026-04-11: Socratic self-questioning implemented — this is the first reasoning-depth capability addition. Pipeline now producing GOOD-grade chains.)

### SWO / Clarvis Brand Integration

### Fresh-Install / Isolation Validation
- [ ] [E2E_CLARVIS_ON_OPENCLOW_OVERLAY] Layer Clarvis onto that fresh OpenClaw install exactly as a new user would. Validate install script, verify script, CLI health, brain health, demo flow, queue access, heartbeat gate/preflight, cron minimal install, public status/feed generation, and that the OpenClaw gateway still works after overlay.
- [ ] [E2E_HERMES_FRESH_ISOLATED] Run a truly fresh isolated Hermes install in `/tmp` or equivalent, with isolated venv/config/session dirs. Validate install, main entry points, config bootstrap, session persistence, basic chat loop, local-model path, and identify the exact supported invocation path (`hermes` vs `run_agent.py`) without hand-wavy workarounds.
- [ ] [E2E_FEATURE_MATRIX_BY_HARNESS] Produce a harness-by-feature matrix for OpenClaw and Hermes: install, chat, memory, brain search, queue, heartbeat, cron autonomy, browser flows, messaging, local-model-only mode, install doctor, public status, and website/public feed generation. Mark each as PASS / PARTIAL / FAIL with evidence.
- [x] [E2E_INSTALL_DOCTOR] Create or strengthen a post-install doctor command/report that gives PASS/WARN/FAIL across harness boot, model connectivity, brain deps, cron readiness, file paths, and feature availability. (2026-04-11: Added 2 new check sections — Feature Availability (heartbeat pipeline, reasoning engine, queue, cognitive workspace, context compressor, calibration, PI) and Model Connectivity (OpenRouter API, Telegram bot). Now 48 checks total.)
- [x] [E2E_RELEASE_GATE_OPENCLOW] Add a release gate for OpenClaw support: no public claim of “works on fresh OpenClaw” unless the isolated end-to-end suite passes with saved artifacts/logs. (2026-04-11: Created scripts/infra/release_gate_openclaw.sh — runs doctor + isolated smoke test + OpenClaw-specific checks. Saves artifacts to docs/validation/openclaw_<timestamp>/. PASS verdict on first run.)
- [ ] [E2E_RELEASE_GATE_HERMES] Add a release gate for Hermes support: no public claim of “works on Hermes” unless the isolated end-to-end suite passes with saved artifacts/logs and a documented supported path.
- [ ] [E2E_TEST_ARTIFACTS_AND_REPORTS] Standardize test artifacts: logs, configs, screenshots if needed, pass/fail summaries, timing, and exact commands run. Store them in a predictable location so future regressions are comparable.
- [ ] [E2E_KNOWN_LIMITATIONS_DOC] After running the full validation, write one brutally honest support matrix: what is fully supported, what is partial, what is experimental, and what is explicitly unsupported. Open source should promise only what we can reproduce.
- [ ] [E2E_INSTALL_REGRESSION_SUITE] Package the core fresh-install validations into repeatable scripts/tests that can be rerun before release and after major installer/harness changes. The goal is not one heroic manual run, but a durable regression suite.

### Install Docs / Support Surface Consolidation (2026-04-07)
- [ ] [INSTALL_DOC_STACK_CONSOLIDATION] Define the final install/support doc stack and the role of each file: `INSTALL.md` (front door), `INSTALL_MATRIX.md` (validation spec), `INSTALL_FRICTION_REPORT.md` (engineering reality), harness runtime guides, and dated validation reports. Remove overlap by design.
- [ ] [INSTALL_MD_TIGHTENING] Refactor `docs/INSTALL.md` into the single canonical install guide. Keep install profiles, first-run flow, and support-level summary; remove duplicated deep harness caveats that belong elsewhere.
- [ ] [SUPPORT_MATRIX_DOC] Create `docs/SUPPORT_MATRIX.md` with brutally clear support levels for each path: standalone, OpenClaw, Clarvis-on-OpenClaw, Hermes, Clarvis-on-Hermes, local-only, and Docker. Use `SUPPORTED / PARTIAL / EXPERIMENTAL / UNSUPPORTED` with evidence links.
- [ ] [INSTALL_MATRIX_PROMOTION] Promote `docs/INSTALL_MATRIX.md` as the source of truth for validation criteria. Make sure README/install docs link to it whenever claims are made about harness support or fresh-install readiness.
- [ ] [OPENCLAW_RUNTIME_GUIDE_SCOPE] Refocus `docs/USER_GUIDE_OPENCLAW.md` into a runtime/operator guide only: usage, autonomy, commands, troubleshooting, and runtime expectations. Strip install duplication.
- [ ] [HERMES_RUNTIME_GUIDE_SCOPE] Refocus `docs/USER_GUIDE_HERMES.md` into a runtime/operator guide only, and add a prominent support-status banner at the top if Hermes remains partial/experimental.
- [ ] [INSTALL_DOC_CROSS_LINKING] Add intentional cross-links between README, INSTALL, SUPPORT_MATRIX, INSTALL_MATRIX, friction report, and harness runtime guides so users can move from marketing surface → install path → validation reality without confusion.
- [ ] [INSTALL_CLAIM_DISCIPLINE] Audit all public claims in README/docs/site about install ease, harness support, and local-only operation. Every claim must map to a tested path or be downgraded in wording.
- [ ] [INSTALL_DOCS_PRUNE] Remove or archive redundant install-related content once the new stack is in place. Goal: fewer docs, clearer roles, lower drift.
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
- [ ] [CALIBRATION_LOW_CONFIDENCE_EXPRESSION] The system never emits confidence below 0.8, even for novel or ambiguous tasks. Add explicit low-confidence paths in `heartbeat_preflight.py`: if task has no prior episodes, no matching procedures, or is tagged as exploratory/research, set confidence to 0.65-0.75 instead of the default 0.88.
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
