# Cron Lane Classification

_Source of truth for which cron job belongs to which operational lane._
_Generated 2026-04-19 from `scripts/crontab.reference` (52 entries)._

## Lane Definitions

| Lane | Purpose | Lock | Touches Phi? |
|------|---------|------|-------------|
| **cognitive** | Claude Code spawners — evolution, planning, reflection, research | Global Claude lock | Indirect (via brain writes) |
| **brain** | Graph/ChromaDB maintenance, hygiene, quality evaluation | Maintenance lock | **Yes** (direct graph/collection ops) |
| **reporting** | Telegram digests, status JSON, dashboards | None | No |
| **monitoring** | Health checks, watchdog, alerts | None | No |
| **maintenance** | Backups, cleanup, data lifecycle, log rotation | Varies | No |
| **benchmark** | PI, CLR, calibration, brief benchmark | None | No (read-only) |
| **audit** | Re-audit runner, restore drills | None | No |
| **project** | Orchestrator, agent lifecycle | None | No |

## Full Classification (52 entries)

### cognitive (17 entries) — Claude Code spawners

| Schedule | Script | Notes |
|----------|--------|-------|
| 01:00 daily | `cron_autonomous.sh` | Overnight slot |
| 06:00 daily | `cron_autonomous.sh` | Morning slot 1 |
| 07:00 daily | `cron_autonomous.sh` | Morning slot 2 |
| 08:00 daily | `cron_morning.sh` | Day planning |
| 09:00 daily | `cron_autonomous.sh` | Morning slot 3 |
| 10:00 daily | `cron_research.sh` | AM research |
| 11:00 daily | `cron_autonomous.sh` | Midday slot 1 |
| 12:00 daily | `cron_autonomous.sh` | Midday slot 2 |
| 13:00 daily | `cron_evolution.sh` | Deep analysis |
| 14:00 daily | `cron_implementation_sprint.sh` | Dedicated impl |
| 15:00 daily | `cron_autonomous.sh` | Afternoon slot 1 |
| 16:00 daily | `cron_research.sh` | PM research |
| 17:00 Mon-Fri\* | `cron_autonomous.sh` | Afternoon slot 2 (\*not Wed/Sat) |
| 17:00 Wed,Sat | `cron_strategic_audit.sh` | Strategic audit |
| 18:00 daily | `cron_evening.sh` | Evening assessment |
| 19:00 daily | `cron_autonomous.sh` | Evening slot 1 |
| 20:00 daily | `cron_autonomous.sh` | Evening slot 2 |
| 21:00 daily | `cron_reflection.sh` | 8-step reflection |
| 22:00 daily | `cron_autonomous.sh` | Evening slot 3 |
| 23:00 daily | `cron_autonomous.sh` | Night slot |

_Note: 20 time slots but 12 unique autonomous + 8 specialized = 20 Claude-spawning entries._

### brain (8 entries) — Graph & ChromaDB

| Schedule | Script | Notes |
|----------|--------|-------|
| 02:45 Sun | `dream_engine.py dream` | Counterfactual dreaming |
| 03:00 1st Sun | `cron_absolute_zero.sh` | AZR self-play reasoning |
| 04:00 daily | `cron_graph_checkpoint.sh` | Graph checkpoint + SHA-256 |
| 04:30 daily | `cron_graph_compaction.sh` | Orphan edges, backfill |
| 04:45 daily | `cron_graph_verify.sh` | Integrity verification |
| 05:00 daily | `cron_chromadb_vacuum.sh` | ChromaDB vacuum |
| 05:15 Sun | `brain_hygiene.py run` | Dedup, prune |
| 06:15 daily | `cron_llm_brain_review.sh` | LLM-judged brain quality |

### maintenance (7 entries)

| Schedule | Script | Notes |
|----------|--------|-------|
| 02:00 daily | `backup_daily.sh` | Incremental backup |
| 02:30 daily | `backup_verify.sh` | Backup verification |
| 05:00 Sun | `canonical_state_refresh.py` | Weekly canonical state |
| 05:10 Sun | `goal_hygiene.py clean` | Stale goal cleanup |
| 05:20 Sun | `data_lifecycle.py` | Archive old chains, rotate sessions |
| 05:25 Sun | `knowledge_synthesis.py learning-strategy` | Learning strategy analysis |
| 05:30 Sun | `cron_cleanup.sh` | Log rotation, memory compression, weekly reaudit |

### monitoring (2 entries)

| Schedule | Script | Notes |
|----------|--------|-------|
| \*/15 min | `health_monitor.sh` | Health checks (96/day) |
| \*/30 min | `cron_watchdog.sh --alert` | Watchdog alerts (48/day) |

### benchmark (6 entries)

| Schedule | Script | Notes |
|----------|--------|-------|
| 02:40 daily | `clarvis cognition context-relevance refresh` | Context relevance |
| 05:45 daily | `cron_pi_refresh.sh` | Daily PI refresh |
| 06:05 daily | `cron_brain_eval.sh` | Deterministic brain eval |
| 06:00 Sun | `performance_benchmark.py record` | Weekly PI benchmark |
| 06:30 Sun | `cron_clr_benchmark.sh` | Weekly CLR benchmark |
| 06:45 Sun | `cron_calibration_report.sh` | Weekly calibration report |

### reporting (3 entries)

| Schedule | Script | Notes |
|----------|--------|-------|
| 09:30 daily | `cron_report_morning.sh` | Telegram morning digest |
| 22:30 daily | `cron_report_evening.sh` | Telegram evening digest |
| 05:50 daily | `generate_status_json.py` | Dashboard status JSON |

### project (1 entry)

| Schedule | Script | Notes |
|----------|--------|-------|
| 19:30 daily | `cron_orchestrator.sh` | Agent orchestration sweep |

### audit (4 entries)

| Schedule | Script | Notes |
|----------|--------|-------|
| 03:00 Q | `restore_drill.sh` | Quarterly restore drill (Jan/Apr/Jul/Oct) |
| 03:15 Q | `reaudit_runner.py quarterly` | Quarterly re-audit |
| 03:30 1st | `cron_monthly_reflection.sh` | Monthly structural reflection |
| 03:45 1st | `brief_benchmark.py` | Monthly brief benchmark |
| 03:50 1st | `reaudit_runner.py monthly` | Monthly re-audit |

## Summary by Lane

| Lane | Count | Frequency | Phi-affecting? |
|------|-------|-----------|---------------|
| cognitive | 20 | 20/day (12 autonomous + 8 specialized) | Indirect |
| brain | 8 | 6/day + 2/week | **Yes** |
| maintenance | 7 | 2/day + 5/week | No |
| benchmark | 6 | 3/day + 3/week | No |
| audit | 5 | 2/month + 2/quarter + 1/quarter | No |
| reporting | 3 | 3/day | No |
| monitoring | 2 | 144/day combined | No |
| project | 1 | 1/day | No |
| **Total** | **52** | | |

## Phi Recovery Interventions

Jobs that directly affect Phi (integration metric):
1. `cron_graph_compaction.sh` (04:30) — repairs orphan edges, backfills
2. `cron_graph_checkpoint.sh` (04:00) — captures graph state
3. `brain_hygiene.py` (Sun 05:15) — dedup/prune (can remove edges)
4. `cron_chromadb_vacuum.sh` (05:00) — collection-level vacuum
5. `dream_engine.py` (Sun 02:45) — creates cross-collection memories

To target Phi recovery without disrupting other lanes, add interventions to the **brain** lane between 04:45 and 05:00 (after graph_verify, before vacuum).

## Merge-Freeze Rules

During merge freezes (e.g., project release branches):
- **Safe to keep**: monitoring, maintenance, benchmark, audit, reporting
- **Safe to pause**: cognitive (all Claude spawners), project
- **Requires judgment**: brain (graph ops should continue but hygiene prune can wait)
