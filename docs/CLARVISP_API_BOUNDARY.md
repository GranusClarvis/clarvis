# ClarvisP API Boundary (v0)

_Status: execution baseline (pre-extraction), source of truth for `clarvis-p` split._

## 1) Purpose

`clarvis-p` is the prompt/context cognition layer:

- how context is assembled
- how budgets are allocated
- how sections are pruned/suppressed
- how retrieval evidence is translated into prompt context

It is intentionally separate from raw memory storage (`clarvis-db`).

Extraction prep package bridge:

- `packages/clarvis-p` (compatibility API wrapper aligned with this boundary)

---

## 2) Public surface (stable-for-v0)

## 2.1 Core context assembly

From `clarvis.context.assembly`:

- `get_adjusted_budgets(tier="standard")`
- `build_decision_context(current_task, tier="standard")`
- `dycp_prune_brief(brief_text, task_text)`
- `generate_tiered_brief(current_task, tier="standard", episodic_hints="", knowledge_hints="", queue_file=None)`

## 2.2 Compression/re-ranking primitives

From `clarvis.context.compressor`:

- `mmr_rerank(results, query_text, lambda_param=..., n=...)`
- `tfidf_extract(text, ratio=...)`
- `compress_text(text, ratio=...)`
- `compress_queue(queue_file=None, max_recent_completed=...)`
- `compress_episodes(episodes, max_items=...)`
- `generate_tiered_brief(...)` (compat wrapper for legacy imports)

## 2.3 Adaptive policy hooks

From `clarvis.context.adaptive_mmr`:

- `classify_mmr_category(task_text)`
- `update_lambdas(days=7)`

---

## 3) Runtime contract with heartbeat pipeline

Current runtime integration points:

- `scripts/heartbeat_preflight.py` consumes tiered briefs
- section suppression input is passed via `suppressed_sections`
- supplementary context blocks are independently gated by relevance history

Expected invariant:

- Context policy changes must be mode-safe and must not corrupt task continuity.

---

## 4) Section suppression gate contract

Section suppression is relevance-history driven and policy-safe:

- low-value sections can be suppressed (e.g. `working_memory`, `metrics`, etc.)
- protected sections remain unsuppressed (`decision_context`, `knowledge`, `reasoning`, `episodes`)
- suppression decisions use context relevance history (not ad-hoc toggles)

This gate exists to reduce semantic noise while preserving critical task-shaping context.

---

## 5) Internal-only surface (not v0 contract)

- script orchestration details in `scripts/context_compressor.py` outside exported functions
- cron scheduling, queue management, autonomous mode selection
- dashboard/public website rendering

---

## 6) Compatibility checks required before extraction

Minimum checks:

1. Tiered brief generation for `minimal/standard/full`.
2. DyCP prune behavior for irrelevant sections.
3. Relevance suppression gate behavior (suppressed vs protected sections).
4. MMR rerank + adaptive lambda update smoke.
5. Preflight integration smoke with `CLARVIS_WORKSPACE=/workspace`.

Shared host compatibility contract runner:

```bash
python3 scripts/compat_contract_check.py
```

---

## 7) Explicit non-goals for `clarvis-p`

- no persistent vector/graph storage ownership
- no task queue ownership
- no cron/agent routing ownership

Those remain in `clarvis-db` (storage) and `clarvis` (orchestration/runtime).
