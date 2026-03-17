# SWE-Pruner + SParC-RAG: Context Pruning & Multi-Agent RAG for Context Relevance

**Date**: 2026-03-17
**Papers**: arXiv:2601.16746 (SWE-Pruner), arXiv:2602.00083 (SParC-RAG)
**Target metric**: Context Relevance (0.387 → 0.75)

## SWE-Pruner — Self-Adaptive Context Pruning for Coding Agents

**Core idea**: Goal-conditioned line-level pruning using a 0.6B neural skimmer trained with CRF loss.

**Key results**:
- 23–54% token reduction on SWE-Bench Verified while maintaining/improving success rates
- Up to 14.84x compression on single-turn tasks (LongCodeQA)
- 87.3% AST correctness (vs. 0.29% for token-level pruning)
- 18–26% fewer agent interaction rounds (more decisive reasoning)

**Methodology**:
1. Agent formulates a goal hint (natural language question about current information need)
2. 0.6B skimmer scores context tokens conditioned on goal hint
3. Scores aggregated to line level, threshold τ=0.5 applied
4. CRF loss (not BCE) captures sequential dependencies between retain/prune decisions
5. Training data: 61K synthetic samples from GitHub Code 2025, 9 task types, LLM-as-Judge filtering

**Why CRF > BCE**: CRF models transition probabilities between adjacent lines, so the model learns that neighboring lines should have correlated retain/prune decisions. This preserves code structure without explicit AST parsing.

## SParC-RAG — Adaptive Sequential-Parallel Scaling with Context Management

**Core idea**: Multi-agent RAG with three specialized agents coordinating retrieval rounds.

**Key results**:
- +6.2 F1 on multi-hop QA after DPO fine-tuning
- 52.2% lower token cost vs. prior best methods
- 27.4% less document overlap (better diversity)

**Three agents**:
1. **Query Rewriter**: One-to-many generation for parallel diversity (reduces Jaccard overlap)
2. **Answer Evaluator**: Weighted DPO with λ=2 for conservative stopping (reduces wrong-stop by 11–15pp)
3. **Context Manager**: Incremental minimal updates + cross-branch evidence merge

**Context Manager details**:
- Within-branch: `m(t) ← MemUpdate(q₀, q(t), m(t-1), r(t), a(t))` — query-focused incremental update
- Cross-branch: SelectBest identifies best path, ContextMerge integrates complementary evidence
- Prevents "context contamination" — uncontrolled accumulation that overwhelms attention

## Clarvis Application Ideas

### 1. Intra-Section Line-Level Pruning (from SWE-Pruner)
Current DyCP operates at section granularity. SWE-Pruner shows line-level pruning within sections significantly improves relevance. **Implementation**: After assembling each section, score individual lines by task-token overlap (zero-LLM goal hint analog). Drop lines below threshold while preserving structural neighbors (CRF-inspired: if line N is kept, bias toward keeping N±1). Applies to: `related_tasks`, `episodes`, `brain_context`, `working_memory`.

### 2. Enriched Related Tasks (from SParC-RAG Context Manager)
The `related_tasks` section scores 0.0 containment because it contains queue titles that share no tokens with Claude Code output. **Fix**: Enrich each related task with actionable context — file paths, function names, concrete overlap description extracted from the task text. This mirrors SParC-RAG's selective integration: include only evidence that connects to the current task.

### 3. Evidence Consolidation for Multi-Source Sections (from SParC-RAG)
Brain search returns multiple results that may be redundant. Instead of concatenating top-N, consolidate: select best result, merge complementary information from others. Reduces noise, improves containment.

### 4. Goal-Hint Generation for Context Assembly
Before assembling the brief, formulate an explicit goal hint from the task description (like SWE-Pruner's `context_focus_question`). Use this hint to condition ALL retrieval — brain search, episode recall, related task selection. Currently these use the raw task text; a distilled goal hint would be more focused.

### 5. Sequential Dependency in Pruning Decisions
CRF insight: don't prune isolated lines — group consecutive low-relevance lines into blocks and prune/keep as units. This preserves structural coherence (code snippets, multi-line learnings) without explicit parsing.

## Priority for Implementation

1. **Related tasks enrichment** (highest ROI — addresses 0.0 containment directly, no model needed)
2. **Intra-section line-level pruning** (addresses noise within kept sections)
3. **Goal hint generation** (improves all retrieval quality upstream)
4. **Evidence consolidation** (diminishing returns with current brain size)

## Connection to Existing Work

- DyCP (arXiv:2601.07994) — already implemented in `assembly.py`. SWE-Pruner extends this from section→line level.
- A-RAG hierarchical retrieval — SParC-RAG offers a complementary multi-round approach.
- MacRAG multi-scale — SParC-RAG's parallel branches are similar but with explicit coordination.
- ACON compression — SWE-Pruner's line-level approach is more principled for code contexts.
