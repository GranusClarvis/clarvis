# Open-Source Sensitive File Audit

_Generated: 2026-03-20. Scan scope: all git-tracked files in workspace._
_Prerequisite for Milestone C (deadline 2026-03-26)._

## Status Legend
- `[ ]` Not fixed
- `[x]` Fixed
- `[~]` Partially fixed / acceptable with env var fallback

---

## CRITICAL — Must Fix Before Any Public Push

### 1. Telegram Bot Token (Active Credential) — ALL FIXED 2026-03-22

| Status | File | Fix Applied |
|--------|------|-------------|
| [x] | `scripts/cron_env.sh` | Default removed; now loads from `.env` file |
| [x] | `docs/OPEN_SOURCE_GAP_AUDIT.md` | Section rewritten, token redacted |
| [x] | `docs/OPEN_SOURCE_READINESS_AUDIT.md` | Section rewritten, token redacted |

**Remaining**: Rotate bot token before publish.

### 2. Telegram Personal Chat ID — ALL FIXED 2026-03-22

| Status | File | Fix Applied |
|--------|------|-------------|
| [x] | `scripts/cron_env.sh` | Default removed; loads from `.env` |
| [x] | `scripts/spawn_claude.sh` | Literal defaults removed (both shell + Python) |
| [x] | `scripts/cron_watchdog.sh` | Literal default removed |
| [x] | `scripts/cron_report_morning.sh` | Uses `CLARVIS_TG_CHAT_ID` env var |
| [x] | `scripts/cron_report_evening.sh` | Uses `CLARVIS_TG_CHAT_ID` env var |
| [x] | `USER.md` | Chat ID removed, references `.env` |
| [x] | `docs/clarvis_orchestrator_design.md` | Replaced with `${CLARVIS_TG_CHAT_ID}` |
| [x] | `docs/WEBSITE_V0_INFORMATION_ARCH.md` | Redacted to pattern reference |
| [x] | `docs/WEBSITE_V0_RELEASE_RUNBOOK.md` | Redacted to `<CHAT_ID_PATTERN>` |
| [x] | `memory/2026-02-23-2155.md` | sender_id fields redacted |

### 3. Telegram Group Chat ID — ALL FIXED 2026-03-22

| Status | File | Fix Applied |
|--------|------|-------------|
| [x] | `AGENTS.md` | Replaced with `${CLARVIS_TG_GROUP_ID}` |
| [x] | `scripts/budget_alert.py` | Uses `CLARVIS_TG_GROUP_ID` env var |
| [x] | `scripts/cron_report_morning.sh` | Uses `CLARVIS_TG_GROUP_ID` env var |
| [x] | `scripts/cron_report_evening.sh` | Uses `CLARVIS_TG_GROUP_ID` env var |
| [x] | `skills/spawn-claude/SKILL.md` | Replaced with `${CLARVIS_TG_GROUP_ID}` |

### 4. Test Password / Email in Tracked Files — FIXED 2026-03-22

| Status | File | Fix Applied |
|--------|------|-------------|
| [x] | `docs/OPEN_SOURCE_GAP_AUDIT.md` | Section rewritten, password + email redacted |
| [x] | `scripts/universal_web_agent.py` | Email replaced with `your@email.com` |
| [~] | `tests/test_open_source_smoke.py` | Acceptable (detection regex pattern) |

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
| [x] | `USER.md` | 31 | Discord IDs removed | Done 2026-03-22 |
| [x] | `USER.md` | 32 | Telegram ID removed | Done 2026-03-22 |
| [x] | `scripts/universal_web_agent.py` | 17 | Email replaced with placeholder | Done 2026-03-22 |
| [x] | `docs/OPEN_SOURCE_GAP_AUDIT.md` | 18 | Email + password redacted | Done 2026-03-22 |
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
