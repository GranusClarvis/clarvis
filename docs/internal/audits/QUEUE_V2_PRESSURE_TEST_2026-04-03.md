# Queue Engine V2 — Pressure Test Review

**Reviewer**: Claude Code Opus (executive function)  
**Date**: 2026-04-03  
**Input**: `docs/QUEUE_ARCHITECTURE_REVIEW_2026-04-03.md` §1-8  
**Verdict**: **Directionally right, but Phase A has a critical design flaw. Fix before proceeding.**

---

## 1. Verdict on V2

The review correctly identifies the three real problems:
1. No task state machine → failed tasks silently retry forever
2. No failure tracking → no backoff, no "this failed 5 times" signal
3. Scoring over-engineering → 9 factors for a 2-10 item queue

The proposed architecture (JSON backing store + state machine + simplified scorer) is the right direction. But the specific design has a **dual-source-of-truth problem** that will cause operational pain.

---

## 2. Biggest Risks (ranked)

### Risk 1: QUEUE.md becomes read-only — operator hostility (CRITICAL)

The review says: _"QUEUE.md (generated)"_ via `render_markdown()`.

This means the operator can no longer `vim QUEUE.md` to add a task, reorder priorities, or annotate a task. Every edit gets overwritten on the next `render_markdown()` call. The current workflow is:

```
Operator (M2.5 or human) → edits QUEUE.md → next heartbeat picks it up
```

The proposed workflow becomes:

```
Operator → must use queue_engine.add() API → engine writes JSON → engine renders QUEUE.md
```

This is a regression. QUEUE.md's greatest strength is that it's a plain text file anyone can edit. Making it generated turns a feature into a liability.

**Fix**: Don't make QUEUE.md generated. Keep it as the human-editable interface. Add `queue_state.json` as a **sidecar** that tracks only volatile runtime state (attempts, last_run, state, failure_reason) keyed by task tag `[TAG]`. The sidecar is disposable — if deleted, worst case is retry counters reset to zero. QUEUE.md remains the source of truth for task existence and priority.

### Risk 2: JSON corruption on partial write (HIGH)

`queue_state.json` is written by `json.dump()` under fcntl lock. If the process is killed mid-write (OOM, `kill -9`, disk full), the file is corrupted. Unlike QUEUE.md (which is append-mostly and survives partial writes because each line is independent), a half-written JSON file is unrecoverable.

**Fix**: Write to `queue_state.json.tmp`, then `os.rename()` (atomic on Linux). Standard pattern. Must be in the spec.

### Risk 3: Migration window — two code paths (MEDIUM)

Phase A says "migrate queue_writer.py to use engine API". During migration, some callers use the old `queue_writer.add_task()` (direct QUEUE.md manipulation) while the engine uses JSON. If both are active simultaneously, they diverge.

**Fix**: Phase A should NOT change queue_writer.py's external API. Instead, queue_engine should be a new module that wraps/replaces queue_writer internals. The transition is: queue_writer.add_task() → internally calls queue_engine.add() → engine updates sidecar. Callers don't change until Phase C.

### Risk 4: "Soak for 1 week" is undefined (MEDIUM)

The review says Phase B follows "only after Phase A soaks for 1 week." But what does soak mean? What metrics determine stability?

**Fix**: Define soak criteria:
- Zero queue_state.json corruption events
- Zero cases where sidecar state and QUEUE.md disagree on task existence
- `stats()` returns valid data for 7 consecutive days
- No heartbeat failures caused by queue_engine code

### Risk 5: Retry backoff hides tasks forever (LOW but insidious)

"Skip N heartbeats after failure" means a task that fails 3 times with exponential backoff (skip 1, skip 2, skip 4 heartbeats) disappears for ~18 hours. With only 12 autonomous runs/day, that's 1.5 days of invisibility. If the failure was transient (network blip), the task is unnecessarily delayed.

**Fix**: Cap backoff at 2 skips (one full cycle). After max retries, move to `deferred` state with a human-readable reason in QUEUE.md — the operator decides whether to retry or delete.

---

## 3. What to Simplify

### Simplification 1: Kill the `render_markdown()` concept

As argued in Risk 1 — QUEUE.md stays human-editable, the sidecar tracks runtime state. The engine reads QUEUE.md to discover tasks, reads the sidecar for state. This eliminates:
- The sync problem
- The "generated vs edited" confusion
- The need to replicate QUEUE.md formatting in code

### Simplification 2: Score simplification should be Phase 1, not Phase B

The scoring change (9 factors → 3) is:
- Zero migration risk (no data format change)
- Immediately testable (compare old vs new rankings on historical episodes)
- The highest-impact change per LOC removed

Moving it to Phase B (after the backing store) delays the highest-value, lowest-risk change behind the lowest-value, highest-risk change. Invert the order.

### Simplification 3: Drop `parent_id` and task dependencies from V2

The schema includes `parent_id` for subtask linkage. But auto-split currently works by text convention (`[~]` parent + `- [ ]` subtasks below it). Adding structural parent-child relationships is a new feature, not a fix for an existing problem. Defer to V3.

### Simplification 4: Drop `metadata: {}` from the schema

An untyped metadata bag invites scope creep. Every feature that "doesn't fit" gets stuffed into metadata. If a field is needed, add it explicitly. Start with the minimum viable schema.

---

## 4. What to Keep

| Component | Verdict | Why |
|---|---|---|
| State machine (pending/running/succeeded/failed/deferred) | **Keep** | Core value of V2. Without this, the rest is pointless. |
| Failure tracking (attempts + last_failure) | **Keep** | Directly addresses the "silent retry forever" bug. |
| `stats()` for observability | **Keep** | Critical gap. Queue health should be observable. |
| Simplified scoring (3 factors) | **Keep** | Removes 6 fragile, low-impact scoring dimensions. |
| P0 floor + delivery lock as post-modifiers | **Keep** | Proven mechanisms, clean separation. |
| Failed penalty in scoring | **Keep** | Tasks that failed N times should rank lower. |
| Gate system (unchanged) | **Keep** | Cleanest component. Don't touch. |
| Locking (unchanged) | **Keep** | Works. Don't touch. |
| Daily auto-task cap | **Keep** | Earned lesson. Don't touch. |

---

## 5. Refined vNext Architecture

### Design shift: Sidecar, not replacement

```
┌─────────────────────────────────────────────────────────────┐
│                     QUEUE ENGINE                             │
│  clarvis/orch/queue_engine.py (new)                         │
│                                                              │
│  Source of truth:  memory/evolution/QUEUE.md (human-editable)│
│  Runtime sidecar:  data/queue_state.json (machine-managed)  │
│                                                              │
│  QUEUE.md owns:        Sidecar owns:                        │
│   - task existence      - state (pending/running/…)         │
│   - priority (section)  - attempts count                    │
│   - text description    - last_failure reason               │
│   - task tag [TAG]      - last_run timestamp                │
│                          - created_at (first seen)          │
│                          - updated_at                       │
│                                                              │
│  Reconciliation:                                            │
│   On every select_next():                                   │
│   1. Parse QUEUE.md → set of (tag, text, priority)          │
│   2. Load sidecar → dict of tag → runtime state             │
│   3. Merge: new tags in MD get default sidecar entry        │
│   4. Tags in sidecar but not in MD → mark stale, ignore     │
│   5. Score merged candidates → return best                  │
│                                                              │
│  State transitions:                                         │
│   pending → running → succeeded                             │
│   pending → running → failed → pending (retry ≤ max)        │
│   failed → deferred (max retries exceeded)                  │
│   any → removed (operator deletes from QUEUE.md)            │
│                                                              │
│  API:                                                       │
│   add(text, priority, tag, source) → writes to QUEUE.md     │
│   select_next() → Task | None (reconciles MD + sidecar)     │
│   mark_running(tag)        → sidecar update                 │
│   mark_succeeded(tag, ann) → sidecar + mark [x] in QUEUE.md │
│   mark_failed(tag, reason) → sidecar update only            │
│   defer(tag, reason)       → sidecar + annotate in QUEUE.md │
│   archive_completed()      → move [x] to QUEUE_ARCHIVE.md   │
│   stats() → dict                                            │
│                                                              │
│  Writes: atomic rename (tmp → final) under fcntl lock       │
│  Max retries: 3 (P0), 2 (P1), 1 (P2)                       │
│  Backoff cap: 2 heartbeat skips maximum                     │
└─────────────────────────────────────────────────────────────┘
```

### Queue Health Observability (`stats()`)

```python
def stats() -> dict:
    """Queue health metrics — call from health_monitor.sh or CLI."""
    return {
        # Snapshot
        "pending": int,          # tasks in pending state
        "running": int,          # tasks currently running (should be 0 or 1)
        "failed": int,           # tasks in failed state (retry pending)
        "deferred": int,         # tasks that hit max retries
        "total": int,            # all tracked tasks
        
        # Throughput (from sidecar history)
        "completed_24h": int,    # tasks succeeded in last 24h
        "failed_24h": int,       # tasks failed in last 24h
        "avg_attempts": float,   # average attempts per completed task
        
        # Health signals
        "oldest_pending_hours": float,  # age of oldest pending task
        "stuck_running": list,          # tasks in running state > 2h (likely orphaned)
        "chronic_failures": list,       # tasks failed >= max_retries
    }
```

This integrates into existing health_monitor.sh (already runs every 15 min) and the Telegram digest.

### Migration Order (revised)

**Phase 1 — Simplify Scorer** (1 session, zero risk):
1. Strip `task_selector.py` to 3 factors (priority, novelty, idle-time)
2. Move removed factors to `_legacy_enrichment()` — logged but not used for scoring
3. Delete 5 keyword lists
4. Validate: run old and new scorers on last 20 episodes, compare rankings

**Phase 2 — Queue Engine + Sidecar** (2-3 sessions):
1. Create `clarvis/orch/queue_engine.py` with sidecar model
2. Wire queue_writer.py internals to use engine (external API unchanged)
3. Add `stats()` and wire into health_monitor.sh
4. Soak: 7 days, criteria defined above

**Phase 3 — Pipeline Integration** (1-2 sessions, after soak):
1. Preflight calls `queue_engine.select_next()` + `mark_running()`
2. Postflight calls `mark_succeeded()` / `mark_failed()`
3. Optional postflight recording steps move to async

---

## 6. Should the Queue Change?

**No new queue items needed.** The review doc correctly advises against scattering this into multiple queue entries. If implementation is greenlit, add ONE item:

```
- [ ] [QUEUE_ENGINE_V2] Implement queue engine: Phase 1 (scorer simplification) then Phase 2 (sidecar state store + stats). Spec: docs/QUEUE_V2_PRESSURE_TEST_2026-04-03.md §5.
```

The existing 2 pending items are fine. No changes to QUEUE.md content.

---

## 7. Summary Table

| Aspect | V2 Proposal | Pressure Test Verdict |
|---|---|---|
| JSON backing store | Replace QUEUE.md | **Reject** — sidecar model instead. QUEUE.md stays editable. |
| render_markdown() | Generate QUEUE.md from JSON | **Reject** — creates dual-source-of-truth. |
| State machine | 5 states with transitions | **Keep** — core value, implement in sidecar. |
| Failure tracking | attempts + last_failure | **Keep** — critical gap. |
| Simplified scoring | 3 factors from 9 | **Keep** — reorder to Phase 1 (lowest risk, highest value). |
| parent_id / dependencies | In task schema | **Defer** — not a current problem. |
| metadata: {} | Open bag | **Reject** — scope creep magnet. |
| Phase order | A (store) → B (scorer) → C (pipeline) | **Reorder** — 1 (scorer) → 2 (store) → 3 (pipeline). |
| Soak criteria | "1 week" (undefined) | **Specify** — 4 concrete metrics for 7 days. |
| Atomic writes | Not mentioned | **Add** — tmp+rename pattern required. |
| Backoff | "skip N heartbeats" (unbounded) | **Cap** — max 2 skips, then defer to operator. |

**Bottom line**: V2 is directionally correct but over-rotates on "JSON replaces markdown." The sidecar model preserves operator ergonomics while adding the structural foundation (state machine, failure tracking, observability) that's actually missing. Simplify the scorer first — it's the cheapest win.
