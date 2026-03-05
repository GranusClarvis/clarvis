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
cd /home/agent/.openclaw/workspace

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
s = GraphStoreSQLite('/home/agent/.openclaw/workspace/data/clarvisdb/graph.db')
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
