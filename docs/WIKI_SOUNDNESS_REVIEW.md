# Wiki Subsystem Soundness Review

**Date:** 2026-04-10
**Reviewer:** Clarvis (Claude Code Opus, BUILD session)
**Scope:** Full wiki subsystem — 13 scripts, 1 spine module, 3 test files, ~7700 LOC

## Executive Summary

The wiki subsystem has **sound architecture** (three-layer: raw → wiki → brain) but **fails its core value proposition**: wiki-assisted retrieval is measurably **worse** than naive baseline on every dimension. The eval suite proves this. The system adds 17x latency overhead for lower coverage, lower citation quality, and lower usefulness. Until the retrieval path is fixed, the wiki is an expensive write-only knowledge store.

## Eval Evidence (2026-04-08, 15 gold questions)

| Dimension        | Wiki   | Baseline | Delta    | Verdict       |
|-----------------|--------|----------|----------|---------------|
| Citation quality | 0.650  | 0.866    | **-0.22**| Wiki loses    |
| Coverage         | 0.667  | 0.906    | **-0.24**| Wiki loses    |
| Usefulness       | 0.739  | 0.906    | **-0.17**| Wiki loses    |
| Consistency      | 1.000  | n/a      | —        | Good          |
| Latency avg (ms) | 227    | 13       | **-214** | Wiki 17x slower|

**5 of 15 queries return zero wiki hits** (WE02, WE04, WE05, WE13, WE15), falling to broad fallback. The baseline finds relevant content for all of them.

## Root Cause Analysis

### Why wiki retrieval loses to baseline

1. **Post-hoc filtering defeats semantic search.** `wiki_retrieve()` calls `brain.recall(query, n=15, collections=["clarvis-learnings"])` then filters results by `source=wiki/*` prefix. The baseline searches ALL collections with no filter. Wiki path sees fewer candidates → worse recall.

2. **Missing pages.** 5 gold queries target pages not synced to the brain (bundle-b-predictive-processing, world-models-from-neural-dreaming, bundle-m-swarm, bundle-g-philosophy, clarvis-self). These pages either don't exist or weren't synced. The wiki cannot answer questions about content it doesn't have.

3. **No structured retrieval.** The wiki has rich metadata (slug, type, tags, aliases, confidence) but retrieval uses only vector similarity — the same mechanism as baseline. There's no tag-filtered search, no slug lookup, no keyword/BM25 path. The structured metadata is write-only.

4. **Graph expansion is dead weight.** Graph neighbors only expand from wiki hits. Zero wiki hits → zero expansion → no value from graph. When wiki hits exist, neighbors are noise (entity stubs like `entity_person_...` that have no content).

5. **Latency overhead without payoff.** 227ms vs 13ms: the extra time goes to post-hoc filtering, disk reads for page enrichment, graph queries, and raw source loading — none of which improve results.

## Component-by-Component Verdict

### KEEP (sound, worth maintaining)

| Component | File | Reason |
|-----------|------|--------|
| Three-layer model | architecture | Raw → wiki → brain is the right separation of concerns |
| Source registry | `knowledge/logs/sources.jsonl` | Append-only provenance with SHA256 dedup — proper audit trail |
| Canonical resolver | `clarvis/wiki/canonical.py` | Dedup, alias resolution, redirect chains — necessary for correctness |
| Page schema + templates | `knowledge/schema/` | YAML frontmatter with required sources, confidence, status — good structure |
| Eval suite | `wiki_eval.py` | 5-dimension comparison against baseline — the very thing that caught the failure |
| Lint engine | `wiki_lint.py` | Orphan/broken-link/stale detection — essential maintenance |
| Tests | `test_wiki_canonical.py`, `test_wiki_eval_suite.py`, `test_wiki_render.py` | Coverage for core logic |

### FIX (broken or underperforming — fix before declaring wiki operational)

| Issue | File(s) | Fix |
|-------|---------|-----|
| **Retrieval worse than baseline** | `wiki_retrieval.py` | Use `where={"source": {"$contains": "wiki/"}}` in ChromaDB query instead of post-hoc filtering. Add tag-filtered and slug-match paths before semantic search. |
| **5/15 gold queries miss** | `wiki_brain_sync.py` | Run `sync --all` after any page create/update. Wire into wiki_compile output. Ensure all 23 pages are in the brain. |
| **Frontmatter parser duplicated 4+ times** | `wiki_retrieval.py`, `wiki_brain_sync.py`, `wiki_compile.py`, `wiki_lint.py` | Extract to `clarvis.wiki.frontmatter` shared module. Current copies will drift. |
| **Relation extraction is noise** | `wiki_brain_sync.py:97-106` | Regex "supports X" / "contradicts X" matches prose fragments, not wiki slugs. Creates garbage graph edges. Either resolve to actual slugs or remove. |
| **Graph neighbors are stub entities** | `wiki_brain_sync.py:293-299` | Entity IDs like `entity_person_karl_friston` point to nothing in the brain. Edges exist but targets have no content. Either create entity memories or stop creating edges to phantoms. |
| **No maintenance cron** | n/a | `wiki_maintenance.py` exists but has no cron entry. Lint/drift/promote never run autonomously. |
| **budget calculation uses char count not tokens** | `wiki_retrieval.py:277` | `max_tokens` parameter counts characters, not tokens. Misleading name. |

### CUT (decorative, unused, or not worth maintaining)

| Component | File | Lines | Reason |
|-----------|------|-------|--------|
| **Wiki render** | `wiki_render.py` | 668 | Slides/memo/plan rendering has no callers in production. No cron, no hook, no pipeline integration. Pure feature-creep. |
| **Wiki backfill** | `wiki_backfill.py` | 338 | Backfills from `memory/research/ingested/` which doesn't appear to have active content. Dead path. |
| **Auto-generated index pages** | `wiki_index.py` | 499 | Generates recent.md, tags.md, questions.md, orphans.md — markdown navigation pages that no retrieval path reads. Decorative. |
| **Temporal graph edges** | `wiki_brain_sync.py:339-346` | — | Edges like `wiki_X → temporal_2026` serve no retrieval function. No query path traverses them. |
| **Raw source loading in retrieval** | `wiki_retrieval.py:122-137` | — | Loading raw source files during retrieval adds latency. The wiki page already contains the relevant content. Only useful for deep audit, not retrieval. |

## Structural Issues (Not Bugs, But Debt)

1. **Same collection for everything.** Wiki pages go into `clarvis-learnings` alongside episodic and procedural memories. This means wiki content competes with 2800+ other memories in vector search. A dedicated `clarvis-wiki` collection would allow wiki-only queries without post-hoc filtering.

2. **No keyword/BM25 path.** Semantic search alone cannot reliably find pages by title or slug. "What is Global Workspace Theory?" should match the page titled "Global Workspace Theory" by exact title match, not by embedding similarity.

3. **Embedding text is too short.** `_build_summary()` caps at 1500 chars — many wiki pages have 3000+ chars of meaningful content. The embedding represents a fraction of the page.

4. **No incremental sync trigger.** `wiki_compile.py` creates/updates pages but doesn't call `wiki_brain_sync.py`. Sync only happens manually or via (non-existent) cron. Pages can exist in wiki/ for days without being searchable.

## Soundness Checklist

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Source-grounded | **PASS** | Every page requires `sources:` field linking to raw evidence. Provenance chain: raw → page → brain memory. |
| Canonical | **PASS** | `CanonicalResolver` with alias index, fuzzy matching, redirect chains, merge logic. Tested. |
| Updateable | **PASS** | Pages have `updated` field, `## Update History` section, and `sync --changed` path. |
| Retrieval-useful | **FAIL** | Wiki retrieval is measurably worse than baseline on all dimensions. |
| Auditable | **PASS** | `sources.jsonl` (registry), `brain_sync.jsonl` (sync log), `lint-log.md`, `maintenance.log`. |
| Better than naive | **FAIL** | Eval delta is negative on citation (-0.22), coverage (-0.24), usefulness (-0.17). |

## Recommended Fix Priority

1. **P0:** Fix retrieval path (ChromaDB `where` filter, dedicated collection, or title-match pre-filter)
2. **P0:** Sync all existing pages to brain (`wiki_brain_sync.py sync --all`)
3. **P1:** Wire compile → sync (auto-sync after page create/update)
4. **P1:** Add wiki maintenance to cron schedule
5. **P1:** Extract shared frontmatter parser to `clarvis.wiki.frontmatter`
6. **P2:** Cut render, backfill, index generation (save ~1500 LOC of dead code)
7. **P2:** Cut phantom entity edges and temporal edges from graph sync

## Bottom Line

The wiki architecture is sound. The implementation is incomplete. The retrieval path — the only thing that matters for an agent — is broken. Fix retrieval, sync all pages, and wire the pipeline end-to-end. Then re-run the eval. The wiki should beat baseline by at least +0.10 on coverage and usefulness before it's declared operational.
