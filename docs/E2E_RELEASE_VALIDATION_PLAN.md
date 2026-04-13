# E2E Release Validation Plan

> Consolidated execution plan for full end-to-end release validation.
> Sources: `INSTALL_MATRIX.md` (criteria), `INSTALL_FRICTION_REPORT.md` (known blockers),
> `INSTALL.md` (profiles), and test scripts in `scripts/infra/` and `tests/`.
>
> **Purpose:** Before any public release claim ("works on X"), run this plan. Every path
> must pass its mandatory gates. Partial results downgrade the claim, not skip the test.

---

## 1. Validation Environments

### ENV-A: Fresh OpenClaw (isolated)

| Property | Value |
|----------|-------|
| Root dir | `/tmp/clarvis-e2e-openclaw-XXXXXX/` (mktemp) |
| npm prefix | `$ROOT/npm-global` |
| Node.js | 22+ (system or nvm) |
| Gateway port | **28789** (non-default, avoids production 18789) |
| API keys | None — local-model-only via Ollama |
| Crontab | **Never touched** — `--dry-run` only |
| systemd | Skip or `--user` with test-specific unit name |
| Cleanup | `rm -rf $ROOT` on exit (trap EXIT) |

### ENV-B: Fresh Hermes Agent (isolated)

| Property | Value |
|----------|-------|
| Root dir | `/tmp/clarvis-e2e-hermes-XXXXXX/` (mktemp) |
| Python | venv at `$ROOT/venv` |
| Config | `$ROOT/hermes-test/.env` — generated non-interactively |
| Model | Ollama `qwen3-vl:4b` via `http://127.0.0.1:11434` |
| Entry point | `python run_agent.py` (NOT `hermes-agent` — see Known Blocker #2) |
| Crontab | **Never touched** |
| Cleanup | `rm -rf $ROOT` on exit |

### ENV-C: Clarvis-on-OpenClaw Overlay (isolated)

| Property | Value |
|----------|-------|
| Root dir | `/tmp/clarvis-e2e-overlay-XXXXXX/` (mktemp) |
| Base | Passing ENV-A install (gateway running on 28789) |
| Python | venv at `$ROOT/venv` |
| `CLARVIS_WORKSPACE` | `$ROOT/workspace` (NOT `/home/agent/.openclaw/workspace`) |
| Brain data | `$ROOT/workspace/data/clarvisdb/` (fresh, empty) |
| Crontab | `--dry-run` only |
| Cleanup | Stop gateway, `rm -rf $ROOT` on exit |

### ENV-D: Clarvis-on-Hermes Overlay (isolated)

| Property | Value |
|----------|-------|
| Root dir | `/tmp/clarvis-e2e-hermes-overlay-XXXXXX/` (mktemp) |
| Base | Passing ENV-B install |
| Python | Same venv as ENV-B (`$ROOT/venv`) |
| `CLARVIS_WORKSPACE` | `$ROOT/workspace` |
| Brain data | Fresh, empty |
| Crontab | **Never touched** |
| Cleanup | `rm -rf $ROOT` on exit |

---

## 2. Isolation Guards (Mandatory Pre-Flight)

Every test script MUST source `scripts/infra/isolation_guard.sh` before any work.
The guard aborts with exit 1 if any of these conditions are true:

| Check | Condition | Why |
|-------|-----------|-----|
| Production workspace | `CLARVIS_WORKSPACE` is `/home/agent/.openclaw/workspace` or unset | Would corrupt live brain/memory |
| Production port | Gateway target port is `18789` | Would conflict with live gateway |
| Production crontab | Script attempts `crontab -` without `--dry-run` | Would overwrite live cron |
| Production auth | Script reads/writes `~/.openclaw/agents/*/auth.json` | Would leak/overwrite credentials |
| Missing temp root | `$ROOT` doesn't start with `/tmp/` or `/opt/clarvis-test/` | Sanity check |
| Nesting guard | `CLARVIS_E2E_ISOLATED` env var not set to `1` | Prevents accidental runs |

---

## 3. Execution Order

```
Phase 1: Isolation infrastructure
  └── Verify isolation_guard.sh exists and works (self-test)

Phase 2: Base harness installs (can run in parallel)
  ├── ENV-A: Fresh OpenClaw install → gate A
  └── ENV-B: Fresh Hermes install → gate B

Phase 3: Overlay installs (sequential, depend on Phase 2)
  ├── ENV-C: Clarvis-on-OpenClaw → gate C (requires gate A pass)
  └── ENV-D: Clarvis-on-Hermes → gate D (requires gate B pass)

Phase 4: Cross-cutting validation
  ├── Local-model-only mode (on ENV-C and ENV-D)
  ├── Feature matrix generation
  └── Known-limitations reconciliation

Phase 5: Release gate decision
  └── Aggregate results → RELEASE_VALIDATION_SUMMARY.md
```

---

## 4. Pass/Fail Gates

### Gate A: Fresh OpenClaw

| # | Criterion | Mandatory | Test Command | Pass | Fail |
|---|-----------|-----------|--------------|------|------|
| A1 | CLI responds | YES | `openclaw --help` | Output shown | Command not found |
| A2 | Onboard completes | YES | `openclaw onboard --accept-risk` | Exit 0 | Crash/hang |
| A3 | Config created | YES | `cat $ROOT/openclaw.json \| python3 -m json.tool` | Valid JSON | Missing/corrupt |
| A4 | Gateway boots | YES | `curl -s http://localhost:28789/health` | HTTP 200 | Connection refused |
| A5 | Chat round-trip | YES | Send message via API, get response | Coherent reply | Timeout/error |
| A6 | No API key needed | YES | `OPENROUTER_API_KEY="" ANTHROPIC_API_KEY=""` + chat | Works with Ollama | Requires key |
| A7 | Clean shutdown | YES | `kill $GW_PID; wait` | Exit 0, no orphans | Orphan process |

**Known blockers (from Friction Report):**
- Blocker #1: Auth field expects `key` not `token` — test must use correct field
- Blocker #4: `--accept-risk` needed for non-interactive onboard
- Blocker #5: Health-check port hardcoded — use `--skip-health` if non-default port

### Gate B: Fresh Hermes

| # | Criterion | Mandatory | Test Command | Pass | Fail |
|---|-----------|-----------|--------------|------|------|
| B1 | pip install | YES | `pip install -e .` | Exit 0 | Dependency error |
| B2 | Entry point | YES | `python run_agent.py --help` | Help shown | ImportError |
| B3 | Config bootstrap | YES | Generate `.env` non-interactively | File created | Requires TTY |
| B4 | Session create | NO | Create + persist session | File written | Crash |
| B5 | System prompt | YES | Load system prompt | Non-empty | Missing |
| B6 | No hardcoded paths | YES | Run from `/tmp` | Works | Path error |

**Known blockers:**
- Blocker #2: `hermes-agent` CLI ignores flags — use `python run_agent.py` instead
- Blocker #3: Model OOM — pre-check RAM before loading
- Blocker #8: `.env` requires TTY — generate programmatically

### Gate C: Clarvis-on-OpenClaw Overlay

| # | Criterion | Mandatory | Test Command | Pass | Fail |
|---|-----------|-----------|--------------|------|------|
| C1 | Install script | YES | `bash scripts/infra/install.sh --profile openclaw` | Exit 0 | Error |
| C2 | Verify script | YES | `bash scripts/infra/verify_install.sh` | 0 failures | Any FAIL |
| C3 | Core imports | YES | Import 12 spine modules | All succeed | Any ImportError |
| C4 | CLI responds | YES | `clarvis --help` | Output | Error |
| C5 | Brain health | YES | `clarvis brain health` | OK | Error |
| C6 | Demo flow | YES | `clarvis demo` | Store+recall works | Crash |
| C7 | Gateway survives | YES | `curl http://localhost:28789/health` | Still HTTP 200 | Broken |
| C8 | Cron dry-run | YES | `clarvis cron install minimal` | Shows entries (dry-run is default) | Error |
| C9 | Smoke suite | YES | `fresh_install_smoke.sh --isolated` | 0 FAIL | Any FAIL |
| C10 | Overlay test | YES | `test_overlay_install.sh` | 0 FAIL | Any FAIL |
| C11 | Open-source smoke | NO | `pytest tests/test_open_source_smoke.py` | All green | Failures |

### Gate D: Clarvis-on-Hermes Overlay

| # | Criterion | Mandatory | Test Command | Pass | Fail |
|---|-----------|-----------|--------------|------|------|
| D1 | Install script | YES | `bash scripts/infra/install.sh --profile hermes` | Exit 0 | Error |
| D2 | Core imports | YES | Import spine modules in Hermes venv | All succeed | ImportError |
| D3 | CLI responds | YES | `clarvis --help` | Output | Error |
| D4 | Brain health | NO | `clarvis brain health` | OK | Error (acceptable if no ChromaDB) |
| D5 | Persona integration | NO | Hermes loads Clarvis system prompt | Clarvis persona active | Falls back to default |
| D6 | Memory access | NO | `clarvis brain search "test"` | Results or empty OK | Crash |
| D7 | Hermes still works | YES | `python run_agent.py` still responds | Works | Broken by overlay |

---

## 5. Mandatory Features by Harness

Features that MUST work for a harness to be publicly claimed as "supported":

| Feature | Standalone | OpenClaw | Hermes | Local-Only |
|---------|-----------|----------|--------|------------|
| `pip install -e .` | YES | YES | YES | YES |
| Core imports (12 modules) | YES | YES | YES | YES |
| `clarvis` CLI | YES | YES | YES | YES |
| Brain (ChromaDB + ONNX) | YES | YES | PARTIAL | YES |
| Brain search (local embeddings) | YES | YES | PARTIAL | YES |
| Queue access | YES | YES | YES | YES |
| Heartbeat gate (zero-LLM) | YES | YES | N/A | YES |
| Cron (minimal preset) | N/A | YES | N/A | N/A |
| Cron (full/recommended) | N/A | YES | N/A | N/A |
| Gateway chat | N/A | YES | N/A | N/A |
| Autonomous evolution | N/A | YES | EXPERIMENTAL | N/A |
| Browser flows | N/A | YES | N/A | N/A |
| Telegram messaging | N/A | YES | N/A | N/A |
| Hermes session mgmt | N/A | N/A | YES | N/A |
| Zero-API-key operation | YES | YES | PARTIAL | YES |

Legend: YES = must pass, PARTIAL = works with caveats, EXPERIMENTAL = may not work, N/A = not applicable.

---

## 6. Test Scripts Inventory

| Script | Coverage | Used In |
|--------|----------|---------|
| `scripts/infra/fresh_install_smoke.sh` | 61 checks: imports, CLI, memory, brain, cron, autonomous, prompt, first-use | Gate C (C9) |
| `scripts/infra/local_model_harness.sh` | ~12 checks: Ollama service, API, model, inference, smoke | Phase 4 local-model |
| `tests/test_overlay_install.sh` | 27 checks: venv, pip, imports, CLI, verify, brain, setup, install | Gate C (C10) |
| `tests/test_cron_isolated_e2e.py` | 19 checks: cron wiring, locks, guards | Gate C (cron) |
| `tests/test_open_source_smoke.py` | Open-source readiness | Gate C (C11) |
| `tests/test_hermes_overlay.sh` | ~15 checks: Hermes+Clarvis coexistence, adapter, brain, CLI | Gate D |
| `scripts/infra/isolation_guard.sh` | Pre-flight safety — blocks production access | All gates |

---

## 7. Known Blockers & Workarounds

Carried forward from `INSTALL_FRICTION_REPORT.md` (2026-04-06):

| # | Blocker | Severity | Workaround | Owner | Status |
|---|---------|----------|------------|-------|--------|
| 1 | OpenClaw auth field `key` vs `token` | CRITICAL | Use `key` field explicitly | Upstream | Open |
| 2 | `hermes-agent` ignores CLI flags | CRITICAL | Use `python run_agent.py` | Upstream | Open |
| 3 | Model OOM (qwen3-vl:4b needs 40.7 GB) | HIGH | Pre-flight RAM check; use smaller model on <16 GB | Clarvis installer | Open |
| 4 | `--accept-risk` not in `--help` | MEDIUM | Document prominently | Upstream | Open |
| 5 | Health-check port hardcoded 18789 | MEDIUM | `--skip-health` on non-default port | Upstream | Open |
| 6 | PEP 668 on Ubuntu 24.04+ | LOW | `install.sh` handles it; use venv | Clarvis | Mitigated |
| 7 | CLAUDE.md not in isolated workspace | LOW | Copy manually in test setup | Clarvis | Accepted |
| 8 | ~~Hermes `.env` requires TTY~~ | ~~MEDIUM~~ | ~~Generate `.env` programmatically~~ | ~~Clarvis wrapper~~ | **FIXED** (2026-04-12) |

---

## 8. Release Gate Decision Matrix

After running all phases, aggregate results:

| Outcome | Criteria | Public Claim Allowed |
|---------|----------|---------------------|
| **FULL PASS** | All mandatory gates pass (A+C or B+D) | "Fully supported on [harness]" |
| **PARTIAL** | All mandatory gates pass with documented workarounds | "Supported with known limitations" |
| **EXPERIMENTAL** | Some mandatory gates fail, non-mandatory mostly pass | "Experimental support" |
| **UNSUPPORTED** | Multiple mandatory gates fail | No public claim; remove from docs |

Write results to `docs/validation/RELEASE_VALIDATION_SUMMARY.md` with:
- Date, commit SHA, operator
- Per-gate pass/fail with evidence (log snippets or exit codes)
- Aggregate status per harness
- Delta from previous validation run

---

## 9. Running the Full Validation

```bash
# Prerequisites
# 1. Ollama running with qwen3-vl:4b (or suitable local model)
# 2. Node.js 22+ available
# 3. Python 3.10+ available
# 4. At least 8 GB RAM free

# Full run (sequential, ~30 min)
bash scripts/infra/e2e_release_validation.sh --all

# Individual paths
bash scripts/infra/e2e_release_validation.sh --path-a    # OpenClaw only
bash scripts/infra/e2e_release_validation.sh --path-c    # Clarvis overlay (needs --path-a first)
bash scripts/infra/e2e_release_validation.sh --path-b    # Hermes only
bash scripts/infra/e2e_release_validation.sh --path-d    # Clarvis-on-Hermes (needs --path-b first)

# Dry-run (prints what would execute, no temp dirs)
bash scripts/infra/e2e_release_validation.sh --dry-run
```

---

_Consolidated 2026-04-11 from: `INSTALL_MATRIX.md`, `INSTALL_FRICTION_REPORT.md`, `INSTALL.md`._
_HERMES_FRESH_INSTALL_REPORT.md referenced in queue but does not exist — Hermes criteria derived from INSTALL_MATRIX.md Path B and Friction Report._
