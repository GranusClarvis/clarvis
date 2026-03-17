# Trajectory-Informed Memory Generation for Self-Improving Agents

**Source**: arXiv:2603.10600, IBM Research, March 2026

## Core Idea

Instead of storing raw episodes or generic facts, extract *actionable learnings* from execution trajectories via structured analysis, then retrieve them contextually to improve future task execution. The system generates three types of tips — strategy (from clean successes), recovery (from failure-then-success sequences), and optimization (from suboptimal successes) — and injects the most relevant tips into future prompts.

## Architecture (4 components)

### 1. Trajectory Intelligence Extractor (TIE)
Four-stage pipeline:
1. **Parse & categorize reasoning**: Classify agent thoughts into analytical, planning, validation, reflection
2. **Semantic pattern recognition**: LLM identifies cognitive patterns — validation behavior, self-correction sequences, error recognition, efficiency awareness
3. **Outcome determination**: Interpret ground-truth labels or synthesize outcome from extracted self-reflective signals
4. **Success pattern analysis**: Classify as clean success, inefficient success, or recovery sequence

### 2. Decision Attribution Analyzer (DAA)
Three-stage causal analysis:
1. **Outcome scanning**: Detect failure/recovery/inefficiency/success indicators with context
2. **Causal tracing**: LLM traces backward through reasoning to identify root cause (not symptom location — "outcome location ≠ cause location")
3. **Prevention/improvement steps**: Actionable, specific, causal, preventive

### 3. Contextual Learning Generator
Produces structured tips with: content, category (strategy/recovery/optimization), implementation steps, trigger condition, negative examples, application context, priority, source trajectory IDs.

Key: tips are generated per-subtask (not per-task) — subtask granularity drives individual task accuracy.

### 4. Adaptive Memory Retrieval
Two strategies:
- **Cosine similarity** (threshold τ≥0.6, no top-k cap): Fast, works well for TGC
- **LLM-guided selection**: Adds metadata filtering + category reasoning. Better for SGC (+7.2pp over cosine)

Key finding: "Tip granularity drives TGC. Retrieval strategy drives SGC."

## Results (AppWorld benchmark)
- +14.3pp scenario goal completion on held-out tasks
- +28.5pp on hardest tasks (Difficulty 3) — 149% relative increase
- Subtask-level tips + LLM-guided retrieval: best overall config

## Mapping to Clarvis

### Already present (partial)
| Paper component | Clarvis equivalent | Gap |
|---|---|---|
| Episode encoding | `EpisodicMemory.encode()` (postflight §5) | Stores outcome + duration but NOT reasoning trace or decision chain |
| Step extraction | `extract_steps()` + `learn_from_task()` (postflight §4) | Extracts steps but no attribution — doesn't distinguish strategy/recovery/optimization |
| Failure learning | `learn_from_failures()` in procedural_memory.py | Scans log for soft failures, creates corrective procedures — closest to recovery tips |
| Trajectory scoring | `trajectory.py` + `record_trajectory_event()` (postflight §5.01) | Scores quality but doesn't extract learnings from score |
| Error classification | `_classify_error()` (postflight) | 5 categories but no causal tracing back through reasoning |

### Key gaps to close

1. **No tip taxonomy**: Current system stores procedures (steps) and failure lessons (text blobs). Paper's strategy/recovery/optimization taxonomy is more structured and enables category-aware retrieval.

2. **No decision attribution**: `_classify_error()` identifies error *type* but not root *cause* in the decision chain. Paper's DAA traces backward from outcome to the actual decision that caused it.

3. **No subtask decomposition**: Current episode = one task. Paper decomposes trajectory into subtasks and generates tips per subtask — critical for complex multi-step tasks.

4. **No tip injection at retrieval time**: `find_procedure()` finds matching procedures but doesn't inject strategy/recovery/optimization tips into the prompt based on multi-dimensional similarity. Preflight context assembly doesn't include per-task tips.

5. **No consolidation**: Paper merges tips across trajectories (dedup, conflict resolution). Current procedures accumulate without cross-trajectory synthesis.

### Actionable implementation path

**Phase 1 (lightweight, no LLM)**: Extend `learn_from_task()` to classify learnings as strategy/recovery/optimization based on task outcome pattern:
- `exit_code == 0` + no error recovery in output → strategy tip
- `exit_code == 0` + error recovery detected in output → recovery tip
- `exit_code == 0` + duration > 2× median for similar tasks → optimization tip
- Store tip_type as metadata tag on procedure

**Phase 2 (postflight enhancement)**: In postflight §4, after step extraction, add a lightweight attribution step:
- For failures: extract the last substantive action before the error (from output_text) as `root_action`
- For recoveries: extract the corrective action as `recovery_action`
- Store these as procedure metadata for richer retrieval

**Phase 3 (preflight injection)**: In context assembly, add a `trajectory_tips` section:
- Query procedures with tip_type metadata filter matching current task category
- Inject top-3 tips (by similarity × recency) into the prompt context
- This directly targets Context Relevance (weakest metric at 0.387)

**Phase 4 (consolidation, periodic)**: Add a cron job or reflection-time pass that:
- Deduplicates near-identical tips (cosine > 0.85)
- Resolves conflicting tips using outcome metadata
- Promotes high-utility tips, demotes unused ones (already partially done via retire_stale)
