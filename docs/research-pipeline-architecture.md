# Research Pipeline Architecture

**Date**: 2026-03-27
**Status**: Implemented

## Problem

The research pipeline was re-ingesting duplicate topics (notably Phi/IIT, consciousness architectures, retrieval optimization). Root causes:

1. **Task selection too loose** — no check whether a topic had already been researched
2. **Artifact ownership too loose** — Claude Code wrote to shared `memory/research/` root; `brain.py ingest-research` swept all `*.md` files there
3. **Ingestion gate too loose** — hash-based dedup only caught exact byte matches, not semantic duplicates

Result: 10+ topics were researched 3-7x each, producing 696+ brain memories with heavy redundancy.

## Solution: 3-Stage Novelty Pipeline

```
QUEUE.md task
    │
    ▼
┌─────────────────────────────┐
│ STAGE 1: PRE-SELECT GATE    │
│ research_novelty.py classify │
│                             │
│ NEW → proceed               │
│ REFINEMENT → proceed        │
│ ALREADY_KNOWN → skip+mark   │
└─────────┬───────────────────┘
          │ (proceed)
          ▼
┌─────────────────────────────┐
│ STAGE 2: EXECUTE            │
│ Claude Code runs research   │
│                             │
│ Artifacts → runs/<run-id>/  │
│ (scoped directory, not root)│
└─────────┬───────────────────┘
          │
          ▼
┌─────────────────────────────┐
│ STAGE 3: POST-EXECUTE GATE  │
│ Per-file novelty evaluation │
│                             │
│ NEW/REFINEMENT → ingest     │
│ ALREADY_KNOWN → skip        │
│                             │
│ + Register topic in registry│
└─────────────────────────────┘
```

## Key Components

### `scripts/research_novelty.py`

Canonical topic registry + novelty classification engine.

- **Registry**: `data/research_topic_registry.json` — maps canonical topic names to metadata (aliases, source files, research count, memory count, dates)
- **Classification**: Word-overlap similarity against registry entries. Thresholds:
  - `SIMILARITY_THRESHOLD = 0.45` — word overlap above this = same topic
  - `REFINEMENT_AGE_DAYS = 14` — older than this → REFINEMENT instead of ALREADY_KNOWN
  - `REFINEMENT_MIN_MEMORIES = 3` — fewer stored memories → REFINEMENT
  - `MAX_RESEARCH_COUNT = 3` — hard block regardless of age
- **File evaluation**: Also checks content novelty (>40% new words → upgrade to REFINEMENT)
- **CLI**: `classify`, `evaluate-file`, `register`, `build`, `list`, `stats`
- **Exit codes**: 0 = proceed (NEW/REFINEMENT), 1 = skip (ALREADY_KNOWN)

### `scripts/cron_research.sh` (modified)

Three-stage pipeline replacing the previous single-stage execute-and-sweep:

1. **Pre-select gate**: Calls `research_novelty.py classify` on the selected task. ALREADY_KNOWN tasks are marked complete with `SKIP:duplicate` annotation and skipped.
2. **Scoped artifacts**: Creates `memory/research/runs/<YYYY-MM-DD-HHMMSS>/` for each run. Claude Code is instructed to write there, not to the root.
3. **Post-execute gate**: Evaluates each output file's novelty before ingestion. Only NEW/REFINEMENT files are ingested via `brain.py ingest-research <file>`. Topics are registered in the novelty registry after ingestion.

Stray files written to `memory/research/` root (Claude Code ignoring instructions) are automatically moved into the run dir for unified processing.

### `scripts/brain.py` ingest-research (modified)

- Root sweep (`memory/research/*.md`) is deprecated with a warning
- Callers should pass specific file paths: `brain.py ingest-research <file>`
- Hash-based dedup still works as a secondary safety net

## Data Files

| File | Purpose |
|------|---------|
| `data/research_topic_registry.json` | Canonical topic registry (80 topics, built from existing data) |
| `data/research_ingested.json` | File-level ingestion tracker (hash dedup) |
| `data/research_lessons.jsonl` | Cross-run lesson tracking |
| `data/research_dispositions.jsonl` | Research-to-queue disposition audit log |

## Verification

```bash
# Check registry health
python3 scripts/research_novelty.py stats

# Test classification of known duplicate
python3 scripts/research_novelty.py classify "Phi/IIT consciousness"
# Expected: ALREADY_KNOWN or REFINEMENT (if old enough)

# Test classification of novel topic
python3 scripts/research_novelty.py classify "Quantum error correction for agents"
# Expected: NEW

# List over-researched topics
python3 scripts/research_novelty.py list | head -20

# Rebuild registry from scratch (idempotent)
python3 scripts/research_novelty.py build
```

## Remaining Risks

1. **Word overlap is not semantic**: Two topics with different words but same meaning could slip through (e.g., "IIT" vs "integrated information theory"). Mitigated by aliases in the registry, but not perfect. A future improvement could use brain embedding similarity.
2. **Claude Code may still write to wrong directory**: The prompt instructs it to use the run dir, but LLMs don't always follow instructions. The stray-file sweep mitigates this.
3. **Existing duplicates in brain**: The 696 memories from prior duplicate ingestion are still in the brain. A separate cleanup pass (brain hygiene dedup) would handle these.
4. **Discovery fallback**: The discovery path still relies on Claude Code to not suggest already-researched topics. The `ALREADY_RESEARCHED` list in the prompt helps, but the novelty registry could be injected there too in a future pass.
