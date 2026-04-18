---
name: claude-code
description: "Delegate complex work to Claude Code — coding, architecture, debugging, planning, reasoning, and deep analysis. Your autonomous thinking partner."
whenToUse: |
  When a task requires deep coding, architecture analysis, multi-file refactoring,
  debugging, or complex reasoning that benefits from Claude Code's full tool access
  and autonomous execution. Use spawn-claude skill for invocation.
metadata: {"clawdbot":{"emoji":"🧠","requires":{"bins":["claude"]}}}
---

# Claude Code — Your Autonomous Thinking Partner

Claude Code is not just a coding tool. It's an autonomous reasoning engine with full file system access, test execution, and deep multi-step problem solving. Use it whenever a task benefits from **isolated focus, deep analysis, or autonomous iteration**.

## ⚠️ CRITICAL — How Claude Code Output Works

**Claude Code with `-p` (non-interactive mode) buffers ALL output until the task fully completes.** There is NO progressive output. This means:

- During execution, you will see **"no new output"** when polling — this is NORMAL
- Claude Code is working (reading files, writing code, running tests) but produces no stdout until it's done
- **DO NOT kill a running Claude Code process just because you see no output** — it's almost certainly working
- A complex multi-step task with Opus takes **5-15 minutes**. With Sonnet, **2-5 minutes**. This is expected behavior.

**If you want real-time progress**, use `--output-format stream-json` — this outputs newline-delimited JSON events as Claude Code works:
```bash
cd /path/to/project && claude -p "task" \
  --dangerously-skip-permissions \
  --output-format stream-json
```

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
cd /path/to/project && claude -p "your task description here" \
  --dangerously-skip-permissions \
  --output-format json
```

Always use `--dangerously-skip-permissions` so Claude Code never blocks waiting for approval.

**Important:** There is NO `--cwd` flag. Set the working directory with `cd` before running claude.

## Timeouts — Don't Kill Prematurely

Claude Code needs time for multi-step tasks. Each API round trip takes 10-30 seconds, and complex tasks need 10-20+ round trips. Use generous timeouts:

| Task type | Recommended timeout |
|-----------|-------------------|
| Simple (ls, echo, one-liner) | 120s |
| Read & review a file | 300s |
| Create/edit a script | 600s |
| Complex multi-file task | 600s |
| Architecture/planning | 900s |
| Build a project | 900s |

Use the shell `timeout` command:
```bash
cd /path/to/project && timeout 600 claude -p "complex task" \
  --dangerously-skip-permissions \
  --output-format json
```

**Rule: When in doubt, use a longer timeout. A task finishing early costs nothing. Killing a task that was about to complete wastes all the work.**

## Model Selection

```bash
# Default: Opus 4.6 — best reasoning, most capable
cd /path && claude -p "..." --model claude-opus-4-6 --dangerously-skip-permissions

# Sonnet: for simple/routine tasks where speed matters more than depth
cd /path && claude -p "..." --model claude-sonnet-4-6 --dangerously-skip-permissions
```

**Default to Opus 4.6** — it produces the best results for coding, architecture, debugging, and reasoning. Use Sonnet only for simple/routine tasks where speed is the priority. Opus takes longer per round trip (15-30s vs 5-10s) so use generous timeouts (600s+).

## Cost Awareness

Use `--max-turns` to scope effort proportionally to task complexity. No need to hardcode budget caps — just be smart:
- Quick fix or review: `--max-turns 15`
- Medium task (feature, refactor): `--max-turns 30`
- Large build or deep debug: `--max-turns 50` or more

## Scoped Tasks — Tool Restriction

```bash
# Read-only analysis / reasoning
cd /path && claude -p "review this code for bugs and propose fixes" \
  --dangerously-skip-permissions \
  --allowedTools "Read,Grep,Glob"

# Code changes only, no bash
cd /path && claude -p "refactor this module" \
  --dangerously-skip-permissions \
  --allowedTools "Read,Write,Edit,Grep,Glob"
```

## Rules

1. **Always use `--dangerously-skip-permissions`** — headless; without this it hangs waiting for approval
2. **Use `cd /path && claude -p ...`** — there is NO `--cwd` flag; set directory with `cd`
3. **Use generous timeouts** — `timeout 300` minimum for anything beyond trivial tasks
4. **Don't kill on "no output"** — Claude Code buffers output; silence means it's working
5. **Default to Opus 4.6** — best model for coding and reasoning; use Sonnet only for simple/routine tasks
6. **Use `--output-format json`** for structured results, or `stream-json` for real-time progress
7. **Notify on completion** — `openclaw system event` so your human knows when background tasks finish

## Common Patterns

### Quick Example — Fix a Bug
```bash
cd $CLARVIS_WORKSPACE && timeout 600 claude -p \
  "The test test_brain_roundtrip.py::test_search_returns_results is failing. Investigate, fix, and verify." \
  --dangerously-skip-permissions --model claude-opus-4-6 --output-format json
```
Expected JSON output:
```json
{"type":"result","result":"Fixed: search index was stale after bulk insert. Added explicit flush. Test passes.","cost_usd":0.12,"duration_ms":45000}
```

### Build a New Project
```bash
mkdir -p ~/projects/new-project && \
cd ~/projects/new-project && \
timeout 600 claude -p "Initialize a Python project with pyproject.toml, src layout, pytest, and a basic CLI" \
  --dangerously-skip-permissions \
  --model claude-opus-4-6
```

### Get a Second Opinion on Architecture
```bash
cd ~/projects/myproject && \
timeout 600 claude -p "Review the architecture of this project. Identify design flaws, suggest improvements, and flag any scalability concerns. Write your analysis to REVIEW.md." \
  --dangerously-skip-permissions \
  --allowedTools "Read,Write,Edit,Grep,Glob" \
  --model claude-opus-4-6
```

### Debug a Hard Problem
```bash
cd ~/projects/myproject && \
timeout 600 claude -p "The test test_auth_flow is failing with 'token expired'. Investigate root cause across all relevant files, fix it, and verify the fix passes." \
  --dangerously-skip-permissions \
  --model claude-opus-4-6
```

### Self-Evolution — Brain Maintenance
```bash
cd $CLARVIS_WORKSPACE/scripts && \
timeout 600 claude -p "Review brain.py, optimize query performance, improve error handling, and run benchmarks before/after" \
  --dangerously-skip-permissions \
  --model claude-opus-4-6
```

### Run a Python Script That Imports Brain
```bash
cd $CLARVIS_WORKSPACE && \
timeout 300 claude -p "Run: python3 scripts/cognition/clarvis_reflection.py and report the output" \
  --dangerously-skip-permissions \
  --model claude-opus-4-6
```
Note: Scripts that import chromadb/brain.py take 1-2 seconds to initialize. This is normal.
