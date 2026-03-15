# Clarvis Modes & Repo Strategy

_Updated: 2026-03-15_

## Direction

Clarvis should evolve into a **main public harness repo** with a small number of clearly-scoped side repos where separation actually improves structure, reuse, or open-source value.

This is explicitly **not** a monolith-everywhere plan and **not** a fragment-everything plan.

The rule:
- keep the main Clarvis harness as the operational center
- extract side repos only when the component has a clean boundary, a reusable public value proposition, and its own testing/documentation surface

## Repo Strategy

### 1. Main repo — `clarvis`
The primary repo should remain the full harness and operator surface:
- runtime behavior
- prompts / modes
- cron orchestration
- queue / planning logic
- integration glue
- dashboards
- deployment and operational docs
- public-facing identity and progress links

This repo is the **orchestration shell** and product surface.

### 2. Side repo candidates
Extract only when the boundary is strong.

#### `clarvis-db`
Public-facing agent brain / context database.
Potential scope:
- memory collections
- retrieval API
- graph relations
- archival / pruning / belief revision
- evaluation / retrieval benchmarks
- context-delivery abstractions

This is the strongest candidate for an independent repo.

#### Other side repos (only if justified)
Possible future extractions:
- context engine / prompt-context delivery layer
- benchmark / eval toolkit (if useful outside Clarvis)
- dashboard / observability surface
- project-agent / orchestration toolkit

Do not extract prematurely.

## Public Presence

Clarvis should have a public website that presents:
- what Clarvis is
- current mode
- current focus / roadmap
- linked repos
- active research / architecture directions
- benchmarks / CLR progress
- status / changelog / recent work

Start simple:
- initial version can be hosted directly on the current machine / IP
- later move to a proper domain

The site should function as both:
- a public project page
- a live identity / progress surface

## Operating Modes

Clarvis should support **three distinct modes** with seamless switching.

### 1. GE — Glorious Evolution
Current autonomous research / queue / self-evolution mode.

Behavior:
- auto research
- auto queue filling
- autonomous evolution work
- trajectory-driven task generation
- broad self-improvement and discovery

Use when:
- user wants maximal autonomous evolution
- Clarvis is expected to push his own agenda within the user-approved direction

### 2. Architecture / Maintenance Mode
Improvement-first mode.

Behavior:
- do not add broad new features unless explicitly asked
- prioritize fixing, simplifying, refactoring, wiring, validating, benchmarking
- if queue is empty, perform infra checks, architecture scans, weak-spot identification, and small fixes
- for larger structural changes, surface recommendations to the user before self-expanding scope

Use when:
- user wants Clarvis to become cleaner, sharper, and more reliable
- the system has accumulated enough surface area that consolidation matters more than expansion

### 3. Passive / User-Directed Mode
Only work when prompted.

Behavior:
- no autonomous queue generation
- no self-initiated research bursts
- no self-surgery unless the user asks
- can still decompose a large user task into subtasks and execute autonomously until completion
- waits quietly when there is no assigned work

Use when:
- user wants full control
- safety / predictability / low-background-change is the priority

## Mode Switching Requirements

Switching modes must:
- be easy for the user
- not corrupt task state
- not silently drop ongoing work
- not degrade memory or planning quality
- preserve active task continuity while changing future task generation policy

Operationally, mode switching should alter:
- queue generation policy
- allowed autonomous behavior
- research cadence
- self-modification authority
- reporting style

But should **not** alter:
- core memory integrity
- current task execution correctness
- benchmark accounting
- historical records

## Structural Principle

For the next phase, Clarvis should optimize for:
1. cleaner architecture
2. stronger memory / retrieval quality
3. clearer repo boundaries
4. measurable value via CLR / evaluation
5. public clarity about what Clarvis is building and why

## Immediate Implications

- queue should prioritize cleanup, evaluation, wiring, and benchmark discipline
- consciousness should not remain an explicit driving goal
- AGI remains a broad direction only where it produces practical improvements
- `clarvis-db` should be treated as a likely future public extraction
- the public website should be treated as a first-class deliverable, not cosmetic garnish
