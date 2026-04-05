#!/bin/bash
# DB VACUUM — 05:00 UTC daily
# Reclaims space from daily prune/consolidate fragmentation.
# Targets: ChromaDB (chroma.sqlite3) + Synaptic memory (synapses.db)
# VACUUM requires exclusive lock; runs after graph compaction (04:30) completes.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lock_helper.sh"

DB_PATH="$CLARVIS_WORKSPACE/data/clarvisdb/chroma.sqlite3"
SYNAPTIC_DB="$CLARVIS_WORKSPACE/data/synaptic/synapses.db"
LOGFILE="$CLARVIS_WORKSPACE/memory/cron/chromadb_vacuum.log"

# Arm script-level timeout (600s = 10 min) — kills script and releases locks on hang
set_script_timeout 600 "$LOGFILE"

# Acquire locks: local + maintenance
acquire_local_lock "/tmp/clarvis_chromadb_vacuum.lock" "$LOGFILE" 1800
acquire_maintenance_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === ChromaDB VACUUM started ===" >> "$LOGFILE"

# Check database exists
if [ ! -f "$DB_PATH" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ERROR: Database not found: $DB_PATH" >> "$LOGFILE"
    exit 1
fi

# Record pre-vacuum stats
SIZE_BEFORE=$(stat -c%s "$DB_PATH" 2>/dev/null || echo 0)
FREE_PAGES=$(sqlite3 "$DB_PATH" "PRAGMA freelist_count;" 2>/dev/null || echo "?")
TOTAL_PAGES=$(sqlite3 "$DB_PATH" "PRAGMA page_count;" 2>/dev/null || echo "?")
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Pre-VACUUM: size=${SIZE_BEFORE} bytes, free_pages=${FREE_PAGES}/${TOTAL_PAGES}" >> "$LOGFILE"

# Run VACUUM with a timeout (should take <30s for a 30MB db)
timeout 120 sqlite3 "$DB_PATH" "VACUUM;" >> "$LOGFILE" 2>&1
EXIT_CODE=$?

# Record post-vacuum stats
SIZE_AFTER=$(stat -c%s "$DB_PATH" 2>/dev/null || echo 0)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Post-VACUUM: size=${SIZE_AFTER} bytes" >> "$LOGFILE"

if [ $EXIT_CODE -eq 0 ]; then
    SAVED=$(( SIZE_BEFORE - SIZE_AFTER ))
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] OK: Reclaimed ${SAVED} bytes" >> "$LOGFILE"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: VACUUM failed (exit $EXIT_CODE)" >> "$LOGFILE"
fi

# Also run ANALYZE to update query planner statistics
timeout 30 sqlite3 "$DB_PATH" "ANALYZE;" >> "$LOGFILE" 2>&1

# --- Synaptic DB VACUUM ---
if [ -f "$SYNAPTIC_DB" ]; then
    SYN_SIZE_BEFORE=$(stat -c%s "$SYNAPTIC_DB" 2>/dev/null || echo 0)
    SYN_FREE=$(sqlite3 "$SYNAPTIC_DB" "PRAGMA freelist_count;" 2>/dev/null || echo "?")
    SYN_TOTAL=$(sqlite3 "$SYNAPTIC_DB" "PRAGMA page_count;" 2>/dev/null || echo "?")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Synaptic pre-VACUUM: size=${SYN_SIZE_BEFORE} bytes, free_pages=${SYN_FREE}/${SYN_TOTAL}" >> "$LOGFILE"

    timeout 180 sqlite3 "$SYNAPTIC_DB" "VACUUM;" >> "$LOGFILE" 2>&1
    SYN_EXIT=$?

    SYN_SIZE_AFTER=$(stat -c%s "$SYNAPTIC_DB" 2>/dev/null || echo 0)
    if [ $SYN_EXIT -eq 0 ]; then
        SYN_SAVED=$(( SYN_SIZE_BEFORE - SYN_SIZE_AFTER ))
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Synaptic OK: Reclaimed ${SYN_SAVED} bytes" >> "$LOGFILE"
    else
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Synaptic WARN: VACUUM failed (exit $SYN_EXIT)" >> "$LOGFILE"
    fi
    timeout 30 sqlite3 "$SYNAPTIC_DB" "ANALYZE;" >> "$LOGFILE" 2>&1
fi

# --- Hebbian access log rotation (keep last 7 days) ---
ACCESS_LOG="$CLARVIS_WORKSPACE/data/hebbian/access_log.jsonl"
if [ -f "$ACCESS_LOG" ]; then
    LINES_BEFORE=$(wc -l < "$ACCESS_LOG")
    CUTOFF=$(date -u -d "7 days ago" +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%S)
    # Keep lines with timestamps >= 7 days ago (field 1 of JSON has "timestamp")
    python3 -c "
import json, sys
cutoff = '$CUTOFF'
kept = 0
with open('$ACCESS_LOG') as f:
    lines = f.readlines()
recent = []
for line in lines:
    try:
        d = json.loads(line)
        ts = d.get('timestamp', d.get('time', ''))
        if ts >= cutoff:
            recent.append(line)
    except:
        pass
with open('$ACCESS_LOG', 'w') as f:
    f.writelines(recent)
print(f'Kept {len(recent)} of {len(lines)} lines')
" >> "$LOGFILE" 2>&1
    LINES_AFTER=$(wc -l < "$ACCESS_LOG")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Access log rotation: ${LINES_BEFORE} → ${LINES_AFTER} lines" >> "$LOGFILE"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === DB VACUUM finished ===" >> "$LOGFILE"
