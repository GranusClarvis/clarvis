# Package Consolidation Plan

_Created 2026-03-17. Tracks consolidation of `packages/` into the `clarvis/` spine module._

## Status Summary

| Package | LOC | Status | Action | Done |
|---------|-----|--------|--------|------|
| clarvis-db | 1,554 | **DEPRECATED** | Spine (`clarvis.brain`) is canonical. Adapter bridge removed. | Yes |
| clarvis-cost | 978 | **LIVE** | Migrate `core.py` + `optimizer.py` → `clarvis/cost/`. | Deferred |
| clarvis-reasoning | 404 | **INCOMPLETE** | Engine (926L) still in `scripts/clarvis_reasoning.py`. Complete migration to spine. | Deferred |

## Completed (2026-03-17)

### clarvis-db → Deprecated
- Removed `clarvis_db` / `clarvis_p` bridge imports from `clarvis/adapters/openclaw.py`
- Adapter now imports directly from spine: `clarvis.brain`, `clarvis.context.assembly`
- Added `packages/clarvis-db/DEPRECATED.md` with migration instructions
- Package preserved for standalone publishing if needed, but not used in Clarvis runtime

## Deferred

### clarvis-cost → Spine Migration (P2)
- **Why defer**: Package is actively used and stable. Migration changes import paths in 4+ files.
- **Plan**: Move `core.py` (582L) + `optimizer.py` (244L) into `clarvis/cost/`. Update imports in `heartbeat_postflight.py`, `cost_tracker.py`, cron scripts, `cli_cost.py`.
- **Risk**: Low. Pure refactor, no logic changes.

### clarvis-reasoning → Complete + Migrate (P2)
- **Why defer**: The package only has validation functions (404L). The real engine (`ClarvisReasoner`, 926L) is still in `scripts/clarvis_reasoning.py`. Migration requires moving both halves together.
- **Plan**: Merge scripts engine + package validation into `clarvis/cognition/reasoning/`. Fix `reasoning_chain_hook.py` imports.
- **Risk**: Medium. Multiple import paths to update, engine has side effects.

## Principles

1. **Spine is canonical** — `clarvis.*` is the import path for all new code
2. **Packages for external publishing only** — standalone PyPI packages for reuse outside Clarvis
3. **No bridge imports** — remove `try: package / except: spine` patterns; use spine directly
4. **Legacy scripts can use spine** — `from clarvis.brain import ...` works everywhere
