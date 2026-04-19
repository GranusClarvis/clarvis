#!/bin/bash
# =============================================================================
# Weekly CLR (Clarvis Rating) Benchmark
# =============================================================================
# Full 7-dimension CLR benchmark with stability check and digest summary.
# Schedule: Sunday 06:30 (after weekly PI benchmark at 06:00)
#
# This runs a full (non-quick) CLR evaluation, records it to history,
# checks stability over the last 14 days, and writes a summary to digest.
# =============================================================================

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/clr_benchmark.log"

# Local lock only (no Claude Code spawned, no maintenance lock needed)
acquire_local_lock "/tmp/clarvis_clr_benchmark.lock" "$LOGFILE" 120

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === Weekly CLR benchmark started ===" >> "$LOGFILE"

cd "$CLARVIS_WORKSPACE" || exit 1

# Run full CLR benchmark and record to history
CLR_OUTPUT=$(timeout 120 python3 -m clarvis metrics clr --record 2>&1)
CLR_EXIT=$?

echo "$CLR_OUTPUT" >> "$LOGFILE"

if [ $CLR_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CLR benchmark FAILED (exit=$CLR_EXIT)" >> "$LOGFILE"
    exit 1
fi

# Extract CLR score and value-add from output
CLR_SCORE=$(echo "$CLR_OUTPUT" | grep -oP 'CLR Score:\s+\K[0-9.]+' || echo "?")
VALUE_ADD=$(echo "$CLR_OUTPUT" | grep -oP 'Value Add:\s+\+\K[0-9.]+' || echo "?")
GATE=$(echo "$CLR_OUTPUT" | grep -oP 'Gate:\s+\K\w+' || echo "?")
RATING=$(echo "$CLR_OUTPUT" | grep -oP 'Rating:\s+\K.*' || echo "?")

# Run stability check
STABILITY_OUTPUT=$(timeout 30 python3 -c "
import json
from clarvis.metrics.clr import evaluate_clr_stability
result = evaluate_clr_stability()
stats = result.get('stats', {})
print(json.dumps({
    'pass': result.get('pass', False),
    'runs': stats.get('runs', 0),
    'mean': stats.get('mean', 0),
    'stddev': stats.get('stddev', 0),
    'failures': result.get('failures', [])
}))
" 2>/dev/null)

STABILITY_PASS=$(echo "$STABILITY_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pass','?'))" 2>/dev/null || echo "?")
STABILITY_RUNS=$(echo "$STABILITY_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('runs','?'))" 2>/dev/null || echo "?")

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CLR=$CLR_SCORE value_add=+$VALUE_ADD gate=$GATE stability=$STABILITY_PASS (n=$STABILITY_RUNS)" >> "$LOGFILE"

# Weekly Phi component regression check
PHI_REGRESSION=$(timeout 30 python3 -c "
import json
from clarvis.metrics.phi import weekly_regression_check
r = weekly_regression_check()
print(json.dumps(r))
" 2>/dev/null || echo '{"status":"error"}')

PHI_REG_STATUS=$(echo "$PHI_REGRESSION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "?")
PHI_REG_DETAIL=""
if [ "$PHI_REG_STATUS" = "regression" ]; then
    PHI_REG_DETAIL=$(echo "$PHI_REGRESSION" | python3 -c "import sys,json; print('; '.join(json.load(sys.stdin).get('regressions',[])))" 2>/dev/null || echo "")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARNING: Phi regression detected: $PHI_REG_DETAIL" >> "$LOGFILE"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Phi weekly check: $PHI_REG_STATUS" >> "$LOGFILE"
fi

# Write summary to digest
PHI_SUFFIX=""
[ "$PHI_REG_STATUS" = "regression" ] && PHI_SUFFIX=" ⚠ Phi regression: $PHI_REG_DETAIL"
DIGEST_SUMMARY="Weekly CLR benchmark: CLR=$CLR_SCORE (+$VALUE_ADD value-add), gate=$GATE, stability=$STABILITY_PASS ($STABILITY_RUNS runs). $RATING$PHI_SUFFIX"
python3 "$CLARVIS_WORKSPACE/scripts/tools/digest_writer.py" evolution \
    "$DIGEST_SUMMARY" >> "$LOGFILE" 2>&1 || true

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly CLR benchmark completed ===" >> "$LOGFILE"
