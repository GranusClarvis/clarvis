# ClarvisDB API Boundary (v0)

_Status: execution baseline (pre-extraction), source of truth for `clarvis-db` split._

## 1) Purpose

`clarvis-db` is the reusable memory/retrieval subsystem.  
It owns storage, recall, graph relations, retrieval evaluation, and retrieval feedback loops.

It **does not** own orchestration (heartbeat/cron/task routing) or prompt assembly policy.

---

## 2) Public surface (stable-for-v0)

These symbols/modules are the initial compatibility contract.

## 2.1 Python SDK contract

From `clarvis.brain`:

- `get_brain()`
- `get_local_brain()`
- `remember(text, importance=..., category=...)`
- `capture(text)`
- `search(query, n=..., min_importance=..., collections=...)`
- lazy singleton `brain` (for host environments already using this pattern)

From `clarvis.brain.retrieval_eval`:

- `classify_batch(results, query) -> (verdict, max_score, scores)`

From `clarvis.brain.retrieval_feedback`:

- `record_feedback(verdict, outcome, max_score=None, task="")`

From `clarvis.brain.retrieval_trace`:

- `append_retrieval_trace(event)`

## 2.2 Data/observability helpers (beta, but exposed)

From `clarvis.metrics.retrieval_trace_report`:

- `load_trace_events(hours=24)`
- `summarize_trace(events)`
- `format_trace_summary(summary, hours=24)`

CLI (current monorepo binding):

- `clarvis metrics retrieval-trace`

---

## 3) Internal-only surface (not part of v0 contract)

These are implementation details and may change without semver guarantees:

- heartbeat hook wiring internals
- queue/task policy logic
- cron scripts
- script-level wrappers in `scripts/` that call brain internals directly
- benchmark orchestration wrappers (kept in main `clarvis` repo)

---

## 4) Storage and config contract

- Workspace root is resolved via `CLARVIS_WORKSPACE` (fallback allowed for legacy path).
- Persistent data is expected under `<workspace>/data/...`.
- Retrieval trace file: `<workspace>/data/retrieval_trace.jsonl`.
- Retrieval quality files: `<workspace>/data/retrieval_quality/...`.

Any future extraction must preserve this environment contract or provide a migration shim.

---

## 5) Host integration boundary (plug-and-play)

`clarvis-db` integration should require only:

1. Python import + initialize (`get_brain()` / `get_local_brain()`), or
2. MCP server adapter (planned), or
3. REST adapter (planned).

Host-specific logic (OpenClaw/Hermes/NanoClaw) stays in adapters, not core memory engine.

---

## 6) Compatibility checks required before extraction

Minimum contract checks to keep green during split:

1. `get_brain()` + `search()` + `remember()` roundtrip.
2. Retrieval eval classification (`classify_batch`) deterministic smoke.
3. Retrieval feedback persistence (`record_feedback`) writes valid state.
4. Retrieval trace append + summary (`append_retrieval_trace` + report functions).
5. Workspace portability check using `CLARVIS_WORKSPACE=/workspace`.

Host contract check command:

```bash
python3 scripts/compat_contract_check.py
```

This validates current public symbols against OpenClaw/Hermes/NanoClaw compatibility contracts.

---

## 7) Explicit non-goals for `clarvis-db`

- No task selection.
- No autonomous queue generation.
- No prompt-template ownership.
- No website/dashboard ownership.

Those remain in `clarvis` (main harness) and `clarvis-p` (prompt/context layer).
