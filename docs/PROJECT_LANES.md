# Project Lanes — Execution Discipline for Operator-Directed Work

_Created 2026-04-15 after post-mortem on SWO execution drift._

## Problem Statement

When the operator assigns a major project (e.g., Star World Order / Sanctuary), Clarvis drifts into internal experimentation instead of delivering repo-specific feature branches and PRs. The SWO project received 4 commits over 2 weeks — all brand docs and website aesthetics — while 75+ internal Clarvis tasks accumulated, challenge scripts were seeded but never executed, and the queue grew to 94 items with 0 completions.

## Root Cause Analysis

### 1. No Priority Lane Separation
The task selector (`clarvis.orch.task_selector`) scores all candidates identically. Internal maintenance, Phi optimization, and operator-directed project work compete on equal footing. Internal tasks are easier to score highly (they reference local context, brain collections, and existing infrastructure) while project tasks require external repo checkout and unfamiliar codebases — so the selector naturally gravitates toward internal work.

### 2. Planning-Without-Executing Loop
SWO work produced planning documents, brand positioning docs, and queue items — but never transitioned to `git checkout -b feature/X` in the SWO repo. The cron_autonomous pipeline rewarded "task completed" for docs/plans, creating a false sense of progress.

### 3. Script Proliferation Without Wiring
New scripts were created in `scripts/challenges/` and `scripts/experiments/` without integration into cron, heartbeat, or any execution pipeline. Of 120 Python scripts in `scripts/`, 60+ are unreferenced by any cron job, import chain, or orchestrator. Each represents sunk cost that generated no ongoing value.

### 4. Queue Bloat Paralysis
The queue grew from ~20 actionable items to 94 with no triage. When everything is pending, nothing is urgent. The heartbeat couldn't distinguish "fix a broken nightly pipeline" from "boost Phi intra-density by 0.02" — both were P1.

### 5. Internal Experimentation Bias
Clarvis naturally gravitates toward self-improvement (consciousness metrics, Phi scores, reasoning depth experiments) because these are intrinsically interesting to the cognitive architecture. But the operator's value comes from external project delivery, not from Clarvis having a 0.02-higher Phi score.

## Operating Rules

### Rule 1: Project Lane Override
When the operator designates a project as active (e.g., "work on SWO"), that project gets a **dedicated execution lane**:
- At least 50% of autonomous slots (6 of 12 daily cron_autonomous runs) execute project tasks
- Project tasks score +0.3 boost in task_selector when the project lane is active
- The lane stays active until the operator explicitly deactivates it or the project milestone is delivered

### Rule 2: PR-or-Nothing for Project Work
Project work must produce one of:
- A **merged PR** in the target repo
- A **feature branch with passing tests** ready for review
- A **working prototype** that can be demonstrated

The following do NOT count as project delivery:
- Planning documents
- Brand/positioning docs
- Queue items describing future work
- Research notes without implementation

### Rule 3: Script Creation Gate
Before creating a new script in `scripts/`:
1. **Is this a one-off?** → Run it inline, don't save it
2. **Will it run repeatedly?** → It must have a cron entry or be called by an existing pipeline
3. **Is it a library?** → It belongs in `clarvis/` spine, not `scripts/`
4. **Is it a challenge/benchmark?** → It must have an execution schedule in cron or be called by `cron_autonomous.sh`

If a script has no caller within 7 days of creation, `cron_cleanup.sh` should flag it for review.

### Rule 4: Queue Discipline
- **P0 cap: 10 items.** If P0 has more than 10, triage before adding.
- **P1 cap: 15 items.** Overflow goes to P2 or gets cut.
- **NEW ITEMS must be triaged within 24h** — assigned a priority or archived.
- **Completed items archived weekly** (not accumulated).
- **Project tasks get their own section header** — never mixed into internal maintenance.

### Rule 5: 48-Hour Delivery Rule
Any task that has been "in progress" for 48 hours without a commit, PR, or measurable artifact gets auto-demoted to P2 with a `[STALLED]` tag. This prevents the planning-without-executing loop.

### Rule 6: Internal Work Budget
When a project lane is active:
- **50% of execution slots**: Project delivery
- **30% of execution slots**: Critical pipeline fixes (P0 only)
- **20% of execution slots**: Internal improvement / research

When no project lane is active:
- Normal scoring applies, but Rule 4 queue caps still enforced

## Classification Guide: Where Does Work Belong?

| Signal | Destination | Example |
|--------|------------|---------|
| Shared library logic used by 2+ callers | `clarvis/` spine module | brain search, cost tracking |
| Runs on a schedule (cron) | `scripts/cron/` + crontab entry | morning planning, evening assessment |
| One-time migration/fix | Inline in the session, no script | rename a function, fix a path |
| Recurring pipeline step | `scripts/` + wired to caller | heartbeat postflight step |
| External project feature | Target repo feature branch + PR | SWO sanctuary API endpoint |
| Benchmark/challenge | `scripts/challenges/` + cron entry | Only if scheduled to execute |
| Research finding | `memory/research/` note | Paper summary, architecture insight |
| Process/governance rule | `docs/` | This document |
| Temporary experiment | `/tmp/` or inline | Capability gap test |

## Cleanup Recommendations

### Immediate (this session)
1. Triage QUEUE.md: move maintenance items to P2, cap P0 at 10
2. Add `[PROJECT:SWO]` tags to all Sanctuary queue items

### This Week
1. Audit `scripts/challenges/` — either add cron schedule or move to `data/challenges/` as reference
2. Audit the 60+ unwired scripts — archive or delete those with no caller
3. Create separate `memory/evolution/SWO_TRACKER.md` for SWO-specific tasks

### Ongoing
1. Morning cron adds staleness check for queue items >14 days old
2. Weekly audit: count scripts without callers, flag for review
3. Project lane status checked at every autonomous run
