# Open-Source Sensitive File Audit

_Generated: 2026-03-20. Scan scope: all git-tracked files in workspace._
_Prerequisite for Milestone C (deadline 2026-03-26)._

## Status Legend
- `[ ]` Not fixed
- `[x]` Fixed
- `[~]` Partially fixed / acceptable with env var fallback

---

## CRITICAL — Must Fix Before Any Public Push

### 1. Telegram Bot Token (Active Credential)

| Status | File | Line | Content | Fix |
|--------|------|------|---------|-----|
| [ ] | `scripts/cron_env.sh` | 25 | `CLARVIS_TG_BOT_TOKEN` default contains full token `REDACTED_TELEGRAM_BOT_TOKEN` | Remove default; require env var. **Rotate token before publish.** |
| [ ] | `docs/OPEN_SOURCE_GAP_AUDIT.md` | 8 | Token prefix `REDACTED_TOKEN_PREFIX` in text | Redact to `<REDACTED>` |
| [ ] | `docs/OPEN_SOURCE_READINESS_AUDIT.md` | 10 | Token prefix `REDACTED_TOKEN_PREFIX` in table | Redact to `<REDACTED>` |

### 2. Telegram Personal Chat ID (`REDACTED_CHAT_ID`)

| Status | File | Line | Content | Fix |
|--------|------|------|---------|-----|
| [ ] | `scripts/cron_env.sh` | 26 | Default in `CLARVIS_TG_CHAT_ID` | Remove default; require env var |
| [ ] | `scripts/spawn_claude.sh` | 25 | Fallback `${CLARVIS_TG_CHAT_ID:-REDACTED_CHAT_ID}` | Remove literal default |
| [ ] | `scripts/spawn_claude.sh` | 158 | Python fallback `"REDACTED_CHAT_ID"` | Remove literal default |
| [ ] | `scripts/cron_watchdog.sh` | 177 | Python fallback `"REDACTED_CHAT_ID"` | Remove literal default |
| [ ] | `scripts/cron_report_morning.sh` | 226 | `DM_CHAT_ID` fallback | Remove literal default |
| [ ] | `scripts/cron_report_evening.sh` | 205 | `DM_CHAT_ID` fallback | Remove literal default |
| [ ] | `USER.md` | 32 | `Telegram: ID REDACTED_CHAT_ID` | Redact or remove line |
| [ ] | `docs/clarvis_orchestrator_design.md` | 586 | `chatId: REDACTED_CHAT_ID` | Replace with `<CHAT_ID>` |
| [ ] | `docs/WEBSITE_V0_INFORMATION_ARCH.md` | 120 | Chat ID in audit checklist | Replace with `<CHAT_ID>` |
| [ ] | `docs/WEBSITE_V0_RELEASE_RUNBOOK.md` | 50 | Chat ID in test pattern | Replace with `<CHAT_ID>` |
| [ ] | `memory/2026-02-23-2155.md` | 45,83,176 | `sender_id` in raw message dump | Delete file or redact IDs |

### 3. Telegram Group Chat ID (`REDACTED_GROUP_ID`)

| Status | File | Line | Content | Fix |
|--------|------|------|---------|-----|
| [ ] | `AGENTS.md` | 280 | Group ID in agent config | Replace with `<GROUP_CHAT_ID>` |
| [ ] | `scripts/budget_alert.py` | 162,200 | Hardcoded group ID | Use env var `CLARVIS_TG_GROUP_ID` |
| [ ] | `scripts/cron_report_morning.sh` | 224 | `GROUP_CHAT_ID` hardcoded | Use env var |
| [ ] | `scripts/cron_report_evening.sh` | 203 | `GROUP_CHAT_ID` hardcoded | Use env var |
| [ ] | `skills/spawn-claude/SKILL.md` | 32,40 | Group ID in example commands | Replace with `<GROUP_CHAT_ID>` |

### 4. Test Password in Tracked Files

| Status | File | Line | Content | Fix |
|--------|------|------|---------|-----|
| [ ] | `docs/OPEN_SOURCE_GAP_AUDIT.md` | 18 | Password `REDACTED_PASSWORD` in plaintext | Redact to `<REDACTED>` |
| [~] | `tests/test_open_source_smoke.py` | 172 | Regex pattern for detecting the password | Acceptable (detection test) |

---

## HIGH — Hardcoded Paths (Portability)

These files use `/home/agent/.openclaw/workspace` without `os.environ.get()` fallback:

| Status | File | Line | Fix |
|--------|------|------|-----|
| [ ] | `clarvis/cli_brain.py` | 15 | `WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")` |
| [ ] | `clarvis/cli_cost.py` | 12 | Same pattern |
| [ ] | `clarvis/cli_bench.py` | 13 | Same pattern |
| [ ] | `clarvis/cli_heartbeat.py` | 24 | Same pattern |
| [ ] | `clarvis/metrics/quality.py` | 24 | Same pattern |
| [ ] | `clarvis/metrics/memory_audit.py` | 19 | Same pattern |

**Already acceptable** (use env var fallback): `clarvis/metrics/clr.py`, `clr_perturbation.py`, `trajectory.py`, `self_model.py`.

---

## MEDIUM — Personal Identity / PII

| Status | File | Line | Content | Fix |
|--------|------|------|---------|-----|
| [ ] | `USER.md` | 3-4 | Real name "Patrick", alias "Inverse" | Anonymize or exclude from public repo |
| [ ] | `USER.md` | 30 | GitHub username `InverseAltruism` | Anonymize |
| [ ] | `USER.md` | 31 | Discord IDs `994258501675270234`, `939859740211691550` | Remove |
| [ ] | `USER.md` | 32 | Telegram ID (see above) | Remove |
| [ ] | `scripts/universal_web_agent.py` | 17 | Email `REDACTED_EMAIL` in docstring | Replace with `user@example.com` |
| [ ] | `docs/OPEN_SOURCE_GAP_AUDIT.md` | 18 | Email `REDACTED_EMAIL` | Redact |
| [ ] | `SOUL.md` | — | References to "Inverse" as creator | Anonymize or parameterize |
| [ ] | `AGENTS.md` | 19 | "report to Inverse" | Anonymize |

---

## LOW — Non-Sensitive but Worth Noting

| Status | File | Content | Fix |
|--------|------|---------|-----|
| [~] | `docs/OPEN_SOURCE_READINESS_AUDIT.md` | Entire file documents sensitive patterns | Keep as internal reference; exclude from public build |
| [~] | `docs/OPEN_SOURCE_GAP_AUDIT.md` | Entire file documents sensitive patterns | Same |
| [~] | `MEMORY.md` | References to "Patrick", "InverseAltruism" | Anonymize for public |
| [~] | Localhost ports `18789`, `11434` | In docs/scripts | Acceptable (loopback only) |

---

## Pre-Existing Protection (Confirmed Safe)

- `.gitignore` excludes: `data/` (ChromaDB, browser sessions, budget config), `*.env`, `*.key`, `*.pem`, `*credentials*`
- `data/budget_config.json` (contains bot token + chat ID) — gitignored
- `data/browser_sessions/` (session cookies) — gitignored
- `data/clarvisdb/` (embeddings may contain leaked text) — gitignored

---

## Remediation Plan

### Before publish (blocking):
1. Rotate Telegram bot token
2. Remove all hardcoded defaults from `cron_env.sh` (token + chat IDs)
3. Remove literal fallback IDs from all scripts (use empty string or error)
4. Redact password from `OPEN_SOURCE_GAP_AUDIT.md`
5. Add env var fallback to 6 `clarvis/` modules with hardcoded `WORKSPACE`
6. Decide: anonymize `USER.md` or add to `.gitignore`

### Recommended `.env.example`:
```bash
CLARVIS_WORKSPACE=/path/to/workspace
CLARVIS_TG_BOT_TOKEN=your-telegram-bot-token
CLARVIS_TG_CHAT_ID=your-chat-id
CLARVIS_TG_GROUP_ID=your-group-chat-id
```

### Git history note:
Even after fixing files, secrets remain in git history. Before public push:
```bash
git filter-repo --invert-paths --path scripts/cron_env.sh
# OR use BFG Repo-Cleaner to strip specific strings
```
Alternatively, start fresh with a squashed initial commit for the public repo.
