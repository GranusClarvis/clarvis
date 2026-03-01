# Clarvis Agent Orchestrator — Design Proposal

Based on ComposioHQ's architecture, this document proposes a multi-project agent orchestration system for Clarvis.

## Current State vs. Proposed State

### Current Architecture
```
Clarvis (Monolith)
├── scripts/ (85+ Python/Bash scripts)
├── cron/ (autonomous job scheduler)
├── data/ (shared ChromaDB brain, episodes, dreams)
├── memory/ (daily logs, evolution queue, digest)
└── packages/ (3 Python packages)

Issues:
- No workspace isolation between projects
- No formal session lifecycle
- Task queue (memory/evolution/QUEUE.md) is manual
- No structured feedback routing (CI, reviews, reactions)
- Monitoring scattered across multiple files
- Cost tracking disconnected from execution
```

### Proposed: Clarvis Orchestrator

```
Clarvis (Orchestrator Core — Python)
├── orchestrator.py              # Core lifecycle manager
│   ├── Session state machine
│   ├── Plugin registry loader
│   ├── Event emission system
│   └── Reaction executor
├── plugins/
│   ├── runtime/                 # Where agents execute
│   │   ├── tmux.py
│   │   ├── docker.py
│   │   └── process.py
│   ├── task_router/             # Which model to use
│   │   └── router.py            # Route by complexity/type
│   ├── notifier/                # How to notify human
│   │   ├── telegram.py
│   │   ├── slack.py
│   │   └── webhook.py
│   └── reaction/                # How to auto-handle events
│       └── reactions.py         # Auto-fix CI, reviews, etc.
├── metadata/
│   └── sessions.jsonl           # Persistent session state
└── config.yaml                  # Projects, reactions, plugins

Project Agents (Isolated)
├── star-world-order/
│   ├── workspace/               # Cloned repo or worktree
│   ├── data/brain/              # Lite ChromaDB (5 collections)
│   ├── memory/                  # Daily logs, learnings
│   ├── logs/
│   └── config/
├── other-project/
│   └── ...
```

---

## 1. Core Architecture

### 1.1 Session Management

Each spawned project agent is a **session** with persistent metadata:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class SessionStatus(Enum):
    SPAWNING = "spawning"        # workspace creation
    WORKING = "working"          # agent running
    PR_OPEN = "pr_open"          # PR created
    CI_FAILED = "ci_failed"      # tests failing
    REVIEW_PENDING = "review_pending"  # awaiting review
    CHANGES_REQUESTED = "changes_requested"  # reviewer feedback
    APPROVED = "approved"        # review passed
    MERGEABLE = "mergeable"      # ready to merge
    MERGED = "merged"            # completed (terminal)
    STUCK = "stuck"              # escalate to human
    ERRORED = "errored"          # fatal error (terminal)

@dataclass
class Session:
    id: str                       # "star-world-order-1"
    project_id: str              # "star-world-order"
    status: SessionStatus
    branch: str | None           # git branch
    workspace_path: str | None   # /home/agent/agents/star-world-order/workspace
    runtime_handle: dict         # how to reach agent (tmux session ID, etc.)
    created_at: datetime
    last_activity_at: datetime
    metadata: dict               # custom fields
```

### 1.2 Lightweight Plugin System

```python
from abc import ABC, abstractmethod
from typing import Protocol

# Plugin slots (Python Protocols instead of interfaces)

class Runtime(Protocol):
    """Where agents execute"""
    name: str

    async def create(self, config: RuntimeCreateConfig) -> RuntimeHandle: ...
    async def sendMessage(self, handle: RuntimeHandle, message: str) -> None: ...
    async def getActivity(self, handle: RuntimeHandle) -> ActivityState: ...
    async def destroy(self, handle: RuntimeHandle) -> None: ...

class TaskRouter(Protocol):
    """Which model to use for this task"""

    async def route(self, task: str, project: ProjectConfig) -> tuple[str, str]:
        """Returns (model_name, modified_prompt)"""
        # Complexity detection → M2.5 ($0.42/1M) vs Opus ($15/1M)

class Notifier(Protocol):
    """How to reach the human"""

    async def notify(self, event: OrchestratorEvent) -> None: ...

class Reaction(Protocol):
    """How to auto-handle feedback"""

    async def handle(self, event: OrchestratorEvent, session: Session) -> bool:
        """Returns True if handled, False if escalate"""
```

### 1.3 Session Lifecycle State Machine

```python
import json
from pathlib import Path

class SessionManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.sessions_file = data_dir / "sessions.jsonl"
        self.events_file = data_dir / "events.jsonl"

    async def spawn(self, project_id: str, task: str) -> Session:
        """Create new session"""
        session_id = f"{project_id}-{self._next_session_number(project_id)}"

        # 1. Create workspace
        workspace_path = f"/home/agent/agents/{project_id}/workspace"
        workspace = await self.runtime.create(
            RuntimeCreateConfig(
                sessionId=session_id,
                workspacePath=workspace_path,
                launchCommand=self._build_launch_command(task)
            )
        )

        # 2. Create session metadata
        session = Session(
            id=session_id,
            project_id=project_id,
            status=SessionStatus.SPAWNING,
            created_at=datetime.now(),
            runtime_handle=workspace.to_dict(),
            metadata={}
        )

        # 3. Persist to disk
        self._write_session(session)
        self._emit_event(OrchestratorEvent(
            type="session.spawned",
            sessionId=session_id,
            message=f"Session {session_id} spawned"
        ))

        return session

    def _write_session(self, session: Session) -> None:
        """Append to sessions.jsonl"""
        with open(self.sessions_file, "a") as f:
            json.dump(session.to_dict(), f)
            f.write("\n")

    def _emit_event(self, event: OrchestratorEvent) -> None:
        """Append to events.jsonl"""
        with open(self.events_file, "a") as f:
            json.dump(event.to_dict(), f)
            f.write("\n")
```

### 1.4 Lifecycle Polling Loop

```python
import asyncio
from typing import Callable

class LifecycleManager:
    def __init__(
        self,
        session_manager: SessionManager,
        plugins: dict,  # {slot: plugin_instance}
        reactions: dict,  # {event_type: reaction_handler}
    ):
        self.session_manager = session_manager
        self.plugins = plugins
        self.reactions = reactions
        self.running = False

    async def start(self, poll_interval: float = 5.0):
        """Main polling loop"""
        self.running = True
        while self.running:
            try:
                for session in self.session_manager.list_active():
                    await self._update_session(session)
            except Exception as e:
                logger.error(f"Lifecycle poll error: {e}")

            await asyncio.sleep(poll_interval)

    async def _update_session(self, session: Session) -> None:
        """Poll one session for state changes"""
        # 1. Detect agent activity
        runtime = self.plugins["runtime"]
        activity = await runtime.getActivity(session.runtime_handle)

        # 2. Handle state transitions
        old_status = session.status
        new_status = await self._infer_status(session, activity)

        if new_status != old_status:
            session.status = new_status
            session.last_activity_at = datetime.now()

            # Emit event
            event = OrchestratorEvent(
                type=self._status_to_event_type(old_status, new_status),
                sessionId=session.id,
                message=f"Status: {old_status.value} → {new_status.value}"
            )
            self.session_manager._emit_event(event)

            # 3. Execute reactions
            await self._handle_reaction(event, session)

            # 4. Persist updated session
            self.session_manager._write_session(session)

    async def _infer_status(
        self,
        session: Session,
        activity: ActivityState
    ) -> SessionStatus:
        """Determine new status based on activity and external signals"""

        # If spawning and agent is active, move to working
        if session.status == SessionStatus.SPAWNING:
            if activity == ActivityState.ACTIVE:
                return SessionStatus.WORKING
            if activity == ActivityState.BLOCKED:
                return SessionStatus.ERRORED

        # If working, check if PR was created
        if session.status == SessionStatus.WORKING:
            if await self._detect_pr(session):
                return SessionStatus.PR_OPEN

        # If PR open, check CI/review status
        if session.status == SessionStatus.PR_OPEN:
            ci_status = await self._get_ci_status(session)
            if ci_status == "failing":
                return SessionStatus.CI_FAILED

            review = await self._get_review_status(session)
            if review == "changes_requested":
                return SessionStatus.CHANGES_REQUESTED
            if review == "approved":
                return SessionStatus.APPROVED

        # If agent idle for >timeout, mark stuck
        idle_time = datetime.now() - session.last_activity_at
        if activity == ActivityState.IDLE and idle_time.total_seconds() > 300:
            return SessionStatus.STUCK

        return session.status

    async def _handle_reaction(
        self,
        event: OrchestratorEvent,
        session: Session
    ) -> None:
        """Execute automatic reactions"""
        reaction_handler = self.reactions.get(event.type)
        if not reaction_handler:
            return

        # Reaction returns (handled: bool, retry_count: int)
        handled, retries = await reaction_handler(event, session)

        if not handled and retries > 0:
            # Escalate after retry limit
            event.type = "reaction.escalated"
            notifier = self.plugins["notifier"]
            await notifier.notify(event)
```

---

## 2. Plugin Implementations

### 2.1 Runtime Plugin (tmux)

```python
import subprocess
import json
from dataclasses import dataclass
from typing import Optional

@dataclass
class RuntimeHandle:
    id: str
    runtime_name: str
    data: dict

class TmuxRuntime:
    name = "tmux"

    async def create(self, config: RuntimeCreateConfig) -> RuntimeHandle:
        """Create tmux session"""
        session_name = config.sessionId

        # Create tmux session
        subprocess.run([
            "tmux", "new-session", "-d",
            "-s", session_name,
            "-c", config.workspacePath
        ], check=True)

        # Send launch command
        if len(config.launchCommand) > 200:
            # Write to temp file and load
            tmp_file = f"/tmp/launch-{session_name}.sh"
            with open(tmp_file, "w") as f:
                f.write(config.launchCommand)
            subprocess.run([
                "tmux", "send-keys", "-t", session_name,
                f"bash {tmp_file}", "Enter"
            ], check=True)
        else:
            subprocess.run([
                "tmux", "send-keys", "-t", session_name,
                config.launchCommand, "Enter"
            ], check=True)

        return RuntimeHandle(
            id=session_name,
            runtime_name="tmux",
            data={"createdAt": time.time()}
        )

    async def sendMessage(self, handle: RuntimeHandle, message: str) -> None:
        """Send text to agent"""
        session_name = handle.id
        subprocess.run([
            "tmux", "send-keys", "-t", session_name,
            message, "Enter"
        ], check=True)

    async def getActivity(self, handle: RuntimeHandle) -> ActivityState:
        """Detect what agent is doing"""
        session_name = handle.id

        # Check if process is running
        result = subprocess.run([
            "tmux", "capture-pane", "-t", session_name, "-p"
        ], capture_output=True, text=True)

        output = result.stdout

        # Simple heuristic: detect prompt patterns
        if ">>>" in output or "?" in output or "waiting" in output.lower():
            return ActivityState.READY
        if "thinking" in output.lower() or "processing" in output.lower():
            return ActivityState.ACTIVE
        if "error" in output.lower() or "failed" in output.lower():
            return ActivityState.BLOCKED

        return ActivityState.ACTIVE

    async def destroy(self, handle: RuntimeHandle) -> None:
        """Kill session"""
        session_name = handle.id
        subprocess.run([
            "tmux", "kill-session", "-t", session_name
        ])
```

### 2.2 Task Router Plugin

```python
class TaskRouter:
    """Route tasks to optimal model by complexity"""

    def __init__(self, openrouter_api: OpenRouterAPI):
        self.openrouter = openrouter_api

    async def route(self, task: str, project: ProjectConfig) -> tuple[str, str]:
        """
        Analyze task complexity, return (model, prompt).
        Model choices:
        - "m2.5": MiniMax ($0.42/1M) — simple routing, queries
        - "glm-5": GLM-5 ($1.32/1M) — code analysis, refactoring
        - "opus": Claude Opus ($15/1M) — complex reasoning
        - "gemini": Gemini Flash ($0.80/1M) — web search, vision
        """

        # 1. Classify task complexity
        keywords = task.lower()
        complexity = "simple"  # default

        if any(w in keywords for w in ["refactor", "architecture", "design"]):
            complexity = "complex"
        elif any(w in keywords for w in ["test", "debug", "fix"]):
            complexity = "medium"
        elif any(w in keywords for w in ["image", "screenshot", "visual"]):
            return ("gemini", task)  # Use vision model

        # 2. Cost-aware routing
        model = {
            "simple": "m2.5",
            "medium": "glm-5",
            "complex": "opus"
        }[complexity]

        # 3. Optional: enhance prompt with project context
        enhanced_prompt = task
        if project.agentRulesFile:
            rules = Path(project.path) / project.agentRulesFile
            if rules.exists():
                enhanced_prompt = f"{task}\n\nRules:\n{rules.read_text()}"

        return (model, enhanced_prompt)
```

### 2.3 Reaction Handler (Auto-Fix CI)

```python
class CIFailureReaction:
    """Auto-fix when CI fails"""

    def __init__(self, runtime: Runtime, notifier: Notifier):
        self.runtime = runtime
        self.notifier = notifier
        self.max_retries = 2

    async def handle(
        self,
        event: OrchestratorEvent,
        session: Session
    ) -> tuple[bool, int]:
        """
        Returns (handled, retries_remaining)
        If handled=False, escalates to human.
        """

        # Get CI failure details
        ci_logs = await self._get_ci_logs(session)
        if not ci_logs:
            return (False, 0)  # No logs, escalate

        # Construct message for agent
        message = f"""
Your PR has failing tests. CI output:

{ci_logs}

Please fix the failing tests and commit.
"""

        # Check retry count
        retry_count = session.metadata.get("ci_retry_count", 0)
        if retry_count >= self.max_retries:
            # Escalate after retries exhausted
            return (False, retry_count)

        # Send to agent
        try:
            await self.runtime.sendMessage(session.runtime_handle, message)
            session.metadata["ci_retry_count"] = retry_count + 1
            return (True, retry_count + 1)
        except Exception as e:
            logger.error(f"Failed to send CI logs to agent: {e}")
            return (False, retry_count)

    async def _get_ci_logs(self, session: Session) -> str | None:
        """Fetch CI failure logs from GitHub"""
        # Use GitHub API to get check runs
        # Filter for failed checks
        # Concatenate failure logs
        return "..."  # Placeholder
```

---

## 3. Metadata Storage

### 3.1 Sessions JSONL Format

```jsonl
{"id":"star-world-order-1","projectId":"star-world-order","status":"spawning","branch":null,"workspacePath":"/home/agent/agents/star-world-order/workspace","runtimeHandle":{"id":"star-world-order-1","runtimeName":"tmux","data":{"createdAt":1709203200.123}},"createdAt":"2025-03-01T10:00:00Z","lastActivityAt":"2025-03-01T10:00:00Z","metadata":{}}
{"id":"star-world-order-1","projectId":"star-world-order","status":"working","branch":"feat/issue-1","workspacePath":"/home/agent/agents/star-world-order/workspace","runtimeHandle":{"id":"star-world-order-1","runtimeName":"tmux","data":{"createdAt":1709203200.123}},"createdAt":"2025-03-01T10:00:00Z","lastActivityAt":"2025-03-01T10:00:30Z","metadata":{}}
```

### 3.2 Events JSONL Format

```jsonl
{"id":"evt-1","type":"session.spawned","priority":"info","sessionId":"star-world-order-1","projectId":"star-world-order","timestamp":"2025-03-01T10:00:00Z","message":"Session spawned","data":{}}
{"id":"evt-2","type":"session.working","priority":"info","sessionId":"star-world-order-1","projectId":"star-world-order","timestamp":"2025-03-01T10:00:30Z","message":"Agent working on task","data":{}}
{"id":"evt-3","type":"pr.created","priority":"action","sessionId":"star-world-order-1","projectId":"star-world-order","timestamp":"2025-03-01T10:15:00Z","message":"PR #42 created","data":{"prNumber":42,"prUrl":"https://github.com/..."}}
{"id":"evt-4","type":"ci.failing","priority":"warning","sessionId":"star-world-order-1","projectId":"star-world-order","timestamp":"2025-03-01T10:20:00Z","message":"CI failing, auto-retrying","data":{}}
```

---

## 4. Configuration

### 4.1 orchestrator.yaml

```yaml
# Clarvis Orchestrator Configuration

port: 8000

# Data directory
dataDir: /home/agent/.openclaw/workspace/data/orchestrator

# Plugin defaults
defaults:
  runtime: tmux
  taskRouter: openrouter_routing
  notifiers: [telegram, slack]

# Projects to orchestrate
projects:
  star-world-order:
    name: "Star World Order"
    repo: owner/star-world-order
    workspacePath: /home/agent/agents/star-world-order/workspace
    workspaceBrain: /home/agent/agents/star-world-order/data/brain
    defaultBranch: dev

    # Task router config
    taskRouting:
      autoRoute: true
      costAware: true
      fallbackModel: glm-5

    # Reactions config
    reactions:
      ci-failed:
        auto: true
        maxRetries: 2
        escalateAfter: 2

      changes-requested:
        auto: true
        maxRetries: 1
        escalateAfter: 30m

      approved-and-green:
        auto: false  # Manual merge

  other-project:
    name: "Other Project"
    # ... similar config

# Notification channels
notifiers:
  telegram:
    botToken: ${CLARVIS_TELEGRAM_TOKEN}
    chatId: REDACTED_CHAT_ID

  slack:
    webhook: ${SLACK_WEBHOOK_URL}

# Notification routing by event priority
notificationRouting:
  urgent: [telegram, slack]  # stuck, needs_input, errored
  action: [telegram, slack]  # pr.created, merge.ready
  warning: [slack]           # ci.failing, changes_requested
  info: [slack]              # session updates
```

---

## 5. Integration with Current Clarvis

### 5.1 Heartbeat Integration

Current flow:
```
cron_morning.sh → spawn_claude.sh → Claude Code → heartbeat_postflight.py → memory/cron/digest.md
```

Proposed flow:
```
cron_morning.sh → orchestrator.spawn(task) → Claude Code
    ↓
orchestrator (polls every 5s) → detects state changes → emits events
    ↓
reactions (auto-handle CI, reviews) → escalate to notifier if needed
    ↓
notifier (Telegram) → digest generation
```

### 5.2 Brain Integration

Each project agent has a **lite brain** (Python):

```python
from clarvis_db import ChromaDB

class LiteBrain:
    """Lightweight agent-specific ChromaDB (5 collections)"""

    def __init__(self, workspace_path: str):
        self.db = ChromaDB(
            persist_directory=f"{workspace_path}/data/brain",
            collections=[
                "project-learnings",  # lessons learned
                "project-procedures",  # tested workflows
                "project-context",    # project-specific facts
                "project-episodes",   # past sessions
                "project-goals",      # current goals
            ]
        )

    async def remember(self, text: str, importance: float = 0.7):
        """Store insight"""
        await self.db.add(
            collection="project-learnings",
            documents=[text],
            metadata=[{"importance": importance}]
        )

    async def search(self, query: str) -> list[str]:
        """Find relevant memories"""
        results = await self.db.query(
            collection="project-context",
            query_texts=[query],
            n_results=5
        )
        return results["documents"][0]
```

### 5.3 Memory Integration

Agent's daily memory lives in `agents/<name>/memory/`:

```
agents/star-world-order/memory/
├── 2025-03-01.md        # Daily log
├── 2025-03-02.md
└── sessions/            # Session records
    ├── star-world-order-1.md
    └── star-world-order-2.md
```

Orchestrator promotion:
```python
async def promote_agent_memory():
    """Sync agent memory to Clarvis main memory"""
    for project in config.projects:
        agent_memory = f"/home/agent/agents/{project.id}/memory"

        # Read latest session summaries
        sessions = list(Path(agent_memory).glob("sessions/*.md"))

        # Extract key learnings
        summaries = [extract_summary(s) for s in sessions]

        # Write to main digest
        main_digest = Path(workspace_path) / "memory/cron" / f"agent_{project.id}_digest.md"
        main_digest.write_text(format_digest(summaries))
```

---

## 6. Monitoring & Observability

### 6.1 Metrics

```python
from dataclasses import dataclass

@dataclass
class PerformanceMetrics:
    # Orchestrator health
    active_sessions: int
    pending_reactions: int
    event_queue_depth: int
    last_poll_duration_ms: float

    # Agent performance (per session)
    session_duration_hours: float
    tokens_used: int
    cost_usd: float
    ci_retry_count: int

    # System health
    disk_usage_mb: float
    db_query_time_ms: float
    event_log_size_mb: float
```

### 6.2 Observability Endpoints

```python
@app.get("/orchestrator/status")
async def status():
    """Current orchestrator state"""
    return {
        "activeSessions": len(session_manager.list_active()),
        "events": {
            "last24h": count_events(since=24h),
            "queuedReactions": count_pending_reactions(),
        },
        "plugins": {
            "runtime": runtime.name,
            "notifier": notifier.name,
            "taskRouter": task_router.name,
        },
    }

@app.get("/sessions")
async def list_sessions():
    """All sessions with status"""
    return [s.to_dict() for s in session_manager.list_all()]

@app.get("/events")
async def list_events(since: str = None, session_id: str = None):
    """Events, optionally filtered"""
    events = session_manager.read_events(since=since)
    if session_id:
        events = [e for e in events if e["sessionId"] == session_id]
    return events
```

---

## 7. Migration Path

### Phase 1: Establish Orchestrator Core (Week 1-2)
- Create `orchestrator.py` (session manager + lifecycle manager)
- Implement `plugins/runtime/tmux.py`
- Implement `plugins/notifier/telegram.py`
- Create `metadata/sessions.jsonl` + `events.jsonl`
- Add `/orchestrator/status` endpoint

### Phase 2: Lite Brain for Agents (Week 2-3)
- Create `lite_brain.py` (5-collection ChromaDB)
- Deploy to first project agent (star-world-order)
- Sync agent memory to main digest

### Phase 3: Reactions & Task Router (Week 3-4)
- Implement `plugins/reaction/*.py` (CI auto-fix, review handling)
- Implement `plugins/taskRouter/openrouter_routing.py`
- Test reaction pipeline with synthetic CI failures

### Phase 4: Integration & Testing (Week 4-5)
- Integrate with existing cron jobs
- Add comprehensive tests (session lifecycle, reactions, persistence)
- Monitor real project execution (star-world-order)
- Refine reaction thresholds based on real data

### Phase 5: Scale to Multiple Projects (Week 5+)
- Deploy orchestrator to manage N projects in parallel
- Add project-specific customizations
- Advanced reactions (merge readiness, auto-merge)

---

## 8. Key Advantages Over Current System

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Workspace Isolation** | Projects share scripts/, brain/ | Each agent isolated `/home/agent/agents/<name>/` |
| **Task Tracking** | QUEUE.md (manual) | Session state machine (automatic) |
| **State Visibility** | Scattered across files | Centralized `sessions.jsonl` + `events.jsonl` |
| **Feedback Routing** | Manual (read digest) | Automatic reactions (CI, reviews) |
| **Cost Control** | Post-hoc tracking | Real-time task routing (M2.5 vs Opus) |
| **Crash Recovery** | Restart heartbeat | Resume from last session state |
| **Notifications** | Digest only | Event-driven (urgent, action, warning, info) |
| **Testing** | Implicit | Explicit lifecycle tests |
| **Scaling** | Hard (scripts tightly coupled) | Easy (plugin architecture) |

---

## 9. File Structure

```
/home/agent/.openclaw/workspace/
├── orchestrator/
│   ├── __init__.py
│   ├── core.py                 # SessionManager + LifecycleManager
│   ├── config.py               # Load & validate orchestrator.yaml
│   ├── plugins/
│   │   ├── runtime/
│   │   │   ├── tmux.py
│   │   │   └── docker.py       # Future
│   │   ├── task_router/
│   │   │   └── openrouter_routing.py
│   │   ├── notifier/
│   │   │   ├── telegram.py
│   │   │   └── slack.py
│   │   └── reaction/
│   │       ├── ci_failure.py
│   │       ├── review_feedback.py
│   │       └── stale_session.py
│   └── metadata/
│       ├── sessions.jsonl      # Persistent state
│       └── events.jsonl        # Audit log
├── orchestrator.yaml           # Configuration
├── api/
│   ├── orchestrator.py         # FastAPI endpoints
│   └── schemas.py              # Pydantic models
└── scripts/
    ├── start_orchestrator.sh
    └── monitor_orchestrator.sh
```

---

## 10. Example: Spawning a Project Agent

```python
# From cron_morning.sh or manual prompt
from orchestrator import SessionManager, LifecycleManager
from plugins.task_router import TaskRouter

manager = SessionManager(data_dir="/home/agent/.openclaw/workspace/data/orchestrator")
task_router = TaskRouter()

# Spawn agent for star-world-order
task = "Implement user authentication flow for Next.js 16"
model, prompt = await task_router.route(task, project="star-world-order")

session = await manager.spawn(
    project_id="star-world-order",
    task=prompt,
    model=model  # "glm-5" (cost-aware routing)
)

print(f"✓ Session {session.id} spawned on {model}")
print(f"  Workspace: {session.workspace_path}")
print(f"  Model: {model} (estimated cost: $0.XX)")

# Lifecycle manager will now:
# 1. Poll every 5s for agent activity
# 2. Detect when PR is created
# 3. Monitor CI/reviews
# 4. Auto-retry if CI fails
# 5. Escalate to human when needed
```

---

## Conclusion

ComposioHQ's **eight-slot plugin architecture** provides a proven blueprint for Clarvis's multi-project agent orchestration. By adopting:

1. **Session-based state machine** — replace QUEUE.md with explicit lifecycle
2. **Plugin architecture** — decouple runtime, task routing, notifications
3. **Persistent metadata** — flat JSON for crash recovery and debugging
4. **Two-tier reactions** — auto-fix routine issues, escalate edge cases
5. **Lite brains per agent** — isolated learnings + context per project

Clarvis can scale from 1 cron job → N parallel project agents, each managed autonomously with human oversight only when needed.
