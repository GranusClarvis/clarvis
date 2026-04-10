# Claude Code Spawn Telegram Relay Investigation

**Date:** 2026-04-09
**Investigated by:** Claude Code (Opus)

## Summary

The rich "Claude Code Spawn" Telegram format **is NOT broken** in `spawn_claude.sh` itself.
The inconsistency is caused by three compounding factors:

1. Most Claude Code spawns go through `cron_autonomous.sh`, which uses a **different, shorter format** ("Heartbeat: ...").
2. Six other cron spawners (morning, evolution, evening, reflection, research, implementation sprint) send **no Telegram notification at all**.
3. The `spawn_claude.sh` worker lost its **error handling** around the Telegram API call during the worker-detach refactor in commit `e1358b8`, making transient failures invisible.

## Detailed Findings

### Finding 1: Two Competing Telegram Formats

There are exactly two scripts that send completion Telegram messages:

| Script | Format | Frequency |
|--------|--------|-----------|
| `scripts/agents/spawn_claude.sh` (line 200) | `"{emoji} Claude Code Spawn: {status}\n\n{clipboard} Task: {task}\n\n{memo} Result:\n{summary}"` | Manual `/spawn` only |
| `scripts/cron/cron_autonomous.sh` (line 631) | `"{emoji} Heartbeat: {status} ({executor}, {duration}s)\n{clipboard} {task}"` | 12x/day |

The "Claude Code Spawn" rich format is ONLY sent when the user explicitly invokes `/spawn` or calls `spawn_claude.sh` directly. The 12x/day autonomous heartbeats use the shorter "Heartbeat" format with no result summary. Six other cron scripts (morning, evolution, evening, reflection, research, implementation_sprint) spawn Claude Code but send **no Telegram notification** at all.

**Implication:** Users see "Heartbeat: OK" messages frequently but rarely see "Claude Code Spawn: OK" because `/spawn` is used far less often than cron.

### Finding 2: Worker Detach Refactor Removed Error Handling

**Commit:** `e1358b8` (2026-03-18, "clarvis: refresh context relevance live and harden claude spawn")

This commit changed `spawn_claude.sh` from inline execution (with `setsid`) to a detached worker pattern (`nohup worker.sh >/dev/null 2>&1 &`).

**What was lost:**

The old inline version had proper error handling for Telegram delivery:
```python
try:
    urllib.request.urlopen(req, timeout=10)
    print(f"[spawn_claude] TG delivery: OK ({target})", file=sys.stderr)
except Exception as e:
    print(f"[spawn_claude] TG delivery failed: {e}", file=sys.stderr)
```

The new worker version (line 65 of the generated worker) has:
```python
urllib.request.urlopen(req, timeout=10)
# NO try/except - crash on any error
```

**Combined with `nohup >/dev/null 2>&1 &`** (line 238), any Telegram API error (network timeout, rate limit, 5xx, etc.) causes the Python script to crash silently. No log entry, no error output, no indication of failure.

**File:** `scripts/agents/spawn_claude.sh`, line 208 (missing try/except), line 238 (nohup to /dev/null)

Compare with `cron_autonomous.sh` line 636-639 which properly wraps the call:
```python
try:
    urllib.request.urlopen(req, timeout=10)
except Exception:
    pass
```

### Finding 3: chat_id Fallback Asymmetry

In `spawn_claude.sh`'s Python TG code (lines 186-191), the `openclaw.json` fallback only retrieves the **bot token**, NOT the `chat_id`:
```python
token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
if not token:
    with open(os.path.join(_oc, 'openclaw.json')) as f:
        config = json.load(f)
    token = config['channels']['telegram']['botToken']
# chat_id has NO openclaw.json fallback
```

In `cron_autonomous.sh` (lines 615-624), the fallback retrieves BOTH:
```python
token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
chat_id = os.environ.get("CLARVIS_TG_CHAT_ID", "")
if not token or not chat_id:
    config = json.load(...)
    if not token: token = config['channels']['telegram']['botToken']
    if not chat_id: chat_id = str(config['channels']['telegram'].get('chatId', ''))
```

**Current impact:** Low, because `chat_id` is passed as a shell argument (`$TG_CHAT_ID`) which is expanded from `$CLARVIS_TG_CHAT_ID` loaded from `.env` by `cron_env.sh`. The env var path works. But if `.env` were ever missing or the var unset, `spawn_claude.sh` would fail where `cron_autonomous.sh` would still try `openclaw.json`. (Note: `openclaw.json` currently has `chatId: false` anyway, so neither fallback works for chat_id.)

### Finding 4: Heredoc Nesting is Correct (Not a Bug)

I verified that the nested heredoc pattern (`<< 'PYEOF'` inside `<<EOF`) correctly preserves the Python code. Despite the outer unquoted `<<EOF` expanding `$variables`, the Python f-string placeholders (`{emoji}`, `{status}`, etc.) have no `$` prefix and are not expanded by bash. The Python code in the generated worker script is syntactically correct and produces the expected rich format (verified by local test).

### Finding 5: Cron Schedule Shows the Volume Disparity

Per the crontab:
- `cron_autonomous.sh` runs 12x/day (hours 1,6,7,9,11,12,15,17,19,20,22,23) -> sends "Heartbeat" format
- `cron_morning.sh`, `cron_evolution.sh`, `cron_evening.sh`, `cron_research.sh` (2x), `cron_reflection.sh`, `cron_implementation_sprint.sh` run 1-2x/day each -> send NO Telegram notification
- `/spawn` (manual via `spawn_claude.sh`) is ad-hoc -> sends rich "Claude Code Spawn" format

So out of ~20+ daily Claude Code invocations, only the ~12 autonomous heartbeats produce Telegram notifications (in the short format), and the remaining 7-8 cron spawns produce none. The "Claude Code Spawn" rich format only appears when the user manually triggers `/spawn`.

## Root Cause Summary

The perception that "rich messages stopped arriving" has three causes:

1. **Volume displacement:** The dominant spawn path shifted to `cron_autonomous.sh` which uses a different (shorter) format. The rich format was always limited to `/spawn`.
2. **Silent failures:** The worker-detach refactor in `e1358b8` (2026-03-18) removed error handling from the Telegram API call. Any transient error (timeout, rate limit) silently drops the message with no trace.
3. **No Telegram from most cron spawners:** 7-8 daily cron spawns (morning, evolution, evening, reflection, research, implementation) produce no Telegram notification at all.

## Fixes Applied

### Fix 1: Restored try/except in spawn_claude.sh (APPLIED)

In `scripts/agents/spawn_claude.sh`, line 207-208, wrapped the `urlopen` call with error handling and stderr logging:

```python
try:
    urllib.request.urlopen(req, timeout=10)
except Exception as _e:
    print(f"[spawn_claude] TG delivery failed: {_e}", file=__import__('sys').stderr)
```

**Verification:** `bash -n scripts/agents/spawn_claude.sh` — syntax OK.

## Remaining Fixes (Not Applied)

### Fix 2: Add chat_id fallback to openclaw.json (Low Priority)

In the same Python block (after line 191), add chat_id fallback matching `cron_autonomous.sh`'s pattern. Low priority because the env var path works.

### Fix 3: Add Telegram notifications to other cron spawners (Enhancement)

Add Telegram delivery to `cron_morning.sh`, `cron_evolution.sh`, `cron_evening.sh`, `cron_reflection.sh`, `cron_research.sh`, and `cron_implementation_sprint.sh` — using the rich "Claude Code Spawn" format or a consistent format for all spawners.

### Fix 4: Log TG delivery status to spawn log (Observability)

Route the worker's Telegram Python output to the logfile instead of `/dev/null`, at minimum for stderr. Change line 238 from:
```bash
nohup "$WORKER_SCRIPT" >/dev/null 2>&1 &
```
to:
```bash
nohup "$WORKER_SCRIPT" >> "$CLARVIS_WORKSPACE/memory/cron/spawn_claude.log" 2>&1 &
```

## Timeline

| Date | Commit | Change | Impact on TG Messages |
|------|--------|--------|-----------------------|
| 2026-02-25 | `3ebbbc0` | spawn_claude.sh created | No Telegram at all |
| 2026-02-27 | `58fa7b5` | Telegram delivery added (inline, with try/except) | Rich format working |
| 2026-03-18 | `e1358b8` | Worker-detach refactor: removed try/except, nohup to /dev/null | Silent failures begin |
| 2026-04-03 | `22c8a88` | Queue spine migration | No TG impact |
| 2026-04-04 | `b059950` | Script reorganization to subdirs | Path updated, no TG impact |
| 2026-04-04 | `c90e294` | Hardcoded path removal | Env var fallback, no TG impact |

## Key File Paths

- **Rich format code:** `/home/agent/.openclaw/workspace/scripts/agents/spawn_claude.sh` (line 200)
- **Short format code:** `/home/agent/.openclaw/workspace/scripts/cron/cron_autonomous.sh` (line 631)
- **Worker heredoc:** `/home/agent/.openclaw/workspace/scripts/agents/spawn_claude.sh` (lines 143-236)
- **Missing try/except:** `/home/agent/.openclaw/workspace/scripts/agents/spawn_claude.sh` (line 208)
- **nohup to /dev/null:** `/home/agent/.openclaw/workspace/scripts/agents/spawn_claude.sh` (line 238)
- **Spawn log:** `/home/agent/.openclaw/workspace/memory/cron/spawn_claude.log`
- **Env credentials:** `/home/agent/.openclaw/workspace/.env` (CLARVIS_TG_BOT_TOKEN, CLARVIS_TG_CHAT_ID)
