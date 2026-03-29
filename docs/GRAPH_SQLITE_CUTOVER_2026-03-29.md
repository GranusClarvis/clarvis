# Graph SQLite Cutover — Finalized 2026-03-29

## Summary

The graph storage backend has been fully cut over from dual-write (JSON + SQLite)
to SQLite-only runtime. JSON is no longer read or written during normal operation.

## What Was Still Live Before This Cleanup

| Component | JSON Usage | Status |
|-----------|-----------|--------|
| `clarvis/brain/graph.py` `_load_graph()` | Always loaded 28MB JSON into memory | **Removed** — now skipped when SQLite active |
| `clarvis/brain/graph.py` `_save_graph()` | Wrote JSON on every edge mutation | **Removed** — no-op when SQLite active |
| `clarvis/brain/graph.py` `add_relationship()` | Dual-wrote JSON + SQLite | **Removed** — SQLite only |
| `clarvis/brain/graph.py` `bulk_intra_link()` | Built edges in self.graph, saved JSON | **Removed** — SQLite batch insert only |
| `clarvis/brain/graph.py` `decay_edges()` | Iterated JSON edges, then also ran SQLite decay | **Removed** — delegates to SQLite store directly |
| `clarvis/brain/graph.py` `backfill_graph_nodes()` | Dual-wrote JSON + SQLite | **Removed** — returns 0 when SQLite active (backfill handled by compaction SQL) |
| `clarvis/brain/graph.py` `prune_high_degree()` | Iterated JSON edges | **Removed** — returns no-op when SQLite active (pruning via compaction) |
| `clarvis/brain/graph.py` `verify_graph_parity()` | Compared JSON vs SQLite (200-sample) | **Replaced** — now runs SQLite integrity check only |
| `scripts/graph_compaction.py` `run_compaction()` | Ran JSON compaction alongside SQLite when dual-write=1 | **Removed** — SQLite compaction only |
| `scripts/cron_graph_verify.sh` | Ran parity check JSON vs SQLite | **Replaced** — SQLite integrity check only |
| `scripts/cron_graph_checkpoint.sh` | Backed up both JSON + SQLite | **Simplified** — SQLite online backup only |
| `scripts/cron_graph_soak_manager.sh` | Tracked soak PASS/FAIL, toggled dual-write | **Stubbed** — logs confirmation, exits |
| `scripts/cron_env.sh` | `CLARVIS_GRAPH_DUAL_WRITE="1"` | **Changed to "0"** |
| `clarvis/brain/constants.py` | `GRAPH_BACKEND` defaulted to "json" | **Changed to "sqlite"** |

## What Remains Intentionally JSON-Based

| File | Purpose | Risk |
|------|---------|------|
| `data/clarvisdb/relationships.json` | Final pre-cutover snapshot (28MB) | None — not read at runtime |
| `data/clarvisdb/archive/relationships.final-pre-cutover.2026-03-29.json` | Archived copy | None |
| `data/clarvisdb/archive/relationships.2026-03-06T055915Z.json` | Historical archive | None |
| `data/clarvisdb/relationships.pre-migration.json` | Pre-migration snapshot | None |
| `data/clarvisdb/relationships.checkpoint.json` | Stale checkpoint (2026-03-06) | None |
| `data/clarvisdb/relationships.json.broken` | Recovered corruption from 2026-03-06 | None |
| `scripts/graph_compaction.py` `run_compaction_json()` | Retained as fallback if SQLite unavailable | No risk — only called when `_sqlite_store is None` |
| `scripts/graphrag_communities.py` `_load_graph()` | Falls back to JSON if SQLite missing | No risk — reads only, SQLite preferred |
| `scripts/lite_brain.py` | Uses `relationships.json` for project agents | Correct — agents have isolated graphs |

## Cleanup Performed

1. **`cron_env.sh`**: Set `CLARVIS_GRAPH_DUAL_WRITE="0"`, updated comments
2. **`clarvis/brain/constants.py`**: Default `GRAPH_BACKEND` changed from `"json"` to `"sqlite"`
3. **`clarvis/brain/graph.py`**: Major refactor:
   - `_load_graph()`: Skips JSON loading when SQLite is active
   - `_save_graph()` / `_force_save_graph()`: No-op when SQLite is active
   - `add_relationship()`: SQLite-first path, JSON fallback only
   - `bulk_cross_link()` / `bulk_intra_link()`: Use `_existing_edge_pairs()` helper to query correct backend
   - `decay_edges()`: Delegates entirely to SQLite store
   - `backfill_graph_nodes()`: Returns 0 when SQLite active
   - `prune_high_degree()`: Returns no-op when SQLite active
   - `verify_graph_parity()`: SQLite integrity check only
4. **`scripts/graph_compaction.py`**: Removed dual-write JSON compaction from `run_compaction()`
5. **`scripts/cron_graph_verify.sh`**: Simplified to SQLite integrity check
6. **`scripts/cron_graph_checkpoint.sh`**: Removed JSON checkpoint path
7. **`scripts/cron_graph_soak_manager.sh`**: Stubbed (logs and exits)
8. **Archived**: `relationships.json` copied to `archive/relationships.final-pre-cutover.2026-03-29.json`
9. **Cleaned up**: 8 orphaned `relationships.json.tmp.*` files (~110MB freed)
10. **Updated**: `data/graph_soak_state.json` to reflect finalized cutover

## Split-Brain Risk

**Eliminated.** Before this cleanup:
- Every edge write went to both JSON (28MB, loaded into memory) and SQLite (63MB)
- JSON was the authoritative source for dedup checks in `bulk_cross_link` / `bulk_intra_link`
- SQLite was the authoritative source for `get_related` reads
- Compaction ran on both stores independently, risking drift

After this cleanup:
- SQLite is the sole runtime store for reads and writes
- JSON file exists on disk but is never opened by runtime code
- No process writes to `relationships.json`
- No risk of divergent state

## Verification

```
Brain initialized OK
SQLite store: True
Graph dict empty (expected): nodes=0, edges=0
Verify: integrity_ok=True, nodes=2859, edges=105983
add_relationship -> SQLite only, JSON untouched
Compaction (dry-run): SQLite-only, 0.6s
JSON file last modified: Sun Mar 29 22:13:19 2026 (before cleanup, not touched)
```

## Operational Changes

- **Soak manager cron** (`05:05`): Now a no-op stub. Safe to remove from crontab.
- **Graph verify cron** (`04:45`): Now runs SQLite integrity check only (faster, no JSON loading).
- **Graph checkpoint cron** (`04:00`): SQLite online backup only (no JSON checkpoint).
- **Compaction cron** (`04:30`): SQLite SQL compaction only (no JSON in-memory compaction).
- **Rollback**: If SQLite is somehow corrupted, restore `graph.checkpoint.db` (updated daily at 04:00).
  For full rollback to JSON, set `CLARVIS_GRAPH_BACKEND=json` in `cron_env.sh` — the JSON file and
  all fallback code paths are preserved.
