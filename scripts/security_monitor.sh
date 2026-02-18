#!/bin/bash
# Clarvis Security Monitor
# Checks for intrusion attempts and prompt injection patterns

DATE=$(date '+%Y-%m-%d %H:%M:%S')
LOG_DIR="/home/agent/.openclaw/workspace/monitoring"
ALERT_LOG="$LOG_DIR/security.log"

log_alert() {
    echo "[$DATE] $1" >> $ALERT_LOG
}

# === SSH INTRUSION CHECK ===
# Check for brute force attempts
FAILED_AUTH=$(grep -c "Failed password" /var/log/auth.log 2>/dev/null || echo 0)
INVALID_USER=$(grep -c "Invalid user" /var/log/auth.log 2>/dev/null || echo 0)

if [ $FAILED_AUTH -gt 5 ]; then
    log_alert "[WARN] Multiple failed SSH attempts: $FAILED_AUTH"
fi

if [ $INVALID_USER -gt 0 ]; then
    log_alert "[WARN] Invalid user login attempts: $INVALID_USER"
fi

# === NETWORK EXPOSURE ===
# Check listening services
LISTEN_TCP=$(ss -tln | grep LISTEN | wc -l)
LISTEN_UDP=$(ss -uln | grep LISTEN | wc -l)

# Known safe ports (adjust as needed)
SAFE_PORTS="22 80 443 18789"
EXPOSED=""

for port in $(ss -tln | grep LISTEN | awk '{print $4}' | grep -oP ':(\d+)$' | cut -d: -f2); do
    if ! echo $SAFE_PORTS | grep -q "\b$port\b"; then
        EXPOSED="$EXPOSED $port"
    fi
done

if [ -n "$EXPOSED" ]; then
    log_alert "[INFO] Non-standard ports open:$EXPOSED"
fi

# === PROMPT INJECTION PATTERNS ===
# Monitor conversation logs for suspicious patterns (would check OpenClaw logs)
# This is a placeholder - actual implementation would need access to message logs
INJECTION_PATTERNS="ignore previous|forget everything|new instructions|you are now|DAN|jailbreak"
# Log pattern detection capability (not actual monitoring of user messages)
log_alert "[INFO] Security monitor initialized - patterns loaded: $INJECTION_PATTERNS"

# === FIREWALL STATUS ===
UFW_STATUS=$(which ufw && ufw status 2>/dev/null | head -1 || echo "ufw not available")

# === RESOURCE ANOMALIES ===
# Check for unusual CPU spikes
CPU_LOAD=$(uptime | awk -F'load average:' '{print $2}' | cut -d',' -f1 | xargs)
CPU_INT=$(echo "$CPU_LOAD" | cut -d'.' -f1)
if [ $CPU_INT -gt 8 ]; then
    log_alert "[WARN] High CPU load: $CPU_LOAD"
fi

# === SUMMARY ===
echo "=== SECURITY STATUS ==="
echo "Failed SSH (recent): $FAILED_AUTH"
echo "Invalid users: $INVALID_USER"
echo "Listening TCP: $LISTEN_TCP | UDP: $LISTEN_UDP"
echo "Firewall: $UFW_STATUS"
echo "Load: $CPU_LOAD"
echo ""
echo "Last 5 security events:"
tail -5 $ALERT_LOG 2>/dev/null || echo "(no events yet)"
