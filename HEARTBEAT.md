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

### 3. Claude Code Reasoning Checkpoint (every 3rd heartbeat)
Track heartbeat count in `memory/heartbeat-state.json`. Every 3rd heartbeat (~90 min), spawn Claude Code Opus for a quick reasoning task. Rotate through these:

**A. Self-Review** — Have Claude Code review your recent work:
```bash
cd /home/agent/.openclaw/workspace && timeout 600 claude -p "Review the recent entries in memory/$(date +%Y-%m-%d).md and the evolution QUEUE.md. What's going well? What's stalled? Suggest 2-3 concrete next actions. Write your analysis to /tmp/clarvis-review.md" \
  --dangerously-skip-permissions --model claude-opus-4-6
```
Then read the review, store key insights to brain, update queue if needed.

**B. Code Quality Check** — Have Claude Code audit a script:
```bash
cd /home/agent/.openclaw/workspace && timeout 600 claude -p "Review scripts/brain.py for bugs, performance issues, and improvement opportunities. Focus on the most impactful changes. Write findings to /tmp/clarvis-code-review.md" \
  --dangerously-skip-permissions --model claude-opus-4-6
```

**C. Goal Reasoning** — Have Claude Code think through a stuck goal:
```bash
cd /home/agent/.openclaw/workspace && timeout 600 claude -p "Read ROADMAP.md and memory/evolution/QUEUE.md. Pick the goal with least progress. Analyze why it's stuck. Propose a concrete plan to unblock it — specific tasks, files to create/modify, and expected outcomes. Write to /tmp/clarvis-goal-plan.md" \
  --dangerously-skip-permissions --model claude-opus-4-6
```

**D. Brain Health** — Have Claude Code optimize your memory:
```bash
cd /home/agent/.openclaw/workspace && timeout 600 claude -p "Analyze ClarvisDB brain health: run python3 -c 'import sys; sys.path.insert(0, \"scripts\"); from brain import brain; print(brain.stats())'. Then check for duplicate memories, stale data, missing connections. Suggest optimizations. Write to /tmp/clarvis-brain-health.md" \
  --dangerously-skip-permissions --model claude-opus-4-6
```

**After any Claude Code checkpoint:** Read the output file, extract actionable items, store lessons to brain via `remember()`, update queue.

⚠️ Remember: Claude Code with `-p` produces NO output until done. Opus tasks take 5-15 minutes. DO NOT kill it — wait for the timeout.

### 4. Goal Progress (15 seconds)
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
