# AgentEvolver: Towards Efficient Self-Evolving Agent System

**Paper**: arXiv:2511.10395 (Nov 2025)
**Authors**: Yunpeng Zhai, Shuchang Tao, Cheng Chen et al. (Alibaba Tongyi Lab)
**Code**: github.com/modelscope/AgentEvolver (Python 3.11+, veRL, GRPO)
**Ingested**: 2026-03-12

## Problem

Current autonomous agent development requires manually constructed task datasets and RL pipelines with extensive random exploration → high data-construction costs, low exploration efficiency, poor sample utilization.

## Three Synergistic Mechanisms

### 1. Self-Questioning (Curiosity-Driven Task Generation)
- **Goal**: Eliminate manual task dataset construction
- **How**: High-temperature LLM explores environments via breadth-first (N_b steps) then depth-first investigation
- Uses environment profiles (entity-attribute-operation descriptions) as action priors
- Myopic decision-making: only considers recent N_d observations to prevent premature convergence
- Task synthesis: transforms explored trajectories into user-preferred problems
- Preference-guided constraints along difficulty and style axes
- Post-generation filtering: verifies feasibility by executing reference solutions
- **Key insight**: Problems generated AFTER exploration, so solutions are discoverable from prior trajectories

### 2. Self-Navigating (Experience Reuse + Hybrid Policy)
- **Experience format**: Natural-language units with "When to use" (retrieval trigger) + "Content" (instructions/strategies)
- **Library construction**: N_pc independent rollouts per task → trajectory preprocessing → experience extraction → LLM validation → vector store indexing
- **Retrieval**: Embedding-based cosine similarity → top-k → re-ranking (contextual relevance) + re-writing (generality enhancement)
- **Hybrid rollouts**: Interleave vanilla trajectories (T^v) and experience-guided ones (T^e), balance via parameter η
- **Experience stripping**: Remove experience tokens before optimization to prevent memorization
- **Selective boosting**: Amplify positive-advantage experience-guided updates via relaxed clipping threshold

### 3. Self-Attributing (Step-Wise Credit Assignment)
- **How**: LLM evaluates complete trajectories holistically, assigns binary GOOD/BAD labels per step based on contribution to outcome
- Replaces complex Process Reward Models with flexible LLM-based reasoning
- **Composite reward**: r̂_t = α·r̂^attr_t + 𝟙_{t=T}·r̂^out (attribution + outcome at terminal step)
- **Key difference from standard RL**: Dense, process-oriented feedback vs sparse trajectory-level rewards
- Trajectory-level standardization ensures equal weighting regardless of trajectory length

## Architecture

**Service-Oriented Design**:
- Master Orchestrator → 4-stage loop: Task Synthesis → Trajectory Rollout → Experience Summarization → Optimization
- Environment Service: Gym-compatible, Ray-based isolated actors, supports AppWorld/BFCL/WebShop/Crafter
- Context Manager: Live Context Timeline (mutable working context) + Timeline Snapshot Recorder (immutable action snapshots)
- 4 context templates: Basic Causal, Reasoning-Augmented (think tokens), Sliding Window, Self-Context Managing (keep/remove/compress)

## Benchmark Results

| Model | AppWorld avg@8 | AppWorld best@8 |
|-------|---------------|-----------------|
| Qwen2.5-7B + GRPO baseline | 15.8% | — |
| Qwen2.5-7B + AgentEvolver | 45.2% | — |
| Qwen2.5-14B + AgentEvolver | 57.6% | — |

- Training: 8× A100 80GB, LR 1e-6, batch 32, 40 epochs/update, KL penalty 0.001
- Built on PyTorch + veRL

## Clarvis Mapping

### 1. Self-Questioning → `cron_autonomous.sh` task selection
- **Current**: Tasks come from static QUEUE.md, attention scoring picks from fixed candidates
- **Opportunity**: Curiosity-driven task generation — agent explores its own capabilities and generates novel improvement tasks
- **Implementation path**: After task completion, analyze what adjacent capabilities could be explored. Generate candidate tasks based on environment profiling (what scripts exist, what they do, what's untested)
- **Concrete**: Add "curiosity exploration" phase to `heartbeat_preflight.py` — when QUEUE.md has no P0 tasks, auto-generate candidates by probing underexplored modules

### 2. Self-Navigating → `evolution_loop.py` experience reuse
- **Current**: Episodes stored in `clarvis-episodes` but not systematically reused for guiding new tasks
- **Opportunity**: Build experience library from successful task completions with "When to use" + "Content" format
- **Implementation path**: Extract procedural patterns from high-confidence episodes, store as retrievable experiences, inject into task briefs
- **Concrete**: Enhance `procedural_memory.py` with AgentEvolver-style experience format — structured "When to use" triggers + "Content" instructions, vector-indexed for retrieval during preflight

### 3. Self-Attributing → `heartbeat_postflight.py` reward attribution
- **Current**: Binary success/fail outcome + confidence score, no step-level attribution
- **Opportunity**: Step-wise credit assignment — which parts of the execution contributed to success/failure
- **Implementation path**: In postflight, analyze output sections against task objectives, assign per-section contribution scores
- **Concrete**: Add trajectory analysis to `heartbeat_postflight.py` — parse Claude Code output into steps, LLM-judge each step's contribution, store step-level rewards in episode metadata

## Key Takeaways for Clarvis

1. **Experience format matters**: Natural-language "When to use" + "Content" is more interpretable and retrievable than raw episode logs. Current procedural_memory.py is close but lacks structured trigger conditions.
2. **Curiosity-driven exploration beats static task lists**: QUEUE.md is manual. Auto-generating improvement tasks from capability gaps would accelerate evolution.
3. **Step-level attribution >> binary outcomes**: Current postflight records success/fail. Knowing WHICH steps helped enables targeted improvement.
4. **Experience stripping prevents memorization**: When reusing past experiences, strip them before learning to maintain generalization — relevant for procedural memory injection.
5. **Hybrid rollout balance (η parameter)**: Don't over-rely on past experience. Balance novel exploration with experience-guided execution. Maps to mixing fresh approaches with procedural memory.
