# Install Friction Report — 2026-04-06

_Rolling engineering blocker report: what broke, why, workaround, fix owner, and release impact._
_For install guides, see `INSTALL.md`. For validation evidence, see `validation/`._

Based on: OpenClaw fresh install (2026-04-05), Hermes fresh install (2026-04-05), Clarvis overlay install (2026-04-06), isolated cron e2e tests (2026-04-06), and fresh-install smoke suite (2026-04-06).

---

## Executive Summary

**Clarvis overlay install works well.** Core imports, CLI, memory paths, cron wiring, and autonomous pipeline guards all pass in isolation (59/61 smoke checks, 19/19 e2e tests). The friction is concentrated in **harness integration** (OpenClaw/Hermes) and **model selection**, not in Clarvis itself.

| Install Path | Status | Blockers | Fix Owner | Release Impact |
|---|---|---|---|---|
| Clarvis standalone (venv) | **PASS** | None | — | Ship |
| Clarvis + OpenClaw | **PARTIAL** | Auth field mismatch, model OOM, health-check port | Upstream (OpenClaw) + Clarvis installer | Blocks "works on OpenClaw" claim |
| Clarvis + Hermes | **PARTIAL** | `hermes-agent` ignores CLI flags, model too slow | Upstream (Hermes) | Blocks "works on Hermes" claim |
| Cron/autonomy | **PASS** | All guards work in isolation; cron install is opt-in | — | Ship |
| Zero-API-key (local only) | **PASS** | Brain/imports/CLI all work; Ollama inference works | — | Ship |

---

## What Broke (CRITICAL — blocks "instant usable")

### 1. OpenClaw auth profile field name mismatch
**Symptom:** "No API key found for provider" after configuring auth profile.
**Root cause:** OpenClaw expects `key` field for `type: "api_key"` auth, but docs/intuition suggest `token`. Error message doesn't hint at correct field name.
**Impact:** Every new user hits this. Zero discoverability.
**Fix needed:** Document the correct field. Ideally, OpenClaw should accept both or give a clear error.

### 2. Hermes `hermes-agent` ignores CLI flags
**Symptom:** `hermes-agent --model X --base_url Y` silently ignores all flags, auto-detects a GitHub Copilot token, and returns 403 errors.
**Root cause:** The `hermes-agent` entry point has its own detection logic that bypasses config.yaml and CLI args. Only `python run_agent.py` works correctly.
**Impact:** The primary documented entry point doesn't work. Users must discover the workaround.
**Fix needed:** Upstream bug report or Clarvis wrapper that always uses `run_agent.py`.

### 3. Model OOM without pre-flight check
**Symptom:** qwen3-vl:4b claims 3.3 GB but actually needs 40.7 GB system memory on 32 GB machine. Ollama retries 4x before failing.
**Impact:** Wastes 5+ minutes on machines that can't run the model.
**Fix needed:** Pre-flight memory check before model pull/load. Recommend smaller models for < 16 GB RAM.

---

## What Required Manual Intervention (FRICTION — slows setup)

### 4. OpenClaw `--accept-risk` flag for non-interactive onboard
Not discoverable from `--help`. User must read error output to learn the flag exists.
**Automation:** Add to guided installer or document prominently.

### 5. OpenClaw health-check port hardcoded to 18789
`onboard` health check fails if gateway runs on non-default port. Workaround: `--skip-health`.
**Automation:** Guided installer should pass `--skip-health` when port differs.

### 6. PEP 668 EXTERNALLY-MANAGED on Ubuntu 24.04+
`pip install` fails in system Python. Install script handles this, but `setup.sh` requires user to have a venv active or `--break-system-packages`.
**Status:** Documented in INSTALL.md troubleshooting. `install.sh` handles it. `test_overlay_install.sh` sets `PIP_USER=0`.

### 7. CLAUDE.md not copied into isolated workspace
Smoke test `--isolated` mode: CLAUDE.md is WARN because it lives at repo root's parent (`../.openclaw/CLAUDE.md`), not in the workspace dir itself.
**Impact:** Minor — only affects isolated testing, not real installs.

### 8. Hermes `.env` requires interactive terminal
`hermes setup` needs a TTY. No non-interactive bootstrap path for CI/headless installs.
**Automation:** Clarvis installer should generate minimal `.env` for Hermes if needed.

---

## What Must Be Automated (QUEUE → GUIDED_INSTALLER)

| Item | Current State | Target |
|---|---|---|
| Auth profile creation | Manual JSON editing | `clarvis install` prompts for API key, writes correct field |
| Model selection | User must know RAM requirements | Pre-flight check: `clarvis install` validates model fits in RAM |
| Cron opt-in | `clarvis cron install <preset> --apply` | Guided installer asks "Enable autonomy? [y/N]" |
| Port conflict detection | Silent failure | Installer checks port availability before starting gateway |
| Hermes entry point workaround | User must discover `run_agent.py` | Clarvis wrapper detects Hermes and uses correct entry point |
| Post-install verification | `verify_install.sh` exists but manual | `clarvis install` runs verification automatically |

---

## What Works Well (no friction)

- **Core install:** `pip install -e .` resolves all deps, no conflicts (Python 3.12.3)
- **Import chain:** All 7 spine modules import cleanly, no eager ChromaDB loading (fixed 2026-04-06)
- **CLI:** `clarvis --help`, `clarvis brain --help`, `clarvis cron --help` all respond
- **Cron wiring:** All 28 cron scripts pass bash syntax check. `cron_env.sh` sources correctly with `CLARVIS_WORKSPACE` override. Lock acquisition, cleanup, and stale-lock reclamation all work.
- **Autonomous guards:** Empty-prompt rejection, short-task rejection, nesting guard — all pass
- **Prompt assembly:** 22/22 checks pass (context compression, brain search, queue extraction)
- **Zero-API-key mode:** Brain search uses local ONNX embeddings. No external API needed for core functionality.
- **Cron isolation:** Tests run in `/tmp` without touching production crontab. Lock files are PID-scoped with EXIT traps.

---

## Test Coverage Summary

| Test Suite | Checks | Pass | Fail | Warn |
|---|---|---|---|---|
| `fresh_install_smoke.sh --isolated` | 61 | 59 | 0 | 1 |
| `test_cron_isolated_e2e.py` | 19 | 19 | 0 | 0 |
| `test_overlay_install.sh` | 27 | 27 | 0 | 0 |
| `local_model_harness.sh test` | ~12 | 12 | 0 | 0 |
| OpenClaw fresh install (manual) | 7 | 5 | 2 | 0 |
| Hermes fresh install (manual) | 6 | 6 | 0 | 0 |

---

_Report generated from automated test runs on 2026-04-06. All test artifacts in `scripts/infra/`, `tests/`, and `memory/research/`.
Priority queue for fixes tracked in `memory/evolution/QUEUE.md` (E2E_* and INSTALL_* items)._
