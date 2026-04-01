# Codex Open-Source Signal Review

**Date**: 2026-03-31
**Task**: [CODEX_OPEN_SOURCE_SIGNAL_REVIEW]
**Source**: github.com/openai/codex (README + repo structure analysis)

---

## Codex Open-Source Presentation Patterns

### License & Governance
- **Apache-2.0** license (permissive, enterprise-friendly)
- `LICENSE` + `NOTICE` files at root
- `SECURITY.md` for vulnerability reporting
- `CHANGELOG.md` with 664 documented releases
- `docs/contributing.md` with contributor guidelines
- 409 active contributors (visible social proof)

### README Structure
1. Badges (license, CI, downloads)
2. One-sentence pitch
3. Quick start (npm, Homebrew, binary — 3 install paths)
4. Feature overview with screenshots/diagrams
5. Architecture / configuration section
6. Links to external docs portal (developers.openai.com/codex)
7. Contributing + License links

### Distribution Model
- **npm**: `@openai/codex` (primary, rolling `0.0.0-dev` version)
- **Homebrew cask**: `brew install --cask codex`
- **GitHub Releases**: Platform-specific signed binaries (macOS arm64/x86, Linux arm64/x86, Windows)
- Code signing: notarized macOS, signed Linux/Windows (institutional trust)

### Key Trust Signals
1. Multi-channel distribution (lowers barrier to entry)
2. Explicit security reporting policy
3. Granular approval model (documented publicly)
4. Per-OS sandbox documentation
5. `AGENTS.md` system as public skill/capability boundary docs
6. MCP server integration examples (shows extensibility)

---

## Comparison Against Clarvis (March 31 Public-Surface Goals)

| Aspect | Codex | Clarvis | Gap |
|--------|-------|---------|-----|
| License | Apache-2.0 | MIT | OK (both permissive) |
| README quality | Professional | Professional | None |
| CONTRIBUTING | docs/contributing.md | Root CONTRIBUTING.md | None |
| CODE_OF_CONDUCT | Inferred (standard) | **Missing** | Add |
| SECURITY.md | Present | **Missing** | Add |
| CHANGELOG | 664 releases | Git log only | Add (low priority) |
| Issue templates | .github/ISSUE_TEMPLATE/ | **Missing** | Add |
| Distribution | npm + Homebrew + binaries | pip only | Partial (acceptable for v1) |
| Docs portal | External site | GitHub-hosted | Acceptable for v1 |
| CI/CD | Bazel + multi-platform | GitHub Actions (lint+test) | OK |
| Package READMEs | Per SDK | Missing per-package | Add |

---

## Adoptable Patterns (Priority-Ordered)

### P1 — Before Any Public Promotion
1. **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1 (standard, signals ethical intent)
2. **SECURITY.md** — Responsible disclosure process
3. **Issue/PR templates** — `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.md`

### P2 — Distribution & Discoverability
4. **CHANGELOG.md** — Summarize phases 1-3, major milestones
5. **Package READMEs** — `packages/{clarvis-db,clarvis-cost,clarvis-reasoning}/README.md`
6. **Deployment matrix in README** — Systems supported, dependencies, hardware

### P3 — Long-Term
7. **PyPI publishing workflow** — `.github/workflows/publish.yml`
8. **External docs site** — GitHub Pages or similar
9. **Contributor count badge** in README

---

## Clarvis Unique Strengths (Lean Into These)

1. **Transparent execution** — Full cron schedule visible, auditable via monitoring
2. **Self-aware metrics** — Phi, PI, self-model (novel for open-source agents)
3. **Standalone extractable packages** — clarvis-db as independent vector memory library
4. **Real-time cost tracking** — Public budget/cost transparency
5. **Architecture documentation** — ARCHITECTURE.md, ROADMAP.md exceed Codex depth

**Recommended positioning**: "Fully transparent, auditable autonomous agent with local-first memory" — differentiates from Codex's opaque ChatGPT-auth model.

---

## Success Criteria Met
- Studied Codex open-source presentation: license, README, governance files, distribution
- Compared against March 31 public-surface goals: identified 3 critical gaps (CoC, SECURITY, templates)
- Identified 3 adoptable patterns with concrete actions
- Identified Clarvis unique strengths for differentiation
