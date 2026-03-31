# Claude Code Harness — Deep Architecture Analysis

**Source**: `data/external_src/claude-harness-src.zip` (1902 TypeScript/TSX files)
**Date**: 2026-03-31
**Purpose**: Extract patterns, mechanisms, and ideas portable to Clarvis/OpenClaw

---

## 1. Overall Architecture

The Claude Code harness is a **React/Ink terminal application** (Bun runtime) with:
- ~88 slash commands, plugin/skill/hook extension points
- 6 task types (local shell, local agent, remote agent, in-process teammate, workflow, dream)
- Defense-in-depth permission system (Zod validation → tool-specific validation → rule matching → hooks → classifier → user prompt)
- JSONL transcript persistence with UUID chain for interrupt recovery
- 4-type memory taxonomy (user/feedback/project/reference) in markdown frontmatter files

## 2. Highest-Value Findings for Clarvis

### 2.1 Tool Permission Pipeline (Defense-in-Depth)

The harness has a **5-layer permission gate** before any tool executes:
1. **Zod schema validation** — rejects malformed input
2. **Tool-specific validateInput()** — e.g., file write checks for external modification, UNC paths, denied directories, team secrets
3. **Permission rule matching** — cascading sources (policy > flags > local > project > user > CLI > session), with wildcard glob patterns
4. **Hook-based decisions** — PreToolUse hooks can approve/block/modify tool input
5. **Classifier** (auto-mode) — transcript-level safety classifier for bash commands

**Clarvis takeaway**: Our `spawn_claude.sh` uses `--dangerously-skip-permissions` which bypasses all of this. For any future multi-agent or user-facing mode, we need layered permission gates. The rule-source hierarchy (policy > project > user > session) is a good model.

### 2.2 Concurrent Tool Execution Model

Tools declare `isConcurrencySafe()` (default: false = serial). Read-only tools run in parallel batches (max 10), write tools run serially. This is enforced in `toolOrchestration.ts`.

**Clarvis takeaway**: Our heartbeat pipeline runs tools sequentially. For brain search + episodic recall + working memory lookups, parallel execution could cut preflight time significantly.

### 2.3 Context Assembly & Caching

System prompt is built from **cached sections** (memoized until `/clear` or `/compact`). A `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` separates static (cache-friendly) from dynamic (memory, MCP instructions) content. Anthropic's prompt caching (`cache_control: { type: 'ephemeral' }`) applies to static sections.

**Clarvis takeaway**: Our context_compressor rebuilds from scratch every heartbeat. Section-level caching with invalidation would reduce token waste.

### 2.4 Auto-Compact & Context Management (4-tier)

1. **Microcompact** — strips content at prompt-cache boundaries (cheapest)
2. **Context collapse** — archives old messages to summarization store
3. **History snip** — removes oldest messages if over threshold
4. **Autocompact** — full LLM summarization when tokens exceed threshold

Plus **reactive compaction** (feature-gated) that triggers on specific patterns.

**Clarvis takeaway**: Our context compression is single-tier. The graduated approach (microcompact → collapse → snip → full compact) preserves more information while staying within token budgets.

### 2.5 Session Persistence & Resume

JSONL transcript files (`~/.claude/projects/<dir>/<session-id>.jsonl`), one message per line. Resume flow:
- Deserializes messages, filters unresolved tool uses and orphaned thinking blocks
- Detects mid-turn interruptions, appends synthetic continuation prompt
- UUID parent chain prevents orphaning

**Clarvis takeaway**: Our episodic memory captures episode summaries but not full session transcripts. The JSONL-per-session approach would give us lossless replay and better conversation learning.

### 2.6 Memory System (4-Type Taxonomy)

- **user**: role, preferences, knowledge (private)
- **feedback**: corrections and confirmations from user (private, optionally team)
- **project**: ongoing work, goals, deadlines (team-biased)
- **reference**: pointers to external systems (usually team)

Memory selection uses a **Sonnet sideQuery** to pick up to 5 relevant files per turn. Files use markdown frontmatter (`name`, `description`, `type`). MEMORY.md is a 200-line index.

**Clarvis takeaway**: We have 10 brain collections but no structured taxonomy for what goes where. The user/feedback/project/reference split maps well to our identity/preferences/learnings/infrastructure collections. The "Sonnet picks relevant memories" approach is interesting vs. our embedding-only retrieval.

### 2.7 Coordinator Mode (Multi-Agent Orchestration)

Two modes: normal (direct chat) and coordinator (orchestrate workers). In coordinator mode:
- Only Agent, SendMessage, TaskStop tools available
- Workers get full tool access
- Results arrive as `<task-notification>` XML blocks
- Worker agents can run in git worktrees (isolated copies)

**Clarvis takeaway**: Our `project_agent.py` does basic spawn→result but lacks the coordinator abstraction. The "coordinator sees only orchestration tools, workers see execution tools" pattern is cleaner than our current model.

### 2.8 Hook System (14+ Lifecycle Events)

PreToolUse, PostToolUse, PostToolUseFailure, UserPromptSubmit, SessionStart, SessionEnd, Stop, StopFailure, PreCompact, PostCompact, PermissionRequest, PermissionDenied, SubagentStart/Stop, etc.

Hooks can be shell scripts, HTTP endpoints, or native callbacks. Exit code 2 = blocking error.

**Clarvis takeaway**: Our heartbeat has pre/postflight but no per-tool hooks. Adding PreToolUse/PostToolUse hooks to brain operations would enable policy enforcement, cost tracking per operation, and audit logging.

### 2.9 Skill System (Markdown Frontmatter + Prompt)

Skills are markdown files with YAML frontmatter (allowedTools, whenToUse, hooks, context). Loaded from bundled + project `.claude/skills/` + user `~/.claude/skills/` + plugins.

**Clarvis takeaway**: Our OpenClaw skills use `SKILL.md` which is similar. The `whenToUse` field for automatic model-driven skill selection is something we could adopt — currently our skills require explicit invocation.

### 2.10 Dream Task (Memory Consolidation)

A dedicated task type that runs a 4-stage memory consolidation agent:
- Reviews recent sessions, distills into topic files + MEMORY.md
- Tracks `filesTouched` and `phase` (starting → updating)
- Rolls back consolidation lock on kill

**Clarvis takeaway**: Our `dream_engine.py` does counterfactual dreaming. The harness's dream is more practical — it's session-log distillation into structured memory. We could add a similar "session distillation" step to our nightly pipeline.

### 2.11 Token Budget & Diminishing Returns Detection

`checkTokenBudget()` tracks per-agent token usage across iterations. Stops at 90% budget OR when detecting diminishing returns (<500 tokens/iteration after 3+ loops).

**Clarvis takeaway**: Our heartbeats have fixed timeouts. Budget-based stopping with diminishing-returns detection would be more efficient — stop early when making no progress instead of burning the full timeout.

### 2.12 Tool Result Size Management

Per-tool `maxResultSizeChars` limits. When exceeded: save full result to `/tmp/claude/tool-results/{messageId}/{toolUseId}`, return preview (first ~8k chars) + file path hint to model.

**Clarvis takeaway**: Our brain search results go directly into context with no size management. Large result sets could be persisted to disk with previews, reducing context bloat.

---

## 3. Architecture Patterns Worth Studying Further

### Queued for follow-up research passes:

| Area | What to investigate | Why it matters |
|------|-------------------|----------------|
| Sandbox adapter | `@anthropic-ai/sandbox-runtime` — file/network/process restrictions | Security model for tool execution |
| Bridge module | Remote control via WebSocket + HTTP hybrid transport | Mobile/web access to Clarvis |
| Classifier system | Auto-mode bash safety classifier | Automated permission decisions |
| Plugin architecture | Built-in + marketplace plugins with MCP/LSP/hooks | Extensibility model |
| Buddy/companion | Seeded PRNG companion generation | Fun UX, but also deterministic personalization |
| Voice module | STT/TTS with SoX, GrowthBook kill-switch | Voice interface for Clarvis |
| Worktree isolation | Git worktree per agent for safe parallel work | Agent isolation without containers |
| HybridTransport | WebSocket reads + HTTP POST writes | Proxy-friendly async transport |
| Reactive compaction | Pattern-triggered context shrinking | Smarter than threshold-only compaction |
| Tool deferred loading | `shouldDefer` + `ToolSearch` tool | Lazy tool schema loading to save context |

---

## 4. Key File Locations (in archive)

- `src/tools.ts` — Central tool registry (getAllBaseTools, getTools, assembleToolPool)
- `src/Tool.ts` — Tool interface (checkPermissions, isReadOnly, isDestructive, isConcurrencySafe)
- `src/query.ts` — Main query loop (10-step per-iteration pipeline)
- `src/services/tools/toolOrchestration.ts` — Concurrent/serial tool execution
- `src/services/tools/toolExecution.ts` — Per-tool execution (validate → permit → hooks → call)
- `src/utils/permissions/permissions.ts` — Permission rule system (3-tier decisions, 8 rule sources)
- `src/utils/sandbox/sandbox-adapter.ts` — OS-level sandboxing
- `src/memdir/memdir.ts` — Memory system (4-type taxonomy, MEMORY.md index)
- `src/memdir/findRelevantMemories.ts` — LLM-based memory selection (Sonnet sideQuery)
- `src/state/AppStateStore.ts` — Immutable state store (custom observer pattern)
- `src/utils/sessionStorage.ts` — JSONL transcript persistence
- `src/utils/conversationRecovery.ts` — Session resume with interrupt detection
- `src/coordinator/coordinatorMode.ts` — Multi-agent coordinator
- `src/tasks/` — 6 task types (LocalShell, LocalAgent, RemoteAgent, InProcessTeammate, Workflow, Dream)
- `src/bootstrap/state.ts` — Global state singleton (~50 fields)
- `src/hooks/` + `src/utils/hooks.ts` — 14+ lifecycle hook events
- `src/skills/bundledSkills.ts` — Skill definition format
- `src/plugins/builtinPlugins.ts` — Plugin architecture
- `src/commands.ts` — 88+ slash command registry
- `src/bridge/` — Remote control module (WebSocket + HTTP hybrid)
- `src/buddy/companion.ts` — Deterministic companion generation
- `src/voice/voiceModeEnabled.ts` — Voice mode kill-switch

---

## 5. Non-Obvious Insights

1. **Fail-closed defaults everywhere**: `isConcurrencySafe: false`, `isReadOnly: false`, `isDestructive: false`. New tools are safe-by-default.
2. **Prompt cache stability**: Tool pool sorted deterministically to maximize cross-request cache hits.
3. **Sticky header latches**: Beta headers (thinking, fast-mode) latch after first send to prevent cache churn on mid-session toggles.
4. **File write race detection**: Timestamps checked — if file was modified externally since last read, write is rejected.
5. **Diminishing returns detection**: Agent loops auto-terminate when producing <500 tokens/iteration after 3+ cycles.
6. **Dream consolidation rollback**: Kill signal rolls back consolidation lock mtime, preventing stale locks.
7. **UNC path rejection**: Prevents Windows NTLM credential leaks via `\\server\share` paths.
8. **50MB transcript cap**: `MAX_TRANSCRIPT_READ_BYTES` prevents OOM on huge sessions.
9. **Agent tool restrictions**: Agents can't use AgentTool (no recursion), AskUserQuestion (no UI), ExitPlanMode (UI-only).
10. **Coordinator tool isolation**: Coordinators see only Agent/SendMessage/TaskStop — forces delegation over direct action.
