# Wiki Subsystem — Productization Review

**Date**: 2026-04-10
**Status**: Internal tool with standalone-product potential

## Verdict

The wiki subsystem is currently an **internal tool** purpose-built for Clarvis's knowledge management. It has genuine differentiators that make it more than a naive RAG wrapper, but it is not yet a standalone product — it lacks multi-user support, a web UI, and packaging for external use.

**Recommendation**: Keep developing it as Clarvis's internal knowledge layer. Extract it as a standalone product only if there is external demand, which would require ~2 weeks of packaging work (see "Gap to Product" below).

## What it is today

A **source-grounded, citation-tracked knowledge vault** with:
- Append-only source registry (JSONL) with content-hash deduplication
- Canonical resolution (one page per concept, fuzzy matching, alias/redirect/merge)
- Quality gates (atomicity, citation, substance checks before compilation)
- 4 output renderers (markdown, memo, plan, Marp slides)
- 9-check lint suite with auto-fix
- Obsidian-compatible vault layout for visual graph browsing
- Brain sync (wiki pages indexed in ClarvisDB for retrieval)
- Fail-safe automation hooks (heartbeat postflight, cron maintenance)

## Differentiators vs Generic RAG

| Feature | Generic RAG | Clarvis Wiki |
|---------|-------------|--------------|
| Source tracking | Chunks with metadata | Full raw source preservation + registry |
| Deduplication | Embedding similarity | Content hash + URL + fuzzy title matching |
| Canonical resolution | None | Alias index, redirects, fuzzy merge |
| Citation grounding | Optional | Mandatory — lint enforces every claim cites a source |
| Quality gates | None | Atomicity, citation, substance checks before page creation |
| Confidence tracking | None | Auto-upgraded from source count (low/medium/high) |
| Output formats | Single answer | 4 renderers (answer, memo, plan, slides) |
| Health monitoring | None | 9-check lint, drift detection, maintenance cron |
| Graph browsing | None | Obsidian-compatible vault with backlinks |
| Updateability | Re-embed on change | Incremental: new sources update existing pages |

**Key distinction**: Generic RAG treats documents as disposable context for a single query. The wiki treats sources as permanent evidence that builds a growing, auditable knowledge graph.

## Differentiators vs Hermes/Karpathy Pattern

The "Karpathy pattern" (LLM + vector DB + web search) is a retrieval pipeline. The wiki is a **compilation pipeline**:

1. **Hermes pattern**: User query → embed → retrieve chunks → generate answer → discard context
2. **Clarvis wiki**: Source drop → ingest → deduplicate → compile to canonical page → lint → index → persist. Answers are saved as artifacts, promotable to permanent pages.

The wiki accumulates knowledge over time. A RAG pipeline answers questions but doesn't learn. The wiki does both: it answers questions *and* the answers become part of the knowledge base.

## Gap to Standalone Product

To extract the wiki as a standalone tool, these would be needed:

| Gap | Effort | Notes |
|-----|--------|-------|
| Remove Clarvis dependencies | 3-5 days | Replace `clarvis.brain` with pluggable backend, remove `_script_loader` |
| Packaging (pip install) | 1-2 days | Setup.py/pyproject.toml, entry points |
| Web UI | 5-7 days | Currently CLI-only; Obsidian is the visual layer |
| Multi-user support | 3-5 days | Currently single-operator, no auth |
| LLM-powered compilation | 2-3 days | Current compilation is template-based; LLM would improve quality |
| Documentation | 1-2 days | User guide, API docs |

**Total**: ~15-25 days of focused work.

## What makes it worth keeping (not cutting)

1. **Source grounding is real** — every wiki page traces to raw evidence files
2. **Canonical resolution prevents knowledge rot** — no duplicate pages, aliases merge
3. **Lint catches real problems** — orphans, broken links, uncited claims, stale pages
4. **The operator workflow is dead simple** — drop/ask/promote/render covers 90% of use
5. **It improves retrieval** — wiki-first retrieval outperforms raw embedding search for structured knowledge

## What is decorative (candidates for cutting)

1. **Confidence auto-upgrade** — the low/medium/high bands are too coarse to be actionable
2. **Tag taxonomy enforcement** — 8 categories is rigid; tags should be freeform with suggested conventions
3. **Implementation plan renderer** — template is too generic; better to let the LLM generate plans directly
4. **Brain sync** — duplicates wiki content in ChromaDB; wiki-first retrieval already searches wiki files directly
