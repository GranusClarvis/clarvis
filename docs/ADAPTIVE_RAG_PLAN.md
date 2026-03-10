# Adaptive RAG Architecture Plan for Clarvis

**Date:** 2026-03-09
**Status:** Approved design — ready for queue-driven implementation
**Research basis:** CRAG (Yan 2024), Self-RAG (Asai 2024), Adaptive-RAG (Jeong 2024), CI-Value (arXiv:2509.21359)

---

## Problem Statement

Clarvis currently treats every brain.recall() the same: query → vector search → ACT-R rerank → return top-N. There is no mechanism to:
1. Decide whether retrieval is even needed (wastes ~7.5s on simple tasks)
2. Evaluate whether retrieved results are actually relevant (silent failure)
3. Retry or adjust when retrieval quality is poor (no corrective loop)
4. Learn from outcomes which retrievals actually helped (no RL signal)

The result: context briefs contain noise, complex tasks get shallow single-pass retrieval, and there's no feedback loop from episode outcomes to retrieval parameters.

## Architecture Overview

Four interconnected capabilities, each building on the previous:

```
                    ┌─────────────────────┐
                    │  1. RETRIEVAL GATE   │  "Should I retrieve at all?"
                    │  (query classifier)  │  Simple → skip, Complex → deep
                    └──────────┬──────────┘
                               │ if retrieve=yes
                    ┌──────────▼──────────┐
                    │  2. RETRIEVAL EVAL   │  "Are these results relevant?"
                    │  (CRAG evaluator)    │  CORRECT / AMBIGUOUS / INCORRECT
                    └──────────┬──────────┘
                               │ if INCORRECT → retry
                    ┌──────────▼──────────┐
                    │  3. ADAPTIVE RETRY   │  "Try again smarter"
                    │  (corrective loop)   │  Rewrite query, broaden scope
                    └──────────┬──────────┘
                               │ results used in task
                    ┌──────────▼──────────┐
                    │  4. RL-LITE FEEDBACK │  "Did this help?"
                    │  (outcome learning)  │  Episode outcome → retrieval params
                    └─────────────────────┘
```

---

## Component 1: Retrieval-Needed Gate

**What:** Before calling brain.recall(), classify whether retrieval will help for this task. Inspired by Self-RAG's RET token — but implemented as a heuristic classifier, not a fine-tuned model.

**Why:** ~30-40% of heartbeat tasks are maintenance/cron that don't benefit from brain context (e.g., "Run graph compaction", "Backup verification"). Skipping retrieval for these saves ~7.5s and prevents noise injection.

**Classification (3-tier, heuristic):**
- **NO_RETRIEVAL** — Task is self-contained, procedural, or infrastructure-only
  - Signals: starts with verbs like "Run", "Backup", "Clean", "Verify", "Check"
  - Signals: references specific scripts/files without needing context
  - Signals: maintenance/cron category from task_selector
- **LIGHT_RETRIEVAL** — Task benefits from procedures + recent episodes only
  - Signals: implementation task with clear scope, tagged with specific file refs
  - Query: 2-3 collections (procedures + learnings), top-3 results
- **DEEP_RETRIEVAL** — Task requires broad knowledge synthesis
  - Signals: research, design, multi-file refactor, "analyze", "improve", "plan"
  - Signals: compound questions, abstract goals, cross-cutting concerns
  - Query: all collections, top-10, enable graph expansion + spreading activation

**Where it lives:**
- New function `classify_retrieval_need(task_text, task_category) -> RetrievalTier` in `clarvis/brain/retrieval_gate.py`
- Called from `heartbeat_preflight.py` §8 (brain search section), before brain.recall()
- Result stored in preflight JSON as `retrieval_tier` for postflight tracking

**File:** `clarvis/brain/retrieval_gate.py` (new, ~80 lines)
**Wiring:** `scripts/heartbeat_preflight.py` (modify §8 brain search block)

---

## Component 2: Retrieval Evaluator (CRAG-style)

**What:** After brain.recall() returns results, evaluate whether they're actually relevant to the query. Classify as CORRECT / AMBIGUOUS / INCORRECT using a zero-LLM heuristic scorer.

**Why:** Currently distance < 0.8 is the only quality filter, and it's applied inconsistently (only for procedures). The evaluator catches cases where vector similarity is high but semantic relevance is low (common with short memories, formulaic text, or topic drift).

**Scoring formula (per result):**
```
relevance = 0.50 * semantic_sim          # 1/(1+distance), already computed
          + 0.25 * keyword_overlap       # query tokens ∩ doc tokens / |query tokens|
          + 0.15 * importance            # from metadata
          + 0.10 * recency_boost         # newer memories get slight boost
```

**Classification thresholds (tunable, stored in config):**
```
max_relevance >= 0.55  → CORRECT     (at least one result is solidly relevant)
max_relevance >= 0.35  → AMBIGUOUS   (marginal results, might help)
max_relevance <  0.35  → INCORRECT   (nothing relevant found)
```

**Actions per tier:**
- **CORRECT** → Use results as-is, apply knowledge strip refinement (Component 2b)
- **AMBIGUOUS** → Use best results + tag as low-confidence in context brief
- **INCORRECT** → Trigger adaptive retry (Component 3), or skip context injection entirely

**Knowledge Strip Refinement (sub-component):**
For CORRECT results, decompose each memory into sentences, re-score each sentence against the query, filter out sub-threshold sentences. This removes noise *within* otherwise-relevant memories.

```python
def strip_refine(query: str, memories: list[dict], threshold=0.3) -> list[dict]:
    """Sentence-level filtering within retrieved memories."""
    for mem in memories:
        sentences = split_sentences(mem["document"])
        kept = [s for s in sentences if keyword_overlap(query, s) > threshold
                or semantic_sim_cached(query, s) > 0.4]
        if kept:
            mem["document"] = " ".join(kept)
            mem["_stripped"] = True
    return memories
```

**Where it lives:**
- New module `clarvis/brain/retrieval_eval.py` (~120 lines)
- `evaluate_retrieval(query, results) -> (verdict, scored_results)` — main entry
- `strip_refine(query, memories) -> refined_memories` — knowledge strip filter
- Registered as a recall hook via `clarvis/brain/hooks.py` (new hook type: `_recall_evaluators`)
- OR: called inline from `heartbeat_preflight.py` after brain.recall(), before context assembly

**Wiring preference:** Hook registration is cleaner (keeps brain.recall() generic), but preflight inline is simpler and more visible. **Recommendation: start inline in preflight, promote to hook after validation.**

**Files:**
- `clarvis/brain/retrieval_eval.py` (new, ~120 lines)
- `scripts/heartbeat_preflight.py` (modify §8 brain search to call evaluator)
- `scripts/context_compressor.py` (strip_refine integrates into MMR pipeline)

---

## Component 3: Adaptive Retry (Corrective Loop)

**What:** When the evaluator returns INCORRECT or AMBIGUOUS, automatically retry with modified parameters. Maximum 1 retry per heartbeat (bound cost).

**Retry strategies (applied in order):**
1. **Query rewrite** — Extract keywords from task text using TF-IDF-weighted terms, rebuild a more targeted query
2. **Collection broadening** — If route_query() narrowed to 2-3 collections, expand to all 10
3. **Threshold relaxation** — Lower min_importance from 0.3 → 0.1, increase n from 5 → 10
4. **Graph expansion** — Enable 1-hop neighbor expansion (uses existing graph edges)

**When to stop retrying:**
- After 1 retry, regardless of outcome (prevents latency spiral)
- If retry returns CORRECT, use those results
- If retry returns AMBIGUOUS, use best results with low-confidence tag
- If retry returns INCORRECT again, skip context injection entirely (no context > bad context)

**Where it lives:**
- Same module `clarvis/brain/retrieval_eval.py` — `adaptive_recall(brain, query, tier, max_retries=1) -> (results, verdict, attempts)`
- Wraps `brain.recall()` + `evaluate_retrieval()` in a retry loop
- Called from `heartbeat_preflight.py` instead of raw `brain.recall()`

**Files:**
- `clarvis/brain/retrieval_eval.py` (extend with retry logic, ~60 more lines)
- `scripts/heartbeat_preflight.py` (replace brain.recall() call with adaptive_recall())

---

## Component 4: RL-Lite Feedback Loop

**What:** After each heartbeat, compare the retrieval quality assessment against the actual task outcome. Use this signal to tune retrieval parameters over time.

**Feedback signals:**
1. **Retrieval verdict vs task outcome:** If CORRECT → success, reward is +1. If INCORRECT → success anyway, retrieval was unnecessary (adjust gate). If CORRECT → failure, retrieval may have been misleading (penalize those results).
2. **Context usefulness:** In postflight, check whether the context brief sections were actually referenced in Claude Code's output (simple substring matching).

**What gets tuned:**
- Retrieval gate thresholds (what counts as NO_RETRIEVAL vs DEEP)
- Evaluator confidence thresholds (what counts as CORRECT vs AMBIGUOUS)
- Per-collection retrieval value (some collections consistently produce better results — weight them higher in routing)
- MMR lambda per task category (already planned in CONTEXT_ADAPTIVE_MMR_TUNING)

**Learning mechanism:**
```python
# In postflight, after outcome is known:
def update_retrieval_params(preflight_data, task_status, output_text):
    retrieval_verdict = preflight_data.get("retrieval_verdict")
    retrieval_tier = preflight_data.get("retrieval_tier")

    # Simple EMA update (exponential moving average)
    alpha = 0.1  # learning rate
    reward = 1.0 if task_status == "success" else -0.5

    # Update per-verdict success rate
    stats = load_retrieval_stats()
    key = f"{retrieval_tier}_{retrieval_verdict}"
    old = stats.get(key, {"reward_ema": 0.5, "count": 0})
    old["reward_ema"] = (1 - alpha) * old["reward_ema"] + alpha * reward
    old["count"] += 1
    stats[key] = old
    save_retrieval_stats(stats)

    # Threshold auto-adjustment (monthly, not per-episode)
    # When enough data accumulates, adjust classification thresholds
    if old["count"] % 50 == 0:
        suggest_threshold_update(stats)
```

**Where it lives:**
- New module `clarvis/brain/retrieval_feedback.py` (~100 lines)
- Called from `scripts/heartbeat_postflight.py` as a new postflight stage
- Data stored in `data/retrieval_quality/retrieval_params.json`
- Threshold suggestions written to `data/retrieval_quality/param_suggestions.json` (human-reviewable before applying)

**Files:**
- `clarvis/brain/retrieval_feedback.py` (new, ~100 lines)
- `scripts/heartbeat_postflight.py` (add §X retrieval feedback stage)
- `data/retrieval_quality/retrieval_params.json` (new, runtime config)

---

## Wiring Diagram

```
heartbeat_preflight.py
│
├── §2 Task Selection (unchanged)
│
├── §8 Brain Search (MODIFIED):
│   │
│   ├── 1. classify_retrieval_need(task)     ← NEW (retrieval_gate.py)
│   │      └── NO_RETRIEVAL? → skip brain search entirely
│   │
│   ├── 2. adaptive_recall(brain, query)     ← NEW (retrieval_eval.py)
│   │      ├── brain.recall(query, ...)      ← existing
│   │      ├── evaluate_retrieval(q, results)← NEW
│   │      │      ├── score each result
│   │      │      └── classify CORRECT/AMBIGUOUS/INCORRECT
│   │      ├── if INCORRECT: retry with rewritten query
│   │      └── return (results, verdict, attempts)
│   │
│   └── 3. strip_refine(query, results)      ← NEW (retrieval_eval.py)
│          └── sentence-level filtering within memories
│
├── §9 Context Assembly (MODIFIED):
│   │
│   ├── MMR reranking (existing, unchanged)
│   ├── context_brief generation (existing)
│   └── tag retrieval_verdict + retrieval_tier in preflight JSON  ← NEW
│
└── Output: preflight.json with retrieval metadata


heartbeat_postflight.py
│
├── §existing stages (unchanged)
│
└── §NEW: Retrieval Feedback
    ├── update_retrieval_params(preflight, status, output)  ← NEW
    ├── log context usefulness (section references)          ← NEW
    └── periodic threshold suggestion                        ← NEW
```

---

## File Inventory

| File | Action | What Changes |
|------|--------|-------------|
| `clarvis/brain/retrieval_gate.py` | **CREATE** | RetrievalTier enum, classify_retrieval_need() |
| `clarvis/brain/retrieval_eval.py` | **CREATE** | evaluate_retrieval(), strip_refine(), adaptive_recall() |
| `clarvis/brain/retrieval_feedback.py` | **CREATE** | update_retrieval_params(), context_usefulness_score() |
| `scripts/heartbeat_preflight.py` | **MODIFY** | §8 uses retrieval gate + adaptive recall |
| `scripts/heartbeat_postflight.py` | **MODIFY** | Add retrieval feedback stage |
| `scripts/context_compressor.py` | **MODIFY** | Integrate strip_refine into brief assembly |
| `scripts/retrieval_quality.py` | **MODIFY** | Add verdict tracking to on_recall() events |
| `clarvis/brain/hooks.py` | **MODIFY** (later) | Add evaluator hook type once inline version validated |
| `data/retrieval_quality/retrieval_params.json` | **CREATE** | Runtime-tunable thresholds and per-collection weights |

---

## Implementation Sequence

**Phase A: Gate + Evaluator** (1 session, ~45 min)
- Build retrieval_gate.py + retrieval_eval.py
- Wire into heartbeat_preflight.py
- Add basic tests
- Validate: run preflight dry-run on 5 sample tasks, check classifications

**Phase B: Strip Refinement + Retry** (1 session, ~30 min)
- Add strip_refine() to retrieval_eval.py
- Add adaptive_recall() retry wrapper
- Wire strip_refine into context_compressor.py brief assembly
- Validate: compare brief sizes before/after on sample tasks

**Phase C: RL-Lite Feedback** (1 session, ~30 min)
- Build retrieval_feedback.py
- Wire into heartbeat_postflight.py
- Initialize retrieval_params.json with current defaults
- Validate: run one full heartbeat cycle, check feedback recording

**Phase D: Tuning + Monitoring** (ongoing, autonomous)
- Retrieval quality dashboard metric: verdict distribution
- Monthly parameter suggestion review
- Threshold auto-tuning with human-reviewable suggestions

---

## Design Decisions

1. **No LLM in the loop** — All evaluation is heuristic (keyword overlap + distance + importance + recency). Zero additional API cost. This is critical for a system that runs 12x/day.

2. **Hook vs inline** — Start inline in preflight for visibility and debuggability. Promote to hook after 1 week of stable operation. The hook registry already supports this pattern.

3. **Max 1 retry** — Corrective loop is bounded to prevent latency spiral. Better to skip context than retry indefinitely.

4. **Threshold suggestions, not auto-apply** — RL-lite generates suggestions that accumulate in a JSON file. Human reviews before applying. This prevents runaway drift.

5. **Modules in clarvis/brain/** — These belong in the brain spine, not scripts/. They're retrieval-layer logic, not orchestration. This aligns with the spine migration direction.

6. **Builds on existing infrastructure** — Uses existing hooks.py registry, retrieval_quality.py event tracking, context_compressor.py MMR pipeline, and preflight/postflight lifecycle. No new frameworks.

---

## Success Metrics

| Metric | Current | Target | How Measured |
|--------|---------|--------|-------------|
| Context Relevance | 0.838 | 0.90 | brief_v2_report.json + episode feedback |
| Retrieval CORRECT rate | unknown | >70% | retrieval_eval verdict distribution |
| Retrieval INCORRECT rate | unknown | <15% | retrieval_eval verdict distribution |
| Preflight latency (no-retrieval tasks) | ~7.5s | <1s | preflight timings |
| Context noise (irrelevant sections) | estimated 30%+ | <15% | strip_refine filtering ratio |
| Semantic retrieval hit rate | 74% | >80% | retrieval_quality.py report |
