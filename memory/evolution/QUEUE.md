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

### Cron Reliability (non-Python)

### Intelligence & Learning Goal (active goal: 58%)
- [x] [LEARNING_STRATEGY_ANALYSIS_CRON] (2026-04-13) Added `learning-strategy` CLI mode to `scripts/cognition/knowledge_synthesis.py` + weekly cron at Sun 05:25. Classifies memories by source (episodes/research/reflection/coding/system), scores quality, writes strategy paragraph to digest.md and stores insight in brain.

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










- [x] [EXTERNAL_CHALLENGE:bench-code-01] (2026-04-13) Property-based test suite: `tests/test_graph_property.py` — 13 Hypothesis tests across 8 test classes verifying: edge dedup, bidirectional consistency, cycle traversal termination, remove consistency, count invariants, orphan detection, bulk integrity, decay correctness. All pass.

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-05] Implement a bloom filter for fast duplicate detection in brain.store() — Add a Bloom filter as a fast pre-check before the expensive ChromaDB cosine similarity dedup in brain.store(). Tune false positive rate to <1%. Measure: (a) how many expensive dedup calls are avoided,

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-03] Implement incremental TF-IDF for streaming document indexing — Build an incremental TF-IDF index that can add documents one at a time without recomputing the entire corpus. Support search queries returning top-k results. Compare accuracy against sklearn's TfidfVe

---

## Research Sessions
