#!/bin/bash
# Graph verification — daily SQLite integrity check.
# Post-cutover (2026-03-29): SQLite is the sole runtime backend.
# Runs integrity check + stats. Exits nonzero on FAIL.
#
# Schedule: after graph_compaction (04:30), e.g. 04:45 UTC

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/graph_verify.log"

# Only run when sqlite backend is active
if [ "${CLARVIS_GRAPH_BACKEND:-sqlite}" != "sqlite" ]; then
    exit 0
fi

# Arm script-level timeout (300s = 5 min) — kills script and releases locks on hang
set_script_timeout 300 "$LOGFILE"

# Acquire maintenance lock (mutual exclusion with checkpoint/compaction/vacuum)
acquire_maintenance_lock "$LOGFILE"

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === Graph verify started ===" >> "$LOGFILE"
echo "[$TS] Backend: sqlite (post-cutover)" >> "$LOGFILE"
echo "[$TS] SQLite DB: $(ls -lh data/clarvisdb/graph.db 2>/dev/null || echo 'NOT FOUND')" >> "$LOGFILE"

OUTPUT=$(python3 - 2>&1 <<'PY'
import sys
from clarvis.brain.graph_store_sqlite import GraphStoreSQLite
import os
store = GraphStoreSQLite(os.path.join(os.environ["CLARVIS_WORKSPACE"], "data/clarvisdb/graph.db"))
ok = store.integrity_check()
stats = store.stats()
store.close()
print(f"integrity_ok={ok}, nodes={stats.get('nodes')}, edges={stats.get('edges')}")
for t, c in sorted(stats.get("edge_types", {}).items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")
sys.exit(0 if ok else 1)
PY
)
EXIT_CODE=$?

echo "$OUTPUT" >> "$LOGFILE"

if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] FAIL: verify exited $EXIT_CODE" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Graph verify finished (FAIL) ===" >> "$LOGFILE"
    exit 1
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Graph verify finished (PASS) ===" >> "$LOGFILE"
