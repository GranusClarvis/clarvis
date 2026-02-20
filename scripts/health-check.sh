#!/bin/bash
# Clarvis Health Check — validates key systems are operational

echo "🔍 Clarvis Health Check"
echo "========================"

# 1. Gateway
if pgrep -f "openclaw-gateway" > /dev/null; then
    echo "✓ Gateway: RUNNING"
else
    echo "✗ Gateway: NOT RUNNING"
fi

# 2. Git (uncommitted changes?)
cd /home/agent/.openclaw/workspace
if git diff --quiet 2>/dev/null; then
    echo "✓ Git: Clean"
else
    echo "⚠ Git: Uncommitted changes"
fi

# 3. ClarvisDB (vector memory)
RESULT=$(python3 -c "
import sys
sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from brain import brain
stats = brain.stats()
print('working')
" 2>/dev/null)

if [ "$RESULT" = "working" ]; then
    echo "✓ ClarvisDB: Brain working"
else
    echo "✗ ClarvisDB: Failed"
fi

# 4. Disk space
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "✓ Disk: ${DISK_USAGE}% used"
else
    echo "⚠ Disk: ${DISK_USAGE}% used (low space)"
fi

# 5. RAM
RAM_USED=$(free | awk 'NR==2 {print $3}')
RAM_TOTAL=$(free | awk 'NR==2 {print $2}')
RAM_PCT=$((RAM_USED * 100 / RAM_TOTAL))
echo "✓ RAM: ${RAM_PCT}% used"

echo ""
echo "========================"
echo "Health check complete."
