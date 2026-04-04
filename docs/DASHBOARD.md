# Clarvis Visual Dashboard

Phase 5 visual ops dashboard — SSE event hub + PixiJS frontend.

## Overview

Real-time system dashboard showing QUEUE tasks, active locks, subagent status, cron activity, and GitHub PRs. Built on Starlette with Server-Sent Events for live updates.

**Port**: 18799 (LAN accessible, read-only, no auth)

## Endpoints

| Path | Method | Description |
|------|--------|-------------|
| `/` | GET | Static PixiJS dashboard (HTML/JS) |
| `/state` | GET | Full JSON system state snapshot |
| `/queue-block/{TAG}` | GET | Full QUEUE.md markdown block for a task |
| `/sse` | GET | Server-Sent Events stream (max 5 clients) |
| `/health` | GET | Health check (`{"status":"ok","ts":"..."}`) |

## Service Management

```bash
# Reload after editing the service file
systemctl --user daemon-reload

# Start / stop / restart
systemctl --user start clarvis-dashboard.service
systemctl --user stop clarvis-dashboard.service
systemctl --user restart clarvis-dashboard.service

# Check status and logs
systemctl --user status clarvis-dashboard.service
journalctl --user -u clarvis-dashboard.service -f

# Enable on boot (auto-start after login)
systemctl --user enable clarvis-dashboard.service

# Disable auto-start
systemctl --user disable clarvis-dashboard.service
```

Requires systemd user session vars:
```bash
export XDG_RUNTIME_DIR=/run/user/1001
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus
```

## Data Sources

- `memory/evolution/QUEUE.md` — task queue (parsed into structured items)
- `memory/cron/digest.md` — cron activity digest (last 15 lines)
- `data/dashboard/events.jsonl` — dashboard events (last 30)
- `/tmp/clarvis_*.lock` — active process locks
- `data/orchestration_scoreboard.jsonl` — agent scores
- GitHub PRs via `gh pr list` (cached 60s)

## SSE Event Types

| Event | Trigger | Payload |
|-------|---------|---------|
| `state` | On connect | Full system state |
| `queue_update` | QUEUE.md changes | Updated task list |
| `agent_status` | Agent config changes | Agent list |
| `cron_activity` | Lock file changes | Active locks |
| `events_update` | New dashboard events | Last 5 events |
| `pr_update` | PR list changes | Open PRs |

Poll interval: 5 seconds.

## Health Monitoring

The dashboard health endpoint (`/health`) is checked by `health_monitor.sh` every 15 minutes. If port 18799 is not listening, an alert is logged but no auto-restart is attempted (the service is non-critical).

## Manual Start (without systemd)

```bash
cd $CLARVIS_WORKSPACE/scripts
python3 dashboard_server.py                  # default port 18799
python3 dashboard_server.py --port 18791     # custom port
```

## Dependencies

- Python 3.12+
- `starlette`, `sse-starlette`, `uvicorn` (pip)
- `gh` CLI (for PR fetching, optional)

## Files

- `scripts/dashboard_server.py` — server application
- `scripts/dashboard_static/` — frontend (HTML, JS, CSS)
- `~/.config/systemd/user/clarvis-dashboard.service` — systemd unit
