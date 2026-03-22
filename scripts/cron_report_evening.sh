#!/bin/bash
# Evening Report - 22:30 UTC
# Comprehensive report: what happened today, metrics, accomplishments
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOCKFILE="/tmp/clarvis_report_evening.lock"
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then exit 0; fi
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

python3 << 'PYEOF'
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import os
import subprocess

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

# Get bot token from env (preferred) or openclaw config (fallback)
TOKEN = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
if not TOKEN:
    try:
        with open('/home/agent/.openclaw/openclaw.json') as f:
            config = json.load(f)
        TOKEN = config['channels']['telegram']['botToken']
    except Exception:
        TOKEN = ""
if not TOKEN:
    print("[report_evening] No Telegram token found, skipping")
    sys.exit(0)


def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return ""


def extract_task_id(context):
    """Extract task ID from digest entry context."""
    m = re.search(r'\[([A-Z][A-Z0-9_]+)\]', context)
    if m:
        return m.group(1)
    return None


def extract_task_desc(context, entry_type):
    """Extract meaningful task description from digest entry."""
    if 'Autonomous' in entry_type or 'Sprint' in entry_type:
        tid = extract_task_id(context)
        if tid:
            return tid
        return "Evolution task"

    if 'Research' in entry_type:
        tid = extract_task_id(context)
        if tid and tid.startswith('RESEARCH'):
            return tid
        m = re.search(r'(?:Researched|Research|Bundle\s+\w+):\s*(.+?)(?:\.|—|Result|\n)', context)
        if m:
            return m.group(1).strip()[:45]
        return "Research task"

    if 'Evolution' in entry_type:
        return "Evolution analysis"

    if 'Morning' in entry_type:
        return "Morning planning"

    if 'Evening' in entry_type:
        return "Evening assessment"

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

    result_match = re.search(r'Result: (\w+)', context)
    result = result_match.group(1) if result_match else None

    entries.append({
        'type': entry_type,
        'time': timestamp,
        'context': context,
        'result': result,
    })

# All entries are today's (digest resets daily at midnight UTC)
# Separate by time period
morning_entries = [e for e in entries if int(e['time'].split(':')[0]) < 10]
daytime_entries = [e for e in entries if 10 <= int(e['time'].split(':')[0]) < 22]
all_entries = entries

# Count successes/failures/timeouts from digest
success_count = sum(1 for e in all_entries if e['result'] == 'success')
fail_count = sum(1 for e in all_entries if e['result'] in ('failure', 'error'))
timeout_count = sum(1 for e in all_entries if e['result'] == 'timeout')

# ==== COMPLETED TASKS — source of truth: QUEUE_ARCHIVE.md ====
archive_content = read_file(os.path.join(WORKSPACE, "memory/evolution/QUEUE_ARCHIVE.md"))

today_completed = []
for line in archive_content.split('\n'):
    if today_str in line and re.match(r'\s*- \[x\]', line):
        tid_match = re.search(r'\[([A-Z][A-Z0-9_]+)\]', line)
        if tid_match:
            tid = tid_match.group(1)
            # Skip meta-entries (sub-tasks that aren't standalone completions)
            if tid not in ('CODE_VALIDATION', 'AUTO_SPLIT', 'LLM_BRAIN_REVIEW'):
                if tid not in today_completed:
                    today_completed.append(tid)

# ==== GIT COMMITS TODAY ====
git_commits = []
try:
    result = subprocess.run(
        ['git', 'log', '--oneline', f'--since={today_str} 00:00:00',
         f'--until={today_str} 23:59:59'],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=5
    )
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            msg = re.sub(r'^[a-f0-9]+\s*', '', line)
            if msg:
                git_commits.append(msg[:50])
except Exception:
    pass

# ==== PARSE QUEUE ====
queue_content = read_file(os.path.join(WORKSPACE, "memory/evolution/QUEUE.md"))

pending_items = []
in_progress_items = []
current_section = "Unknown"
for line in queue_content.split('\n'):
    if line.startswith('## '):
        current_section = line.strip('# ').strip()
    elif line.startswith('### '):
        current_section = line.strip('# ').strip()

    m = re.match(r'\s*- \[ \] \[([A-Z][A-Z0-9_]+)\]', line)
    if m:
        pending_items.append({'id': m.group(1), 'section': current_section})

    m2 = re.match(r'\s*- \[~\] \[([A-Z][A-Z0-9_]+)\]', line)
    if m2:
        in_progress_items.append({'id': m2.group(1), 'section': current_section})

total_pending = len(pending_items) + len(in_progress_items)

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

# ==== BUILD REPORT ====
lines = []
lines.append("🌙 Clarvis Evening Report")
lines.append("=" * 40)
lines.append("")

# Today's work — full day from digest
lines.append("📅 TODAY'S WORK")
lines.append("-" * 20)
if all_entries:
    for e in all_entries:
        result_str = f"[{e['result']}]" if e['result'] else ""
        task = extract_task_desc(e['context'], e['type'])
        lines.append(f"  {e['time']} → {task} {result_str}".rstrip())
    lines.append(f"  — {success_count} success, {fail_count} fail, {timeout_count} timeout")
else:
    lines.append("  (No activity in digest)")
lines.append("")

# Completed tasks (from archive — real source of truth)
lines.append("✅ COMPLETED TODAY")
lines.append("-" * 20)
if today_completed:
    for t in today_completed:
        lines.append(f"  • {t}")
    lines.append(f"  Total: {len(today_completed)} tasks")
else:
    lines.append("  (No tasks archived today)")
lines.append("")

# Git commits
lines.append("📝 GIT COMMITS")
lines.append("-" * 20)
if git_commits:
    for c in git_commits[:5]:
        lines.append(f"  • {c}")
else:
    lines.append("  None")
lines.append("")

# Queue
lines.append("📋 QUEUE")
lines.append("-" * 20)
lines.append(f"  Pending: {len(pending_items)}, In-progress: {len(in_progress_items)}")
if pending_items:
    next_ids = [i['id'] for i in pending_items[:3]]
    lines.append(f"  Next: {', '.join(next_ids)}")
lines.append("")

# Brain
lines.append("🧠 BRAIN")
lines.append("-" * 20)
lines.append(f"  Memories: {stats.get('total_memories', '?')}")
cols = stats.get('collections', {})
if cols:
    top_cols = sorted(cols.items(), key=lambda x: x[1], reverse=True)[:3]
    cols_str = ", ".join([f"{k.split('-')[-1]}({v})" for k, v in top_cols])
    lines.append(f"  Top: {cols_str}")

lines.append("")
lines.append("=" * 40)
lines.append("Good night, sir.")

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
    print("[report_evening] Sent to Reports topic")
except Exception as e:
    print(f"[report_evening] Group delivery failed ({e}), falling back to DM")
    data = urllib.parse.urlencode({"chat_id": DM_CHAT_ID, "text": report})
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e2:
        print(f"[report_evening] DM delivery also failed: {e2}")

print(report)
PYEOF
