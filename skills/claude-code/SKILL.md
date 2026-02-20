---
name: claude-code
description: "Delegate complex work to Claude Code — coding, architecture, debugging, planning, reasoning, and deep analysis. Your autonomous thinking partner."
metadata: {"clawdbot":{"emoji":"🧠","requires":{"bins":["claude"]}}}
---

# Claude Code — Your Autonomous Thinking Partner

Claude Code is not just a coding tool. It's an autonomous reasoning engine with full file system access, test execution, and deep multi-step problem solving. Use it whenever a task benefits from **isolated focus, deep analysis, or autonomous iteration**.

## When to Delegate

**Always delegate when:**
- Building or scaffolding a new project
- Debugging complex failures (multi-file, multi-step)
- Refactoring or restructuring codebases
- Architecture design — get a second opinion with fresh context
- Planning complex features — let Claude Code explore the codebase and propose
- Deep code review — more thorough than inline analysis
- Any task requiring 10+ minutes of focused autonomous work
- You need a reasoning partner with clean context (no conversation pollution)

**Keep inline when:**
- Simple one-liner fixes
- Reading a file to answer a question
- Quick lookups or status checks

## Quick Start — One-Shot Task

```bash
claude -p "your task description here" \
  --dangerously-skip-permissions \
  --output-format json
```

Always use `--dangerously-skip-permissions` so Claude Code never blocks waiting for approval.

## Background Mode — Long Tasks

For tasks that take a while, run in background so you can keep chatting:

```bash
pty:true background:true
claude -p "build a FastAPI service with auth, tests, and Docker setup" \
  --dangerously-skip-permissions \
  --output-format json
```

When it finishes, notify your human:
```bash
openclaw system event --type "task-complete" --message "Claude Code finished: [task summary]"
```

## Model Selection

```bash
# Use Opus for complex architecture, planning, hard debugging
claude -p "..." --model claude-opus-4-6 --dangerously-skip-permissions

# Use Sonnet for routine coding tasks (faster, cheaper)
claude -p "..." --model claude-sonnet-4-6 --dangerously-skip-permissions
```

## Cost Awareness

Use `--max-turns` to scope effort proportionally to task complexity. No need to hardcode budget caps — just be smart:
- Quick fix or review: `--max-turns 15`
- Medium task (feature, refactor): `--max-turns 30`
- Large build or deep debug: `--max-turns 50` or more

Optionally use `--max-budget-usd` if you want a hard cost ceiling for a specific task, but don't default to low caps — let Claude Code work until the job is done.

## Scoped Tasks — Tool Restriction

```bash
# Read-only analysis / reasoning
claude -p "review this code for bugs and propose fixes" \
  --dangerously-skip-permissions \
  --allowedTools "Read,Grep,Glob"

# Code changes only, no bash
claude -p "refactor this module" \
  --dangerously-skip-permissions \
  --allowedTools "Read,Write,Edit,Grep,Glob"
```

## Rules

1. **Always use `--dangerously-skip-permissions`** — headless; without this it hangs
2. **Always set a workdir** — `--cwd /path/to/project` or `cd` first
3. **Never run in `~/.openclaw/workspace/`** — that's your soul; coding goes in project dirs
4. **Use `--output-format json`** for structured results you can parse
5. **Notify on completion** — `openclaw system event` so your human knows when background tasks finish

## Common Patterns

### Build a New Project
```bash
mkdir -p /home/agent/projects/new-project && \
claude -p "Initialize a Python project with pyproject.toml, src layout, pytest, and a basic CLI" \
  --dangerously-skip-permissions \
  --cwd /home/agent/projects/new-project
```

### Get a Second Opinion on Architecture
```bash
claude -p "Review the architecture of this project. Identify design flaws, suggest improvements, and flag any scalability concerns. Write your analysis to REVIEW.md." \
  --dangerously-skip-permissions \
  --cwd /home/agent/projects/myproject \
  --allowedTools "Read,Write,Edit,Grep,Glob" \
  --model claude-opus-4-6
```

### Plan a Complex Feature
```bash
claude -p "I need to add user authentication with OAuth2. Explore the codebase, understand the current structure, and write a detailed implementation plan to PLAN.md with specific files to create/modify." \
  --dangerously-skip-permissions \
  --cwd /home/agent/projects/myproject \
  --model claude-opus-4-6
```

### Debug a Hard Problem
```bash
claude -p "The test test_auth_flow is failing with 'token expired'. Investigate root cause across all relevant files, fix it, and verify the fix passes." \
  --dangerously-skip-permissions \
  --cwd /home/agent/projects/myproject
```

### Self-Evolution — Brain Maintenance
```bash
claude -p "Review brain.py, optimize query performance, improve error handling, and run benchmarks before/after" \
  --dangerously-skip-permissions \
  --cwd /home/agent/.openclaw/workspace/scripts
```
