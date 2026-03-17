# Repo Consolidation Plan — Final Decision

_Date: 2026-03-16_
_Status: DECIDED_

## Decision: Two repos. No vanity packages.

### Repo 1: `clarvis` (main)

**URL:** `github.com/GranusClarvis/clarvis`
**Contains:**
- `clarvis/` — spine: brain, heartbeat, cognition, context, metrics, runtime, orch, adapters, compat
- `scripts/` — operational scripts (cron orchestrators, brain tools, maintenance, cognitive architecture)
- `tests/` — all tests (consolidated from `tests/`, `scripts/tests/`, `clarvis/tests/`)
- `skills/` — OpenClaw skill definitions
- `docs/` — architecture, ADRs, plans, boundary specs
- `memory/` — structural docs only (daily logs excluded from public via .gitignore)
- `data/` — excluded from public (.gitignore), runtime only
- Identity docs: `AGENTS.md`, `SOUL.md`, `ROADMAP.md`, `HEARTBEAT.md`, `SELF.md`, `MEMORY.md`

**Absorbs (as internal modules, not packages):**
- `clarvis-cost` → `clarvis/cost/` (or stays in `packages/` for now as internal dependency)
- `clarvis-reasoning` → `clarvis/cognition/reasoning.py` (already partially there)

### Repo 2: `clarvis-db` (standalone brain package)

**URL:** `github.com/GranusClarvis/clarvis-db`
**Contains:**
- `clarvis_db/` — ChromaDB vector memory with Hebbian learning, STDP synapses
- `tests/`
- `README.md`, `LICENSE`, `CHANGELOG.md`, `pyproject.toml`

**Why separate:**
1. **Clean API boundary** — documented in `docs/CLARVISDB_API_BOUNDARY.md`
2. **Independently useful** — any agent system can use it for vector memory with Hebbian learning
3. **Has real tests** — the only package with meaningful test coverage
4. **Different release cadence** — brain internals evolve independently of harness

**Extraction status:** `stabilizing` → `public-ready` when CI + LICENSE file + credential scrub complete.

---

## Explicitly Rejected

### clarvis-p (context/prompt layer)
- **Status:** REJECTED as separate package
- **Reason:** No external consumer exists. The "bridge" just re-exports from `clarvis.context.*`. One consumer (Clarvis itself) = internal module, not package.
- **Where the code lives:** `clarvis/context/` (assembly, relevance, compression)
- **When to reconsider:** If a second agent host genuinely needs context assembly as a dependency
- **Boundary spec preserved:** `docs/CLARVISP_API_BOUNDARY.md` defines what the API would look like if extraction becomes justified

### clarvis-cost (cost tracking)
- **Status:** REJECTED as separate package
- **Reason:** 5 internal callers, 0 external consumers. Adds package overhead for a single-project utility.
- **Where the code lives:** `packages/clarvis-cost/` (keep as-is for now, absorb into `clarvis/cost/` when convenient)
- **Import consumers:** `heartbeat_postflight.py`, `cost_tracker.py`, `cron_implementation_sprint.sh`, `cron_research.sh`, `cli_cost.py`

### clarvis-reasoning (meta-cognitive reasoning)
- **Status:** REJECTED as separate package
- **Reason:** 3 internal callers, 0 external consumers. Already partially absorbed into `clarvis/cognition/reasoning.py`.
- **Where the code lives:** `packages/clarvis-reasoning/` → will fully absorb into `clarvis/cognition/`

### Any 4th+ repo
- **Status:** REJECTED unless strong evidence emerges
- **Anti-sprawl rule:** New repos require: (1) at least 2 real consumers, (2) clean API boundary, (3) independent release cadence, (4) meaningful test coverage

---

## Anti-Package-Sprawl Policy

Before creating ANY new package or repo, verify ALL of the following:

1. **≥2 independent consumers** exist (or will exist within 30 days with concrete plans)
2. **Clean API boundary** documented and stable for ≥14 days
3. **Real tests** that test behavior, not just imports
4. **Independent release cadence** — the package changes on a different schedule than the main repo
5. **Not a re-export** — the package has substantial logic, not just `from clarvis.X import *`

If any check fails → keep as internal module in `clarvis/`.

---

## Migration Path

### Phase 1: Consolidate tests (can do now)
- Move `scripts/tests/` and `clarvis/tests/` → `tests/`
- Delete `scripts/deprecated/` directory
- Single `pytest` invocation from repo root

### Phase 2: Absorb clarvis-reasoning (low effort)
- `clarvis/cognition/reasoning.py` already imports from `clarvis_reasoning`
- Inline the core logic, remove `packages/clarvis-reasoning/`
- Update 3 callers

### Phase 3: Extract clarvis-db (when ready)
- Create `github.com/GranusClarvis/clarvis-db`
- Copy `packages/clarvis-db/` content
- Add CI, LICENSE, scrub test data for credentials
- Main repo adds `clarvis-db` as pip dependency

### Phase 4: Absorb clarvis-cost (optional, low priority)
- Move core logic into `clarvis/cost/`
- Update 5 callers
- Remove `packages/clarvis-cost/`
- Only do this if the separate package causes maintenance friction

---

## Website Alignment

The public website (`docs/WEBSITE_V0_INFORMATION_ARCH.md`) should show:
- **2 repos**: `clarvis` + `clarvis-db`
- **No mention of**: `clarvis-p`, `clarvis-cost`, `clarvis-reasoning`
- Extraction status labels on `/repos` page reflect actual state
