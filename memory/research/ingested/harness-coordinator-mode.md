# Harness Coordinator Mode — Deep Research

**Date**: 2026-04-01
**Source**: Claude Code docs (code.claude.com), Anthropic engineering blog, Addy Osmani "Code Agent Orchestra", harness source analysis
**Task**: HARNESS_COORDINATOR_MODE

---

## 1. Two Distinct Multi-Agent Patterns in Claude Code

### 1.1 Subagents (Within-Session Delegation)
- Subagents run **inside** the parent session's process, each with its own context window
- Communication is **one-way**: subagent reports result back to caller, no peer-to-peer
- **Cannot spawn other subagents** (max depth = 1, no recursion)
- Tool isolation via `tools` allowlist or `disallowedTools` denylist in YAML frontmatter
- Built-in types: Explore (Haiku, read-only), Plan (read-only), General-purpose (all tools)
- Results return to parent context — many subagents = context bloat risk

### 1.2 Agent Teams (Cross-Session Coordination)
- Each teammate is a **separate Claude Code instance** with fully independent context
- **Peer-to-peer messaging** via SendMessage + shared task list with dependency tracking
- Lead coordinates, but teammates can message each other directly
- Stored locally: `~/.claude/teams/{name}/config.json`, `~/.claude/tasks/{name}/`
- Experimental (requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)
- Sweet spot: **3-5 teammates**, 5-6 tasks per teammate
- No nested teams (depth 1 only)

## 2. Coordinator Tool Isolation — The Core Pattern

The coordinator pattern enforces **role-based tool restriction at spawn time**:

```
Coordinator tools: Agent(worker, researcher), SendMessage, TaskStop, Read, Grep, Glob
Worker tools:      Read, Edit, Write, Bash, Grep, Glob (full execution)
```

**Key mechanism**: The `tools` field in subagent YAML frontmatter is an **allowlist**. If `Agent` is omitted, the agent cannot spawn subagents. `Agent(worker, researcher)` restricts which types can be spawned.

```yaml
# coordinator.md
---
name: coordinator
description: Coordinates work across specialized agents
tools: Agent(worker, researcher), Read, Bash
---
```

**Why this matters**: Forces the coordinator to **delegate, not execute**. The coordinator cannot edit files or write code — it can only read, plan, dispatch, and synthesize. This prevents the common failure mode where an orchestrator starts doing work itself instead of managing workers.

## 3. Communication Protocols

### 3.1 Subagent Communication
- Results arrive as `<task-notification>` XML blocks in parent context
- No back-channel — subagent cannot ask parent for clarification during execution
- Background subagents auto-deny permissions not pre-approved

### 3.2 Agent Team Communication
- **SendMessage**: targeted message to one teammate by agent ID
- **Broadcast**: message all teammates simultaneously (expensive — scales with team size)
- **Shared task list**: tasks with states (pending, in_progress, completed, blocked)
- Dependency tracking: blocked tasks auto-unblock when dependencies complete
- File locking prevents concurrent writes to same file
- Idle notifications: teammates auto-notify lead when they finish

## 4. Isolation Mechanisms

### 4.1 Git Worktree Isolation
- `isolation: "worktree"` in frontmatter gives agent its own git working copy
- Shared `.git/objects` (space efficient), atomic merge/discard
- Worktree auto-cleaned if agent makes no changes
- Enables true parallel work without file conflicts

### 4.2 Context Window Isolation
- Each subagent/teammate gets fresh context (no parent history)
- Loads project context independently (CLAUDE.md, MCP servers, skills)
- Auto-compaction at ~95% capacity (configurable via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`)

### 4.3 Permission Isolation
- Teammates inherit lead's permission mode at spawn
- Can override per-teammate post-spawn
- `permissionMode: "dontAsk"` = auto-deny (safe for autonomous workers)
- `permissionMode: "bypassPermissions"` = skip all checks (current Clarvis model)
- PreToolUse hooks enable fine-grained conditional validation (e.g., read-only SQL only)

## 5. Lifecycle Hooks Relevant to Coordination

| Hook | Fires When | Use Case |
|------|-----------|----------|
| SubagentStart | Worker begins execution | Setup (DB connections, context injection) |
| SubagentStop | Worker completes | Cleanup, result validation, promotion |
| TeammateIdle | Teammate about to go idle | Keep-alive, reassignment |
| TaskCreated | New task added to shared list | Validation, priority enforcement |
| TaskCompleted | Task marked done | Quality gate (tests, lint), auto-merge |
| PreToolUse | Before any tool call | Conditional tool restriction (hook exits code 2 to block) |

## 6. Key Lessons from Anthropic's Multi-Agent Research System

1. **Detailed task descriptions prevent duplication** — vague prompts cause workers to do identical work
2. **Explicit effort scaling**: 1 agent for simple queries, 10+ for complex research
3. **Synchronous execution is simpler but bottlenecks** — lead waits for all workers before proceeding
4. **Agents need heuristics, not rigid rules** — frameworks for collaboration > strict instructions
5. **Verification is the bottleneck, not generation** — knowing output is correct is the hard part

## 7. Lessons from "Code Agent Orchestra" (Osmani 2026)

1. **One file, one owner** — prevents merge conflicts, enables true parallelism
2. **Hard iteration limits** (MAX_ITERATIONS=8) with forced reflection after 3+ retries
3. **Human-curated institutional memory wins** — agent-written AGENTS.md reduces success ~3%, increases cost 20%
4. **Factory model**: Plan → Spawn → Monitor → Verify → Integrate → Retro
5. **Dedicated read-only reviewer agent** validates all output before lead reviews

## 8. Clarvis Application — Redesign Blueprint

### 8.1 Current State
- `project_agent.py`: flat spawn-and-wait, global lock (1 concurrent), `--dangerously-skip-permissions`
- `agent_orchestrator.py`: parallel execution pool (ThreadPoolExecutor), DAG dependencies, mailbox messaging
- `spawn_claude.sh`: worktree isolation skeleton (--isolated flag), single concurrent via global lock
- No tool-level isolation — all spawned agents get full capabilities

### 8.2 Proposed: Heartbeat as Coordinator

```
Clarvis Heartbeat (Coordinator)
  ├── Tools: spawn_worker(), send_message(), stop_worker(), read context
  ├── CANNOT: edit files, run bash, write code directly
  └── Dispatches to specialist workers:
      ├── Research Worker    — read-only tools, web access, brain search
      ├── Implementation Worker — full tool access, worktree isolation
      └── Maintenance Worker — restricted to brain ops, graph, cleanup scripts
```

**Implementation path**:
1. Define worker types as prompt templates with tool-constraint metadata
2. `project_agent.py` spawn accepts `worker_type` parameter selecting template
3. Heartbeat preflight scores tasks → routes to appropriate worker type
4. Workers return A2A protocol results (already implemented)
5. Heartbeat postflight validates + promotes results (already implemented)

### 8.3 Concrete Changes Needed

| Change | Effort | Impact |
|--------|--------|--------|
| Worker type templates (3 types: research/impl/maintenance) | S | Tool isolation foundation |
| Concurrent spawn slots (raise from 1 to 3) | S | Parallel workers |
| Worktree isolation for impl workers (wire existing skeleton) | M | Safe parallel file changes |
| Coordinator prompt mode in heartbeat (read-only dispatch) | M | Prevents coordinator self-execution |
| Per-worker-type tool restriction in spawn prompt | S | Enforced specialization |
| Budget-aware stopping (token tracking + diminishing returns) | M | Cost efficiency |

### 8.4 Bloat Score Relevance (Currently 0.400)
- **Research workers** (read-only) produce notes, not code — no bloat risk
- **Implementation workers** in worktrees prevent half-finished changes from polluting main
- **Maintenance workers** are explicitly tasked with cleanup — bloat-reducing by design
- The coordinator pattern itself reduces bloat: coordinator doesn't create files, only routes tasks
- **Net effect**: Positive. Worker specialization means implementation workers can include explicit anti-bloat instructions

---

## Sources
- [Claude Code Custom Subagents](https://code.claude.com/docs/en/sub-agents)
- [Claude Code Agent Teams](https://code.claude.com/docs/en/agent-teams)
- [Anthropic: How We Built Our Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Addy Osmani: The Code Agent Orchestra](https://addyosmani.com/blog/code-agent-orchestra/)
- [Harness Architecture Analysis (internal)](../claude_harness_architecture_2026-03-31.md)
