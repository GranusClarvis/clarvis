# Research Pipeline Audit — 2026-04-07

## Purpose

Map the full lifecycle of a research topic from discovery to archive. Identify every place a repeat can slip through.

---

## Lifecycle Stages

### Stage 1: Discovery (topic enters the system)

**Entry points:**
1. **cron_research.sh discovery fallback** — When no research tasks exist in QUEUE.md, Claude Code proposes 3-5 topics. Adds via `queue_writer.py add "Research: [topic]" --priority P1 --source research_discovery`.
2. **cron_autonomous.sh / cron_evolution.sh** — May propose research tasks with `[RESEARCH_*]` tags.
3. **Manual/CLI** — Operator adds directly to QUEUE.md or via `python3 -m clarvis queue add`.

**Dedup checks at this stage:**
- Discovery prompt includes `ALREADY_RESEARCHED` list built from 3 sources:
  - `data/research_ingested.json` (filename-based keys)
  - `memory/evolution/QUEUE_ARCHIVE.md` (completed `[x]` items matching research keywords)
  - `data/research_topic_registry.json` (canonical topics with `research_count >= 1`)
- `queue_writer.py add_task()` calls `_is_research_topic_completed()` → `RepeatClassifier.is_repeat()` for research-flavored tasks from auto-sources.

**Gap 1: Prompt-level dedup is advisory.** Claude Code sees the "already researched" list but may still propose similar topics with different wording. The registry uses word-overlap (F1 score >= 0.45) which can miss rephrased topics.

**Gap 2: Discovery fallback only runs when auto-replenish is enabled** (`RESEARCH_AUTO_REPLENISH=1`). Currently off by default — low risk but worth noting.

### Stage 2: Queue Injection

**What happens:** Task text lands in QUEUE.md under appropriate priority section.

**Dedup checks:**
- `add_task()` in `clarvis/queue/writer.py`:
  - Word-overlap dedup against existing QUEUE.md items (threshold ~0.6)
  - Checks sidecar `data/queue_state.json` for succeeded-but-not-yet-archived tasks
  - `_is_research_topic_completed()` calls `RepeatClassifier` which consults the topic registry
- Manual sources (`manual`, `cli`, `user`) bypass the registry lock — this is intentional (explicit reopen path).

**Gap 3: The RepeatClassifier and TopicRegistry use different matching logic.** RepeatClassifier imports word_overlap from research_novelty but adds scope comparison. TopicRegistry.classify() is the primary novelty check. Two separate classification paths exist that could disagree.

### Stage 3: Pre-Select Novelty Gate

**What happens:** `cron_research.sh` picks the first unchecked research task from QUEUE.md. Before spawning Claude Code, it runs:
```
python3 research_novelty.py classify "$RESEARCH_TASK"
```

**Outcomes:**
- Exit 0 (NEW/REFINEMENT) → proceed to execution
- Exit 1 (ALREADY_KNOWN) → mark `[x]` with `SKIP:duplicate` annotation, write to digest, exit

**Gap 4: Task selection regex is broad.** Matches `research:`, `bundle`, `study`, `paper`, `explore`, `investigate` — could pick non-research tasks. Low severity since novelty gate filters.

**~~Gap 5~~ FIXED (2026-04-07):** `_normalize()` now strips ALL bracket tags via `[^\]]*]`, plus standalone dates, queue task IDs (underscore-containing), .md extensions, and path prefixes. 8 noise types stripped deterministically.

### Stage 4: Execution

**What happens:** Claude Code runs with a structured prompt for 1800s max. Writes artifacts to `memory/research/runs/YYYY-MM-DD-HHMMSS/`.

**Outputs:**
- Markdown artifact(s) in the run directory
- Brain memories via `brain.py remember` (called by Claude inside the session)
- Structured `RESEARCH_RESULT` block in stdout
- Queue items added via `queue_writer.py add` (if DECISION=APPLY)

**Gap 6: Claude Code may also store brain memories directly** via `brain.py remember`. These are NOT tracked by the topic registry's `memory_count` field. The registry only gets updated during Stage 5 ingestion.

### Stage 5: Post-Execute Novelty Gate + Ingestion

**What happens (on exit 0):**
1. Stray files in `memory/research/` root (written despite instructions) are moved to run dir
2. Each `.md` file in run dir is evaluated: `research_novelty.py evaluate-file`
3. Files passing novelty → ingested via `brain.py ingest-research`
4. After ingestion → registered via `research_novelty.py register`

**`brain.py ingest-research` does:**
- Splits markdown by `## ` headers
- Stores each section in `clarvis-learnings` collection (importance 0.8-0.85)
- Tracks file hash + metadata in `data/research_ingested.json`
- Moves file to `memory/research/ingested/`

**`research_novelty.py register` does:**
- Updates or creates entry in `data/research_topic_registry.json`
- Increments `research_count`, updates `last_researched`
- Adds source filename to `source_files` list

**~~Gap 7~~ FIXED (2026-04-07):** `cron_research.sh` now captures `ingest-research` output, extracts actual memory count via `grep -oP`, and passes it to `register --memories $REAL_MEM_COUNT`.

**Gap 8: If `evaluate-file` fails (exit 1), the file stays in the run dir but is never ingested or registered.** It's effectively orphaned — not tracked anywhere as "seen but rejected."

### Stage 6: Lesson Recording

**What happens:** After execution, structured output is parsed and recorded in `data/research_lessons.jsonl` via `research_lesson_store.py`.

**Fields:** topic, decision, findings (500 chars), queue_items, outcome, timestamp.

**Used for:** Injected into future research prompts as cross-run learning.

**No gap here** — lessons are append-only and don't affect dedup.

### Stage 7: Queue Completion + Archive

**What happens:**
- `cron_research.sh` calls `mark_task_complete()` + `archive_completed()` deterministically (does not rely on Claude doing it)
- Marks `[x]` in QUEUE.md with UTC timestamp annotation
- `archive_completed()` moves checked items to `QUEUE_ARCHIVE.md`
- V2 sidecar run record is ended with success/failure

**Gap 9: `mark_task_complete` matches by word overlap (0.6 threshold).** If the task text in QUEUE.md was edited between selection and completion, matching may fail → `Queue mark result: False`. The task remains unchecked, gets picked again next run.

### Stage 8: Closed State

A topic is "done" when:
- `research_topic_registry.json` has `research_count >= 1` (or >= 3 for hard block)
- `data/research_ingested.json` has the file hash
- `QUEUE_ARCHIVE.md` has the `[x]` entry
- Sidecar `data/queue_state.json` has `state: succeeded`

**Gap 10: No single field says "this topic family is done."** Four independent stores must agree. A topic can be:
- Done in registry but not archived (queue mark failed)
- Archived but not in registry (ingestion was skipped by novelty gate)
- In ingested.json but not in registry (registered before registry existed)
- In sidecar as succeeded but not in archive (archive_completed hasn't run)

---

## Repeat Slip-Through Vectors (Summary)

| # | Vector | Severity | Where |
|---|--------|----------|-------|
| 1 | Rephrased topic bypasses word-overlap dedup | **HIGH** | Discovery, Queue injection |
| 2 | ~~Tags without dates not stripped by _normalize~~ **FIXED** | ~~MEDIUM~~ | Pre-select gate |
| 3 | ~~memory_count is hardcoded 1, not actual count~~ **FIXED** | ~~LOW~~ | Registry accuracy |
| 4 | Queue mark fails on text mismatch → re-selection | **HIGH** | Queue completion |
| 5 | Four independent state stores with no reconciliation | **HIGH** | Closed state |
| 6 | Two classification paths (TopicRegistry vs RepeatClassifier) | MEDIUM | Injection vs pre-select |
| 7 | Orphaned rejected files not tracked | LOW | Post-execute gate |
| 8 | Claude-stored memories not counted in registry | LOW | Execution |

---

## State Stores Inventory

| Store | File | What It Tracks | Written By |
|-------|------|----------------|------------|
| Topic Registry | `data/research_topic_registry.json` | Canonical topics, aliases, research_count, memory_count | `research_novelty.py register` |
| Ingestion Tracker | `data/research_ingested.json` | File hashes, ingestion timestamps per filename | `brain.py ingest-research` |
| Lesson Store | `data/research_lessons.jsonl` | Cross-run outcomes (topic, decision, findings) | `research_lesson_store.py` |
| Queue Sidecar | `data/queue_state.json` | Runtime state machine (pending/running/succeeded/failed) | `clarvis/queue/engine.py` |
| Queue Archive | `memory/evolution/QUEUE_ARCHIVE.md` | Completed task text with timestamps | `queue_writer.py archive_completed` |
| QUEUE.md | `memory/evolution/QUEUE.md` | Active task list with `[ ]`/`[x]` state | Multiple writers |

---

## Recommendations

1. **Canonical Topic ID** — Replace fuzzy name matching with stable slugs. Each registry entry gets a deterministic `topic_id` derived from canonical_name. All state stores reference this ID.

2. **Single source of truth** — The topic registry should be THE authority on whether a topic family is done. Other stores (ingested.json, archive, sidecar) are evidence but the registry owns the verdict.

3. ~~**Fix _normalize to strip all bracket tags**~~ **DONE** — Now strips 8 noise types deterministically.

4. ~~**Fix memory_count**~~ **DONE** — `cron_research.sh` now captures and passes real count.

5. **Fix queue mark reliability** — Use task tag `[RESEARCH_*]` for matching instead of word overlap on full text.
