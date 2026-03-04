# Safety Invariants — Clarvis

Enforceable rules that MUST hold at all times. Violations trigger alerts.
Checked by `postflight_safety_check()` in `heartbeat_postflight.py` and
optionally by a pre-commit hook.

## Invariant 1: Memory Backup Before Destructive Operations

**Rule:** Never delete, prune, or archive memories without a prior backup checkpoint.

- `brain.py optimize-full` MUST be preceded by `backup_daily.sh` or equivalent.
- `graph_compaction.py` and `vacuum` share `/tmp/clarvis_maintenance.lock`; maintenance
  window (04:00–05:00 CET) is the only approved slot for destructive graph operations.
- Deleting a ChromaDB collection outright is forbidden outside of test fixtures.

**Enforcement:** Postflight checks that `data/clarvisdb/` has not shrunk by >10% in total size.

## Invariant 2: Gate Check Before Code Commits

**Rule:** No commits to `scripts/`, `clarvis/`, or `packages/` without `gate_check.sh` passing.

- `compileall` syntax check must pass.
- `pytest` for `clarvis-db` must pass.
- CLI smoke tests (`clarvis --help`, `brain stats`) must pass.

**Enforcement:** Pre-commit hook runs `python3 -m py_compile` on staged `.py` files.
Full gate check runs in postflight after code-modifying heartbeats.

## Invariant 3: Browser Credentials Isolation

**Rule:** Browser session credentials (cookies, tokens) are stored ONLY in
`data/browser_sessions/` and never written to git, environment variables, or brain memory.

- `.gitignore` excludes `data/browser_sessions/`.
- Brain `store()` must never be called with raw credentials as document text.
- `clarvis_browser.py` loads cookies from `default_session.json` only.

**Enforcement:** Pre-commit hook rejects staged files matching `*session*.json` or `*cookie*`.

## Invariant 4: No Nested Claude Code Sessions

**Rule:** Claude Code MUST NOT be spawned from within another Claude Code session.

- All cron spawners use `env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT` to clear nesting guards.
- `spawn_claude.sh` checks for `CLAUDECODE` env var before proceeding.
- Violation causes session crashes and resource contention.

**Enforcement:** Checked at spawn time by environment variable guard.

## Invariant 5: Cron Mutual Exclusion

**Rule:** Only one Claude Code heartbeat may execute at a time.

- Global lock: `/tmp/clarvis_claude_global.lock` acquired by all spawners.
- Maintenance lock: `/tmp/clarvis_maintenance.lock` for graph/vacuum operations.
- PID-based stale-lock detection with 2-hour expiry.

**Enforcement:** Lock acquisition at cron script entry; `trap EXIT` cleanup.

## Invariant 6: Cost Budget Limits

**Rule:** Daily spending must stay within budget alert thresholds.

- Thresholds defined in `data/budget_config.json`.
- `budget_alert.py` runs in morning/evening reports.
- Exceeding hard limit triggers Telegram alert to user.

**Enforcement:** `budget_alert.py --status` checked in report scripts.

## Invariant 7: No Silent Data Loss

**Rule:** Modifications to `.jsonl` data files must use atomic write (write to `.tmp` then `os.replace()`).

- Applies to: `episodes.json`, `costs.jsonl`, `performance_history.jsonl`,
  `confidence_calibration.json`, `task_sizing_log.jsonl`.
- Truncation of rolling files must keep at least the most recent N entries (never empty).

**Enforcement:** Code review pattern; postflight checks file existence.

## Invariant 8: Brain Health Minimum

**Rule:** Brain must pass `health_check()` after any memory-modifying operation.

- `brain.health_check()` verifies store + recall round-trip.
- If health check fails, the operation is logged as a regression and a P0 fix task is pushed.

**Enforcement:** Postflight self-test harness runs `brain.health_check()` after code-modifying heartbeats.

---

## Checking Invariants

```bash
# Pre-commit: syntax check on staged .py files
python3 scripts/safety_check.py pre-commit

# Postflight: full invariant check
python3 scripts/safety_check.py postflight

# Manual: check all invariants
python3 scripts/safety_check.py all
```
