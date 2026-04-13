# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint (2026-04-13)


### Today's Priorities (2026-04-13)

## P1 — This Week

### Phi Recovery — Intra-Collection Density (weakest Phi sub-component: 0.38)
- [ ] [PHI_INTRA_DENSITY_BOOST] Boost intra-collection density by running targeted auto_link within each collection — identify the 3 collections with lowest internal edge density, then create semantically valid intra-collection edges using pairwise similarity above 0.75 threshold. Measure: intra_collection_density component must rise from 0.38 toward 0.50+. Verify with `python3 -m clarvis brain health`.

### Reasoning Chain Depth (capability score: 0.80, Phase 4.2 gap)

### Conceptual Framework Activation (Phase 4.3 gap — "beyond keyword matching")
- [ ] [CONCEPTUAL_FRAMEWORK_WIRING] Wire `clarvis.cognition.conceptual_framework` into heartbeat preflight context — the module exists but is not called during task execution. Add a conceptual_framework.get_relevant_frameworks(task) call to preflight context assembly so reasoning benefits from cross-domain concept maps. Verify: preflight output includes framework context for at least 1 test task.

### Cron Reliability (non-Python)
- [ ] [CRON_TIMEOUT_AUDIT] (Bash/shell) Audit all cron shell scripts for timeout handling — grep for scripts missing `timeout` wrapping on Claude Code spawns, scripts without lock-file cleanup on SIGTERM, and scripts that silently swallow errors. Produce a checklist of fixes. Target: every spawner script has proper timeout + trap + lock cleanup.

### Intelligence & Learning Goal (active goal: 58%)
- [ ] [LEARNING_STRATEGY_ANALYSIS_CRON] Create a weekly cron entry that runs `knowledge_synthesis.py` with a learning-strategy analysis mode — review what was learned in the past 7 days, identify which learning sources (episodes, research, reflection, coding challenges) produced the highest-quality memories, and write a 1-paragraph strategy adjustment to `memory/cron/digest.md`. Target: learning compounding becomes measurable week-over-week.

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







- [ ] [EXTERNAL_CHALLENGE:coding-challenge-09] Implement a regex engine from scratch (Thompson NFA) — Build a regex engine using Thompson's NFA construction: support concatenation, alternation (|), Kleene star (*), plus (+), optional (?), and character classes [a-z]. Convert regex to NFA, simulate NFA

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-04] Build a git-diff semantic analyzer that classifies changes — Create a tool that reads a git diff and classifies each hunk as: bugfix, feature, refactor, test, docs, or config. Use heuristics (file paths, changed line patterns, commit message) — no LLM calls. Te

- [ ] [EXTERNAL_CHALLENGE:bench-code-01] Write a property-based test suite for ClarvisDB graph operations — Use Hypothesis library to generate random graph operations (add_edge, remove_edge, traverse) and verify invariants: no orphan edges after cleanup, bidirectional consistency, cycle detection correctnes

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-05] Implement a bloom filter for fast duplicate detection in brain.store() — Add a Bloom filter as a fast pre-check before the expensive ChromaDB cosine similarity dedup in brain.store(). Tune false positive rate to <1%. Measure: (a) how many expensive dedup calls are avoided,

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-03] Implement incremental TF-IDF for streaming document indexing — Build an incremental TF-IDF index that can add documents one at a time without recomputing the entire corpus. Support search queries returning top-k results. Compare accuracy against sklearn's TfidfVe
- [ ] [EXTERNAL_CHALLENGE:coding-challenge-next] Pick and complete next coding challenge from benchmark suite.

---

## Research Sessions
