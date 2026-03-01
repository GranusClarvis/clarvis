# ComposioHQ Agent Orchestrator — Architecture Analysis

## Executive Summary

ComposioHQ's **Agent Orchestrator** is a production-grade TypeScript system for orchestrating parallel AI coding agents across isolated execution environments. It manages the complete lifecycle from workspace creation through PR merge, implementing a sophisticated **eight-slot plugin architecture** that decouples agents, runtimes, workspaces, trackers, and notification channels.

**Core Philosophy:** "Push, not pull." Spawn agents, walk away, get notified only when human judgment is needed. Auto-handle routine feedback (CI failures, review comments), escalate edge cases.

---

## 1. Multi-Agent Architecture Overview

### 1.1 Core Concept: Eight Swappable Slots

Agent Orchestrator treats orchestration as a **pluggable system** where eight concerns are completely decoupled:

| Slot | Purpose | Default | Alternatives |
|------|---------|---------|-------------|
| **Runtime** | Where sessions execute | tmux | Docker, Kubernetes, process, SSH, E2B |
| **Agent** | Which AI coding tool | Claude Code | Codex, Aider, OpenCode |
| **Workspace** | Code isolation mechanism | git worktree | git clone, full copy |
| **Tracker** | Issue/ticket system | GitHub Issues | Linear, Jira |
| **SCM** | PR/CI/review management | GitHub | GitLab |
| **Notifier** | Human notifications | Desktop | Slack, Discord, webhooks, email |
| **Terminal** | Human interaction UI | iTerm2 | Web dashboard, none |
| **Lifecycle** | Core state machine | (built-in) | Not pluggable |

**Key insight:** Every interface is defined as TypeScript, all plugins implement one interface, and the core system never contains agent/runtime/tracker-specific logic.

### 1.2 Session as Unit of Orchestration

Each spawned agent runs as a **session**—a fully isolated container of work:

```
Session = {
  id: "my-app-3"           # unique identifier
  projectId: "my-app"      # which project
  status: "working"        # lifecycle state (spawning → working → pr_open → ci_failed → ...)
  branch: "feat/issue-99"  # git branch
  workspacePath: "/tmp/..." # isolated code directory
  runtimeHandle: {...}     # how to communicate with agent (tmux session, container ID, etc.)
  pr: { number, url, ...}  # PR info once created
  agentInfo: { summary, cost, sessionId }  # agent's own data
}
```

**Sessions are persistent**: metadata stored as flat JSON files, allowing crash recovery, monitoring, and multi-process safety via lock files.

---

## 2. Workspace Isolation Mechanisms

### 2.1 Two Isolation Strategies

#### **Workspace Strategy 1: Git Worktree (Primary)**
- Creates lightweight git worktree on same filesystem
- Each session gets isolated branch without full repo duplication
- Fast: ~100ms vs. ~5s for clone
- Memory efficient: shared object database
- **Pattern:** `/home/user/.worktrees/project-id/session-id/`

```typescript
// From workspace-worktree plugin
const worktreeCmd = [
  "git", "worktree", "add",
  "--track",
  "-b", "feat/issue-99",
  "/path/to/worktree/session-id",
  "origin/main"
];
```

#### **Workspace Strategy 2: Full Clone (Fallback)**
- Complete `git clone` for maximum isolation
- Slower but works when worktrees aren't possible
- Each clone has independent git state, remotes, config
- **Pattern:** `/home/user/.ao-clones/project-id/session-id/`

```typescript
// From workspace-clone plugin
const clonePath = join(cloneBaseDir, projectId, sessionId);
const remoteUrl = await git(sourceRepo, "remote", "get-url", "origin");
await git(clonePath, "clone", remoteUrl, clonePath);
```

### 2.2 Isolation Guarantees

Each workspace gets:
1. **Independent git branch** — agents never interfere
2. **Isolated filesystem** — separate node_modules, build artifacts
3. **Independent git state** — separate index, reflog, hooks
4. **Optional symlinks** — shared configs (.env, .claude) via symlink overlay
5. **Optional post-create hooks** — per-project setup (pnpm install, etc.)

**Safety:** Session-scoped paths validate all IDs with regex to prevent directory traversal:
```typescript
const SAFE_PATH_SEGMENT = /^[a-zA-Z0-9_-]+$/;
if (!SAFE_PATH_SEGMENT.test(sessionId)) {
  throw new Error(`Invalid session ID: ${sessionId}`);
}
```

---

## 3. Agent Communication Protocol

### 3.1 Bidirectional Event-Driven Communication

Agent Orchestrator uses **pull-based activity detection** combined with **push-based message delivery**:

```
┌─────────────────────────────────────────┐
│  Lifecycle Manager (Polling Loop)       │
├─────────────────────────────────────────┤
│ Every 5 seconds:                        │
│  1. Detect activity from each agent     │
│  2. Poll PR/CI/review state via SCM API │
│  3. Emit events on state transitions    │
│  4. Execute reactions (auto-fixes)      │
│  5. Push notifications to human         │
└─────────────────────────────────────────┘
         ↕                          ↕
    [Agents]              [GitHub API / SCM]
```

### 3.2 Activity Detection

**From agent plugin perspective:**

```typescript
export interface Agent {
  // Detect what agent is doing from terminal output (fallback)
  detectActivity(terminalOutput: string): ActivityState;

  // Preferred: native activity detection (e.g., Claude Code session file)
  getActivityState(session: Session, readyThresholdMs?: number):
    Promise<ActivityDetection | null>;

  // Check if process is still running
  isProcessRunning(handle: RuntimeHandle): Promise<boolean>;
}
```

**Activity states:**
- `"active"` — agent is processing (thinking, writing code)
- `"ready"` — agent finished its turn, alive and waiting for input
- `"idle"` — agent inactive for >5 minutes (stale)
- `"waiting_input"` — agent is asking a question
- `"blocked"` — agent hit an error
- `"exited"` — process stopped

### 3.3 Message Delivery

**Two patterns for sending prompts to agents:**

#### Pattern 1: Inline (Default)
```typescript
agent.getLaunchCommand(config)
// => "claude -p 'Fix the failing tests' --dangerously-skip-permissions"
```
Issue: Large prompts get truncated by shell/tmux (>200 chars).

#### Pattern 2: Post-Launch (For Long Prompts)
```typescript
promptDelivery: "post-launch"
// 1. Start agent in interactive mode (no initial prompt)
// 2. Wait for readiness signal
// 3. Send prompt via runtime.sendMessage(handle, prompt)
```

**Implementation in runtime-tmux:**
```typescript
if (config.launchCommand.length > 200) {
  // Write to temp file, load into tmux buffer, paste
  const bufferName = `ao-launch-${randomUUID().slice(0, 8)}`;
  await tmux("load-buffer", "-b", bufferName, tmpPath);
  await tmux("paste-buffer", "-b", bufferName, "-t", sessionName, "-d");
}
```

---

## 4. Lifecycle State Machine

### 4.1 Session Status Transitions

```
spawning
  ↓
working (agent writing code)
  ├→ pr_open (agent created PR)
  │   ├→ ci_failed (tests failed)
  │   │   └→ working (auto-retry, or manual instruction)
  │   ├→ review_pending (waiting for human review)
  │   │   ├→ changes_requested (auto-fix or escalate)
  │   │   └→ approved
  │   │       ├→ mergeable (green CI + approval)
  │   │       └→ merged
  └→ stuck | errored | needs_input
      └→ (human escalation)
```

**Terminal statuses:** `merged`, `killed`, `done`, `errored`, `terminated`

### 4.2 Reaction System

Reactions are **automatic responses** to state transitions, configurable per project:

```yaml
reactions:
  ci-failed:
    auto: true                 # enable auto-handling
    action: send-to-agent      # route CI output back to agent
    retries: 2                 # max retry attempts
    escalateAfter: 2           # escalate if >2 attempts fail

  changes-requested:
    auto: true
    action: send-to-agent
    escalateAfter: 30m         # escalate if not resolved in 30m

  approved-and-green:
    auto: false                # disable auto-merge (human decides)
    action: notify             # just notify
    priority: action           # high-priority notification
```

**Event types emitted:**
- Session: `spawned`, `working`, `exited`, `stuck`, `needs_input`, `errored`
- PR: `created`, `updated`, `merged`, `closed`
- CI: `passing`, `failing`, `fix_sent`, `fix_failed`
- Review: `pending`, `approved`, `changes_requested`, `comments_sent`, `comments_unresolved`
- Reactions: `triggered`, `escalated`

---

## 5. SCM Integration (GitHub Example)

### 5.1 Rich PR Lifecycle Tracking

```typescript
export interface SCM {
  // PR Detection & State
  detectPR(session, project): Promise<PRInfo | null>;
  getPRState(pr): Promise<"open" | "merged" | "closed">;
  getPRSummary?(pr): Promise<{ state, title, additions, deletions }>;

  // PR Actions
  mergePR(pr, method?): Promise<void>;  // merge | squash | rebase
  closePR(pr): Promise<void>;

  // CI Integration
  getCIChecks(pr): Promise<CICheck[]>;       // individual checks
  getCISummary(pr): Promise<CIStatus>;       // overall: pending|passing|failing|none

  // Review Tracking (comprehensive)
  getReviews(pr): Promise<Review[]>;
  getReviewDecision(pr): Promise<"approved" | "changes_requested" | "pending" | "none">;
  getPendingComments(pr): Promise<ReviewComment[]>;
  getAutomatedComments(pr): Promise<AutomatedComment[]>;  // lint, security, etc.

  // Merge Readiness
  getMergeability(pr): Promise<{
    mergeable: boolean;
    ciPassing: boolean;
    approved: boolean;
    noConflicts: boolean;
    blockers: string[];
  }>;
}
```

### 5.2 Implementation: GitHub Plugin (via `gh` CLI)

```typescript
async function getReviewDecision(pr: PRInfo): Promise<ReviewDecision> {
  const raw = await gh([
    "pr", "view", String(pr.number),
    "--repo", `${pr.owner}/${pr.repo}`,
    "--json", "reviewDecision"
  ]);
  const data = JSON.parse(raw);
  return data.reviewDecision;  // "APPROVED" | "CHANGES_REQUESTED" | "PENDING"
}
```

**Key pattern:** All plugins use `gh` CLI, wrapped with:
- **Error handling** — typed exceptions with context
- **Timeouts** — 30 second max per command
- **Buffering** — 10MB max output (prevents OOM)
- **JSON parsing** — wrapped in try/catch for corrupted responses

---

## 6. Plugin Architecture Deep Dive

### 6.1 Plugin Module Contract

Every plugin exports a **PluginModule** with compile-time type verification:

```typescript
export const manifest = {
  name: "claude-code",
  slot: "agent" as const,
  description: "AI coding agent: Claude Code",
  version: "0.1.0",
};

export function create(config?: Record<string, unknown>): Agent {
  return {
    name: "claude-code",
    processName: "claude",

    getLaunchCommand(config: AgentLaunchConfig): string {
      return `/home/agent/.local/bin/claude \
        --dangerously-skip-permissions \
        -p "${config.prompt}"`;
    },

    async getActivityState(session, readyThresholdMs) {
      // Read Claude Code's internal state file
      const sessionFile = join(
        session.workspacePath,
        ".claude/metadata.jsonl"
      );
      const lines = readFileSync(sessionFile, "utf-8").split("\n");
      const lastEntry = JSON.parse(lines[lines.length - 2]);

      return {
        state: lastEntry.isWaiting ? "ready" : "active",
        timestamp: new Date(lastEntry.timestamp)
      };
    },

    // ... other methods
  };
}

export default { manifest, create } satisfies PluginModule<Agent>;
```

**Critical pattern:** Use `satisfies PluginModule<Agent>` for **compile-time interface verification**. If any method is missing or has wrong signature, TypeScript fails immediately.

### 6.2 Plugin Registry

```typescript
class PluginRegistry {
  register(plugin: PluginModule, config?: Record<string, unknown>): void;
  get<T>(slot: PluginSlot, name: string): T | null;
  list(slot: PluginSlot): PluginManifest[];
  async loadBuiltins(config?: OrchestratorConfig): Promise<void>;
}
```

**Loading plugins:**
```typescript
const registry = createPluginRegistry();

// Load built-in plugins (tmux, claude-code, github, etc.)
await registry.loadBuiltins(config);

// Get a runtime implementation
const runtime = registry.get<Runtime>("runtime", "tmux");

// Get agent implementation
const agent = registry.get<Agent>("agent", "claude-code");
```

---

## 7. Metadata Storage & Persistence

### 7.1 Flat-File Metadata (No Database)

Session metadata stored as JSON files in `~/.agent-orchestrator/`:

```
~/.agent-orchestrator/
├── sessions/
│   ├── my-app-1.json          # Session metadata
│   ├── my-app-2.json
│   └── archive/               # Merged sessions
│       └── my-app-1.json
├── events.jsonl               # All events (append-only log)
└── config.yaml.checksum       # For detecting config changes
```

**Session metadata example:**
```json
{
  "id": "my-app-1",
  "projectId": "my-app",
  "status": "pr_open",
  "activity": "ready",
  "branch": "feat/issue-99",
  "issueId": "123",
  "workspacePath": "/home/user/.worktrees/my-app/my-app-1",
  "runtimeHandle": {
    "id": "my-app-1",
    "runtimeName": "tmux",
    "data": { "createdAt": 1709203200000 }
  },
  "pr": {
    "number": 42,
    "url": "https://github.com/acme/app/pull/42",
    "title": "feat: add feature",
    "owner": "acme",
    "repo": "app",
    "branch": "feat/issue-99",
    "baseBranch": "main",
    "isDraft": false
  },
  "agentInfo": {
    "summary": "Fixed failing tests",
    "agentSessionId": "claude-session-xyz",
    "cost": {
      "inputTokens": 5000,
      "outputTokens": 2000,
      "estimatedCostUsd": 0.042
    }
  },
  "createdAt": "2025-03-01T10:00:00Z",
  "lastActivityAt": "2025-03-01T10:15:30Z",
  "metadata": {
    "custom_field": "custom_value"
  }
}
```

### 7.2 Append-Only Event Log

```
events.jsonl (each line is a JSON object)
{"id":"evt-1","type":"session.spawned","priority":"info","sessionId":"my-app-1","timestamp":"2025-03-01T10:00:00Z",...}
{"id":"evt-2","type":"session.working","priority":"info","sessionId":"my-app-1","timestamp":"2025-03-01T10:00:05Z",...}
{"id":"evt-3","type":"pr.created","priority":"action","sessionId":"my-app-1","timestamp":"2025-03-01T10:10:00Z",...}
```

**Advantages:**
- Crash-safe (append-only)
- Complete audit trail
- No locking (only append, no corruption risk)
- Queryable (simple line-based filtering)

### 7.3 Concurrency Safety

**Lock file pattern (in `/tmp/`):**
```typescript
const lockPath = `/tmp/clarvis_${sessionId}.lock`;

// Acquire lock with stale detection
if (existsSync(lockPath)) {
  const mtime = statSync(lockPath).mtime.getTime();
  if (Date.now() - mtime > 5 * 60_000) {  // 5 min stale
    unlinkSync(lockPath);  // Force release
  } else {
    throw new Error(`Session locked by another process`);
  }
}

try {
  writeFileSync(lockPath, String(process.pid));
  // Safe to modify session metadata
} finally {
  unlinkSync(lockPath);  // Release lock
}
```

---

## 8. Testing Patterns

### 8.1 Plugin Integration Testing

Tests verify full path: **core service → real plugin → mocked external API**

```typescript
import { describe, it, expect, vi } from "vitest";

// Mock execFile at module level (before plugin imports)
const { ghMock } = vi.hoisted(() => ({ ghMock: vi.fn() }));
vi.mock("node:child_process", () => ({
  execFile: Object.assign(vi.fn(), {
    [Symbol.for("nodejs.util.promisify.custom")]: ghMock
  })
}));

// Real tracker plugin imported AFTER mock is hoisted
import trackerGithub from "@composio/ao-plugin-tracker-github";

describe("tracker-github", () => {
  it("fetches issue details", async () => {
    // Mock gh CLI response
    ghMock.mockResolvedValueOnce({
      stdout: JSON.stringify({
        number: 42,
        title: "Bug report",
        body: "...",
        state: "OPEN"
      })
    });

    const tracker = trackerGithub.create();
    const issue = await tracker.getIssue("42", projectConfig);

    expect(issue.id).toBe("42");
    expect(issue.title).toBe("Bug report");
  });
});
```

### 8.2 Session Manager Tests (60+ cases)

Covers:
- Session spawn/destroy lifecycle
- Metadata persistence
- Concurrent session safety
- PR detection and tracking
- State transition validation

```typescript
it("prevents concurrent session modifications", async () => {
  const sessionId = "my-app-1";
  const handle1 = sessionManager.spawn(config);

  // Try to spawn same session again (should fail)
  await expect(sessionManager.spawn(config))
    .rejects.toThrow("Session locked");
});
```

### 8.3 Lifecycle Manager Tests (24+ cases)

Covers:
- Event emission on state transitions
- Reaction triggering
- Escalation logic
- Notification routing

```typescript
it("escalates CI failure after retries", async () => {
  const session = makeSession({ status: "ci_failed" });
  const events: OrchestratorEvent[] = [];

  lifecycleManager.on("event", (e) => events.push(e));

  // Trigger auto-fix reaction (retry 1)
  await lifecycleManager.handleReaction(session, "ci-failed");
  expect(events).toContainEqual({ type: "ci.fix_sent" });

  // Simulate fix failed, retry 2
  session.status = "ci_failed";
  await lifecycleManager.handleReaction(session, "ci-failed");

  // After retries exhausted, escalate
  expect(events).toContainEqual({ type: "reaction.escalated" });
});
```

**Test coverage:** 3,288 test cases across core, plugins, and web packages.

---

## 9. Web Dashboard Architecture

### 9.1 Real-Time Session Monitoring

**Next.js 15 App Router** with **Server-Sent Events (SSE)** for live updates:

```typescript
// API route: GET /api/events
export async function GET(request: Request) {
  const controller = new AbortController();
  const stream = new ReadableStream({
    start(enqueue) {
      // Poll lifecycle manager every 1s
      const interval = setInterval(() => {
        const events = lifecycleManager.pollSinceLastId(lastSeenId);
        for (const event of events) {
          enqueue(`data: ${JSON.stringify(event)}\n\n`);
          lastSeenId = event.id;
        }
      }, 1000);

      request.signal.addEventListener("abort", () => {
        clearInterval(interval);
      });
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache"
    }
  });
}
```

**Frontend hooks:**
```typescript
export function useSessionEvents() {
  const [events, setEvents] = useState<OrchestratorEvent[]>([]);

  useEffect(() => {
    const eventSource = new EventSource("/api/events");
    eventSource.onmessage = (e) => {
      setEvents(prev => [...prev, JSON.parse(e.data)]);
    };
    return () => eventSource.close();
  }, []);

  return events;
}
```

### 9.2 Dashboard Features

- **Session list** — status, branch, PR link, agent activity
- **Real-time activity** — color-coded status (spawning→working→pr_open→merged)
- **PR/CI view** — CI check status, review decisions, merge readiness
- **Manual controls** — send message, kill session, restore crashed session
- **Event log** — searchable, filterable audit trail

---

## 10. Key Design Decisions & Lessons

### 10.1 Why Eight Slots?

The orchestrator separates concerns because:

1. **Agents vary wildly** — Claude Code, Codex, Aider have different launch commands, session formats, activity detection
2. **Runtimes vary** — tmux, Docker, Kubernetes, SSH, cloud sandboxes all have different APIs
3. **Trackers vary** — GitHub Issues, Linear, Jira have different APIs and data models
4. **Notifications vary** — desktop, Slack, Discord have different integrations
5. **Organizations vary** — some use GitHub, some use GitLab; some use Linear, some use Jira

By making each a plugin slot, you add support for a new agent/runtime/tracker by implementing one interface.

### 10.2 Stateless Orchestrator

No database, no server state beyond flat JSON files. Why?

- **Simple** — understand everything by reading files
- **Debuggable** — view session state as plain JSON
- **Crash-safe** — no in-memory state to lose
- **Multi-process safe** — lock files handle concurrency
- **Portable** — move `~/.agent-orchestrator/` to another machine

### 10.3 Push Notifications, Not Dashboard-Centric

The Notifier is the primary human interface, not the web dashboard. Why?

- **Human-centric** — notifications interrupt human's workflow (intentional)
- **Mobile-friendly** — push to Slack/Discord/email, not just browser
- **Respects attention** — no constant dashboard checking
- **Event-driven** — react to important state transitions, not polling

### 10.4 Two-Tier Event Handling

1. **Tier 1 (Auto):** Routine issues (CI failed → route to agent for retry)
2. **Tier 2 (Escalate):** Edge cases (retry exhausted → notify human)

This balance prevents:
- **Alert fatigue** — no notification for every CI failure
- **Lost autonomy** — human shouldn't micro-manage
- **Silent failures** — important issues still escalate

---

## 11. Applicability to Clarvis's Agent Orchestrator

### 11.1 Recommended Patterns to Adopt

#### 1. **Plugin Architecture**
```
Current Clarvis: Brain, heartbeat, cron scripts mixed together
Recommended: Extract runtimes, trackers, notification as plugins
Example: A "github" tracker plugin, a "telegram" notifier plugin
```

#### 2. **Workspace Isolation**
```
Current Clarvis: Projects share scripts/, brain/, memory/
Recommended: Per-project workspace isolation (like worktrees)
File structure:
  /home/agent/agents/<name>/workspace/   (isolated repo)
  /home/agent/agents/<name>/data/brain/  (isolated ChromaDB)
  /home/agent/agents/<name>/memory/      (isolated memories)
```

#### 3. **Session State Machine**
```
Current Clarvis: Tasks go into QUEUE.md, manually tracked
Recommended: Explicit session states + lifecycle manager
States: spawning → working → pr_open → ci_failed → review_pending → mergeable → merged
Events: pr.created, ci.failing, review.approved (routable to notifiers)
```

#### 4. **Metadata as JSON**
```
Current Clarvis: Memories in ChromaDB, memories in markdown
Recommended: Flat JSON for session state (like ~/.agent-orchestrator/sessions/)
Benefits: Debuggable, crash-safe, multi-process safe
```

#### 5. **Activity Detection**
```
Current Clarvis: Heartbeat checks "did recent cron job finish?"
Recommended: Rich activity states (active, ready, idle, blocked, waiting_input)
Mapping: Check output file mtime, JSONL session log, process existence
```

### 11.2 What NOT to Copy

1. **TypeScript + npm workspace** — Clarvis uses Python, which is fine
2. **Strictly 8 slots** — Clarvis could have 5-6 slots (brain, runtime, task router, reaction engine, notifier)
3. **Git worktrees** — Clarvis already has isolated `agents/` directories, but could adopt worktree pattern for sub-projects

### 11.3 Hybrid Architecture for Clarvis

```
Clarvis (Orchestrator Core)
├── Python-based agent lifecycle manager
│   ├── Session state machine (like lifecycle-manager.ts)
│   ├── Plugin registry (runtime, task router, notifier)
│   └── Metadata store (JSON sessions + JSONL events)
├── Project Agents (isolated)
│   ├── workspace/ (cloned repo, isolated git)
│   ├── data/brain/ (lite ChromaDB, 5 collections)
│   └── memory/ (markdown daily logs)
└── Notifiers (Telegram, email, webhook)
```

**Python plugin interfaces:**
```python
class Runtime(ABC):
    async def create(self, config: RuntimeCreateConfig) -> RuntimeHandle: ...
    async def spawn_agent(self, handle: RuntimeHandle, prompt: str) -> None: ...
    async def get_output(self, handle: RuntimeHandle) -> str: ...

class TaskRouter(ABC):
    def route(self, task: str) -> Tuple[str, str]:  # (model, prompt)
        """Route task to optimal model by complexity"""

class Notifier(ABC):
    async def notify(self, event: OrchestratorEvent) -> None: ...
```

---

## 12. Summary: Key Takeaways

### Principles
1. **Decouple concerns via plugins** — agents, runtimes, trackers, notifiers are independently swappable
2. **Stateless orchestration** — flat JSON + event log, no database
3. **Rich state machines** — explicit session states enable robust error handling
4. **Two-tier reactions** — auto-fix routine issues, escalate edge cases to human
5. **Activity-driven polling** — detect what agent is doing natively, not via shell parsing
6. **Push over pull** — notifications interrupt workflow, dashboard is secondary

### Architecture
- **8 plugin slots** — Runtime, Agent, Workspace, Tracker, SCM, Notifier, Terminal, Lifecycle
- **Session as unit** — each spawned agent is a session with persistent metadata
- **Workspace isolation** — git worktree (fast) or clone (maximum isolation)
- **Event-driven lifecycle** — state machine emits events, reactions triggered, humans notified
- **Rich PR/CI tracking** — comprehensive SCM interface covers full pipeline

### Testing
- **Plugin integration tests** — mock external APIs, test real plugin code
- **Session manager tests** — cover spawn, destroy, metadata persistence, concurrency
- **Lifecycle tests** — test state transitions, reaction triggering, escalation logic
- **3,288 test cases** — comprehensive coverage across all packages

---

## 13. File Reference: Key Source Files

**Core Types & Config:**
- `/tmp/agent-orchestrator/packages/core/src/types.ts` — All interfaces (780+ lines)
- `/tmp/agent-orchestrator/packages/core/src/session-manager.ts` — CRUD for sessions
- `/tmp/agent-orchestrator/packages/core/src/lifecycle-manager.ts` — State machine + reactions
- `/tmp/agent-orchestrator/agent-orchestrator.yaml.example` — Config format

**Plugin Examples:**
- `/tmp/agent-orchestrator/packages/plugins/runtime-tmux/src/index.ts` — tmux plugin
- `/tmp/agent-orchestrator/packages/plugins/workspace-clone/src/index.ts` — Clone isolation
- `/tmp/agent-orchestrator/packages/plugins/tracker-github/src/index.ts` — GitHub integration

**Testing:**
- `/tmp/agent-orchestrator/packages/core/src/__tests__/plugin-integration.test.ts` — How to test plugins
- `/tmp/agent-orchestrator/packages/core/src/__tests__/session-manager.test.ts` — Session lifecycle tests

**Documentation:**
- `/tmp/agent-orchestrator/CLAUDE.md` — Code conventions, plugin pattern, TypeScript rules
- `/tmp/agent-orchestrator/README.md` — User-facing overview

---

## Appendix: Configuration Example

```yaml
# agent-orchestrator.yaml
port: 3000
dataDir: ~/.agent-orchestrator
worktreeDir: ~/.worktrees

defaults:
  runtime: tmux
  agent: claude-code
  workspace: worktree
  notifiers: [desktop, slack]

projects:
  clarvis:
    repo: GranusClarvis/clarvis
    path: ~/clarvis
    defaultBranch: main
    sessionPrefix: clarvis
    tracker:
      plugin: github    # or: linear
    reactions:
      ci-failed:
        auto: true
        action: send-to-agent
        retries: 2
      changes-requested:
        auto: true
        action: send-to-agent
        escalateAfter: 30m
      approved-and-green:
        auto: false       # manual merge
        action: notify

notifiers:
  slack:
    plugin: slack
    webhook: ${SLACK_WEBHOOK_URL}

notificationRouting:
  urgent: [desktop, slack]    # stuck, needs input, errored
  action: [desktop, slack]    # PR ready to merge
  warning: [slack]            # fix attempt failed
  info: [slack]               # summary, all done
```

---

## Conclusion

ComposioHQ's Agent Orchestrator demonstrates that **sophisticated multi-agent orchestration can be achieved with:**

- **Simple abstractions** (8 plugin interfaces)
- **Stateless design** (flat JSON, event logs)
- **Rich state machines** (20+ session statuses)
- **Two-tier reactions** (auto-handle routine, escalate edge cases)
- **Comprehensive testing** (3,288 test cases)

The architecture is particularly strong in:
1. **Plugin extensibility** — adding new agent/runtime/tracker is a 1-interface implementation
2. **Isolation guarantees** — worktree or clone-based, validated session IDs
3. **Activity detection** — native per-agent mechanism, not fragile shell parsing
4. **PR/CI lifecycle** — comprehensive SCM interface covering full pipeline
5. **Crash recovery** — persistent metadata + lock files enable safe multi-process operation

For Clarvis's agent orchestrator, adopting the **plugin architecture, session-based state machine, and two-tier reaction system** would provide a solid foundation for scaling from single-task cron jobs to a sophisticated multi-project delegation system.
