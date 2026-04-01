# Codex Desktop App Path — Evaluation for Clarvis

**Date**: 2026-04-01
**Task**: [CODEX_DESKTOP_APP_PATH]

---

## 1. What Codex/Harness Offer as UX

| Product | UX Surface | Key Properties |
|---------|-----------|----------------|
| **Codex CLI** | Full-screen Ratatui TUI | Local-first, sandboxed, multi-agent, reactive terminal |
| **Claude Code** | React/Ink terminal + VS Code extension + web app + desktop app (Mac/Win) | Multi-surface, prompt caching, session persistence |
| **Clarvis** | Telegram chat + CLI scripts + cron logs | Chat-first, no dashboard, results via digest.md |

Both competing products invest heavily in visual feedback:
- Codex: full-screen terminal with tool approval UI, agent progress, reasoning display
- Claude Code: desktop app (Electron), web app, IDE extensions — same core with multiple shells

## 2. What Clarvis Currently Has

- **Operator interaction**: Telegram bot (text in → text out, `/costs`, `/budget`, `/spawn`)
- **Monitoring**: `health_monitor.sh` (terminal), `generate_status_json.py` (JSON for dashboards)
- **Subconscious visibility**: `memory/cron/digest.md` (text summary, read by M2.5)
- **Brain exploration**: CLI (`python3 -m clarvis brain search "query"`)
- **New**: `scripts/attention_visualizer.py` (HTML brain search visualization)

## 3. Assessment: Does Clarvis Need a Desktop App?

**No.** A desktop app would be the wrong investment for these reasons:

### 3.1 Clarvis is server-resident, not local

Codex and Claude Code run on the operator's machine. Their UX is about making local tool execution visible and controllable. Clarvis runs on a VPS — there's no local process to wrap in a desktop shell. A desktop app would be a remote client, which is just a web app with extra packaging overhead.

### 3.2 The operator interface is Telegram

Patrick interacts via Telegram. Adding a desktop app means maintaining two UX surfaces. Telegram is already available on desktop, mobile, and web. The marginal value of a custom app over Telegram is low.

### 3.3 What would actually help: a lightweight web dashboard

Instead of a desktop app, Clarvis would benefit from a **single-page status dashboard** served from the VPS:

| Component | Purpose | Already Exists? |
|-----------|---------|-----------------|
| System health | Gateway, cron, brain status | Yes (`generate_status_json.py`) |
| Brain explorer | Search + attention visualization | Partial (`attention_visualizer.py` HTML) |
| Cost tracker | Usage, budget, daily trends | Yes (JSON from `cost_tracker.py`) |
| Evolution queue | Current tasks, progress | Yes (`QUEUE.md`) |
| Cron timeline | What ran, when, success/fail | Partial (logs exist, no timeline view) |
| Agent status | Project agents, spawn history | Yes (`project_agent.py info`) |

A static HTML dashboard regenerated every 15 minutes by cron (using existing `generate_status_json.py` data) would provide 80% of the value of a desktop app with 5% of the effort.

### 3.4 What to actually build (if prioritized)

**Minimal viable dashboard** (P2, ~2-3 hours):
1. `scripts/generate_dashboard.py` — reads `status.json` + `QUEUE.md` + cost data, outputs `data/dashboard.html`
2. Serve via a simple HTTP endpoint on the gateway (or `python3 -m http.server` on a port)
3. Auto-refresh via cron every 15 min
4. Include: health indicators, today's tasks, cost chart, brain stats, recent episodes

**Not worth building**: Electron app, native app, real-time WebSocket dashboard, interactive brain explorer. These are premature given the single-operator, single-VPS architecture.

## 4. What IS Worth Stealing from the Desktop App Pattern

| Pattern | Value | Effort |
|---------|-------|--------|
| **Status JSON endpoint** | Already done (`generate_status_json.py`) | None |
| **Structured session history** | View past heartbeat sessions and their outcomes | Medium — needs JSONL session logging |
| **Attention visualization** | Already built today (`attention_visualizer.py`) | Done |
| **Remote intervention** | Pause/resume/redirect a running heartbeat from Telegram | High — needs IPC mechanism |

## 5. Recommendation

**Skip the desktop app path.** Clarvis's UX advantage is autonomous operation — the operator should see results, not watch processes. Invest in:
1. Richer Telegram reports (embed charts via Telegram's image API)
2. Static HTML dashboard (cron-generated, served from VPS)
3. Session transcript logging (feeds brain, enables replay)

These provide more operator value per hour of effort than any app shell.
