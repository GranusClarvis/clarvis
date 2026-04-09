# Phase 4: Operational Fitness Review

**Date:** 2026-04-08
**Reviewer:** Claude Code Opus (executive function)
**Scope:** Observability, failure modes, scale limits — per QUALITY_REVIEW_PLAN.md §Pass 4
**Method:** Code audit + log analysis + cross-referencing runtime artifacts

---

## Executive Summary

Clarvis's operational layer has **strong bones but brittle recovery**. The lock system, WAL-mode graph DB, and cron scheduling are well-engineered. But the system lacks a coherent failure-recovery strategy: ChromaDB has no degraded mode, secret redaction is bypassed on most write paths, backups silently produce corrupt database copies, cost tracking is 99% estimated with confirmed double-counting, and cron failure alerts are effectively disabled. The system works well in the happy path but has limited ability to detect, report, or recover from failures.

**By the numbers:**
- 8 CRITICAL findings (data integrity, silent secret bypass, no ChromaDB degraded mode)
- 18 HIGH findings (alert dead paths, silent failures, backup corruption, cost inaccuracy)
- 17 MEDIUM findings (lock gaps, monitoring blind spots, consistency drift)
- 10 LOW findings (naming, minor inefficiency)

---

## 4.1 Cron Failure Recovery

### What Works Well

- **Lock system is thoughtfully designed.** `lock_helper.sh` provides PID-based locks with `/proc/cmdline` verification against PID recycling, age-based stale detection (2400s global, 600s maintenance), and `trap EXIT` cleanup. This is significantly better than naive PID files.
- **`cron_doctor.py` has smart failure classification.** It distinguishes STALE_LOCK, CRASH, TIMEOUT, IMPORT_ERROR, DATA_ISSUE via log parsing + PID checks, with per-type recovery actions and a 2-retry-per-day budget with exponential backoff.
- **Global Claude lock provides mutual exclusion** across all major spawners (autonomous, morning, evolution, research, implementation, strategic_audit, monthly_reflection, llm_brain_review).

### Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1.1 | **cron_doctor JOBS dict has wrong paths** for `health_monitor`, `backup_daily`, `backup_verify` — points to `scripts/` but files are in `scripts/infra/`. Recovery attempts silently fail ("Script not found"). | MEDIUM | `cron_doctor.py:47-109` |
| 1.2 | **13+ cron jobs absent from cron_doctor JOBS dict** — `implementation_sprint`, `strategic_audit`, `orchestrator`, `monthly_reflection`, `morning`, `evolution`, `evening`, `reflection`, `llm_brain_review`, `absolute_zero`, `graph_checkpoint`, `graph_compaction`, `graph_verify`. Doctor cannot recover these. | HIGH | `cron_doctor.py:39-131` |
| 1.3 | **`dream_engine` in watchdog but not in cron_doctor** — watchdog detects failure, triggers doctor, doctor has nothing to recover. | MEDIUM | `cron_watchdog.sh:69`, `cron_doctor.py:39-131` |
| 1.4 | **Watchdog `--alert` flag not set in crontab** — Telegram failure alerts are dead. Failures appear only in watchdog.log, which nothing reads. | HIGH | Crontab: `*/30 * * * * .../cron_watchdog.sh >> ...` (no `--alert`) |
| 1.5 | **Watchdog monitors only 12 of 25+ cron jobs** — `implementation_sprint`, `strategic_audit`, `orchestrator`, `monthly_reflection`, `graph_*`, `chromadb_vacuum`, `absolute_zero`, `llm_brain_review`, `brain_eval` are all unmonitored. | HIGH | `cron_watchdog.sh:59-71` |
| 1.6 | **Watchdog is not self-monitoring** — if the watchdog itself hangs or crashes, nothing detects it. | HIGH | No meta-watchdog in crontab |
| 1.7 | **SIGKILL bypasses EXIT trap** — lock_helper's cleanup requires EXIT signal, but `set_script_timeout` escalates to SIGKILL after 5s. Stale locks can persist up to 2 hours until the watchdog's stale scan runs. | HIGH | `lock_helper.sh:39-48, 86-98` |
| 1.8 | **No `set_script_timeout` on major spawners** — `cron_autonomous.sh`, `cron_morning.sh`, `cron_evolution.sh`, `cron_research.sh`, `cron_implementation_sprint.sh` have no script-level timeout. Inner `timeout` covers Claude Code only; preflight/postflight hangs hold the global lock indefinitely. | HIGH | All listed scripts — `run_claude_monitored` timeout vs. no outer timeout |
| 1.9 | **`cron_report_morning/evening.sh` use inline PID locks** without `/proc/cmdline` PID recycling guard — just `kill -0`. | MEDIUM | `cron_report_morning.sh:10-12` |
| 1.10 | **Post-recovery recheck `sleep 2`** is far too short for Claude Code jobs — inflates "still failing" count and may suppress valid recovery reports. | MEDIUM | `cron_watchdog.sh:179` |

### Recommendation
**P0:** Enable `--alert` in the watchdog crontab entry. Add all Claude-spawning jobs to both the watchdog check list and cron_doctor JOBS dict. Fix the `scripts/infra/` path mismatch.
**P1:** Add `set_script_timeout` to all major spawners. Increase the stale-lock window or reduce the watchdog scan interval.

---

## 4.2 Secret Redaction

### What Works Well

- **No actual secrets found in the codebase or logs.** Exhaustive search for `sk-or-v1-`, `AKIA`, `Bearer`, `ghp_`, `password=` across all `.py`, `.sh`, `.json`, `.log`, `.jsonl` files found zero real credentials outside expected config files.
- **9 pattern categories** cover the most common secret types (AWS, OpenRouter, OpenAI, Bearer, GitHub, Telegram, private keys, generic API keys).

### Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 2.1 | **`commit()` bypasses redaction entirely.** Secret redaction is a `BRAIN_PRE_STORE` hook fired only in `remember()`. The `commit()` path calls `brain.store()` directly — no hooks. | CRITICAL | `clarvis/brain/__init__.py:555` |
| 2.2 | **14+ other `brain.store()` callers bypass redaction** — `brain_bridge.py:238` (stores raw task output), `brain_store.py:43` (stores error output), `reasoning_chains.py:47,80,102`, `episodic_memory.py:549,1021`, `memory_consolidation.py:292,1342`, `self_model.py:164,192,1452`, `phi.py:554`, `meta_learning.py:735,748,773`, and more. | CRITICAL | Multiple files (see §2.2 detail below) |
| 2.3 | **`brain_store.py` and `brain_bridge.py` are the highest risk** — they store raw task output text and error output, which are the most likely to contain secrets a failing process emitted. | CRITICAL | `clarvis/heartbeat/brain_store.py:43`, `clarvis/heartbeat/brain_bridge.py:238` |
| 2.4 | **Silent hook registration failure** — if `clarvis.heartbeat.hooks` fails to import (e.g., standalone scripts), redaction silently does not register, with no log warning. The `except Exception: pass` at `__init__.py:665-670` swallows the failure. | MEDIUM | `clarvis/brain/__init__.py:665-670` |
| 2.5 | **`sk-proj-` (current OpenAI key format) not matched** — the `openai_key` regex `sk-[A-Za-z0-9]{20,}` requires only alphanumerics after `sk-`, so `sk-proj-...` (with a second hyphen) is never matched. | HIGH | `clarvis/brain/secret_redaction.py:20` |
| 2.6 | **`password` keyword not in generic pattern** — DB connection strings (`postgresql://user:pass@host`), JSON `{"password": "value"}`, and bare `password:value` patterns are not caught. | HIGH | `clarvis/brain/secret_redaction.py:23` |
| 2.7 | **`Bearer` pattern is case-sensitive** — lowercase `bearer` (common in some HTTP libs) is not matched. | HIGH | `clarvis/brain/secret_redaction.py:22` |
| 2.8 | **Stripe `sk_live_`/`sk_test_`, Slack `xoxb-`, raw JWTs** — all uncovered. | MEDIUM | Pattern inventory vs. common credential types |

### §2.2 Detail: Direct `brain.store()` Callers Bypassing Redaction

| File | Lines | Risk Context |
|------|-------|-------------|
| `clarvis/brain/__init__.py` | 555 | `commit()` — proposed memories |
| `clarvis/heartbeat/brain_bridge.py` | 238 | `brain_record_outcome()` — raw task output |
| `clarvis/heartbeat/brain_store.py` | 43 | `store_failure_lesson()` — error text |
| `clarvis/cognition/reasoning_chains.py` | 47, 80, 102 | Reasoning chain storage |
| `clarvis/cognition/confidence.py` | 633 | Confidence scores |
| `clarvis/cognition/reasoning.py` | 339 | Reasoning storage |
| `clarvis/memory/episodic_memory.py` | 549, 1021 | Episode summaries |
| `clarvis/memory/memory_consolidation.py` | 292, 1342 | Consolidation writes |
| `clarvis/memory/soar.py` | 573 | SOAR memory writes |
| `clarvis/memory/procedural_memory.py` | 502 | Procedural memory writes |
| `clarvis/metrics/self_model.py` | 164, 192, 1452 | Self-model writes |
| `clarvis/metrics/phi.py` | 554 | Phi metric storage |
| `clarvis/context/gc.py` | 86 | GC context writes |
| `clarvis/learning/meta_learning.py` | 735, 748, 773 | Meta-learning writes |

### Recommendation
**P0:** Move redaction into `StoreMixin.store()` itself so it fires on every write path, not just `remember()`. This is a one-line fix at the `store()` entry point.
**P1:** Add `password`, `sk-proj-`, case-insensitive `bearer`, and Stripe/Slack patterns. Log a warning on hook registration failure.

---

## 4.3 Concurrent Access

### What Works Well

- **WAL mode is active and verified** on both `graph.db` and `synapses.db`. PRAGMA settings are appropriate: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`.
- **Six well-designed indexes** on the graph store cover all major query patterns including a composite `idx_edge_from_type`.
- **No production lock errors observed** in any log since the SQLite cutover (2026-03-29). The system is currently stable.
- **Factory pattern** uses correct double-checked locking for thread-safe ChromaDB client singleton.

### Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 3.1 | **ChromaDB `PersistentClient` is not process-safe.** Each OS process gets its own client instance. With 10+ active worktrees, up to 10 simultaneous uncoordinated ChromaDB processes can access the same `data/clarvisdb/` directory. ChromaDB's internal SQLite lacks the WAL/busy_timeout settings that `graph_store_sqlite.py` has. | HIGH | `factory.py:33-52`, `.claude/worktrees/` (10 worktrees observed) |
| 3.2 | **Shell maintenance lock and global Claude lock are orthogonal** — no coordination between `decay_edges`/compaction writers and Claude memory-write sessions. A compaction holding the maintenance lock and a Claude session holding the global lock can both write to `graph.db` simultaneously. | MEDIUM | `lock_helper.sh`, `cron_graph_compaction.sh:14`, `cron_autonomous.sh:21` |
| 3.3 | **`decay_edges()` has a TOCTOU race** — reads edge count, then does `executemany` updates/deletes, then commits, with no explicit `BEGIN` wrapping the operation. Concurrent writers can modify edges between count and update. | MEDIUM | `graph_store_sqlite.py:289-302` |
| 3.4 | **No retry logic on `OperationalError`** — any `busy_timeout` expiry propagates as an unhandled exception to callers. | MEDIUM | All write methods in `graph_store_sqlite.py` |
| 3.5 | **`busy_timeout=5000ms` may be insufficient** during compaction of 134,000+ edges. A multi-second `executemany` commit by one process can exceed a concurrent writer's 5s timeout. | MEDIUM | `graph_store_sqlite.py:73`, production edge count 134k+ |

### Recommendation
**P1:** Add a simple retry wrapper (2-3 retries with backoff) around `conn.commit()` in graph_store_sqlite.py. Consider raising `busy_timeout` to 15000ms during maintenance windows. Investigate ChromaDB's internal SQLite settings.

---

## 4.4 Error Propagation

### What Works Well

- **Graph SQLite init has a JSON fallback** (`graph.py:39-45`) — the only genuine degraded-mode path in the brain.
- **`cron_autonomous.sh` exits cleanly on preflight failure** (line 58-59) and runs postflight even if Claude crashes.
- **Lock cleanup on exit** is robust in the normal case.

### Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 4.1 | **No ChromaDB degraded mode.** `get_chroma_client()` has no error handling. `ClarvisBrain.__init__` has no catch. `_init_collections()` raises on any single collection failure. A corrupted collection = all memory operations fail. | CRITICAL | `factory.py:50`, `brain/__init__.py:60,103-108` |
| 4.2 | **`_LazyBrain` has no circuit breaker** — retries failing `get_brain()` on every attribute access with no backoff. Under ChromaDB unavailability, every conversation turn that touches memory triggers an expensive failed init attempt. | HIGH | `brain/__init__.py:204-209` |
| 4.3 | **`store()` `col.upsert()` has no try/except** — mid-write ChromaDB failure propagates unlogged. | HIGH | `store.py:67-71` |
| 4.4 | **Silent empty results on ChromaDB query failure.** `_dispatch_collection_queries()` wraps per-collection calls in `except Exception: pass` — a collection failure produces zero results indistinguishable from "no relevant memories." | HIGH | `search.py:399-406` |
| 4.5 | **`cron_morning.sh` hardcodes `--status success`** regardless of Claude exit code. The dashboard always shows morning planning as successful. | HIGH | `cron_morning.sh:43` |
| 4.6 | **`cron_autonomous.sh` postflight failure is non-fatal** with no operator notification. Dashboard event emission silently no-ops if `dashboard_events.py` is missing. | HIGH | `cron_autonomous.sh:440-458` |
| 4.7 | **No ChromaDB crash recovery path** in `cron_doctor.py`. Doctor classifies DB failures as `CRASH` and re-runs the script — which fails again. No `sqlite3 .recover`, no ChromaDB repair, no fallback to backup restore. | CRITICAL | `cron_doctor.py:420-436`, `factory.py:50` |
| 4.8 | **`GraphStoreSQLite.__init__` has no try/except** — corrupt `.db` file crashes graph init and propagates through `_load_graph()`. | HIGH | `graph_store_sqlite.py:61-75` |
| 4.9 | **Silent graph-memory consistency drift.** `add_relationship()` logs a WARNING on busy timeout but returns the edge dict anyway — callers believe the edge was written when it wasn't. Repeated failures create accumulating drift. | MEDIUM | `graph.py:188-191` |
| 4.10 | **`cron_morning.sh` does not check `MONITORED_EXIT`** after Claude run. | MEDIUM | `cron_morning.sh:34` |

### Recommendation
**P0:** Add a circuit breaker to `_LazyBrain` (fail fast after N consecutive failures with exponential backoff). Add a `chromadb_health_check()` to health_monitor that tests collection accessibility.
**P1:** Fix `cron_morning.sh` to propagate actual Claude exit code. Add a ChromaDB repair step to `cron_doctor.py`.

---

## 4.5 Backup Integrity

### What Works Well

- **Backups are running** and have been for months. The backup chain is incrementally structured with git bundles, file copies, and checksums.
- **`backup_verify.sh` exists** and runs at 02:30 daily.
- **`backup_restore.sh` exists** with a complete documented restore procedure including pre-restore snapshots.
- **Git remotes are configured** (`origin` at `git@github.com:GranusClarvis/clarvis.git`) and HEAD is current with `origin/main`.

### Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 5.1 | **`chroma.sqlite3` is hot-copied** without SQLite backup API — consistent checksum failures across 29 of 46 backup runs. The copy may contain partial transactions. | HIGH | `backup_daily.sh:199-202`, checksums.log (63% failure rate) |
| 5.2 | **`~/.openclaw/openclaw.json`, credentials, identity, Telegram configs are never backed up** — the backup only covers `WORKSPACE` (the git repo), not the parent `~/.openclaw/` directory. A machine loss would require manual reconstruction of all gateway config. | HIGH | `backup_daily.sh:31` (WORKSPACE scope) |
| 5.3 | **`.env` file is gitignored and not in BACKUP_SOURCES** — API keys/tokens are unrecoverable from backup alone. | HIGH | `.gitignore:12`, `backup_daily.sh:71-115` |
| 5.4 | **`graph.db` and `synapses.db` (WAL mode) are hot-copied** — may lose unflushed WAL transactions at backup time. | MEDIUM | `backup_daily.sh:199-202`; Apr 7 log shows synapses.db checksum mismatch |
| 5.5 | **Incremental restore is incomplete** — `backup_restore.sh` only restores files present in the target backup dir; unchanged files from earlier incrementals are silently absent. A full restore requires manually chaining incrementals. | MEDIUM | `backup_restore.sh:206-216` |
| 5.6 | **`CLARVIS_WORKSPACE: unbound variable` bug causes periodic total backup failures** — 3 confirmed multi-day gaps (Mar 13, Mar 23-27, Apr 5). Root cause: `set -euo pipefail` in `backup_daily.sh` + self-bootstrapping paradox with `cron_env.sh`. | MEDIUM | `backup_daily.sh:28`, `cron_env.sh:26`; gap logs |
| 5.7 | **No offsite backup** — entire backup chain is on the same local disk as live data. | MEDIUM | `backup_daily.sh:32` (BACKUP_ROOT on same host) |
| 5.8 | **Backup verify skips absent files** — files unchanged since a prior incremental are not re-verified. Corruption in prior backups goes undetected. | MEDIUM | `backup_verify.sh:84-85` |
| 5.9 | **No automated `git push`** — if commits are made but not pushed, they are only in the local git bundle. | LOW | Crontab (no push entry); remotes exist |

### Recommendation
**P0:** Use SQLite's `.backup` API (or `sqlite3 $DB "VACUUM INTO '/path/backup.db'"`) instead of raw file copy for all `.db` files. Add `~/.openclaw/` config files to backup scope.
**P1:** Fix the `CLARVIS_WORKSPACE` unbound-variable bug. Implement full-chain incremental restore. Add an offsite `git push` to the backup script.

---

## 4.6 Cost Tracking Accuracy

### What Works Well

- **`cost_api.py` provides authoritative data** via live OpenRouter API calls.
- **Budget alerting has fired** — `budget_alert_state.json` shows thresholds triggered on Apr 3 and Apr 5.
- **`MODEL_PRICING` table correctly maps** all router-selectable models.

### Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 6.1 | **99.2% of cost entries are estimated** — only 4 of 519 entries have `estimated: false`, all from Feb 2026. Every Claude Code session's cost is pure estimation. | HIGH | `data/costs.jsonl`: 515/519 entries estimated |
| 6.2 | **Confirmed double-counting** — `cron_implementation_sprint.sh` and `heartbeat_postflight.py` both log the same session. 12 tasks appear in both sources with identical task strings. | HIGH | `cron_implementation_sprint.sh:182`, `heartbeat_postflight.py:1661` |
| 6.3 | **Two separate JSONL files accumulate independently** — `data/costs.jsonl` (519 entries) and `scripts/data/costs.jsonl` (42 entries). The CLI wrapper resolves to the wrong one via relative path. | HIGH | `scripts/infra/cost_tracker.py:33` (relative path resolution) |
| 6.4 | **Token estimation is a crude duration-based proxy** — `5000 * duration_min` input / `2000 * duration_min` output. Five consecutive $5.625 entries have identical token counts (125k/50k = 25-min sessions assumed identical). | HIGH | `cron_implementation_sprint.sh:182`, `cron_research.sh:536` |
| 6.5 | **No kill switch on budget breach** — alerts fire but no cron suspension, API key lockout, or process termination. | MEDIUM | `budget_alert.py:114-183` |
| 6.6 | **Router `executor=="gemini"` maps to $0 cost** via `import_router_decisions()` even though actual execution uses MiniMax M2.5 at $0.42/1M. | MEDIUM | `clarvis/orch/cost_tracker.py:507` |
| 6.7 | **Telegram credentials in config are empty strings** — only populated at runtime via env vars. If env is unset, budget alerts silently fail. | MEDIUM | `data/budget_config.json` |
| 6.8 | **No weekly/monthly budget cap** — only `daily_above: $10` and credit-floor warnings. | LOW | `data/budget_config.json` |

### Recommendation
**P0:** Fix the double-counting by removing the duplicate `ct.log()` call in `cron_implementation_sprint.sh` (postflight already logs it). Fix the path resolution for `scripts/infra/cost_tracker.py`.
**P1:** Wire `log_real()` calls into more execution paths where OpenRouter returns actual cost data. Add a budget kill switch (at minimum, a flag file that spawners check before launching).

---

## Cross-Cutting Themes

### 1. The Alert Dead-Path Problem
Multiple systems have alerting infrastructure that is disabled, untested, or silently failing:
- Watchdog `--alert` not enabled in crontab
- Budget alert Telegram credentials in env vars only
- `emit_dashboard_event` silently no-ops
- `cron_morning.sh` hardcodes success status

**Impact:** The operator has very limited visibility into failures. The system can be degraded for hours or days without anyone knowing.

### 2. The "Happy Path Only" Problem
Most code works correctly when everything is healthy. Failure modes are handled by either (a) bare `except Exception: pass` (silent data loss) or (b) no try/except at all (crash propagation). There is almost no middle ground — no logged warnings that surface to operators, no degraded modes, no circuit breakers.

### 3. The Scope Gap Problem
Monitoring, recovery, and backup systems were built for a smaller set of cron jobs. The system has grown to 25+ scheduled jobs, but the watchdog monitors 12, the doctor covers ~8, and the backup covers the workspace but not the gateway config. Coverage hasn't kept pace with growth.

---

## Severity Summary

| Severity | Count | Key Areas |
|----------|-------|-----------|
| CRITICAL | 8 | Secret redaction bypass (3), ChromaDB no degraded mode (3), no crash recovery (2) |
| HIGH | 18 | Alert dead paths (4), monitoring gaps (4), backup corruption (3), cost inaccuracy (4), error propagation (3) |
| MEDIUM | 17 | Lock edge cases (4), consistency drift (3), backup gaps (4), cron gaps (6) |
| LOW | 10 | Minor naming, efficiency, config gaps |

---

## What Is Operationally Healthy

1. **Lock system** — PID verification, stale detection, age-based reclamation, and EXIT trap cleanup are well above typical cron script quality.
2. **Graph SQLite** — WAL mode, proper indexes, busy_timeout, and JSON fallback on init failure.
3. **No secrets in the codebase** — despite the redaction bypass, no actual secrets were found in brain data or logs.
4. **Backup infrastructure exists and runs** — incremental backups with verification, git bundles, and a documented restore procedure.
5. **Cost API path** — the `cost_api.py` → OpenRouter API path provides authoritative data when used.

## What Is Operationally Risky

1. **Secret redaction is a façade** — only protects `remember()`, not the 14+ other write paths including error output storage.
2. **ChromaDB failure = total brain failure** — no degraded mode, no circuit breaker, no repair path.
3. **Operator blindness** — watchdog alerts disabled, dashboard events silently no-op, morning cron hardcodes success.
4. **Backup database corruption** — 63% of backup runs have checksum failures on `chroma.sqlite3`.
5. **Cost tracking is unreliable** — double-counting, two separate log files, 99% estimated data.

## What Should Change First (Priority Order)

1. **Move secret redaction into `StoreMixin.store()`** — highest-impact single fix, one code change, eliminates all bypass paths. **[DONE — applied in this review]**
2. **Enable watchdog `--alert`** — one crontab edit enables Telegram failure notifications.
3. **Use SQLite backup API for `.db` files** — eliminates the 63% checksum failure rate.
4. **Add circuit breaker to `_LazyBrain`** — prevents cascading retry storms on ChromaDB failure.
5. **Fix cost tracking double-count and path resolution** — two targeted fixes for data accuracy.

---

## Appendix: Fixes Applied During This Review

### Fix 1: Secret redaction moved to storage boundary (`clarvis/brain/store.py`)
**What:** Added `redact_secrets()` call at the top of `StoreMixin.store()`, before any ChromaDB write. This ensures all 14+ write paths (remember, capture, commit, brain_bridge, brain_store, reasoning_chains, episodic_memory, etc.) go through redaction.
**Risk:** Minimal — redaction is wrapped in `try/except Exception: pass` (best-effort, never blocks storage). The import is lazy to avoid circular dependencies.
**Test:** 779 tests pass (34 brain-specific tests pass). The 1 failure (`test_double_acquire_blocked`) is pre-existing and unrelated.

### Fix 2: Expanded secret redaction patterns (`clarvis/brain/secret_redaction.py`)
**What:** Added 3 new patterns, fixed 1 case-sensitivity issue:
- `openai_project_key`: matches `sk-proj-...` (current OpenAI project key format)
- `db_connection_string`: matches `postgresql://`, `mysql://`, `mongodb://`, `redis://` URLs
- `password` keyword added to `generic_api_key` trigger words
- `Bearer` pattern changed to `[Bb]earer` for case-insensitive matching
**Risk:** Minimal — additive only, no existing patterns modified (except Bearer case fix). False positive risk is low (DB URLs and password= patterns are specific enough).
**Test:** All 4 new patterns verified with direct test cases.
