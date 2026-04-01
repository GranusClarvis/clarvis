# Codex Session Lifecycle, Context Management & Recovery — Deep Dive

**Date**: 2026-03-31
**Task**: [CODEX_SESSION_AND_CONTEXT_MODEL]
**Sources**: Plugin source (`/tmp/agent-orchestrator/packages/plugins/agent-codex/src/`), architecture doc, Codex repo analysis

---

## 1. Session Lifecycle (Source-Verified)

### Session Storage Structure
```
~/.codex/sessions/
  YYYY/
    MM/
      DD/
        rollout-<id>.jsonl    # Per-session rollout files (can be 100MB+)
```
- Date-sharded directories (max scan depth: 4 levels)
- JSONL format with typed line entries
- `session_meta` entry in first ~10 lines contains `cwd`, `model`
- `thread_started` events carry `threadId`
- `event_msg` with `token_count` subtype tracks `input_tokens`, `output_tokens`, `cached_tokens`, `reasoning_tokens`

### Session File Schema (from plugin parsing)
```typescript
interface CodexJsonlLine {
  type?: string;           // "session_meta" | "event_msg" | user events
  cwd?: string;            // workspace path (in session_meta)
  model?: string;          // model name (in session_meta)
  threadId?: string;       // thread identifier (from thread_started)
  content?: string;        // user message content
  role?: string;           // message role
  msg?: {
    type?: string;         // "token_count" for usage events
    input_tokens?: number;
    output_tokens?: number;
    cached_tokens?: number;
    reasoning_tokens?: number;
  };
}
```

### Separate History System
- `~/.codex/history.jsonl` — full conversation transcripts (separate from session rollout)
- `history.persistence`: `save-all | none`
- `history.max_bytes`: caps file size (e.g., 104857600 = 100 MiB); oldest entries dropped on overflow
- `history.sensitivePatterns` — regex array for filtering secrets from persisted history

### State Storage
- `sqlite_home` — SQLite state database (separate from JSONL)
- `CODEX_HOME` env var overrides root state dir (default: `~/.codex`)
- Auth stored in `auth.json` or OS keychain (`keyring-store` crate)

---

## 2. App-Server Protocol (Thread/Session Management)

Codex exposes a JSON-RPC v2 protocol via `codex app-server` subprocess (stdin/stdout):

### Thread Operations
| Method | Params | Purpose |
|--------|--------|---------|
| `thread/start` | `{model, modelProvider, cwd, approvalPolicy, sandbox, personality}` | Create new conversation |
| `thread/resume` | `{threadId}` | Restore existing thread |
| `thread/list` | `{cursor?, limit?}` | Paginated thread listing |
| `thread/archive` | `{threadId}` | Archive a thread |

### Turn Operations
| Method | Params | Purpose |
|--------|--------|---------|
| `turn/start` | `{threadId, input: [{type: "text", text}], cwd?, model?}` | Send message |
| `turn/interrupt` | `{threadId, turnId}` | Interrupt running turn |

### Protocol Handshake
1. Client sends `initialize` with `clientInfo` (name, title, version)
2. Server responds with capabilities
3. Client sends `initialized` notification
4. Client can now send thread/turn requests

### Approval Flow
- Server sends JSON-RPC request with `id` + approval details
- Client responds with `{decision: "accept" | "acceptForSession" | "decline" | "cancel"}`
- `acceptForSession` — persists approval for the entire session (no re-asking)

---

## 3. Session Recovery & Resume

### CLI Resume
```bash
codex resume <threadId>          # Restore full thread state
codex /resume                    # Interactive session picker with directory scoping
codex /fork                      # Clone current conversation into new thread
```

### Programmatic Resume (from plugin)
```typescript
// Find matching session by workspace path
const sessionFile = await findCodexSessionFile(workspacePath);
const data = await streamCodexSessionData(sessionFile);  // Streaming parse, avoids 100MB+ load

// Build restore command
`codex resume --model ${model} ${threadId}`
```

- Session file matching: scans `~/.codex/sessions/` recursively, reads first 4KB to check `session_meta.cwd`
- Streaming parser: processes JSONL line-by-line to aggregate model, threadId, token counts without full load
- 30s session file path cache (`SESSION_FILE_CACHE_TTL_MS`) prevents redundant filesystem scans

### Activity Detection
- Session file `mtime` used as activity proxy
- If mtime < threshold (default: ready threshold): agent is "active"
- If mtime > threshold: agent is "idle"
- No process heartbeat — relies on continuous JSONL append during work

---

## 4. Context Window Management

### Auto-Compaction
- `model_auto_compact_token_limit` — token threshold triggering automatic history compaction
- `model_context_window` — override auto-detected context size
- Compaction summarizes visible conversation to free tokens

### Manual Compaction
- `/compact` slash command — on-demand compaction
- `compact_prompt` — custom compaction system prompt
- `experimental_compact_prompt_file` — load compaction prompt from file

### Reasoning Controls
| Config | Values | Purpose |
|--------|--------|---------|
| `model_reasoning_effort` | `minimal, low, medium, high, xhigh` | Control reasoning depth |
| `model_reasoning_summary` | `auto, concise, detailed, none` | Reasoning visibility |
| `model_verbosity` | `low, medium, high` | Response verbosity (GPT-5) |

### Token Budget (Multi-Agent)
- Per-agent budget with diminishing-returns detection
- Auto-stops agents producing <500 tokens/iteration after 3+ loops
- `job_max_runtime_seconds = 1800` timeout per worker

---

## 5. Three-Way Comparison: Session & Context Models

### Session Persistence

| Aspect | Codex | Claude Harness | Clarvis |
|--------|-------|----------------|---------|
| **Format** | JSONL (date-sharded rollout files) | JSONL (UUID-chained transcripts) | Episodic memory summaries (JSON) |
| **Storage** | `~/.codex/sessions/YYYY/MM/DD/` | Session-specific JSONL files | `data/episodic_memory.json` + ChromaDB |
| **Size Management** | Streaming parse for 100MB+ files; max_bytes cap on history | Orphan filtering, interrupt detection | Summary-based (never grows large) |
| **Resume** | `codex resume <threadId>` — full thread restore | UUID chain + synthetic resume message | No resume — each heartbeat is independent |
| **Session Identity** | ThreadId (UUID) | Conversation UUID chain | Episode ID + reasoning chain ID |
| **Token Tracking** | Per-session input/output/cached/reasoning tokens | Per-turn token counting | Per-heartbeat cost tracking (clarvis-cost) |

### Context Compaction

| Aspect | Codex | Claude Harness | Clarvis |
|--------|-------|----------------|---------|
| **Strategy** | Threshold-triggered auto-compact + manual `/compact` | 4-tier graduated: microcompact→collapse→snip→autocompact | Single-tier `context_compressor.py` |
| **Customization** | Custom compact prompts (inline or file) | Feature-gated, pattern-reactive | Template-based brief generation |
| **Granularity** | Binary (compact or don't) | Progressive (preserve more at lower tiers) | Binary |
| **Reasoning Budget** | 5-level effort control + summary modes | Extended thinking with budget | N/A |
| **Token Limits** | Per-agent diminishing-returns detection | 90% threshold OR <500 tok/iteration | Fixed timeouts only |

### Recovery Semantics

| Aspect | Codex | Claude Harness | Clarvis |
|--------|-------|----------------|---------|
| **Crash Recovery** | ThreadId persisted in JSONL → resume picks up | UUID chain + orphan detection → synthetic resume | No crash recovery (heartbeats are ephemeral) |
| **Interrupt Handling** | `turn/interrupt` via app-server protocol | Interrupt detection in session storage | SIGTERM → trap cleanup in lockfiles |
| **State Continuity** | Full thread state restore (context, tools, approvals) | Full conversation restore (messages, tool results) | No continuity — each run starts fresh |
| **Activity Detection** | Session file mtime as proxy (no heartbeat needed) | Process-level monitoring | PID lockfile existence check |

---

## 6. Lessons for Clarvis

### What We Should Adopt (Priority-Ordered)

#### P1: Session JSONL Transcript (from both Codex + Harness)
**Gap**: Clarvis heartbeats produce episodic summaries but no raw transcript. We can't replay, audit, or learn from the full conversation flow.
**Proposal**: Add JSONL append to `spawn_claude.sh` and heartbeat pipeline:
```
{timestamp, type: "session_start|turn|tool_use|result|session_end", content, tokens}
```
Store in `data/sessions/YYYY-MM-DD/heartbeat-<id>.jsonl`. Feed to `conversation_learner.py`.

#### P1: Activity Detection via File Mtime
**Gap**: Our watchdog uses PID lockfile checks and process scanning. Codex's mtime-based approach is simpler and more reliable.
**Proposal**: Have Claude Code spawns write a heartbeat marker file. Watchdog checks mtime instead of parsing process tables.

#### P2: Graduated Context Compaction
**Gap**: `context_compressor.py` is single-tier — summarize or don't. Both Codex and Harness have progressive strategies.
**Proposal**: Add tiers to `context_compressor.py`:
1. **Micro**: Drop tool result details, keep summaries
2. **Working**: Compress old context sections, keep recent
3. **Full**: LLM summarization (current behavior)

#### P2: Token Budget with Diminishing Returns
**Gap**: We use fixed timeouts (600-1800s). Codex detects <500 tok/iteration after 3+ loops.
**Proposal**: Parse Claude Code output for token usage. If 3+ iterations produce <500 tokens each, trigger early termination in `spawn_claude.sh`.

#### P3: Thread Resume for Long-Running Tasks
**Gap**: Each heartbeat starts fresh. Codex and Harness both support continuing conversations.
**Proposal**: For multi-step tasks in QUEUE.md, persist thread context between heartbeats via session JSONL + resume prompt injection.

---

## 7. Architectural Insight

Codex's session model reflects its **developer-tool philosophy**: sessions are conversations that humans want to return to. The app-server protocol (`thread/start`, `thread/resume`, `turn/start`) maps directly to IDE workflows where a developer starts a task, gets interrupted, and resumes later.

Clarvis's model reflects its **autonomous-agent philosophy**: heartbeats are ephemeral task executions. Each one starts fresh because the "memory" lives in the brain (ChromaDB), not in conversation history. This is actually a strength for autonomous operation — no session corruption, no stale context accumulation.

**The synthesis**: Keep ephemeral heartbeats as the primary execution model, but add JSONL transcripts as an observability layer (for learning and audit, not for resume). Adopt graduated compaction to better use context windows within each heartbeat. Consider thread resume only for explicitly multi-step tasks that span heartbeat boundaries.

---

## Success Criteria Met
- [x] Inspected Codex source in depth for session lifecycle (JSONL structure, date-sharding, streaming parse)
- [x] Analyzed conversation persistence (rollout files, history.jsonl, session_meta, thread/turn protocol)
- [x] Documented context-window management (auto-compact, manual compact, reasoning controls, token budgets)
- [x] Documented recovery semantics (thread resume, activity detection via mtime, crash recovery)
- [x] Compared directly to harness transcript/recovery model (UUID chain, interrupt detection, 4-tier compaction)
- [x] Compared to heartbeat/session history approach (ephemeral vs persistent, summary vs transcript)
- [x] Produced actionable adoption priorities with proposals
