# Spine Migration Phase 6 Execution Report: Wiki Subsystem Consolidation

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: SPINE_MIGRATION_PLAN.md, Phase 6
**Scope**: Organize 12 root-level wiki_* scripts into a proper subsystem. Extract shared library logic into spine (`clarvis/wiki/`). Move operational scripts to `scripts/wiki/`. Remove dead scripts.

---

## Prior Phase Verification

| Phase | Claim | Verified |
|-------|-------|----------|
| Phase 0 | Dead code removal of `brain_mem/lite_brain.py`, `brain_mem/cognitive_workspace.py` | DONE. Files no longer exist (cleaned since Phase 5). |
| Phase 1 | brain_mem/ thin wrappers deleted | YES. Zero `from brain_mem.` imports remain. |
| Phase 2 | cognition/ stubs and metrics/ wrappers deleted | YES. Zero legacy imports remain. |
| Phase 3 | queue_writer wrapper deleted, all callers migrated | YES. Zero `from queue_writer import` imports remain. |
| Phase 4 | hooks/ library extraction (obligations, workspace_broadcast, soar_engine) | YES. Zero legacy imports remain. |
| Phase 5 | tools/ library extraction (prompt_builder, prompt_optimizer, context_compressor) | YES. Zero legacy imports remain (context_compressor.py itself kept as orchestration layer). |

---

## Plan Corrections

The migration plan's dead code analysis for Phase 6 was **partially wrong**:

| Script | Plan said | Actual status | Action taken |
|--------|-----------|---------------|--------------|
| `wiki_eval.py` | "no callers, no cron" — delete | Has CLI + test file (`test_wiki_eval_suite.py`, 44 import sites). Operator evaluation tool. | **Kept. Moved to `scripts/wiki/`.** |
| `wiki_render.py` | "no callers, no cron" — delete | Has CLI + test file (`test_wiki_render.py`, 9 import sites). Rendering tool. | **Kept. Moved to `scripts/wiki/`.** |
| `wiki_maintenance.py` | "says 'for cron' but never wired" — delete | **ACTIVELY USED** by `clarvis wiki maintenance` CLI command. Called via subprocess by `cli_wiki.py`. | **Kept. Moved to `scripts/wiki/`.** |
| `wiki_index.py` | "no callers, no cron" — delete | **ACTIVELY USED** by `clarvis wiki rebuild-index` CLI command AND called via subprocess by `wiki_maintenance.py`. | **Kept. Moved to `scripts/wiki/`.** |

Per the decision framework: "if it has a `if __name__` block with useful CLI, it may be an operator tool even with zero automated callers." All four scripts have useful CLIs and/or active callers. None were deleted.

The plan also listed `wiki_retrieval.py` as a spine extraction candidate (1 caller). Per the "2+ callers" threshold, it does NOT qualify. Kept as operational script.

---

## Changes Made

### 6.1 Spine Module: `clarvis/wiki/canonical.py` — Library Extraction

`scripts/wiki_canonical.py` was 735 lines of library logic + CLI, imported by 2 wiki scripts and 1 test file.

**Actions:**
- Created `clarvis/wiki/__init__.py` — exports from canonical module.
- Created `clarvis/wiki/canonical.py` (spine module, 508 LOC) containing all library logic:
  - `_normalize`, `_slugify`, `_trigrams`, `_trigram_similarity` — text normalization
  - `_parse_frontmatter` — shared YAML frontmatter parser (duplicated across 4+ wiki scripts)
  - `CanonicalResolver` class — full alias index, resolve, suggest, find_duplicates, add_alias, create_redirect, merge_pages, _update_backlinks
  - `_extract_section`, `_clean_empty_aliases` — helpers
  - `get_resolver`, `resolve_canonical`, `find_duplicates` — public API
  - `TYPE_DIR_MAP`, `WORKSPACE`, `KNOWLEDGE`, `WIKI_DIR` — constants
- Converted `scripts/wiki/wiki_canonical.py` to thin CLI wrapper (134 LOC, down from 735). Imports all logic from spine.

**Python callers updated (spine imports):**

| File | Old Import | New Import |
|------|-----------|------------|
| `scripts/wiki/wiki_compile.py:24-28` | `from wiki_canonical import CanonicalResolver, get_resolver` (try/except + sys.path) | `from clarvis.wiki.canonical import CanonicalResolver, get_resolver` |
| `scripts/wiki/wiki_compile.py:621` | `from wiki_canonical import _trigram_similarity` | `from clarvis.wiki.canonical import _trigram_similarity` |
| `scripts/wiki/wiki_query.py:28-41` | `sys.path + from wiki_canonical import CanonicalResolver, _slugify, _normalize` (with fallback defs) | `from clarvis.wiki.canonical import CanonicalResolver, _slugify, _normalize` |
| `tests/test_wiki_canonical.py:8-13` | `sys.path.insert(...scripts) + from wiki_canonical import (...)` | `from clarvis.wiki.canonical import (...)` |

### 6.2 Directory Reorganization: scripts/ → scripts/wiki/

All 12 wiki scripts moved from `scripts/` root to `scripts/wiki/` via `git mv`:

| Script | Purpose | Role |
|--------|---------|------|
| `wiki_canonical.py` | Canonical resolution CLI | Thin CLI wrapper (library in spine) |
| `wiki_ingest.py` | Source ingestion pipeline | CLI tool + library (called by cli_wiki, wiki_backfill) |
| `wiki_compile.py` | Raw → wiki page promotion | CLI tool + library (called by cli_wiki, wiki_ingest, wiki_backfill) |
| `wiki_query.py` | Question answering from wiki | CLI tool + library (called by cli_wiki, wiki_render) |
| `wiki_lint.py` | Wiki health checks | CLI tool + library (called by cli_wiki, wiki_maintenance) |
| `wiki_index.py` | Index page generation | CLI tool (called by cli_wiki, wiki_maintenance) |
| `wiki_brain_sync.py` | Wiki → ClarvisDB sync | CLI tool + library (called by cli_wiki, wiki_backfill) |
| `wiki_backfill.py` | Corpus backfill | CLI tool (called by cli_wiki) |
| `wiki_maintenance.py` | Autonomous maintenance jobs | CLI tool (called by cli_wiki) |
| `wiki_retrieval.py` | Wiki-first retrieval bridge | CLI tool + library (called by wiki_eval) |
| `wiki_eval.py` | Retrieval evaluation suite | CLI + test tool |
| `wiki_render.py` | Output renderers (markdown, memo, plan, slides) | CLI + test tool |

### 6.3 Caller Path Updates

**CLI gateway (`clarvis/cli_wiki.py`):**
- Changed `SCRIPTS = .../scripts` → `SCRIPTS = .../scripts/wiki` (1 line). All 15 `_run()` calls now resolve to `scripts/wiki/wiki_*.py`.

**Inter-wiki sys.path fixes (3 scripts):**
| File | Old sys.path | New sys.path |
|------|-------------|--------------|
| `scripts/wiki/wiki_maintenance.py:44` | `str(WORKSPACE / "scripts")` | `str(Path(__file__).resolve().parent)` |
| `scripts/wiki/wiki_eval.py:31` | `str(WORKSPACE / "scripts")` | `str(Path(__file__).resolve().parent)` |
| `scripts/wiki/wiki_backfill.py:194,234,241` | `str(WORKSPACE / "scripts")` (3 sites) | `str(Path(__file__).resolve().parent)` |

**Subprocess path fixes (`wiki_maintenance.py`):**
| Line | Old Path | New Path |
|------|---------|----------|
| 280 | `WORKSPACE / "scripts" / "wiki_ingest.py"` | `WORKSPACE / "scripts" / "wiki" / "wiki_ingest.py"` |
| 311 | `WORKSPACE / "scripts" / "wiki_index.py"` | `WORKSPACE / "scripts" / "wiki" / "wiki_index.py"` |

**Test file sys.path fixes:**
| File | Old Path | New Path |
|------|---------|----------|
| `tests/test_wiki_render.py:7` | `...parent / "scripts"` | `...parent / "scripts" / "wiki"` |
| `tests/test_wiki_eval_suite.py:20` | `WORKSPACE / "scripts"` | `WORKSPACE / "scripts" / "wiki"` |

**Unchanged (already correct after move):**
- `scripts/wiki/wiki_render.py:38` — `Path(__file__).parent` resolves to `scripts/wiki/` ✓
- `scripts/wiki/wiki_ingest.py:1148` — `Path(__file__).parent` resolves to `scripts/wiki/` ✓
- `scripts/wiki/wiki_brain_sync.py:38` — `str(WORKSPACE)` for clarvis.brain import ✓
- `scripts/wiki/wiki_retrieval.py:33` — `str(WORKSPACE)` for clarvis.brain import ✓

---

## Verification

| Check | Result |
|-------|--------|
| `from clarvis.wiki.canonical import CanonicalResolver` | OK |
| `from clarvis.wiki import CanonicalResolver, get_resolver` | OK |
| `grep -r "from wiki_canonical import" *.py` | **0 matches** (zero legacy imports) |
| `grep -r "scripts/wiki_.*\.py" *.py` | **0 matches** (no stale root-level paths) |
| `python3 scripts/wiki/wiki_canonical.py --help` | OK (CLI wrapper works) |
| `python3 -m clarvis wiki status` | OK (19 pages, all sections listed) |
| `python3 -m pytest tests/test_wiki_canonical.py -v` | **24 passed** |
| `python3 -m pytest tests/test_wiki_render.py -v` | **21 passed** |
| `python3 -m pytest tests/test_wiki_eval_suite.py -v` | **44 passed** |
| `python3 -m pytest tests/test_critical_paths.py -v` | **47 passed** |
| `python3 -m pytest tests/test_cost_tracker.py tests/test_cost_optimizer.py tests/test_metacognition.py tests/test_prompt_route_golden.py tests/test_queue_writer_mode_gate.py -v` | **109 passed** |
| **Total tests** | **245 passed, 0 failures** |

---

## Files Changed

| File | Change |
|------|--------|
| `clarvis/wiki/__init__.py` | **CREATED** (spine module init, 28 LOC) |
| `clarvis/wiki/canonical.py` | **CREATED** (spine module, 508 LOC) |
| `scripts/wiki/wiki_canonical.py` | **REWRITTEN** to thin CLI wrapper (134 LOC, down from 735) |
| `scripts/wiki/wiki_compile.py` | 3 import sites updated (wiki_canonical → spine) |
| `scripts/wiki/wiki_query.py` | 1 import block replaced (try/except + sys.path + fallback → spine import) |
| `scripts/wiki/wiki_maintenance.py` | sys.path fix + 2 subprocess path fixes |
| `scripts/wiki/wiki_eval.py` | sys.path fix |
| `scripts/wiki/wiki_backfill.py` | 3 sys.path fixes |
| `scripts/wiki/wiki_ingest.py` | Error message path fix |
| `clarvis/cli_wiki.py` | SCRIPTS path updated to `scripts/wiki/` |
| `tests/test_wiki_canonical.py` | Import updated to spine |
| `tests/test_wiki_render.py` | sys.path updated |
| `tests/test_wiki_eval_suite.py` | sys.path updated |
| All 12 `scripts/wiki_*.py` | **git mv** to `scripts/wiki/wiki_*.py` |

## What Was NOT Done

| Item | Why |
|------|-----|
| `wiki_eval.py` deletion | Plan said "dead" but has useful CLI + test coverage (44 test sites). Operator tool. |
| `wiki_render.py` deletion | Plan said "dead" but has useful CLI + test coverage (9 test sites). Operator tool. |
| `wiki_maintenance.py` deletion | Plan said "dead" but **actively called** by `clarvis wiki maintenance` CLI. |
| `wiki_index.py` deletion | Plan said "dead" but **actively called** by `clarvis wiki rebuild-index` CLI + wiki_maintenance subprocess. |
| `wiki_retrieval.py` spine extraction | Only 1 caller (wiki_eval). Below 2+ threshold. |
| `store.py` creation | Plan mentioned "shared storage abstractions" but no concrete existing code to extract. |
| Deduplication of `_parse_frontmatter` across wiki scripts | wiki_compile, wiki_brain_sync, wiki_index, wiki_query all have local copies. The canonical version is now in the spine, but forcing all scripts to use it would mean adding spine imports to scripts that currently don't need them. Can be done incrementally in Phase 7 (sys.path elimination). |

## Acceptance Criteria (from plan)

- "`wiki_canonical` importable as `from clarvis.wiki import canonical`" — **YES**. `from clarvis.wiki.canonical import CanonicalResolver` works. `from clarvis.wiki import CanonicalResolver` also works.
- "Root-level wiki_* scripts moved to `scripts/wiki/`" — **YES**. All 12 scripts moved via `git mv`. Zero wiki_*.py files remain in `scripts/` root.
- "Dead scripts removed" — **PARTIALLY**. Zero scripts were dead upon verification. The plan's dead code list was incorrect for all 4 entries. See "Plan Corrections" section above.

## Payoff

- Wiki subsystem has clear ownership: `clarvis/wiki/` for library logic, `scripts/wiki/` for operational scripts.
- 601 LOC moved from scripts to spine (735 → 134 CLI wrapper).
- 4 import sites across 3 Python files migrated from `sys.path`-dependent imports to clean spine imports.
- 6 sys.path hacks updated to use `Path(__file__).parent` instead of hardcoded `WORKSPACE / "scripts"`.
- 2 subprocess paths corrected for the new directory structure.
- Zero root-level wiki script sprawl.

## What Still Remains After Phase 6

| Item | Phase |
|------|-------|
| 17 `sys.path` hacks within spine modules (`clarvis/*.py`) | Phase 7 |
| Duplicated `_parse_frontmatter` in wiki_compile, wiki_brain_sync, wiki_index, wiki_query | Phase 7 (can import from spine during sys.path cleanup) |
| Scripts that import via `sys.path.insert(0, scripts/)` for non-wiki modules | Phase 8 |
| Doc references update | Phase 9 |
