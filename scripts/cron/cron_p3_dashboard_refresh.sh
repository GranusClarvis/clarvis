#!/bin/bash
# Daily P@3 retrieval-quality dashboard refresh — [P3_DASHBOARD_REFRESH_CRON].
#
# Targets the weakest Precision@3 metric. The dashboard at
# data/retrieval_quality/dashboard.md previously drifted ~7 weeks stale when
# unmaintained (manually regenerated 2026-05-05). This job refreshes it daily
# and alerts on regressions.
#
# Schedule: 04:55 daily — lands inside the maintenance window, before
# ChromaDB vacuum (05:00) and PI refresh (05:45).
#
# Steps:
#   1. Run scripts/brain_mem/retrieval_benchmark.py golden_qa
#      (refreshes data/retrieval_benchmark/latest.json + history.jsonl)
#   2. Run scripts/brain_mem/retrieval_dashboard.py
#      (writes data/retrieval_quality/dashboard.md with same-day last_updated)
#   3. Compare current vs prior P@3; alert via Telegram if drop > 0.05
#
# Locking: /tmp/clarvis_p3_refresh.lock via lock_helper.sh (trap EXIT cleanup)
#
# Flags:
#   --dry-run    Run end-to-end but skip Telegram send. Sets DRY_RUN=1 for
#                the alert step.
#   --synth-drop Inject a synthetic prior P@3 to force the alert path
#                (used for verification only).
#
# Canonical-source TBD pending [P3_DASHBOARD_SOURCE_AUDIT]; this job aggregates
# the existing producers until that audit names a single source.

DRY_RUN=0
SYNTH_DROP=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --synth-drop) SYNTH_DROP=1 ;;
    esac
done

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/p3_dashboard_refresh.log"
OPS_LOG="$CLARVIS_WORKSPACE/monitoring/p3_dashboard_refresh.log"
mkdir -p "$(dirname "$OPS_LOG")"

# Local lock — pure Python, no Claude Code; stale threshold 120s
acquire_local_lock "/tmp/clarvis_p3_refresh.lock" "$LOGFILE" 120

cd "$CLARVIS_WORKSPACE" || exit 1

TS_START="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS_START] === P@3 dashboard refresh started (dry_run=$DRY_RUN synth_drop=$SYNTH_DROP) ===" | tee -a "$LOGFILE" >> "$OPS_LOG"

# Capture prior P@3 BEFORE running benchmark (read penultimate-most-recent history entry,
# or the last one if we'd want to compare against pre-run state). We snapshot the last
# entry now and compare it against the new last entry after the benchmark writes.
PRIOR_P3=$(python3 - <<'PYEOF'
import json, os
from pathlib import Path
ws = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
hist = ws / "data/retrieval_benchmark/history.jsonl"
if not hist.exists():
    print("")
else:
    last = ""
    with hist.open() as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    if last:
        try:
            rec = json.loads(last)
            v = rec.get("avg_precision_at_k")
            print(f"{v:.4f}" if v is not None else "")
        except Exception:
            print("")
    else:
        print("")
PYEOF
)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] prior_p3=${PRIOR_P3:-none}" | tee -a "$LOGFILE" >> "$OPS_LOG"

# Step 1 — refresh benchmark fixture
timeout 120 python3 scripts/brain_mem/retrieval_benchmark.py golden_qa >> "$LOGFILE" 2>&1
BENCH_EXIT=$?
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] benchmark exit=$BENCH_EXIT" | tee -a "$LOGFILE" >> "$OPS_LOG"

# Step 2 — render dashboard
timeout 30 python3 scripts/brain_mem/retrieval_dashboard.py >> "$LOGFILE" 2>&1
DASH_EXIT=$?
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] dashboard exit=$DASH_EXIT" | tee -a "$LOGFILE" >> "$OPS_LOG"

# Verify dashboard freshness
DASHBOARD_FILE="$CLARVIS_WORKSPACE/data/retrieval_quality/dashboard.md"
if [ -f "$DASHBOARD_FILE" ]; then
    DASH_AGE=$(( $(date +%s) - $(stat -c%Y "$DASHBOARD_FILE" 2>/dev/null || echo 0) ))
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] dashboard age=${DASH_AGE}s" | tee -a "$LOGFILE" >> "$OPS_LOG"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: dashboard file missing after refresh" | tee -a "$LOGFILE" >> "$OPS_LOG"
fi

# Step 3 — P@3 drop alert (>0.05 vs prior).
# Reads latest.json for current; compares against PRIOR_P3 captured above.
# --synth-drop forces alert path by overriding prior with current+0.10.
# --dry-run skips the actual Telegram send.
PRIOR_P3="$PRIOR_P3" DRY_RUN="$DRY_RUN" SYNTH_DROP="$SYNTH_DROP" \
    LOGFILE="$LOGFILE" python3 - <<'PYEOF' >> "$LOGFILE" 2>&1
import json, os, sys
from pathlib import Path

ws = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
latest = ws / "data/retrieval_benchmark/latest.json"

if not latest.exists():
    print(f"[p3-alert] no latest.json; skipping alert")
    sys.exit(0)

try:
    cur = json.loads(latest.read_text())
except Exception as e:
    print(f"[p3-alert] failed to parse latest.json: {e}")
    sys.exit(0)

new_p3 = cur.get("avg_precision_at_k")
if new_p3 is None:
    print(f"[p3-alert] no avg_precision_at_k in latest.json; skipping")
    sys.exit(0)

prior_raw = os.environ.get("PRIOR_P3", "").strip()
synth = os.environ.get("SYNTH_DROP", "0") == "1"
dry_run = os.environ.get("DRY_RUN", "0") == "1"

if synth:
    # Force a regression by claiming prior was 0.10 above current
    prior = float(new_p3) + 0.10
    print(f"[p3-alert] SYNTHETIC: prior={prior:.4f} (forced) new={new_p3:.4f}")
elif prior_raw:
    try:
        prior = float(prior_raw)
    except ValueError:
        print(f"[p3-alert] could not parse PRIOR_P3='{prior_raw}'; skipping")
        sys.exit(0)
else:
    print(f"[p3-alert] no prior P@3 available (first run?); skipping")
    sys.exit(0)

drop = prior - float(new_p3)
print(f"[p3-alert] prior={prior:.4f} new={new_p3:.4f} drop={drop:+.4f}")

if drop <= 0.05:
    print(f"[p3-alert] drop within tolerance (<=0.05); no alert")
    sys.exit(0)

# Build alert message
msg = (
    "<b>P@3 Retrieval Drop</b>\n\n"
    f"prior: <code>{prior:.3f}</code>\n"
    f"new:   <code>{float(new_p3):.3f}</code>\n"
    f"drop:  <code>-{drop:.3f}</code> (threshold 0.05)\n\n"
    f"Dashboard: data/retrieval_quality/dashboard.md\n"
    f"Source: scripts/cron/cron_p3_dashboard_refresh.sh"
)

if dry_run:
    print(f"[p3-alert] DRY_RUN: would send Telegram alert:\n{msg}")
    sys.exit(0)

# Use budget_alert.send_telegram helper
try:
    sys.path.insert(0, str(ws / "scripts" / "infra"))
    from budget_alert import send_telegram
except Exception as e:
    print(f"[p3-alert] failed to import budget_alert.send_telegram: {e}")
    sys.exit(0)

token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
chat_id = os.environ.get("CLARVIS_TG_CHAT_ID", "")
topic = os.environ.get("CLARVIS_TG_REPORTS_TOPIC", "")
if not token or not chat_id:
    print(f"[p3-alert] Telegram credentials missing; alert NOT sent (would have been: drop={drop:.3f})")
    sys.exit(0)

ok = send_telegram(token, chat_id, msg, topic_id=topic)
print(f"[p3-alert] Telegram send ok={ok}")
PYEOF
ALERT_EXIT=$?

TS_END="$(date -u +%Y-%m-%dT%H:%M:%S)"
if [ $BENCH_EXIT -eq 0 ] && [ $DASH_EXIT -eq 0 ]; then
    echo "[$TS_END] P@3 dashboard refresh completed (alert_step=$ALERT_EXIT)" | tee -a "$LOGFILE" >> "$OPS_LOG"
    exit 0
else
    echo "[$TS_END] P@3 dashboard refresh FAILED (bench=$BENCH_EXIT dashboard=$DASH_EXIT)" | tee -a "$LOGFILE" >> "$OPS_LOG"
    exit 1
fi
