# Open-Source Gap Audit — 2026-03-17

Hard gap list: what blocks public repo release today.

## CRITICAL (Must Fix Before Any Public Exposure)

### 1. Hardcoded Telegram Secrets (8 locations)
Bot token `REDACTED_TOKEN_PREFIX` and chat ID `REDACTED_CHAT_ID` in:
- `scripts/budget_alert.py:42-43`
- `scripts/cron_report_morning.sh:23`, `cron_report_evening.sh:23`
- `scripts/cron_watchdog.sh` (embedded Python)
- `scripts/spawn_claude.sh:25,55`
- `data/budget_config.json:20-21`

**Fix**: Move to env vars (`CLARVIS_TELEGRAM_BOT_TOKEN`, `CLARVIS_TELEGRAM_CHAT_ID`). Rotate token.

### 2. Test Credentials in ChromaDB Embeddings
Email `REDACTED_EMAIL` + password `REDACTED_PASSWORD` embedded in:
- `data/clarvisdb/community_summaries.json`
- `data/memory_archive/archived_memories.json`
- `scripts/universal_web_agent.py:183` (docstring)

**Fix**: Purge from brain, regenerate embeddings, sanitize docstrings.

### 3. Hardcoded User Paths (146+ Python files)
`/home/agent/.openclaw/workspace` appears in 146 Python + 7 shell files.
Most use `os.environ.get("CLARVIS_WORKSPACE", "/home/agent/...")` pattern (partial mitigation).

**Fix**: Verify all files support env var fallback. Document required env vars.

### 4. Personal Identity in Docs
"Patrick"/"Inverse" in USER.md, SOUL.md, MEMORY.md, HEARTBEAT.md, CLAUDE.md.

**Fix**: Move personal docs out of public repo or anonymize.

---

## HIGH (Should Fix Before Release)

### 5. Missing Root Files
- [ ] `LICENSE` file (standalone, not just in pyproject.toml)
- [ ] `CONTRIBUTING.md`
- [ ] `CHANGELOG.md`

### 6. Deprecated Scripts (32 files)
`scripts/deprecated/` — dead code, potential secret surface. Delete before release.

### 7. No CI/CD
No `.github/workflows/`. External PRs won't be validated.
Add: test.yml (pytest), lint.yml (black/flake8).

### 8. Tracked Data File
`data/golden_qa.json` contains identity terms. Sanitize or .gitignore.

---

## MEDIUM (Nice to Fix)

### 9. Systemd/NUC Assumptions
Code assumes systemd user session, NUC hardware benchmarks. Document as deployment-specific.

### 10. Package Documentation Gaps
clarvis-db, clarvis-cost, clarvis-reasoning lack standalone README/CHANGELOG.

### 11. Legacy Import Pattern
`sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")` in 10+ scripts.

### 12. Test Directory Fragmentation
Tests in `tests/`, `scripts/tests/`, `clarvis/tests/`, `packages/*/tests/`.

---

## Presentability Review (2026-03-17)

What's already good (no action needed):
- **Code quality**: No circular imports. All 6 core modules import cleanly. Professional code style.
- **README.md**: Professional, well-structured — mermaid diagrams, quick start, known limitations, doc links.
- **Package structure**: `clarvis/` spine is clean and well-organized (brain/, memory/, cognition/, context/, metrics/, heartbeat/, runtime/, orch/, adapters/).
- **Documentation**: LAUNCH_PACKET.md, ARCHITECTURE.md, OPEN_SOURCE_GAP_AUDIT.md are comprehensive.
- **Smoke tests**: `tests/test_open_source_smoke.py` covers imports, mode wiring, secret scanning, package metadata, CLI structure.
- **Only 2 TODO/FIXME** in source (both in docstrings, acceptable).
- **No offensive content** found in codebase.

What needs improvement (already tracked above):
- Secrets (items 1-2) are the only true blockers. Everything else is HIGH/MEDIUM.
- `clarvis/cli_brain.py:5` uses raw hardcoded path without env var fallback — highest-visibility instance.
- `data/budget_config.json` secret not caught by `test_open_source_smoke.py` (scans .py only, not .json).
- `spawn_claude.sh:160` has additional chat ID reference not in audit.

---

## Release Gate Checklist

- [ ] Telegram token rotated
- [ ] All secrets moved to env vars
- [ ] ChromaDB purged of credentials
- [ ] Personal identity docs removed/anonymized
- [ ] LICENSE + CONTRIBUTING.md added
- [ ] scripts/deprecated/ deleted
- [ ] GitHub Actions CI added
- [ ] golden_qa.json sanitized
- [ ] README.md updated for external users
