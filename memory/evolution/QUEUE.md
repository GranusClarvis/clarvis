# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint

### Evening Code Review Bugs (2026-04-09)

### Strategic Audit Emergency Fixes (2026-04-08 audit)

### Evening Code Review Follow-up (2026-04-07)

### Research Pipeline Simplification / Completion Integrity (2026-04-07)

### LLM Wiki / Obsidian Knowledge Layer (2026-04-07)

## P1 — This Week

### Strategic Audit Structural Fixes (2026-04-08 audit)
- [ ] [LLM_BRAIN_REVIEW 2026-04-09] [LLM_BRAIN_REVIEW] Add temporal indexing or a recency-boosted retrieval path for queries containing time signals ('last 24 hours', 'recently', 'today') — e.g., filter by metadata timestamp before semantic ranking — Temporal queries (Probe 6) consistently return zero relevant results. An agent that cannot recall what it did yesterday has a fundamental operational gap.
- [ ] [DEAD_CODE_PURGE] Delete 40+ dead scripts with no active execution path: evolution/*.py, agents/*.py, tools/*.py (except ast_surgery), hooks/*.py (except canonical_state_refresh, goal_hygiene), cognition/*.py (except dream_engine), metrics/*.py (except performance_benchmark, brief_benchmark). 93% of scripts/ is dead code.
- [ ] [REASONING_CAPABILITY_SPRINT] Dedicate 2+ evolution cycles to reasoning chain improvements, deliberate practice on hard problems, or synthesis loop implementation. Last 20 commits are all infrastructure — zero target reasoning depth or novel cognition. (2026-04-10: 15 new challenges seeded, 5 are reasoning-depth focused, 2 are synthesis — pipeline now primed for reasoning work.)

### Queue Architecture v2 (2026-04-04 audit)

### Runtime Bootstrap / Path Hygiene (2026-04-04 restructure audit)

### Context/Prompt Pipeline

### SWO / Clarvis Brand Integration
- [ ] [LLM_BRAIN_REVIEW 2026-04-08] [LLM_BRAIN_REVIEW] Implement timestamp-weighted retrieval for temporal queries — detect recency intent ('last 24h', 'recently', 'today') and boost results by freshness — Probe 6 is a total miss. Temporal queries are common in agent operation (digest generation, evening reviews) and currently return stale results.
- [ ] [SWO_README_FEATURE_MATRIX] Add a clear feature matrix showing what Clarvis can do today: memory, autonomous execution, research, browser use, messaging, benchmarking, queueing, cron orchestration, cognition/metrics, project agents, and public website/status surfaces.
- [ ] [SWO_README_COMPETITIVE_COMPARISON] Add a restrained comparison section against typical harnesses/agent shells: where Clarvis is stronger (persistent local memory, autonomous background loops, typed metrics, queue/cron integration, inspectability) and where it is intentionally different. No marketing sludge.
- [ ] [SWO_README_VISUALS] Add clean visuals to the README: one architecture diagram, one heartbeat/evolution flow, one memory-system diagram, and one compact capability map. Keep diagrams maintainable and truthful.
- [ ] [SWO_README_PROOF_LINKING] Every major README claim should point to a real surface: CLI command, docs page, benchmark file, website page, or source module. No aspirational claims without evidence.
- [ ] [SWO_WEBSITE_HOME_REDESIGN] Redesign `website/static/index.html` toward the SWO style brief while keeping it readable and technical. Improve hierarchy, section flow, feature framing, and visual polish without making it look like a game splash screen.
- [ ] [SWO_WEBSITE_SECTION_SYSTEM] Create a coherent section system across website pages: hero, capabilities, architecture, benchmarks, repos, roadmap, FAQ/footer. Use consistent cards, spacing, badges, diagrams, and CTA patterns.
- [ ] [SWO_WEBSITE_COMPARISON_SURFACE] Add a tasteful comparison surface on the site (or README) explaining why Clarvis is not just another chat harness. Focus on architecture and operational differences, not chest-beating.
- [ ] [SWO_WEBSITE_VISUAL_POLISH_PASS] Apply the SWO brand tokens already planned in `docs/SWO_CLARVIS_REDESIGN_CONCEPT.md`: palette, typography discipline, cards, badges, and subtle motifs. Keep it premium, not noisy.
- [ ] [SWO_WEBSITE_GRAPHICS_AND_DATA] Add maintainable visuals/graphs for key sections: memory architecture, heartbeat loop, benchmark/performance view, and public status. Prefer generated/static assets that can be updated, not hand-wavy mockups.
- [ ] [SWO_WEBSITE_MOBILE_AND_READABILITY_AUDIT] Audit responsive behavior, contrast, spacing, and content density across pages so the redesign remains legible on mobile and not overdesigned on desktop.
- [ ] [SWO_PUBLIC_DOCS_PRUNE] Audit root `docs/` for internal-only plans, stale execution checklists, one-off audit artifacts, and obsolete strategy notes. Remove, archive, or relocate anything that does not belong in the public repo surface.
- [ ] [SWO_DOCS_INFORMATION_ARCHITECTURE] Split docs into clear buckets: public docs, operator/private docs, historical audits, and internal planning. Public repo should not feel like a dumping ground.
- [ ] [SWO_TRACKED_FILE_EXAMPLE_AUDIT] Audit every `*.example` / `*.template` pair and the corresponding tracked real file. Decide intentionally which real files belong in git (e.g. public templates) versus which should be generated, private, or untracked.
- [ ] [SWO_PRIVATE_FILE_DETRACKING] For files that should not be versioned alongside examples (public-facing repo + local operator variants), de-track them cleanly and replace with canonical examples/templates plus generation/bootstrap instructions.
- [ ] [SWO_REPO_JUNK_SWEEP] Remove obviously non-source junk from the repo surface: caches, stray compiled artifacts like `website/__pycache__/`, dead duplicate docs, and other presentation-eroding clutter.
- [ ] [SWO_PUBLIC_REPO_SURFACE_AUDIT] Perform one final repo-surface pass: top-level tree, README, docs, website, examples, templates, generated assets, and historical plans. Output a short punch-list of what still makes the repo feel amateur or confusing.

### Fresh-Install / Isolation Validation
- [ ] [E2E_INSTALL_VALIDATION_PLAN] Consolidate existing install-validation artifacts (`docs/INSTALL_MATRIX.md`, `docs/INSTALL_FRICTION_REPORT.md`, `docs/HERMES_FRESH_INSTALL_REPORT.md`) into one execution plan for full end-to-end release validation. Define exact environments, pass/fail gates, and which features are mandatory on each harness.
- [ ] [E2E_OPENCLOW_FRESH_ISOLATED] Run a truly fresh isolated OpenClaw install in `/tmp` or equivalent test root using a non-default port, isolated npm prefix, isolated config, and isolated Python env. Validate onboarding, gateway boot, config creation, local-model path, chat round-trip, clean shutdown, and zero contamination of production Clarvis.
- [ ] [E2E_CLARVIS_ON_OPENCLOW_OVERLAY] Layer Clarvis onto that fresh OpenClaw install exactly as a new user would. Validate install script, verify script, CLI health, brain health, demo flow, queue access, heartbeat gate/preflight, cron minimal install, public status/feed generation, and that the OpenClaw gateway still works after overlay.
- [ ] [E2E_HERMES_FRESH_ISOLATED] Run a truly fresh isolated Hermes install in `/tmp` or equivalent, with isolated venv/config/session dirs. Validate install, main entry points, config bootstrap, session persistence, basic chat loop, local-model path, and identify the exact supported invocation path (`hermes` vs `run_agent.py`) without hand-wavy workarounds.
- [ ] [E2E_CLARVIS_ON_HERMES_OVERLAY] Define and test the real Clarvis-on-Hermes integration path, not just repo coexistence. Verify what actually works: install/bootstrap, persona/system-prompt integration, memory/brain access, CLI/tooling usage, and any harness-specific wrappers needed for a usable operator experience.
- [ ] [E2E_FEATURE_MATRIX_BY_HARNESS] Produce a harness-by-feature matrix for OpenClaw and Hermes: install, chat, memory, brain search, queue, heartbeat, cron autonomy, browser flows, messaging, local-model-only mode, install doctor, public status, and website/public feed generation. Mark each as PASS / PARTIAL / FAIL with evidence.
- [ ] [E2E_LOCAL_MODEL_ONLY_VALIDATION] Verify the zero-API-key path end to end on both supported harnesses where applicable. Explicitly test what works with only local models and what degrades gracefully. No marketing claims about “local-first” without this proof.
- [ ] [E2E_ISOLATION_GUARDS] Add hard safety guards to all fresh-install tests so they cannot touch production ports, crontab, workspace, gateway, or auth files. Test harness validation is worthless if it can silently borrow the real environment.
- [ ] [E2E_FIRST_RUN_UX_AUDIT] Audit the first-run experience as if you were a stranger: missing prompts, hidden flags, port assumptions, auth gotchas, model-selection confusion, interactive-only steps, and any point where a human has to “just know” something undocumented.
- [ ] [E2E_INSTALL_DOCTOR] Create or strengthen a post-install doctor command/report that gives PASS/WARN/FAIL across harness boot, model connectivity, brain deps, cron readiness, file paths, and feature availability. This should be the canonical “is this install actually good?” command.
- [ ] [E2E_RELEASE_GATE_OPENCLOW] Add a release gate for OpenClaw support: no public claim of “works on fresh OpenClaw” unless the isolated end-to-end suite passes with saved artifacts/logs.
- [ ] [E2E_RELEASE_GATE_HERMES] Add a release gate for Hermes support: no public claim of “works on Hermes” unless the isolated end-to-end suite passes with saved artifacts/logs and a documented supported path.
- [ ] [E2E_TEST_ARTIFACTS_AND_REPORTS] Standardize test artifacts: logs, configs, screenshots if needed, pass/fail summaries, timing, and exact commands run. Store them in a predictable location so future regressions are comparable.
- [ ] [E2E_KNOWN_LIMITATIONS_DOC] After running the full validation, write one brutally honest support matrix: what is fully supported, what is partial, what is experimental, and what is explicitly unsupported. Open source should promise only what we can reproduce.
- [ ] [E2E_INSTALL_REGRESSION_SUITE] Package the core fresh-install validations into repeatable scripts/tests that can be rerun before release and after major installer/harness changes. The goal is not one heroic manual run, but a durable regression suite.

### Install Docs / Support Surface Consolidation (2026-04-07)
- [ ] [INSTALL_DOC_STACK_CONSOLIDATION] Define the final install/support doc stack and the role of each file: `INSTALL.md` (front door), `INSTALL_MATRIX.md` (validation spec), `INSTALL_FRICTION_REPORT.md` (engineering reality), harness runtime guides, and dated validation reports. Remove overlap by design.
- [ ] [INSTALL_MD_TIGHTENING] Refactor `docs/INSTALL.md` into the single canonical install guide. Keep install profiles, first-run flow, and support-level summary; remove duplicated deep harness caveats that belong elsewhere.
- [ ] [SUPPORT_MATRIX_DOC] Create `docs/SUPPORT_MATRIX.md` with brutally clear support levels for each path: standalone, OpenClaw, Clarvis-on-OpenClaw, Hermes, Clarvis-on-Hermes, local-only, and Docker. Use `SUPPORTED / PARTIAL / EXPERIMENTAL / UNSUPPORTED` with evidence links.
- [ ] [INSTALL_MATRIX_PROMOTION] Promote `docs/INSTALL_MATRIX.md` as the source of truth for validation criteria. Make sure README/install docs link to it whenever claims are made about harness support or fresh-install readiness.
- [ ] [FRICTION_REPORT_SCOPE_CLEANUP] Keep `docs/INSTALL_FRICTION_REPORT.md`, but tighten it into a rolling engineering blocker report: what broke, why, workaround, fix owner, and release impact. It should not try to be a user guide.
- [ ] [VALIDATION_REPORTS_FOLDER] Create a dedicated `docs/validation/` area (or equivalent) for dated install/e2e evidence. Move one-off reports like `HERMES_FRESH_INSTALL_REPORT.md` out of the main public docs root.
- [ ] [HERMES_REPORT_RELOCATION] Re-home `docs/HERMES_FRESH_INSTALL_REPORT.md` into the validation/reports area with a dated filename and short index note. Keep the evidence, reduce root-doc clutter.
- [ ] [OPENCLAW_RUNTIME_GUIDE_SCOPE] Refocus `docs/USER_GUIDE_OPENCLAW.md` into a runtime/operator guide only: usage, autonomy, commands, troubleshooting, and runtime expectations. Strip install duplication.
- [ ] [HERMES_RUNTIME_GUIDE_SCOPE] Refocus `docs/USER_GUIDE_HERMES.md` into a runtime/operator guide only, and add a prominent support-status banner at the top if Hermes remains partial/experimental.
- [ ] [INSTALL_DOC_CROSS_LINKING] Add intentional cross-links between README, INSTALL, SUPPORT_MATRIX, INSTALL_MATRIX, friction report, and harness runtime guides so users can move from marketing surface → install path → validation reality without confusion.
- [ ] [INSTALL_CLAIM_DISCIPLINE] Audit all public claims in README/docs/site about install ease, harness support, and local-only operation. Every claim must map to a tested path or be downgraded in wording.
- [ ] [INSTALL_DOCS_PRUNE] Remove or archive redundant install-related content once the new stack is in place. Goal: fewer docs, clearer roles, lower drift.
- [ ] [RELEASE_VALIDATION_SUMMARY_DOC] Add a single `docs/validation/RELEASE_VALIDATION_SUMMARY.md` summarizing what was tested, what passed, what partially passed, and what can be claimed publicly at the current release.

### Guided Installer / Onboarding UX

### User-Facing Clarvis Docs / Help Surface

### Spine Migration (continued)

### Execution Reliability

### Open-Source Release

---

## P2 — When Idle

### Spine Migration (low priority)

### Benchmarking

### Agent Orchestrator

### Deep Cognition (Phase 4-5 gaps)
- [ ] [COGNITION_GATE_PROMOTION] Gate promotion of self-improvements — require benchmark delta before accepting code changes.
- [ ] [COGNITION_CONCEPTUAL_FRAMEWORK] Knowledge synthesis beyond keyword matching — conceptual framework building.

### Calibration / Brier Score (weakest metric — all-time Brier=0.1148 vs target 0.1, 7-day=0.2400)
- [ ] [BRIER_7D_REGRESSION_DIAGNOSIS] Diagnose why 7-day Brier (0.2400) is 2x worse than all-time (0.1148). Analyze `data/calibration/predictions.jsonl` for recent mispredictions — identify which task types or confidence bands are miscalibrated. Fix the confidence estimator or recalibration logic.
- [ ] [CALIBRATION_CONFIDENCE_BAND_AUDIT] Audit confidence bands in heartbeat preflight — current threshold (0.825) may be too coarse. Implement per-domain confidence adjustments based on historical accuracy by task type (research vs code vs maintenance).
- [ ] [CALIBRATION_BAND_GRANULARITY] Only 2 confidence bands are used system-wide (0.8 and 0.9). Add at least 0.7 and 0.85 bands so the system can express genuine uncertainty instead of rounding everything to one of two values. Update `heartbeat_preflight.py` and `clarvis_confidence.py`.
- [ ] [CALIBRATION_FEEDBACK_CLOSE_LOOP] Ensure prediction outcomes are written back to `predictions.jsonl` with `resolved: true` field — current records lack this field, making it harder for downstream tools to distinguish resolved from pending. Standardize the schema.
- [ ] [CALIBRATION_OVERCONFIDENCE_PENALTY] The system predicts 0.88 avg confidence but fails 12.2% of the time — each failure costs (0.88)^2=0.77 in Brier penalty. Add a failure-pattern detector to `clarvis_confidence.py` that lowers confidence for task types with >10% historical failure rate (currently: all types use uniform ~0.88). Use rolling 30-day accuracy by task_type to set per-type base confidence.
- [ ] [CALIBRATION_LOW_CONFIDENCE_EXPRESSION] The system never emits confidence below 0.8, even for novel or ambiguous tasks. Add explicit low-confidence paths in `heartbeat_preflight.py`: if task has no prior episodes, no matching procedures, or is tagged as exploratory/research, set confidence to 0.65-0.75 instead of the default 0.88.
- [ ] [REASONING_CHAIN_DEPTH_ENFORCEMENT] Reasoning chains capability is weakest at 0.80. Audit `clarvis/cognition/reasoning.py` and `reasoning_chains.py` for single-step chains — enforce minimum 3-step reasoning for P0/P1 tasks. Add a post-chain quality gate that rejects chains with fewer than 2 meaningful steps and logs the rejection reason.
- [ ] [CRON_BRIER_CALIBRATION_REPORT] Non-Python: add a weekly cron entry (Sun ~06:45) that runs a shell script computing Brier score (7-day and all-time), confidence band distribution, and failure-rate-by-type — writes a one-page calibration report to `memory/cron/calibration_report.md`. Wire into digest so the conscious layer sees calibration drift early.

### CLR Autonomy Dimension (critically low: 0.025)
- [ ] [CLR_AUTONOMY_DIGEST_FRESHNESS] CLR autonomy score is 0.025 because digest age=23.4h. Ensure `cron_report_*.sh` and `digest_writer.py` reliably update `memory/cron/digest.md` — add staleness alert to watchdog if digest is >6h old.

### Adaptive RAG Pipeline
- [ ] [RAG_PHASE1_GATE] Implement GATE phase of adaptive RAG — query classification before retrieval. Design: `docs/ADAPTIVE_RAG_PLAN.md`.

### Cron Schedule Hygiene (non-Python)
- [ ] [CRON_SCHEDULE_DRIFT_AUDIT] Non-code: diff system crontab against CLAUDE.md schedule table. Fix any drift (missing jobs, wrong times, stale entries). Verify all 30+ entries match documented schedule.

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)
- [ ] [FIX_BENCHMARK_EPISODE_MEASUREMENT] The episode_success_rate in performance_metrics.json reads 0.0 but live measurement returns 0.943 (347/368). The 05:45 PI refresh on 2026-04-09 recorded 0.0 — likely EpisodicMemory init failed during that run (episodes.json was truncated/corrupted). Re-run `performance_benchmark.py record` to fix the stored metric. Add a guard in `benchmark_episodes()` that logs a warning and falls back to direct JSON parse if EpisodicMemory throws, rather than returning 0.0 which tanks PI by 15 weight points.
- [ ] [EPISODE_CORRUPTION_RESILIENCE] Add a pre-check to `clarvis/memory/episodic_memory.py` init that validates episodes.json is parseable JSON before loading. If corrupt: rename to `.corrupt.bak`, log a warning, and start fresh. Postflight will repopulate. This prevents cascade failures in benchmark, CLR, self_model, and quality metrics that all read episodes.
- [ ] [PI_REFRESH_STALENESS_GUARD] The cron_pi_refresh (05:45) wrote episode_success_rate=0.0 and action_accuracy=0.0 to performance_metrics.json, tanking PI from 0.999 to 0.701 in one run. Add a staleness/sanity guard: if a core metric (episode_success_rate, retrieval_hit_rate, phi) drops by >50% from previous measurement, log a `PI_ANOMALY` warning and retain the previous value with a `stale: true` flag rather than silently recording the collapse.

### Task Quality Score (currently 0.35, target 0.70)
- [ ] [TASK_QUALITY_SCORE_DIAGNOSIS] task_quality_score=0.35 (target 0.70) — diagnose why. Trace the computation path through `quality.py` and `performance_benchmark.py`, identify which sub-components are dragging it down, and fix any measurement bugs or calibration issues similar to the episode_success_rate=0.0 artifact.

### Cron / Non-Python (2026-04-09 evolution)
- [ ] [CRON_PI_ANOMALY_ALERT] Non-Python: add a shell check to `cron_pi_refresh.sh` that compares new PI against previous and sends a Telegram alert if PI drops >0.15 in a single refresh. Pattern: `jq '.pi.pi' data/performance_metrics.json`, compare, alert via `curl` to Telegram bot. Prevents silent PI collapses from going unnoticed until the next evolution cycle.

---

## Partial Items (tracked, not actively worked)

### External Challenges

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-09] Implement a regex engine from scratch (Thompson NFA) — Build a regex engine using Thompson's NFA construction: support concatenation, alternation (|), Kleene star (*), plus (+), optional (?), and character classes [a-z]. Convert regex to NFA, simulate NFA

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-04] Build a git-diff semantic analyzer that classifies changes — Create a tool that reads a git diff and classifies each hunk as: bugfix, feature, refactor, test, docs, or config. Use heuristics (file paths, changed line patterns, commit message) — no LLM calls. Te

- [ ] [EXTERNAL_CHALLENGE:bench-code-01] Write a property-based test suite for ClarvisDB graph operations — Use Hypothesis library to generate random graph operations (add_edge, remove_edge, traverse) and verify invariants: no orphan edges after cleanup, bidirectional consistency, cycle detection correctnes

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-05] Implement a bloom filter for fast duplicate detection in brain.store() — Add a Bloom filter as a fast pre-check before the expensive ChromaDB cosine similarity dedup in brain.store(). Tune false positive rate to <1%. Measure: (a) how many expensive dedup calls are avoided,

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-03] Implement incremental TF-IDF for streaming document indexing — Build an incremental TF-IDF index that can add documents one at a time without recomputing the entire corpus. Support search queries returning top-k results. Compare accuracy against sklearn's TfidfVe
- [ ] [EXTERNAL_CHALLENGE:coding-challenge-next] Pick and complete next coding challenge from benchmark suite.

---

## Research Sessions
