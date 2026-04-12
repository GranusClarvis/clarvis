# Clarvis on Hermes — Runtime / Operator Guide

> **Support Status: Experimental / Partial**
> Hermes integration is not production-ready. The OpenClaw gateway remains the
> primary supported harness. Key gaps: `hermes-agent` CLI flag handling, local
> model performance, incomplete cron migration, no Telegram/Discord gateway.
> See [Limitations](#limitations) and the
> [Support Matrix](SUPPORT_MATRIX.md) for details.

---

## Overview

[Hermes Agent](https://github.com/NousResearch/hermes-agent) is NousResearch's
Python-based agent harness. Clarvis can run on Hermes as an alternative to the
OpenClaw gateway for development, testing, and local-only setups.

For installation instructions, see [INSTALL.md](../INSTALL.md).
For harness comparison, see [SUPPORT_MATRIX.md](SUPPORT_MATRIX.md).

## Key Differences from OpenClaw

| Aspect | Clarvis on OpenClaw | Clarvis on Hermes |
|--------|-------------------|------------------|
| **Runtime** | Node.js gateway (systemd) | Python CLI / programmatic |
| **Chat interface** | Telegram/Discord via gateway | Terminal CLI or programmatic API |
| **Model routing** | OpenRouter via gateway config | `~/.hermes/config.yaml` |
| **Session storage** | OpenClaw sessions | `~/.hermes/sessions/` (SQLite) |
| **Skills** | OpenClaw SKILL.md format | Hermes Skills Hub format |
| **Daemon mode** | `systemctl --user` | Not daemon by default |
| **Config** | `openclaw.json` | `~/.hermes/config.yaml` + `.env` |
| **Cron/autonomy** | System crontab (30+ jobs) | `hermes cron` (built-in scheduler) |

## Runtime Operations

### CLI Interaction

```bash
hermes chat              # Interactive chat session
hermes run "your task"   # One-shot task execution
hermes sessions list     # List saved sessions
```

**Important**: Use the `hermes` CLI (not `hermes-agent`) — `hermes` correctly
reads `config.yaml`, while `hermes-agent` has flag-handling bugs (see
[Limitations](#limitations)).

### Useful Commands

| Command | What it does |
|---------|-------------|
| `hermes doctor` | Full diagnostic — checks config, deps, model connectivity |
| `hermes status` | Current model, provider, services, sessions |
| `hermes config set <key> <value>` | Update config.yaml |
| `hermes skills list` | List available skills |
| `hermes version` | Show version + update availability |
| `hermes sessions list` | List saved chat sessions |

### Clarvis Brain Access

The Clarvis brain works identically on both harnesses — it reads from
`CLARVIS_WORKSPACE`:

```bash
export CLARVIS_WORKSPACE=/path/to/clarvis/workspace
python3 -m clarvis brain search "query"
python3 -m clarvis brain health
```

## Configuration

### `~/.hermes/config.yaml`
```yaml
model: "your-model-id"
provider: "openrouter"  # or ollama, anthropic, openai
base_url: "https://openrouter.ai/api/v1"
```

### `~/.hermes/.env`
```
OPENROUTER_API_KEY=sk-or-v1-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Profile Isolation

Run Hermes alongside production Clarvis without conflict:
```bash
hermes profile create dev
hermes profile use dev
# Separate sessions, config, and memories
```

## Limitations

### Known Issues

1. **`hermes-agent` CLI ignores flags** (HIGH): The `hermes-agent` entry point
   does not respect `--model`, `--base_url`, or `--api_key` flags.
   - **Workaround**: Use `hermes` CLI or invoke `python run_agent.py` directly.

2. **Local models are slow** (MEDIUM): qwen3-vl:4b at ~7 tok/s on CPU cannot
   complete tool-calling loops in reasonable time.
   - **Recommendation**: Use a faster model or route through OpenRouter.

3. **No headless `.env` setup** (LOW): `hermes setup` requires an interactive
   terminal. For headless/CI, manually create `~/.hermes/.env`.

4. **Auth token confusion** (LOW): Hermes auto-detects Claude Code OAuth tokens
   in `~/.hermes/auth.json`, which may not work for Hermes itself.

### What's Not Available on Hermes

- **Telegram/Discord integration**: No built-in chat gateway.
- **OpenClaw skills**: Clarvis's 19 OpenClaw-format skills don't directly port.
- **systemd daemon mode**: Hermes doesn't run as a persistent service.
- **Cron autonomy**: Full 30+ job schedule needs manual migration.

## When to Use Hermes vs OpenClaw

**Use Hermes** for development/testing, programmatic integration, local-only
setups (Hermes + Ollama), or profile isolation.

**Stay on OpenClaw** for production chat (Telegram/Discord), full cron
autonomy, or multi-model routing.
