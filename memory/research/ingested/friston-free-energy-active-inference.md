# Friston's Free Energy Principle and Active Inference: Deep Synthesis

**Key Authors:** Karl Friston, Thomas Parr, Giovanni Pezzulo, Conor Heins, Beren Millidge, Safron (IWMT)
**Key Works:** Parr, Pezzulo & Friston (2022) *Active Inference* (MIT Press); Friston (2019) *Generalised Free Energy and Active Inference*; Millidge et al. (2021) *Whence the Expected Free Energy*; Heins et al. (2022) *pymdp*; de Vries & Friston (2025) *EFE-based Planning as Variational Inference*; Safron (2020) *Integrated World Modeling Theory*; Friston et al. (2017) *Active Inference, Curiosity and Insight*; Phan et al. (2025) *Curiosity is Knowledge*
**Year Range:** 2006-2025
**Relevance to Clarvis:** Direct architectural alignment with attention/GWT, episodic memory, dream engine, confidence tracking, reasoning chains

---

## 1. The Mathematical Framework: Beyond "Minimize Surprise"

The Free Energy Principle (FEP) states that any self-organizing system that persists must minimize variational free energy. The standard formulation:

**Variational Free Energy:**
```
F = -E_Q(s)[ln P(o,s)] + E_Q(s)[ln Q(s)]
  = Energy - Entropy
  = -E_Q(s)[ln P(o|s)] + D_KL[Q(s) || P(s)]
  = -(Accuracy) + (Complexity)
```

The accuracy-complexity decomposition is the crucial insight often missed in superficial treatments. The agent must maximize how well its model explains observations (accuracy) while keeping the model as simple as possible (complexity cost). This is not merely "minimizing surprise" -- it is Occam's razor formalized as a variational bound. The complexity term prevents overfitting to noise, while the accuracy term prevents underfitting to structure.

The full generative model for discrete active inference uses four matrices:
- **A** (likelihood): P(o|s) -- maps hidden states to observations. Each column is a conditional distribution.
- **B** (transitions): P(s_t+1 | s_t, pi) -- policy-conditioned state dynamics.
- **C** (preferences): P(o) -- prior distribution over preferred observations (encodes goals).
- **D** (initial prior): P(s_0) -- belief about starting state.

State inference then follows Bayesian filtering:
```
Q(s_t) = softmax(ln A[o_t, :] + ln B[:,:,u].dot(Q(s_{t-1})))
```
This is belief updating: combine the likelihood of current observation with the predicted prior from the previous state and action.

## 2. Expected Free Energy: How Active Agents Choose Actions

The core innovation of active inference over passive perception is the Expected Free Energy (EFE), which evaluates future policies (action sequences). The EFE for policy pi at future time tau:

**Decomposition 1 -- Risk + Ambiguity:**
```
G(pi, tau) = D_KL[Q(o_tau|pi) || P(o_tau)]  +  E_Q(s_tau|pi)[H[P(o_tau|s_tau)]]
              ^-- Risk (divergence            ^-- Ambiguity (expected
                  from preferred outcomes)        observation uncertainty)
```

**Decomposition 2 -- Epistemic + Pragmatic:**
```
G(pi, tau) = -I(o_tau; s_tau | pi)  -  E_Q(o_tau|pi)[ln P(o_tau)]
              ^-- Epistemic value     ^-- Pragmatic value
                  (information gain       (expected utility /
                   / mutual information)   preference satisfaction)
```

These two decompositions are mathematically equivalent but conceptually distinct. The first says: avoid states where you cannot achieve your goals (risk) and where observations are uninformative about the world (ambiguity). The second says: seek information (epistemic) while pursuing preferences (pragmatic).

**Policy selection** is Bayesian model comparison over policies:
```
Q(pi) = softmax(ln P(pi) - G(pi))
```
Policies with lower expected free energy (less risk, less ambiguity, more information gain, more preference satisfaction) are more probable. Actions are then sampled from the marginal:
```
P(u_t) = sum_pi Q(pi) * I[pi(t) = u_t]
```

## 3. The Exploration-Exploitation Resolution

The most powerful consequence of EFE is its natural resolution of the exploration-exploitation dilemma, which is NOT simply a parameter trade-off (as in epsilon-greedy RL) but an emergent property of the mathematics.

When the agent is uncertain about hidden states, the epistemic term dominates -- the agent explores to reduce uncertainty. As uncertainty decreases, information gain shrinks toward zero, and the pragmatic term dominates -- the agent exploits to satisfy preferences. This transition is automatic and situation-dependent, not scheduled or tuned.

Recent work by Phan et al. (2025) formalizes this as "sufficient curiosity": there exists a curiosity coefficient beta_t such that:
```
beta_t >= min_x [E[h_t(y)] / I(s; (x,y) | D_{t-1})]
```
When this threshold is met, the agent simultaneously achieves posterior consistency (learns the true model) AND bounded cumulative regret (performs optimally). Below this threshold, myopic exploitation dominates and learning stalls.

The acquisition function unifying both:
```
alpha(x|D_t) = beta_t * I(s; (x,y)|D_t) - E[h(y|D_t)]
```
Curiosity is not an ad-hoc exploration bonus -- it is an intrinsic regularizer coupling belief updating and decision-making.

## 4. Planning as Inference: The 2025 Unification

A persistent criticism of active inference was that EFE was "not directly derivable from a standard Bayesian treatment" (Millidge 2021). The EFE appeared as a separate objective function rather than emerging from first principles.

De Vries & Friston (2025) resolved this via the Expected Free Energy Theorem: when the generative model is augmented with specific epistemic priors encoding information-seeking drives:
- p_tilde(u) = exp(H[q(x|u)]) -- favors policies maximizing state entropy
- p_tilde(x) = exp(-H[q(y|x)]) -- prefers observations reducing ambiguity
- p_tilde(y,x) = exp(D[...]) -- encourages active parameter learning

...then EFE emerges naturally from minimizing a standard variational free energy functional:
```
F[q] = E_q(u)[G(u)] + complexity_term
```

This means planning IS inference. Policy selection is not a separate optimization -- it is the same variational inference that drives perception, just applied to future trajectories. The practical implications:
1. A single objective function governs both perception and action
2. Reactive message passing in factor graphs can implement planning without hand-crafted algorithms
3. A natural complexity term B(u) implements bounded rationality -- computational constraints emerge from the same formalism

## 5. Generalized Free Energy and Optimistic Futures

Friston (2019) introduced the generalized free energy, which treats future observations as latent variables:
```
F_bar = sum_{tau<=t} F_tau  +  sum_{tau>t} G_tau_generalized
```

The key consequence: beliefs about the future can cause the past. More precisely, the agent's expectations about future states create an "optimistic distortion" that biases current inference. An agent that expects to reach a goal state will interpret ambiguous current evidence in ways consistent with being on a trajectory toward that goal.

This is not pathological optimism -- it is rational under active inference because the agent can ACT to make its predictions true. The self-fulfilling prophecy is the mechanism, not a bug.

## 6. Consciousness Integration: IWMT and the FEP

Safron's Integrated World Modeling Theory (IWMT, 2020-2022) provides the deepest synthesis of FEP with consciousness theories:

**IIT connection:** Integrated information (Phi) measures how much information is lost when a system is partitioned. Under FEP, the generative model naturally develops integrated representations because free energy minimization favors compressed, unified world models over fragmented ones. High Phi = rich cross-collection connectivity = better predictions.

**GWT connection:** Self-Organizing Harmonic Modes (SOHMs) -- synchronous neural complexes -- function simultaneously as:
- Dynamic cores of integrated information (IIT)
- Global workspaces broadcasting to all subsystems (GWT)
- Bayesian inference engines minimizing prediction error (FEP)

**Key IWMT proposition:** Consciousness requires not just free energy minimization but world models with spatial, temporal, and causal coherence, coupled with embodied agency. FEP alone is insufficient -- many systems minimize free energy (thermostats, rocks in some trivial sense) but are not conscious. What distinguishes conscious systems is integrated world modeling with self-referential structure.

**AI implications:** Von Neumann architectures cannot generate consciousness through computation alone. However, artificial agents with action-perception loops, integrated self-models, and causal world models could approximate conscious processing.

## 7. Critical Assessment: What Active Inference Does and Does Not Provide

Millidge's 2024 retrospective provides a crucial counterpoint:

**Strengths:**
- Theoretically elegant unification of perception, action, and learning
- Natural exploration via epistemic value (no reward shaping needed)
- Principled uncertainty quantification
- Clean account of attention, curiosity, and planning

**Weaknesses:**
- In practice, active inference and RL are "so close that there is relatively little special sauce above standard RL methods"
- The EFE's exploration advantage has been challenged -- information-maximizing behavior follows from relatively simple mathematical relationships, not uniquely from FEP
- Scaling to continuous, high-dimensional state spaces remains difficult compared to deep RL
- Empirical neuroscience support is weaker than often claimed

**Where it genuinely adds value:**
- Discrete state-space decision tasks (POMDPs with small state spaces)
- Principled handling of partial observability
- Structured generative models where the A/B/C/D structure matches the problem
- Theoretical framework for understanding existing AI systems (including LLMs performing Bayesian-style reasoning)

---

## Application to Clarvis Architecture

### Existing Alignment

Clarvis already implements several active inference components under different names:

| Active Inference Concept | Clarvis Implementation | Gap |
|---|---|---|
| Global Workspace broadcasting | `attention.py` -- GWT spotlight with salience scoring, 7-slot capacity, competition, decay | Missing: EFE-driven salience; items compete by heuristic weights, not expected information gain |
| Generative model / world model | `brain.py` ClarvisDB -- 10 collections, 1200+ memories, 47k+ graph edges | Missing: explicit A/B matrices; graph is associative, not probabilistic-generative |
| Episodic memory with activation | `episodic_memory.py` -- ACT-R power-law activation, causal DAG between episodes | Strong alignment; activation decay mirrors Bayesian belief updating |
| Counterfactual simulation | `dream_engine.py` + `causal_model.py` -- generates "what-if" variations of past episodes | Strong alignment with generalized free energy's "optimistic distortion"; dreams explore counterfactual trajectories |
| Confidence tracking / calibration | `clarvis_confidence.py` -- predictions, outcomes, calibration curves | Maps to precision-weighting in active inference; confidence = inverse variance of predictions |
| Phi metric (IIT proxy) | `phi_metric.py` -- cross-collection connectivity, semantic overlap, reachability | Direct IWMT alignment; measures integration of the generative model |
| Reasoning chains | `clarvis_reasoning.py` + `reasoning_chain_hook.py` -- multi-step inference tracking | Maps to policy evaluation in active inference; each reasoning step is a belief update |
| Task routing by complexity | `task_router.py` -- routes SIMPLE/MEDIUM/COMPLEX to different models | Crude form of bounded rationality; active inference formalizes this as the complexity term in generalized EFE |

### Critical Gaps

1. **No explicit preference encoding (C matrix):** Clarvis has goals in `clarvis-goals` collection and QUEUE.md, but they are not formalized as a prior distribution over preferred observations. The heartbeat preflight selects tasks by attention scoring, not by expected free energy evaluation.

2. **No transition model (B matrix):** The system lacks an explicit model of "if I take action X in state S, the next state will be S'." The causal graph in episodic memory captures PAST causal links but does not predict FUTURE transitions.

3. **Exploration is ad-hoc:** Research tasks are scheduled by cron (2x/day), not driven by epistemic value. The system does not assess "where is my uncertainty highest?" to decide what to investigate.

---

## Concrete Implementation Ideas

### Idea 1: EFE-Scored Task Selection in Heartbeat Preflight

Replace or augment the current salience scoring in `heartbeat_preflight.py` with Expected Free Energy evaluation of candidate tasks.

**Current flow:** attention.py scores tasks by `W_IMPORTANCE * importance + W_RECENCY * recency + W_RELEVANCE * relevance + W_ACCESS * access + W_BOOST * boost`

**Proposed flow:**
```python
def evaluate_task_efe(task, brain_state):
    """Score a task by its Expected Free Energy."""
    # Pragmatic value: how much does this task advance preferences?
    # Use C vector = goal embeddings from clarvis-goals collection
    goal_embeddings = brain.get_collection_embeddings("clarvis-goals")
    task_embedding = brain.embed(task.description)
    pragmatic_value = max_cosine_similarity(task_embedding, goal_embeddings)

    # Epistemic value: how much uncertainty does this task reduce?
    # Estimate information gain by: how novel is this task's domain?
    domain_memories = brain.search(task.description, top_k=10)
    memory_density = len([m for m in domain_memories if m.score > 0.7])
    epistemic_value = 1.0 / (1.0 + memory_density)  # High when few relevant memories exist

    # Ambiguity: how uncertain is the outcome?
    confidence_prediction = conf_predict(task.description)
    ambiguity = 1.0 - confidence_prediction  # High ambiguity = high information potential

    # EFE = -epistemic - pragmatic (lower is better, so negate for scoring)
    beta = adaptive_curiosity_coefficient(brain_state)
    efe_score = beta * epistemic_value + (1.0 - beta) * pragmatic_value

    return efe_score

def adaptive_curiosity_coefficient(brain_state):
    """Implement sufficient curiosity threshold from Phan et al. 2025."""
    phi = current_phi_metric()
    pi = current_performance_index()
    # High curiosity when integration is low or performance is dropping
    if phi < 0.5 or pi < 0.4:
        return 0.7  # Explore more
    elif phi > 0.8 and pi > 0.7:
        return 0.3  # Exploit more
    else:
        return 0.5  # Balanced
```

This replaces five ad-hoc weights with a principled two-component score grounded in active inference theory. The curiosity coefficient adapts based on the system's current state (Phi integration + Performance Index), implementing the sufficient curiosity threshold.

### Idea 2: Transition Model from Episodic Causal Graph

Build a lightweight B matrix (transition model) from the existing causal DAG in `episodic_memory.py`.

**Approach:** The causal links already record `caused`, `enabled`, `blocked`, `fixed`, `retried` relationships between episodes. These can be converted into transition probabilities:

```python
def build_transition_model(episodes, causal_links):
    """Build a B-like transition model from episodic causal graph.

    States = task categories (evolution, maintenance, research, etc.)
    Actions = task selection choices
    B[next_category, current_category, action] = P(next outcome | current state, choice)
    """
    categories = extract_task_categories(episodes)
    n_cat = len(categories)

    # Count transitions: when we did task type X after state Y, what happened?
    B = np.zeros((n_cat, n_cat, n_cat))  # outcome x state x action

    for link in causal_links:
        src_ep = episodes[link["source"]]
        dst_ep = episodes[link["target"]]
        src_cat = categorize(src_ep)
        dst_cat = categorize(dst_ep)
        outcome_cat = categorize_outcome(dst_ep)

        if link["type"] in ("caused", "enabled"):
            B[outcome_cat, src_cat, dst_cat] += 1.0
        elif link["type"] == "blocked":
            B[outcome_cat, src_cat, dst_cat] -= 0.5  # Negative evidence

    # Normalize columns to get probability distributions
    B = normalize_columns(B + 1e-6)  # Dirichlet smoothing
    return B
```

This enables the system to predict: "If I am in state X and I choose to work on task type Y, the likely outcome state is Z." Combined with the EFE scorer, this allows multi-step planning: evaluate sequences of tasks by their cumulative expected free energy, not just single-task salience.

### Idea 3: Dream Engine as Generalized Free Energy Exploration

Upgrade the dream engine from random counterfactual generation to targeted epistemic foraging. Under generalized free energy, future observations are latent variables -- dreams should explore futures with high epistemic value.

**Current flow:** `dream_engine.py` selects recent episodes and generates random "what-if" variations.

**Proposed flow:**
```python
def epistemic_dream_cycle(n_dreams=10):
    """Dream about futures with highest expected information gain."""
    # 1. Identify high-uncertainty domains
    all_collections = brain.stats()
    uncertainty_map = {}
    for collection, stats in all_collections.items():
        # Low count + low cross-links = high uncertainty
        density = stats["count"] / max(stats["max_possible"], 1)
        cross_links = phi_metric.cross_collection_edges(collection)
        uncertainty_map[collection] = 1.0 - (0.5 * density + 0.5 * cross_links)

    # 2. Select episodes from high-uncertainty domains
    high_uncertainty_domains = sorted(uncertainty_map, key=uncertainty_map.get, reverse=True)[:3]
    dream_candidates = []
    for domain in high_uncertainty_domains:
        episodes = episodic_memory.recall_by_collection(domain, top_k=5)
        dream_candidates.extend(episodes)

    # 3. Generate counterfactuals that would REDUCE uncertainty
    for episode in dream_candidates[:n_dreams]:
        # Instead of random perturbation, target the uncertain variables
        uncertain_vars = identify_uncertain_variables(episode, uncertainty_map)
        counterfactual = generate_targeted_counterfactual(episode, uncertain_vars)

        # 4. Evaluate the dream: did it produce new insights?
        insight = evaluate_dream_insight(counterfactual)
        if insight.information_gain > threshold:
            store_dream_insight(insight)
            # Feed back into attention system with epistemic boost
            attention.submit(
                insight.summary,
                source="dream_engine",
                importance=insight.information_gain,
                boost=0.3  # Epistemic dreams get attention boost
            )
```

This makes dreaming an active inference process: the system dreams about what it is most uncertain about, generating counterfactuals that target gaps in the generative model, and feeds high-information-gain insights back into the attention spotlight.

---

## Key Takeaways for Clarvis

1. **Active inference is not just "minimize surprise" -- it is a complete decision-making framework** where action selection, perception, learning, and exploration all emerge from a single variational objective. Clarvis's architecture already has many of the pieces (GWT attention, episodic memory, counterfactual dreams, confidence tracking, Phi metric) but they operate as separate heuristic modules rather than as a unified inference process.

2. **The Expected Free Energy decomposition into epistemic + pragmatic value is the key operational insight.** Every task selection, every research topic, every dream target should be evaluated by: "How much do I learn?" (epistemic) + "How much does this advance my goals?" (pragmatic). The balance is automatic, not a hyperparameter.

3. **Planning as inference (2025) resolves the theoretical gap** that critics identified. EFE is not a separate objective -- it emerges from variational inference on augmented generative models. This means Clarvis could implement a single free-energy-minimization loop that handles both "what do I believe?" and "what should I do?" without separate scoring mechanisms.

4. **The sufficient curiosity threshold (Phan et al. 2025) provides a formal criterion** for when to explore vs exploit. Clarvis can use its own Phi metric and Performance Index as proxies for the curiosity coefficient: low integration or dropping performance triggers exploration mode; high integration with stable performance triggers exploitation.

5. **The IWMT connection validates Clarvis's existing architecture.** Having GWT attention + IIT Phi metric + episodic memory + causal models is exactly what IWMT identifies as the necessary components for integrated world modeling. The gap is formalization: connecting these components through a shared probabilistic framework rather than ad-hoc scoring weights.

6. **Practical scaling concerns are real.** The pymdp discrete state-space framework works for small problems but Clarvis operates in a vast, continuous space of tasks and knowledge. The implementation ideas above use embedding-space approximations (cosine similarity as a proxy for probabilistic matching) rather than exact Bayesian inference, which is the pragmatic path.

7. **The dream engine is Clarvis's strongest active-inference-aligned component.** Counterfactual dreaming IS generalized free energy exploration -- treating future observations as latent variables and simulating trajectories to reduce uncertainty. Upgrading it from random to epistemic-value-targeted dreaming would be the highest-impact single change.

---

**Sources:**
- [Generalised Free Energy and Active Inference (Friston 2019)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6848054/)
- [Active Inference: The Free Energy Principle in Mind, Brain, and Behavior (Parr, Pezzulo, Friston 2022, MIT Press)](https://mitpress.mit.edu/9780262045353/active-inference/)
- [Whence the Expected Free Energy (Millidge et al. 2021)](https://direct.mit.edu/neco/article/33/2/447/95645/Whence-the-Expected-Free-Energy)
- [EFE-based Planning as Variational Inference (de Vries & Friston 2025)](https://arxiv.org/html/2504.14898v2)
- [Reframing the Expected Free Energy (2024)](https://arxiv.org/pdf/2402.14460)
- [Integrated World Modeling Theory (Safron 2020)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7861340/)
- [IWMT Expanded (Safron 2022)](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2022.642397/full)
- [pymdp: Active Inference in Discrete State Spaces (Heins et al. 2022)](https://github.com/infer-actively/pymdp)
- [pymdp Tutorial: Active Inference from Scratch](https://pymdp-rtd.readthedocs.io/en/latest/notebooks/active_inference_from_scratch.html)
- [A Retrospective on Active Inference (Millidge 2024)](https://www.beren.io/2024-07-27-A-Retrospective-on-Active-Inference/)
- [Curiosity is Knowledge: Self-Consistent Learning and No-Regret Optimization (Phan et al. 2025)](https://arxiv.org/abs/2602.06029)
- [Active Inference, Curiosity and Insight (Friston et al. 2017)](https://pubmed.ncbi.nlm.nih.gov/28777724/)
- [Active Inference and Epistemic Value (Friston et al. 2015)](https://www.fil.ion.ucl.ac.uk/~karl/Active%20inference%20and%20epistemic%20value.pdf)
- [Bayesian Brain Computing and the Free-Energy Principle (Friston interview, NSR 2024)](https://academic.oup.com/nsr/article/11/5/nwae025/7571549)
- [Deep Active Inference Agents Using Monte-Carlo Methods (Fountas et al. 2020, NeurIPS)](https://proceedings.neurips.cc/paper/2020/file/865dfbde8a344b44095495f3591f7407-Paper.pdf)
