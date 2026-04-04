---
name: spawn-claude
description: "Spawn Claude Code (Opus) to handle a complex task. Usage: /spawn <task description>"
whenToUse: |
  When the user requests a complex coding task, implementation, refactoring, or
  multi-step work that benefits from Claude Code's autonomous execution with full
  tool access. Not for simple questions or quick lookups.
metadata: {"clawdbot":{"emoji":"🚀","requires":{"bins":["claude"]}}}
user-invocable: true
---

# /spawn — Spawn Claude Code Properly

When the user sends `/spawn <task>`, spawn Claude Code to handle it.

## What This Skill Does

Takes the user's task description and launches Claude Code (Opus 4.6) via the `claude` CLI with proper settings. This is the CORRECT way to delegate work to Claude Code.

## Execution Steps

1. Take everything after `/spawn` as the task description
2. Write the task to a temp file (avoids shell parsing issues)
3. Spawn Claude Code via `exec` with the `claude` CLI
4. Report back when done

## Template

```bash
# PREFERRED: Use spawn_claude.sh (handles env, full paths, logging, TG delivery)
$CLARVIS_WORKSPACE/scripts/spawn_claude.sh "{user's task description here}" 1200
# Add --no-tg to skip Telegram delivery
# Add --isolated to run in git worktree isolation (safe for experimental changes)
$CLARVIS_WORKSPACE/scripts/spawn_claude.sh "{task}" 1200 --isolated
# Deliver output to a specific Telegram topic thread (e.g. Claude Code topic):
$CLARVIS_WORKSPACE/scripts/spawn_claude.sh "{task}" 1200 --topic=2 --chat=${CLARVIS_TG_GROUP_ID}
# Combine flags:
$CLARVIS_WORKSPACE/scripts/spawn_claude.sh "{task}" 1200 --no-tg --isolated
```

### Topic-Aware Delivery
When spawning from the Claude Code topic (thread 2), always include topic flags:
```bash
$CLARVIS_WORKSPACE/scripts/spawn_claude.sh "{task}" 1200 --topic=2 --chat=${CLARVIS_TG_GROUP_ID}
```

### Agent Lifecycle Manager (advanced)
```bash
# Spawn with full lifecycle tracking:
python3 scripts/agent_lifecycle.py spawn "task" --timeout 1200 --isolated
# List / status / kill / restore / merge:
python3 scripts/agent_lifecycle.py list
python3 scripts/agent_lifecycle.py status <agent_id>
python3 scripts/agent_lifecycle.py kill <agent_id>
python3 scripts/agent_lifecycle.py restore <agent_id>
python3 scripts/agent_lifecycle.py merge <agent_id>
python3 scripts/agent_lifecycle.py cleanup
```

### Auto-Fix PR Review Comments
```bash
# Show what would be fixed (dry run):
python3 scripts/pr_autofix.py <pr_number> --dry-run
# Fix all actionable review comments:
python3 scripts/pr_autofix.py <pr_number>
# Fix in isolation:
python3 scripts/pr_autofix.py <pr_number> --isolated
```

## Rules

- **From /spawn command:** Use `spawn_claude.sh` — it handles env setup, brain context injection, output capture, logging, and TG delivery
- **From conversation (no /spawn):** Use ACP — first `exec prompt_builder.py build --task "..." --tier standard`, then `sessions_spawn({runtime: "acp", agentId: "claude", task: "<enriched>", thread: true})`
- **NEVER use `sessions_spawn` WITHOUT `runtime: "acp"`** — that spawns M2.5, not Claude Code
- **NEVER use `--output-format json`** — wraps output in JSON, makes it unreadable
- **Minimum timeout: 600s** — default 1200s, use 1800s for large tasks
- **Tell the user** you've spawned it and what the timeout is
- **Wait for completion** — do NOT try to do the work yourself while Claude Code runs
- **Report results** — when Claude Code finishes, summarize what it did
- User gets TG notification automatically when spawn completes
- **Use --isolated** for experimental/risky tasks — changes stay on a branch until explicitly merged

## Example

User: `/spawn investigate why the research pipeline is producing empty results`

Response: "Spawning Claude Code (Opus) with 20 min timeout to investigate the research pipeline."

Then execute the template above with the task.
