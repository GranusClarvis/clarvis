# Graph Backend: SQLite Cutover (2026-03-29)

## Summary

On 2026-03-29, the ClarvisDB graph backend was cut over from JSON file storage to SQLite+WAL. SQLite is now the sole runtime backend for all graph operations (node/edge CRUD, traversal, compaction).

## What Changed

- **Before**: `data/clarvisdb/knowledge_graph.json` — loaded into memory on startup, flushed to disk on writes. No ACID, no concurrent-access safety.
- **After**: `data/clarvisdb/knowledge_graph.db` — SQLite with WAL mode, indexed columns (source, target, type), ACID transactions. Busy timeout for concurrent readers/writers.

## Key Files

- `clarvis/brain/graph_store_sqlite.py` — SQLite graph store implementation
- `scripts/infra/graph_cutover.py` — Cutover/rollback tooling
- `scripts/infra/graph_migrate_to_sqlite.py` — One-time migration script

## JSON File Status

The original `knowledge_graph.json` is retained as an archival snapshot. It is **not read or written at runtime**. It may be used for emergency rollback via `graph_cutover.py rollback`.

## Verification

- Graph health: `python3 -m clarvis brain health`
- Graph stats: `python3 -m clarvis brain stats` (reports `graph_nodes` and `graph_edges`)
- Graph integrity: `scripts/cron/cron_graph_verify.sh`
