# Temporal Retrieval Root Cause Analysis & Fix Plan

**Date:** 2026-03-24
**Source:** LLM_BRAIN_REVIEW queue task, ChromaDB cookbook, time-aware RAG research
**Decision:** APPLY

## Problem Statement

Temporal/recency queries (e.g., "what happened recently") return only 1-3 results with poor relevance, despite 64+ recent episodes existing in the brain.

## Root Cause Analysis

### 1. ISO String Timestamps Block DB-Level Filtering
`created_at` is stored as an ISO 8601 string (e.g., `"2026-03-24T07:04:51+00:00"`). ChromaDB's `where` clause comparison operators (`$gt`, `$gte`, `$lt`, `$lte`) only work on **int/float** values. This means **all temporal filtering happens post-query in Python** — after ChromaDB has already returned its top-N by semantic similarity.

### 2. Semantic Mismatch for Temporal Queries
The query "what happened recently" has L2 distances of 1.39-1.50 from episode documents like "Episode: [TASK_NAME] -> success". These are poor matches. Semantic embeddings encode *meaning*, not *time* — recency is orthogonal to embedding distance.

### 3. Post-Query Filtering Decimates Results
Quantified: ChromaDB returns 5 episode results by semantic similarity. **4 of 5 are older than 7 days** and get filtered by the `cutoff_date` check. Only **1 of 64 recent episodes** survives. The filtering happens at `search.py:307-309`.

### 4. No Over-Fetching Compensation
When `since_days` is set, the code still requests only `n` results per collection from ChromaDB. With temporal filtering removing 80%+, the effective yield is `n * 0.2`.

### 5. No Chronological Fallback
For pure temporal queries (high temporal intent, low content signal), the system should fall back to reverse-chronological `col.get()` instead of semantic search. Currently it always does embedding-based search.

## Fix Plan (4 Changes)

### Fix 1: Add `created_epoch` Numeric Metadata (store.py)
```python
# In StoreMixin.store(), add alongside created_at:
metadata["created_epoch"] = int(datetime.now(timezone.utc).timestamp())
```
Then use in queries:
```python
where={"created_epoch": {"$gte": cutoff_epoch}}
```
This pushes temporal filtering to the DB layer. ChromaDB returns only recent results, no post-query loss.

**Backfill:** One-time script to parse existing `created_at` → epoch for all 2244 memories across 10 collections.

### Fix 2: Over-Fetch Multiplier (search.py)
When `since_days` is set, multiply the per-collection `n` by 3x for the ChromaDB query, then trim after filtering:
```python
fetch_n = n * 3 if cutoff_date else n
results = col.query(..., n_results=fetch_n)
```
This is a safety net even after Fix 1 (belt + suspenders).

### Fix 3: Chronological Fallback for Pure Temporal Queries (search.py)
Detect when query has temporal intent but low content signal. In these cases, use `col.get()` ordered by `created_epoch` descending instead of semantic search:
```python
if temporal_intent and content_signal_low:
    # Use metadata-only retrieval, sorted by time
    results = col.get(where={"created_epoch": {"$gte": cutoff_epoch}}, limit=n)
```
Content signal detection: strip temporal keywords from query, check if remaining tokens have meaningful semantic content.

### Fix 4: Increase Default n for Temporal Queries
Temporal queries should default to `n=15` instead of `n=5`, since users asking "what happened" want a timeline, not a single result.

## Implementation Order

1. **Fix 1 (created_epoch)** — highest impact, enables all other fixes. ~M effort.
   - Modify `store.py` to add `created_epoch`
   - Backfill script for existing memories
   - Modify `search.py` to use `where` clause when `since_days` is set
2. **Fix 2 (over-fetch)** — trivial, 5-line change. ~S effort.
3. **Fix 4 (default n)** — trivial. ~S effort.
4. **Fix 3 (chronological fallback)** — moderate, needs content-signal detection. ~M effort.

## Relation to Action Accuracy (Weakest Metric: 0.980)

Temporal retrieval directly impacts action accuracy: if the agent can't recall recent context, it makes decisions based on stale information. Fixing this should improve context quality for heartbeat tasks, which downstream improves action accuracy.

## Sources

- [ChromaDB Time-based Queries Cookbook](https://cookbook.chromadb.dev/strategies/time-based-queries/)
- [ChromaDB Metadata Filtering Docs](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
- [ChromaDB Issue #2688 — created_at WHERE clause](https://github.com/chroma-core/chroma/issues/2688)
- [Ragie Docs — Recency Bias in Retrievals](https://docs.ragie.ai/docs/retrievals-recency-bias)
- [Time-Aware RAG with Temporal Graphs (arXiv:2510.13590)](https://arxiv.org/html/2510.13590v1)
- [Hybrid Search with Temporal Filtering — TimescaleDB](https://www.tigerdata.com/blog/hybrid-search-timescaledb-vector-keyword-temporal-filtering)
