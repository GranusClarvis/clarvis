# Queue/Control Architecture Design Review — 2026-04-03

**Reviewer**: Claude Code Opus (executive function)
**Scope**: Queue lifecycle, task selection, heartbeat pipeline, locking, state management
**Method**: Full source read of queue_writer.py, task_selector.py, heartbeat_gate.py, heartbeat_preflight.py, heartbeat_postflight.py, lock_helper.sh, cron_autonomous.sh, queue_auto_archive.py

---

## 1. Current Architecture Critique

### What works well

1. **Heartbeat gate** (`clarvis/heartbeat/gate.py`): Elegant zero-LLM design. File fingerprinting avoids wasted tokens. Force-wake conditions (4h gap, midnight, max skips) are well-tuned safety valves. This is the cleanest component in the pipeline.

2. **Lock helper** (`scripts/lock_helper.sh`): Three-tier locking (local/global-Claude/maintenance) with stale detection and PID verification via `/proc/<pid>/cmdline` is solid. The backward-compatible lock format was a good call.

3. **Daily auto-task cap** (queue_writer.py): `MAX_AUTO_TASKS_PER_DAY = 5` prevents runaway queue inflation. Structural refactor gate blocks aesthetic-driven tasks. These are earned lessons codified well.

4. **Batched preflight/postflight**: Consolidating 25+ subprocess cold-starts into 2 processes was a real performance win (7-8s/heartbeat).

### Structural problems

**Problem 1: Markdown is the database.**
QUEUE.md is simultaneously a human-readable document and the task state store. Every state transition (add, in-progress, complete, archive) is a regex-based string replacement in a text file. This creates:
- **Parse fragility**: Section detection relies on `## P0`, `## P1`, `## P2` headers. Any formatting change breaks parsing.
- **No schema enforcement**: A task is whatever text follows `- [ ]`. Tags are optional conventions, not enforced structure.
- **No metadata**: No creation timestamp, no attempt count, no failure history, no last-executed time, no estimated duration. All of this has to be inferred from git history or episodes.json.
- **Archive bloat**: QUEUE_ARCHIVE.md is 2070 lines — a flat append-only text file with no indexing. Dedup checks scan the entire archive on every `add_task()`.

**Problem 2: Task state machine is implicit.**
The lifecycle `[ ] → [~] → [x]` exists only in human convention. There is no enforcement:
- Nothing prevents marking a `[ ]` directly as `[x]` (skipping in-progress).
- Nothing prevents a `[~]` from being un-marked back to `[ ]`.
- A task can fail (Claude exits non-zero), yet the task stays as `[ ]` — no failure state, no retry counter, no backoff.
- Postflight records the *episode* but doesn't update the *task state in QUEUE.md*. The task just sits there to be retried.

**Problem 3: Reader/writer concurrency gap.**
`queue_writer.py` uses fcntl locks for writes. Good. But `task_selector.py` reads QUEUE.md without any lock. `cron_autonomous.sh` reads the preflight JSON output, not the queue directly, but there's a TOCTOU window: between preflight selecting a task and the executor starting, another cron job could modify the queue. In practice, the global Claude lock prevents concurrent execution, so this is unlikely — but it's an accidental safety property, not a designed one.

**Problem 4: Preflight is a god function.**
`heartbeat_preflight.py` is 450+ lines with 25+ try/except import blocks. It handles:
- Stuck agent detection
- External challenge injection
- Attention system tick
- Codelet competition
- Task parsing and scoring
- 5 candidate gates (cognitive load, sizing, verification, mode, confidence)
- Auto-splitting
- Context assembly (brain search, episodic recall, compression)
- Router classification
- Procedural memory lookup
- Prompt variant selection
- Obligation tracking

This is too many responsibilities. A failure in any module (even a non-fatal one) adds noise to logs and slows the pipeline. More importantly, it makes the preflight impossible to test in isolation — you can't run the task selector without also running the attention system, codelet competition, and brain search.

---

## 2. Upgraded Design Critique

The "upgraded" design adds cognitive sophistication (somatic markers, codelet competition, world model re-ranking, spotlight alignment, novelty scoring, improve-existing bias, context-relevance boost) to the task selector.

### What the upgrades get right

- **Novelty penalty**: Prevents the system from grinding the same topic repeatedly. Jaccard similarity against recent completed tasks is a sound heuristic.
- **P0 floor guarantee**: Hard rule that P0 tasks can't be pushed below rank 3. Simple, correct, prevents priority inversion.
- **Delivery lock**: Focus-narrowing during deadline sprints. Clean implementation.

### What the upgrades get wrong

**Over-sophistication for the problem size.**
The queue typically has 2-10 pending tasks. The scoring system has 9 factors, 5 keyword lists, 4 bonus systems, and 3 re-ranking passes. For a queue this small, the marginal value of factor 7 (somatic markers) over a simpler system is negligible. The typical "final_score" spread is probably <0.15 across candidates, meaning small coefficient changes can completely reorder selection. This is **fragile precision** — high complexity, low predictability.

Scoring formula:
```
base_final = 0.70 * salience + 0.10 * spotlight_align + 0.10 * somatic + 0.10 * codelet
final = base_final * (1.0 + 0.3 * novelty)
```

Then world model re-ranking applies:
```
salience = 0.85 * salience + 0.15 * wm_signal
```

Then P0 floor enforcement. Then delivery lock. Four mutation passes on the same score. Each pass can invalidate assumptions from the previous one.

**Keyword-based "intelligence" is brittle.**
The scoring relies on keyword lists (AGI_KEYWORDS, INTEGRATION_KEYWORDS, ARCHITECTURAL_KEYWORDS, IMPROVE_EXISTING_KEYWORDS, CONTEXT_IMPROVEMENT_KEYWORDS). These are static lists that:
- Don't account for negation ("don't add new" would still boost NEW_FEATURE_KEYWORDS)
- Have overlap (is "refactor" architectural or improvement?)
- Require manual maintenance as the system evolves
- Give false signals on tasks with coincidental keyword matches

**The cognitive metaphors add conceptual load without proportional operational value.**
"Somatic markers", "codelet competition", "global workspace spotlight", "spreading activation" — these are interesting cognitive science concepts but they're implemented as small bias terms (typically ±0.05 to ±0.15) on a system that already decides correctly 90%+ of the time based on priority section alone. The complexity cost is real: anyone debugging task selection has to understand 9 interacting factors instead of 3.

---

## 3. Edge Cases and Failure Modes

### Race conditions
1. **Double execution**: If a cron job runs long enough to overlap with the next scheduled run, the local lock prevents double-start. But if the lock file is corrupted or the stale threshold (2400s) is crossed, two instances can run. The global Claude lock is the real safety net, but it only prevents concurrent Claude spawns, not concurrent preflight runs.

2. **Queue mutation during execution**: Task X is selected at preflight. During execution, queue_writer adds a P0 task. Postflight records the outcome of task X but doesn't know about the new P0. The next heartbeat will pick it up, but there's a ~2h worst-case delay (autonomous runs 8x/day).

3. **Auto-split orphans**: `_try_auto_split` creates subtasks and marks the parent `[~]`. If the parent marking fails (logged as "non-fatal"), you get subtasks with no parent linkage — they'll execute but the parent stays `[ ]` forever.

### Silent failures
4. **Postflight no-ops**: Of the 24+ recording steps in postflight, many are wrapped in try/except with fallback to None. If episodic_memory fails to import, episodes aren't recorded — but there's no alert. The system silently degrades.

5. **Archive dedup false negatives**: Word overlap at 50% threshold can miss semantic duplicates with different vocabulary ("fix brain search" vs "repair ClarvisDB recall"). Conversely, it can false-positive on unrelated tasks that share common words.

6. **Confidence gate global cache**: `_confidence_gate_cache` is a module-level global computed once per preflight run. If `dynamic_confidence()` returns LOW due to a transient condition, ALL candidates in that heartbeat are skipped. The system does nothing for that entire cycle.

### Scaling limits
7. **Archive scan on every add**: `add_tasks()` reads the entire 2070-line archive for dedup on every invocation. O(n*m) word overlap comparison. Not a problem today, but archive grows monotonically.

8. **Episodes.json full scan for novelty**: `_get_recent_completed_tasks()` reads the entire episodes.json, reverses it, and takes the last 15. No pagination, no index.

---

## 4. What Is Over-Complicated

| Component | Current complexity | Needed complexity |
|---|---|---|
| Task scoring | 9 factors, 4 mutation passes | Priority + recency + novelty (3 factors) |
| Keyword lists | 5 lists, ~60 keywords, manually maintained | 1-2 lists or none (priority is explicit) |
| Preflight | 450+ lines, 25+ imports, 10+ phases | Gate → Select → Classify → Assemble context |
| Postflight | 24+ recording steps | Episode record + queue state update + digest |
| Somatic markers | Emotional bias on task selection | Remove: no evidence it improves selection |
| Codelet competition | Cognitive subsystem bidding | Remove: adds ~0.05 bias, obscures selection logic |
| World model re-ranking | Predicted success probability | Keep but simplify: use episode history, not a separate model |
| Attention GWT for queue | Tasks submitted to global workspace | Overkill: GWT is for runtime attention, not batch scheduling |

---

## 5. What Is Missing

### Critical gaps

1. **Task state machine with transitions**: No explicit states (PENDING, RUNNING, SUCCEEDED, FAILED, DEFERRED, ARCHIVED). No transition validation. No timestamps on transitions. No retry policy.

2. **Failure tracking per task**: When a task fails (Claude exits non-zero), nothing records this against the task. The same task can fail 10 times in a row. There's no "max retries" or "backoff after failure" mechanism.

3. **Task execution history**: "Was this task attempted before? When? What happened?" requires cross-referencing episodes.json by task text similarity. There's no direct link from a queue item to its execution records.

4. **Observability**: No dashboard showing queue health metrics — throughput (tasks completed/day), failure rate, average time-in-queue, selection distribution by priority, stale task detection. The `performance_benchmark.py` measures brain speed, not queue health.

5. **Structured task schema**: Tasks have no formal schema. A task is arbitrary markdown text. There's no way to attach metadata (estimated duration, required capabilities, dependencies, blocked-by) without encoding it in the text and parsing with regex.

### Nice-to-have gaps

6. **Task dependencies**: No way to express "B depends on A" or "run C after D succeeds". The `[~]` in-progress + subtask pattern is a partial workaround but isn't enforced.

7. **Idempotency keys**: No way to prevent a task from being selected if it's already running in another session (e.g., a user-spawned Claude Code working on the same thing).

---

## 6. Recommended vNext Architecture

### Design principles
- **Markdown for humans, JSON for machines**: Keep QUEUE.md as a human-readable view, but add a structured backing store.
- **Explicit state machine**: Tasks have defined states with validated transitions.
- **Simplify scoring**: 3 factors, not 9. Priority is king. Novelty and recency are tiebreakers.
- **Separate concerns**: Gate, Select, Execute, Record are independent stages.
- **Fail loudly on critical paths, silently on optional paths**: Core pipeline (gate → select → execute → record) must never silently degrade.

### Architecture blocks

```
┌──────────────────────────────────────────────────────┐
│                    QUEUE ENGINE                       │
│  (clarvis/orch/queue_engine.py — new)                │
│                                                      │
│  Backing store: data/queue_state.json                │
│  Human view:    memory/evolution/QUEUE.md (generated) │
│                                                      │
│  Task schema:                                        │
│  {                                                   │
│    "id": "TAG",                                      │
│    "text": "description",                            │
│    "priority": "P0|P1|P2",                           │
│    "state": "pending|running|succeeded|failed|deferred",│
│    "created_at": "ISO8601",                          │
│    "updated_at": "ISO8601",                          │
│    "attempts": 0,                                    │
│    "last_failure": null | "reason",                  │
│    "source": "manual|auto|external",                 │
│    "parent_id": null | "TAG",                        │
│    "metadata": {}                                    │
│  }                                                   │
│                                                      │
│  State transitions (enforced):                       │
│    pending → running → succeeded → archived          │
│    pending → running → failed → pending (retry)      │
│    pending → deferred (oversized/gated)               │
│    running → failed (timeout/crash)                  │
│    failed → pending (retry, if attempts < max)       │
│    failed → deferred (max retries exceeded)          │
│                                                      │
│  API:                                                │
│    add(text, priority, source) → id                  │
│    select_next() → Task | None                       │
│    mark_running(id)                                  │
│    mark_succeeded(id, annotation)                    │
│    mark_failed(id, reason)                           │
│    defer(id, reason)                                 │
│    archive_completed()                               │
│    render_markdown() → writes QUEUE.md               │
│    stats() → {pending, running, failed, throughput}  │
│                                                      │
│  Locking: fcntl on queue_state.json.lock             │
│  Max retries: 3 (configurable per priority)          │
│  Retry backoff: skip N heartbeats after failure      │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│                   TASK SCORER                         │
│  (clarvis/orch/task_selector.py — simplified)        │
│                                                      │
│  3 factors:                                          │
│    1. Priority weight: P0=0.9, P1=0.6, P2=0.3       │
│    2. Novelty: inverse Jaccard vs recent episodes    │
│    3. Recency bias: boost tasks idle > 24h           │
│                                                      │
│  Score = priority * (1.0 + 0.2*novelty + 0.1*idle)  │
│                                                      │
│  Modifiers (applied post-score, not as factors):     │
│    - P0 floor: guarantee top-3                       │
│    - Delivery lock: non-delivery tasks * 0.3         │
│    - Failed penalty: attempts > 0 → deprioritize     │
│                                                      │
│  Remove: somatic markers, codelet competition,       │
│  world model re-ranking, 5 keyword lists,            │
│  spotlight alignment, context-relevance boost        │
│  (these are attention-system concerns, not           │
│   scheduling concerns)                               │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│               EXECUTION PIPELINE                     │
│  (scripts/cron_autonomous.sh + preflight/postflight) │
│                                                      │
│  Phase 1: GATE                                       │
│    clarvis/heartbeat/gate.py (unchanged — clean)     │
│                                                      │
│  Phase 2: SELECT                                     │
│    queue_engine.select_next() → scored candidate     │
│    candidate_gates(task) → pass/defer/skip           │
│    queue_engine.mark_running(id)                     │
│                                                      │
│  Phase 3: PREPARE                                    │
│    router.classify(task) → executor tier             │
│    context_assembly(task) → brief + procedures       │
│    (This is what preflight does, minus attention/     │
│     codelet/somatic/AST prediction bloat)            │
│                                                      │
│  Phase 4: EXECUTE                                    │
│    spawn executor (Claude Code or cheap model)       │
│                                                      │
│  Phase 5: RECORD                                     │
│    exit_code → queue_engine.mark_succeeded/failed(id)│
│    episode_record(task, outcome, duration)            │
│    digest_append(summary)                            │
│    (This is what postflight does, minus 20 optional  │
│     recording steps that can run asynchronously)     │
└──────────────────────────────────────────────────────┘
```

### Migration path

This is NOT a rewrite. It's a refactor in 3 phases:

**Phase A — Queue Engine** (standalone, no pipeline changes):
1. Create `clarvis/orch/queue_engine.py` with JSON backing store
2. Add `render_markdown()` that generates QUEUE.md from state
3. Migrate `queue_writer.py` to use engine API instead of direct markdown manipulation
4. Validate: QUEUE.md output is identical to current format

**Phase B — Simplified Scorer** (task_selector.py):
1. Strip scoring to 3 factors (priority, novelty, recency)
2. Move cognitive modules (somatic, codelet, spotlight) to optional "enrichment" layer that runs independently and logs insights but doesn't affect selection
3. Keep P0 floor and delivery lock as post-score modifiers

**Phase C — Pipeline Integration** (preflight/postflight):
1. Preflight calls `queue_engine.select_next()` and `queue_engine.mark_running()`
2. Postflight calls `queue_engine.mark_succeeded()` or `queue_engine.mark_failed()`
3. Split optional recording steps into background async (they don't need to block the pipeline)

---

## 7. Queue Tasks Assessment

### Should NOT be added to queue

The design review itself doesn't warrant new queue items unless specific implementation is committed to. Most of the recommendations above are Phase A/B/C of a refactor that should be done as one coordinated effort, not as scattered queue items.

### Existing items: no changes needed

The 2 pending items (`SPINE_REMAINING_LIBRARY_MODULES`, `BLOAT_AGGRESSIVE_DEDUP_PRUNE`) are correctly scoped and prioritized. The queue_engine work proposed above would be a new P2 item if/when committed to.

### If the operator decides to proceed: one item

If this review is accepted and implementation is greenlit, add ONE queue item:

```
- [ ] [QUEUE_ENGINE_V2] Implement stateful queue engine (Phase A: JSON backing store + state machine + render_markdown). Spec: docs/QUEUE_ARCHITECTURE_REVIEW_2026-04-03.md §6. Phase B (scorer simplification) and Phase C (pipeline integration) follow only after Phase A soaks for 1 week.
```

Do NOT add Phase B and C as separate queue items yet — they depend on Phase A proving stable.

---

## 8. Summary

| Aspect | Verdict |
|---|---|
| Gate system | Clean, keep as-is |
| Locking | Solid, keep as-is |
| Queue storage | Needs structured backing store (JSON) |
| Task state machine | Missing entirely, critical gap |
| Task scoring | Over-engineered by ~3x, simplify to 3 factors |
| Preflight | God function, needs separation of concerns |
| Postflight | Too many optional recording steps inline |
| Failure handling | No retry tracking, no backoff — must fix |
| Observability | No queue health metrics — add stats() |

**Bottom line**: The current architecture works because the queue is small and execution is serialized. It will not scale gracefully if queue size grows, execution becomes concurrent, or failure rates increase. The recommended vNext preserves what works (gate, locks, daily cap) while adding the missing structural foundation (state machine, failure tracking, structured store) and removing accidental complexity (9-factor scoring, cognitive metaphors in the scheduler).
