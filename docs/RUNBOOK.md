# Runbook

_Last updated: 2026-04-13. Operational procedures for Clarvis._

---

## 1. Heartbeat (Autonomous Task Execution)

The heartbeat pipeline executes one task per cycle: gate → preflight → Claude Code → postflight.

### Run a Manual Heartbeat
```bash
# 1. Gate check (should task run?)
python3 -m clarvis heartbeat gate
echo $?  # 0 = WAKE (proceed), 1 = SKIP

# 2. Preflight (task selection + context assembly)
python3 -m clarvis heartbeat run > /tmp/heartbeat_context.txt

# 3. Execute (normally done by cron_autonomous.sh)
cat /tmp/heartbeat_context.txt  # review the prompt
source scripts/cron_env.sh
timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
  claude -p "$(cat /tmp/heartbeat_context.txt)" \
  --dangerously-skip-permissions --model claude-opus-4-7 > /tmp/claude_output.txt 2>&1

# 4. Postflight (episode encoding, metrics)
python3 scripts/pipeline/heartbeat_postflight.py
```

### Check Heartbeat Health
```bash
# Gate state
python3 -c "import json; print(json.dumps(json.load(open('data/heartbeat_gate_state.json')), indent=2))"

# Recent episodes
python3 -c "import json; eps=json.load(open('data/episodes.json')); [print(e['task_id'], e.get('outcome','?')) for e in eps[-5:]]"
```

---

## 2. Brain (ClarvisDB)

---

## 2.1 Evolution Queue Format (QUEUE.md)

The evolution loop relies on `memory/evolution/QUEUE.md` being structured consistently.

### Required format (top-level tasks)
Use a **single line** per task:

```md
- [ ] [TAG] One-line description. Include acceptance criteria if possible.
```

- `TAG` should be **unique**, ALLCAPS, snake-ish (`ORCH_DEP_MAP`, `GRAPH_SOAK_5DAY`).
- Always include the `[TAG]` prefix: postflight marks completion by **tag**, not by brittle text matching.

### Subtasks
Indent subtasks beneath the parent (2 spaces is standard):

```md
  - [ ] [TAG_1] Subtask description
  - [ ] [TAG_2] Subtask description
```

### Status conventions
- Pending: `- [ ]`
- In progress / blocked: `- [~] [TAG] BLOCKED: reason (what is needed)`
- Done: `- [x] [TAG] ... (YYYY-MM-DD HH:MM UTC)`

### What NOT to do
- Don’t write untagged tasks (they won’t be tracked reliably).
- Don’t make multi-paragraph tasks at the top level; put details in subtasks or a linked doc.

### Quick view
```bash
cat memory/evolution/QUEUE.md
```

---

## 2. Brain (ClarvisDB)

### Health Check
```bash
python3 -m clarvis brain health        # Full report (collections, counts, graph)
python3 -m clarvis brain stats         # Quick stats
```

### Search & Store
```bash
python3 -m clarvis brain search "query text" --n 10   # Search all collections
# For store/remember, use the Python API:
python3 -c "from clarvis.brain import remember; remember('important fact', importance=0.9)"
```

### Maintenance
```bash
python3 -m clarvis brain optimize-full   # Decay + dedup + noise prune + archive
python3 -m clarvis brain backfill        # Fix orphan graph nodes
```

### Smoke Test
```bash
python3 -c "from clarvis.brain import brain; print(brain.stats()); print(brain.health_check())"
```

---

## 3. Performance Benchmark

### Run Full Benchmark
```bash
python3 -m clarvis bench run              # Full 8-dimension benchmark (records to history)
```

### Quick Checks
```bash
python3 -m clarvis bench pi               # Composite PI score (cached, instant)
python3 -m clarvis bench pi --fresh       # Recompute PI (slow, full measurement)
python3 -m clarvis bench quick            # Quick benchmark subset (JSON)
python3 scripts/performance_benchmark.py report      # Human-readable report (not in CLI yet)
```

### View History
```bash
# Latest metrics
python3 -c "import json; print(json.dumps(json.load(open('data/performance_metrics.json')), indent=2))" | head -30

# PI trend
tail -5 data/performance_history.jsonl | python3 -c "import sys,json; [print(json.loads(l).get('pi','?')) for l in sys.stdin]"
```

---

## 4. Self-Model & Capabilities

```bash
python3 scripts/self_model.py update     # Re-assess all 7 capability domains
python3 scripts/self_model.py report     # Print current assessment
python3 scripts/self_model.py history    # Capability trend
```

---

## 5. Backups

### Daily Backup (runs automatically at 02:00 CET)
```bash
bash scripts/backup_daily.sh             # Manual trigger
bash scripts/backup_verify.sh            # Verify last backup integrity
```

### Emergency ChromaDB Backup
```bash
# Stop all cron jobs first
cp -r data/clarvisdb/ data/clarvisdb_emergency_$(date +%Y%m%d_%H%M%S)/
```

### Restore from Backup
```bash
# 1. Stop gateway and cron
systemctl --user stop openclaw-gateway.service

# 2. Identify backup
ls -la data/clarvisdb_backup_*

# 3. Restore
mv data/clarvisdb data/clarvisdb_broken_$(date +%s)
cp -r data/clarvisdb_backup_<timestamp>/ data/clarvisdb/

# 4. Verify
python3 -m clarvis brain health

# 5. Restart
systemctl --user start openclaw-gateway.service
```

---

## 6. Gateway Management

```bash
# Must set these env vars first (or source cron_env.sh)
export XDG_RUNTIME_DIR=/run/user/1001
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus

systemctl --user status openclaw-gateway.service    # Check status
systemctl --user start openclaw-gateway.service     # Start
systemctl --user stop openclaw-gateway.service      # Stop
systemctl --user restart openclaw-gateway.service   # Restart
journalctl --user -u openclaw-gateway.service -n 50 # View logs
```

**Important:** Gateway is managed via systemd, NOT pm2. Do not use pm2 commands.

---

## 7. Updates

```bash
workspace/scripts/safe_update.sh --check     # Check for updates (safe, read-only)
workspace/scripts/safe_update.sh             # Full update with backup + health checks
workspace/scripts/safe_update.sh --rollback  # Emergency rollback
```

**Warning:** `safe_update.sh` has self-decapitation protection — it detects if running inside the gateway process tree and refuses to run.

---

## 8. Cost Tracking

```bash
python3 scripts/cost_tracker.py telegram    # Real OpenRouter usage (formatted)
python3 scripts/cost_tracker.py api          # Raw API data
python3 scripts/budget_alert.py --status     # Budget thresholds and remaining
```

**Note:** Do NOT use `data/costs.jsonl` for cost data — it contains stale estimates. Always use `cost_tracker.py` for real API figures.

---

## 9. Health Monitoring

### Automatic (cron)
- Health checks every 15 minutes (`health_monitor.sh`)
- Watchdog every 30 minutes (`cron_watchdog.sh`)
- Auto-recovery via `cron_doctor.py`

### Manual
```bash
bash scripts/health_monitor.sh              # Run health checks now
bash scripts/cron_watchdog.sh               # Run watchdog now
python3 scripts/cron_doctor.py              # Run auto-recovery
```

### View Logs
```bash
tail -20 monitoring/health.log
tail -20 monitoring/watchdog.log
tail -20 monitoring/alerts.log
```

---

## 10. Evolution Queue

### View Queue
```bash
python3 -m clarvis queue status            # Summary: counts by priority and section
python3 -m clarvis queue next              # Show next P0 task
cat memory/evolution/QUEUE.md              # Full queue (raw markdown)
```

### Add Task
```bash
python3 -m clarvis queue add "Task description" -p P1
python3 -m clarvis queue archive           # Archive completed tasks
```

### Task Selection (what heartbeat picks next)
```bash
python3 scripts/task_selector.py            # Show what would be selected
```

---

## 11. Structural Health

```bash
python3 scripts/import_health.py --report    # Full structural report
python3 scripts/import_health.py --check-cycles  # Circular import detection
python3 scripts/import_health.py --depth     # Dependency depth analysis
```

---

## 12. Spawning Claude Code (from M2.5 or manual)

### Preferred Method
```bash
workspace/scripts/agents/spawn_claude.sh "Your task here" 1200
# Add --no-tg as 3rd arg to skip Telegram delivery
```

### Manual Method
```bash
source workspace/scripts/cron_env.sh
cat > /tmp/claude_task.txt << 'ENDPROMPT'
Task description here.
ENDPROMPT
timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
  claude -p "$(cat /tmp/claude_task.txt)" \
  --dangerously-skip-permissions --model claude-opus-4-7 > /tmp/claude_output.txt 2>&1
cat /tmp/claude_output.txt
```

---

## 13. Cron Management (CLI)

### Inspect Cron Jobs
```bash
clarvis cron list              # Show all clarvis cron entries from crontab
clarvis cron status            # Last-run timestamps from memory/cron/*.log
```

### Run a Cron Job Manually
```bash
clarvis cron run reflection            # Execute scripts/cron_reflection.sh
clarvis cron run autonomous            # Execute scripts/cron_autonomous.sh
clarvis cron run reflection --dry-run  # Show what would be called
```

The `run` subcommand delegates to `scripts/cron_<job>.sh` via subprocess — no logic is rewritten.
Lock acquisition, env bootstrap, and timeout handling remain in the shell scripts.

### Cron Pilot Migration

**Proposed pilot**: `cron_reflection.sh` — it runs Python-only steps (no Claude Code spawn), making it the safest candidate.

To migrate one cron entry (after 7-day soak with no regressions):

1. **Add parallel crontab entry** (do NOT remove the old one yet):
   ```
   # PILOT: clarvis CLI wrapper (added YYYY-MM-DD, soak 7 days)
   # 0 21 * * * $CLARVIS_WORKSPACE/scripts/cron_reflection.sh >> .../reflection.log 2>&1
   0 21 * * * cd $CLARVIS_WORKSPACE && python3 -m clarvis cron run reflection >> $CLARVIS_WORKSPACE/memory/cron/reflection.log 2>&1
   ```

2. **Monitor for 7 days**: compare `reflection.log` output, check for errors.

3. **If clean**: remove the old `cron_reflection.sh` entry, keep the `clarvis cron run` entry.

4. **If regression**: revert to old entry, investigate, fix, retry.

**Important**: Do NOT edit crontab without explicit approval from the operator.

---

## 14. Troubleshooting

### Claude Code Hangs
- Check for missing `--dangerously-skip-permissions` flag
- Check if another instance holds the lock: `cat /tmp/clarvis_claude_global.lock`
- Kill stale: `kill $(cat /tmp/clarvis_claude_global.lock) 2>/dev/null; rm /tmp/clarvis_claude_global.lock`

### Cron Not Running
```bash
crontab -l | grep clarvis     # Verify cron entries exist
tail -20 memory/cron/autonomous.log  # Check last output
python3 scripts/cron_doctor.py        # Auto-diagnose and recover
```

### Brain Errors
```bash
python3 -m clarvis brain health       # Will report collection issues
ls -la data/clarvisdb/chroma.sqlite3  # Check DB file exists and is non-empty
```

### Import Errors After Refactoring
```bash
python3 scripts/import_health.py --report  # Find broken imports
git log --oneline -5                        # Check recent changes
git diff HEAD~1 -- scripts/ clarvis/       # Review what changed
```
