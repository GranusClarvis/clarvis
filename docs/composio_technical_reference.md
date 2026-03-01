# ComposioHQ Agent Orchestrator — Technical Reference

## Table of Contents
1. [Type Definitions](#type-definitions)
2. [Plugin Interface Examples](#plugin-interface-examples)
3. [Session Lifecycle Flow](#session-lifecycle-flow)
4. [Communication Patterns](#communication-patterns)
5. [Error Handling](#error-handling)
6. [Security Considerations](#security-considerations)

---

## Type Definitions

### Session Type Hierarchy

```typescript
// ============ CORE SESSION ============
interface Session {
  id: SessionId;                    // "my-app-1"
  projectId: string;                // "my-app"
  status: SessionStatus;            // "working" | "pr_open" | "ci_failed" | ...
  activity: ActivityState | null;   // "active" | "ready" | "idle" | "blocked" | "exited"
  branch: string | null;            // "feat/issue-99"
  issueId: string | null;           // "123"
  workspacePath: string | null;     // "/home/user/.worktrees/my-app/my-app-1"
  runtimeHandle: RuntimeHandle | null;  // how to reach the agent
  pr: PRInfo | null;                // PR metadata once created
  agentInfo: AgentSessionInfo | null;   // agent's internal state
  createdAt: Date;
  lastActivityAt: Date;
  restoredAt?: Date;                // when last revived from crash
  metadata: Record<string, string>; // custom fields
}

// ============ SESSION STATUS ============
type SessionStatus =
  | "spawning"           // workspace + runtime being created
  | "working"            // agent running, no PR yet
  | "pr_open"            // agent created PR
  | "ci_failed"          // tests failing (auto-retry candidate)
  | "review_pending"     // awaiting human review
  | "changes_requested"  // reviewer left comments
  | "approved"           // reviewer approved
  | "mergeable"          // approved + green CI (ready to merge)
  | "merged"             // PR merged (terminal)
  | "cleanup"            // workspace cleanup in progress
  | "needs_input"        // agent asking user for permission
  | "stuck"              // agent appears deadlocked (escalate)
  | "errored"            // agent crashed or fatal error
  | "killed"             // human killed session (terminal)
  | "done"               // session completed normally (terminal)
  | "terminated";        // abruptly terminated

// ============ ACTIVITY STATES ============
type ActivityState =
  | "active"       // processing (thinking, writing code)
  | "ready"        // finished its turn, awaiting input
  | "idle"         // inactive >5 minutes (stale)
  | "waiting_input"// asking human for permission
  | "blocked"      // hit an error or stuck
  | "exited";      // process no longer running

interface ActivityDetection {
  state: ActivityState;
  timestamp?: Date;  // when activity was last observed
}
```

### Runtime & Agent Types

```typescript
// ============ RUNTIME PLUGIN ============
interface Runtime {
  readonly name: string;  // "tmux" | "docker" | "kubernetes" | "process"

  // Create isolated execution environment
  create(config: RuntimeCreateConfig): Promise<RuntimeHandle>;

  // Destroy session environment
  destroy(handle: RuntimeHandle): Promise<void>;

  // Send text to agent (prompt injection)
  sendMessage(handle: RuntimeHandle, message: string): Promise<void>;

  // Get recent terminal output
  getOutput(handle: RuntimeHandle, lines?: number): Promise<string>;

  // Check if session still alive
  isAlive(handle: RuntimeHandle): Promise<boolean>;

  // Optional: resource metrics
  getMetrics?(handle: RuntimeHandle): Promise<RuntimeMetrics>;

  // Optional: how to attach human (tmux session, container ID, URL)
  getAttachInfo?(handle: RuntimeHandle): Promise<AttachInfo>;
}

interface RuntimeHandle {
  id: string;                      // unique to runtime ("my-app-1", "container-abc123")
  runtimeName: string;             // which runtime implementation
  data: Record<string, unknown>;   // runtime-specific data (createdAt, uptime, etc.)
}

// ============ AGENT PLUGIN ============
interface Agent {
  readonly name: string;              // "claude-code" | "codex" | "aider"
  readonly processName: string;       // "claude" | "codex" | "aider"
  readonly promptDelivery?: "inline" | "post-launch";  // how to deliver initial prompt

  // Generate launch command (e.g., "claude -p 'Fix tests'")
  getLaunchCommand(config: AgentLaunchConfig): string;

  // Environment variables for agent process
  getEnvironment(config: AgentLaunchConfig): Record<string, string>;

  // Detect what agent is doing from terminal output (deprecated)
  detectActivity(terminalOutput: string): ActivityState;

  // Preferred: detect activity using agent's native mechanism
  getActivityState(
    session: Session,
    readyThresholdMs?: number  // when "ready" becomes "idle"
  ): Promise<ActivityDetection | null>;

  // Check if agent process is running
  isProcessRunning(handle: RuntimeHandle): Promise<boolean>;

  // Extract info from agent's internal data
  getSessionInfo(session: Session): Promise<AgentSessionInfo | null>;

  // Optional: resume a previous session
  getRestoreCommand?(
    session: Session,
    project: ProjectConfig
  ): Promise<string | null>;

  // Optional: post-launch setup (MCP servers, etc.)
  postLaunchSetup?(session: Session): Promise<void>;

  // Optional: set up workspace hooks for auto-metadata updates
  setupWorkspaceHooks?(
    workspacePath: string,
    config: WorkspaceHooksConfig
  ): Promise<void>;
}

interface AgentSessionInfo {
  summary: string | null;           // agent's work summary
  summaryIsFallback?: boolean;      // true if truncated, not real summary
  agentSessionId: string | null;    // for resume
  cost?: CostEstimate;              // token usage + estimate
}

interface CostEstimate {
  inputTokens: number;
  outputTokens: number;
  estimatedCostUsd: number;
}
```

### Workspace Types

```typescript
// ============ WORKSPACE PLUGIN ============
interface Workspace {
  readonly name: string;  // "worktree" | "clone"

  // Create isolated workspace for session
  create(config: WorkspaceCreateConfig): Promise<WorkspaceInfo>;

  // Destroy workspace
  destroy(workspacePath: string): Promise<void>;

  // List all workspaces for a project
  list(projectId: string): Promise<WorkspaceInfo[]>;

  // Optional: run hooks after creation (symlinks, installs)
  postCreate?(info: WorkspaceInfo, project: ProjectConfig): Promise<void>;

  // Optional: validate workspace exists
  exists?(workspacePath: string): Promise<boolean>;

  // Optional: revive a workspace (e.g., recreate worktree)
  restore?(
    config: WorkspaceCreateConfig,
    workspacePath: string
  ): Promise<WorkspaceInfo>;
}

interface WorkspaceCreateConfig {
  projectId: string;
  project: ProjectConfig;
  sessionId: SessionId;
  branch: string;
}

interface WorkspaceInfo {
  path: string;        // absolute filesystem path
  branch: string;      // git branch name
  sessionId: SessionId;
  projectId: string;
}
```

### Tracker Types

```typescript
// ============ TRACKER PLUGIN ============
interface Tracker {
  readonly name: string;  // "github" | "linear" | "jira"

  // Fetch issue details
  getIssue(
    identifier: string,
    project: ProjectConfig
  ): Promise<Issue>;

  // Check if issue is closed
  isCompleted(
    identifier: string,
    project: ProjectConfig
  ): Promise<boolean>;

  // Generate URL for issue
  issueUrl(identifier: string, project: ProjectConfig): string;

  // Extract human-readable label (e.g., "#42", "INT-1327")
  issueLabel?(url: string, project: ProjectConfig): string;

  // Generate git branch name for issue
  branchName(identifier: string, project: ProjectConfig): string;

  // Generate initial prompt for agent (includes issue context)
  generatePrompt(
    identifier: string,
    project: ProjectConfig
  ): Promise<string>;

  // Optional: list issues with filters
  listIssues?(
    filters: IssueFilters,
    project: ProjectConfig
  ): Promise<Issue[]>;

  // Optional: update issue state
  updateIssue?(
    identifier: string,
    update: IssueUpdate,
    project: ProjectConfig
  ): Promise<void>;

  // Optional: create new issue
  createIssue?(
    input: CreateIssueInput,
    project: ProjectConfig
  ): Promise<Issue>;
}

interface Issue {
  id: string;
  title: string;
  description: string;
  url: string;
  state: "open" | "in_progress" | "closed" | "cancelled";
  labels: string[];
  assignee?: string;
  priority?: number;
}
```

### SCM (Source Code Management) Types

```typescript
// ============ SCM PLUGIN ============
interface SCM {
  readonly name: string;  // "github" | "gitlab"

  // ---- PR LIFECYCLE ----
  detectPR(session: Session, project: ProjectConfig): Promise<PRInfo | null>;
  getPRState(pr: PRInfo): Promise<PRState>;
  getPRSummary?(pr: PRInfo): Promise<PRSummary>;
  mergePR(pr: PRInfo, method?: MergeMethod): Promise<void>;
  closePR(pr: PRInfo): Promise<void>;

  // ---- CI TRACKING ----
  getCIChecks(pr: PRInfo): Promise<CICheck[]>;      // individual check status
  getCISummary(pr: PRInfo): Promise<CIStatus>;      // overall status

  // ---- REVIEW TRACKING ----
  getReviews(pr: PRInfo): Promise<Review[]>;
  getReviewDecision(pr: PRInfo): Promise<ReviewDecision>;
  getPendingComments(pr: PRInfo): Promise<ReviewComment[]>;
  getAutomatedComments(pr: PRInfo): Promise<AutomatedComment[]>;

  // ---- MERGE READINESS ----
  getMergeability(pr: PRInfo): Promise<MergeReadiness>;
}

interface PRInfo {
  number: number;
  url: string;
  title: string;
  owner: string;        // "acme"
  repo: string;         // "my-app"
  branch: string;       // "feat/issue-99"
  baseBranch: string;   // "main"
  isDraft: boolean;
}

type PRState = "open" | "merged" | "closed";

interface PRSummary extends PRState {
  title: string;
  additions: number;
  deletions: number;
}

type MergeMethod = "merge" | "squash" | "rebase";

interface CICheck {
  name: string;
  status: "pending" | "running" | "passed" | "failed" | "skipped";
  url?: string;
  conclusion?: string;
  startedAt?: Date;
  completedAt?: Date;
}

type CIStatus = "pending" | "passing" | "failing" | "none";

interface Review {
  author: string;
  state: "approved" | "changes_requested" | "commented" | "dismissed" | "pending";
  body?: string;
  submittedAt: Date;
}

type ReviewDecision = "approved" | "changes_requested" | "pending" | "none";

interface ReviewComment {
  id: string;
  author: string;
  body: string;
  path?: string;
  line?: number;
  isResolved: boolean;
  createdAt: Date;
  url: string;
}

interface AutomatedComment {
  id: string;
  botName: string;
  body: string;
  path?: string;
  line?: number;
  severity: "error" | "warning" | "info";
  createdAt: Date;
  url: string;
}

interface MergeReadiness {
  mergeable: boolean;
  ciPassing: boolean;
  approved: boolean;
  noConflicts: boolean;
  blockers: string[];
}
```

### Event Types

```typescript
// ============ EVENTS ============
type EventPriority = "urgent" | "action" | "warning" | "info";

type EventType =
  // Session lifecycle
  | "session.spawned"
  | "session.working"
  | "session.exited"
  | "session.stuck"
  | "session.needs_input"
  | "session.errored"
  // PR lifecycle
  | "pr.created"
  | "pr.updated"
  | "pr.merged"
  | "pr.closed"
  // CI
  | "ci.passing"
  | "ci.failing"
  | "ci.fix_sent"
  | "ci.fix_failed"
  // Reviews
  | "review.pending"
  | "review.approved"
  | "review.changes_requested"
  | "review.comments_sent"
  // Reactions
  | "reaction.triggered"
  | "reaction.escalated"
  | "summary.all_complete";

interface OrchestratorEvent {
  id: string;
  type: EventType;
  priority: EventPriority;
  sessionId: SessionId;
  projectId: string;
  timestamp: Date;
  message: string;
  data?: Record<string, unknown>;
}
```

---

## Plugin Interface Examples

### Example 1: Minimal Runtime Plugin

```typescript
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { PluginModule, Runtime, RuntimeCreateConfig, RuntimeHandle } from "@composio/ao-core";

const execFileAsync = promisify(execFile);

export const manifest = {
  name: "process",
  slot: "runtime" as const,
  description: "Runtime: spawn child processes (local dev only)",
  version: "0.1.0",
};

export function create(): Runtime {
  const processes = new Map<string, NodeJS.Process>();

  return {
    name: "process",

    async create(config: RuntimeCreateConfig): Promise<RuntimeHandle> {
      const { spawn } = await import("node:child_process");
      const child = spawn("bash", {
        cwd: config.workspacePath,
        env: { ...process.env, ...config.environment },
        stdio: ["pipe", "pipe", "pipe"],
      });

      processes.set(config.sessionId, child);

      return {
        id: config.sessionId,
        runtimeName: "process",
        data: { pid: child.pid },
      };
    },

    async destroy(handle: RuntimeHandle): Promise<void> {
      const proc = processes.get(handle.id);
      if (proc) {
        proc.kill("SIGTERM");
        processes.delete(handle.id);
      }
    },

    async sendMessage(handle: RuntimeHandle, message: string): Promise<void> {
      const proc = processes.get(handle.id);
      if (proc && proc.stdin) {
        proc.stdin.write(`${message}\n`);
      }
    },

    async getOutput(handle: RuntimeHandle, lines: number = 100): Promise<string> {
      // In real implementation, capture stdout from child process
      return "";
    },

    async isAlive(handle: RuntimeHandle): Promise<boolean> {
      const proc = processes.get(handle.id);
      return proc ? !proc.killed : false;
    },
  };
}

export default { manifest, create } satisfies PluginModule<Runtime>;
```

### Example 2: Workspace Plugin with Isolation

```typescript
import { execFile } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import type { PluginModule, Workspace, WorkspaceCreateConfig, WorkspaceInfo } from "@composio/ao-core";

const execFileAsync = promisify(execFile);

async function git(cwd: string, ...args: string[]): Promise<string> {
  const { stdout } = await execFileAsync("git", args, { cwd });
  return stdout.trim();
}

export const manifest = {
  name: "worktree",
  slot: "workspace" as const,
  description: "Workspace: git worktrees for parallel isolation",
  version: "0.1.0",
};

export function create(): Workspace {
  const worktreeBaseDir = process.env.WORKTREE_DIR || "~/.worktrees";

  return {
    name: "worktree",

    async create(config: WorkspaceCreateConfig): Promise<WorkspaceInfo> {
      const projectDir = join(worktreeBaseDir, config.projectId);
      const worktreePath = join(projectDir, config.sessionId);

      mkdirSync(projectDir, { recursive: true });

      // Create git worktree (lightweight, shares object database)
      await git(
        config.project.path,
        "worktree", "add",
        "--track",
        "-b", config.branch,
        worktreePath,
        `origin/${config.project.defaultBranch}`
      );

      return {
        path: worktreePath,
        branch: config.branch,
        sessionId: config.sessionId,
        projectId: config.projectId,
      };
    },

    async destroy(workspacePath: string): Promise<void> {
      const parentRepo = findParentGitRepo(workspacePath);
      if (parentRepo) {
        // Remove worktree (cleanup local branch)
        await git(parentRepo, "worktree", "remove", "--force", workspacePath);
      }
      // Clean up filesystem
      if (existsSync(workspacePath)) {
        rmSync(workspacePath, { recursive: true });
      }
    },

    async list(projectId: string): Promise<WorkspaceInfo[]> {
      const projectDir = join(worktreeBaseDir, projectId);
      if (!existsSync(projectDir)) return [];

      // Scan directory for existing worktrees
      const entries = readdirSync(projectDir);
      return entries.map(sessionId => ({
        path: join(projectDir, sessionId),
        branch: sessionId,  // In reality, read from .git/HEAD
        sessionId,
        projectId,
      }));
    },

    async exists(workspacePath: string): Promise<boolean> {
      return existsSync(join(workspacePath, ".git"));
    },
  };
}

export default { manifest, create } satisfies PluginModule<Workspace>;
```

---

## Session Lifecycle Flow

### Complete Spawn → Merge → Archive Flow

```
1. SPAWN REQUEST
   ↓
   ├─ Acquire lock (prevent concurrent spawn)
   ├─ Validate project config
   ├─ Workspace.create() → creates worktree + branch
   │  ├─ git worktree add
   │  ├─ git checkout -b feat/issue-99
   │  └─ Workspace.postCreate() → run symlinks, pnpm install
   ├─ Runtime.create() → create tmux session
   │  ├─ tmux new-session -d -s my-app-1
   │  └─ load launch command into session
   ├─ Agent.getLaunchCommand() → "claude -p 'Fix tests' ..."
   ├─ Runtime.sendMessage() → send launch command to tmux
   └─ Write session metadata to disk
      ~/.agent-orchestrator/sessions/my-app-1.json
      {
        "id": "my-app-1",
        "status": "spawning",
        "branch": "feat/issue-99",
        "workspacePath": "/home/user/.worktrees/my-app/my-app-1",
        "runtimeHandle": { "id": "my-app-1", "runtimeName": "tmux", ... }
      }

2. LIFECYCLE POLLING (every 5 seconds)
   ├─ For each session:
   │  ├─ Agent.getActivityState() → detect what agent is doing
   │  │  └─ Return: { state: "active" | "ready" | "idle" | ... }
   │  ├─ If status was "spawning" and activity == "active":
   │  │  └─ Transition to "working" (emit "session.working" event)
   │  ├─ If status was "working" and SCM.detectPR() returns PRInfo:
   │  │  ├─ Transition to "pr_open" (emit "pr.created" event)
   │  │  └─ Start polling PR state
   │  ├─ If status was "pr_open":
   │  │  ├─ SCM.getCISummary() → check test status
   │  │  │  ├─ If "failing":
   │  │  │  │  └─ Transition to "ci_failed" (emit "ci.failing" event)
   │  │  │  │     Reaction: auto-send CI logs to agent for retry
   │  │  │  └─ If "passing":
   │  │  │     └─ Continue to review check
   │  │  ├─ SCM.getReviewDecision() → check reviewer feedback
   │  │  │  ├─ If "changes_requested":
   │  │  │  │  └─ Transition to "changes_requested" (emit event)
   │  │  │  │     Reaction: send comments to agent for fixes
   │  │  │  └─ If "approved":
   │  │  │     └─ Transition to "approved" (emit "review.approved")
   │  │  └─ SCM.getMergeability() → check merge readiness
   │  │     ├─ If mergeable && ci_passing && approved:
   │  │     │  └─ Transition to "mergeable" (emit "merge.ready")
   │  │     │     Reaction: notify human (auto-merge disabled by default)
   │  │     └─ If !mergeable:
   │  │        └─ Transition to "needs_input" (emit "session.needs_input")
   │  │           Escalate to human
   │  ├─ If activity == "idle" for >timeout:
   │  │  └─ Transition to "stuck" (emit "session.stuck")
   │  │     Reaction: escalate to human for investigation
   │  └─ Update lastActivityAt timestamp
   │
   └─ For each "reaction.triggered" event:
      ├─ Get reaction config for this event type
      ├─ If reaction.auto == true and retries_remaining > 0:
      │  ├─ Construct response (CI logs, review comments)
      │  ├─ Runtime.sendMessage(handle, response)
      │  └─ Decrement retries_remaining
      ├─ Else if escalateAfter exceeded OR retries exhausted:
      │  ├─ Transition to "needs_input"
      │  └─ Emit "reaction.escalated" → notify human

3. MANUAL MERGE (when "mergeable")
   ├─ Human reviews PR in dashboard
   ├─ Human clicks "Merge"
   ├─ Orchestrator calls SCM.mergePR()
   │  └─ gh pr merge --squash
   ├─ Transition to "merged" (emit "merge.completed")
   └─ Cleanup phase:
      ├─ Workspace.destroy(workspacePath)
      │  └─ git worktree remove
      ├─ Runtime.destroy(runtimeHandle)
      │  └─ tmux kill-session
      └─ Move session metadata to archive/
         ~/.agent-orchestrator/sessions/archive/my-app-1.json

4. CRASH RECOVERY
   ├─ Human clicks "Restore" on crashed session
   ├─ Check if session is restorable (not merged, not killed)
   ├─ Agent.getRestoreCommand() → "claude --attach-to session-xyz"
   ├─ Runtime.create() with restore command
   └─ Resume polling
```

---

## Communication Patterns

### Pattern 1: Direct Message Injection

```typescript
// Orchestrator wants to send feedback to agent

const message = `
CI logs from failed tests:
${ciOutput}

Please fix the failing tests and commit.
`;

await runtime.sendMessage(runtimeHandle, message);
// Tmux implementation:
//   tmux send-keys -t my-app-1 "message text" Enter
```

**Advantages:**
- Simple
- No additional protocol needed
- Agent receives in its stdin stream

**Disadvantages:**
- Message might be lost if agent isn't in interactive mode
- No way to know if message was received
- Shell parsing can truncate long messages

### Pattern 2: File-Based State Exchange

```typescript
// Agent writes to .claude/metadata.jsonl
// Orchestrator polls this file

const lines = readFileSync(
  join(workspacePath, ".claude/metadata.jsonl"),
  "utf-8"
).split("\n");

for (const line of lines) {
  if (!line) continue;
  const entry = JSON.parse(line);
  // { timestamp, isWaiting, currentTask, tokenCount, ... }
  return {
    state: entry.isWaiting ? "ready" : "active",
    timestamp: new Date(entry.timestamp)
  };
}
```

**Advantages:**
- Reliable (persistent on disk)
- Crash-safe
- Rich structured data
- No shell parsing issues

**Disadvantages:**
- Requires agent to implement file writing
- File I/O overhead (mitigated by caching)
- Needs cleanup mechanism

### Pattern 3: Hook-Based Notifications

```typescript
// Agent setup: hook into git commands (Claude Code's PostToolUse)
// When agent runs "git commit", hook executes metadata update

// ~/.claude/settings.json
{
  "tools": {
    "postToolUse": [
      {
        "toolName": "bash",
        "script": "python3 /path/to/update_metadata.py --branch $(git rev-parse --abbrev-ref HEAD)"
      }
    ]
  }
}

// This script runs AFTER every git command, updating session metadata
// Orchestrator detects via file polling or inotify
```

**Advantages:**
- Automatic (no explicit calls needed)
- Triggered on important events (commits, PRs)
- Rich context (git output, branch, etc.)

**Disadvantages:**
- Requires agent support for hooks
- Hook execution errors can break agent workflow
- Tight coupling to agent's tooling

---

## Error Handling

### Plugin Error Handling Pattern

```typescript
// ❌ BAD: Errors propagate to caller
export async function getIssue(id: string, project: ProjectConfig): Promise<Issue> {
  const { stdout } = await execFile("gh", ["issue", "view", id]);
  return JSON.parse(stdout);
}

// ✅ GOOD: Typed exceptions with context
export async function getIssue(id: string, project: ProjectConfig): Promise<Issue> {
  try {
    const { stdout } = await execFile("gh", [
      "issue", "view", id,
      "--repo", project.repo,
      "--json", "number,title,body,state"
    ], { timeout: 30_000 });
    return JSON.parse(stdout);
  } catch (err: unknown) {
    if (err instanceof Error) {
      if (err.message.includes("not found")) {
        throw new IssueNotFoundError(`Issue ${id} not found in ${project.repo}`);
      }
      throw new PluginError(`Failed to fetch issue ${id}: ${err.message}`, {
        cause: err,
        projectId: project.id,
      });
    }
    throw err;
  }
}

// Core service catches and handles
export async function fetchIssue(id: string, project: ProjectConfig) {
  try {
    const issue = await tracker.getIssue(id, project);
    return issue;
  } catch (err: unknown) {
    if (isIssueNotFoundError(err)) {
      // Session can't proceed without issue context
      sessionStatus = "errored";
      await notify("Issue not found, session can't proceed");
      return;
    }
    if (isPluginError(err)) {
      // Temporary failure, retry
      sessionStatus = "needs_input";
      await notify("Failed to fetch issue, please check GitHub");
      return;
    }
    throw err;  // Unexpected error, crash
  }
}
```

### Session State Validation

```typescript
// Prevent invalid state transitions
function validateStatusTransition(from: SessionStatus, to: SessionStatus) {
  const validTransitions: Record<SessionStatus, Set<SessionStatus>> = {
    "spawning": new Set(["working", "errored", "killed"]),
    "working": new Set(["pr_open", "stuck", "errored", "killed"]),
    "pr_open": new Set(["ci_failed", "review_pending", "merged", "closed"]),
    "ci_failed": new Set(["working", "stuck", "errored"]),
    "review_pending": new Set(["changes_requested", "approved", "closed"]),
    "changes_requested": new Set(["working", "review_pending", "stuck"]),
    "approved": new Set(["mergeable", "review_pending"]),
    "mergeable": new Set(["merged", "closed"]),
    // Terminal states
    "merged": new Set([]),
    "killed": new Set([]),
    "errored": new Set([]),
    "done": new Set([]),
  };

  if (!validTransitions[from]?.has(to)) {
    throw new InvalidStatusTransitionError(
      `Cannot transition from "${from}" to "${to}"`
    );
  }
}
```

---

## Security Considerations

### 1. Command Injection Prevention

```typescript
// ❌ VULNERABLE: Shell injection via string interpolation
const branch = userInput;  // "feat/issue; rm -rf /"
await execFile("bash", ["-c", `git checkout ${branch}`]);  // DANGEROUS!

// ✅ SAFE: Argument array (no shell interpolation)
await execFile("git", ["checkout", branch]);  // branch is literal arg, no shell expansion

// ❌ ALSO VULNERABLE: JSON.stringify is not shell escaping
const escaped = JSON.stringify(branch);
await execFile("bash", ["-c", `git checkout ${escaped}`]);  // Still dangerous!

// ✅ SAFE: Use node-built-ins for escaping
import { escapeShellArg } from "node:shellwords";
const escaped = escapeShellArg(branch);
await execFile("bash", ["-c", `git checkout ${escaped}`]);
```

### 2. Session ID Validation

```typescript
// Session IDs used in filesystem paths MUST be validated
const SAFE_SESSION_ID = /^[a-zA-Z0-9_-]+$/;

function assertValidSessionId(id: string): void {
  if (!SAFE_SESSION_ID.test(id)) {
    throw new Error(`Invalid session ID "${id}": contains unsafe characters`);
  }
}

// Before creating workspace path
assertValidSessionId(config.sessionId);
const workspacePath = join(worktreeDir, config.projectId, config.sessionId);
// This prevents directory traversal: sessionId can't be "../.."
```

### 3. External Data Validation

```typescript
// Always validate data from external sources (APIs, files, stdin)
interface IssueFromAPI {
  number: number;
  title: string;
  body: string;
}

// ❌ UNSAFE: Trust API response types
const issue = JSON.parse(apiResponse);
console.log(issue.title);  // What if body is an object? What if title is missing?

// ✅ SAFE: Validate against schema
import { z } from "zod";

const IssueSchema = z.object({
  number: z.number(),
  title: z.string(),
  body: z.string(),
});

const issue = IssueSchema.parse(JSON.parse(apiResponse));
console.log(issue.title);  // TypeScript guarantees string
```

### 4. Timeout Protection

```typescript
// Always add timeouts to external commands
// Prevents: hanging processes, DoS, resource exhaustion

await execFile("gh", ["pr", "view", prNumber], {
  timeout: 30_000,      // 30 second max
  maxBuffer: 10 * 1024 * 1024,  // 10MB max output
});

// Similarly for network operations
const response = await fetch(url, {
  signal: AbortSignal.timeout(10_000),  // 10 second timeout
});
```

### 5. Workspace Isolation

```typescript
// Each session's workspace is isolated (can't escape to parent)
const projectDir = "/home/user/.worktrees/my-app";
const sessionId = "session-1";  // Validated above

// Creates: /home/user/.worktrees/my-app/session-1
const workspacePath = join(projectDir, sessionId);

// When executing commands in this workspace:
await execFile("npm", ["install"], {
  cwd: workspacePath,  // Commands confined to this dir
  env: {
    // Override PATH to prevent system-wide tools
    PATH: join(workspacePath, "node_modules/.bin"),
    HOME: workspacePath,  // Prevent ~ expansion outside workspace
  }
});
```

---

## Configuration & Deployment

### Typical Deployment Layout

```
~/.agent-orchestrator/           # data directory
├── agent-orchestrator.yaml      # config
├── sessions/
│   ├── my-app-1.json
│   ├── my-app-2.json
│   └── archive/
│       └── my-app-1.json
├── events.jsonl                 # append-only event log
└── config.yaml.checksum         # for detecting changes

~/.worktrees/                     # workspace directory
├── my-app/
│   ├── my-app-1/                # worktree for session my-app-1
│   │   ├── .git
│   │   ├── src/
│   │   └── ...
│   └── my-app-2/
└── other-project/
    └── other-1/
```

### Environment Variables

```bash
# Agent Orchestrator
export AGENT_ORCHESTRATOR_DATA_DIR="${HOME}/.agent-orchestrator"
export AGENT_ORCHESTRATOR_WORKTREE_DIR="${HOME}/.worktrees"
export AGENT_ORCHESTRATOR_PORT=3000

# Plugin configuration
export GITHUB_TOKEN="ghp_..."
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."

# Agent-specific
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

---

## Further Reading

- **TypeScript conventions**: See CLAUDE.md in the repository
- **Plugin examples**: `/packages/plugins/*/src/index.ts`
- **Test patterns**: `/packages/core/src/__tests__/*.test.ts`
- **Config example**: `agent-orchestrator.yaml.example`
