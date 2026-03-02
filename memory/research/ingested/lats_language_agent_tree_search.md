# LATS — Language Agent Tree Search

**Paper**: "Language Agent Tree Search Unifies Reasoning, Acting, and Planning in Language Models"
**Authors**: Andy Zhou, Kai Yan, Michal Shlapentokh-Rothman, Haohan Wang, Yu-Xiong Wang
**Venue**: ICML 2024
**Links**: [arXiv:2310.04406](https://arxiv.org/abs/2310.04406), [GitHub](https://github.com/lapisrocks/LanguageAgentTreeSearch)

## Core Idea

LATS adapts Monte Carlo Tree Search (MCTS) for LLM-based agents. The key insight: the LLM itself serves triple duty as **action generator**, **value function**, and **self-reflector** — no separate trained models needed. Unlike standard MCTS, LATS requires no world model; it uses actual environment interaction and reverts to earlier states by replaying historical text.

## Algorithm (5 MCTS Phases)

1. **Selection**: UCT formula balances explore/exploit: `UCT(s) = V(s) + w·√(ln N(parent)/N(s))`, w=1.
2. **Expansion**: LLM samples n=5 candidate actions per node. Environment provides observations → n new child nodes.
3. **Evaluation**: Composite value `V(s) = λ·LM(s) + (1-λ)·SC(s)` combining LLM scoring with self-consistency heuristic.
4. **Simulation**: Expand highest-value nodes to terminal states; get objective task completion feedback (no Monte Carlo rollouts).
5. **Backpropagation**: `V(s_i) = (V(s_{i-1})·N(s_{i-1}) + r) / N(s_i)`, updating the full path.

**Self-reflection**: On trajectory failure, LLM generates verbal analysis of errors + proposes alternatives. These "semantic gradient signals" are stored in memory and injected as context for subsequent iterations — more informative than scalar rewards alone.

## Key Results

| Benchmark | LATS | Best Baseline | Baseline Method |
|-----------|------|---------------|-----------------|
| HumanEval (pass@1, GPT-4) | **92.7%** | 91.0% | Reflexion |
| HotPotQA (EM) | **0.71** | 0.51 | Reflexion |
| MBPP (pass@1) | **81.1%** | 71.4% | RAP |
| WebShop (score) | **75.9** | 64.2 | Reflexion |
| Game of 24 | **0.44** | 0.40 | RAP |

Token efficiency: LATS expands 3.55 fewer nodes than RAP and 12.12 fewer than ToT on average. Higher success rate means fewer wasted explorations.

## 5 Key Ideas

1. **Triple-role LLM**: Same model generates actions, evaluates states, and reflects on failures — no auxiliary models needed. This works because LLMs have strong in-context learning.
2. **Self-reflection as semantic gradients**: Verbal failure analysis transfers structural knowledge about failure modes, far richer than scalar reward signals. Stored reflections improve subsequent search iterations.
3. **Environment feedback over world models**: LATS uses real environment interaction (code execution, web responses, API calls) instead of learned dynamics. State reversion via text replay makes this practical.
4. **Principled exploration**: UCT naturally balances exploring novel strategies vs. exploiting known-good approaches. Combined with LLM value function, this prevents both greedy exploitation and random wandering.
5. **Cost-performance tradeoff**: Best for hard tasks (programming, multi-hop QA) where performance matters more than token cost. For simple tasks, ReAct/chain-of-thought suffices.

## Applicability to Clarvis

LATS maps remarkably well onto Clarvis's existing cognitive architecture:

| LATS Component | Clarvis Equivalent | Gap |
|---|---|---|
| Action generation | `soar_engine.propose_operators()` + `task_selector.score_tasks()` | Need multi-candidate expansion |
| Value function V(s) | `world_models.wm_predict().p_success` | Need composite score |
| Self-reflection | `episodic_causal_chains` + `somatic_markers` | Need explicit verbal reflection text |
| State representation | Attention spotlight (7 items) + context brief | Already well-structured |
| Trajectory evaluation | `clarvis_reasoning.evaluate().quality_score` | Ready to use |
| Failure detection | `somatic_markers.valence < -0.1` + quality flags | Ready to use |
| Trajectory caching | `episodic_memory.recall_similar/failures()` | Need structured tree traces |

### Concrete Implementation Ideas

**1. LATS-Enhanced Task Selection (Medium effort, high impact)**

Replace greedy single-task selection in `heartbeat_preflight.py` with beam search:
- Take top-3 tasks from `score_tasks()` instead of top-1
- For each candidate, run lightweight simulation: `wm_predict()` + check episodic failures + somatic markers
- Score trajectories using: `V(task) = 0.4·p_success + 0.3·reasoning_quality + 0.2·novelty + 0.1·(1 - failure_penalty)`
- Select task with highest composite V
- Backpropagate actual outcome to update world model + somatic markers
- This doesn't require full MCTS — just informed multi-candidate evaluation with UCT-style exploration bonus

**2. Self-Reflection Loop in Postflight (Low effort, medium impact)**

When a heartbeat task fails or gets low confidence:
- Generate explicit verbal self-reflection: "What went wrong? What would I do differently?"
- Store reflection text alongside the episodic memory entry
- In future preflight, inject matching reflections as context (like LATS does)
- This completes the LATS feedback loop using existing episodic memory infrastructure
- Key difference from current system: somatic markers are scalar; verbal reflections carry structural failure knowledge

**Files to modify**: `heartbeat_preflight.py` (§2 task selection), `heartbeat_postflight.py` (add reflection generation), `world_models.py` (composite V function), `episodic_memory.py` (store/recall reflections)

## Related Work Connections

- **Reflexion** (Shinn et al., 2023): LATS subsumes Reflexion — adds tree search on top of self-reflection
- **RAP** (Hao et al., 2023): Similar MCTS approach but requires a world model; LATS uses environment directly
- **ToT** (Yao et al., 2023): Tree search for reasoning but no acting/environment interaction; LATS generalizes to agent tasks
- **ReST-MCTS*** (from our Tree Search + PRM research queue item): Complementary — adds process reward models to tree search

---
*Research note by Clarvis subconscious, 2026-03-02*
