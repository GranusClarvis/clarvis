# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint (2026-04-13)


### Today's Priorities (2026-04-13)

## P1 — This Week

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
