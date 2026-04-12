# E2E Fresh Install Validation Report — 2026-04-12

## Summary

Ran end-to-end Clarvis installation on both fresh OpenClaw and fresh Hermes environments.
Both paths pass with zero critical failures.

## Results

### Clarvis on Fresh OpenClaw

- **Verdict**: PASS (42/45 checks, 0 failures, 3 warnings)
- **Script**: `scripts/infra/e2e_clarvis_on_openclaw_fresh.sh`
- **Artifact**: `docs/validation/e2e_clarvis_on_openclaw_fresh_20260412_170512/result.json`
- **What was tested**:
  - Phase A: Fresh OpenClaw install in /tmp (npm, onboard, config, gateway)
  - Phase B: Clarvis install via `install.sh --profile openclaw`
  - Phase C: 12 core imports, 4 CLI commands, brain health, heartbeat gate, 6 cron scripts, OpenClaw adapter, 5 docs, queue system, verify_install.sh
  - Phase D: Gateway boot + clean shutdown on non-default port
- **Warnings**:
  1. `openclaw onboard` exits 1 (gateway self-test fails, but config + workspace created fine)
  2. Brain store/recall on fresh DB returns ERROR (CLARVIS_WORKSPACE isolation — brain.store works but search returns empty on fresh empty collections)
  3. CLAUDE.md lives in parent dir (not copied into workspace clone)
- **Friction**: None blocking. Onboard exit code is cosmetic.

### Clarvis on Fresh Hermes

- **Verdict**: PASS (38/39 checks, 0 failures, 1 warning)
- **Script**: `scripts/infra/e2e_clarvis_on_hermes_fresh.sh`
- **Artifact**: `docs/validation/e2e_clarvis_on_hermes_fresh_20260412_170902/result.json`
- **What was tested**:
  - Phase A: Fresh venv, hermes-agent install (PyPI + GitHub fallback)
  - Phase B: Clarvis install via `install.sh --profile hermes`
  - Phase C: 11 core imports, 4 CLI commands, brain health, heartbeat gate, cron scripts, Hermes adapter, docs, queue, verify_install.sh, Hermes post-overlay survival
- **Warning**: `pip install hermes-agent` fails (package not on PyPI). Falls back to GitHub source install successfully.
- **Friction**: Users must install hermes-agent from source: `pip install git+https://github.com/NousResearch/hermes-agent.git`
- **Key finding**: Clarvis overlay does NOT break Hermes CLI — `hermes` command still available after overlay.

## Runtime Guide Update

Refocused `docs/USER_GUIDE_OPENCLAW.md` into "Runtime & Operator Guide":
- Added scope banner with cross-links to INSTALL.md and SUPPORT_MATRIX.md
- Added "Runtime Expectations" section (what to expect after install)
- Added "Cron Management" commands section
- Added cron troubleshooting entry

## Actionable Next Steps

1. **hermes-agent PyPI**: The install.sh hermes profile should document that hermes-agent needs source install, or add a pip fallback to the install script itself
2. **Brain fresh-DB handling**: The brain store/recall round-trip should gracefully handle empty collections (returns empty, not error)
3. **CLAUDE.md location**: Consider copying CLAUDE.md into workspace during install, or having the test check the parent dir
