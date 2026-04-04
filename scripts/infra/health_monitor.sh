#!/bin/bash
# Clarvis Self-Monitoring System
# Runs every 15 minutes via cron
source $CLARVIS_WORKSPACE/scripts/cron/cron_env.sh

DATE=$(date '+%Y-%m-%d %H:%M:%S')
LOG_DIR="$CLARVIS_WORKSPACE/monitoring"
mkdir -p "$LOG_DIR"

# === DAILY MEMORY FILE BOOTSTRAP (ensure it exists for consumers) ===
python3 $CLARVIS_WORKSPACE/scripts/tools/daily_memory_log.py ensure >/dev/null 2>&1 || true

# === SYSTEM HEALTH ===
MEM_TOTAL=$(free -m | awk '/^Mem:/{print $2}')
MEM_USED=$(free -m | awk '/^Mem:/{print $3}')
MEM_PCT=$((MEM_USED * 100 / MEM_TOTAL))

DISK_USED=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
LOAD=$(uptime | awk -F'load average:' '{print $2}' | cut -d',' -f1 | xargs)

# === PROCESS MONITORING ===
# Check gateway via port (most reliable) and process
if ! ss -tlnp 2>/dev/null | grep -q ":18789 "; then
    echo "[$DATE] [ALERT] Gateway port 18789 not listening!" >> "$LOG_DIR"/alerts.log
    # Attempt auto-recovery via systemd (preferred) or PM2 (fallback)
    systemctl --user start openclaw-gateway.service 2>/dev/null \
        || pm2 start openclaw-gateway 2>/dev/null || true

fi

# Check dashboard (non-critical — log only, no auto-restart)
if ! ss -tlnp 2>/dev/null | grep -q ":18799 "; then
    echo "[$DATE] [INFO] Dashboard port 18799 not listening (service may be stopped)" >> "$LOG_DIR"/alerts.log
fi

# === SECURITY CHECKS ===
# Check for failed SSH attempts
FAILED_SSH=$(grep "Failed password" /var/log/auth.log 2>/dev/null | tail -5 | wc -l)

# Check for unusual processes (exclude self and system)
SUSPICIOUS=$(ps aux | grep -E "nc |netcat |nmap |masscan |hydra" | grep -v grep | wc -l)

# === NETWORK EXPOSURE ===
OPEN_PORTS=$(ss -tuln | awk 'NR>1 {print $1}' | sort -u | wc -l)

# === WALLET BALANCE (hourly, not every 15m — non-essential external API call) ===
USDC_BALANCE=""
WALLET_CACHE="/tmp/clarvis_wallet_cache"
WALLET_STALE=true
if [ -f "$WALLET_CACHE" ]; then
    CACHE_AGE=$(( $(date +%s) - $(stat -c%Y "$WALLET_CACHE" 2>/dev/null || echo 0) ))
    if [ "$CACHE_AGE" -lt 3600 ]; then
        USDC_BALANCE=$(cat "$WALLET_CACHE")
        WALLET_STALE=false
    fi
fi
if [ "$WALLET_STALE" = true ]; then
    WALLET_INFO=$(curl -s --connect-timeout 5 --max-time 10 https://api.mcporter.io/v1/conway/wallet_info 2>/dev/null)
    USDC_BALANCE=$(echo "$WALLET_INFO" | grep -oP '"usdc":\K[0-9]+')
    [ -n "$USDC_BALANCE" ] && echo "$USDC_BALANCE" > "$WALLET_CACHE"
fi

# === LOG STATUS ===
echo "[$DATE] MEM:${MEM_PCT}% DISK:${DISK_USED}% LOAD:$LOAD PORTS:$OPEN_PORTS SSH_FAILS:$FAILED_SSH WALLET:\$$USDC_BALANCE" >> "$LOG_DIR"/health.log

# === ALERTS ===
if [ "${MEM_PCT:-0}" -gt 90 ]; then
    echo "[$DATE] [CRITICAL] Memory usage at ${MEM_PCT}%" >> "$LOG_DIR"/alerts.log

fi

if [ "${DISK_USED:-0}" -gt 90 ]; then
    echo "[$DATE] [CRITICAL] Disk usage at ${DISK_USED}%" >> "$LOG_DIR"/alerts.log

fi

if [ "${SUSPICIOUS:-0}" -gt 0 ]; then
    echo "[$DATE] [WARNING] Suspicious processes detected" >> "$LOG_DIR"/alerts.log
fi

# === BRAIN HYGIENE CHECK (once per hour, not every 15min) ===
BRAIN_CACHE="/tmp/clarvis_brain_check_cache"
BRAIN_STALE=true
if [ -f "$BRAIN_CACHE" ]; then
    BRAIN_AGE=$(( $(date +%s) - $(stat -c%Y "$BRAIN_CACHE" 2>/dev/null || echo 0) ))
    [ "$BRAIN_AGE" -lt 3600 ] && BRAIN_STALE=false
fi
if [ "$BRAIN_STALE" = true ]; then
    python3 $CLARVIS_WORKSPACE/scripts/brain_mem/brain_hygiene.py check >> "$LOG_DIR"/health.log 2>&1 || {
        echo "[$DATE] [WARNING] Brain hygiene check failed or detected regression" >> "$LOG_DIR"/alerts.log
    
    }
    touch "$BRAIN_CACHE"
fi

# === PI BENCHMARK CHECK (once per hour, cached) ===
PI_CACHE="/tmp/clarvis_pi_check_cache"
PI_STALE=true
if [ -f "$PI_CACHE" ]; then
    PI_AGE=$(( $(date +%s) - $(stat -c%Y "$PI_CACHE" 2>/dev/null || echo 0) ))
    [ "$PI_AGE" -lt 3600 ] && PI_STALE=false
fi
if [ "$PI_STALE" = true ]; then
    PI_VAL=$(cd $CLARVIS_WORKSPACE && python3 - <<'PYEOF' 2>/dev/null
import sys; sys.path.insert(0, 'scripts/metrics')
from performance_benchmark import run_quick_benchmark
try:
    result = run_quick_benchmark()
    print(f'{result["pi_estimate"]["pi"]:.3f}')
except Exception:
    print('error')
PYEOF
)
    if [ "$PI_VAL" != "error" ] && [ -n "$PI_VAL" ]; then
        PI_NUM=$(echo "$PI_VAL" | tr -d '[:space:]')
        echo "[$DATE] PI=$PI_NUM" >> "$LOG_DIR"/health.log
        if python3 -c "import sys; sys.exit(0 if float('$PI_NUM') < 0.70 else 1)" 2>/dev/null; then
            echo "[$DATE] [WARNING] Performance Index below 0.70: PI=$PI_NUM" >> "$LOG_DIR"/alerts.log
            : # PI below threshold — alert logged above
        fi
    fi
    touch "$PI_CACHE"
fi

# === PHI SUB-METRICS CHECK (once per hour, cached) ===
PHI_SUB_CACHE="/tmp/clarvis_phi_sub_cache"
PHI_SUB_STALE=true
if [ -f "$PHI_SUB_CACHE" ]; then
    PHI_SUB_AGE=$(( $(date +%s) - $(stat -c%Y "$PHI_SUB_CACHE" 2>/dev/null || echo 0) ))
    [ "$PHI_SUB_AGE" -lt 3600 ] && PHI_SUB_STALE=false
fi
if [ "$PHI_SUB_STALE" = true ]; then
    PHI_SUB_JSON=$(cd $CLARVIS_WORKSPACE && python3 -c "
import sys, json
sys.path.insert(0, '.')
try:
    from clarvis.metrics.phi import compute_phi
    result = compute_phi()
    print(json.dumps({'phi': result['phi'], 'components': result['components']}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
" 2>/dev/null)
    if echo "$PHI_SUB_JSON" | python3 -c "import sys,json; json.load(sys.stdin)['components']" 2>/dev/null; then
        # Extract values
        PHI_TOTAL=$(echo "$PHI_SUB_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['phi'])")
        # Find 3 weakest sub-metrics and report
        PHI_WEAK=$(echo "$PHI_SUB_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
comps = data['components']
ranked = sorted(comps.items(), key=lambda x: x[1])
for name, val in ranked[:3]:
    print(f'  {name}={val:.4f}')
")
        echo "[$DATE] Phi=$PHI_TOTAL weakest:" >> "$LOG_DIR"/health.log
        echo "$PHI_WEAK" >> "$LOG_DIR"/health.log

        # Alert on state changes only: enter warning, escalate to critical, or recover.
        PHI_ALERT_STATE_FILE="/tmp/clarvis_phi_alert_state.json"
        PHI_ALERT_DECISION=$(PHI_ALERT_STATE_FILE="$PHI_ALERT_STATE_FILE" DATE="$DATE" PHI_TOTAL="$PHI_TOTAL" PHI_WEAK="$PHI_WEAK" PHI_SUB_JSON="$PHI_SUB_JSON" python3 - <<'PY'
import json, os
from pathlib import Path

state_path = Path(os.environ['PHI_ALERT_STATE_FILE'])
data = json.loads(os.environ['PHI_SUB_JSON'])
components = data['components']
phi_total = os.environ['PHI_TOTAL']
date = os.environ['DATE']
phi_weak = os.environ['PHI_WEAK']

below = {k: round(v, 4) for k, v in components.items() if v < 0.50}
zeros = {k: v for k, v in below.items() if v <= 0.0001}
if zeros or len(below) >= 2:
    severity = 'critical'
elif below:
    severity = 'warning'
else:
    severity = 'ok'

current = {
    'severity': severity,
    'below': below,
}

previous = {'severity': 'ok', 'below': {}}
if state_path.exists():
    try:
        previous = json.loads(state_path.read_text())
    except Exception:
        previous = {'severity': 'ok', 'below': {}}

send = False
kind = 'noop'
log_line = ''
tg_msg = ''

if severity == 'ok' and previous.get('severity') != 'ok':
    send = True
    kind = 'recovery'
    log_line = f"[{date}] [INFO] Phi sub-metric recovery: all components >= 0.50 (Phi={phi_total})"
    tg_msg = f"✅ Phi sub-metric recovery\nAll components are now >= 0.50\nPhi={phi_total}"
elif severity != 'ok':
    prev_sev = previous.get('severity', 'ok')
    prev_below = previous.get('below', {})
    changed_keys = set(prev_below) != set(below)
    worsened = any(below.get(k, 1.0) < prev_below.get(k, 1.0) - 0.03 for k in below)
    escalated = (prev_sev != 'critical' and severity == 'critical')
    entered = (prev_sev == 'ok')
    if entered or escalated or changed_keys or worsened:
        send = True
        kind = 'alert'
        level_emoji = '🚨' if severity == 'critical' else '⚠️'
        level_word = severity.upper()
        joined = ' | '.join(f'{k}={v:.4f}' for k, v in below.items())
        log_line = f"[{date}] [{level_word}] Phi sub-metric state change: {joined}"
        tg_msg = f"{level_emoji} Phi sub-metric {severity}\n{joined}\nPhi={phi_total} | Weakest 3:\n{phi_weak}"

state_path.write_text(json.dumps(current))
print(json.dumps({'send': send, 'kind': kind, 'log_line': log_line, 'tg_msg': tg_msg}))
PY
)
        PHI_ALERT_SEND=$(echo "$PHI_ALERT_DECISION" | python3 -c "import sys,json; print('1' if json.load(sys.stdin).get('send') else '0')" 2>/dev/null)
        if [ "$PHI_ALERT_SEND" = "1" ]; then
            PHI_ALERT_LOG=$(echo "$PHI_ALERT_DECISION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('log_line',''))" 2>/dev/null)
            PHI_ALERT_MSG=$(echo "$PHI_ALERT_DECISION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tg_msg',''))" 2>/dev/null)
            [ -n "$PHI_ALERT_LOG" ] && echo "$PHI_ALERT_LOG" >> "$LOG_DIR"/alerts.log
            TG_TOKEN="${CLARVIS_TG_BOT_TOKEN:-}"
            TG_CHAT="${CLARVIS_TG_CHAT_ID:-}"
            if [ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ] && [ -n "$PHI_ALERT_MSG" ]; then
                curl -s --max-time 10 \
                    "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
                    -d chat_id="$TG_CHAT" \
                    -d text="$PHI_ALERT_MSG" \
                    -d parse_mode="HTML" >/dev/null 2>&1 || true
            fi
        fi
    fi
    touch "$PHI_SUB_CACHE"
fi

# === CONTEXT RELEVANCE TREND ===
CR_CACHE="/tmp/clarvis_cr_cache"
CR_STALE=true
if [ -f "$CR_CACHE" ]; then
    CACHE_AGE=$(( $(date +%s) - $(stat -c%Y "$CR_CACHE" 2>/dev/null || echo 0) ))
    [ "$CACHE_AGE" -lt 3600 ] && CR_STALE=false
fi
if $CR_STALE; then
    CR_VAL=$(python3 -m clarvis cognition context-relevance aggregate --days 7 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('mean_relevance',0))" 2>/dev/null)
    if [ -n "$CR_VAL" ] && [ "$CR_VAL" != "0" ]; then
        echo "[$DATE] CR=$CR_VAL" >> "$LOG_DIR"/context_relevance_trend.log
        # Alert if drop > 0.05 from 14-day baseline
        CR_BASELINE=$(python3 -m clarvis cognition context-relevance aggregate --days 14 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('mean_relevance',0))" 2>/dev/null)
        if [ -n "$CR_BASELINE" ] && python3 -c "
delta = float('$CR_BASELINE') - float('$CR_VAL')
exit(0 if delta > 0.05 else 1)
" 2>/dev/null; then
            echo "[$DATE] [WARNING] Context relevance dropped >0.05: 7d=$CR_VAL vs 14d=$CR_BASELINE" >> "$LOG_DIR"/alerts.log
        fi
    fi
    touch "$CR_CACHE"
fi

# Keep last 1000 lines of health log
tail -n 1000 $LOG_DIR/health.log > $LOG_DIR/health.log.tmp && mv $LOG_DIR/health.log.tmp $LOG_DIR/health.log

# === MACHINE-READABLE JSON EXPORT ===
# Collects all metrics into a single JSON file for downstream dashboards/alerting.
# Values from hourly-cached checks (PI, Phi) are read from their cache files;
# if stale or missing they show as null rather than triggering expensive recomputation.
GATEWAY_STATUS="down"
ss -tlnp 2>/dev/null | grep -q ":18789 " && GATEWAY_STATUS="up"

# Brain count (fast — just a ChromaDB count)
BRAIN_COUNT=$(cd $CLARVIS_WORKSPACE && python3 -c "
import sys; sys.path.insert(0, 'scripts')
try:
    from brain import get_brain
    print(get_brain().stats()['total_memories'])
except Exception:
    print('null')
" 2>/dev/null)
[ -z "$BRAIN_COUNT" ] && BRAIN_COUNT="null"

# Cron health: count OK vs failed from recent cron log entries (last 24h)
CRON_OK=0
CRON_FAIL=0
if [ -f "$LOG_DIR/health.log" ]; then
    TODAY=$(date '+%Y-%m-%d')
    CRON_OK=$(grep -c -E "\[.*$TODAY.*\].*(completed|OK|success)" "$LOG_DIR/health.log" 2>/dev/null || true)
    CRON_FAIL=$(grep -c -E "\[.*$TODAY.*\].*(FAIL|ERROR|CRITICAL)" "$LOG_DIR/alerts.log" 2>/dev/null || true)
    CRON_OK=${CRON_OK:-0}
    CRON_FAIL=${CRON_FAIL:-0}
fi

# Read cached PI value (computed hourly above)
CACHED_PI="null"
if [ -n "${PI_VAL:-}" ] && [ "${PI_VAL:-}" != "error" ]; then
    CACHED_PI="$PI_VAL"
elif [ -f $CLARVIS_WORKSPACE/data/performance_metrics.json ]; then
    CACHED_PI=$(python3 -c "
import json
try:
    d = json.load(open('$CLARVIS_WORKSPACE/data/performance_metrics.json'))
    print(round(d.get('pi_estimate', d.get('pi', {}).get('pi', 0)), 4))
except Exception:
    print('null')
" 2>/dev/null)
fi

# Read cached Phi value
CACHED_PHI="null"
if [ -n "${PHI_TOTAL:-}" ]; then
    CACHED_PHI="$PHI_TOTAL"
elif [ -f $CLARVIS_WORKSPACE/data/phi_history.json ]; then
    CACHED_PHI=$(python3 -c "
import json
try:
    h = json.load(open('$CLARVIS_WORKSPACE/data/phi_history.json'))
    if h: print(h[-1].get('phi', 'null'))
    else: print('null')
except Exception:
    print('null')
" 2>/dev/null)
fi

# Write JSON (atomic via tmp + mv)
JSON_TMP="$LOG_DIR/health_latest.json.tmp.$$"
cat > "$JSON_TMP" <<ENDJSON
{
  "timestamp": "$DATE",
  "brain_count": $BRAIN_COUNT,
  "cron_ok_count": $CRON_OK,
  "cron_fail_count": $CRON_FAIL,
  "disk_pct": $DISK_USED,
  "mem_pct": $MEM_PCT,
  "load": "$LOAD",
  "gateway_status": "$GATEWAY_STATUS",
  "phi": $CACHED_PHI,
  "pi": $CACHED_PI
}
ENDJSON
mv "$JSON_TMP" "$LOG_DIR/health_latest.json"

# Summary output for quick check
echo "=== CLARVIS STATUS ==="
echo "Uptime: $(uptime -p)"
echo "Memory: ${MEM_USED}MB / ${MEM_TOTAL}MB (${MEM_PCT}%)"
echo "Disk: ${DISK_USED}% used"
echo "Load: $LOAD"
echo "Wallet: \$$USDC_BALANCE USDC"
echo "Open Ports: $OPEN_PORTS"
echo "Failed SSH (recent): $FAILED_SSH"
echo "Alerts: $(tail -3 $LOG_DIR/alerts.log 2>/dev/null | tr '\n' ' ')"
