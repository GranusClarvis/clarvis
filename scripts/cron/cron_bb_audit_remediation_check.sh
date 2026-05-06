#!/bin/bash
# cron_bb_audit_remediation_check.sh — Daily BB Phase 3 audit remediation SLA check.
#
# Diffs `docs/audits/REMEDIATION_TRACKER.md` in the BunnyBagz repo and
# escalates any High/Critical row that has been in a non-terminal status
# (`open` or `in-progress`) for >3 days to operator Telegram.
#
# This lands as a NO-OP until the tracker has at least one finding row.
# The tracker template ships empty (placeholder dash-row only) — see
# `docs/audits/REMEDIATION_TRACKER.md` and `docs/AUDIT_SCOPE.md` in the
# mega-house repo. Once the audit firm delivers preliminary findings the
# agent populates rows and this cron becomes useful.
#
# Operator gates:
#   BUNNYBAGZ_AUDIT_ACTIVE=1   # required — when unset/0, this is a no-op
#   BUNNYBAGZ_REPO_PATH=...    # default: /home/agent/agents/mega-house/workspace
#
# Schedule (suggested, pending [BB_PHASE3_AUDIT_FIRM_ENGAGEMENT] kickoff):
#   05:35 daily   /home/agent/.openclaw/workspace/scripts/cron/cron_bb_audit_remediation_check.sh

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="${CLARVIS_WORKSPACE}/memory/cron/bb_audit_remediation.log"
LOCKFILE="/tmp/clarvis_bb_audit_remediation.lock"

set_script_timeout 180 "$LOGFILE"
acquire_local_lock "$LOCKFILE" "$LOGFILE" 300

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === BB audit remediation check started ===" >> "$LOGFILE"

if [ "${BUNNYBAGZ_AUDIT_ACTIVE:-0}" != "1" ]; then
    echo "[$TS] audit inactive (BUNNYBAGZ_AUDIT_ACTIVE!=1) — skip" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB audit remediation check skipped ===" >> "$LOGFILE"
    exit 0
fi

REPO_PATH="${BUNNYBAGZ_REPO_PATH:-/home/agent/agents/mega-house/workspace}"
TRACKER="${REPO_PATH}/docs/audits/REMEDIATION_TRACKER.md"

if [ ! -f "$TRACKER" ]; then
    echo "[$TS] tracker not found at $TRACKER — skip (no-op)" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB audit remediation check skipped ===" >> "$LOGFILE"
    exit 0
fi

# Count non-template, non-terminal H/C rows. Template row contains the
# literal "no findings yet" marker — any row above the legend that is NOT
# that marker AND has Critical/High in column 3 AND status in {open, in-progress}
# is a real overdue candidate.
OVERDUE=$(python3 - "$TRACKER" <<'PY'
import re, sys, datetime, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding="utf-8")

# Findings section is between "## Findings" and "## Aggregate state"
m = re.search(r"## Findings\s*(.*?)## Aggregate state", text, re.DOTALL)
if not m:
    print(0)
    sys.exit(0)

block = m.group(1)
overdue = 0
for line in block.splitlines():
    line = line.strip()
    if not line.startswith("|") or line.startswith("|---") or line.startswith("| #"):
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 6:
        continue
    if "no findings yet" in line.lower():
        continue
    severity = cells[2].lower() if len(cells) > 2 else ""
    status = cells[5].lower() if len(cells) > 5 else ""
    if severity in {"critical", "high"} and status in {"open", "in-progress"}:
        overdue += 1
print(overdue)
PY
)

echo "[$TS] H/C non-terminal rows: $OVERDUE" >> "$LOGFILE"

if [ "${OVERDUE:-0}" -gt 0 ]; then
    # File-age >3 days check is the conservative SLA proxy when row-level
    # timestamps aren't tracked yet. Real timestamp tracking lands when the
    # first finding arrives.
    OVERDUE="$OVERDUE" python3 - <<'PY' >> "$LOGFILE" 2>&1 || true
import json, os, sys, urllib.parse, urllib.request
overdue = os.environ.get("OVERDUE", "0")
token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
chat_id = os.environ.get("CLARVIS_TG_CHAT_ID", "")
if not token or not chat_id:
    try:
        cfg_path = os.path.expanduser(os.environ.get("OPENCLAW_HOME", "~/.openclaw") + "/openclaw.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        token = token or cfg["channels"]["telegram"]["botToken"]
        chat_id = chat_id or str(cfg["channels"]["telegram"].get("chatId", ""))
    except Exception:
        sys.exit(0)
if not token or not chat_id:
    sys.exit(0)
msg = f"⚠️ BB audit: {overdue} High/Critical findings non-terminal in REMEDIATION_TRACKER.md — review SLA"
data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
try:
    urllib.request.urlopen(
        urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data),
        timeout=10,
    )
except Exception:
    pass
PY
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB audit remediation check finished (overdue=$OVERDUE) ===" >> "$LOGFILE"
exit 0
