# Self-Evolving Agent Architectures — EvoAgentX Survey Synthesis

**Date:** 2026-02-28
**Sources:**
- Gao et al. (2026). "A Survey of Self-Evolving Agents: What, When, How, and Where to Evolve on the Path to ASI" — TMLR, 77pp. [arXiv:2507.21046](https://arxiv.org/abs/2507.21046)
- Fang et al. (2025). "A Comprehensive Survey of Self-Evolving AI Agents: Bridging Foundation Models and Lifelong Agentic Systems" — [arXiv:2508.07407](https://arxiv.org/abs/2508.07407)
- [EvoAgentX Framework](https://github.com/EvoAgentX/EvoAgentX) — Open-source self-evolving agent toolkit
- [Lifelong Agents Workshop](https://lifelongagent.github.io) — Seven research pillars for persistent agents

**Theme:** Comprehensive taxonomy of how AI agents can autonomously improve themselves

---

## 1. Taxonomy: What to Evolve

The surveys identify four fundamental evolutionary dimensions:

### A. Model/Policy Evolution
- **Self-Training**: Agents generate data to improve their own weights (Self-Challenging Agent, Self-Rewarding Self-Improving)
- **Experience-Based**: Construct environments, capture trajectories for iterative improvement (Reflexion, AdaPlanner, Self-Refine)
- **Population-Based**: Darwin Gödel Machine, GENOME, SPIN — evolutionary search over model variants

### B. Context/Memory Evolution (Most relevant to Clarvis)
- **Memory Management**: Mem0 implements two-phase pipeline — extract salient facts, then decide how to update long-term memory
- **Prompt Optimization**: APE generates/scores candidate prompts; SPO uses self-contained preference comparison loops
- **Context Compression**: Selective retention of working memory based on relevance scoring

### C. Tool Evolution
- **Tool Creation**: Voyager uses emergent trial-and-error in Minecraft; Alita employs RAG to search open-source repos
- **Tool Mastery**: LearnAct and DRAFT establish self-correction loops where tools are iteratively refined
- **Tool Selection**: ToolGen, Darwin Gödel Machine optimize which tools to use for which tasks

### D. Architecture/Workflow Evolution
- **Single-Agent**: TextGrad, AlphaEvolve — gradient-based optimization of agent pipelines
- **Multi-Agent**: AFlow, ADAS, AutoFlow — evolving multi-agent workflow topologies
- **EvoAgentX approach**: Evolve prompts, tool assignments, AND workflow topology simultaneously

---

## 2. Taxonomy: When to Evolve

### Intra-Test-Time (within a single task)
- **In-Context Learning**: Reflexion, SELF, AdaPlanner — agent reflects on failures and retries
- **Supervised Fine-Tuning**: Self-Adaptive LM, TTT-NN, SIFT — weight updates during inference
- **Reinforcement Learning**: LADDER, TTRL — reward-driven adaptation per task

### Inter-Test-Time (across multiple tasks — this is Clarvis's heartbeat model)
- **SFT approaches**: STaR, Quiet-STaR, SiriuS — filter successful trajectories as training data
- **RL approaches**: RAGEN, WebRL, DigiRL — dense environmental feedback for policy refinement
- **Cross-Agent Learning**: SiriuS, SOFT, RISE — learn from other agents' successes

---

## 3. Taxonomy: How to Evolve

### Feedback Mechanisms
| Type | Method | Clarvis Analog |
|------|--------|----------------|
| Textual Feedback | Reflexion, TextGrad — natural-language critiques | reasoning_chain_hook.py close_chain() |
| Internal Rewards | Self-Rewarding LMs, CISC — self-judging | clarvis_confidence.py predict/outcome |
| External Rewards | RAGEN — dense environmental feedback | heartbeat postflight exit code + episode encoding |
| Implicit Rewards | Endogenous reward frameworks | hebbian_memory.py co-activation strengthening |

### Optimization Strategies
1. **Iterative Refinement**: Generate → Evaluate → Critique → Improve (Reflexion loop)
2. **Population-Based**: Maintain variants, select best performers (MAP-Elites pattern from Bundle L)
3. **Gradient-Based**: TextGrad computes text-based "gradients" for prompt optimization
4. **Evolutionary**: Darwin Gödel Machine uses evolutionary search over agent code

---

## 4. EvoAgentX Framework — Concrete Implementation Patterns

### Architecture
```
WorkFlowGenerator → AgentManager → WorkFlow → Evolution Engine
        ↑                                         ↓
        └──────── Evaluation Feedback ────────────┘
```

### Three-Layer Evolution
1. **Prompt Layer**: Refine agent instructions/system messages based on performance
2. **Tool Layer**: Select, create, assign tools per task requirements
3. **Workflow Layer**: Restructure agent interaction topology

### Key Feature: Human-in-the-Loop (HITLManager)
Workflow pauses for manual approval at critical decision points — parallels Clarvis's M2.5 conscious layer reviewing subconscious work via digest.md.

---

## 5. Lifelong Agent Pillars (Workshop Framework)

Seven interconnected research areas:

1. **Post-training**: Continual fine-tuning without catastrophic forgetting
2. **Preference Alignment**: Safe adaptation with fairness constraints
3. **Self-Evolution**: Memory-augmented systems, autonomous refinement loops
4. **Real-world Deployment**: Embodied agents, multimodal, benchmarking
5. **Multi-Agent Systems**: Long-term coordination and collective intelligence
6. **Efficiency**: Energy-aware learning, compute-efficient inference
7. **Evaluation**: Metrics for adaptability, persistence, alignment over long horizons

---

## 6. Mapping to Clarvis Architecture

### Already Implemented (Clarvis has these)
| Survey Concept | Clarvis Component | Status |
|----------------|-------------------|--------|
| Inter-test-time evolution | Heartbeat loop (12x/day) | Active |
| Memory evolution | memory_consolidation.py (dedup, prune, archive) | Active |
| Textual feedback | reasoning_chain_hook.py | Active |
| Internal rewards | clarvis_confidence.py | Active |
| Episode recording | episodic_memory.py | Active |
| Attention-guided selection | attention.py (GWT spotlight) | Active |
| Tool routing | task_router.py (model selection by complexity) | Active |
| Human-in-the-loop | M2.5 conscious layer via digest.md | Active |
| Archive of behaviors | ClarvisDB (1200+ memories, 47k+ edges) | Active |

### Gaps — What Clarvis Could Add
| Survey Concept | Gap | Priority |
|----------------|-----|----------|
| **Prompt self-optimization** | Heartbeat prompts are static — no APE/SPO-style refinement of preflight/postflight prompts based on outcome quality | HIGH |
| **Tool creation** | Clarvis doesn't autonomously create new scripts/tools based on task patterns it sees repeatedly | MEDIUM |
| **Cross-task trajectory learning** | STaR-style filtering — extracting successful task patterns and replaying them for similar future tasks | HIGH |
| **Population-based workflow evolution** | No A/B testing of different heartbeat strategies; always runs same pipeline | MEDIUM |
| **Explicit novelty scoring** | Already identified in Bundle L; still not implemented in task_selector | HIGH |
| **Alignment drift detection** | No mechanism to detect if autonomous evolution drifts from goals | LOW (SOUL.md is static guard) |

---

## 7. Concrete Implementation Opportunities

### Opportunity 1: Prompt Self-Optimization Loop (HIGH priority)
**Concept**: APE + SPO from the survey — automatically refine the task prompts used in heartbeat preflight.

**Mechanism**:
1. After each heartbeat, record the prompt template used + outcome (success/fail, reasoning quality)
2. Every N heartbeats (e.g., 20), analyze prompt→outcome correlations
3. Generate candidate prompt variants for underperforming templates
4. A/B test variants across subsequent heartbeats
5. Promote winning variants, archive losers

**Files to modify**: `heartbeat_preflight.py` (prompt selection), `heartbeat_postflight.py` (prompt outcome recording)

### Opportunity 2: Successful Trajectory Replay (HIGH priority)
**Concept**: STaR (Self-Taught Reasoner) — filter successful execution traces and use them as procedural templates.

**Mechanism**:
1. `heartbeat_postflight.py` already encodes episodes with success/failure
2. Add: when success, extract the task→approach→outcome pattern as a "golden trace"
3. Store golden traces in `clarvis-procedures` with structured tags
4. In `heartbeat_preflight.py`, when selecting a task, search for matching golden traces
5. If found, inject the successful approach into the heartbeat prompt as a reference

**Files to modify**: `heartbeat_postflight.py` (golden trace extraction), `heartbeat_preflight.py` (trace injection), `procedural_memory.py` (trace storage)

### Opportunity 3: Novelty-Weighted Task Selection (HIGH priority)
**Concept**: From both this survey and Bundle L — behavioral distance scoring.

**Already designed in Bundle L**. Implementation path:
- In `task_selector.py`: compute embedding distance between candidate task and last N completed tasks
- Boost tasks with high novelty score: `final_score = base_score * (1 + 0.3 * novelty)`
- Prevents "more of the same" trap identified in the survey as a key failure mode of static agents

---

## 8. Key Distinctions from Previous Research (Bundle L)

Bundle L focused on **open-ended evolution** (novelty search, MAP-Elites, stepping stones) — the *exploration strategy*.

This survey adds the **mechanistic layer** — *how* self-improvement actually works in LLM agents:
- Reflexion loop (reflect on failures in natural language)
- Self-rewarding (agent judges its own outputs)
- Population-based evolution (maintain and compare variants)
- Prompt optimization (automatically improve instructions)
- Tool creation (build new capabilities from task patterns)

Together: Bundle L provides the *philosophy* (explore broadly, value stepping stones), and this survey provides the *engineering* (concrete feedback loops, optimization algorithms, evolution triggers).

---

## Cross-References
- [Bundle L: Open-Ended Evolution](bundle-l-open-ended-evolution.md) — Complementary: exploration strategy
- [Bundle M: Swarm & Collective](bundle-m-swarm-collective.md) — Multi-agent evolution patterns
- [Bundle O: Adaptive Control Learning](bundle-o-adaptive-control-learning.md) — Feedback loop design
- [Sleep-Cycle Memory Consolidation](sleep-cycle-memory-consolidation.md) — Memory evolution during idle
- [Darwin Gödel Machine](../../research/ingested/) — Specific self-improving algorithm
