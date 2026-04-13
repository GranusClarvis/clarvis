# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint (2026-04-12)


## P1 — This Week

### Strategic Audit Structural Fixes (2026-04-11 audit)

### Fresh-Install / Isolation Validation

### Install Docs / Support Surface Consolidation (2026-04-07) — DEPRIORITIZED by audit 2026-04-11, move to P2 when reasoning work is complete
- [ ] [RUNTIME_AUDIT_FINDINGS_REVIEW] Convert the latest full Claude runtime audit into a detailed review doc with evidence for each finding: what is working, what is partially wired, what silently degrades, and what remains ambiguous. Include exact file paths, current behavior, confidence level, and whether the issue is architectural, operational, or merely cosmetic.
- [ ] [RUNTIME_HARDENING_PLAN] Produce a proper remediation plan from the runtime audit findings: group issues by severity, define desired end-state, list exact code/docs/cron changes required, identify validation steps, and specify how to prove Clarvis is in a genuinely stable state after fixes.
- [ ] [HEARTBEAT_GATE_WIRING_IN_AUTONOMOUS] Wire the heartbeat gate logic into `scripts/cron/cron_autonomous.sh` where it makes sense so expensive autonomous cycles can defer early when nothing meaningful changed. Preserve correctness; optimize for cost without suppressing real work.
- [ ] [CLAUDE_MD_PATH_DRIFT_CLEANUP] Audit and fix stale script/path references in `CLAUDE.md` and any adjacent operator docs after the script reorganization into subdirs. Remove misleading paths so spawn/runtime instructions match reality.
- [ ] [SIDECAR_PRUNING_SCHEDULE] Review sidecar growth and wire `prune_sidecar()` or equivalent maintenance into an actual scheduled path with sane thresholds, observability, and rollback safety. Goal: sidecar maintenance should be real, not theoretical.
- [ ] [ACP_PROCESS_BASELINE_AUDIT] Audit the long-lived `claude-agent-acp` processes and establish a baseline: which are intentional persistent workers, expected RAM footprint, restart conditions, and leak-detection thresholds. Document how to distinguish healthy persistence from runaway residue.
- [ ] [REASONING_CHAIN_DEPTH_REMEDIATION] The runtime audit says reasoning chains are technically working but shallow (only a tiny fraction reach 4+ meaningful steps). Design and implement a proper fix: define depth targets by task class, strengthen chain-quality gates, and verify measurable improvement without fake verbosity.
- [ ] [PERFECT_STATE_ACCEPTANCE_CRITERIA] Define what "Clarvis in a perfect state" means operationally: cron health, queue flow, pre/postflight integrity, digest freshness, memory integrity, spine feature availability, alert hygiene, and runtime cleanliness. Turn this into a repeatable acceptance checklist + verification script/report.

---

## P2 — When Idle

### Phi Recovery (0.620→0.65 target, added 2026-04-12)
- [ ] [PHI_INTRA_DENSITY_BOOST] **(Phi bottleneck)** Intra-collection density is 0.380 — by far the weakest Phi component. The 3 worst collections: clarvis-learnings (0.283), autonomous-learning (0.286), clarvis-memories (0.319). Write a targeted script that iterates each collection, finds semantically similar memory pairs (cosine >0.6) that lack a graph edge, and adds intra-collection edges. Cap at 500 new edges per collection to avoid bloat. Verify Phi improves after.
- [ ] [PHI_DEDUP_101_CLEANUP] Brain health reports 101 potential duplicates. Near-duplicate memories with slightly different wording dilute intra-collection density (two nodes, no edge, similar embedding). Run `clarvis brain optimize-full` or a targeted dedup pass, then re-measure Phi to confirm density improvement.
- [ ] [BRAIN_STORE_RECALL_FIX] Brain health check reports "store/recall test: unhealthy". Diagnose why the basic store→retrieve round-trip fails. This is a fundamental integrity issue — fix before any Phi optimization work can be trusted.
- [ ] [PHI_WEEKLY_TREND_CRON] **(Non-Python)** Add a weekly cron entry (Sun ~06:10) that runs a shell script: compute Phi, extract per-component scores, compare to last week's values, and write a one-page trend report to `memory/cron/phi_trend_report.md`. Alert to Telegram if Phi drops >0.03 in a week. Wire into digest.

### Deep Cognition (Phase 4-5 gaps)
- [ ] [COGNITION_CONCEPTUAL_FRAMEWORK] Knowledge synthesis beyond keyword matching — conceptual framework building.

### Calibration / Brier Score (weakest metric — all-time Brier=0.1148 vs target 0.1, 7-day=0.2400)
- [ ] [BRIER_7D_REGRESSION_DIAGNOSIS] Diagnose why 7-day Brier (0.2400) is 2x worse than all-time (0.1148). Analyze `data/calibration/predictions.jsonl` for recent mispredictions — identify which task types or confidence bands are miscalibrated. Fix the confidence estimator or recalibration logic.
- [ ] [CALIBRATION_CONFIDENCE_BAND_AUDIT] Audit confidence bands in heartbeat preflight — current threshold (0.825) may be too coarse. Implement per-domain confidence adjustments based on historical accuracy by task type (research vs code vs maintenance).
- [ ] [CALIBRATION_BAND_GRANULARITY] _(Updated 2026-04-10: actual distribution is 0.78-0.91 across 10 distinct values, not "only 0.8 and 0.9" — recalibration is working. Real gap: no values below 0.78 even for novel tasks. Merge with CALIBRATION_LOW_CONFIDENCE_EXPRESSION.)_ Add low-confidence expression (0.65-0.75) for novel/exploratory tasks. Update `heartbeat_preflight.py` and `clarvis/cognition/confidence.py`.
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
