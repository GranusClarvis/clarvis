# SWE-EVO & Self-Improving Coding Agents — Research Note

**Date**: 2026-03-09
**Source**: arXiv:2512.18470 (SWE-EVO), arXiv:2504.15228 (SICA), arXiv:2505.22954 (DGM), arXiv:2510.21614 (HGM)
**Task**: RESEARCH_SWE_EVO_LONGITUDINAL

## Summary

SWE-EVO is a benchmark for long-horizon software evolution — not self-modification per se, but it exposes the capability gap that self-improving agents must overcome. Three related systems (SICA, Darwin Gödel Machine, Huxley-Gödel Machine) directly tackle self-modification and provide the longitudinal evaluation angle.

## Key Findings

### SWE-EVO Benchmark
- **48 tasks** from 7 Python projects (Django, scikit-learn, pydantic, etc.)
- Average task: **21 files modified, 610 lines changed, 874 tests**
- Best agent (GPT-5 + SWE-Agent): **20.83% resolution** vs 65% on single-issue SWE-Bench
- Fix Rate metric: partial credit with **zero regression tolerance** (any broken existing test = 0 score)
- Dominant failure mode for strong models: **instruction following** (>60%), not syntax or tooling
- Weaker models fail on tool use, syntax, and getting stuck in loops

### SICA (Self-Improving Coding Agent)
- Agent edits its **own Python source code** across iterations
- SWE-bench: **17% → 53%** over 14 iterations (+36pp)
- Self-modifications: smart diff editors, AST symbol locators, context-sensitive minimization
- **Minimal catastrophic forgetting**: scores stable or improving across all benchmarks
- Validation: independent sub-agent verifier + async LLM overseer + full benchmark re-eval
- Failure modes: **ideation brittleness** (LLM struggles to propose truly novel modifications), **scaffolding plateau** (gains saturate without weight updates)

### Darwin Gödel Machine (DGM)
- Evolutionary archive of agents — parallel lineage exploration
- SWE-bench: **20% → 50%** through self-modification (code editing tools, context management, peer review)
- Avoids local optima via **population diversity** (tree of diverse agents)
- Minimal catastrophic forgetting on diverse benchmarks

### Huxley-Gödel Machine (HGM)
- Key insight: **Metaproductivity-Performance Mismatch** — optimizing for benchmark score ≠ optimizing for improvement potential
- **Clade-Metaproductivity (CMP)**: evaluates lineage quality (aggregate descendant performance) instead of individual performance
- Uses Thompson Sampling to guide exploration toward high-CMP lineages
- Achieves human-level on SWE-bench Lite with fewer CPU hours than DGM

## Clarvis Applications

### 1. Evolution Quality Gating (addresses CRON_OUTPUT_QUALITY_AUDIT)
Clarvis autonomous evolution already mirrors SICA's archive pattern (QUEUE_ARCHIVE.md). Missing piece: **explicit before/after metric comparison per evolution step**. After each autonomous task, compare PI/Phi/brain-stats before vs after. If metrics regress, flag in digest. This is exactly what SICA's benchmark re-evaluation gate does.

### 2. Fix Rate for Partial Credit
Current evolution tasks are binary (done/not done). Adopt SWE-EVO's Fix Rate concept: for multi-step tasks, track what fraction of intended changes landed. This improves CRON_OUTPUT_QUALITY_AUDIT accuracy and helps identify "partially useful" cron slots.

### 3. Ideation Diversity (addresses task selection staleness)
SICA's biggest failure is **ideation brittleness** — the LLM runs out of novel modification ideas. Clarvis shows similar symptoms (repeated task selection, low-value outputs). Countermeasure: add explicit novelty scoring to heartbeat task selection — penalize tasks similar to recent completions. DGM's population diversity approach maps to trying different QUEUE categories rather than grinding one pillar.

### 4. Lineage Thinking (HGM insight)
Instead of just tracking "did this task succeed?", track "did completing this task unlock or improve subsequent tasks?" — Clade-Metaproductivity for Clarvis. Tasks that unblock other tasks (spine migration → CLI parity → cron entrypoints) should be valued higher than isolated improvements.

### 5. Context Relevance Connection
SWE-EVO's finding that instruction following is the dominant failure mode for strong models directly relates to Context Relevance (0.838). Better context → better instruction interpretation → higher resolution rate. The multi-file evolution scenario is exactly where context quality matters most — the agent needs to understand cross-file dependencies. This validates investing in CONTEXT_RELEVANCE_FEEDBACK and CONTEXT_ADAPTIVE_MMR_TUNING.

## Brain Memories Stored
5 memories in `clarvis-learnings` (importance 0.75-0.85):
1. SWE-EVO benchmark details and capability gap
2. Self-improving agents landscape (SICA/DGM/HGM comparison)
3. Catastrophic forgetting protection mechanisms
4. Fix Rate metric and partial credit scoring
5. Self-improvement failure modes and plateaus
