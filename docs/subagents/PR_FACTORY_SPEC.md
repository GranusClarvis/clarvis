# Subagent PR Factory Spec (Authoritative)

_Status: FINAL — source of truth for implementation._

Operating contract for **project subagents** (LiteBrain agents). Not for Clarvis core brain.

Goal: every subagent run ships a PR for the requested task. Quality comes from deterministic artifacts + bounded refinement, not hope.

---

## 0. Operating Contract

### 0.1 Run Guarantee — Always Ship a PR

Every run ends in exactly one PR class:

- **Class A — Full completion.** Task implemented, validated, shipped.
- **Class B — Best safe progress.** Core task done, a real blocker prevented full closure. Gap documented, next step explicit.
- **Class C — Task-unblocking.** A concrete blocker prevents the task this run. Ship the smallest enabling change that unblocks **the same requested task**. Not for drive-by cleanups.

**Two-PR policy:** If the task is blocked, ship two PRs in sequence:
1. Class C — removes the blocker
2. Class A/B — implements the task (next run or same run if time permits)

The unblocking PR must be tightly linked to the original task.

**Truthfulness:** Never misrepresent completion. If shipping B or C, say so in the PR body.

#### Class C Requirements (anti-spam)

Must satisfy at least one measurable enabling outcome:
- Adds a failing regression test for the target behavior
- Fixes test/CI scaffolding so validations can run
- Adds missing hooks/instrumentation required for the main change
- Isolates pre-existing CI breakage (xfail/skip/quarantine + rationale)

PR description must include:
- `Original task:` (verbatim or linked)
- `Blocker:` (what prevented direct implementation)
- `Unblocks:` (how this PR enables the task)
- `Next PR:` (exact next step)

### 0.2 Refinement Policy — Max 2 Evidence-Triggered Loops

Each run gets:
1. **Attempt 1** — implement + verify
2. **Refinement 1** — only if a concrete issue was found (failing test, missed requirement, unnecessary scope)
3. **Refinement 2** — only if still justified by evidence

After that, ship. No fourth pass.

**Allowed triggers:** validation failed, requirement missed, self-review found a concrete edge case, diff has avoidable scope bloat, PR class can be upgraded with one more bounded pass.

**Not allowed:** vague unease, speculative perfectionism, hallucinated architecture concerns, gut feelings.

Evidence steers behavior but is never an excuse to avoid the requested task.

### 0.3 Done Definition

"Done" means:
- Requested change implemented (or explicitly blocked per B/C)
- Repo checks run
- Diff scoped to the task
- Memory updated
- PR created

If B/C: PR body includes why A was impossible, what remains, exact next step.

---

## 1. Hybrid Repo Intelligence (Subagent Brain)

Five layers, generated from the repo. Not "memories" — ground truth.

### Layer 1 — Deterministic Artifacts

Stored in agent workspace under `data/artifacts/`. Generated once, refreshed on staleness.

| Artifact | Contents |
|----------|----------|
| `project_brief.md` | What the product is, sector/domain, product intent, key constraints from repo docs, non-obvious invariants |
| `stack_detect.json` | Languages, frameworks, package managers, test/lint/typecheck/build tools |
| `commands.json` | Install/dev/build/test/lint/typecheck commands with confidence + verified flag |
| `architecture_map.md` | Entrypoints, module layout, runtime flow, key directories, hot paths |

Optional (generate when relevant):
| `trust_boundaries.md` | Untrusted inputs, entry points, validation points, auth/authz |
| `dependency_snapshot.json` | Lockfile summary, critical deps, framework versions, audit notes |

Each artifact carries: `generated_at`, `git_sha`, `generator_version`.

### Layer 2 — Precision Indexes

Stored in `data/indexes/`. Answer exact grounding questions.

| Index | Contents |
|-------|----------|
| `file_index.json` | path → type + hash + tags |
| `symbol_index.json` | symbol → file + type + exported/local |
| `route_index.json` | route/method → handler file |
| `config_env_index.json` | env/config key → consumer files |
| `test_index.json` | test files → related modules + coverage hints |

Optional: `db_index.json` (model/table → query locations/migrations)

### Layer 3 — Atomic Fact Cards (LiteBrain)

Small structured facts stored in LiteBrain collections:
- `FACT`: POST /api/governance/vote → app/api/governance/route.ts
- `INVARIANT`: votingPower must be derived server-side
- `PROCEDURE`: pnpm test --filter governance passed
- `GOTCHA`: CI lint fails on unrelated generated files

Each: type, text, source, confidence, related file tags.

### Layer 4 — Episodic Memory

Per-run summaries (blockers, flaky checks, patterns). Retrievable, lower priority than artifacts.

### Layer 5 — Sector/Product Playbook ✅

Derived from repo docs. Domain-specific constraints (trading safety, content boundaries, governance lifecycle, etc.).
Implemented: `project-sector` collection, `generate_sector_playbook()`, wired into brief + hybrid_recall + writeback.

---

## 2. Execution Brief Compiler

The prompt is compiled, not handwritten.

### 2.1 Task Classification

Classify each task: `bugfix | feature | refactor | docs | tests | config | hardening | investigation`

Affects: required evidence depth, validation plan, acceptable PR class.

### 2.2 Execution Brief Schema

Generated per run, saved as `execution_brief.json`:

```json
{
  "task_interpretation": "...",
  "task_class": "bugfix",
  "success_criteria": ["..."],
  "non_negotiables": ["..."],
  "relevant_files": ["..."],
  "artifact_excerpts": {},
  "relevant_facts": [],
  "relevant_episodes": [],
  "required_validations": ["..."],
  "fallback_strategy": "Class B if X, Class C if Y"
}
```

### 2.3 Context Tiers

- **Tier 0 (always):** task interpretation, success criteria, commands, architecture hotspots, relevant indexes, critical invariants
- **Tier 1 (if relevant):** prior procedures, similar episodes, sector constraints, known gotchas
- **Tier 2 (only when needed):** longer doc excerpts, broad roadmap, large architectural notes

---

## 3. PR Factory State Machine

### A) Context Build

| Step | Action |
|------|--------|
| 1. INTAKE_REFRESH | Generate or refresh deterministic artifacts (detect staleness by git SHA) |
| 2. INDEX_REFRESH | Update precision indexes |
| 3. RETRIEVE_CONTEXT | Pull relevant facts, episodes, sector context from LiteBrain |
| 4. TASK_CLASSIFY | Determine task category, set validation expectations |
| 5. BRIEF_COMPILE | Assemble execution brief, persist to disk |

### B) Attempt 1

| Step | Action |
|------|--------|
| 6. RECON | Identify relevant files, symbols, routes, current behavior, existing tests, likely change locations. If recon is weak, strengthen it — don't skip implementation. If truly blocked, ship Class C. |
| 7. PLAN | Intended change, expected files, validation plan, failure modes, target PR class |
| 8. IMPLEMENT | Edit code, create tests/docs if needed, keep structured change notes |
| 9. VERIFY_TECHNICAL | Run build/test/lint/typecheck. Capture pre-existing baseline failures. |
| 10. VERIFY_REQUIREMENTS | Task fulfilled? Non-negotiables preserved? Scope matches request? |
| 11. SELF_REVIEW | Did I satisfy the request? What changed? What could be wrong? Unnecessary scope? Which PR class? Need a refinement loop (evidence-based)? |

### C) Refinement Loops (max 2)

| Step | Action |
|------|--------|
| 12. REFINE_1 | Fix failing checks, missed criteria, unnecessary scope. Re-verify (9→10→11). |
| 13. REFINE_2 | Only if evidence justifies. Re-verify. Then ship. |

Before starting a loop, answer: What exact issue? What evidence? Likely to improve PR class? If not, ship.

### D) Ship

| Step | Action |
|------|--------|
| 14. PR_CLASS_DECISION | Choose A/B/C based on evidence. |
| 15. CREATE_PR | PR body includes: task, what changed, why, validations, pre-existing failures, limitations, PR class. If Class C: include task-linkage fields. |
| 16. MEMORY_WRITEBACK | Episode summary, new facts, procedure updates, golden QA (mandatory). |

---

## 4. Memory Writeback Contract (Mandatory)

### 4.1 Episode Summary (`episode_summary.json`)

Required: task, task_class, pr_class, pr_url, files_changed, validations_run, pass_fail, blockers, next_step.

### 4.2 Atomic Fact Updates

Store only: new exact truths, invariants, route/symbol relationships, grounded facts.

### 4.3 Procedure Updates

Store only commands that actually worked.

### 4.4 Golden QA Updates

Add 1–3 precision questions only if real knowledge was gained.

---

## 5. Evaluation & Staleness

### 5.1 Repo IQ Benchmark

Three tiers: architecture knowledge, operational knowledge, minute-detail grounding. Answers must cite file paths, symbols, enforcement locations.

### 5.2 Drift Detection

Mark artifacts stale when: significant file changes, new modules/routes, major dependency changes, schema changes. Refresh before next run.

---

## 6. Rollout Plan (Wrapper, Not Rewrite)

**Non-negotiable:** Build as an additive wrapper around existing `project_agent.py spawn`. Do not rewrite the orchestrator.

**Keep unchanged:** agent isolation, branch/PR creation, commit safety, A2A protocol, spawn prompt machinery, trust gates, concurrency locks, retry logic.

**Add:** deterministic intake + indexes, execution brief compiler, PR class rules in prompt, evidence-gated refinement instructions, mandatory writeback.

### Implementation Phases

1. **Phase 1 — Spec sync + prompt injection.** Inject PR class rules, two-PR policy, refinement limits, and task-linkage requirements into the spawn prompt. Add acceptance tests.
2. **Phase 2 — Deterministic intake.** Add artifact generators + precision indexes. Store in agent data dir. Wire staleness detection.
3. **Phase 3 — Brief compiler + loops.** Compile execution brief from artifacts + LiteBrain. Add recon/verify/refine instructions. Wire mandatory writeback.

Pilot on one repo first, then generalize.

---

## One-Sentence Summary

Each subagent operates as a bounded, always-shipping PR factory that uses compiled context from deterministic repo artifacts, performs evidence-gated implementation with at most two refinements, and ships the best justified PR class with mandatory memory writeback.
