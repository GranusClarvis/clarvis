# Orchestrator Plan — 2026-03-06

_Clarvis as boss/orchestrator of specialized project agents with durable brains and multi-session execution loops._

## 0. Current State Assessment

**What works today:**
- `project_agent.py`: create/spawn/promote/benchmark/seed/destroy (1289 LOC)
- `agent_orchestrator.py`: parallel execution pool, DAG, self-healing, mailboxes (764 LOC)
- `orchestration_benchmark.py`: 5-dimension scoring (isolation, latency, PR success, retrieval, cost)
- `lite_brain.py`: 5-collection ChromaDB per agent with golden QA benchmarking
- First PR delivered: star-world-order #175, 62.5s, 100% success rate
- 5 agent directories exist (star-world-order, clarvis-db, goat, kinkly, star-arena)

**What's missing (in priority order):**
1. No multi-session loop — agents run once and die; no plan→execute→test→fix cycle
2. No task decomposition — large tasks get one shot, often timeout
3. No CI/review feedback loop — PR created but agent doesn't respond to CI failures
4. No concurrency control between cron and agents — global Claude lock serializes everything
5. No scoreboard — can't see agent performance at a glance
6. No trust system — all agents treated equally regardless of track record

---

## 1. What the Orchestrator Must Do First

**Minimum viable orchestrator (MVO)** — three capabilities before anything else:

### 1.1 Task Decomposition (before spawn)

Large tasks fail because a single Claude Code session can't do everything in 1200s. The orchestrator must decompose before delegating.

```
Input:  "Implement user authentication with OAuth"
Output: [
  {id: "t1", task: "Add NextAuth.js dependency and config file", deps: []},
  {id: "t2", task: "Create login/signup pages", deps: ["t1"]},
  {id: "t3", task: "Add API route for session handling", deps: ["t1"]},
  {id: "t4", task: "Write tests for auth flow", deps: ["t2", "t3"]},
  {id: "t5", task: "Create PR with all changes", deps: ["t4"]}
]
```

**Implementation**: Add `decompose_task()` to `project_agent.py`. Uses the agent's lite brain procedures + repo structure to break tasks into 2-5 subtasks with dependencies. Each subtask gets its own spawn with ≤1200s timeout. Subtasks share a work branch.

**Decision: who decomposes?**
- Option A: Clarvis decomposes (uses main brain + project context) — **preferred for now**
- Option B: Agent self-decomposes (first session plans, subsequent sessions execute)
- Start with A, evolve to B when agents have richer brains

### 1.2 Multi-Session Execution Loop

Instead of fire-and-forget, agents run in a loop until DONE or exhausted:

```
┌─────────────────────────────────────────────┐
│           ORCHESTRATOR LOOP                  │
│                                              │
│  1. PLAN     → decompose task into subtasks  │
│  2. EXECUTE  → spawn agent on next subtask   │
│  3. VERIFY   → check result (tests, lint,    │
│                 PR status, CI)               │
│  4. DECIDE   →                               │
│     ├─ SUCCESS → next subtask or DONE        │
│     ├─ FIXABLE → re-spawn with error context │
│     └─ STUCK   → escalate to human           │
│  5. REFLECT  → store episode, update brain   │
│                                              │
│  Exit: all subtasks DONE, or max_sessions    │
│        reached, or budget exhausted          │
└─────────────────────────────────────────────┘
```

**Exit criteria:**
- All subtasks complete with `status: "success"` → **DONE**
- Any subtask fails after `max_retries` (default: 2) → **STUCK** (escalate)
- Total sessions > `max_sessions` (default: 8 per task) → **BUDGET_EXCEEDED**
- Total cost > `budget_usd` (default: $2.00 per task) → **BUDGET_EXCEEDED**
- Wall clock > `max_wall_hours` (default: 4h) → **TIMEOUT**

**Safeguards:**
- Each session gets its own timeout (600-1800s based on subtask complexity)
- Sessions share a work branch — each picks up where the last left off
- Cost tracked via `_snapshot_cost()` before/after each session
- After 2 consecutive failures on same subtask, agent stops and reports

### 1.3 CI/Review Feedback Loop

When a PR is created, the orchestrator monitors it and re-spawns the agent if CI fails:

```
PR created → poll GitHub checks (every 60s, max 10min)
  ├─ All checks pass → mark DONE, notify human
  ├─ Check fails → extract failure logs, re-spawn agent with:
  │   "Your PR has failing CI. Fix these errors: <logs>"
  │   (max 2 CI-fix attempts)
  └─ Timeout → mark STUCK, notify human
```

**Implementation**: Add `_poll_pr_status(pr_url, timeout=600)` to project_agent.py. Uses `gh pr checks <number> --repo <repo>` to poll. On failure, extracts check run logs via `gh api` and builds retry context.

---

## 2. Agent Brain: What It Should Contain

Current lite brain has 5 collections. This is sufficient for now but needs richer content.

### 2.1 Collection Schema (keep 5, enrich content)

| Collection | Purpose | What to store | Source |
|---|---|---|---|
| `project-procedures` | Build/test/deploy recipes | Commands that work, CI config, deploy steps, env setup | Auto-extracted from successful sessions |
| `project-learnings` | Repo knowledge | Architecture decisions, gotchas, patterns, dependency notes | Agent discoveries + golden QA |
| `project-context` | Current state | Active branches, open PRs, recent changes, blockers | Updated each session start |
| `project-episodes` | Task history | Task→result pairs with timing, cost, and outcome | Auto-stored post-session |
| `project-goals` | What to achieve | Active issues, milestones, PR descriptions | Synced from GitHub issues |

### 2.2 New Data Structures (alongside brain, not inside it)

Add these as flat files in `agents/<name>/data/`:

**`ci_context.json`** — Last CI run results, common failure patterns:
```json
{
  "last_green_sha": "abc123",
  "common_failures": [
    {"pattern": "ESLint: no-unused-vars", "fix": "Remove unused import", "count": 3}
  ],
  "test_framework": "vitest",
  "build_command": "npm run build",
  "test_command": "npm run test"
}
```

**`dependency_map.json`** — Key files and their relationships (built once, updated on major changes):
```json
{
  "entry_points": ["src/app/layout.tsx", "src/app/page.tsx"],
  "config_files": ["next.config.ts", "tsconfig.json", "tailwind.config.ts"],
  "test_dirs": ["__tests__/", "src/**/*.test.ts"],
  "key_modules": {
    "auth": ["src/lib/auth.ts", "src/middleware.ts"],
    "api": ["src/app/api/*/route.ts"]
  }
}
```

**`pr_history.jsonl`** — Append-only log of all PRs:
```jsonl
{"pr": 175, "title": "ci: add test workflow", "branch": "clarvis/star-world-order/t001", "status": "merged", "ci_green": true, "review_iterations": 0, "time_to_merge_hours": 2.1, "cost_usd": 0.03, "task_id": "t001"}
```

### 2.3 Golden QA Evolution

Current golden QA is static (manually authored). Evolve it:
1. After each successful task, auto-generate 1-2 QA pairs from the task context
2. Validate new QA pairs don't duplicate existing ones (cosine < 0.85)
3. Cap at 50 QA pairs per agent (oldest expire)
4. Run `benchmark_retrieval()` weekly via cron to detect brain drift

---

## 3. Multi-Session Agent Loop (Detailed)

### 3.1 Session State Machine

```
             ┌──────────┐
             │ PLANNING  │ ← decompose_task()
             └─────┬─────┘
                   │ subtasks ready
                   ▼
             ┌──────────┐
        ┌───▶│ EXECUTING │ ← spawn next subtask
        │    └─────┬─────┘
        │          │ session complete
        │          ▼
        │    ┌──────────┐
        │    │ VERIFYING │ ← check tests, lint, CI
        │    └─────┬─────┘
        │          │
        │    ┌─────┴─────┐
        │    ▼           ▼
        │ SUCCESS     FAILURE
        │    │           │
        │    │     retries left?
        │    │     ├─ yes → build retry context
        │    │     │        ─────────┐
        │    │     └─ no → STUCK     │
        │    │                       │
        │    ▼                       │
        │ more subtasks?             │
        │ ├─ yes ────────────────────┘
        │ └─ no → DONE
        │
        └─── (retry with error context)
```

### 3.2 Loop Implementation (pseudocode)

```python
def run_task_loop(agent_name: str, task: str, config: LoopConfig) -> LoopResult:
    """Multi-session execution loop for a project agent."""

    # Phase 1: Decompose
    subtasks = decompose_task(agent_name, task)
    if len(subtasks) == 0:
        subtasks = [{"id": "t1", "task": task, "deps": []}]  # single task fallback

    results = {}
    total_cost = 0.0
    total_sessions = 0

    # Phase 2: Execute subtasks in dependency order
    for subtask in topo_sort(subtasks):
        # Wait for dependencies
        dep_results = {d: results[d] for d in subtask["deps"] if d in results}
        if any(r["status"] == "failed" for r in dep_results.values()):
            results[subtask["id"]] = {"status": "skipped", "reason": "dependency failed"}
            continue

        # Build context from dependency outputs
        context = build_subtask_context(subtask, dep_results)

        # Execute with retry
        for attempt in range(config.max_retries + 1):
            total_sessions += 1

            # Budget check
            if total_cost > config.budget_usd:
                return LoopResult(status="budget_exceeded", results=results, cost=total_cost)
            if total_sessions > config.max_sessions:
                return LoopResult(status="session_limit", results=results, cost=total_cost)

            # Spawn
            result = cmd_spawn(agent_name, subtask["task"],
                             timeout=config.subtask_timeout, context=context)
            cost = result.get("cost_usd", 0)
            total_cost += cost

            # Verify
            if result["status"] == "success":
                # Check if tests pass
                if result.get("tests_passed", True):
                    results[subtask["id"]] = result
                    break
                else:
                    # Tests failed — retry with test output
                    context = build_retry_context(result, attempt, "tests_failed")
            elif result["status"] == "partial":
                # Partial success — continue from where it left off
                context = build_retry_context(result, attempt, "partial")
            else:
                # Full failure
                if attempt == config.max_retries:
                    results[subtask["id"]] = {"status": "failed", **result}
                    return LoopResult(status="stuck", results=results, cost=total_cost,
                                   stuck_on=subtask["id"])
                context = build_retry_context(result, attempt, "failed")

            # Brief pause between retries
            time.sleep(15 * (attempt + 1))

        # Phase 3: Post-subtask reflection
        store_episode(agent_name, subtask, results[subtask["id"]])

    # Phase 4: CI verification (if PR was created)
    pr_url = find_pr_url(results)
    if pr_url:
        ci_result = poll_pr_status(pr_url, timeout=600)
        if ci_result["status"] == "failing":
            # One more attempt to fix CI
            fix_result = cmd_spawn(agent_name,
                f"Fix CI failures on PR {pr_url}: {ci_result['logs']}",
                timeout=900)
            total_cost += fix_result.get("cost_usd", 0)

    return LoopResult(status="done", results=results, cost=total_cost, pr_url=pr_url)
```

### 3.3 Checkpointing Between Sessions

Each session in the loop operates on the same work branch. Checkpointing happens via git:

1. **Before spawn**: `git fetch origin && git checkout <work-branch>` (picks up previous session's commits)
2. **After spawn**: Agent commits its changes (enforced by spawn prompt constraints)
3. **Between sessions**: Orchestrator reads the branch state to build context for next session

No external checkpoint store needed — git IS the checkpoint.

For non-code state (e.g., "I tried approach X and it didn't work"), the agent writes to its lite brain `project-episodes` collection, which persists across sessions.

---

## 4. Task Decomposition Strategy

### 4.1 Decomposition Rules

```
SIMPLE (1 subtask, ≤1200s):
  - Bug fix with clear reproduction
  - Add/update a single file
  - Configuration change
  - Documentation update

MEDIUM (2-3 subtasks, ≤2400s total):
  - Feature touching 2-5 files
  - Refactoring with tests
  - CI/CD pipeline change

COMPLEX (3-5 subtasks, ≤4800s total):
  - New feature with multiple components
  - Cross-cutting concern (auth, logging, i18n)
  - Architecture change with migration
```

### 4.2 Decomposition Prompt Template

```
Given this task for project '{agent_name}':
  {task}

Project info:
  - Repo: {repo_url}
  - Branch: {branch}
  - Tech stack: {inferred from package.json/requirements.txt}
  - Known procedures: {procedures from lite brain}
  - Recent changes: {last 5 commits}

Break this into 2-5 sequential subtasks. Each subtask must:
1. Be completable in a single Claude Code session (≤20 min)
2. End with a testable/verifiable state
3. Build on previous subtask's git commits

Output JSON array: [{"id": "t1", "task": "...", "deps": [], "complexity": "simple|medium"}]
If the task is simple enough for one session, return a single-element array.
```

### 4.3 Research Between Sessions

For tasks requiring research (new library, unfamiliar API):
1. First subtask is always **research-only**: "Explore the codebase and document: (a) relevant files, (b) patterns used, (c) dependencies. Write findings to a scratch file."
2. Research subtask output becomes context for implementation subtasks
3. No code changes in research subtask — prevents premature commits

---

## 5. Concurrency and Clash Control

### 5.1 Lock Hierarchy

```
Level 1: Global Claude Lock (/tmp/clarvis_claude_global.lock)
  └── Acquired by: cron_autonomous.sh, cron_*.sh, spawn_claude.sh
  └── Purpose: prevent concurrent Claude Code sessions (API cost, context confusion)
  └── Problem: blocks EVERYTHING — cron can't run while agent loop is active

Level 2: Repo Lock (/tmp/clarvis_agent_<name>.lock)  ← NEW
  └── Acquired by: project_agent.py spawn (per agent)
  └── Purpose: prevent concurrent spawns on same repo (branch conflicts)
  └── Allows: different agents to run in parallel (different repos)

Level 3: Branch Lock (advisory, via git)
  └── Acquired by: _sync_and_checkout_work_branch()
  └── Purpose: prevent two sessions on same branch
  └── Implementation: check if branch exists on remote with uncommitted local changes
```

### 5.2 Cron + Agent Coexistence

**Problem**: Global Claude lock means cron heartbeats and agent loops can't overlap.

**Solution**: Time-slotted execution with agent priority windows.

```
Cron Schedule (existing, unchanged):
  08:00  cron_morning.sh
  09:30  cron_report.sh
  10:00  cron_research.sh
  ...

Agent Windows (NEW — insert between cron slots):
  09:00-09:25  Agent loop slot 1 (after morning, before report)
  11:00-11:55  Agent loop slot 2 (between autonomous slots)
  14:30-14:55  Agent loop slot 3 (after implementation sprint)
  16:30-16:55  Agent loop slot 4 (after research)

Mechanism:
  - Agent loop checks cron schedule before starting a session
  - If next cron job starts within 10 minutes, defer to next window
  - Agent loop releases global lock between sessions (allows cron to interleave)
  - Cron jobs respect agent lock: if agent is mid-session, cron waits up to 5 min then skips
```

**Implementation**: Add `is_cron_window_clear(minutes_needed: int) -> bool` to project_agent.py. Reads system crontab, checks if any job is scheduled within `minutes_needed` minutes.

### 5.3 Parallel Agents (Future)

When running multiple agents simultaneously:
- Each agent gets its own repo lock (Level 2) — no conflicts between repos
- Global Claude lock is per-session, not per-loop — released between sessions
- Max concurrent Claude sessions: 1 (API constraint) — agents queue behind each other
- `agent_orchestrator.py run_parallel()` already handles this via semaphore

---

## 6. Evaluation: Non-Self-Referential Benchmarks

### 6.1 Hard Metrics (measurable, no self-reporting)

| Metric | How to measure | Target | Source |
|---|---|---|---|
| **PR Success Rate** | PRs merged / PRs created | ≥ 60% | `gh pr list --state merged` |
| **CI Green Rate** | PRs with all checks passing on first attempt | ≥ 50% | `gh pr checks` |
| **Time-to-Merge** | PR creation → merge timestamp | < 24h (for simple), < 72h (complex) | GitHub API |
| **Review Iterations** | Number of "changes requested" before approval | ≤ 2 | GitHub API |
| **Regression Rate** | PRs that introduced test failures on main after merge | < 5% | CI history on main branch |
| **Cost per PR** | OpenRouter spend from task start to PR merge | < $1.00 (simple), < $3.00 (complex) | `_snapshot_cost()` delta |
| **Decomposition Accuracy** | Subtasks that complete without retry / total subtasks | ≥ 70% | Loop result data |
| **Session Efficiency** | Useful sessions / total sessions (excluding retries that didn't help) | ≥ 80% | Loop result data |

### 6.2 Scoreboard Implementation

File: `data/orchestration_scoreboard.jsonl` (append-only)

```jsonl
{"date": "2026-03-06", "agent": "star-world-order", "tasks": 4, "prs_created": 1, "prs_merged": 1, "ci_green_first": 1, "avg_sessions_per_task": 1.0, "avg_cost_usd": 0.03, "retries": 0, "stuck": 0, "composite": 0.75}
```

CLI: `python3 scripts/orchestration_scoreboard.py [summary|agent <name>|history]`

Summary output:
```
Orchestration Scoreboard — 2026-03-06
─────────────────────────────────────────────────────
Agent              Tasks  PRs  Merged  CI✓  Cost   Score
star-world-order       4    1      1   100%  $0.12  0.75
clarvis-db             0    0      0     —   $0.00   —
─────────────────────────────────────────────────────
Total                  4    1      1   100%  $0.12
```

### 6.3 Trust Score

Per-agent trust score derived entirely from outcomes (never self-reported):

```python
TRUST_ADJUSTMENTS = {
    "pr_merged":        +0.05,   # PR successfully merged
    "ci_green_first":   +0.03,   # CI passed on first attempt
    "task_success":     +0.02,   # Task completed without retry
    "task_failed":      -0.10,   # Task failed after all retries
    "ci_broke_main":    -0.20,   # PR caused regression on main
    "scope_violation":  -0.15,   # Agent modified files outside repo
    "timeout":          -0.05,   # Session exceeded timeout
    "budget_exceeded":  -0.08,   # Task exceeded cost budget
}

TRUST_TIERS = {
    "autonomous": 0.80,    # Can run without human review
    "supervised": 0.50,    # Needs PR review before merge
    "restricted": 0.20,    # Single subtask at a time, always reviewed
    "suspended":  0.00,    # Cannot run (too many failures)
}
```

Stored in: `agents/<name>/data/trust.json`
Updated by: orchestrator loop post-task

---

## 7. Data Model Summary

### 7.1 Orchestrator State

```
data/orchestrator/
├── scoreboard.jsonl        # Per-agent daily metrics (append-only)
├── task_runs.jsonl          # Individual task loop results (append-only)
└── decompositions/          # Task decomposition plans
    └── <task_id>.json
```

### 7.2 Per-Agent State

```
agents/<name>/
├── data/
│   ├── brain/               # LiteBrain ChromaDB (5 collections) — EXISTING
│   ├── golden_qa.json       # Retrieval benchmark pairs — EXISTING
│   ├── benchmark.json       # Latest benchmark scores — EXISTING
│   ├── ci_context.json      # CI patterns and commands — NEW
│   ├── dependency_map.json  # Key file relationships — NEW
│   ├── pr_history.jsonl     # All PR outcomes — NEW
│   └── trust.json           # Trust score + adjustment log — NEW
├── configs/
│   └── agent.json           # Agent metadata — EXISTING (extend with trust, budget)
├── memory/
│   ├── summaries/           # Per-task results — EXISTING
│   ├── promoted/            # Promotion markers — EXISTING
│   └── procedures.md        # Consolidated how-tos — EXISTING
└── logs/                    # Per-session logs — EXISTING
```

### 7.3 Agent Config Extensions

Add to `agent.json`:
```json
{
  "trust_score": 0.50,
  "trust_tier": "supervised",
  "budget": {
    "max_timeout": 1800,
    "max_daily_tasks": 10,
    "max_cost_per_task_usd": 2.00,
    "max_sessions_per_task": 8
  },
  "loop_config": {
    "max_retries_per_subtask": 2,
    "max_wall_hours": 4,
    "ci_poll_timeout": 600,
    "ci_fix_attempts": 2
  },
  "ci": {
    "test_command": "npm run test",
    "build_command": "npm run build",
    "lint_command": "npm run lint"
  }
}
```

---

## 8. Rollout Plan (Incremental, Reversible)

### Phase 1: Scoreboard + Trust (1-2 sessions, no breaking changes)

**What**: Add `orchestration_scoreboard.py` and trust scoring to existing pipeline.

Tasks:
1. Create `scripts/orchestration_scoreboard.py` — reads existing `memory/summaries/` data, computes metrics, writes `data/orchestrator/scoreboard.jsonl`
2. Add `trust_score` field to `agent.json` template and existing agents
3. Add trust adjustment logic to `cmd_spawn()` post-processing in `project_agent.py`
4. CLI: `orchestration_scoreboard.py summary` for human-readable output

**Reversibility**: Pure additive — new files and fields only, no existing behavior changed.

### Phase 2: Multi-Session Loop (2-3 sessions)

**What**: Add `run_task_loop()` to `project_agent.py` as a new command.

Tasks:
1. Add `decompose_task()` function — takes task + agent context, returns subtask list
2. Add `run_task_loop()` function — implements the loop from §3.2
3. Add `poll_pr_status()` — polls GitHub checks via `gh` CLI
4. New CLI command: `project_agent.py loop <name> "<task>"` — runs multi-session loop
5. Existing `spawn` command unchanged — `loop` is opt-in

**Reversibility**: New command only. `spawn` still works for single-shot tasks.

### Phase 3: CI Feedback Loop (1-2 sessions)

**What**: After PR creation, monitor CI and re-spawn agent to fix failures.

Tasks:
1. Add `_poll_ci_checks(pr_number, repo)` — uses `gh pr checks`
2. Add `_extract_ci_failure_logs(pr_number, repo)` — uses `gh api` to get check run logs
3. Wire into `run_task_loop()` as final phase
4. Add CI context extraction: after first successful build, write `ci_context.json`

**Reversibility**: CI polling is optional — controlled by `loop_config.ci_fix_attempts` (set 0 to disable).

### Phase 4: Cron Integration (1 session)

**What**: Add agent loop scheduling to cron, with cron-coexistence logic.

Tasks:
1. Add `is_cron_window_clear()` to `project_agent.py`
2. Create `scripts/cron_agent_loop.sh` — runs pending agent tasks during clear windows
3. Add crontab entry: `*/30 * * * * cron_agent_loop.sh` (checks for pending work every 30 min)
4. Add `project_agent.py promote` to existing daily cron (cron_evening.sh or standalone)

**Reversibility**: Single crontab entry — remove to disable.

### Phase 5: Enhanced Brain + Decomposition (2-3 sessions)

**What**: Enrich agent brains with CI context, dependency maps, auto-generated golden QA.

Tasks:
1. Add `build_dependency_map()` — scans repo for key files, writes `dependency_map.json`
2. Add `build_ci_context()` — extracts test/build/lint commands from config files
3. Add auto-QA generation — after successful tasks, generate QA pairs for lite brain
4. Wire dependency map + CI context into spawn prompt as additional context

---

## 9. Architecture Diagram

```
┌───────────────────────────────────────────────────────────┐
│                     CLARVIS (Orchestrator)                  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│  │ Decomposer   │  │ Loop Engine  │  │ Scoreboard     │   │
│  │              │  │              │  │                │   │
│  │ task → [t1,  │  │ plan→exec→   │  │ metrics,       │   │
│  │  t2, t3]     │  │ verify→fix   │  │ trust scores   │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────┘   │
│         │                 │                    │            │
│         │    ┌────────────┴──────────┐         │            │
│         └───▶│   project_agent.py    │◀────────┘            │
│              │   (spawn/promote)     │                      │
│              └────────────┬──────────┘                      │
│                           │                                 │
│              ┌────────────┴──────────┐                      │
│              │  Global Claude Lock   │                      │
│              │  + Cron Coexistence   │                      │
│              └────────────┬──────────┘                      │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            │ spawn (one at a time)
                ┌───────────┴───────────┐
                ▼                       ▼
  ┌──────────────────┐    ┌──────────────────┐
  │ Agent: SWO       │    │ Agent: clarvis-db │
  │                  │    │                  │
  │ workspace/       │    │ workspace/       │
  │ data/brain/      │    │ data/brain/      │
  │ data/trust.json  │    │ data/trust.json  │
  │ data/ci_context  │    │ data/ci_context  │
  │ memory/summaries │    │ memory/summaries │
  └──────────────────┘    └──────────────────┘
         │                       │
         │ promote               │ promote
         ▼                       ▼
  ┌──────────────────────────────────────────┐
  │ Clarvis Main Brain                       │
  │ clarvis-procedures (tagged project:*)    │
  │ memory/cron/agent_*_digest.md            │
  └──────────────────────────────────────────┘
```

---

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Decomposition location | Orchestrator (Clarvis), not agent | Agents lack broad context; Clarvis has main brain + all project brains |
| Session isolation | Shared work branch, separate sessions | Git handles checkpointing; no need for external state store |
| Lock strategy | Release global lock between sessions | Allows cron to interleave; prevents starvation |
| CI monitoring | Poll via `gh` CLI, not webhooks | No server to run; webhooks need endpoint; polling is simpler |
| Trust system | Outcome-based, never self-reported | Prevents gaming; aligns incentives with results |
| Scoring | External metrics only (GH API, CI, cost API) | No self-referential benchmarks; all verifiable by third party |
| Retry strategy | Max 2 retries with exponential context enrichment | Diminishing returns after 2; context gets richer each retry |
| Where to add code | Extend `project_agent.py`, not new orchestrator module | Avoid parallel systems; build on what works |

---

## 11. Open Questions (for future iteration)

1. **Agent self-improvement**: Should agents evolve their own procedures.md? (Yes, but with trust-gated writes)
2. **Cross-agent learning**: Can agent A's procedures help agent B? (Via main brain promotion — already works)
3. **Human-in-the-loop**: At what trust level should agents auto-merge? (Never for now — always require human review)
4. **Model routing for subtasks**: Should simple subtasks use cheaper models? (Defer — all subtasks use Opus for reliability)
5. **Parallel subtask execution**: When subtasks have no deps, run in parallel? (Defer — serial is simpler and debuggable)
