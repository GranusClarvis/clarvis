#!/bin/bash
# Clarvis Self-Monitoring System
# Runs every 15 minutes via cron
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

DATE=$(date '+%Y-%m-%d %H:%M:%S')
LOG_DIR="/home/agent/.openclaw/workspace/monitoring"
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
    python3 /home/agent/.openclaw/workspace/scripts/brain_hygiene.py check >> "$LOG_DIR"/health.log 2>&1 || {
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
    PI_VAL=$(cd /home/agent/.openclaw/workspace && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from performance_benchmark import run_quick_benchmark
try:
    result = run_quick_benchmark()
    print(f'{result[\"pi_estimate\"][\"pi\"]:.3f}')
except Exception:
    print('error')
" 2>/dev/null)
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

# Keep last 1000 lines of health log
tail -n 1000 $LOG_DIR/health.log > $LOG_DIR/health.log.tmp && mv $LOG_DIR/health.log.tmp $LOG_DIR/health.log

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
