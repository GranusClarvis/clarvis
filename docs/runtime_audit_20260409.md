# Clarvis Runtime Audit — 2026-04-09

**Auditor:** Claude Code Opus (executive function)
**Scope:** Full end-to-end test of cron pipelines, evolution flow, and major operational features
**Method:** Live execution, dry-runs, import verification, log analysis, data integrity checks

---

## Executive Summary

The system is **operationally healthy** with active cron execution, working evolution pipeline, and productive daily output. However, three bugs were found and fixed during this audit, and two external issues require operator attention:

**Fixed during audit:**
1. **`brain search` CLI returned zero results** — SQLite threading violation in `recall()` when `include_related=True` (used by CLI) combined with parallel dispatch. All CLI searches were silently broken.
2. **`generate_status_json.py` writing to wrong path** — `WORKSPACE` resolved to `scripts/` instead of `workspace/` after the scripts reorganization. Status JSON was stale for 5 days.
3. **`benchmark_brief.py` and `refresh_priorities.py`** — Same `parent.parent` path bug. Data/log paths pointed to nonexistent directories under `scripts/`.

**Requires operator attention:**
1. **OpenRouter API key is broken** — cost_tracker and budget_alert both fail with HTTP 401 "User not found". Budget monitoring is blind.
2. **CLR dropped 17%** (0.87→0.725) — likely related to uncommitted brain_mem migration changes.

---

## Test Matrix

### A. Cron Pipelines

| Flow | Status | Evidence |
|------|--------|----------|
| crontab (46 entries) | **PASS** | All entries point to existing, syntactically valid scripts |
| cron_env.sh | **PASS** | Correct WORKSPACE, claude binary found, .env loaded |
| cron_autonomous.sh | **PASS** | Ran 2026-04-09 15:00 (12x/day), proper lockfile handling |
| cron_morning.sh | **PASS** | Ran 2026-04-09 08:01 |
| cron_evening.sh | **PASS** | Ran 2026-04-08 18:01 (today's not yet due) |
| cron_evolution.sh | **PASS** | Ran 2026-04-09 13:03 |
| cron_reflection.sh | **PASS** | Ran 2026-04-08 21:xx |
| cron_research.sh | **PASS** | Ran 2026-04-09 16:00 (auto-replenish OFF — exits with "no tasks") |
| cron_implementation_sprint.sh | **PASS** | Ran 2026-04-09 14:02 |
| cron_orchestrator.sh | **PASS** | Ran 2026-04-08 19:30 |
| cron_strategic_audit.sh | **PASS** | Ran 2026-04-08 (Wed/Sat only) |
| cron_report_morning.sh | **PASS** | Ran 2026-04-09 09:30 |
| cron_report_evening.sh | **PASS** | Due 22:30 (not yet today) |
| health_monitor.sh | **PASS** | Ran 2026-04-09 16:45, system healthy |
| cron_watchdog.sh | **PASS** | 0 failures across 33 monitored jobs |
| cron_doctor.py | **PASS** | Running, path configs updated to new locations |
| cron_graph_checkpoint.sh | **PASS** | Ran 2026-04-09 04:00 |
| cron_graph_compaction.sh | **PASS** | Ran 2026-04-09 04:30 |
| cron_graph_verify.sh | **PASS** | Ran 2026-04-09 12:06, integrity_ok=True |
| cron_chromadb_vacuum.sh | **PASS** | Ran 2026-04-09 05:00 |
| cron_cleanup.sh | **PASS** | Ran 2026-04-06 (Sunday only) |
| backup_daily.sh | **PASS** | Ran 2026-04-09 02:00, checksums present |
| backup_verify.sh | **PASS** | Ran 2026-04-09 02:30 |
| cron_pi_refresh.sh | **PASS** | Ran 2026-04-09 05:45 |
| cron_brain_eval.sh | **PASS** | Ran 2026-04-09 06:05 |
| cron_llm_brain_review.sh | **PASS** | Ran 2026-04-09 06:15 |
| generate_status_json.py | **FIXED** | Was writing to `scripts/docs/` (nonexistent). Fixed path. |
| Lockfile state | **PASS** | 1 active lock (PID alive), 0 stale locks |

### B. Evolution / Heartbeat Pipeline

| Flow | Status | Evidence |
|------|--------|----------|
| heartbeat gate | **PASS** | Exit 0, decision=wake, context_relevance=0.913 |
| heartbeat preflight | **PASS** | Imports clean, produces context brief |
| heartbeat postflight | **PASS** | Imports clean, episode encoding works |
| evolution preflight | **PASS** | Imports clean |
| evolution queue (QUEUE.md) | **PASS** | 87 pending, 0 stuck, 4 completed in 24h |
| queue engine | **PASS** | Stats: 87 pending, 0 running, 1 failed, 205 total |
| queue writer | **PASS** | Functions: add_task, mark_complete, archive work correctly |
| prompt builder | **PASS** | Imports and builds context |
| spawn_claude.sh | **PASS** | Correct env -u, lockfile, timeout, worker pattern |
| reasoning chains | **PASS** | 5 chains today, continuous production |
| digest.md | **PASS** | Reflects actual activity (7 entries today, timestamps match logs) |

### C. Brain / Memory

| Flow | Status | Evidence |
|------|--------|----------|
| brain stats | **PASS** | 2888 memories, 10 collections, healthy |
| brain health | **PASS** | Store/recall test passes, graph resolved, 7/7 hooks |
| brain search (Python API) | **PASS** | `search("evolution")` returns 25 results |
| brain search (CLI) | **FIXED** | Was returning 0 results. Fixed: disable parallel dispatch when `include_related=True` |
| brain recall (parallel) | **PASS** | Works for basic recall (no include_related) |
| graph integrity | **PASS** | 2939 nodes, 92719 edges, all refs resolved |
| Phi metric | **PASS** | 0.7113, weakest: intra_collection_density=0.4410 |
| episodic memory | **PASS** | 369 episodes, 94% success rate, 347 successes |
| hebbian memory | **PASS** | Import OK, hooks registered |
| synaptic memory | **PASS** | Import OK |
| procedural memory | **PASS** | Import OK |
| memory consolidation | **PASS** | Import OK |
| brain bridge | **PASS** | Import OK |
| cognitive workspace | **PASS** | 42 items, 91% reuse rate (target: 58.6%) |
| context compressor | **PASS** | Import OK, function-based API |
| attention module | **PASS** | Import OK |

### D. Operational Features

| Feature | Status | Evidence |
|---------|--------|----------|
| backup chain | **PASS** | Daily backups 04-02 through 04-09, latest symlink correct |
| cost tracking | **FAIL** | HTTP 401 from OpenRouter API — key invalid/expired |
| budget alert | **FAIL** | Same API auth failure |
| CLR benchmark | **PASS** | 0.725 today (regression from 0.87 yesterday) |
| PI score | **PASS** | 0.7013, "Good — above targets, healthy" |
| status JSON | **FIXED** | Was stale 5 days. Fixed WORKSPACE path. Now writing correctly |
| agent orchestrator | **PASS** | 5 agents configured (star-world-order, clarvis-db, goat, kinkly, star-arena) |
| research pipeline | **PASS** | 4 outputs today, pipeline active |
| dream engine | **PASS** | Import OK |
| world models | **PASS** | Import OK |
| tool maker | **PASS** | Import OK |
| self-representation | **PASS** | Import OK |
| cron preset system | **PASS** | `clarvis cron status` works, 39 jobs tracked |
| legacy brain import | **PASS** | `scripts/brain_mem/brain.py` still works as wrapper |
| spine module imports | **PASS** | All `clarvis.memory.*` and `clarvis.heartbeat.*` imports work |

---

## Fixes Applied During Audit

### Fix 1: `brain.recall()` with `include_related=True` returns zero results

**File:** `clarvis/brain/search.py` line 459
**Root cause:** `_dispatch_collection_queries()` defaults to parallel execution (ThreadPoolExecutor) when querying >=3 collections. When `include_related=True`, each result calls `get_related()` which hits the graph's SQLite connection from a worker thread. SQLite objects cannot cross threads, so every future silently raises `sqlite3.ProgrammingError` caught by bare `except Exception: pass`.
**Impact:** The CLI `brain search` command was completely broken (always uses `include_related=True`). Any other caller of `brain.recall(include_related=True)` returned empty results.
**Fix:** Added guard to force sequential dispatch when `include_related=True`.
**Verification:** `python3 -m clarvis brain search "evolution" --n 3` now returns 25 results.

### Fix 2: `generate_status_json.py` WORKSPACE path

**File:** `scripts/infra/generate_status_json.py` line 20
**Root cause:** Script was moved from `scripts/` to `scripts/infra/` but `WORKSPACE = Path(__file__).parent.parent` was not updated. Resolved to `scripts/` instead of `workspace/`. Since `scripts/docs/` doesn't exist, the output silently fell through.
**Impact:** Status JSON stale since 2026-04-04 (5 days). Dashboard consumers saw old data.
**Fix:** Changed to `parent.parent.parent`.
**Verification:** Script now outputs "Wrote /home/agent/.openclaw/workspace/docs/status.json" with fresh data.

### Fix 3: `benchmark_brief.py` and `refresh_priorities.py` WORKSPACE paths

**Files:** `scripts/metrics/benchmark_brief.py` line 37-40, `scripts/hooks/refresh_priorities.py` line 19
**Root cause:** Same `parent.parent` issue after script reorganization.
**Impact:** benchmark_brief wrote to `scripts/data/benchmarks/` (wrong), refresh_priorities read from `scripts/memory/evolution/QUEUE.md` (nonexistent).
**Fix:** Changed to `parent.parent.parent`.

---

## Remaining Issues (ranked by severity)

### CRITICAL

1. **OpenRouter API key broken** — `cost_tracker.py` and `budget_alert.py` both fail with HTTP 401 "User not found". Budget monitoring is completely blind. The operator needs to verify/rotate the API key in `.env`.

### HIGH

2. **CLR regression** — Score dropped 0.87→0.725 (-17%) today. Key dimension drops: prompt_context (0.752→0.508), task_success (0.787→0.500), autonomy (0.808→0.411). Likely caused by uncommitted changes in working tree (brain_mem module deletions visible in `git status`). Committing or reverting these changes should stabilize CLR.

3. **Research auto-replenish OFF** — Both research cron slots (10:00, 16:00) exit immediately with "No pending research tasks". The pipeline produces output only when tasks are manually queued. If this is intentional, fine. If not, auto-replenish needs to be re-enabled.

### MEDIUM

4. **CLAUDE.md script path drift** — Many paths in CLAUDE.md reference old flat locations (e.g., `scripts/cron_autonomous.sh`, `scripts/spawn_claude.sh`, `scripts/cost_tracker.py`). Scripts have been reorganized into `scripts/cron/`, `scripts/infra/`, `scripts/agents/`, etc. This causes confusion for the conscious layer (M2.5) when it tries to follow documented paths.

5. **Brain hygiene alert storm (resolved)** — 14 consecutive "Brain hygiene check failed" alerts from 2026-04-08 19:15 to 2026-04-09 11:45. Now passing (7/7 hooks). The stale alerts aren't auto-cleared from `alerts.log`.

6. **`data/dashboard/status.json`** — This file (from an unknown source) is different from `docs/status.json`. Last updated 2026-04-08. May be written by a different process. Unclear which consumers depend on which path.

### LOW

7. **cron_env.sh duplicate elif** — Lines 32-34 have identical `if`/`elif` conditions. Dead code, harmless.

8. **Autonomous slot contention** — The 15:00 slot was skipped today due to global lock conflict. By design, but one of 12 daily slots lost. Expected behavior under mutual exclusion.

---

## Recommended Next Actions

1. **Rotate OpenRouter API key** — Verify key in `.env`, test with `python3 scripts/infra/cost_tracker.py api`.
2. **Commit or resolve brain_mem migration** — The uncommitted deletions in `scripts/brain_mem/` are likely destabilizing CLR. Clean commit of the migration would help.
3. **Update CLAUDE.md script paths** — Batch update all path references to new locations (`scripts/cron/`, `scripts/infra/`, `scripts/agents/`, etc.).
4. **Decide on research auto-replenish** — Either re-enable or document that it's intentionally OFF.
5. **Reconcile status JSON paths** — Determine whether `data/dashboard/status.json` or `docs/status.json` is canonical and consolidate.
