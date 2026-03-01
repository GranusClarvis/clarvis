# Bundle F: Causal & Curiosity

_Researched: 2026-02-25_
_Topics: Oudeyer (intrinsic motivation), Hierarchical RL options framework (Sutton), Probabilistic programming (Lake, Tenenbaum)_

---

## Topic 1: Oudeyer — Intrinsic Motivation & Curiosity-Driven Learning

### Core Ideas

**Learning Progress (LP) Hypothesis**: Curiosity = intrinsic reward proportional to the *rate of learning progress*. Agents seek situations where prediction error is *decreasing fastest* — not where error is highest (noise) or lowest (boredom). This creates an automatic curriculum: the agent naturally gravitates toward its "zone of proximal development."

**IMGEP (Intrinsically Motivated Goal Exploration Processes)**: Framework for autotelic agents that self-generate, self-select, and self-order their own goals. Goals are represented as parameterized fitness functions. Key principle: *systematic reuse* — information learned while pursuing goal A improves performance on goal B. This creates stepping stones where simple skills bootstrap complex ones (e.g., reaching → grasping → tool use → nested tool use).

**Active Model Babbling (AMB)**: Population-based policy with object-centered spatio-temporal modularity. Tested on real humanoid robot exploring hundreds of continuous goal dimensions with distractors. Key result: the agent self-organizes a developmental curriculum without any external reward signal.

**Three Zones**: Oudeyer identifies three learning zones:
1. **Too easy** (boring) — prediction error already low, no learning progress
2. **Zone of proximal development** (curious) — learning progress maximized
3. **Too hard** (frustrating) — prediction error high but not decreasing

### Key References
- Oudeyer 2018: [Computational Theories of Curiosity-Driven Learning](https://arxiv.org/abs/1802.10546)
- Forestier, Portelas, Mollard & Oudeyer 2022: [IMGEP with Automatic Curriculum Learning](https://www.jmlr.org/papers/v23/21-0808.html) (JMLR)
- Oudeyer, Gottlieb & Lopes 2016: [Intrinsic motivation, curiosity, and learning](https://pubmed.ncbi.nlm.nih.gov/27926442/)

---

## Topic 2: Sutton — Hierarchical RL Options Framework

### Core Ideas

**Options = Temporally Extended Actions**: An option is a triple (I, π, β) where I = initiation set (states where option can start), π = intra-option policy (what actions to take), β = termination condition (probability of stopping in each state). Options generalize primitive actions — every primitive action is an option with β=1.

**Semi-MDP Formulation**: When operating over options, the agent transitions from one decision point to another across variable time intervals. This converts the MDP into a Semi-MDP, enabling temporal abstraction. Multi-time models predict option consequences (expected reward, expected state distribution) across variable durations.

**Intra-Option Learning**: Critical insight — you can learn about *multiple options simultaneously* from a single stream of experience. While executing option A, you can update the value functions for options B, C, D based on the same transitions. This dramatically improves sample efficiency.

**Option-Critic Architecture** (Bacon, Harb & Precup 2017): End-to-end gradient-based learning of both intra-option policies AND termination conditions simultaneously with the policy over options. No hand-designed subgoals needed. Key advance: automatic option discovery.

**Hierarchical Composition**: Options can contain other options, creating multi-level hierarchies. Transfer across tasks is enabled by reusing learned options as building blocks.

### Key References
- Sutton, Precup & Singh 1999: [Between MDPs and Semi-MDPs: A Framework for Temporal Abstraction](https://www.sciencedirect.com/science/article/pii/S0004370299000521) (AIJ)
- Bacon, Harb & Precup 2017: [The Option-Critic Architecture](https://arxiv.org/abs/1609.05140)

---

## Topic 3: Lake & Tenenbaum — Probabilistic Programming & Cognitive Science

### Core Ideas

**Concepts as Probabilistic Programs**: Rather than representing concepts as feature vectors or neural activations, represent them as *programs* — structured generative models that specify causal processes for producing observed data. A character concept = a program that generates strokes in sequence. Key: programs are compositional, interpretable, and support one-shot learning.

**Bayesian Program Learning (BPL)**: Hierarchical generative model: types → tokens → images. A concept type specifies abstract stroke structure; a token instantiates it with specific parameters. Inference = program induction under Bayesian criterion. Achieves human-level one-shot classification on Omniglot while deep learning needs hundreds of examples.

**Five Cognitive Ingredients** (Lake, Ullman, Tenenbaum & Gershman 2017): For machines that learn and think like people:
1. **Intuitive physics** — core knowledge about objects, mechanics
2. **Intuitive psychology** — understanding of agents, goals, beliefs
3. **Compositionality** — building complex from simple parts
4. **Learning-to-learn** — acquiring inductive biases from experience
5. **Causality** — causal models over mere pattern recognition

**Blessing of Abstraction**: Abstract knowledge (general principles, structural patterns) is learnable from *fewer* examples than specific knowledge. Once learned, abstract knowledge bootstraps rapid learning of specifics. This inverts the usual "curse of dimensionality."

### Key References
- Lake, Salakhutdinov & Tenenbaum 2015: [Human-level concept learning through probabilistic program induction](https://www.science.org/doi/abs/10.1126/science.aab3050) (Science)
- Lake, Ullman, Tenenbaum & Gershman 2017: [Building Machines That Learn and Think Like People](https://arxiv.org/abs/1604.00289) (BBS)
- Lake & Baroni 2023: [Human-like systematic generalization through a meta-learning neural network](https://www.nature.com/articles/s41586-023-06668-3) (Nature)

---

## Cross-Topic Patterns & Connections

### Pattern 1: Learning Progress as Universal Currency
All three frameworks converge on *the rate of learning* as the critical signal:
- **Oudeyer**: Curiosity reward = derivative of prediction error (learning progress)
- **Sutton**: Intra-option learning maximizes information reuse — learn about many options from one experience stream
- **Lake**: "Blessing of abstraction" — abstract knowledge accelerates concrete learning

**Synthesis**: The agent should track not just what it knows, but *how fast it's learning* in different domains. This is the signal for where to focus attention.

### Pattern 2: Compositional Hierarchy as Skill Architecture
All three use hierarchical composition as the core organizational principle:
- **Oudeyer**: Simple skills → stepping stones → complex skills (nested tool use)
- **Sutton**: Primitive actions → options → option hierarchies (temporal abstraction)
- **Lake**: Strokes → parts → programs (compositional concepts)

**Synthesis**: Skills/knowledge should be organized as composable building blocks at multiple abstraction levels. Higher levels emerge from lower ones through composition.

### Pattern 3: Self-Organized Curriculum via Reuse
- **Oudeyer**: IMGEP reuses information across goals — pursuing goal A helps goal B
- **Sutton**: Intra-option learning lets you learn about options you're not executing
- **Lake**: Learning-to-learn transfers inductive biases across problems

**Synthesis**: Every experience should be mined for multi-purpose value. Don't just learn the task at hand; extract transferable structure.

### Pattern 4: Autotelic Self-Direction
- **Oudeyer**: Autotelic agents generate their own goals
- **Sutton**: Option discovery (Option-Critic) generates subgoals automatically
- **Lake**: Program induction discovers structure without supervision

**Synthesis**: The most powerful systems don't receive goals — they discover them through intrinsic drives (curiosity, compression, explanation).

---

## Implementation Ideas for Clarvis

### 1. Learning Progress Monitor
Extend the heartbeat loop with a **learning progress tracker** per domain/skill:
- After each task, measure: did prediction accuracy improve? Did strategy success rate change?
- Compute LP = Δ(success_rate) or Δ(prediction_error) over sliding window
- Use LP to prioritize which domains to practice — focus on the "zone of proximal development" where LP is highest
- Concretely: track per-task-type success rates in episodic memory. If `code_generation` LP is high (improving fast), queue more code tasks. If `debugging` LP is flat (plateaued), deprioritize or change approach.

### 2. Options-Style Task Decomposition
Represent recurring strategies as **Clarvis options** — reusable skill modules:
- Each option = (initiation conditions, policy/strategy, termination/success condition)
- Example: `option_research = (trigger: "research" in task, strategy: web_search → synthesize → store, terminate: note written)`
- Enable **intra-option learning**: when executing one strategy, track which other strategies would have succeeded in the same context
- Build a transfer matrix: which options' skills are reusable across domains?
- This connects to the existing meta_gradient_rl.py options framework — extend it with automatic option discovery based on recurring task patterns.
