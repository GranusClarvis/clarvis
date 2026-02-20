# Claude Code Usage - Lessons Learned

## The Issue
Claude Code was appearing to "hang" but it was just needing MORE TIME.

## Timeout Guidelines
| Task Size | Timeout | Examples |
|-----------|---------|----------|
| Small | 2-6 min | Simple questions, quick edits |
| Medium | 6-10 min | Code reviews, small implementations |
| Large | 10-20 min | Big projects, deep reasoning |
| Very Large | 20+ min | Complex architecture, full implementations |

## What Works
- **Short prompts**: "say OK", "what is 1+1" → instant
- **Reasoning prompts**: Need 120s+ timeout
- **Big tasks**: Need 600s+ (10+ min)
- **File output**: Like cron does → `>> file.log 2>&1`

## The Fix
Use longer timeouts:
```bash
# Small task
cd /path && timeout 180 claude -p "task" --dangerously-skip-permissions

# Big task  
cd /path && timeout 600 claude -p "complex task" --dangerously-skip-permissions
```

## Cron Comparison
- Cron runs: ~94 seconds for daily reflection
- My timeouts: 20-60 seconds ← TOO SHORT
- Correct: 120-600+ seconds

## Pattern for Reasoning
1. Use `cd` first
2. Choose timeout based on task size
3. Redirect to file for long outputs
4. Be patient - deep thinking takes time
