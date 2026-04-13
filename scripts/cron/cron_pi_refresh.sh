#!/bin/bash
# Daily PI refresh — runs quality + episodes + brain_stats + speed benchmarks
# and updates the stored PI metrics. Fast subset (<30s) to prevent staleness
# between full weekly benchmarks (Sun 06:00).
#
# Schedule: 05:45 daily (after maintenance window, before autonomous 06:00)

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/pi_refresh.log"

# Local lock only (no Claude Code, no maintenance lock needed)
acquire_local_lock "/tmp/clarvis_pi_refresh.lock" "$LOGFILE" 120

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === PI refresh started ===" >> "$LOGFILE"

cd "$CLARVIS_WORKSPACE" || exit 1

timeout 60 python3 scripts/metrics/performance_benchmark.py refresh >> "$LOGFILE" 2>&1
EXIT_CODE=$?

# Also record CLR (Clarvis Rating) composite score
timeout 30 python3 -m clarvis metrics clr --record >> "$LOGFILE" 2>&1
CLR_EXIT=$?
if [ $CLR_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CLR refresh failed (exit=$CLR_EXIT)" >> "$LOGFILE"
fi

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TS] PI refresh completed successfully" >> "$LOGFILE"
else
    echo "[$TS] PI refresh failed (exit=$EXIT_CODE)" >> "$LOGFILE"
fi

# --- PI anomaly Telegram alert ---
# Check if performance_benchmark.py logged any PI_ANOMALY records during this refresh.
# Alert file: data/performance_alerts.jsonl (appended by performance_benchmark.py)
ALERTS_FILE="$CLARVIS_WORKSPACE/data/performance_alerts.jsonl"
if [ -f "$ALERTS_FILE" ]; then
    # Only alert on anomalies from the last 5 minutes (this refresh window)
    python3 << 'PYEOF'
import json, os, sys, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

alerts_file = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")) + "/data/performance_alerts.jsonl"
cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
recent = []
try:
    with open(alerts_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") == "PI_ANOMALY" and rec.get("timestamp", "") >= cutoff:
                recent.append(rec)
except Exception as e:
    print(f"[PI-REFRESH] WARN: Failed to read alerts file: {e}", file=sys.stderr)
    sys.exit(0)

if not recent:
    sys.exit(0)

# Build alert message
drops = []
for rec in recent:
    for a in rec.get("anomalies", []):
        drops.append(f"  {a['metric']}: {a['prev']:.3f} → {a['new']:.3f} ({a['drop_pct']}% drop)")
msg = "⚠️ PI Anomaly Alert\n\n" + "\n".join(drops) + "\n\nAnomalous metrics retained at previous values."

# Send via Telegram (same pattern as watchdog)
try:
    token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
    if not token:
        openclaw_home = os.environ.get("OPENCLAW_HOME", os.path.expanduser("~/.openclaw"))
        with open(os.path.join(openclaw_home, "openclaw.json")) as f:
            config = json.load(f)
        token = config["channels"]["telegram"]["botToken"]
    chat_id = os.environ.get("CLARVIS_TG_CHAT_ID", "")
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg})
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data.encode())
    urllib.request.urlopen(req, timeout=10)
    print("PI anomaly alert sent to Telegram")
except Exception as e:
    print(f"PI anomaly alert send failed: {e}", file=sys.stderr)
PYEOF
fi
