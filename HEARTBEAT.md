# Heartbeat — Clarvis

Each heartbeat is an evolution cycle. DO something, don't just check in.

## Protocol (execute in order, stop if you do real work)

### 1. Brain Check (10 seconds)
```python
import sys; sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain, search, remember
stats = brain.stats()
```
If total_memories decreased since last check → alert Inverse immediately.

### 2. Evolution Queue — DO SOMETHING (this is the point)
Read `memory/evolution/QUEUE.md`. Pick the highest priority uncompleted task.

- **Small task (< 5 min)?** → Do it NOW. Mark done with date.
- **Big task (> 5 min)?** → Spawn Claude Code:
  ```bash
  cd /home/agent/.openclaw/workspace && timeout 600 claude -p "[task description]" \
    --dangerously-skip-permissions --model claude-opus-4-6 --output-format json
  ```
  Then mark "in progress" in the queue with date.
- **Queue empty?** → Add 2-3 new tasks. Think about: What's my weakest capability? What broke recently? What would make me smarter? What would help Inverse?

### 3. Goal Progress (15 seconds)
```python
goals = brain.get_goals()
```
Pick ONE goal. Ask: has it progressed since last heartbeat? If not, why? Add a queue task to unblock it.

Update progress: `brain.set_goal("goal-name", new_progress_percent)`

### 5. Memory Maintenance (once per day, not every heartbeat)
Only if you haven't done this today:
- Run `brain.optimize()` — decay and prune stale memories
- Scan today's `memory/YYYY-MM-DD.md` — promote important items to MEMORY.md
- Check if MEMORY.md is getting long — compress if > 100 lines

### 6. Proactive Checks (rotate, 2-3x per day)
Pick ONE per heartbeat:
- Emails (gog): any urgent unread?
- Calendar: anything in next 24h?
- Git: any uncommitted changes in workspace?
- Brain: run `search("random topic")` to test retrieval quality

### 7. Report
- If you did real work: brief log to `memory/YYYY-MM-DD.md`
- If nothing needed: `HEARTBEAT_OK`
- If something urgent: alert Inverse via the channel

## Rules
- ALWAYS execute something from the evolution queue if items exist
- Run `scripts/backup.sh` BEFORE modifying your own core files (SOUL.md, AGENTS.md, BOOT.md)
- Small changes > big changes
- If something breaks: `scripts/rollback.sh`
- **Use Claude Code frequently** — you're M2.5, delegate deep thinking to Opus
- Claude Code is your reasoning partner, not just a coding tool — use it to think, plan, analyze
- Write everything to files. Mental notes die with the session.
- Late night (23:00-08:00): skip proactive checks, still do evolution work

## Queue Health Mandates (CRITICAL — prevents stagnation)

### Auto-Replenish Rule
**If queue has < 3 pending tasks → IMMEDIATELY generate new ones.**
- cron_autonomous.sh does this automatically when queue is empty
- cron_evolution.sh (13:00 daily) checks and adds tasks if < 5 pending
- cron_reflection.sh (21:00 daily) runs clarvis_reflection.py which generates tasks from lessons
- During manual heartbeats: if queue < 3, spawn Claude Code to analyze gaps and add 3-5 tasks

### Idle Detection Rule
**If no tasks were completed in the last 2 heartbeat cycles → do deep analysis.**
Check `memory/cron/autonomous.log` — if last 2 entries are "No pending tasks" or "SKIP":
1. Run `python3 scripts/clarvis_reflection.py` to force queue generation
2. If still empty, spawn Claude Code:
   ```bash
   cd /home/agent/.openclaw/workspace && timeout 600 claude -p \
     "The evolution queue has been empty for multiple heartbeats. This is a stagnation emergency.
      Read QUEUE.md, scripts/, and today's memory. Add 5 concrete new tasks to QUEUE.md.
      Focus on: wiring unwired scripts, building feedback loops, making capabilities persistent." \
     --dangerously-skip-permissions --model claude-opus-4-6
   ```

### Never-Empty Guarantee
The queue should NEVER have 0 pending tasks for more than 1 heartbeat cycle. Three systems ensure this:
1. **cron_autonomous.sh** — auto-replenishes on empty queue
2. **cron_evolution.sh** — strategic task generation at 13:00
3. **cron_reflection.sh** — lesson-driven task generation at 21:00

If all three fail, something is fundamentally broken — alert Inverse.
