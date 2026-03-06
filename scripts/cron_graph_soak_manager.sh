#!/bin/bash
# Graph soak manager — auto-cutover after N consecutive PASS days.
#
# Policy:
# - During soak: CLARVIS_GRAPH_BACKEND=sqlite and CLARVIS_GRAPH_DUAL_WRITE=1
# - Daily: cron_graph_verify.sh runs and logs PASS/FAIL
# - After N consecutive PASS days: set CLARVIS_GRAPH_DUAL_WRITE=0 (SQLite-only writes)
#   and archive relationships.json.
#
# This does NOT delete JSON; it just stops writing it.

set -euo pipefail

source /home/agent/.openclaw/workspace/scripts/cron_env.sh

WORKDIR="/home/agent/.openclaw/workspace"
LOG="$WORKDIR/memory/cron/graph_soak_manager.log"
VERIFY_LOG="$WORKDIR/memory/cron/graph_verify.log"
STATE_FILE="$WORKDIR/data/graph_soak_state.json"
CRON_ENV="$WORKDIR/scripts/cron_env.sh"
ARCHIVE_DIR="$WORKDIR/data/clarvisdb/archive"

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"

echo "[$TS] === Graph soak manager tick ===" >> "$LOG"

if [ "${CLARVIS_GRAPH_BACKEND:-json}" != "sqlite" ]; then
  echo "[$TS] Backend != sqlite; nothing to do" >> "$LOG"
  exit 0
fi

TARGET_DAYS="${CLARVIS_GRAPH_SOAK_DAYS:-5}"
DUAL_WRITE="${CLARVIS_GRAPH_DUAL_WRITE:-1}"

echo "[$TS] Target days: $TARGET_DAYS, dual_write=$DUAL_WRITE" >> "$LOG"

if [ ! -f "$VERIFY_LOG" ]; then
  echo "[$TS] No verify log yet: $VERIFY_LOG" >> "$LOG"
  exit 0
fi

# Determine last result from verify log
LAST_LINE=$(tac "$VERIFY_LOG" | grep -m1 "=== Graph verify finished" || true)
if echo "$LAST_LINE" | grep -q "(PASS)"; then
  LAST="PASS"
elif echo "$LAST_LINE" | grep -q "(FAIL)"; then
  LAST="FAIL"
else
  LAST="UNKNOWN"
fi

echo "[$TS] Last verify: $LAST" >> "$LOG"

python3 - <<PY >> "$LOG" 2>&1
import json, os, time
state_path = "${STATE_FILE}"
last = "${LAST}"
try:
    state = json.load(open(state_path))
except Exception:
    state = {"consecutive_pass": 0, "last": None, "updated_at": None}

if last == "PASS":
    state["consecutive_pass"] = int(state.get("consecutive_pass", 0)) + 1
elif last == "FAIL":
    state["consecutive_pass"] = 0

state["last"] = last
state["updated_at"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

os.makedirs(os.path.dirname(state_path), exist_ok=True)
with open(state_path, 'w') as f:
    json.dump(state, f, indent=2)
print("state=", state)
PY

CONSEC=$(python3 - <<PY
import json
p='${STATE_FILE}'
try:
  s=json.load(open(p))
  print(s.get('consecutive_pass',0))
except Exception:
  print(0)
PY
)

echo "[$TS] Consecutive PASS days: $CONSEC" >> "$LOG"

# If already cut over to SQLite-only writes, nothing more to do.
if [ "$DUAL_WRITE" = "0" ]; then
  echo "[$TS] Dual-write already disabled; done." >> "$LOG"
  exit 0
fi

if [ "$CONSEC" -lt "$TARGET_DAYS" ]; then
  exit 0
fi

# Cutover: disable dual-write in cron_env.sh
mkdir -p "$ARCHIVE_DIR"
ARCHIVE_PATH="$ARCHIVE_DIR/relationships.pre-sqlite-only.$(date -u +%Y-%m-%dT%H%M%SZ).json"
if [ -f "$WORKDIR/data/clarvisdb/relationships.json" ]; then
  cp "$WORKDIR/data/clarvisdb/relationships.json" "$ARCHIVE_PATH"
  echo "[$TS] Archived JSON to $ARCHIVE_PATH" >> "$LOG"
fi

# Toggle dual-write in cron_env.sh
if grep -q '^export CLARVIS_GRAPH_DUAL_WRITE="1"' "$CRON_ENV"; then
  sed -i 's/^export CLARVIS_GRAPH_DUAL_WRITE="1"/export CLARVIS_GRAPH_DUAL_WRITE="0"/' "$CRON_ENV"
  echo "[$TS] Disabled CLARVIS_GRAPH_DUAL_WRITE in cron_env.sh (SQLite-only writes enabled)" >> "$LOG"
else
  echo "[$TS] WARN: could not find dual-write line to toggle" >> "$LOG"
fi

exit 0
