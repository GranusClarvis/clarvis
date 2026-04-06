# Clarvis on Hermes — User Guide

## What is Hermes?

[Hermes Agent](https://github.com/NousResearch/hermes-agent) is NousResearch's Python-based agent harness. It provides a CLI, session management, skill system, and self-evolution framework. Clarvis can run on Hermes as an alternative to the OpenClaw gateway.

## Key Differences from OpenClaw

| Aspect | Clarvis on OpenClaw | Clarvis on Hermes |
|--------|-------------------|------------------|
| **Runtime** | Node.js gateway (systemd) | Python CLI / programmatic |
| **Chat interface** | Telegram/Discord via gateway | Terminal CLI or programmatic API |
| **Model routing** | OpenRouter via gateway config | `~/.hermes/config.yaml` |
| **Session storage** | OpenClaw sessions | `~/.hermes/sessions/` (SQLite) |
| **Skills** | OpenClaw SKILL.md format | Hermes Skills Hub format |
| **Daemon mode** | `systemctl --user` | Not daemon by default |
| **Identity** | `SOUL.md` in workspace | `~/.hermes/SOUL.md` (auto-generated) |
| **Config** | `openclaw.json` | `~/.hermes/config.yaml` + `.env` |
| **Cron/autonomy** | System crontab (30+ jobs) | `hermes cron` (built-in scheduler) |

## Installation

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | 3.12 recommended |
| pip | 21+ | |
| git | 2.x | |
| SQLite | 3.35+ | FTS5 for session search |

### Install Steps

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
pip install -e .

# Configure model provider
hermes config set model "your-model"
hermes config set provider "openrouter"  # or ollama, anthropic, etc.

# Verify
hermes doctor    # Comprehensive diagnostic
hermes status    # Overview of config and services
```

### Migration from OpenClaw

Hermes includes a migration tool:
```bash
hermes claw migrate   # Import OpenClaw settings, memories, skills, API keys
```

## How to Use Clarvis on Hermes

### CLI Interaction

```bash
hermes chat              # Interactive chat session
hermes run "your task"   # One-shot task execution
hermes sessions list     # List saved sessions
```

**Important**: Use the `hermes` CLI (not `hermes-agent`) for programmatic use — `hermes` correctly reads `config.yaml`, while `hermes-agent` has flag-handling bugs (see Limitations below).

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

The Clarvis brain works identically on both harnesses — it reads from `CLARVIS_WORKSPACE`:

```bash
export CLARVIS_WORKSPACE=/path/to/clarvis/workspace
python3 -m clarvis brain search "query"
python3 -m clarvis brain health
```

## Limitations

### Known Issues

1. **`hermes-agent` CLI ignores flags** (HIGH): The `hermes-agent` entry point does not respect `--model`, `--base_url`, or `--api_key` flags. It auto-detects OAuth tokens from the environment instead.
   - **Workaround**: Use `hermes` CLI or invoke `python run_agent.py` directly with flags.

2. **Local models are slow** (MEDIUM): qwen3-vl:4b at ~7 tok/s on CPU cannot complete tool-calling loops in reasonable time. The model's thinking tokens consume the budget before producing content.
   - **Recommendation**: Use a faster model (qwen2.5:7b, llama3.2:3b) or a GPU, or route through OpenRouter.

3. **No headless `.env` setup** (LOW): `hermes setup` requires an interactive terminal. For headless/CI, manually create `~/.hermes/.env` or copy from `.env.example`.

4. **Auth token confusion** (LOW): Hermes auto-detects and stores Claude Code OAuth tokens in `~/.hermes/auth.json`, which may not work for Hermes itself.

### What's Not Available on Hermes

- **Telegram/Discord integration**: No built-in chat gateway — Hermes is CLI/programmatic only.
- **OpenClaw skills**: Clarvis's 19 OpenClaw-format skills don't directly port to Hermes Skills Hub.
- **systemd daemon mode**: Hermes doesn't run as a persistent service by default.
- **Cron autonomy**: While Hermes has `hermes cron`, the full 30+ job schedule from OpenClaw needs manual migration.

## Recommended Usage Patterns

### When to Use Hermes over OpenClaw

- **Development/testing**: Hermes's Python-native CLI is faster for iterating on Clarvis modules.
- **Programmatic integration**: Import Hermes as a Python library for embedding in other tools.
- **Local-only setups**: Hermes + Ollama works without any cloud API keys.
- **Profile isolation**: `hermes profile` enables running multiple agent personalities on one machine.

### When to Stay on OpenClaw

- **Production chat**: Telegram/Discord gateway is mature and stable.
- **Full autonomy**: The 30+ cron job schedule is battle-tested on OpenClaw.
- **Multi-model routing**: OpenClaw's gateway handles model routing centrally.

## Configuration Reference

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
