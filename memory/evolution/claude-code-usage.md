# Claude Code Usage - Lessons Learned

## The Issue
Claude Code was appearing to "hang" but it was just needing MORE TIME.

## What Works
- **Short prompts**: "say OK", "what is 1+1" → instant
- **Reasoning prompts**: Need 120s+ timeout
- **File output**: Like cron does → `>> file.log 2>&1`

## The Fix
Use longer timeouts for reasoning tasks:
```bash
cd /path && timeout 120 claude -p "reasoning task" --dangerously-skip-permissions
```

## Cron Comparison
- Cron runs: ~94 seconds for daily reflection
- My timeouts: 20-60 seconds ← TOO SHORT
- Correct: 120+ seconds

## Pattern for Reasoning
1. Use `cd` first
2. Use `timeout 120` or more
3. Redirect to file for long outputs
4. Be patient - reasoning takes time
