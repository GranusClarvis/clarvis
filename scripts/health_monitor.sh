#!/bin/bash
# Clarvis Self-Monitoring System
# Runs every 15 minutes via cron
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

DATE=$(date '+%Y-%m-%d %H:%M:%S')
LOG_DIR="/home/agent/.openclaw/workspace/monitoring"
ALERT=0

# === SYSTEM HEALTH ===
MEM_TOTAL=$(free -m | awk '/^Mem:/{print $2}')
MEM_USED=$(free -m | awk '/^Mem:/{print $3}')
MEM_AVAIL=$(free -m | awk '/^Mem:/{print $7}')
MEM_PCT=$((MEM_USED * 100 / MEM_TOTAL))

DISK_USED=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
LOAD=$(uptime | awk -F'load average:' '{print $2}' | cut -d',' -f1 | xargs)

# === PROCESS MONITORING ===
GATEWAY_PID=$(pgrep -f "openclaw-gateway" | head -1)
if [ -z "$GATEWAY_PID" ]; then
    echo "[ALERT] Gateway process not found!" >> $LOG_DIR/alerts.log
    ALERT=1
fi

# === SECURITY CHECKS ===
# Check for failed SSH attempts
FAILED_SSH=$(grep "Failed password" /var/log/auth.log 2>/dev/null | tail -5 | wc -l)

# Check for unusual processes (exclude self and system)
SUSPICIOUS=$(ps aux | grep -E "nc |netcat |nmap |masscan |hydra" | grep -v grep | wc -l)

# === NETWORK EXPOSURE ===
OPEN_PORTS=$(ss -tuln | awk 'NR>1 {print $1}' | sort -u | wc -l)

# === WALLET BALANCE ===
WALLET_INFO=$(curl -s https://api.mcporter.io/v1/conway/wallet_info 2>/dev/null)
USDC_BALANCE=$(echo "$WALLET_INFO" | grep -oP '"usdc":\K[0-9]+')

# === LOG STATUS ===
echo "[$DATE] MEM:${MEM_PCT}% DISK:${DISK_USED}% LOAD:$LOAD PORTS:$OPEN_PORTS SSH_FAILS:$FAILED_SSH WALLET:\$$USDC_BALANCE" >> $LOG_DIR/health.log

# === ALERTS ===
if [ $MEM_PCT -gt 90 ]; then
    echo "[$DATE] [CRITICAL] Memory usage at ${MEM_PCT}%" >> $LOG_DIR/alerts.log
    ALERT=1
fi

if [ $DISK_USED -gt 90 ]; then
    echo "[$DATE] [CRITICAL] Disk usage at ${DISK_USED}%" >> $LOG_DIR/alerts.log
    ALERT=1
fi

if [ $SUSPICIOUS -gt 0 ]; then
    echo "[$DATE] [WARNING] Suspicious processes detected" >> $LOG_DIR/alerts.log
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
