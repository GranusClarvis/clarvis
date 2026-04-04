# Consolidation Plan — Repo Boundaries

> **Note (2026-04-03):** The `packages/` directory (clarvis-db, clarvis-cost, clarvis-reasoning) has been
> consolidated into the `clarvis/` spine module. References to standalone packages below are historical.
> See `clarvis/brain/`, `clarvis/orch/cost_tracker.py`, `clarvis/cognition/metacognition.py`.


_One-pager summary. Full details: [REPO_CONSOLIDATION_PLAN.md](./REPO_CONSOLIDATION_PLAN.md)_
_Status: DECIDED (2026-03-16). Updated 2026-03-28._

---

## Two Repos, No Sprawl

| Repo | URL | Contents | Status |
|------|-----|----------|--------|
| **clarvis** (main) | `GranusClarvis/clarvis` | Spine (`clarvis/`), scripts, skills, tests, docs, identity docs | Active, public-ready |
| **clarvis-db** (standalone) | `GranusClarvis/clarvis-db` | ChromaDB vector memory + Hebbian learning package | Stabilizing → extract when gates pass |

## What Stays in Main Repo

- **`clarvis/`** — spine: brain, heartbeat, cognition, context, metrics, runtime, orch, adapters, compat
- **`scripts/`** — 109 Python + 37 Bash operational scripts (cron, maintenance, cognitive architecture)
- **`packages/clarvis-cost/`** — internal cost tracking (0 external consumers, absorb into `clarvis/cost/` eventually)
- **`packages/clarvis-reasoning/`** — internal reasoning quality (0 external consumers, absorb into `clarvis/cognition/` eventually)
- **`skills/`** — 19 OpenClaw skill definitions
- **`tests/`** — consolidated test directory
- **`docs/`** — architecture, ADRs, boundary specs, website assets
- **`data/`** — runtime only, excluded from git via .gitignore

## What Moves Out

- **`packages/clarvis-db/`** → separate repo `GranusClarvis/clarvis-db`
  - **Why**: clean API boundary, independently useful, has real tests, different release cadence
  - **Extraction plan**: `docs/CLARVISDB_EXTRACTION_PLAN.md`
  - **Gates**: `docs/EXTRACTION_GATES.md`
  - Main repo adds `clarvis-db` as pip dependency post-extraction

## Explicitly Rejected as Separate Packages

| Candidate | Reason | Where it lives |
|-----------|--------|----------------|
| clarvis-p (context) | No external consumer, just re-exports | `clarvis/context/` |
| clarvis-cost | 5 internal callers, 0 external | `packages/clarvis-cost/` → `clarvis/cost/` |
| clarvis-reasoning | 3 internal callers, 0 external | `packages/clarvis-reasoning/` → `clarvis/cognition/` |

## Anti-Sprawl Rule

New repos require ALL of: (1) 2+ real consumers, (2) clean API boundary, (3) real tests, (4) independent release cadence, (5) substantial logic (not re-exports).

## Migration Sequence

1. **Consolidate tests** — done (single `pytest` from root)
2. **Absorb clarvis-reasoning** — inline into `clarvis/cognition/`, update 3 callers
3. **Extract clarvis-db** — when extraction gates pass
4. **Absorb clarvis-cost** — optional, when maintenance friction warrants it
