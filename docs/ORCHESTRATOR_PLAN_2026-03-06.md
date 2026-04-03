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

---

## 12. Research: claw-empire (GreenSheep01201/claw-empire)

_Deep review conducted 2026-03-06. Repo is a full AI agent office simulator built on OpenClaw._

### 12.1 Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    claw-empire Architecture                       │
│                                                                  │
│  ┌─────────────────┐     REST + WS      ┌─────────────────────┐ │
│  │  React 19 SPA   │◄──────────────────►│  Express 5 Server   │ │
│  │                  │    (port 8790)      │  (single process)   │ │
│  │  PixiJS 8 canvas│                     │                     │ │
│  │  (pixel-art     │   14 WS event types │  SQLite (27 tables) │ │
│  │   office view)  │   + HTTP polling    │  node:sqlite built-in│ │
│  │                  │                     │                     │ │
│  │  React state    │                     │  In-memory Maps for  │ │
│  │  (30+ useState) │                     │  orchestration state │ │
│  └─────────────────┘                     └────────┬────────────┘ │
│                                                   │              │
│                              ┌────────────────────┼──────┐       │
│                              ▼                    ▼      ▼       │
│                   ┌──────────────┐  ┌──────────┐  ┌──────────┐  │
│                   │ CLI Agents   │  │ HTTP     │  │ API      │  │
│                   │ claude,codex │  │ Agents   │  │ Agents   │  │
│                   │ gemini,      │  │ copilot, │  │ openai,  │  │
│                   │ opencode     │  │ antigrav │  │ ollama,  │  │
│                   └──────┬───────┘  └──────────┘  │ etc.     │  │
│                          │                         └──────────┘  │
│                   ┌──────▼───────┐                               │
│                   │ Git Worktree │  (.climpire-worktrees/<id>)   │
│                   │ per task     │  Branch: climpire/<task_id>   │
│                   └──────────────┘                               │
└──────────────────────────────────────────────────────────────────┘
```

**Tech stack**: React 19 + Vite 7 + Tailwind 4 + PixiJS 8 (frontend), Express 5 + node:sqlite + ws (backend). Node >= 22 required. ~660 files, modular route structure.

### 12.2 Orchestration Mechanics

#### Task State Machine
```
inbox → planned → collaborating → in_progress → review → done
  |                                    |              |
  +← (failure resets to inbox)         +→ cancelled   +→ revision_requested
                                       +→ pending (pause)
```

- **8 task states** (vs our 2: success/failure). The `collaborating` state is notable — it represents cross-department pre-work before execution begins.
- **`source_task_id`** links delegated tasks to parents, forming a tree.
- **`subtasks` table** with `target_department_id` + `delegated_task_id` bridges cross-department delegation.

#### Agent Lifecycle
- **Creation**: POST /api/agents — name, department, role (team_leader/senior/junior/intern), cli_provider (7 types), personality, workflow_pack_key
- **Configuration**: PATCH — cli_model, reasoning_level, oauth_account_id, api_provider_id
- **Spawning** — 3 provider paths:
  1. **CLI** (claude/codex/gemini/opencode): `child_process.spawn()` → stdout parsed for subtask events
  2. **HTTP** (copilot/antigravity): OAuth-authenticated HTTP calls with AbortController
  3. **API** (openai/anthropic/google/ollama/etc): Direct LLM API calls
- **Stopping**: SIGINT (pause) or SIGTERM→SIGKILL (cancel), with delegation state cleanup
- **Resuming**: `pending` → `planned`, auto-re-spawns with 450-900ms random delay
- **Destruction**: Blocked while `working`, cascades by nullifying foreign keys

#### Auto-Assignment Algorithm
Multi-layer ranking: workflow-pack department priorities → constrained agent scope → status (idle > break) → non-leader preferred → fewest tasks done → earliest created.

#### Locking / Concurrency
**Single-process Node.js — no distributed locks.** All concurrency is in-memory:
- `activeProcesses: Map<taskId, {pid, controller}>` — prevents double-spawning
- `subtaskDelegationDispatchInFlight: Set<taskId>` — prevents concurrent delegation for same task
- `plannerSubtaskRoutingInFlight: Set<taskId>` — prevents concurrent subtask re-routing
- `reviewInFlight: Set<taskId>` — prevents concurrent review processing
- Git worktrees provide code-level isolation between concurrent agents

**Key pattern**: In-flight guard sets with queued retries:
```typescript
if (subtaskDelegationDispatchInFlight.has(taskId)) {
  pendingDelegationOptionsByTask.set(taskId, opts); // queue for later
  return;
}
subtaskDelegationDispatchInFlight.add(taskId);
// ... proceed, then .delete() when done
```

#### Cross-Department Collaboration
- Sequential department batching: departments processed one at a time with 900-1600ms random delays
- Origin team priority: foreign delegation deferred until origin team finishes its subtasks
- Subtask seeding from planning meetings: creates subtasks from approved plans, then LLM re-routes to correct departments
- Video-specific ordering: `[VIDEO_FINAL_RENDER]` subtasks held until all other subtasks complete

#### Run Complete Handler
Central post-execution hub: on success → auto-complete own-dept subtasks → trigger foreign delegation → move to review → schedule review meeting → finishReview (merge worktree). On failure → reset to inbox → cleanup worktree → send failure report → continue cross-dept queues.

### 12.3 2D Dashboard Implementation

#### Rendering Stack
- **Engine**: PixiJS 8 on HTML5 `<canvas>`, `antialias: false`, `scaleMode: "nearest"`, `imageRendering: "pixelated"`
- **Scene building**: Imperative PixiJS scene graph, rebuilt from scratch on every React state change
- **Layout**: Vertical zones — CEO office (110px) → hallway (32px) → department grid (3-col responsive) → hallway → break room (110px)
- **Animation**: PixiJS `app.ticker` at 60fps handles: CEO WASD movement, crown bob, working particles, CLI utilization effects (sweat/distress/collapse), sub-clone floating, wall clocks, break room ambiance, delivery arc animations
- **All furniture/rooms drawn procedurally** via PixiJS `Graphics` (rectangles, circles, fills) — no sprite sheets for environment. Only agent avatars use sprite images.

#### State Model
- **React `useState` at App root** (30+ state variables, no Redux/Zustand) — agents, tasks, departments, subAgents, meetingPresence, crossDeptDeliveries, etc.
- **Agent visual states**: idle (static), working (sparkle particles), break (in break room with coffee), offline (translucent gray + zzz)
- **CLI utilization overlays**: <60% normal, 60-79% sweat drops, 80-99% red tint + sweat, 100% rotated in bed with blanket
- **Scene rebuild trigger**: any change to agents/tasks/subAgents/language/theme → full scene rebuild

#### Transport
- **WebSocket** (primary): 14 event types — `task_update`, `agent_status`, `cli_output`, `subtask_update`, `cross_dept_delivery`, `ceo_office_call`, `chat_stream`, `task_report`, etc.
- **Batched broadcasting**: `cli_output` batched at 250ms, `subtask_update` at 150ms. All others immediate.
- **HTTP live sync** (backup): Debounced polling via `scheduleLiveSync()` — tasks + agents + stats + decision inbox fetched together. 5s interval fallback.
- **Visibility-aware**: Pauses polling when tab hidden, resumes on focus.

#### Dashboard Data Shown
- CEO office: 4 KPI cards (Staff count, Working count, In Progress, Done/Total)
- Dashboard page (React component): HUD stats, ranking board (top 5 by XP), department performance bars, working/idle agent lists, mission log (6 recent tasks)
- Agent detail: sprite, role badge, unread indicator, CLI utilization bar

### 12.4 Steal List — 5 Concrete Adoptable Changes

#### 1. WebSocket/SSE Event Hub with Batched Broadcasting
**What claw-empire does**: `server/ws/hub.ts` — batched broadcasting with per-event-type cooldown intervals (250ms for cli_output, 150ms for subtask_update, immediate for others). Collects payloads during cooldown, flushes max 60 items per batch.

**Clarvis adoption**: Our `ORCH_VISUAL_DASHBOARD_2` task needs exactly this pattern. Instead of polling files, build an SSE event hub that batches high-frequency events (task progress) and sends critical events (task_complete, agent_status) immediately.

**File targets**:
- `scripts/dashboard_events.py` — new, SSE event hub with batched broadcasting
- `scripts/project_agent.py` — emit events to hub on spawn/complete/promote
- `scripts/heartbeat_postflight.py` — emit events on task completion

#### 2. Auto-Commit Safety Whitelist for Worktree Merges
**What claw-empire does**: `server/modules/workflow/core/worktree/shared.ts` — before merging a worktree, auto-commits with a safety filter:
- Extension whitelist: `.ts, .tsx, .js, .json, .md, .css, .py, .go...`
- Blocked pattern: `/(\.env|id_rsa|id_ed25519|.*\.(pem|key|p12|pfx|sqlite|db|log|zip|tar|gz))$/`
- Tracked changes always staged; untracked only if whitelisted + not blocked

**Clarvis adoption**: Our project agents don't currently have merge safety. When agents commit, they could accidentally stage secrets or binaries.

**File targets**:
- `scripts/project_agent.py` (`cmd_spawn()`) — add auto-commit safety filter before `git add/commit`
- Add `SAFE_EXTENSIONS` and `BLOCKED_PATTERNS` constants

#### 3. Stale Process Detection + Cleanup Before Re-Spawn
**What claw-empire does**: Before re-running a task, checks if a stale process exists from a previous run:
```typescript
const existing = activeProcesses.get(taskId);
if (existing) {
  if (isPidAlive(existing.pid)) return 409; // still running
  activeProcesses.delete(taskId);  // stale — clean up
}
```

**Clarvis adoption**: Our global lock (`/tmp/clarvis_claude_global.lock`) doesn't detect stale locks from crashed processes reliably. The lockfile has PID-based detection but no cross-referencing with actual process state.

**File targets**:
- `scripts/project_agent.py` — add `_check_stale_lock(agent_name)` that reads PID from lockfile, checks `/proc/<pid>/cmdline`, auto-cleans if stale
- `scripts/cron_env.sh` — harden `_acquire_lock()` with `/proc` liveness check

#### 4. Sequential Delegation with Randomized Delays
**What claw-empire does**: Cross-department subtask delegation processes one department at a time, with 900-1600ms random delays between batches. Prevents thundering herd when decomposed tasks need multiple agents. In-flight guard Set prevents concurrent delegation for same parent task.

**Clarvis adoption**: Our `project_agent.py loop` command processes subtasks serially (good), but has no delay between sessions and no guard against concurrent loop invocations on the same agent. Adding randomized backoff between sessions reduces API burst and gives cron windows to interleave.

**File targets**:
- `scripts/project_agent.py` (`run_task_loop()`) — add `time.sleep(random.uniform(10, 20))` between subtask sessions
- `scripts/project_agent.py` — add per-agent in-flight lockfile (`/tmp/clarvis_agent_<name>_loop.lock`) with stale PID detection

#### 5. Break Rotation / Lifecycle Timer for Dashboard "Aliveness"
**What claw-empire does**: Server-side timer (60s interval) randomly rotates idle agents to/from `break` status (40% return chance, 50% send-on-break chance). Creates visual dynamism without actual work happening.

**Clarvis adoption**: For the pixel-art dashboard, static agent positions will look dead. A simple lifecycle timer that varies agent visual state (idle→thinking→idle, or idle→reviewing_brain→idle) based on actual cron activity would make the dashboard feel alive.

**File targets**:
- `scripts/dashboard_events.py` — add agent state rotation timer that emits `agent_status` events
- Read actual cron status (`/tmp/clarvis_*.lock` files, recent log timestamps) to drive visual states rather than faking them

### 12.5 What NOT to Copy (and Why)

| claw-empire Pattern | Why Not for Clarvis |
|---|---|
| **Full Express+React web app** | Clarvis is Python + systemd + Telegram. A full web framework adds 660+ files, Node.js dependency, and a new process to manage. Our dashboard should be a lightweight static page + SSE/WS from a small Python server. |
| **In-memory Maps for critical state** | All orchestration state (active sessions, delegation chains, review rounds) lives in Maps/Sets — lost on server restart. We should persist to JSONL/SQLite. Our `project_agent.py` already uses file-based state (agent.json, trust.json). |
| **27-table SQLite schema** | Massively over-engineered for our use case. We have 5 agents, not 13. Our flat-file approach (agent.json + JSONL logs) is sufficient and easier to debug/backup. Only add SQLite if we hit performance limits on JSONL. |
| **Multi-round review consensus meetings** | claw-empire has planning meetings → review meetings → revision rounds → re-review. Our review loop is: human reads PR on GitHub → approves/rejects. Meeting simulation adds complexity with no value for a single-user system. |
| **Workflow packs (6 task profiles)** | Each pack has its own input schema, prompt preset, QA rules, output template, routing keywords, cost profile. We have one workflow: decompose → spawn → verify → promote. Template proliferation adds maintenance burden. |
| **i18n (4 languages in every table)** | Single user (operator), single language (English). Adding `name_ko/ja/zh` columns to everything is pure bloat. |
| **CEO WASD movement in PixiJS** | Fun but pointless for a read-only monitoring dashboard. Our CEO interacts via Telegram, not a game controller. |
| **OAuth multi-account rotation with failure tracking** | claw-empire tracks multiple OAuth accounts per provider with priority, failure counts, and auto-swap. We use a single OpenRouter API key. Unnecessary complexity. |

### 12.6 Dashboard Architecture Recommendation

Based on claw-empire analysis, here's the recommended stack for `ORCH_VISUAL_DASHBOARD`:

```
┌──────────────────────────────────────────────────────────────────┐
│                 Clarvis Visual Dashboard (Read-Only)              │
│                                                                  │
│  ┌────────────────────────┐      SSE        ┌─────────────────┐ │
│  │  Static HTML + JS      │◄───────────────│ Python SSE      │ │
│  │                        │   (EventSource) │ Server          │ │
│  │  PixiJS 8 canvas       │                 │ (Starlette)     │ │
│  │  (pixel-art rooms,     │                 │ port: 18791     │ │
│  │   agent sprites,       │   Initial load  │                 │ │
│  │   status particles)    │◄───────────────│ GET /state      │ │
│  │                        │   (full state)  │ GET /sse        │ │
│  │  No React needed —     │                 │                 │ │
│  │  vanilla JS + PixiJS   │                 │ Reads:          │ │
│  │                        │                 │ - QUEUE.md      │ │
│  └────────────────────────┘                 │ - digest.md     │ │
│                                             │ - agent configs │ │
│  Key differences from claw-empire:          │ - scoreboard    │ │
│  - SSE not WebSocket (simpler, one-way)     │ - lock files    │ │
│  - No React (read-only = no interaction)    │ - cron logs     │ │
│  - Starlette not Express (Python ecosystem) │ - gh pr list    │ │
│  - LAN-only binding (no auth needed)        └─────────────────┘ │
│  - ~200 lines Python + ~500 lines JS (vs 660 files)            │
└──────────────────────────────────────────────────────────────────┘
```

**Event types to implement** (inspired by claw-empire's 14, reduced to 6):
1. `task_started` — agent began working on a task
2. `task_completed` — task finished (success/failure)
3. `agent_status` — agent state changed (idle/working/offline)
4. `queue_update` — QUEUE.md changed (new task added/completed)
5. `cron_activity` — cron job started/finished
6. `pr_update` — PR created/merged/CI status change

**Rendering approach**: Follow claw-empire's procedural drawing (PixiJS Graphics for rooms/furniture) + sprite images for agents. But simpler: 1 room per agent (not 6 departments), no CEO movement, no meeting table, no delivery animations. Just rooms with agents showing current activity.
