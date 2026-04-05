# Install Matrix — Validation Targets

> Defines the supported install paths, prerequisites, local-model-only mode, and pass/fail
> criteria for "usable without extra hassle." Each path is independently testable.

## Install Paths

### Path A: Fresh OpenClaw Install (no Clarvis)

**What:** Install OpenClaw from scratch on a clean machine (or isolated dir), verify the
gateway boots and basic chat works with a local model only (no API keys).

**Prerequisites:**
| Requirement | Version | Notes |
|-------------|---------|-------|
| Node.js | 22+ | `nvm install 22` or system package |
| npm | 10+ | Comes with Node.js |
| Linux/macOS/WSL2 | Any | systemd optional (for daemon mode) |

**Install steps:**
```bash
curl -fsSL https://openclaw.ai/install.sh | bash
# OR: npm install -g openclaw@latest
openclaw onboard --install-daemon
```

**Local-model-only mode:**
- Configure `openclaw.json` → `agents.defaults.model` to use Ollama endpoint
- Model: `ollama/qwen3-vl:4b` (3.3 GB) or any Ollama-served model
- Set `auth.profiles` to empty (no OpenRouter/OpenAI keys)
- Gateway should still boot and accept chat via localhost

**Pass/fail criteria:**
| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 1 | `openclaw` CLI responds to `--help` | Output shown | Command not found |
| 2 | `openclaw onboard` completes without error | Exits 0 | Crash or hang |
| 3 | Gateway starts on configured port | HTTP 200 on health endpoint | Connection refused |
| 4 | Send a chat message, get a response | Any coherent reply | Timeout or error |
| 5 | `openclaw.json` is created and valid JSON | Parseable | Missing or corrupt |
| 6 | No API key required for local-model path | Chat works with Ollama only | Requires external key |
| 7 | Clean shutdown (`Ctrl-C` or `systemctl stop`) | Exits cleanly | Orphan process |

---

### Path B: Fresh Hermes Agent Install (NousResearch)

**What:** Install NousResearch/hermes-agent from scratch in an isolated location. Verify
the harness boots, session basics work, and self-evolution pipeline can run.

**Prerequisites:**
| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | 3.12 recommended |
| pip | 21+ | |
| git | 2.x | For cloning |
| SQLite | 3.35+ | FTS5 for session search |

**Install steps:**
```bash
git clone https://github.com/NousResearch/hermes-agent.git /tmp/hermes-test
cd /tmp/hermes-test
pip install -e .
# Follow README for model configuration
```

**Local-model-only mode:**
- Hermes supports local Ollama models via config
- No API key needed for basic harness operation
- Self-evolution (GEPA optimizer) requires LLM access — may need at minimum a local model

**Pass/fail criteria:**
| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 1 | `pip install -e .` completes | Exits 0 | Dependency error |
| 2 | Main entry point responds | Help or REPL | ImportError |
| 3 | Session can be created and persisted | Session file written | Crash |
| 4 | System prompt is loaded | Non-empty | Missing/empty |
| 5 | Basic chat round-trip (with local model) | Response received | Timeout |
| 6 | No hardcoded paths assume specific user/dir | Works in /tmp | Path error |

---

### Path C: Clarvis-on-Top Install (layered onto OpenClaw)

**What:** Starting from a working OpenClaw install (Path A), layer Clarvis on top.
Verify the Python spine, brain, CLI, and cron schedule work without breaking the
underlying OpenClaw gateway.

**Prerequisites:**
| Requirement | Version | Notes |
|-------------|---------|-------|
| Working OpenClaw (Path A) | Any | Gateway must be running |
| Python | 3.10+ | 3.12 recommended |
| pip | 21+ | |
| SQLite | 3.35+ | For graph backend |
| Disk | 2 GB+ | Brain data + ONNX model |
| RAM | 4 GB+ | ChromaDB + ONNX embeddings in memory |

**Install steps:**
```bash
cd ~/.openclaw/  # or wherever OpenClaw lives
git clone https://github.com/GranusClarvis/clarvis.git workspace
cd workspace
bash scripts/infra/install.sh --profile openclaw
# OR for full autonomous layer:
bash scripts/infra/install.sh --profile fullstack
```

**Local-model-only mode:**
- Brain (ChromaDB + ONNX) is fully local — no API needed
- CLI commands (`clarvis brain`, `clarvis demo`) work offline
- Cron jobs that spawn Claude Code need API access (not local-model-compatible)
- Heartbeat gate/preflight are zero-LLM and work locally
- Use `clarvis cron install minimal --apply` for local-only cron (no LLM spawning)

**Pass/fail criteria:**
| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 1 | `bash scripts/infra/install.sh` completes | Exits 0 | Error |
| 2 | `bash scripts/infra/verify_install.sh` passes | 0 failures | Any FAIL |
| 3 | `clarvis demo` runs end-to-end | Output shows store+recall | Crash |
| 4 | `clarvis brain health` reports OK | Health pass | Error |
| 5 | OpenClaw gateway still works after install | Chat functional | Gateway broken |
| 6 | `clarvis cron install minimal --apply` succeeds | Cron entries visible | Error |
| 7 | Cron jobs don't interfere with gateway | Both run independently | Conflicts |
| 8 | `pytest tests/test_open_source_smoke.py` passes | All green | Failures |

---

## Test Execution Order

Run paths sequentially — each validates a prerequisite for the next:

```
Path A (OpenClaw) → verify gateway works
       ↓
Path C (Clarvis-on-top) → verify overlay doesn't break gateway
       ↓
Path B (Hermes) → independent, run anytime for comparison
```

## Isolation Requirements

Each test MUST run in an isolated environment to avoid contaminating the production system:

| Aspect | Requirement |
|--------|-------------|
| Install directory | `/tmp/clarvis-install-test/` or `/opt/clarvis-test/` — NOT `/home/agent/.openclaw/` |
| npm prefix | `--prefix /tmp/test-npm-global` to avoid overwriting global openclaw |
| Python venv | `python3 -m venv /tmp/test-venv` for pip isolation |
| Crontab | Do NOT modify system crontab — use `--dry-run` or a test user |
| Ports | Use non-default port (e.g., 28789) to avoid conflicting with production gateway |
| Brain data | Separate `CLARVIS_WORKSPACE` pointing to test dir |
| systemd | Skip or use `--user` with test unit name |

## Local-Model-Only Test Mode

For zero-API-key validation:

1. Start Ollama: `systemctl --user start ollama.service`
2. Ensure model available: `ollama list` (need at least `qwen3-vl:4b`)
3. Configure endpoints to `http://127.0.0.1:11434`
4. Set `OPENROUTER_API_KEY=""` and `ANTHROPIC_API_KEY=""` explicitly
5. Every pass/fail criterion above must work in this mode (except explicitly noted LLM-dependent features)

## Definition of "Usable Without Extra Hassle"

An install path passes the "usable" bar if:
1. **Zero manual JSON editing** — installer handles config creation
2. **No hidden dependencies** — all requirements caught by prereq check or clear error
3. **First command works** — `clarvis demo` or equivalent succeeds immediately after install
4. **Clear error on missing optional** — e.g., "ChromaDB not installed, brain features disabled" rather than a traceback
5. **Uninstall is clean** — removing the install leaves no orphan processes, cron entries, or broken system state
