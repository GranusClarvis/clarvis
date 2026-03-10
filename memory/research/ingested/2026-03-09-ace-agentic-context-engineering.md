# Agentic Context Engineering (ACE)

**Paper**: arXiv:2510.04618 (Oct 2025, accepted ICLR 2026)
**Authors**: Qizheng Zhang + 12 co-authors (Stanford et al.)
**Code**: https://github.com/ace-agent/ace
**Researched**: 2026-03-09

## Core Problem

LLM context adaptation (modifying inputs with instructions/strategies rather than weight updates) suffers from two failure modes:

1. **Brevity bias**: Compression-oriented approaches (GEPA, DSPy) drop domain insights for concise summaries
2. **Context collapse**: Iterative full-context rewriting erodes details over time — observed as 18,282→122 tokens in a single step, accuracy 66.7%→57.1%

## ACE Framework

Three-role agentic pipeline with structured grow-and-refine:

| Role | Function | Output |
|------|----------|--------|
| **Generator** | Produces reasoning trajectories for tasks | Solution attempts + strategy annotations |
| **Reflector** | Evaluates outcomes, extracts actionable lessons | Structured insight bullets (NOT context edits) |
| **Curator** | Converts reflections into delta updates, merges into playbook | ADD/MODIFY/REMOVE operations on playbook entries |

### Playbook Structure

Hierarchical sections with tracked bullets:
```
## STRATEGIES & INSIGHTS
[str-00001] helpful=5 harmful=0 :: Strategy description
## COMMON MISTAKES TO AVOID
[mis-00004] helpful=6 harmful=0 :: Error pattern
```

Each bullet has: unique ID, helpful/harmful counters (empirically tracked across task executions), content.

### Grow-and-Refine Mechanism

- **Growth**: New insights append as uniquely-identified bullets without modifying existing entries
- **Refinement**: Counters updated in-place, semantic-embedding dedup prunes redundancy
- **Pruning trigger**: Lazy (when token budget exceeded) or proactive (after each delta)
- **Token budget**: Configurable (default 80k tokens)

### Delta Updates vs Monolithic Rewrites

Instead of asking an LLM to rewrite the entire accumulated context (which causes collapse), ACE produces compact deltas — small sets of candidate bullets distilled by the Reflector and integrated by the Curator using "lightweight, non-LLM logic." This enables parallel merging and localized edits.

## Key Results

| Benchmark | ACE Improvement | Comparison |
|-----------|-----------------|------------|
| Agent tasks (AppWorld) | +10.6% | vs baselines |
| Finance domain | +8.6% | vs baselines |
| AppWorld leaderboard | Matches IBM CUGA (60.3%) | Using smaller DeepSeek-V3.1 |
| Latency (offline) | -82.3% | vs GEPA |
| Latency (online) | -91.5% | vs Dynamic Cheatsheet |
| Rollouts needed | 357 | vs GEPA's 1,434 |

### Offline vs Online Optimization

- **Offline**: Evolve system prompts on training data, evaluate on test (e.g., improving cron prompt templates)
- **Online**: Adapt context sequentially during deployment (e.g., per-task memory updates)
- Both use the same grow-and-refine mechanism

## Clarvis Application Ideas

### 1. Evolving Context Brief (High Priority — targets Context Relevance 0.838)

Current `context_compressor.py` generates a static context brief by compressing queue + health + episodes. An ACE-inspired approach would:

- **Track helpful/harmful counters** on each context item (queue entries, health metrics, episode summaries) included in the brief
- **Postflight feedback loop**: After each heartbeat, compare which context items were present vs task outcome (success/partial/fail) to update counters
- **Prune low-utility items**: Items consistently present during failures get harmful++ and eventually drop from the brief
- This directly feeds the `[CONTEXT_RELEVANCE_FEEDBACK]` and `[RETRIEVAL_RL_FEEDBACK]` queue items

### 2. Evolving Cron Prompts (Offline Optimization)

Cron orchestrators (`cron_autonomous.sh`, `cron_morning.sh`, etc.) contain static prompt templates. An ACE offline loop could:

- Run the same cron task N times with prompt variants
- Reflector evaluates output quality
- Curator evolves the prompt with proven strategies
- Aligns with `[CRON_OUTPUT_QUALITY_AUDIT]` queue item

### 3. Structured Playbook for Heartbeat (New Architecture)

Replace the current flat context brief with a structured ACE playbook:
```
## TASK SELECTION STRATEGIES
[tsk-001] helpful=12 harmful=1 :: Prefer queue items with clear acceptance criteria over vague improvement tasks
## CONTEXT ASSEMBLY PATTERNS
[ctx-001] helpful=8 harmful=0 :: Include last 3 episode outcomes for continuity
## COMMON FAILURE MODES
[fail-001] helpful=6 harmful=2 :: Avoid spawning browser tasks without checking Ollama status first
```

### 4. Reflector Separation in Postflight

Current `heartbeat_postflight.py` evaluates task outcomes AND writes to memory simultaneously. ACE's separation principle suggests:

- Postflight → assess outcome (Generator feedback)
- New step: extract structured lessons from outcome (Reflector)
- Final step: apply lessons to context/memory (Curator)
- This prevents feedback contamination — bad evaluations don't immediately corrupt context

### 5. Connection to Existing Queue Items

| Queue Item | ACE Connection |
|------------|----------------|
| `[CONTEXT_RELEVANCE_FEEDBACK]` | Direct implementation of helpful/harmful counters on context items |
| `[RETRIEVAL_RL_FEEDBACK]` | ACE's reward signal from Reflector maps to retrieval verdict × task outcome |
| `[RETRIEVAL_EVAL]` | ACE's Reflector role = CRAG-style evaluator |
| `[CONTEXT_ADAPTIVE_MMR_TUNING]` | ACE's playbook could store optimal MMR lambda per task category |
| `[CONTEXT_ENGINE_SPIKE]` | ACE playbook = natural format for Clarvis context engine's runtime context |
| `[BRIEF_BENCHMARK_REFRESH]` | ACE's offline evaluation framework = systematic brief benchmarking |

## Key Takeaway

ACE's core insight is that context should be treated as a **versioned, empirically-grounded knowledge base** (not a prompt to be rewritten), with each entry earning its place through tracked utility. This maps directly to Clarvis's context_brief problem: currently we compress context but never learn which parts of the compressed context actually help task execution. Adding helpful/harmful counters to brief items and a postflight feedback loop would be a minimal ACE-inspired change with high impact on Context Relevance.
