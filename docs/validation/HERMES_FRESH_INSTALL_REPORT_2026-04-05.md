# Hermes Agent Fresh Install Report

> **Date:** 2026-04-05
> **Install Path:** B (NousResearch/hermes-agent, isolated)
> **Location:** `/tmp/hermes-test` (venv: `/tmp/hermes-venv`)
> **Version:** hermes-agent 0.7.0 (2026.4.3)
> **Local Model:** Ollama qwen3-vl:4b (3.3 GB, CPU-only)

## Pass/Fail Matrix (from INSTALL_MATRIX.md)

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | `pip install -e .` completes | **PASS** | Clean install, all 60+ deps resolved, 0 errors |
| 2 | Main entry point responds | **PASS** | `hermes --help` shows full CLI, `hermes-agent --help` initializes agent |
| 3 | Session can be created and persisted | **PASS** | `~/.hermes/sessions/` created, `hermes sessions list` works |
| 4 | System prompt is loaded | **PASS** | `SOUL.md` auto-generated with default Hermes persona |
| 5 | Basic chat round-trip (local model) | **PASS** | Ollama round-trip works via `python run_agent.py` (674s for "Say hello" — 28 tools = 5166 tokens context). `hermes-agent` entry point ignores flags (bug), but direct invocation works. Response: "Hello! How can I assist you today?" |
| 6 | No hardcoded paths assume specific user/dir | **PASS** | Grep found 0 hardcoded `/home/agent` paths in agent module |

## Setup Friction Points

### FRICTION-1: `hermes-agent` CLI ignores flags (HIGH)
The `hermes-agent` (run_agent.py) entry point does not respect `--model`, `--base_url`, or `--api_key` flags passed via CLI. It auto-detects a GitHub Copilot OAuth token from the environment and uses that instead. The `hermes` CLI (hermes_cli/) correctly reads `~/.hermes/config.yaml` — the two entry points have divergent config resolution.

**Impact:** Users trying `hermes-agent` with local models hit a 403 error immediately.
**Workaround:** Use `python run_agent.py --query "..." --model "qwen3-vl:4b" --base_url "http://127.0.0.1:11434/v1" --api_key "ollama"` directly (works), or use `hermes` CLI which reads config.yaml.

### FRICTION-2: qwen3-vl:4b too slow for agent loop (MEDIUM)
At ~7 tok/s on CPU, qwen3-vl:4b cannot complete a tool-calling round-trip within reasonable time. The model uses reasoning/thinking tokens by default (Qwen3 behavior), consuming the token budget before producing content. A 100-token request times out after 120s.

**Impact:** Local-model-only testing is impractical with the only available Ollama model.
**Recommendation:** Need a faster non-thinking model (e.g., qwen2.5:7b, llama3.2:3b) or GPU.

### FRICTION-3: No `.env` file auto-created (LOW)
`hermes doctor` flags missing `.env` file, but `hermes setup` requires interactive terminal. No non-interactive way to create a minimal `.env` for headless/CI setups.

**Workaround:** `touch ~/.hermes/.env` or copy from `.env.example`.

### FRICTION-4: Auth file auto-populated from Claude Code session (LOW)
The install auto-detected and stored a Claude Code Anthropic OAuth token in `~/.hermes/auth.json`. This is convenient but surprising — the token appears without user action, and hermes-agent tried to use a GitHub Copilot token from the environment.

**Impact:** Confusing error messages when the auto-detected tokens don't work for Hermes.

## What Worked Well

1. **Clean dependency resolution** — `pip install -e .` with no conflicts, 60+ packages
2. **`hermes doctor`** — comprehensive diagnostic output, clear actionable suggestions
3. **`hermes config set`** — simple config management, correctly writes config.yaml
4. **`hermes status`** — clean overview showing model, provider, services, sessions
5. **`hermes skills list`** — works immediately, Skills Hub ready
6. **Directory structure** — `~/.hermes/` auto-created with correct subdirs (sessions, logs, memories, cron)
7. **SOUL.md auto-generated** — default persona ready without manual config
8. **No hardcoded paths** — clean isolation, works from `/tmp`
9. **`hermes version`** — shows update availability, useful for maintenance

## Hidden Dependencies Discovered

- `exa-py`, `firecrawl-py`, `parallel-web`, `fal-client` are core deps (not optional) — these are web/image tools that require API keys to actually use
- `edge-tts` (TTS) is a core dep — works without API key (uses Microsoft Edge TTS)
- `prompt_toolkit` — interactive terminal dep, not needed for headless/gateway use

## Recommendations for Clarvis Integration

1. **Use `hermes` CLI** (not `hermes-agent`) for programmatic interaction — it respects config.yaml
2. **Install a faster Ollama model** for local testing (qwen2.5:7b or llama3.2:3b recommended)
3. **The migration path exists:** `hermes claw migrate` can import OpenClaw settings, memories, skills, and API keys
4. **Profile isolation** (`hermes profile`) could enable running Hermes alongside production Clarvis without conflict
5. **Config.yaml is the truth** — `~/.hermes/config.yaml` controls model/provider; `.env` only for API keys
