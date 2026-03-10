# Research: openai/symphony — Autonomous Project Work Orchestration

_Ingested: 2026-03-09. Source: https://github.com/openai/symphony (Apache 2.0)_
_Status: Engineering Preview (prototype, not production-ready)_

## What It Is

Symphony is a long-running daemon that polls an issue tracker (Linear), creates isolated per-issue workspaces, and spawns a coding agent (Codex app-server) for each issue. Teams manage work items on their board; Symphony handles execution autonomously.

**Core thesis**: Move from supervising coding agents to managing work items. The agent is a black box — you define the work, Symphony handles scheduling, isolation, retries, and observability.

## Architecture (from SPEC.md v1)

### 6 Layers
1. **Policy Layer** (repo-defined): `WORKFLOW.md` — prompt + config in YAML front matter. Version-controlled with the code.
2. **Configuration Layer**: Typed getters over YAML front matter. Environment variable indirection (`$VAR_NAME`). Defaults for everything.
3. **Coordination Layer** (orchestrator): Poll loop → eligibility check → dispatch → retry with exponential backoff → reconciliation. In-memory state, no persistent DB required.
4. **Execution Layer**: Per-issue filesystem workspaces. Lifecycle hooks (`after_create`, `before_run`, `after_run`, `before_remove`). Git clone in `after_create`.
5. **Integration Layer**: Linear API client. Normalizes tracker data into stable `Issue` model with fields: id, identifier, title, description, priority, state, branch_name, labels, blocked_by, timestamps.
6. **Observability Layer**: Structured logs + optional Phoenix LiveView dashboard (Elixir impl) or any status surface.

### 7 Components
1. **Workflow Loader** — Reads `WORKFLOW.md`, parses YAML front matter + Liquid-template prompt body
2. **Config Layer** — Typed getters with defaults + `$VAR` env resolution
3. **Issue Tracker Client** — Fetches candidate issues, reconciles state changes
4. **Orchestrator** — Poll tick, runtime state, dispatch/retry/stop decisions
5. **Workspace Manager** — `root/<sanitized-identifier>/`, lifecycle hooks, cleanup
6. **Agent Runner** — Launches Codex app-server via `bash -lc`, streams events over stdio JSON-RPC
7. **Status Surface** — Optional dashboard (Phoenix LiveView in Elixir impl, or custom)

### Key Design Decisions
- **No persistent database** — All orchestrator state is in-memory. Restart recovery through tracker reconciliation (re-fetch active issues from Linear).
- **WORKFLOW.md as single source of truth** — Prompt template + config in one file, versioned with code. Changes apply dynamically (most settings).
- **Liquid templates** for prompts — `{{ issue.identifier }}`, `{{ issue.title }}`, `{{ attempt }}` (null on first run, integer on retry).
- **Bounded concurrency** — `max_concurrent_agents` (default 10), plus per-state limits via `max_concurrent_agents_by_state`.
- **Exponential backoff** — Failed runs retry with backoff up to `max_retry_backoff_ms` (default 5 min).
- **Terminal state cleanup** — When issue moves to Done/Closed/Cancelled, active agent is stopped and workspace cleaned.

### Codex App-Server Integration
- Launches via `codex app-server` (JSON-RPC over stdio)
- Sandbox modes: `read-only`, `workspace-write`, `danger-full-access`
- Approval policies: `untrusted`, `on-failure`, `on-request`, `never`
- Turn timeout: 1 hour default
- Stall detection: 5 min default (disable with <= 0)
- Agent-side Linear GraphQL tool for ticket manipulation

## Elixir Implementation Details
- **Language**: Elixir/OTP (94.9% of repo) — chosen for BEAM's process supervision and hot code reload
- **Dashboard**: Phoenix LiveView at `localhost:<port>/` with JSON API at `/api/v1/state`
- **Skills**: `commit`, `push`, `pull`, `land`, `linear` — shipped in `.codex/` directory
- **Setup**: Requires `mise` (Erlang/Elixir version manager), `mix setup && mix build`
- **Run**: `./bin/symphony ./WORKFLOW.md [--logs-root ./log] [--port 4000]`
- Safer defaults when policy fields omitted (reject sandbox approvals, workspace-write sandbox, turn-scoped write policy)

## What's Useful for Clarvis

### 1. WORKFLOW.md Pattern (HIGH value)
**Symphony**: Single `WORKFLOW.md` per repo defines prompt template + runtime config in YAML front matter.
**Clarvis analog**: Our cron orchestrators embed prompts inline in bash scripts. Moving to a `WORKFLOW.md` pattern per project agent would:
- Version prompts with the code
- Make prompt iteration independent of orchestrator changes
- Allow different workflow configs per project (timeout, model, concurrency)

**Adoption path**: Add `WORKFLOW.md` to project agent directories. `project_agent.py` reads it instead of hardcoded prompts. Low effort, high maintainability gain.

### 2. Per-Issue Workspace Isolation (ALREADY DONE)
**Symphony**: Creates `workspace_root/<sanitized-identifier>/` per issue with lifecycle hooks.
**Clarvis**: Our `project_agent.py` already does this — agents get `/opt/clarvis-agents/<name>/workspace/`. Git worktrees for branch isolation. Lifecycle via `create`/`destroy` commands.

**Status**: Already implemented. No action needed.

### 3. Reconciliation-Based Recovery (MEDIUM value)
**Symphony**: No persistent DB. On restart, re-fetches active issues from tracker and reconciles with in-memory state. Simplifies recovery.
**Clarvis**: We use file-based state (agent.json, trust.json, JSONL logs). On crash, state persists. But we could add reconciliation: after restart, verify lock files against running processes and clean stale state.

**Adoption path**: Already partially addressed by stale lock detection (claw-empire steal list). Full reconciliation pass on `cron_doctor.py` startup would be the Symphony-inspired addition.

### 4. Bounded Concurrency with Per-State Limits (LOW value now, HIGH later)
**Symphony**: `max_concurrent_agents: 10` global + `max_concurrent_agents_by_state: { "In Progress": 3 }` per-state caps.
**Clarvis**: Currently global lock (1 concurrent). When we move to parallel agents, per-state limits would prevent all agents from doing the same type of work.

**Adoption path**: Defer until parallel agent execution is implemented.

### 5. Exponential Backoff for Retries (LOW value)
**Symphony**: Failed runs retry with exponential backoff up to 5 min.
**Clarvis**: Our failures currently don't retry — they surface in episodes and the next heartbeat picks a new task. Retry logic would add complexity for marginal gain (most failures are due to task quality, not transient issues).

**Status**: Not needed now. Revisit if transient failures become a pattern.

## What Overlaps With What We Already Built

| Symphony Feature | Clarvis Equivalent | Gap |
|---|---|---|
| Workspace Manager | `project_agent.py create/destroy` | Clarvis has persistent state (agent.json); Symphony is stateless |
| Orchestrator poll loop | `cron_autonomous.sh` (12x/day) | Symphony polls Linear; Clarvis reads QUEUE.md |
| Prompt templates | Inline in cron scripts | Gap: should externalize to WORKFLOW.md files |
| Bounded concurrency | Global lock (`/tmp/clarvis_claude_global.lock`) | Gap: only 1 concurrent, no per-state limits |
| Issue tracker integration | QUEUE.md + manual curation | Gap: no automatic issue import from external tracker |
| Lifecycle hooks | heartbeat_preflight/postflight | Similar concept, different granularity |
| Status surface | `dashboard_server.py` (Starlette SSE + PixiJS) | Clarvis already has this |
| Agent subprocess management | `spawn_claude.sh` + lock files | Gap: Symphony uses JSON-RPC streaming; we use buffered stdout |

## What to Steal

1. **WORKFLOW.md-per-project pattern**: Externalize project agent prompts into versioned files. ~2 hours of work.
2. **Reconciliation on startup**: Add a `reconcile()` step to `cron_doctor.py` that verifies all lock files, cleans stale state, and re-syncs agent status. ~1 hour.
3. **Per-state concurrency limits** (future): When we move to parallel agents, add `max_by_type` config to prevent all agents doing the same work type.

## What's NOT Useful

- **Linear integration**: We don't use Linear. Our issue tracker is QUEUE.md. No value in adding a Linear client.
- **Codex app-server protocol**: We use Claude Code CLI with `--dangerously-skip-permissions`. Different execution model. No value in switching to JSON-RPC.
- **Elixir/OTP runtime**: Our stack is Python + bash + systemd. Adding Erlang/BEAM would be a massive dependency for marginal supervision gain.
- **No-database design**: Clarvis already has persistent state (ChromaDB, agent.json, JSONL). Going stateless would lose valuable context.
- **Liquid templates**: Overkill for our prompt construction. Python f-strings or Jinja2 (already available) are sufficient.

## Assessment

Symphony is well-architected for **teams using Linear + Codex** in a CI/CD-heavy workflow. Its core insight — manage work items, not agents — aligns with Clarvis's autonomous evolution model. But the implementation is tightly coupled to Linear + Codex app-server, making most of the code non-reusable.

**Net value for Clarvis**: 2 actionable ideas (WORKFLOW.md pattern, reconciliation), 1 future idea (per-state concurrency). The rest overlaps with or is inferior to our existing architecture.

**Recommendation**: Steal the WORKFLOW.md pattern for project agents. Skip the rest. Mark [OPENAI_SYMPHONY_RESEARCH] complete.
