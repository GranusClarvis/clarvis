#!/bin/bash
# Morning Report - 09:30 UTC
# Comprehensive report: what happened overnight, metrics, priorities
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOCKFILE="/tmp/clarvis_report_morning.lock"
MAX_LOCK_AGE=1200  # seconds — reclaim stale locks older than 20 min
if [ -f "$LOCKFILE" ]; then
    lock_content=$(cat "$LOCKFILE" 2>/dev/null)
    pid=$(echo "$lock_content" | awk '{print $1}')
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        # Verify PID is actually a report script (guards against PID recycling)
        cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
        if echo "$cmdline" | grep -q "cron_report"; then
            lock_age=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
            if [ "$lock_age" -lt "$MAX_LOCK_AGE" ]; then
                exit 0
            fi
            echo "[report_morning] Stale lock (age=${lock_age}s, pid=$pid) — reclaiming"
        else
            echo "[report_morning] PID $pid recycled (cmdline mismatch) — reclaiming lock"
        fi
    fi
    rm -f "$LOCKFILE"
fi
echo "$$ $(date -u +%Y-%m-%dT%H:%M:%S)" > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

python3 << 'PYEOF'
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
import os
import subprocess

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.getcwd())
today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

# Get bot token from env (preferred) or openclaw config (fallback)
TOKEN = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
if not TOKEN:
    try:
        _oc = os.environ.get('OPENCLAW_HOME', os.path.expanduser('~/.openclaw'))
        with open(os.path.join(_oc, 'openclaw.json')) as f:
            config = json.load(f)
        TOKEN = config['channels']['telegram']['botToken']
    except Exception:
        TOKEN = ""
if not TOKEN:
    print("[report_morning] No Telegram token found, skipping")
    sys.exit(0)


def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return ""


def extract_task_id(context):
    """Extract task ID from digest entry context. Looks for [UPPER_CASE_ID] patterns."""
    m = re.search(r'\[([A-Z][A-Z0-9_]+)\]', context)
    if m:
        return m.group(1)
    return None


def extract_task_desc(context, entry_type):
    """Extract meaningful task description from digest entry."""
    # For autonomous: use task ID or first meaningful line
    if 'Autonomous' in entry_type or 'Sprint' in entry_type:
        tid = extract_task_id(context)
        if tid:
            return tid
        return "Evolution task"

    if 'Research' in entry_type:
        tid = extract_task_id(context)
        if tid and tid.startswith('RESEARCH'):
            return tid
        # Try to extract research topic
        m = re.search(r'(?:Researched|Research|Bundle\s+\w+):\s*(.+?)(?:\.|—|Result|\n)', context)
        if m:
            return m.group(1).strip()[:45]
        return "Research task"

    if 'Evolution' in entry_type:
        return "Evolution analysis"

    if 'Morning' in entry_type:
        return "Morning planning"

    if 'Reflection' in entry_type:
        return "Reflection cycle"

    return entry_type.split('—')[0].strip()[:30]


# ==== PARSE DIGEST ====
digest_content = read_file(os.path.join(WORKSPACE, "memory/cron/digest.md"))

entries = []
pattern = r'### (.+?) — (\d{2}:\d{2}) UTC'
for match in re.finditer(pattern, digest_content):
    entry_type = match.group(1).strip()
    timestamp = match.group(2)
    start = match.start()
    end = digest_content.find('###', start + 10)
    if end == -1:
        end = len(digest_content)
    context = digest_content[start:end].strip()

    # Extract result
    result_match = re.search(r'Result: (\w+)', context)
    result = result_match.group(1) if result_match else None

    entries.append({
        'type': entry_type,
        'time': timestamp,
        'context': context,
        'result': result,
    })

# Filter to overnight entries (after midnight UTC until 10:00 — digest resets at midnight,
# so we can only see post-midnight entries)
overnight_entries = [e for e in entries if int(e['time'].split(':')[0]) < 10]

# ==== COMPLETED TASKS — source of truth: QUEUE_ARCHIVE.md ====
archive_content = read_file(os.path.join(WORKSPACE, "memory/evolution/QUEUE_ARCHIVE.md"))

today_completed = []
# Match lines like: - [x] [TASK_ID] ... (2026-03-20...) or ... (Done 2026-03-20...)
for line in archive_content.split('\n'):
    if today_str in line and re.match(r'\s*- \[x\]', line):
        tid_match = re.search(r'\[([A-Z][A-Z0-9_]+)\]', line)
        if tid_match:
            tid = tid_match.group(1)
            # Skip meta-entries like CODE_VALIDATION, AUTO_SPLIT (they're sub-tasks)
            if tid not in ('CODE_VALIDATION', 'AUTO_SPLIT', 'LLM_BRAIN_REVIEW'):
                if tid not in today_completed:
                    today_completed.append(tid)

# Also count successful tasks from digest as supplementary
digest_successes = [e for e in overnight_entries if e['result'] == 'success']

# ==== PARSE QUEUE — pending items by section ====
queue_content = read_file(os.path.join(WORKSPACE, "memory/evolution/QUEUE.md"))

# Collect all pending items with their section context
pending_items = []
current_section = "Unknown"
for line in queue_content.split('\n'):
    # Track which section we're in
    if line.startswith('## '):
        current_section = line.strip('# ').strip()
    elif line.startswith('### '):
        current_section = line.strip('# ').strip()

    # Match pending items
    m = re.match(r'\s*- \[ \] \[([A-Z][A-Z0-9_]+)\](.*)$', line)
    if m:
        tid = m.group(1)
        desc = m.group(2).strip()[:50]
        pending_items.append({'id': tid, 'section': current_section, 'desc': desc})

    # Match in-progress items
    m2 = re.match(r'\s*- \[~\] \[([A-Z][A-Z0-9_]+)\](.*)$', line)
    if m2:
        tid = m2.group(1)
        pending_items.append({'id': tid, 'section': current_section, 'desc': 'in-progress'})

# Separate by priority
p0_items = [i for i in pending_items if 'P0' in i['section'] or 'Fixes' in i['section']]
new_items = [i for i in pending_items if 'NEW' in i['section']]
other_items = [i for i in pending_items if i not in p0_items and i not in new_items]
total_pending = len(pending_items)

# ==== GIT COMMITS (overnight) ====
git_commits = []
try:
    result = subprocess.run(
        ['git', 'log', '--oneline', f'--since={today_str} 00:00:00',
         f'--until={today_str} 10:00:00'],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=5
    )
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            msg = re.sub(r'^[a-f0-9]+\s*', '', line)
            if msg:
                git_commits.append(msg[:50])
except Exception:
    pass

# Also get yesterday's late commits
try:
    result = subprocess.run(
        ['git', 'log', '--oneline', f'--since={yesterday_str} 22:00:00',
         f'--until={today_str} 00:00:00'],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=5
    )
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            msg = re.sub(r'^[a-f0-9]+\s*', '', line)
            if msg:
                git_commits.append(msg[:50])
except Exception:
    pass

# ==== BRAIN STATS ====
try:
    _stats_out = subprocess.run(
        ['python3', '-m', 'clarvis', 'brain', 'stats'],
        capture_output=True, text=True, timeout=30,
        cwd=WORKSPACE
    )
    stats = json.loads(_stats_out.stdout)
except Exception:
    stats = {'total_memories': '?', 'collections': {}}

# ==== GOALS ====
goal_lines = []
try:
    sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
    from clarvis.brain import brain as _brain
    goals = _brain.get_goals()
    for g in goals[:3]:
        doc = g.get('document', '')
        prog_match = re.search(r'progress: (\d+)%', doc)
        goal_match = re.search(r'Goal:\s*([^—]+)', doc)
        if prog_match and goal_match:
            prog = prog_match.group(1)
            name = goal_match.group(1).strip()[:30]
            goal_lines.append(f"  {name}: {prog}%")
except Exception:
    goal_lines.append("  (unavailable)")
if not goal_lines:
    goal_lines.append("  (no active goals)")

# ==== BUILD REPORT ====
lines = []
lines.append("🌅 Clarvis Morning Report")
lines.append("=" * 40)
lines.append("")

# Overnight activity from digest
lines.append("🌙 OVERNIGHT WORK")
lines.append("-" * 20)
if overnight_entries:
    for e in overnight_entries:
        result_str = f"[{e['result']}]" if e['result'] else ""
        task_desc = extract_task_desc(e['context'], e['type'])
        lines.append(f"  {e['time']} → {task_desc} {result_str}".rstrip())
else:
    lines.append("  (No overnight activity in digest)")
lines.append("")

# Git commits overnight
if git_commits:
    lines.append("📝 OVERNIGHT COMMITS")
    lines.append("-" * 20)
    for c in git_commits[:4]:
        lines.append(f"  • {c}")
    lines.append("")

# Completed tasks (from archive, the real source of truth)
if today_completed:
    lines.append("✅ COMPLETED TODAY (so far)")
    lines.append("-" * 20)
    for t in today_completed[:6]:
        lines.append(f"  • {t}")
    lines.append("")

# Queue status
lines.append("📋 QUEUE STATUS")
lines.append("-" * 20)
lines.append(f"  Total pending: {total_pending}")
if p0_items:
    lines.append("  P0:")
    for t in p0_items[:3]:
        lines.append(f"    • {t['id']}")
if new_items:
    lines.append("  New:")
    for t in new_items[:3]:
        lines.append(f"    • {t['id']}")
if not p0_items and not new_items and other_items:
    lines.append("  Next:")
    for t in other_items[:3]:
        lines.append(f"    • {t['id']}")
if total_pending == 0:
    lines.append("  (Queue empty)")
lines.append("")

# Brain state
lines.append("🧠 BRAIN")
lines.append("-" * 20)
lines.append(f"  Memories: {stats.get('total_memories', '?')}")
cols = stats.get('collections', {})
if cols:
    top_cols = sorted(cols.items(), key=lambda x: x[1], reverse=True)[:4]
    cols_str = ", ".join([f"{k.split('-')[-1]}({v})" for k, v in top_cols])
    lines.append(f"  Top: {cols_str}")

# Goals
lines.append("")
lines.append("🎯 GOALS")
lines.append("-" * 20)
for gl in goal_lines:
    lines.append(gl)

lines.append("")

# Rating prompt for yesterday's unlabeled tasks
try:
    sys.path.insert(0, os.path.join(WORKSPACE, "scripts", "tools"))
    from operator_value_label import get_unlabeled_summary
    rating_block = get_unlabeled_summary(days=2, max_items=5)
    if rating_block:
        lines.append(rating_block)
        lines.append("")
except Exception:
    pass

lines.append("=" * 40)
lines.append("Ready for the day, sir.")

report = "\n".join(lines)

# Send to Telegram
GROUP_CHAT_ID = os.environ.get("CLARVIS_TG_GROUP_ID", "")
REPORTS_TOPIC = os.environ.get("CLARVIS_TG_REPORTS_TOPIC", "5")
DM_CHAT_ID = os.environ.get("CLARVIS_TG_CHAT_ID", "")

params = {"chat_id": GROUP_CHAT_ID, "text": report, "message_thread_id": REPORTS_TOPIC}
data = urllib.parse.urlencode(params)
req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
try:
    urllib.request.urlopen(req, timeout=10)
    print("[report_morning] Sent to Reports topic")
except Exception as e:
    print(f"[report_morning] Group delivery failed ({e}), falling back to DM")
    data = urllib.parse.urlencode({"chat_id": DM_CHAT_ID, "text": report})
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e2:
        print(f"[report_morning] DM delivery also failed: {e2}")

print(report)
PYEOF
