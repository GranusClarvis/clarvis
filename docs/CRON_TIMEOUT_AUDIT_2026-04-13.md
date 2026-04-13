# Cron Timeout Audit — 2026-04-13

## Summary

Audited all 27 cron shell scripts + spawn_claude.sh for:
1. Missing timeout wrapping on Claude Code spawns
2. Missing lock-file cleanup on SIGTERM
3. Silently swallowed errors

## Results

### 1. Timeout Wrapping on Claude Code Spawns: PASS
All 13 Claude-spawning scripts properly use either `timeout <sec>` or `run_claude_monitored <sec>` (from cron_env.sh).

### 2. Lock-File Cleanup: PASS
All scripts with lockfiles use either `lock_helper.sh` (with `_lock_helper_cleanup` on EXIT) or explicit `trap 'rm -f "$LOCKFILE"' EXIT`.

### 3. Silent Error Swallowing: 3 FIXED, remainder acceptable

## Fixes Applied (2026-04-13)

| File | Line | Before | After | Severity |
|------|------|--------|-------|----------|
| spawn_claude.sh | 93 | `2>/dev/null \|\| echo ""` on prompt_builder | `2>> "$LOGFILE" \|\| echo ""` | P0 |
| cron_autonomous.sh | 52 | `2>/dev/null` on detect-stuck stderr | `2>> "$LOGFILE"` | P0 |
| cron_pi_refresh.sh | 60 | bare `except Exception: sys.exit(0)` | logs error before exit | P0 |

## Remaining Items (acceptable as-is)

### `|| true` on non-critical operations (by design)
These suppress errors on best-effort operations where failure should not abort the script:
- cron_morning.sh:20 — session_hook (optional enrichment)
- cron_morning.sh:24 — daily_memory_log (optional bootstrap)
- cron_evening.sh:79 — self_report (non-blocking assessment)
- cron_evening.sh:83 — dashboard regen (cosmetic)
- cron_autonomous.sh:65 — daily_memory_log bootstrap
- cron_autonomous.sh:76 — external_challenge inject
- cron_research.sh:76 — external_challenge inject
- cron_strategic_audit.sh:20 — AST surgery scan (informational)
- cron_orchestrator.sh — multiple (orchestration is best-effort by design)
- cron_cleanup.sh:25 — sidecar pruning (logs warning)

### `2>&1` redirections to logfile (correct pattern)
Most scripts capture stderr to logfiles, which is proper error handling — errors are visible in logs.

### Missing `set -euo pipefail`
Most cron scripts intentionally omit strict mode because they contain multiple stages that should run independently. A failing assessment shouldn't prevent the Claude spawn. The `lock_helper.sh` and `cron_env.sh` infrastructure handle critical failures (lock acquisition, env setup).

## Checklist for Future Scripts

When writing a new cron script that spawns Claude Code:
- [ ] Source `cron_env.sh` and `lock_helper.sh`
- [ ] Use `acquire_local_lock` + `acquire_global_claude_lock`
- [ ] Use `run_claude_monitored <timeout>` (not raw `timeout` + claude)
- [ ] Never use `2>/dev/null` on python calls — use `2>> "$LOGFILE"`
- [ ] `|| true` only on genuinely non-critical operations
- [ ] All python stderr goes to logfile for debugging
