# Package Consolidation Plan

_Created 2026-03-17. Updated 2026-04-03 (second pass complete)._

## Status Summary

| Package | LOC | Status | Spine Equivalent | Safe to Delete? |
|---------|-----|--------|------------------|-----------------|
| clarvis-db | 1,554 | **DEPRECATED** | `clarvis.brain` | Yes — zero external imports |
| clarvis-cost | 978 | **DEPRECATED** | `clarvis.orch.cost_tracker` | Yes — zero external imports |
| clarvis-reasoning | 404 | **DEPRECATED** | `clarvis.cognition.reasoning` | Yes — zero external imports |

All three packages have **zero runtime imports** from outside their own `packages/` directories.
The spine provides all functionality. Packages are retained only for potential standalone publishing.

## Completed

### Pass 1 (2026-03-17): clarvis-db → Deprecated
- Removed `clarvis_db` / `clarvis_p` bridge imports from `clarvis/adapters/openclaw.py`
- Adapter now imports directly from spine: `clarvis.brain`, `clarvis.context.assembly`
- Added `packages/clarvis-db/DEPRECATED.md` with migration instructions

### Pass 2 (2026-04-03): All Three Packages Deprecated
- **clarvis-cost**: Added DEPRECATED.md. Spine equivalent `clarvis.orch.cost_tracker` confirmed canonical — `scripts/cost_tracker.py` and `heartbeat_postflight.py` both import from spine.
- **clarvis-reasoning**: Added DEPRECATED.md. Spine equivalent `clarvis.cognition.reasoning` confirmed canonical — `scripts/clarvis_reasoning.py` is a bridge re-exporting from spine.
- **Dockerfile**: Removed standalone package installs; spine `pip install ".[all]"` provides everything.
- **CI**: Decoupled package tests from spine test suite; CI now runs `tests/` only.
- **pyproject.toml**: `testpaths` updated from `["packages", "tests"]` to `["tests"]`.
- **Docstring fix**: `clarvis/cognition/reasoning.py` usage example updated to spine import path.

## Deletion Safety Assessment

All three packages can be safely deleted from the monorepo. Evidence:
1. `grep -r 'from clarvis_cost\|from clarvis_db\|from clarvis_reasoning'` returns only self-referential hits inside `packages/`.
2. No spine code, no scripts, no cron jobs import from any package.
3. All bridge scripts (`scripts/cost_tracker.py`, `scripts/clarvis_reasoning.py`) import from spine.
4. Dockerfile and CI no longer depend on package installs.

**Recommendation**: Delete `packages/` when ready, or keep for standalone PyPI publishing.

## Principles

1. **Spine is canonical** — `clarvis.*` is the import path for all new code
2. **Packages for external publishing only** — standalone PyPI packages for reuse outside Clarvis
3. **No bridge imports** — remove `try: package / except: spine` patterns; use spine directly
4. **Legacy scripts can use spine** — `from clarvis.brain import ...` works everywhere
