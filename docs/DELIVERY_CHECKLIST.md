# Delivery Checklist — 2026-03-31 Deadline

_Created: 2026-03-22. Single source of truth for what's done, what's left._
_Cross-referenced from: ROADMAP.md, QUEUE.md, OPEN_SOURCE_READINESS_AUDIT.md, FORK_INTEGRATION_PLAN.md_

**Goal:** Presentable Clarvis by 2026-03-31 — open-source-ready main repo, working website v0, clean repo boundaries, strong brain/context quality, reliable orchestration, tested structure.

---

## Milestone A — Foundation Freeze (target: 2026-03-19) — LATE

Core architecture and APIs should be stable. No breaking changes after this milestone.

| # | Item | Status | Evidence / Notes |
|---|------|--------|------------------|
| A1 | Brain API stable (`clarvis.brain`) | DONE | Spine module, factory pattern, singleton wired, 87 tests |
| A2 | Graph backend stable (SQLite+WAL) | DONE | `graph_cutover.py`, soak tests running, checkpoint/compact/verify cron |
| A3 | Heartbeat pipeline frozen | DONE | gate → preflight → execute → postflight, all wired |
| A4 | CLR benchmark merged from fork | DONE | `clarvis/metrics/clr.py`, 672 lines, schema v1.0 frozen |
| A5 | Runtime mode control-plane | **TODO** | Fork has clean implementation (`clarvis/runtime/mode.py`). Not yet merged. |
| A6 | Trajectory evaluation harness | **TODO** | Fork has `clarvis/metrics/trajectory.py`. Not yet merged. |
| A7 | CLI stable (`python3 -m clarvis`) | PARTIAL | brain, heartbeat, bench commands work. `mode` subcommand not yet wired. |
| A8 | ADR documentation merged | **TODO** | Fork has ADR-0001, ADR-0002. Trivial merge. |

**Remaining work:** Merge runtime mode, trajectory harness, and ADRs from fork (Category 1 items from FORK_INTEGRATION_PLAN). Stabilize CLI with `mode` subcommand.

---

## Milestone B — Brain / Context Quality (target: 2026-03-23) — IN PROGRESS

| # | Item | Status | Evidence / Notes |
|---|------|--------|------------------|
| B1 | Context relevance ≥ 0.75 | DONE | Current: 0.801 (above target) |
| B2 | Retrieval hit rate ≥ 80% | DONE | 1.000 after MEMORY_REPAIR fix |
| B3 | PI ≥ 0.90 | DONE | PI = 0.976 |
| B4 | Phi ≥ 0.50 | DONE | Phi = 0.754 |
| B5 | Brain bloat score < 0.30 | DONE | Graph compacted (109k→134k edges managed) |
| B6 | CLR context_relevance sub-score | DONE | Added in commit `ad623a0` |
| B7 | Suppression threshold sweep | DONE | Data-driven, commit `71d9f44` |
| B8 | Semantic cross-collection bridges | PARTIAL | Pair scores improving but full Phi verification blocked on compute time (120s timeout) |

**Remaining work:** B8 needs graph compaction or parallel Phi computation to verify. Not a blocker — metric targets all met.

---

## Milestone C — Repo / Open-Source Readiness (target: 2026-03-26) — NOT STARTED

| # | Item | Status | Evidence / Notes |
|---|------|--------|------------------|
| C1 | Remove hardcoded secrets | **BLOCKER** | Telegram bot token, chat ID, test password in 6+ files. See OPEN_SOURCE_READINESS_AUDIT §1. |
| C2 | Purge credentials from ChromaDB | **BLOCKER** | Test password embedded in `community_summaries.json` + memory_archive. Requires re-embedding. |
| C3 | Verify data/monitoring in .gitignore | **TODO** | Already in .gitignore but need `git ls-files` verification they're not tracked. |
| C4 | Delete `scripts/deprecated/` | **TODO** | Dead code directory. |
| C5 | Consolidate tests to `tests/` | **TODO** | Currently split across `tests/`, `scripts/tests/`, `clarvis/tests/`. |
| C6 | Add README.md at repo root | **DONE** | Enhanced with current status + repo boundaries. |
| C7 | Add LICENSE file at repo root | **TODO** | MIT in pyproject.toml but no standalone file. |
| C8 | Add CONTRIBUTING.md | **TODO** | Standard open-source requirement. |
| C9 | Basic CI workflow (lint + test) | **TODO** | No GitHub Actions exist. |
| C10 | Hardcoded paths audit | LOW | 630+ `/home/agent` occurrences. Most have env var fallback. Document as deployment-specific. |
| C11 | `clarvis-db` extraction to separate repo | **TODO** | API boundary documented. Needs LICENSE, CI, credential scrub. |

**Remaining work:** C1-C2 are release blockers. C3-C9 are required. C10-C11 are nice-to-have for v0.

---

## Milestone D — Public Surface (target: 2026-03-29) — NOT STARTED

| # | Item | Status | Evidence / Notes |
|---|------|--------|------------------|
| D1 | Website v0 scaffold | **TODO** | Info architecture documented in `docs/WEBSITE_V0_INFORMATION_ARCH.md`. No code yet. |
| D2 | Public feed endpoint (`/api/status`) | **TODO** | Data contract defined in website v0 doc. |
| D3 | CLR score visible on website | **TODO** | Depends on D1 + CLR being merged (A4 done). |
| D4 | Architecture page | **TODO** | Content exists in SELF.md/ROADMAP.md. Needs sanitization. |
| D5 | Repos page with extraction status | **DONE** | `website/static/repos.html` — 2 repos, status badges, anti-sprawl policy. |
| D6 | Domain/deployment | **TODO** | Pre-domain: IP-first deployment. |

**Remaining work:** All items. Website v0 is the largest remaining deliverable. Consider a static site generator (Hugo/Astro) for speed.

---

## Milestone E — Final Validation (target: 2026-03-31) — NOT STARTED

| # | Item | Status | Evidence / Notes |
|---|------|--------|------------------|
| E1 | Full test suite passes | **TODO** | Need consolidated test run across all packages. |
| E2 | Secret scan passes (no leaks) | **TODO** | Depends on C1-C2 completion. |
| E3 | Fresh clone + setup works | **TODO** | No setup instructions exist. |
| E4 | Website v0 live and accessible | **TODO** | Depends on D1-D6. |
| E5 | README accurately describes project | **TODO** | Depends on C6. |
| E6 | ROADMAP.md updated for public | **TODO** | Remove internal details (chat IDs, specific scripts). |

---

## Summary

| Milestone | Target Date | Status | Done | Total | Blockers |
|-----------|------------|--------|------|-------|----------|
| A — Foundation Freeze | 2026-03-19 | LATE | 4/8 | 8 | Fork merge pending |
| B — Brain/Context | 2026-03-23 | 95% | 7/8 | 8 | None critical |
| C — Open-Source Ready | 2026-03-26 | 0% | 0/11 | 11 | Secrets removal (C1-C2) |
| D — Public Surface | 2026-03-29 | 0% | 0/6 | 6 | Website build |
| E — Final Validation | 2026-03-31 | 0% | 0/6 | 6 | Depends on C+D |

**Critical path:** C1-C2 (secrets) → C6 (README) → D1 (website) → E3 (fresh clone)

**Risk assessment:** 9 days remain. A+B are nearly done. C is the highest-risk milestone — secrets removal and credential purging are non-trivial. D (website) can be minimal but still requires ~2-3 sessions. Recommend prioritizing C1-C2 immediately in the next autonomous slot.

---

_Update this file as items complete. Mark [DONE] with date._
