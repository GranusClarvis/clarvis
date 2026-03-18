# clarvis-db — DEPRECATED

**Status**: Deprecated as of 2026-03-17.

`clarvis-db` was the standalone vector memory package (ChromaDB + Hebbian + STDP).
The canonical brain implementation now lives in `clarvis.brain` (the spine module),
which provides the same ChromaDB + ONNX functionality plus graph, episodic memory,
and full integration with the heartbeat pipeline.

## What happened

- `clarvis.brain` became the production API; all scripts and cron jobs use it.
- `clarvis-db` is only self-referentially imported (its own tests + adapter fallback).
- The adapter fallback in `clarvis/adapters/openclaw.py` has been removed — spine is canonical.

## Migration

Replace any `from clarvis_db import ...` with:

```python
from clarvis.brain import brain, search, remember, capture
```

## Tests

The test suite in `packages/clarvis-db/tests/` remains valid for the standalone
VectorStore + Hebbian + STDP engines. These may be published separately if needed.
