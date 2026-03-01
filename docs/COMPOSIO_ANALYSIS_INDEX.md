# ComposioHQ Agent Orchestrator — Analysis Index

## Overview

This directory contains a comprehensive analysis of **ComposioHQ's Agent Orchestrator** — an open-source multi-agent orchestration system — and proposes applying its architecture to Clarvis's planned agent orchestration system.

**Total Documentation:** 2,767 lines across 3 documents, covering architecture, implementation, and design proposals.

---

## Document Guide

### 1. **composio_agent_orchestrator_analysis.md** (867 lines)
**Purpose:** High-level architectural analysis and key design decisions

**Contents:**
- Executive summary of the system
- Multi-agent architecture overview (8 swappable plugin slots)
- Workspace isolation mechanisms (git worktree vs. clone)
- Agent communication protocol (activity detection, message injection)
- Session lifecycle state machine (15 statuses, state transitions)
- Reaction system (auto-handle CI failures, review comments, escalations)
- SCM integration (rich PR/CI/review tracking)
- Plugin architecture deep dive (contract, registry, composition)
- Metadata storage (flat JSON files, append-only event log)
- Testing patterns (3,288 test cases)
- Web dashboard architecture (real-time updates via SSE)
- Key design decisions & lessons learned
- Applicability to Clarvis system
- Summary of principles, architecture, and testing approaches

**Read this for:** Understanding the big picture, design philosophy, and how it differs from traditional approaches.

---

### 2. **composio_technical_reference.md** (1,017 lines)
**Purpose:** Deep technical reference with complete type definitions and implementation examples

**Contents:**
- **Type definitions** (Session, SessionStatus, ActivityState, RuntimeHandle, etc.)
- **Interface specifications** (Runtime, Agent, Workspace, Tracker, SCM, Notifier)
- **Plugin interface examples** with full TypeScript code:
  - Minimal Runtime plugin (tmux)
  - Workspace plugin with isolation (git worktree)
  - Complete SCM types (PR, CI, review, merge readiness)
  - Event system (priority levels, event types)
- **Session lifecycle flow** (complete spawn → merge → archive sequence)
- **Communication patterns**:
  - Pattern 1: Direct message injection
  - Pattern 2: File-based state exchange
  - Pattern 3: Hook-based notifications
- **Error handling** (typed exceptions, validation, state machine safety)
- **Security considerations** (command injection prevention, validation, timeouts)
- **Configuration & deployment** (file layout, env vars)

**Read this for:** Understanding the concrete implementation details, type system, and how to implement plugins.

---

### 3. **clarvis_orchestrator_design.md** (883 lines)
**Purpose:** Concrete design proposal for adapting ComposioHQ's architecture to Clarvis

**Contents:**
- **Current state vs. proposed state** (monolith → orchestrator + isolated agents)
- **Core architecture for Clarvis**:
  - Session management (Python dataclasses + persistent JSON)
  - Lightweight plugin system (Python Protocols)
  - Session lifecycle state machine (implementation code)
  - Lifecycle polling loop (the core orchestrator loop)
- **Plugin implementations for Clarvis**:
  - TmuxRuntime plugin (Python version)
  - TaskRouter plugin (cost-aware M2.5 vs Opus routing)
  - CIFailureReaction handler (auto-fix failing tests)
- **Metadata storage** (JSONL format examples)
- **orchestrator.yaml configuration** (Clarvis-specific)
- **Integration with current Clarvis** (heartbeat, brain, memory)
- **Monitoring & observability** (metrics, endpoints)
- **Migration path** (5-phase rollout plan)
- **Key advantages** (comparison table)
- **File structure** for new orchestrator package
- **Example: spawning a project agent**
- **Conclusion** (why this architecture works for Clarvis)

**Read this for:** Concrete implementation guidance, migration planning, and how to apply these ideas to Clarvis.

---

## Quick Reference Tables

### Architecture Comparison

| Aspect | ComposioHQ | Clarvis Proposed |
|--------|-----------|------------------|
| **Language** | TypeScript | Python |
| **Plugin Slots** | 8 | 5-6 |
| **Workspace Isolation** | git worktree / clone | git worktree / clone |
| **Session Storage** | JSONL (flat files) | JSONL (flat files) |
| **State Machine** | 15 statuses | 15 statuses (same) |
| **Task Routing** | Not built-in | TaskRouter plugin |
| **Reactions** | CI, reviews, escalation | CI, reviews, escalation |
| **Notifications** | Desktop, Slack, webhook | Telegram, Slack, webhook |
| **Testing** | 3,288 tests (TypeScript) | Planned with pytest |

### Plugin Slots (Clarvis)

| Slot | Purpose | Example Plugin |
|------|---------|-----------------|
| **runtime** | Where agent executes | tmux, docker, process |
| **task_router** | Which model to use | openrouter_routing (M2.5 vs Opus) |
| **reaction** | Auto-handle events | ci_failure, review_feedback, stale |
| **notifier** | Push to human | telegram, slack, webhook |
| **session_store** | Persist state | jsonl_store |

### Key Interfaces (Python Protocols)

```python
class Runtime(Protocol):
    async def create(config) -> RuntimeHandle
    async def sendMessage(handle, text)
    async def getActivity(handle) -> ActivityState
    async def destroy(handle)

class TaskRouter(Protocol):
    async def route(task, project) -> (model: str, prompt: str)

class Notifier(Protocol):
    async def notify(event: OrchestratorEvent)

class Reaction(Protocol):
    async def handle(event, session) -> (handled: bool, retries: int)
```

---

## Key Concepts

### Session
**Definition:** Each spawned project agent is a "session" — a container with:
- Unique ID (e.g., "star-world-order-1")
- Status (spawning → working → pr_open → merged)
- Workspace path (isolated filesystem)
- Runtime handle (how to reach it)
- Metadata (custom fields, retry counts)

**Persistence:** Stored as JSON in `sessions.jsonl` (append-only), enabling:
- Crash recovery
- Multi-process safety (lock files)
- Debugging (view full state as JSON)

### Activity State
**Definition:** What the agent is currently doing:
- `"active"` — thinking/coding
- `"ready"` — finished its turn, waiting for input
- `"idle"` — inactive >5 minutes (potential issue)
- `"blocked"` — error or stuck
- `"exited"` — process stopped

**Detection:** Two mechanisms:
1. **Native** (preferred): Agent writes activity to file (e.g., `.claude/metadata.jsonl`)
2. **Fallback**: Parse terminal output (fragile, for backward compatibility)

### Reaction
**Definition:** Automatic response to state transitions (events):
- `ci-failed` → auto-send CI logs to agent for retry (2 retries max)
- `changes-requested` → auto-send review comments to agent (escalate after 30m)
- `approved-and-green` → notify human (manual merge by default)

**Two-tier handling:**
- **Tier 1 (auto):** Routine issues (CI retry, review response)
- **Tier 2 (escalate):** Edge cases (retry exhausted, unresolvable conflicts)

---

## Implementation Roadmap (for Clarvis)

### Phase 1: Core Orchestrator (Week 1-2)
- [ ] Create `orchestrator/core.py` (SessionManager + LifecycleManager)
- [ ] Implement `plugins/runtime/tmux.py`
- [ ] Implement `plugins/notifier/telegram.py`
- [ ] Create `metadata/sessions.jsonl` + `events.jsonl`
- [ ] Add REST API endpoints (`/orchestrator/status`, `/sessions`)

### Phase 2: Lite Brain per Agent (Week 2-3)
- [ ] Create `lite_brain.py` (5-collection ChromaDB per project)
- [ ] Deploy to star-world-order project agent
- [ ] Integrate memory promotion (→ main digest)

### Phase 3: Reactions & Task Router (Week 3-4)
- [ ] Implement `plugins/reaction/ci_failure.py` (auto-retry)
- [ ] Implement `plugins/reaction/review_feedback.py` (address comments)
- [ ] Implement `plugins/task_router/openrouter_routing.py` (cost-aware)
- [ ] Test reactions with synthetic CI failures

### Phase 4: Integration & Testing (Week 4-5)
- [ ] Integrate with existing `cron_morning.sh`, `spawn_claude.sh`
- [ ] Add pytest tests (session lifecycle, reactions, persistence)
- [ ] Monitor star-world-order real execution
- [ ] Refine reaction thresholds

### Phase 5: Scale (Week 5+)
- [ ] Deploy to multiple projects in parallel
- [ ] Add per-project customizations
- [ ] Advanced reactions (auto-merge, conflict resolution)

---

## File Locations

All files are saved in `/home/agent/.openclaw/workspace/docs/`:

```
docs/
├── COMPOSIO_ANALYSIS_INDEX.md              # This file
├── composio_agent_orchestrator_analysis.md # Architecture & design
├── composio_technical_reference.md         # Types, plugins, examples
└── clarvis_orchestrator_design.md          # Clarvis implementation proposal
```

To view:
```bash
cat /home/agent/.openclaw/workspace/docs/composio_agent_orchestrator_analysis.md | less
cat /home/agent/.openclaw/workspace/docs/composio_technical_reference.md | less
cat /home/agent/.openclaw/workspace/docs/clarvis_orchestrator_design.md | less
```

---

## Key Takeaways

### Principles
1. **Decouple concerns** — agents, runtimes, trackers are independent plugins
2. **Stateless orchestration** — flat JSON, event log, no database
3. **Rich state machines** — explicit statuses enable robust error handling
4. **Two-tier reactions** — auto-fix routine, escalate edge cases
5. **Activity-driven** — detect what agent is doing natively, not fragile parsing

### For Clarvis
1. **Session management** provides single source of truth for agent state
2. **Plugin architecture** makes adding new task routers, notifiers trivial
3. **Metadata persistence** enables crash recovery and debugging
4. **Task router plugin** achieves cost control (M2.5 vs Opus)
5. **Lite brains** keep per-project learning isolated but searchable
6. **Two-tier reactions** balance autonomy with human oversight

### What NOT to Copy
1. Don't force Python into TypeScript patterns (Clarvis uses Python correctly)
2. Don't create 8 slots if 5-6 suffice (Clarvis doesn't need all of them)
3. Don't over-engineer early (start with tmux runtime + Telegram notifier)

---

## Related Clarvis Files

- `/home/agent/.openclaw/CLAUDE.md` — Clarvis system overview
- `/home/agent/.openclaw/workspace/AGENTS.md` — Session boot, spawning rules
- `/home/agent/.openclaw/workspace/MEMORY.md` — Current long-term memory structure
- `/home/agent/.openclaw/workspace/scripts/project_agent.py` — Early agent orchestration attempt
- `/home/agent/.openclaw/workspace/scripts/lite_brain.py` — Lite ChromaDB implementation

---

## References

### ComposioHQ Agent Orchestrator
- **GitHub:** https://github.com/ComposioHQ/agent-orchestrator
- **Stars:** 2.8k (as of 2025-03-01)
- **Tests:** 3,288 test cases
- **License:** MIT

### Key Source Files (Analyzed)
- `packages/core/src/types.ts` — All interfaces (780+ lines)
- `packages/core/src/session-manager.ts` — CRUD for sessions
- `packages/core/src/lifecycle-manager.ts` — State machine + reactions
- `packages/plugins/runtime-tmux/src/index.ts` — tmux plugin example
- `CLAUDE.md` — Code conventions, architecture decisions
- `agent-orchestrator.yaml.example` — Configuration format

---

## Next Steps

1. **Review** the three documents in order:
   1. Start with `composio_agent_orchestrator_analysis.md` (big picture)
   2. Dive into `composio_technical_reference.md` (implementation details)
   3. Read `clarvis_orchestrator_design.md` (Clarvis-specific proposal)

2. **Discuss** with team:
   - Does this architecture align with Clarvis's goals?
   - Which plugin slots are essential vs. nice-to-have?
   - Phased rollout (Phase 1: core, Phase 2: lite brain, Phase 3: reactions)?

3. **Prototype** Phase 1:
   - Start with `orchestrator/core.py` + `plugins/runtime/tmux.py`
   - Test with one project agent
   - Measure impact on session recovery, crash resilience

4. **Iterate:**
   - Refine plugin interfaces based on real usage
   - Add telemetry (session duration, cost, success rate)
   - Scale to multiple projects once Phase 1 is stable

---

## Questions & Clarifications

### Q: Why JSONL instead of SQLite?
**A:** JSONL (append-only) is:
- Crash-safe (never corrupts on hard failure)
- Multi-process safe (append-only, no locking needed)
- Debuggable (view state as plain text)
- Searchable (can grep events)

SQLite is better for queries but worse for operational safety.

### Q: Why polling instead of webhooks?
**A:** Polling (every 5s) is:
- Simpler (no external webhook server needed)
- More reliable (no lost events if webhook fails)
- Controllable (can adjust poll interval based on load)

Webhooks would save API calls but add operational complexity.

### Q: What about distributed orchestration (multiple machines)?
**A:** Current design assumes single machine (localhost tmux sessions). To scale to multiple machines:
1. Add distributed runtime plugins (Docker, Kubernetes, SSH)
2. Use a message queue (Redis, RabbitMQ) for inter-process communication
3. Add distributed session lock mechanism (Redis locks vs. file locks)

This is Phase 5+ territory, not required for initial rollout.

### Q: Can we migrate existing Claude Code sessions to this system?
**A:** Yes, partially:
1. Session state can be reconstructed from session files + logs
2. But CLI-spawned agents won't emit activity metadata (need setupWorkspaceHooks)
3. Best approach: Phase in new sessions, keep old ones running until natural completion

---

## Contact & Feedback

For questions about this analysis, see:
- `/home/agent/.openclaw/workspace/AGENTS.md` — Communication protocol
- `/home/agent/.openclaw/CLAUDE.md` — Architecture guidelines

---

**Document Generated:** 2025-03-01
**Source Repository:** https://github.com/ComposioHQ/agent-orchestrator
**Target:** Clarvis multi-project agent orchestration system
