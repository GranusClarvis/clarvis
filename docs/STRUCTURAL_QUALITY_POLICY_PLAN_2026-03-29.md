# Structural Quality Policy Plan — 2026-03-29

## Problem

The current system mixed three different concerns into one bad loop:

1. **Measurement** — `clarvis/metrics/quality.py` flags files with functions >100 lines via `reasonable_function_length`.
2. **Detection** — `scripts/heartbeat_postflight.py` scans changed Python files with AST.
3. **Enforcement** — postflight auto-inserted a queue task `[DECOMPOSE_LONG_FUNCTIONS]` with a stricter **80-line** target.

That turned a weak heuristic into an autonomous refactor mandate.

## Why this is bad

A single line-count threshold is not a good structural proxy.
It fails to distinguish:
- long but coherent orchestrators
- prompt/template builders
- report renderers
- data assembly pipelines
- genuinely tangled multi-responsibility functions

This creates pressure toward helper explosion, fragmentation, and metric gaming.

## Design goals for a better policy

A scalable Clarvis policy should be:
- **Advisory-first**, not auto-remediation-first
- **Multi-signal**, not single-threshold
- **Context-sensitive** by function role
- **Human-auditable** before queue insertion
- **Stability-preserving** (don’t churn mature code for aesthetics)
- **Cheap to compute** in postflight

## Proposed replacement architecture

### Layer 1 — Structural signal (keep, but weaken)
Replace `reasonable_function_length` with a non-binary structural risk score.

Signals:
- function length buckets: >120, >180, >260
- nesting depth
- branch count (`if`/`for`/`while`/`try`)
- return sites
- local variable count
- boolean condition complexity
- exception fan-out
- helper call density (negative signal: if already modular, risk lower)

Output:
- `low`, `medium`, `high` structural risk
- no direct remediation from length alone

### Layer 2 — Role-aware exemptions / dampening
Classify functions by role before scoring urgency:
- orchestrator / pipeline
- renderer / formatter
- prompt builder
- adapter / wrapper
- parser / transformer
- algorithmic core

Examples:
- Long renderer with flat flow: lower urgency
- Long orchestration function with many phases but readable sectioning: medium urgency, review only
- Long function with mixed parsing + side effects + validation + persistence: high urgency

### Layer 3 — Review recommendation, not queue insertion
Postflight should emit one of:
- `OK`
- `REVIEW_LATER`
- `REVIEW_SOON`
- `HIGH_RISK_REFACTOR_CANDIDATE`

This goes to:
- logs
- optional dashboard/status artifact
- periodic audit report

It should **not** auto-create queue tasks.

### Layer 4 — Queue creation only from stronger evidence
A queue item should only be created when at least **2 of 4** are true:
- structural risk is high
- file has poor test coverage or repeated regressions
- same function changed repeatedly in short window
- audit/reviewer marks readability/maintainability as degraded

Even then, task wording should be:
- `Review structure of X` 
not
- `Decompose until <= N lines`

### Layer 5 — Prefer targeted refactor intent
Queue tasks should specify the real issue:
- split side effects from pure computation
- separate rendering from data assembly
- extract validation from persistence
- isolate policy/config construction from execution

Never use line count as the task objective.

## Proposed concrete changes

### Immediate
1. Keep auto-queue disabled in `heartbeat_postflight.py`
2. Remove `[DECOMPOSE_LONG_FUNCTIONS]` queue items
3. Stop generating tasks with `Target: all functions <= N lines`

### Near-term
1. Replace `reasonable_function_length` boolean with `structural_complexity_risk`
2. Add AST-based complexity sub-metrics:
   - length
   - nesting
   - branch count
   - side-effect indicators
   - mixed-responsibility hints
3. Log top offenders to a JSON artifact (report only)

### Medium-term
1. Add `scripts/structural_audit.py` or `python3 -m clarvis audit structure`
2. Output ranked candidates with rationale:
   - why it was flagged
   - suggested refactor shape
   - whether to ignore
3. Integrate with benchmark/dashboard as informational maintenance debt, not active queue pressure

## Decision policy

### When to refactor
Refactor when a function is:
- hard to test in isolation
- mixing pure logic and side effects
- repeatedly breaking
- hiding several responsibilities
- difficult to review because phase boundaries are unclear

### When to leave it alone
Leave it alone when a function is:
- long but linear
- easy to scan top-to-bottom
- effectively documenting a pipeline
- mostly rendering/formatting with clear sections
- stable and not causing bugs

## Recommended task phrasing examples

Bad:
- Decompose oversized functions to <=80 lines

Good:
- Review `render_html()` and separate template assembly from section rendering if it improves readability
- Isolate retrieval scoring from reporting in `performance_benchmark.py`
- Split state mutation from prompt construction in `heartbeat_postflight.py`

## Final principle

For Clarvis, structure policy should optimize for:
**comprehension, change safety, and testability**
—not visual neatness or arbitrary line caps.
