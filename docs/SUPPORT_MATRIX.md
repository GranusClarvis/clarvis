# Support Matrix — Clarvis

> **Last validated:** 2026-04-06 (smoke suite + manual harness tests)
> **Last updated:** 2026-04-11
> **Commit:** See `git log --oneline -1` at time of validation
>
> This document is the **single source of truth** for what Clarvis supports.
> Every claim in README, INSTALL.md, or the website must be traceable to a row below.
> If it's not in this matrix, we don't claim it.

---

## Support Levels

| Level | Meaning | What we promise |
|-------|---------|-----------------|
| **SUPPORTED** | Tested, reproducible, automated regression | Works on fresh install. Bugs get fixed. |
| **PARTIAL** | Works with documented workarounds | Functional but has known friction. Workarounds documented below. |
| **EXPERIMENTAL** | May work, not regularly tested | No guarantees. May break between releases. |
| **UNSUPPORTED** | Known broken or never tested | Do not use. No fix planned unless demand arises. |

---

## Install Path Matrix

| Install Path | Level | Evidence | Blocker Summary |
|---|---|---|---|
| **Clarvis standalone** (venv, no harness) | **SUPPORTED** | 59/61 smoke, 27/27 overlay, 19/19 cron e2e | None. Core path. |
| **Clarvis + OpenClaw** (overlay) | **PARTIAL** | 5/7 manual checks pass | Auth field mismatch (upstream), health-check port hardcoded (upstream) |
| **Clarvis + Hermes** (overlay) | **EXPERIMENTAL** | 6/6 Hermes criteria pass, but CLI flags broken | `hermes-agent` ignores CLI flags (upstream), model too slow on CPU |
| **Zero-API-key** (local Ollama only) | **SUPPORTED** | 12/12 local model harness | Brain, CLI, imports all work locally. Cron/autonomy needs API. |
| **Docker** | **UNSUPPORTED** | No Dockerfile exists | Not tested, not packaged. |
| **Windows native** | **UNSUPPORTED** | Never tested | Use WSL2 instead. |
| **macOS** | **EXPERIMENTAL** | Not regularly tested | Should work (Python + SQLite), but no CI coverage. |

---

## Feature Matrix

### Core Features (harness-independent)

| Feature | Standalone | OpenClaw | Hermes | Local-Only | Notes |
|---|---|---|---|---|---|
| `pip install -e .` | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | Python 3.10-3.12 tested |
| Core spine imports (12 modules) | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | No eager ChromaDB load |
| `clarvis` CLI (`--help`, `brain`, `cron`) | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | |
| Brain (ChromaDB + ONNX embeddings) | **SUPPORTED** | **SUPPORTED** | **PARTIAL** | **SUPPORTED** | Hermes: works but not integrated into Hermes session flow |
| Brain search (semantic, local) | **SUPPORTED** | **SUPPORTED** | **PARTIAL** | **SUPPORTED** | Same caveat as above |
| Graph backend (SQLite+WAL) | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | |
| Queue read/write | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | |
| `clarvis demo` (store+recall) | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | |
| Heartbeat gate (zero-LLM) | **SUPPORTED** | **SUPPORTED** | N/A | **SUPPORTED** | |
| Heartbeat preflight+postflight | **SUPPORTED** | **SUPPORTED** | N/A | **PARTIAL** | Needs LLM for task execution |
| Performance benchmark (PI) | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | |
| Cost tracking | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | |

### Harness-Specific Features

| Feature | Standalone | OpenClaw | Hermes | Local-Only | Notes |
|---|---|---|---|---|---|
| Gateway chat (Telegram/Discord) | N/A | **PARTIAL** | N/A | N/A | Auth field mismatch blocker |
| Cron schedule (minimal preset) | N/A | **SUPPORTED** | N/A | N/A | `--dry-run` default, safe |
| Cron schedule (recommended/full) | N/A | **SUPPORTED** | N/A | N/A | Requires Claude Code API key |
| Autonomous evolution (heartbeat loop) | N/A | **SUPPORTED** | **EXPERIMENTAL** | N/A | Hermes: no integration tested |
| Spawn Claude Code from harness | N/A | **SUPPORTED** | **UNSUPPORTED** | N/A | Hermes has no spawn path |
| Browser automation | N/A | **PARTIAL** | N/A | N/A | CDP-dependent, session fragile |
| Telegram bot integration | N/A | **PARTIAL** | N/A | N/A | Works but requires manual config |
| Hermes session management | N/A | N/A | **PARTIAL** | N/A | Works via `hermes` CLI, not `hermes-agent` |
| Hermes GEPA self-evolution | N/A | N/A | **EXPERIMENTAL** | N/A | Needs fast LLM, untested with Clarvis |
| systemd service management | N/A | **SUPPORTED** | N/A | N/A | Linux only |
| Project agent orchestration | N/A | **SUPPORTED** | **UNSUPPORTED** | N/A | Tested only on OpenClaw path |

---

## Known Blockers (open, affect support claims)

| # | Blocker | Severity | Affects | Owner | Workaround |
|---|---------|----------|---------|-------|------------|
| 1 | OpenClaw auth field expects `key` not `token` | CRITICAL | OpenClaw path | Upstream | Use `key` field in auth profile JSON |
| 2 | `hermes-agent` CLI ignores `--model`, `--base_url` flags | CRITICAL | Hermes path | Upstream | Use `python run_agent.py` or `hermes` CLI instead |
| 3 | qwen3-vl:4b needs 40.7 GB RAM (not 3.3 GB as listed) | HIGH | Local-only on <64 GB | Clarvis installer | Use smaller model; add pre-flight RAM check |
| 4 | `--accept-risk` flag undiscoverable in `--help` | MEDIUM | OpenClaw onboard | Upstream | Document prominently |
| 5 | Health-check port hardcoded to 18789 | MEDIUM | OpenClaw non-default port | Upstream | Pass `--skip-health` |
| 6 | PEP 668 on Ubuntu 24.04+ | LOW | System Python installs | Clarvis | Use venv (installer handles this) |
| 7 | Hermes `.env` requires interactive TTY | MEDIUM | Hermes headless/CI | Clarvis wrapper | Generate `.env` programmatically |
| 8 | Hermes model too slow on CPU for agent loop | MEDIUM | Hermes local-only | User | Use GPU or faster model |

---

## What We Explicitly Do NOT Support

These are not bugs — they are conscious scope boundaries:

1. **Docker deployment** — No Dockerfile. No plans unless community demand.
2. **Windows native** — Not tested, not planned. WSL2 is the path.
3. **Python < 3.10** — Hard requirement (match statements, type hints).
4. **Hermes as primary harness** — Experimental overlay only. OpenClaw is the reference.
5. **Multi-user / multi-tenant** — Clarvis is single-operator by design.
6. **Cloud-hosted brain** — ChromaDB is local-only. No remote vector DB support.
7. **Automatic API key setup** — User must provide their own keys manually.
8. **GPU-accelerated embeddings** — ONNX MiniLM runs CPU-only. Fast enough (~269ms avg).
9. **Non-Linux cron schedule** — systemd + crontab is Linux-only. macOS launchd not tested.
10. **Hermes + Claude Code spawning** — No integration path exists.

---

## Test Evidence Summary

| Test Suite | Checks | Pass | Fail | Warn | Date |
|---|---|---|---|---|---|
| `fresh_install_smoke.sh --isolated` | 61 | 59 | 0 | 1 | 2026-04-06 |
| `test_overlay_install.sh` | 27 | 27 | 0 | 0 | 2026-04-06 |
| `test_cron_isolated_e2e.py` | 19 | 19 | 0 | 0 | 2026-04-06 |
| `local_model_harness.sh test` | 12 | 12 | 0 | 0 | 2026-04-06 |
| OpenClaw fresh install (manual) | 7 | 5 | 2 | 0 | 2026-04-05 |
| Hermes fresh install (manual) | 6 | 6 | 0 | 0 | 2026-04-05 |
| `test_open_source_smoke.py` | varies | all | 0 | 0 | 2026-04-06 |

**Total automated checks: 119+ pass, 0 fail, 1 warn.**
Manual harness checks: 11/13 pass (2 OpenClaw blockers from upstream).

---

## How to Re-Validate

```bash
# Individual gates (recommended before any release claim)
bash scripts/infra/release_gate_openclaw.sh    # OpenClaw claim gate
bash scripts/infra/release_gate_hermes.sh      # Hermes claim gate
bash scripts/infra/fresh_install_smoke.sh      # Core smoke (no harness)
```

---

## Updating This Document

When you change support status:
1. Run the relevant gate script and record results
2. Update the matrix row with new level and evidence
3. Update "Last validated" date at the top
4. If downgrading: update README/INSTALL.md claims to match
5. If upgrading: link to the validation report in `docs/validation/`

---

_See also: [INSTALL.md](INSTALL.md) (how to install), [INSTALL_MATRIX.md](INSTALL_MATRIX.md) (validation criteria),
[INSTALL_FRICTION_REPORT.md](INSTALL_FRICTION_REPORT.md) (engineering blockers),
[E2E_RELEASE_VALIDATION_PLAN.md](E2E_RELEASE_VALIDATION_PLAN.md) (full validation procedure)._
