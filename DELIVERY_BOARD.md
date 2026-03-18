# Delivery Board — 14-Day Window

**Start**: 2026-03-17 | **Deadline**: 2026-03-31 | **Lock**: Active (`DELIVERY_LOCK.md`)

## Goal
Presentable Clarvis: open-source-ready repo, working website v0, clean structure, strong brain/recall, reliable orchestration, tested and maintainable.

---

## Milestone A — Foundation Freeze (by 2026-03-19)

| # | Task | Status | Notes |
|---|------|--------|-------|
| A1 | DLV_STRUCTURE_CLEANUP | DONE | 86 files / 17.5k lines removed |
| A2 | DLV_DEADLINE_LOCK | DONE | Lock wired into task_selector.py |
| A3 | DLV_CRITICAL_PATH_BOARD | DONE | This file |
| A4 | DLV_QUEUE_PRUNE | TODO | Prune non-delivery queue items |
| A5 | DLV_OPEN_SOURCE_GAP_AUDIT | DONE | `docs/OPEN_SOURCE_GAP_AUDIT.md` — 4 critical, 4 high, 4 medium |

**Blockers**: None

## Milestone B — Brain / Context Quality (by 2026-03-23)

| # | Task | Status | Notes |
|---|------|--------|-------|
| B1 | DLV_CONTEXT_RELEVANCE_RECOVERY | IN PROGRESS | Context Relevance=0.695 (was 0.387), target 0.75 |
| B2 | DLV_BRAIN_QUERY_POLICY | TODO | When to query vs stay lean |
| B3 | DLV_RECALL_PRECISION_REPORT | TODO | Retrieval quality dashboard |
| B4 | DLV_GOAL_HYGIENE_FINAL | TODO | Clean stale goals |

**Blockers**: B1 depends on related_tasks quality fix (CONTEXT_RELATED_TASKS_QUALITY in P1)

## Milestone C — Repo / Open-Source Readiness (by 2026-03-26)

| # | Task | Status | Notes |
|---|------|--------|-------|
| C1 | DLV_REPO_CONSOLIDATION_EXEC | TODO | Clarvis / clarvis-db / clarvis-p boundaries |
| C2 | DLV_OPEN_SOURCE_SMOKE_GREEN | TODO | Smoke checks green |
| C3 | DLV_MODE_SYSTEM_WIRING | TODO | GE/Arch/Passive actually govern runtime |

**Blockers**: C1 needs consolidation decisions (may need user input)

## Milestone D — Public Surface (by 2026-03-29)

| # | Task | Status | Notes |
|---|------|--------|-------|
| D1 | DLV_WEBSITE_V0_BUILD | TODO | Landing page on raw IP |
| D2 | DLV_PUBLIC_FEED_SAFE | TODO | Sanitized public feed |
| D3 | DLV_REPO_PRESENTATION | TODO | README, docs coherent externally |

**Blockers**: D1-D3 depend on C1 (repo boundaries settled first)

## Milestone E — Final Validation (by 2026-03-31)

| # | Task | Status | Notes |
|---|------|--------|-------|
| E1 | DLV_FINAL_BENCH_PASS | TODO | CLR, retrieval, smoke, orchestration |
| E2 | DLV_PRESENTABILITY_REVIEW | TODO | Final human review |
| E3 | DLV_LAUNCH_PACKET | TODO | Concise launch packet |

**Blockers**: All of A-D must be complete

---

## Critical Path

```
A (Foundation) ──→ B (Brain Quality) ──→ C (Repo/OS) ──→ D (Public) ──→ E (Validation)
   by 03-19          by 03-23              by 03-26         by 03-29       by 03-31
```

**Highest risk**: B1 (Context Relevance at 0.695, needs 0.75 — refresh pipeline now fixed)
**Dependency chain**: A4/A5 inform what C1-C3 need to fix → D depends on clean repo → E validates all

## Daily Status Updates

| Date | Progress | Next |
|------|----------|------|
| 2026-03-17 | A1-A3 done. Lock active. Board created. | A4, A5, then B1 |
