#!/bin/bash
# =============================================================================
# Clarvis Restore Drill — Quarterly Backup Validation
# =============================================================================
# Restores the latest backup to a temp directory, verifies ClarvisDB can load,
# runs brain.health_check(), and reports pass/fail.
#
# Usage:
#   ./restore_drill.sh              # Run restore drill against latest backup
#   ./restore_drill.sh --backup <name>  # Test specific backup
#   ./restore_drill.sh --dry-run    # Show what would be tested without restoring
#
# Exit codes:
#   0  — Drill passed (backup is restorable and brain is healthy)
#   1  — Drill failed (restore or health check failed)
#   2  — No backup found / setup error
#
# Scheduled: quarterly via crontab (1st of Jan/Apr/Jul/Oct at 03:00)
# Source: Phase 10 reliability gap — backups verified but never test-restored.
# =============================================================================

set -euo pipefail
export CLARVIS_WORKSPACE="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"

# Source cron env if available (for consistent PATH, etc.)
[ -f "$CLARVIS_WORKSPACE/scripts/cron/cron_env.sh" ] && source "$CLARVIS_WORKSPACE/scripts/cron/cron_env.sh" 2>/dev/null || true

# --- Configuration ---
BACKUP_ROOT="$HOME/.openclaw/backups/daily"
DRILL_LOG="$CLARVIS_WORKSPACE/monitoring/restore_drill.log"
DRILL_HISTORY="$CLARVIS_WORKSPACE/data/metrics/restore_drill_history.jsonl"
TEMP_ROOT=""
DRY_RUN=false
BACKUP_NAME=""

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)   DRY_RUN=true; shift ;;
    --backup)    BACKUP_NAME="$2"; shift 2 ;;
    *)           echo "Unknown arg: $1"; exit 2 ;;
  esac
done

# --- Helpers ---
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$DRILL_LOG"; }
die() { log "FATAL: $*"; exit 2; }

cleanup() {
  if [ -n "$TEMP_ROOT" ] && [ -d "$TEMP_ROOT" ]; then
    log "Cleaning up temp directory: $TEMP_ROOT"
    rm -rf "$TEMP_ROOT"
  fi
}
trap cleanup EXIT

# --- Ensure log directories exist ---
mkdir -p "$(dirname "$DRILL_LOG")" "$(dirname "$DRILL_HISTORY")"

log "=== RESTORE DRILL START ==="

# --- Find backup to test ---
if [ -n "$BACKUP_NAME" ]; then
  BACKUP_DIR="$BACKUP_ROOT/$BACKUP_NAME"
  [ -d "$BACKUP_DIR" ] || die "Backup not found: $BACKUP_DIR"
elif [ -L "$BACKUP_ROOT/latest" ]; then
  BACKUP_DIR="$(readlink -f "$BACKUP_ROOT/latest")"
  [ -d "$BACKUP_DIR" ] || die "Latest backup symlink broken: $BACKUP_ROOT/latest"
else
  die "No backups found in $BACKUP_ROOT"
fi

BACKUP_LABEL="$(basename "$BACKUP_DIR")"
log "Testing backup: $BACKUP_LABEL ($BACKUP_DIR)"

# --- Check backup has ClarvisDB data ---
BACKUP_CHROMA="$BACKUP_DIR/data/clarvisdb"
if [ ! -d "$BACKUP_CHROMA" ]; then
  die "Backup missing ClarvisDB directory: $BACKUP_CHROMA"
fi

BACKUP_SIZE=$(du -sh "$BACKUP_CHROMA" 2>/dev/null | cut -f1)
log "ClarvisDB backup size: $BACKUP_SIZE"

# --- Check for meta.json ---
META_FILE="$BACKUP_DIR/meta.json"
if [ -f "$META_FILE" ]; then
  BACKUP_TYPE=$(python3 -c "import json; print(json.load(open('$META_FILE')).get('type','unknown'))" 2>/dev/null || echo "unknown")
  BACKUP_MEMORIES=$(python3 -c "import json; print(json.load(open('$META_FILE')).get('clarvisdb_memories','?'))" 2>/dev/null || echo "?")
  log "Backup type: $BACKUP_TYPE, memories at backup time: $BACKUP_MEMORIES"
fi

if [ "$DRY_RUN" = true ]; then
  log "DRY RUN — would restore $BACKUP_LABEL to temp dir and run health_check()"
  log "Backup contents:"
  ls -la "$BACKUP_CHROMA"/ 2>/dev/null | head -20
  log "=== DRY RUN COMPLETE ==="
  exit 0
fi

# --- Create temp directory ---
TEMP_ROOT=$(mktemp -d /tmp/clarvis_restore_drill_XXXXXX)
TEMP_WORKSPACE="$TEMP_ROOT/workspace"
TEMP_CLARVISDB="$TEMP_WORKSPACE/data/clarvisdb"
mkdir -p "$TEMP_CLARVISDB"

log "Temp workspace: $TEMP_WORKSPACE"

# --- Build incremental chain for ClarvisDB ---
# Incremental backups only include changed files. To get a complete ClarvisDB,
# we need to layer all backups in the chain (oldest first).
log "Building backup chain..."
CHAIN=()
# Collect all backups from oldest to the target, in chronological order
for dir in $(ls -dt "$BACKUP_ROOT"/2*/ 2>/dev/null | tac); do
  dname=$(basename "$dir")
  target_name=$(basename "$BACKUP_DIR")
  [[ "$dname" > "$target_name" ]] && continue
  [ -d "$dir/data/clarvisdb" ] && CHAIN+=("$dir")
done
log "Backup chain: ${#CHAIN[@]} backup(s) to layer"

# --- Restore ClarvisDB to temp directory ---
log "Restoring ClarvisDB to temp directory..."
RESTORE_START=$(date +%s%N)

# Layer each backup in chronological order (oldest first, newest overwrites)
for chain_dir in "${CHAIN[@]}"; do
  chain_chroma="$chain_dir/data/clarvisdb"
  if [ -d "$chain_chroma" ]; then
    cp -a "$chain_chroma"/. "$TEMP_CLARVISDB"/
  fi
done

RESTORE_END=$(date +%s%N)
RESTORE_MS=$(( (RESTORE_END - RESTORE_START) / 1000000 ))
log "Restore completed in ${RESTORE_MS}ms (${#CHAIN[@]} layers)"

# --- Verify restored files exist ---
RESTORED_SIZE=$(du -sh "$TEMP_CLARVISDB" 2>/dev/null | cut -f1)
log "Restored ClarvisDB size: $RESTORED_SIZE"

if [ ! -f "$TEMP_CLARVISDB/chroma.sqlite3" ]; then
  log "FAIL: chroma.sqlite3 not found in restored data"
  RESULT="FAIL"
  FAIL_REASON="chroma.sqlite3 missing after restore"
else
  log "chroma.sqlite3 present"

  # Check graph.db if it exists in backup
  if [ -f "$BACKUP_CHROMA/graph.db" ]; then
    if [ -f "$TEMP_CLARVISDB/graph.db" ]; then
      log "graph.db present"
    else
      log "WARNING: graph.db missing after restore"
    fi
  fi

  # --- Run brain health check against restored data ---
  log "Running brain.health_check() against restored ClarvisDB..."

  HEALTH_OUTPUT=$(CLARVIS_WORKSPACE="$TEMP_WORKSPACE" python3 -c "
import json, sys, os, time

# Prevent constants.py from creating dirs in the real workspace
os.environ['CLARVIS_WORKSPACE'] = '$TEMP_WORKSPACE'

# Clear any cached singleton clients so we get a fresh one
from clarvis.brain import factory
factory._clients.clear()

# Import after env is set
from clarvis.brain import ClarvisBrain

try:
    t0 = time.monotonic()
    brain = ClarvisBrain()
    init_ms = round((time.monotonic() - t0) * 1000)

    t0 = time.monotonic()
    result = brain.health_check()
    check_ms = round((time.monotonic() - t0) * 1000)

    result['init_ms'] = init_ms
    result['check_ms'] = check_ms

    # Classify issues: orphan edges are warnings (data quality), not
    # restore failures. Critical = anything that blocks store/recall.
    issues = result.get('issues', [])
    critical = [i for i in issues if 'orphan' not in i.lower()]
    warnings = [i for i in issues if 'orphan' in i.lower()]
    result['critical_issues'] = critical
    result['warnings'] = warnings
    # Drill passes if core functionality works (no critical issues)
    result['drill_status'] = 'fail' if critical else 'pass'

    print(json.dumps(result))
except Exception as e:
    print(json.dumps({'status': 'unhealthy', 'drill_status': 'fail', 'error': str(e)}))
    sys.exit(1)
" 2>&1) || true

  log "Health check output: $HEALTH_OUTPUT"

  # Parse result — use drill_status (pass if core store/recall works,
  # even if there are non-critical warnings like orphan edges)
  DRILL_STATUS=$(echo "$HEALTH_OUTPUT" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read().strip().split('\n')[-1])
    print(data.get('drill_status', 'fail'))
except:
    print('parse_error')
" 2>/dev/null || echo "parse_error")

  # Extract metrics for the record
  METRICS=$(echo "$HEALTH_OUTPUT" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read().strip().split('\n')[-1])
    print(f\"memories={data.get('total_memories','?')} collections={data.get('collections','?')} edges={data.get('graph_edges','?')} orphans={data.get('orphan_edges','?')} init={data.get('init_ms','?')}ms check={data.get('check_ms','?')}ms\")
    warns = data.get('warnings', [])
    if warns:
        print(f'Warnings: {warns}')
except:
    print('metrics unavailable')
" 2>/dev/null || echo "metrics unavailable")
  log "Metrics: $METRICS"

  if [ "$DRILL_STATUS" = "pass" ]; then
    RESULT="PASS"
    log "PASS: Brain loads, store/recall works on restored backup"
  else
    RESULT="FAIL"
    FAIL_REASON="health_check critical issues — see output above"
    log "FAIL: Brain health check has critical failures"
  fi
fi

# --- Write drill history record ---
DRILL_RECORD=$(python3 -c "
import json, datetime
record = {
    'timestamp': datetime.datetime.now().isoformat(),
    'backup': '$BACKUP_LABEL',
    'result': '$RESULT',
    'restore_ms': $RESTORE_MS,
    'backup_size': '$BACKUP_SIZE',
    'restored_size': '$RESTORED_SIZE',
}
try:
    data = json.loads('''$HEALTH_OUTPUT'''.strip().split(chr(10))[-1])
    record['health'] = data
except:
    pass
print(json.dumps(record))
" 2>/dev/null || echo '{}')

echo "$DRILL_RECORD" >> "$DRILL_HISTORY"
log "Drill record appended to $DRILL_HISTORY"

# --- Final report ---
log "=== RESTORE DRILL $RESULT ==="
log "Backup tested: $BACKUP_LABEL"
log "Restore time: ${RESTORE_MS}ms"

if [ "$RESULT" = "PASS" ]; then
  log "Backup is restorable and brain is healthy."
  exit 0
else
  log "DRILL FAILED: ${FAIL_REASON:-unknown}"
  exit 1
fi
