# Release Validation Summary

> **Date:** 2026-04-13
> **Base commit:** 2344dc5
> **Validator:** Clarvis maintenance engine (automated)
> **Prior validation:** 2026-04-12 (E2E fresh installs on OpenClaw + Hermes)

---

## Overall Verdict

| Install Path | Status | Evidence | Publicly Claimable? |
|---|---|---|---|
| **Clarvis standalone** (venv, no harness) | **SUPPORTED** | 59/61 smoke, 27/27 overlay, 19/19 cron e2e | Yes |
| **Clarvis + OpenClaw** (overlay) | **PARTIAL** | 42/45 E2E checks (3 warnings, 0 failures) | Yes, with "known limitations" qualifier |
| **Clarvis + Hermes** (overlay) | **EXPERIMENTAL** | 38/39 E2E checks (1 warning, 0 failures) | No — EXPERIMENTAL qualifier required |
| **Zero-API-key** (local Ollama) | **SUPPORTED** | 12/12 local model harness | Yes |
| **Docker** | **EXPERIMENTAL** | Dockerfile exists, not CI-tested | No — contributor quickstart only |
| **Windows native** | **UNSUPPORTED** | Never tested | No |
| **macOS** | **EXPERIMENTAL** | Not regularly tested | No |

---

## What Passed

### Core (harness-independent)

| Test Suite | Checks | Pass | Fail | Warn | Date |
|---|---|---|---|---|---|
| `fresh_install_smoke.sh --isolated` | 61 | 59 | 0 | 1 | 2026-04-06 |
| `test_overlay_install.sh` | 27 | 27 | 0 | 0 | 2026-04-06 |
| `test_cron_isolated_e2e.py` | 19 | 19 | 0 | 0 | 2026-04-06 |
| `local_model_harness.sh test` | 12 | 12 | 0 | 0 | 2026-04-06 |
| `test_open_source_smoke.py` | varies | all | 0 | 0 | 2026-04-06 |

**Total core checks: 119+ pass, 0 fail.**

Fully passing areas:
- `pip install -e .` — clean dependency resolution (Python 3.10-3.12)
- All 12 core spine module imports (no eager ChromaDB load)
- `clarvis` CLI (all subcommands respond to `--help`)
- Brain (ChromaDB + ONNX) — local semantic search, graph backend
- Queue read/write
- Heartbeat gate (zero-LLM)
- Performance benchmark (PI)
- Cost tracking
- Cron wiring (all scripts pass syntax check, locks/guards validated)

### Harness E2E (2026-04-12)

| Test Suite | Checks | Pass | Fail | Warn | Date |
|---|---|---|---|---|---|
| `e2e_clarvis_on_openclaw_fresh.sh` | 45 | 42 | 0 | 3 | 2026-04-12 |
| `e2e_clarvis_on_hermes_fresh.sh` | 39 | 38 | 0 | 1 | 2026-04-12 |

**Total harness checks: 80/84 pass (4 warnings, 0 failures).**

---

## What Partially Passed

### Clarvis + OpenClaw (PARTIAL)

3 warnings from E2E:
1. `openclaw onboard` exits 1 — cosmetic (config + workspace created fine)
2. Brain store/recall on fresh empty DB returns ERROR — expected on fresh install
3. CLAUDE.md lives in parent dir, not copied into workspace

**Upstream blockers preventing SUPPORTED:**
- Auth field expects `key` not `token` (upstream OpenClaw)
- Health-check port hardcoded to 18789 (upstream OpenClaw)

### Clarvis + Hermes (EXPERIMENTAL)

1 warning from E2E:
1. `pip install hermes-agent` fails on PyPI — falls back to GitHub source OK

**Upstream blockers preventing PARTIAL/SUPPORTED:**
- `hermes-agent` CLI ignores `--model`, `--base_url` flags (upstream NousResearch)
- hermes-agent not on PyPI (upstream)
- Local model ~674s/turn on CPU — unusable for agent loops (hardware)

---

## What Did Not Pass / Was Not Tested

| Item | Status | Reason |
|---|---|---|
| Docker production | NOT TESTED | Dockerfile exists for contributor quickstart; no CI, no production testing |
| Windows native | NOT TESTED | No test infrastructure |
| macOS | NOT TESTED | No CI coverage |
| Hermes GEPA self-evolution | NOT TESTED | Needs fast LLM, untested with Clarvis integration |
| Browser automation | NOT TESTED in E2E | CDP-dependent, session fragile — manual only |

---

## Open Blockers (affect public claims)

| # | Blocker | Severity | Owner | Status |
|---|---------|----------|-------|--------|
| 1 | OpenClaw auth field `key` vs `token` | CRITICAL | Upstream | Open |
| 2 | `hermes-agent` ignores CLI flags | CRITICAL | Upstream | Open |
| 3 | qwen3-vl:4b needs 40.7 GB RAM (not 3.3 GB) | HIGH | Clarvis installer | Open |
| 4 | `--accept-risk` not in `--help` | MEDIUM | Upstream | Open |
| 5 | Health-check port hardcoded 18789 | MEDIUM | Upstream | Open |
| 6 | PEP 668 on Ubuntu 24.04+ | LOW | Clarvis | Mitigated (installer handles) |
| 7 | ~~Hermes `.env` requires TTY~~ | — | — | **FIXED** 2026-04-12 |

---

## Claim Discipline Audit (2026-04-13)

Claims in README, INSTALL.md, and docs were audited against test evidence. Fixes applied:

| Claim | Location | Issue | Fix |
|---|---|---|---|
| `bash scripts/verify_install.sh` | INSTALL.md | File at `scripts/infra/`, not `scripts/` | Path corrected |
| `bash scripts/setup.sh` | README.md Contributing | File at `scripts/infra/`, not `scripts/` | Path corrected |
| Docker "UNSUPPORTED — No Dockerfile" | SUPPORT_MATRIX.md | Dockerfile exists | Updated to EXPERIMENTAL (contributor quickstart) |
| Hermes profile at same level as others | INSTALL.md | No EXPERIMENTAL caveat | Added EXPERIMENTAL banner + caveat |
| Docker profile at same level as others | INSTALL.md | No caveat about non-production | Added EXPERIMENTAL banner |
| Friction Report Blocker #8 "Open" | INSTALL_FRICTION_REPORT.md | Fixed on 2026-04-12 | Marked FIXED |
| E2E Plan Blocker #8 "Open" | E2E_RELEASE_VALIDATION_PLAN.md | Fixed on 2026-04-12 | Marked FIXED |
| Hermes entry point "run_agent.py" | INSTALL_FRICTION_REPORT.md | Correct entry is `hermes` CLI | Updated |

---

## What Can Be Claimed Publicly

Based on the evidence above, the following claims are safe to make:

**Safe claims:**
- "Clarvis works as a standalone Python package on Linux (Python 3.10+)"
- "Local memory system works without any API keys"
- "Installer supports multiple profiles with guided setup"
- "Background execution via cron is available and tested"
- "OpenClaw integration works with documented workarounds"

**Claims requiring qualification:**
- "Works on OpenClaw" → must add "with known upstream limitations"
- "Works on Hermes" → must say "EXPERIMENTAL"
- "Docker support" → must say "contributor quickstart only, not production-tested"
- "Works on macOS" → must say "not regularly tested"

**Claims that must NOT be made:**
- "Works on Windows" (never tested)
- "Hermes is an alternative to OpenClaw" (without EXPERIMENTAL qualifier)
- "Docker is production-ready"
- "Zero friction install" (upstream blockers exist for harness paths)

---

## Delta from Previous Validation

| Metric | 2026-04-06 | 2026-04-12 | Change |
|---|---|---|---|
| Core smoke checks | 59/61 | 59/61 | No change |
| OpenClaw E2E | N/A | 42/45 | New |
| Hermes E2E | N/A | 38/39 | New |
| Hermes .env blocker | Open | **FIXED** | Improved |
| Docker claim | "No Dockerfile" | Dockerfile exists | Corrected to EXPERIMENTAL |

---

## How to Re-Validate

```bash
# Core smoke (any time)
bash scripts/infra/fresh_install_smoke.sh --isolated

# OpenClaw E2E
bash scripts/infra/e2e_clarvis_on_openclaw_fresh.sh

# Hermes E2E
bash scripts/infra/e2e_clarvis_on_hermes_fresh.sh

# Release gates
bash scripts/infra/release_gate_openclaw.sh
bash scripts/infra/release_gate_hermes.sh
```

---

_See also: [SUPPORT_MATRIX.md](../SUPPORT_MATRIX.md), [ADOPTION_MATRIX.md](../ADOPTION_MATRIX.md),
[INSTALL.md](../INSTALL.md), [INSTALL_FRICTION_REPORT.md](../INSTALL_FRICTION_REPORT.md),
[E2E_RELEASE_VALIDATION_PLAN.md](../E2E_RELEASE_VALIDATION_PLAN.md)_
