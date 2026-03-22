# Open-Source Readiness Audit — 2026-03-16

## Status: NOT READY — 3 blockers, 6 medium, 4 low

## CRITICAL (Must fix before any public exposure)

### 1. Hardcoded Secrets — FIXED 2026-03-22
All Telegram secrets (bot token, chat IDs) moved from hardcoded defaults to env vars loaded from `.env` (gitignored). See `.env.example`. Affected: `cron_env.sh`, `budget_alert.py`, `cron_report_*.sh`, `cron_watchdog.sh`, `spawn_claude.sh`, `USER.md`.

**Remaining**: Rotate bot token. Purge test credentials from untracked ChromaDB data (C2 task).

### 2. Private Data in Tracked Directories
| Directory | Content | Size |
|-----------|---------|------|
| `data/clarvisdb/` | ChromaDB + HNSW indexes | ~634 MB |
| `data/` (all) | Costs, episodes, dreams, decisions, code outcomes | ~100+ MB |
| `memory/` daily logs | 129 .md files with agent reasoning | ~500 KB |
| `monitoring/` | Watchdog/health logs | ~400 KB |
| `data/browser_sessions/` | Auth cookies, session tokens | variable |

**Fix**: `data/`, `monitoring/` already in `.gitignore`. Verify they are NOT tracked by git. For `memory/` daily logs: exclude from public, keep only structural docs.

### 3. Build Artifacts Possibly Tracked
- `__pycache__/` dirs throughout (clarvis/, scripts/, tests/)
- `.pytest_cache/`, `*.egg-info/` in packages/
- Verify: `git ls-files '*.pyc'` — if any tracked, purge from history.

## MEDIUM (Fix before release)

### 4. Hardcoded Paths (630+ occurrences)
`/home/agent/.openclaw/workspace` appears in most Python files. Many already use `os.environ.get("CLARVIS_WORKSPACE", "/home/agent/...")` which is correct — the fallback just needs to be relative or documented.

**Fix**: Audit remaining hardcoded paths in `clarvis/orch/cost_api.py`, `clarvis/metrics/phi.py`, etc. Convert to env var pattern.

### 5. Script Bloat
- `scripts/`: ~160 Python + ~40 shell = ~200 files
- `clarvis/`: ~92 Python files (organized spine)
- `scripts/deprecated/`: full subdirectory of dead code
- Duplicate test locations: `tests/`, `scripts/tests/`, `clarvis/tests/`

**Fix**: Delete `deprecated/`. Consolidate tests to `tests/`. Legacy scripts are fine as-is for now (they work, users reference them).

### 6. Systemd/NUC-Specific Logic
- `cron_env.sh` assumes systemd user session
- Performance targets calibrated to NUC hardware
- Gateway managed via `systemctl --user`

**Fix**: Document as deployment-specific. Core code doesn't depend on systemd.

### 7. Missing Root Documentation
- No `README.md` at repo root
- No `CONTRIBUTING.md`
- No `LICENSE` file at root (MIT in pyproject.toml but no standalone file)
- No `CHANGELOG.md`

### 8. Package Readiness
| Package | Version | Tests | License | Ready |
|---------|---------|-------|---------|-------|
| clarvis-db | 1.0.0 | Yes | MIT (pyproject.toml) | ~90% |
| clarvis-cost | 1.0.0 | Minimal | MIT | ~80% |
| clarvis-reasoning | 1.0.0 | No | MIT | ~70% |

All need: standalone LICENSE file, CHANGELOG.md, CI workflow.

### 9. No CI/CD
No GitHub Actions workflows. Should add: lint, test, type-check for PRs.

## LOW (Polish before release)

### 10. Legacy Import Pattern
`sys.path.insert(0, ...)` in 10+ scripts. Works, but not portable.

### 11. OpenClaw Dependency
Several modules assume OpenClaw gateway structure (`~/.openclaw/agents/`). Document as optional integration.

### 12. Localhost Ports
Gateway (18789), Browser (18800), Ollama (11434) — documentation only, no code dependency. Safe.

### 13. Compressed Memory Files
`memory/` has `.md.gz` compressed files from older dates. Exclude from public.

## What's Safe to Open-Source Now

- `clarvis/` package (spine modules — brain, heartbeat, cognition, metrics, context, orch)
- `packages/clarvis-db/` (with credential scrub of test data)
- `tests/` (consolidated)
- `docs/` (architecture, ADRs, plans)
- Identity docs: `AGENTS.md`, `SOUL.md`, `ROADMAP.md`, `HEARTBEAT.md`, `SELF.md`
- `skills/` (OpenClaw skill definitions)

## Recommended Cleanup Order

1. **Week 1**: Secrets → env vars, verify .gitignore enforcement, purge tracked artifacts
2. **Week 2**: Root README + LICENSE + CONTRIBUTING, consolidate tests, delete deprecated/
3. **Week 3**: CI/CD (GitHub Actions), package standalone files, path audit
4. **Gate**: All 3 critical items resolved → ready for private beta
