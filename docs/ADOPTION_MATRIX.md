# Adoption Matrix — Fresh Install Truth Table

> **Generated:** 2026-04-12
> **Evidence:** E2E validation runs from `docs/validation/` (same date)
> **Purpose:** Single reference for what actually works on a fresh machine.

---

## Install Paths

| | **OpenClaw base** | **Hermes base** | **Clarvis-on-OpenClaw** | **Clarvis-on-Hermes** |
|---|---|---|---|---|
| **Install command** | `npm i -g openclaw` | `pip install git+…/hermes-agent.git` | `install.sh --profile openclaw` | `install.sh --profile hermes` |
| **Install friction** | Node 18+ required | PyPI package absent; must install from GitHub source | Node 18+ + `openclaw onboard` exits 1 (cosmetic) | GitHub source fallback auto-handled by installer |
| **First-run success** | Yes (onboard creates config) | Yes (`hermes --help` works) | 42/45 checks pass (3 warnings) | 38/39 checks pass (1 warning) |
| **Local-LLM-only** | No (gateway needs API key for model routing) | Yes (`hermes` + Ollama) | No (same as base) | Yes — but ~674s per turn on CPU (unusable for agent loops) |
| **Exact invocation** | `openclaw` CLI or systemd service | `hermes` CLI (**not** `hermes-agent`) | `systemctl --user start openclaw-gateway.service` | `hermes chat` or `hermes run "task"` |
| **Chat interface** | Telegram/Discord via gateway | Terminal CLI only | Same as base | Same as base |
| **Cron/autonomy** | N/A (not a Clarvis feature) | N/A | 30+ system crontab jobs, tested | Not integrated — manual only |
| **Brain (ChromaDB)** | N/A | N/A | SUPPORTED (local, tested) | SUPPORTED (local, tested, independent of Hermes) |
| **Session persistence** | OpenClaw sessions | `~/.hermes/sessions/` (SQLite) | OpenClaw sessions | Works via `hermes` CLI |
| **systemd daemon** | Yes (`openclaw-gateway.service`) | No | Yes | No |
| **Config bootstrap** | `openclaw.json` auto-created by onboard | `~/.hermes/config.yaml` auto-created by installer | Same as base | Same as base |
| **Headless setup** | Yes (non-interactive `onboard`) | Yes (installer creates config.yaml + .env) | Yes | Yes |
| **End-to-end feature coverage** | Gateway + chat + skills | CLI chat + sessions + skills hub | Full Clarvis stack (brain, heartbeat, cron, queue, CLI) | Clarvis brain/CLI/queue work; no cron, no gateway, no spawn |
| **Support level** | PARTIAL (upstream auth bug) | EXPERIMENTAL | PARTIAL | EXPERIMENTAL |

---

## Honestly Claimable?

| Path | Claimable for users? | Rationale |
|---|---|---|
| **OpenClaw base** | Yes, with caveat | Works but `onboard` exit code and auth field mismatch need upstream fixes |
| **Hermes base** | Yes, with caveat | Works but PyPI absent, `hermes-agent` entry point broken (use `hermes` CLI) |
| **Clarvis-on-OpenClaw** | Yes (PARTIAL) | 93% automated pass rate. Two upstream blockers documented. Primary supported path. |
| **Clarvis-on-Hermes** | **No — EXPERIMENTAL only** | Brain/CLI/queue work, but: no cron integration, no gateway, local model too slow for agent loops, `hermes-agent` flags broken. Cannot claim "alternative to OpenClaw" without qualification. |

---

## Blockers Preventing Upgrade to SUPPORTED

### Clarvis-on-Hermes → SUPPORTED requires:
1. **hermes-agent on PyPI** — or official install docs from NousResearch (upstream)
2. **`hermes-agent` CLI flag fix** — `--model`, `--base_url` must work (upstream)
3. **Cron integration** — either Hermes built-in scheduler or documented manual migration
4. **Usable local-model performance** — <30s per turn for basic chat (hardware or model fix)
5. **Headless `.env` generation** — DONE (installer now creates it)

### Clarvis-on-OpenClaw → SUPPORTED requires:
1. **Auth field mismatch fix** — `key` vs `token` in auth profile JSON (upstream)
2. **Health-check port not hardcoded** — upstream OpenClaw fix

---

## Test Evidence

| Test | Checks | Pass | Fail | Warn | Date |
|---|---|---|---|---|---|
| `e2e_clarvis_on_openclaw_fresh.sh` | 45 | 42 | 0 | 3 | 2026-04-12 |
| `e2e_clarvis_on_hermes_fresh.sh` | 39 | 38 | 0 | 1 | 2026-04-12 |
| `fresh_install_smoke.sh --isolated` | 61 | 59 | 0 | 1 | 2026-04-06 |
| `local_model_harness.sh test` | 12 | 12 | 0 | 0 | 2026-04-06 |

---

_See also: [SUPPORT_MATRIX.md](SUPPORT_MATRIX.md), [INSTALL.md](INSTALL.md), [USER_GUIDE_HERMES.md](USER_GUIDE_HERMES.md)_
