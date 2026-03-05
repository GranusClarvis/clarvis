# Marathon Runner — Runbook

## What It Does

`scripts/claude_marathon.sh` chains Claude Code tasks back-to-back for a fixed time budget (default: 7 hours). It reads from `memory/evolution/QUEUE.md`, spawns Claude in batches of 1–3 tasks, runs invariants after each batch, and stops on failure or time exhaustion.

## Quick Start

```bash
# Default 7-hour marathon
./scripts/claude_marathon.sh

# 2-hour sprint, 2 tasks per batch
./scripts/claude_marathon.sh --minutes 120 --max-batches 2

# Preview what would run (no execution)
./scripts/claude_marathon.sh --dry-run

# Longer timeout per Claude spawn (for complex tasks)
./scripts/claude_marathon.sh --timeout-per-claude 3600
```

## Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--minutes N` | 420 | Total time budget in minutes |
| `--max-batches N` | 3 | Max tasks per Claude batch |
| `--timeout-per-claude N` | 2400 | Timeout per Claude spawn (seconds) |
| `--dry-run` | off | Show what would run without executing |

## How It Works

### Loop (each batch):
1. **Select tasks** — `marathon_task_selector.py` picks 1–3 eligible tasks from QUEUE.md
   - Priority: P0 > Pillar 3 (graph soak) > other pillars > smallest-first
   - Skips: tasks needing external creds, blocked dependencies, oversized tasks
   - Auto-splits oversized tasks via `queue_writer.ensure_subtasks_for_tag`
2. **Spawn Claude** — via `spawn_claude.sh` with `--no-tg` (no Telegram)
   - Timeout capped to remaining time budget minus 180s buffer
   - Minimum timeout: 600s (will not start a batch with less)
3. **Auto-commit** — if working tree is dirty after Claude finishes
4. **Run invariants** — `invariants_check.py` (pytest, golden QA, brain health, hooks)
   - If ANY check fails → writes `docs/MARATHON_STOP_REPORT.md` and exits

### Stop Conditions
- Time budget exhausted (< timeout + 180s remaining)
- Queue empty or no eligible tasks
- Invariants check failure (writes stop report)

## Locking

- **Local lock:** `/tmp/clarvis_marathon.lock` (stale: budget + 5 min)
- **Global Claude lock:** `/tmp/clarvis_claude_global.lock` (shared with all cron spawners)
- Marathon **will not start** if another Claude session (cron_autonomous, etc.) holds the global lock

## Task Selection Details

`scripts/marathon_task_selector.py` handles task picking:

- **Dependency awareness:** e.g., `GRAPH_JSON_WRITE_REMOVAL` blocked until `GRAPH_SOAK_7DAY` done
- **Credential filter:** skips tasks tagged `AUTONOMY_LOGIN`, `AUTONOMY_POST`, etc.
- **Research filter:** deprioritizes research tasks (long, uncertain outcomes)
- **Complexity check:** uses `cognitive_load.estimate_task_complexity()` to skip oversized tasks
- **Batch sizing:** max 3 tasks, max 900 chars total

## Log File

All output logged to `memory/cron/marathon.log` with ISO 8601 timestamps.

## Troubleshooting

### Marathon won't start
```bash
# Check if global lock is held
ls -la /tmp/clarvis_claude_global.lock
cat /tmp/clarvis_claude_global.lock  # shows PID
kill -0 $(cat /tmp/clarvis_claude_global.lock)  # check if alive
```

### Invariants failed mid-run
```bash
# Check stop report
cat docs/MARATHON_STOP_REPORT.md

# Run invariants manually
python3 scripts/invariants_check.py

# Fix issues, then restart
./scripts/claude_marathon.sh
```

### Stale lock
```bash
rm /tmp/clarvis_marathon.lock
rm /tmp/clarvis_claude_global.lock
```

## Files

| File | Purpose |
|------|---------|
| `scripts/claude_marathon.sh` | Main marathon runner |
| `scripts/marathon_task_selector.py` | Task selection + batching |
| `memory/cron/marathon.log` | Execution log |
| `docs/MARATHON_STOP_REPORT.md` | Written on invariant failure |
