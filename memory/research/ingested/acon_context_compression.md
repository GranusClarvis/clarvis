# ACON: Optimizing Context Compression for Long-Horizon LLM Agents

**Paper**: Kang et al. (2025), arXiv:2510.00615
**Authors**: Minki Kang, Wei-Ning Chen, Dongge Han, Huseyin A. Inan, Lukas Wutschitz, Yanzhi Chen, Robert Sim, Saravan Rajmohan (Microsoft)
**Code**: github.com/microsoft/acon (MIT license, Python 3.11+)
**Reviewed**: 2026-03-08

## Core Problem

Long-horizon agentic tasks accumulate growing context (action history + environment observations), increasing cost and degrading performance. ACON provides a unified framework to compress both observation and history while maintaining task success.

## Key Ideas

### 1. Contrastive Compression Guideline Optimization (Gradient-Free)

The central innovation: natural-language "compression guidelines" evolve through contrastive analysis of paired trajectories.

- Run agent with full context (succeeds) and compressed context (fails)
- LLM optimizer analyzes the failure: "What information was lost that caused failure?"
- Guidelines updated in natural language — no parameter updates needed
- Works with closed-source API models (gradient-free)

### 2. Two-Phase Optimization

**Utility Maximization (UT)**: From failure cases, identify wrongly discarded information and add it back to guidelines. Maximizes task success.

**Compression Maximization (CO)**: From success cases, identify unnecessarily kept information and remove it from guidelines. Maximizes compression ratio.

The two phases together create an optimal keep/discard boundary.

### 3. Observation vs History Separation

- **History compression**: Applied when accumulated interaction history exceeds T_hist (default 4096 tokens). Compresses both actions and outcomes into summaries.
- **Observation compression**: Applied when individual environment responses exceed T_obs (default 1024 tokens). Removes redundant/distracting content from tool outputs.
- **Selective thresholds**: Skip compression for already-short contexts to avoid overhead.

### 4. Distillation to Small Models

Teacher LLM with optimized guidelines generates compressed outputs; student model (Qwen3-14B, Phi-4) trained via cross-entropy distillation. Preserves 95% of teacher's accuracy. Decouples decision-making from compression.

## Benchmark Results

| Benchmark | Tasks | Baseline Acc | ACON Acc | Token Reduction | Notes |
|-----------|-------|-------------|----------|-----------------|-------|
| AppWorld | 168 | 56.0% | 56.5% | 26% (9.93K→7.33K) | Acc maintained |
| OfficeBench | 95 | 76.84% | 72.63% | 37% (7.27K→4.54K) | Small acc drop |
| 8-Obj QA | 100 | 0.366 EM | 0.336 EM | 59% (10.35K→4.22K) | F1 improved! (0.458→0.488) |

Best optimizer: o3 with contrastive feedback. Removing contrastive feedback costs -0.6% accuracy.

## Clarvis Application (5 Ideas)

### Idea 1: Contrastive Feedback Loop for Context Relevance (HIGH PRIORITY)

**Directly targets context_relevance=0.838.** In `heartbeat_postflight.py`, after task completion:
- Compare which brief sections were actually referenced in Claude Code output
- Compute `referenced_sections / total_sections` as true relevance
- Store per-episode as ground truth
- Over time, accumulate success/fail pairs to identify which brief sections correlate with task success

This is the zero-LLM analog of ACON's contrastive optimization. Already proposed as `[CONTEXT_RELEVANCE_FEEDBACK]` in QUEUE.md.

### Idea 2: Dynamic Section Budgets in generate_tiered_brief()

Current `TIER_BUDGETS` are static (e.g., decision_context=100, spotlight=80, metrics=40). With accumulated feedback data:
- Increase budget for sections that correlate with task success
- Decrease budget for sections rarely referenced
- Implement as a weekly cron job that reads episode feedback and updates a `data/compression_guidelines.json`

This mirrors ACON's guideline evolution without needing an LLM optimizer.

### Idea 3: Separate Observation and History Compression

Current `compress_text()` treats all input uniformly. Split into:
- `compress_observation(text)` — for tool outputs, brain search results, health data (remove redundancy, keep decision-critical numbers)
- `compress_history(text)` — for episode history, queue completions (summarize action-outcome pairs)
- Apply ACON-style selective thresholds: only compress when exceeding per-type token limits

### Idea 4: Task-Specific Compression Rules

ACON's guidelines are task-type-aware. Our `_build_decision_context()` already extracts success criteria from task text. Extend this:
- Maintain per-task-category compression rules (research tasks need different context than implementation tasks)
- Wire into `spawn_claude.sh --category` (proposed in `[SPAWN_ADAPTIVE_TIMEOUT]`)
- Different categories get different TIER_BUDGETS automatically

### Idea 5: Compression Quality Scoring

ACON measures compression quality by task outcome (not ROUGE/BLEU). Implement:
- In postflight: log `{task, brief_sections_provided, brief_sections_used, outcome}`
- Monthly: compute per-section utility score
- Auto-prune sections with utility < 0.1 from default brief generation
- This creates a self-improving compression pipeline

## Relationship to Other Queue Items

- **[CONTEXT_RELEVANCE_FEEDBACK]**: ACON validates this approach — contrastive feedback is the core mechanism
- **[BRIEF_BENCHMARK_REFRESH]**: ACON shows static benchmarks are insufficient; need outcome-based measurement
- **[PREFLIGHT_SPEED]**: ACON's selective thresholds (skip compression when context is short) could reduce preflight overhead
- **[MEMR3_REFLECTIVE_RETRIEVAL]**: Complementary — MemR3 optimizes retrieval, ACON optimizes compression of retrieved results

## Key Takeaway

ACON's gradient-free contrastive optimization is directly applicable to Clarvis without LLM overhead. The core loop — "compare what we gave the agent vs what it used, then adjust" — can be implemented purely with token-overlap analysis in postflight. This is the highest-leverage improvement for context_relevance.
