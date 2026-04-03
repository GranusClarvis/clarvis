# clarvis-cost — DEPRECATED

**Status**: Deprecated as of 2026-04-03.

`clarvis-cost` was the standalone cost tracking and token optimization package.
The canonical implementation now lives in `clarvis.orch.cost_tracker` (the spine module),
which provides the same CostTracker, pricing tables, token estimation, rollups, and
budget checks, plus integration with the spine CLI (`clarvis cost`).

## What happened

- `clarvis.orch.cost_tracker` became the production API; all scripts and cron jobs use it.
- `clarvis-cost` is only self-referentially imported (its own tests + CLI).
- `scripts/cost_tracker.py` imports from `clarvis.orch.cost_tracker`, not the package.
- `heartbeat_postflight.py` imports from `clarvis.orch.cost_tracker`.

## Migration

Replace any `from clarvis_cost import ...` with:

```python
from clarvis.orch.cost_tracker import CostTracker, estimate_cost, estimate_tokens
```

For the optimizer:

```python
# optimizer.py functions are available via CostTracker methods
# or import directly from clarvis.orch.cost_tracker
```

## Tests

The test suite in `packages/clarvis-cost/tests/` remains valid for the standalone
CostTracker engine. These may be published separately if needed.
