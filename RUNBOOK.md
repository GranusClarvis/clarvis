# Graph Storage Upgrade — SQLite+WAL Runbook

## Overview

ClarvisDB's graph storage supports two backends:
- **JSON** (default): `data/clarvisdb/relationships.json` — legacy, loaded entirely into memory
- **SQLite+WAL**: `data/clarvisdb/graph.db` — indexed, ACID, hot-backup capable

Backend is selected via `CLARVIS_GRAPH_BACKEND` environment variable (`json` or `sqlite`).

## Migration Procedure

### Prerequisites
- No active cron jobs modifying the graph (check: `ls /tmp/clarvis_maintenance.lock`)
- Confirm `relationships.json` is not being written to

### Step 1: Safe Migration

```bash
cd $CLARVIS_WORKSPACE

# Safe mode: snapshots JSON, migrates, verifies parity
python3 scripts/graph_migrate_to_sqlite.py --safe
```

This will:
1. Copy `relationships.json` → `relationships.pre-migration.json` (snapshot)
2. Import all nodes/edges into `graph.db` (bulk insert)
3. Run graph-verify parity check (200-sample edge verification)

Expected output ends with `Result: PASS`.

### Step 2: Verify (optional second check)

```bash
CLARVIS_GRAPH_BACKEND=sqlite python3 -m clarvis brain graph-verify --sample-n 500
```

### Step 2b: Run Invariants Check

```bash
python3 scripts/invariants_check.py
```

Runs pytest, golden-qa retrieval, graph-verify (if sqlite), brain health, and hook registration count. Outputs a JSONL record to `data/invariants_runs.jsonl`. Exit 0 = all PASS.

The safe migration (`--safe`) runs this automatically after Step 3. The cutover tool (`graph_cutover.py`) requires it to pass before proceeding.

### Step 3: Enable Soak

Edit `scripts/cron_env.sh` and uncomment:
```bash
export CLARVIS_GRAPH_BACKEND="sqlite"
```

This activates SQLite for all cron scripts. The daily `cron_graph_verify.sh` will run parity checks automatically.

### Step 4: Monitor Soak

Check daily verification logs:
```bash
tail -20 memory/cron/graph_verify.log
```

Check compaction uses SQLite path:
```bash
tail -30 memory/cron/graph_compaction.log
# Should show "Backend: SQLite"
```

## Rollback Procedure

### Quick Rollback (re-comment env var)
```bash
# In scripts/cron_env.sh, comment out:
# export CLARVIS_GRAPH_BACKEND="sqlite"
```

The JSON backend remains untouched throughout. Dual-write ensures both stores stay in sync.

### Full Rollback (restore pre-migration snapshot)
```bash
cp data/clarvisdb/relationships.pre-migration.json data/clarvisdb/relationships.json
# Comment out CLARVIS_GRAPH_BACKEND in cron_env.sh
```

## Consumer Matrix

| Consumer | JSON path | SQLite path | Backend-aware |
|----------|-----------|-------------|---------------|
| `graph_compaction.py` | Load full JSON, filter in-memory | SQL DELETE/INSERT | Yes |
| `cron_graph_checkpoint.sh` | `cp relationships.json` | SQLite online backup API | Yes |
| `graphrag_communities.py` | `json.load()` | SQL SELECT to dict | Yes |
| `graph_migrate_to_sqlite.py` | Source | Target | N/A |
| `cron_graph_verify.sh` | — | Parity check | sqlite-only |
| `GraphMixin` (brain) | Always loaded | Dual-write when sqlite | Yes |
| `backup_daily.sh` | Backs up JSON | Not yet updated | No (backups JSON regardless) |

## Daily Cron Schedule (graph-related)

| Time (UTC) | Script | Purpose |
|------------|--------|---------|
| 04:00 | `cron_graph_checkpoint.sh` | Backup (JSON cp or SQLite backup API) |
| 04:30 | `cron_graph_compaction.sh` | Orphan removal, dedup, backfill |
| 04:45 | `cron_graph_verify.sh` | Parity check (sqlite only, exits nonzero on FAIL) |
| 05:00 | `chromadb_vacuum` | SQLite VACUUM on ChromaDB |

All graph maintenance jobs share `/tmp/clarvis_maintenance.lock` for mutual exclusion.

### On-Demand: Invariants Check

```bash
python3 scripts/invariants_check.py          # Run all, log to data/invariants_runs.jsonl
python3 scripts/invariants_check.py --json   # Print result, no file write
python3 scripts/invariants_check.py --check pytest  # Single check
```

Checks: pytest, golden-qa, graph-verify (sqlite only), brain-health, hook-count.

## Troubleshooting

### Parity check fails
```bash
# Check what diverged
CLARVIS_GRAPH_BACKEND=sqlite python3 -m clarvis brain graph-verify --sample-n 500
```
Look at `sample_mismatched` in the output. Common causes:
- Edges added to JSON but not dual-written (pre-Phase-2 writes)
- Fix: re-run `python3 scripts/graph_migrate_to_sqlite.py` to re-sync

### SQLite DB corruption
```bash
python3 -c "
from clarvis.brain.graph_store_sqlite import GraphStoreSQLite
s = GraphStoreSQLite('$CLARVIS_WORKSPACE/data/clarvisdb/graph.db')
print('integrity:', s.integrity_check())
print('stats:', s.stats())
"
```
If integrity_check returns False, restore from checkpoint:
```bash
cp data/clarvisdb/graph.checkpoint.db data/clarvisdb/graph.db
```

### Graph.db missing WAL/SHM files
Normal — SQLite creates/removes them automatically. If they persist after clean shutdown, it's safe to delete them.

---

## Phase 4: Cutover (JSON → SQLite)

### Automated Cutover

Use `scripts/graph_cutover.py` for the full cutover sequence:

```bash
# Check current state
python3 scripts/graph_cutover.py --status

# Dry run (see what would happen)
python3 scripts/graph_cutover.py --dry-run

# Execute cutover
python3 scripts/graph_cutover.py

# Rollback (one command)
python3 scripts/graph_cutover.py --rollback
```

The cutover script:
1. Runs invariants check (`invariants_check.py`) — refuses to proceed on FAIL
2. Runs pre-flight checks (SQLite exists, integrity OK, parity OK, no locks)
3. Archives `relationships.json` to `data/clarvisdb/archive/relationships.<timestamp>.json`
4. Enables `CLARVIS_GRAPH_BACKEND="sqlite"` in `cron_env.sh`

**JSON dual-write continues** — `relationships.json` is still written to on every mutation. This preserves rollback safety. The JSON file is archived (copied, not removed).

### Rollback

One command:
```bash
python3 scripts/graph_cutover.py --rollback
```

This re-comments `CLARVIS_GRAPH_BACKEND` in `cron_env.sh`. Since dual-write kept JSON in sync, no data is lost.

If the original JSON was lost, the script restores from the latest archive in `data/clarvisdb/archive/`.

### JSON Write Path Removal Checklist

After a successful soak period (recommended: 7+ days with zero parity failures), the JSON write paths can be removed. This is Phase 4b and should NOT be done until all prerequisites are met:

**Prerequisites:**
- [ ] Soak period: 7+ consecutive days with `cron_graph_verify.sh` passing (exit 0)
- [ ] Zero parity failures in `memory/cron/graph_verify.log`
- [ ] `graph_cutover.py` has been executed (not just dry-run)
- [ ] `backup_daily.sh` updated to back up `graph.db` instead of (or in addition to) `relationships.json`
- [ ] Manual verification: `clarvis brain graph-verify --sample-n 500` passes

**Files to modify for JSON write removal:**
1. `clarvis/brain/graph.py` — `_save_graph()`, `_load_graph()` (JSON load), `add_relationship()` (JSON append), `backfill_graph_nodes()` (JSON write), `bulk_intra_link()` (JSON write), `decay_edges()` (JSON write)
2. `clarvis/brain/graph.py` — `verify_graph_parity()` can be simplified (no JSON comparison)
3. `scripts/graph_compaction.py` — remove `run_compaction_json()` function
4. `scripts/cron_graph_checkpoint.sh` — remove JSON `cp` path
5. `scripts/graphrag_communities.py` — remove JSON load path

**What to keep:**
- `relationships.json` file on disk (read-only archive, 30-day retention)
- `graph_migrate_to_sqlite.py` — useful for recovery/re-import
- `GraphStoreSQLite.export_json()` — can regenerate JSON from SQLite if needed
