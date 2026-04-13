# Hermes Integration Status

**Last updated:** 2026-04-13
**Status:** EXPERIMENTAL
**Validated against:** hermes-agent 0.7.0 (NousResearch)

## What Works

| Feature | Status | Notes |
|---------|--------|-------|
| Clarvis spine (Python packages) | Working | All 12 core imports pass |
| CLI (`clarvis --help`, all subcommands) | Working | |
| Brain (ChromaDB + ONNX) | Working | Local, harness-independent |
| Heartbeat gate (zero-LLM) | Working | |
| Cron script syntax | Working | All scripts pass `bash -n` |
| HermesAdapter import + detection | Working | |
| Queue system (read/write) | Working | |
| Brain seed data | Working | Initial memories on fresh install |
| OpenRouter chat round-trip | Working | MiniMax M2.5 via direct API call |

## What Doesn't Work

### Upstream Issues (NousResearch/hermes-agent)

| Issue | Severity | Details |
|-------|----------|---------|
| `hermes-agent` CLI ignores flags | Critical | `--model`, `--base_url`, `--api_key` flags are silently ignored. Workaround: use `hermes` CLI instead |
| Provider detection fails for Ollama | Critical | `config.yaml` says `provider: ollama` but runtime logs "unknown provider 'ollama'" |
| Not on PyPI | High | `pip install hermes-agent` fails. Must install from source: `pip install git+https://github.com/NousResearch/hermes-agent.git` |
| Local model too slow | High | qwen3-vl:4b at ~7 tok/s on CPU = ~674s per tool-calling round-trip. Unusable for agent loops |
| Stream stalling | Medium | Connection killed after 180s of no chunks (observed in `.hermes/logs/errors.log`) |

### Not Implemented (Clarvis side)

| Feature | Status | Notes |
|---------|--------|-------|
| Cron autonomy via Hermes | Not built | `~/.hermes/cron/` exists but is empty. Autonomous tasks use system crontab, not Hermes scheduler |
| Telegram/Discord gateway | Not available | Hermes is CLI/programmatic only. No chat channel integration |
| OpenClaw skill porting | Not built | OpenClaw skills don't translate to Hermes Skills Hub format |
| Hermes GEPA self-evolution | Not tested | Hermes's optimizer pipeline not validated with Clarvis overlay |

## Working Path: `hermes` CLI with Provider Flags

The `hermes` CLI (not `hermes-agent`) works correctly when you pass the provider
and model directly. This bypasses the config.yaml provider detection issues:

```bash
# Single query with OpenRouter (confirmed working 2026-04-13):
OPENROUTER_API_KEY=sk-or-v1-... hermes chat -q "your question" \
    --provider openrouter -m "minimax/minimax-m2.5" --max-turns 1

# Interactive session:
OPENROUTER_API_KEY=sk-or-v1-... hermes chat --provider openrouter -m "model/name"
```

Supported providers (from `hermes chat --help`):
`auto`, `openrouter`, `nous`, `openai-codex`, `copilot-acp`, `copilot`,
`anthropic`, `huggingface`, `zai`, `kimi-coding`, `minimax`, `minimax-cn`, `kilocode`

**Important:** Use the `hermes` CLI (not `hermes-agent`) for all interaction.
The `hermes-agent` entry point ignores CLI flags (upstream bug).

## E2E Test Results (2026-04-13)

| Test | Checks | Pass | Fail | Warn | Skip | Verdict |
|------|--------|------|------|------|------|---------|
| `e2e_clarvis_on_hermes_fresh.sh --quick` | 37 | 33 | 0 | 0 | 4 | PASS |
| Direct API chat round-trip | 1 | 1 | 0 | 0 | 0 | PASS |
| `hermes chat -q ... --provider openrouter` | 1 | 1 | 0 | 0 | 0 | **PASS** (confirmed via `/tmp/hermes-venv`, MiniMax M2.5) |

## What a Real User Gets Today

1. **Install works** — `install.sh --profile hermes` completes, hermes-agent installed from source
2. **Brain works** — local vector memory, search, seed data all functional
3. **CLI works** — all `clarvis` subcommands available
4. **Chat works** — `hermes chat -q "..." --provider openrouter -m model/name` confirmed working
5. **Config.yaml provider detection** — unreliable (upstream). Use `--provider` flag per-session instead
6. **Autonomy** — not available (cron uses system crontab, not Hermes scheduler)
7. **Gateway** — not available (Hermes has no Telegram/Discord integration)

## Recommendation

For users who want a working Clarvis install today:
- Use **OpenClaw** profile if you need chat channels (Telegram/Discord)
- Use **Standalone** profile if you only need brain + CLI
- Use **Hermes** profile only if you specifically need the Hermes tool ecosystem
  and understand the EXPERIMENTAL limitations

The Hermes path is viable for Clarvis brain + CLI features. The upstream
`hermes-agent` issues make the Hermes-specific features (chat, tools, GEPA)
unreliable until NousResearch fixes the CLI flag handling and provider detection.
