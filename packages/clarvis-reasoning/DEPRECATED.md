# clarvis-reasoning — DEPRECATED

**Status**: Deprecated as of 2026-04-03.

`clarvis-reasoning` was the standalone meta-cognitive reasoning quality assessment package.
The canonical implementation now lives in `clarvis.cognition.reasoning` (the spine module),
which provides the full ClarvisReasoner engine (926L) plus the metacognition quality checks,
integrated with the heartbeat pipeline and reasoning chain hooks.

## What happened

- `clarvis.cognition.reasoning` became the production API; all scripts use spine imports.
- `clarvis-reasoning` is only self-referentially imported (its own tests + CLI).
- `scripts/clarvis_reasoning.py` is a bridge that re-exports from `clarvis.cognition.reasoning`.
- `scripts/reasoning_chain_hook.py` imports from `reasoning_chains`, not the package.

## Migration

Replace any `from clarvis_reasoning import ...` with:

```python
from clarvis.cognition.reasoning import (
    ReasoningStep, ReasoningSession, ClarvisReasoner,
    get_reasoner, reasoner,
)
```

For metacognition quality checks:

```python
from clarvis.cognition.reasoning import (
    check_step_quality, evaluate_session, diagnose_sessions,
)
```

## Tests

The test suite in `packages/clarvis-reasoning/tests/` remains valid for the standalone
metacognition engine. These may be published separately if needed.
