# World Models: From Neural Dreaming to Cognitive Planning

**Research synthesis** | Key period: 2018--2025 | Ingested: 2026-02-27

## Foundational Authors & Papers

| Paper | Authors | Year | Venue | Key Contribution |
|-------|---------|------|-------|-----------------|
| World Models | David Ha, Jurgen Schmidhuber | 2018 | arXiv 1803.10122 | V-M-C architecture: VAE + MDN-RNN + linear controller |
| DreamerV1/V2/V3 | Danijar Hafner et al. | 2020--2025 | ICLR / Nature | RSSM latent dynamics, actor-critic in imagination |
| I-JEPA / V-JEPA / V-JEPA 2 | Yann LeCun, Mahmoud Assran, Adrien Bardes et al. (Meta FAIR) | 2023--2025 | CVPR / arXiv | Joint embedding prediction (latent-space, not pixel-space) |
| IRIS | Eloi Alonso, Vincent Micheli, Francois Fleuret | 2023 | ICLR (notable top 5%) | Discrete autoencoder + autoregressive transformer world model |
| DIAMOND | Eloi Alonso et al. | 2024 | NeurIPS Spotlight | Diffusion-based world model; visual details matter |
| Genie 2 / 3 | Google DeepMind | 2024--2025 | Blog / internal | Foundation world models: interactive 3D from video, real-time |
| Free Energy Principle / Active Inference | Karl Friston | 2006--present | Various | Organisms minimize variational free energy via world models |
| GWT + Internal Simulation | Murray Shanahan (extending Bernard Baars) | 2005 | Consciousness & Cognition | Cognitive architecture combining global workspace with simulation loops |

---

## Key Idea 1: The V-M-C Decomposition (Ha & Schmidhuber 2018)

The foundational architecture decomposes an agent into three components:

- **V (Vision Model)**: A Variational Autoencoder that compresses high-dimensional observations into a compact latent vector `z_t`. The encoder maps observation `o_t -> z_t`; the decoder reconstructs `z_t -> o_hat_t`. This creates a learned, compressed state space.
- **M (Memory/Dynamics Model)**: An MDN-RNN (Mixture Density Network + Recurrent Neural Network) that predicts the *distribution* of future latent states: `P(z_{t+1} | z_t, a_t, h_t)`. Because environments are stochastic, M outputs a probability density (Gaussian mixture) rather than a point prediction. The hidden state `h_t` serves as a compressed summary of all history.
- **C (Controller)**: A deliberately simple linear controller mapping `[z_t, h_t] -> a_t`. Trained via CMA-ES (Covariance Matrix Adaptation Evolution Strategy), not gradient descent. The simplicity forces V and M to learn meaningful representations.

**Critical insight: "Dreaming"**. Once V and M are trained, the agent can train C entirely inside the world model -- generating imagined rollouts without interacting with the real environment. Ha & Schmidhuber showed this works on CarRacing-v0 and VizDoom, but also demonstrated a failure mode: the agent can learn to exploit imperfections in the world model (the "dreamer's curse" or "model exploitation").

**Relevance to Clarvis**: The V-M-C decomposition maps to Clarvis's architecture as: V = brain.recall() embeddings (ONNX MiniLM perception), M = episodic_memory + causal_links (dynamics/history), C = heartbeat preflight task selection + Claude Code executor (action selection). The current dream_engine.py lacks a true M -- it uses template-based counterfactuals rather than a learned dynamics model.

---

## Key Idea 2: Latent Dynamics and Imagination Training (DreamerV3)

DreamerV3 (Hafner et al., published in Nature 2025, first arXiv 2023) represents the state of the art in model-based RL with a single fixed hyperparameter configuration across 150+ diverse tasks.

### RSSM Architecture (Recurrent State-Space Model)

The world model has five sub-networks:

1. **Sequence model**: `h_t = f_phi(h_{t-1}, z_{t-1}, a_{t-1})` -- deterministic recurrent state (GRU-like), aggregates history
2. **Encoder**: `z_t ~ q_phi(z_t | h_t, o_t)` -- posterior, uses current observation
3. **Dynamics predictor**: `z_hat_t ~ p_phi(z_t | h_t)` -- prior, predicts without observation (used during imagination)
4. **Reward predictor**: `r_t ~ p_phi(r_t | h_t, z_t)` -- predicts reward from state
5. **Continue predictor**: `c_t ~ p_phi(c_t | h_t, z_t)` -- predicts episode termination

### Categorical Discrete Representations

The latent state `z_t` is represented as **32 categorical variables, each with 32 classes** (total: 32 x 32 = 1024-dimensional one-hot composite). This is a departure from Gaussian latents used in DreamerV1/V2. Categorical representations:
- Are more expressive for multimodal distributions
- Avoid posterior collapse more easily
- Use **1% uniform mixing (unimix)**: each categorical has 1% probability spread uniformly, preventing hard zero probabilities

### Symlog Transform

A key robustness technique: `symlog(x) = sign(x) * ln(|x| + 1)`. Applied to:
- Encoder inputs (squash observations)
- Decoder outputs
- Reward predictions
- Critic value estimates
This handles environments with reward magnitudes spanning orders of magnitude.

### Actor-Critic in Imagination

The policy (actor) and value function (critic) are trained **entirely on imagined trajectories**:
1. Start from a real encoded state `(h_t, z_t)`
2. Roll out H steps using only the dynamics predictor (no observations needed)
3. Actor outputs actions; dynamics model produces next states; reward model produces rewards
4. Actor trained with REINFORCE; Critic trained with lambda-returns
5. **Crucially: gradients do NOT backpropagate through the world model** -- actor/critic and world model are separate optimization problems

### KL Balancing and Free Bits

The world model loss includes a KL divergence term between encoder (posterior) and dynamics (prior):
- **KL balancing**: 80% of the gradient goes to the prior (teach the dynamics to predict better), 20% to the posterior (don't collapse the encoder)
- **Free bits**: KL clipped below 1 nat to prevent degenerate solutions where dynamics are trivial but uninformative

**Relevance to Clarvis**: DreamerV3's imagination training is the gold standard for what Clarvis's dream engine could become. The current dream_engine.py generates counterfactuals via template matching; a proper world model would *learn* the dynamics of Clarvis's operational environment (what causes failures, what enables successes, how tasks chain) and generate imagined trajectories for policy improvement.

---

## Key Idea 3: JEPA vs Generative World Models (LeCun / Meta FAIR)

LeCun's core thesis (articulated in the "A Path Towards Autonomous Machine Intelligence" position paper, 2022): **world models should predict in latent space, not pixel space**.

### The JEPA Principle

In a generative world model (VAE, diffusion, autoregressive pixel prediction):
- Predict: `o_{t+1} = f(o_t, a_t)` (next observation in pixel/token space)
- Problem: most pixel-level details are irrelevant for planning; prediction is expensive and brittle

In JEPA:
- Predict: `s_{t+1} = f(s_t, a_t)` where `s = encoder(o)` (next *representation* in embedding space)
- The encoder discards irrelevant details; the predictor only models task-relevant dynamics
- No decoder needed -- you never reconstruct pixels
- This is more efficient and focuses on semantics

### The JEPA Family

- **I-JEPA** (Image, 2023): Uses a context block from one part of an image to predict masked target representations in another part. Self-supervised, no contrastive pairs, no augmentations. Learns semantic features.
- **V-JEPA** (Video, 2024): Predicts masked spatio-temporal regions in video. Trained on 2M+ unlabeled videos. First large-scale video JEPA with "frozen evaluation" capability (pre-trained encoder + predictor; only a lightweight head is trained for downstream tasks).
- **V-JEPA 2** (2025): The breakthrough -- **first JEPA that works as a world model for robotics planning**:
  - 1.2B parameter ViT encoder
  - Phase 1: Self-supervised pretraining on 1M+ hours of video and 1M images (no action labels)
  - Phase 2: Fine-tuned on just 62 hours of robot data with action sequences
  - Planning via Model Predictive Control: encoder embeds current + goal states; predictor evaluates candidate action sequences by imagining consequences in latent space; best action executed; re-plan every step
  - **65--80% success rate** on pick-and-place tasks in *unseen environments*
  - Benchmark: 77.3% top-1 on Something-Something v2, 39.7 recall@5 on Epic-Kitchens-100
- **VL-JEPA** (Vision-Language, 2025): Predicts continuous text embeddings instead of generating tokens. 50% fewer trainable parameters than standard VLMs with stronger performance.
- **C-JEPA** (Contrastive, 2025): Adds VICReg-style variance/covariance regularization to I-JEPA for greater stability.

### Why This Matters for Cognitive Architecture

JEPA's latent-space prediction is analogous to how the brain does **mental simulation**: you don't re-render the full visual scene when imagining walking down a hallway -- you predict abstract state changes (where walls are, what's around the corner). This is computationally cheaper and more robust than pixel-level imagination.

**Relevance to Clarvis**: Clarvis already operates in embedding space (ChromaDB MiniLM vectors). The JEPA insight suggests that dream_engine.py should predict *in embedding space* -- given an episode embedding and a hypothetical action, predict the resulting embedding of the outcome, rather than generating natural-language counterfactuals. This is how V-JEPA 2 enables robot planning.

---

## Key Idea 4: Transformer and Diffusion World Models (IRIS, DIAMOND)

### IRIS (Alonso, Micheli, Fleuret -- ICLR 2023)

Architecture: **Discrete autoencoder + Autoregressive Transformer**.

1. Observations are tokenized into discrete tokens via a VQ-VAE-style autoencoder
2. The world model is an autoregressive transformer that predicts the next token sequence (actions + observation tokens) given history
3. The policy is trained **entirely on imagined trajectories** generated by the transformer

Performance: Mean human-normalized score of 1.046 on Atari 100k. Superhuman on 10/26 games after only 2 hours of real-time experience. This demonstrated that transformers can serve as effective world models, treating dynamics prediction as sequence modeling.

**Delta-IRIS**: Encodes *stochastic deltas* between timesteps rather than full frames, reducing redundancy.

### DIAMOND (Alonso et al. -- NeurIPS 2024 Spotlight)

Architecture: **Diffusion model as world model**.

Key insight: Discrete tokenization (as in IRIS) can discard visual details that are important for RL. A diffusion model preserves full visual fidelity.

1. Uses EDM noise schedule (Karras et al. 2022) -- stable even at single-step denoising
2. Actions are conditioned directly alongside previous frames
3. Stochastic environments (e.g., Boxing) benefit from n=3 denoising steps for mode selection; deterministic elements work with n=1
4. Mean human-normalized score of **1.46** on Atari 100k -- 46% better than human, new state of the art for world-model-trained agents
5. Extended to serve as an interactive "neural game engine" (trained on Counter-Strike: GO gameplay)

**The key debate**: IRIS/discrete approaches are faster but lose detail; DIAMOND/diffusion approaches are more faithful but computationally heavier. DreamerV3's categorical approach sits between them.

**Relevance to Clarvis**: The IRIS approach of treating dynamics as sequence modeling is directly applicable to Clarvis's text-based operational domain. Episodes are already sequences of (context, action, outcome). A transformer trained on episode sequences could predict outcomes of novel action sequences -- true learned dynamics.

---

## Key Idea 5: Foundation World Models (Genie 2, Genie 3)

Google DeepMind's Genie line represents the scaling hypothesis applied to world models: train a single massive model on diverse video data to create a *foundation world model* -- a general-purpose simulator.

### Genie 2 (December 2024)

- **Architecture**: Autoregressive latent diffusion model with a large transformer backbone
- **Pipeline**: Video frames -> autoencoder -> latent tokens -> causal transformer (processes latents with causal mask, like an LLM) -> autoregressive frame-by-frame generation
- **Action conditioning**: Keyboard/mouse inputs + classifier-free guidance for controllability
- **Capabilities**: Object interactions (balloons, doors, explosives), character animation, NPC behavior, water/smoke/particle effects, gravity, lighting (point + directional), reflections/bloom
- **Memory**: Remembers parts of the world no longer in view; renders them accurately on return
- **Consistency**: 10--60 seconds of coherent world simulation
- **Counterfactuals**: Can generate diverse trajectories from the same starting frame
- **Use case**: Rapid prototyping of RL training environments (used with DeepMind's SIMA agents)

### Genie 3 (August 2025)

- **~11 billion parameters** across specialized sub-networks (object permanence, physics, lighting, textures, interactions)
- **Real-time**: 24 fps at 720p (first real-time world model)
- **Consistency**: Several minutes (vs 10--60s for Genie 2)
- **Visual memory**: Extends ~1 minute back
- Uses latent "visual and spatio-temporal tokens" rather than raw pixels
- Novel attention mechanism for both local (frame-to-frame) and global (world state) coherence
- DeepMind positions this as "a key stepping stone on the path to AGI" -- unlimited curriculum of simulation environments for agent training

**Relevance to Clarvis**: Genie's approach of training world models on observational data (without action labels in phase 1) is directly relevant. Clarvis has 1200+ brain memories and extensive episode history. A small-scale "text world model" could be trained on this operational history to simulate Clarvis's environment dynamics.

---

## Key Idea 6: Cognitive Science Foundations

### Predictive Processing and Free Energy (Friston)

Karl Friston's Free Energy Principle (2006-present) provides the theoretical foundation for why biological organisms maintain world models:

- **Core claim**: All living systems minimize variational free energy -- the divergence between their internal model and actual sensory input
- **Two strategies**: (1) Update the internal model to better match reality (perception/learning); (2) Act on the world to make it match predictions (active inference)
- **Hierarchy**: The brain maintains a hierarchy of generative models predicting at multiple timescales (milliseconds for motor control, hours for planning, years for life goals)
- **Active inference**: Organisms choose actions that minimize *expected* free energy over future horizons, balancing epistemic value (information gain) and pragmatic value (goal achievement)

This is functionally identical to DreamerV3's imagination training: imagine futures, evaluate expected reward (pragmatic) and information gain (epistemic), select actions.

### GWT + Internal Simulation (Shanahan 2005, extending Baars 1988)

Murray Shanahan proposed a cognitive architecture with two interacting sensorimotor loops:

1. **First-order loop**: Direct sensory-motor coupling (stimulus -> response). Fast, reactive.
2. **Higher-order loop**: Internal simulation loop. Takes current state, runs it through a *world model* to predict consequences, feeds predictions back into the decision process. Slow, deliberative.

The Global Workspace (Baars) determines what enters consciousness via salience competition. The simulation loop runs hypothetical scenarios through the same processing pipeline as real perception, but with predicted rather than observed inputs. This is why imagination "feels like" perception.

**Key architectural insight**: Planning = running the first-order sensorimotor loop offline, with the world model substituting for the environment. This is exactly what DreamerV3 does.

### Mental Simulation and Prospection

Prospective simulation (imagining future scenarios) relies on:
- **Hippocampal replay/preplay**: The hippocampus replays past experiences (consolidation) and generates novel sequences (preplay) for planning
- **Prefrontal cortex**: Holds goals and evaluates simulated trajectories against them
- **Default mode network**: Active during mind-wandering and spontaneous mental simulation

**Relevance to Clarvis**: Clarvis already has the GWT architecture (attention.py with salience competition, broadcast). It has episodic memory with activation-based retrieval (ACT-R model in episodic_memory.py). What it lacks is the *simulation loop* -- using a learned dynamics model to generate predicted future states and evaluate them against goals. The dream_engine.py currently does template-based counterfactuals, not learned simulation.

---

## Key Idea 7: The Spectrum of World Model Fidelity

World models exist on a spectrum from abstract to pixel-perfect:

```
Abstract/Efficient                                    Concrete/Expensive
    |                                                        |
    v                                                        v
JEPA latent    DreamerV3      IRIS discrete     DIAMOND      Genie 3
predictions    categorical    VQ-VAE tokens     diffusion    autoregressive
               32x32 cats                       pixel-level  latent diffusion

Planning:      Planning:      Planning:         Planning:    Planning:
MPC in embed   Actor-critic   AC on imagined    AC on        Agent training
space          in imagination trajectories      imagined     in simulation
                                                trajectories
```

Each point on this spectrum trades off:
- **Computational cost**: JEPA is cheapest (no decoder), Genie 3 is most expensive
- **Visual fidelity**: DIAMOND/Genie preserve pixel detail, JEPA/Dreamer abstract away
- **Planning horizon**: Abstract models plan farther (cheaper rollouts), concrete models are limited
- **Task specificity**: Abstract models transfer better, concrete models capture domain details

For Clarvis (a text/memory-based cognitive agent, not a visual agent), the left side of the spectrum is most relevant: **JEPA-style latent prediction and DreamerV3-style imagination in embedding space**.

---

## Application to Clarvis Architecture

### Current State Analysis

Clarvis's `dream_engine.py` (508 lines) implements:
- Episode selection with recency/valence weighting
- 7 counterfactual templates (failure_flip, success_flip, cascading_failure, slow_path, wrong_approach, data_corruption, pearl_intervention)
- Rule-based insight synthesis via domain keyword matching
- Integration with reasoning chains and brain storage

**What it lacks compared to a proper world model**:
1. **No learned dynamics**: Counterfactuals are generated by templates, not by a model that has learned how Clarvis's environment actually works
2. **No latent state prediction**: No embedding-space forward model that predicts what state follows from an action
3. **No imagination rollouts**: Cannot chain multiple steps of prediction to evaluate action sequences
4. **No policy improvement from dreams**: Insights are stored as text but don't directly improve action selection (no actor-critic loop)
5. **No model of environment stochasticity**: Templates assume deterministic outcomes; real operations are probabilistic

### Concrete Implementation Ideas

#### Implementation 1: Episode Dynamics Transformer (Lightweight IRIS for Text)

Build a small transformer that models Clarvis's operational dynamics as sequence prediction over episode embeddings.

**Architecture**:
```
Episode Tokenizer:
  - Input: (task_embedding, context_embedding, action_type, time_features)
  - task_embedding: MiniLM embedding of the task description (384-dim)
  - context_embedding: MiniLM embedding of system state context
  - action_type: one-hot of {implement, fix, research, optimize, test, maintain}
  - time_features: hour_of_day, day_of_week, episodes_in_last_24h

Dynamics Transformer:
  - Input: sequence of K tokenized episodes (context window)
  - Architecture: 4-layer transformer, 256-dim, 4 heads
  - Predicts: next episode embedding + outcome probability + duration estimate
  - Training: self-supervised on Clarvis's 1200+ episode history

Imagination Loop (runs during dream cycle):
  1. Sample a starting state from recent episodes
  2. For each candidate task in QUEUE.md:
     a. Encode task as episode token
     b. Roll out 3-5 steps with dynamics transformer
     c. Score trajectory: P(success) * importance - P(failure) * risk
  3. Re-rank queue by imagined trajectory scores
  4. Store imagination traces in brain as dream insights
```

**Why this works for Clarvis**: Clarvis already generates MiniLM embeddings for everything stored in ChromaDB. The episode history has rich (context, action, outcome) triples. A small transformer (trainable on a NUC CPU with PyTorch) could learn patterns like "research tasks succeed more in morning slots" or "implementation after research has higher success rate" or "back-to-back complex tasks cause failures."

**Training data**: ~1200 episodes in `data/episodes.json`, each with task, outcome, duration, valence, causal links. Augment with episode embeddings from `clarvis-episodes` collection.

#### Implementation 2: Embedding-Space JEPA Predictor (Latent World Model)

Inspired by V-JEPA 2, build a predictor that operates entirely in Clarvis's embedding space.

**Architecture**:
```
State Encoder:
  - brain.recall(current_context, n=10) -> [10 x 384-dim embeddings]
  - Attention pooling -> 384-dim state vector s_t

Action Encoder:
  - Task description -> MiniLM embedding -> 384-dim action vector a_t

JEPA Predictor (lightweight MLP):
  - Input: concat(s_t, a_t) = 768-dim
  - Hidden: 512 -> 256 -> 384
  - Output: predicted next state embedding s_hat_{t+1}
  - Loss: cosine similarity between s_hat_{t+1} and actual s_{t+1}

Planning (Model Predictive Control):
  1. Encode current state s_t from brain context
  2. For each candidate action (task from queue):
     a. Predict s_hat_{t+1} = predictor(s_t, a_t)
     b. Compute value: cosine_sim(s_hat_{t+1}, goal_embedding)
     c. Optionally chain: predict s_hat_{t+2} from s_hat_{t+1}
  3. Select action with highest cumulative value
  4. After execution, compute prediction error |s_{t+1} - s_hat_{t+1}|
  5. High prediction error -> novel situation -> boost exploration
```

**Why this is ideal for Clarvis**: It leverages the existing MiniLM embedding space. No pixel reconstruction needed. The predictor is tiny (an MLP, not a transformer). Training requires only (state, action, next_state) triples extracted from episode history. The planning loop integrates directly with heartbeat_preflight.py's task selection.

**Bonus: Surprise-driven exploration**: When predicted embeddings diverge strongly from actual outcomes, this signals novel situations. These surprise signals can boost salience in attention.py, creating a curiosity-driven exploration loop analogous to DreamerV3's information gain.

#### Implementation 3: Probabilistic Episode Simulator (DreamerV3-Inspired)

The most ambitious option: a full DreamerV3-inspired world model adapted for Clarvis's discrete, text-based domain.

**Architecture**:
```
RSSM adapted for text operations:

Deterministic state h_t (hidden summary of operational history):
  - GRU with 512 units
  - Input: previous stochastic state z_{t-1} + action embedding a_{t-1}

Stochastic state z_t (current situation representation):
  - 8 categorical variables x 16 classes = 128-dim
  - Categories could represent: system_health, task_complexity,
    resource_availability, time_pressure, knowledge_state,
    error_state, queue_state, brain_state
  - Encoder (posterior): z_t ~ Cat(f(h_t, observation_embedding))
  - Prior: z_hat_t ~ Cat(g(h_t))

Reward model:
  - P(success | h_t, z_t) -- binary success prediction
  - Expected_duration(h_t, z_t) -- resource cost prediction
  - Information_gain(h_t, z_t) -- epistemic value (how much we learn)

Continue model:
  - P(system_healthy | h_t, z_t) -- operational continuity

Actor-Critic in Imagination:
  - Actor: selects task from queue given (h_t, z_t)
  - Critic: estimates long-term value V(h_t, z_t)
  - Train on 15-step imagined rollouts (= imagining 15 heartbeats ahead)
  - Actor uses REINFORCE; Critic uses lambda-returns

Training:
  - World model: on episode history (minimize reconstruction + KL)
  - Actor-critic: on imagined trajectories (maximize expected value)
  - Gradients of actor-critic do NOT backprop through world model
```

**Integration with existing systems**:
- Replaces template-based counterfactuals in dream_engine.py with learned simulation
- Imagination rollouts run during the 02:45 dream window
- Actor's task rankings feed into heartbeat_preflight.py attention scores
- Prediction errors stored in brain as "surprise" signals
- KL divergence between prior and posterior tracks how "predictable" the environment is -- sudden KL spikes indicate environmental regime changes

**Training feasibility**: With ~1200 episodes and growing, this is a small dataset. Regularization is critical. Options:
- Data augmentation via the existing template counterfactuals (use them as training data, not inference)
- Pre-train the encoder using brain embeddings (transfer from MiniLM)
- Use the categorical representation (8x16) to limit model capacity and prevent overfitting
- Dropout and weight decay on all components

---

## Summary: The World Models Research Landscape in 2025

The field has converged on several core principles:

1. **Learn a compressed latent representation** of the environment (whether discrete tokens, categorical distributions, or continuous embeddings)
2. **Predict dynamics in latent space**, not in observation space (the JEPA insight)
3. **Train policies on imagined trajectories** to achieve data efficiency orders of magnitude beyond model-free RL
4. **Use the prediction error** as a signal for novelty, exploration, and model improvement
5. **Scale the world model** to foundation-model size for generality across tasks (Genie), or keep it small and domain-specific for efficiency (DreamerV3)
6. **Connect to cognitive science**: world models are the computational equivalent of the brain's predictive processing, active inference, and mental simulation capabilities

For Clarvis specifically, the most impactful path is **Implementation 2** (Embedding-Space JEPA Predictor) as an immediate upgrade, with a roadmap toward **Implementation 3** (Probabilistic Episode Simulator) as the episode dataset grows. The key missing piece in Clarvis today is not the dreaming infrastructure (that exists) but the *learned dynamics model* that turns template-based imagination into principled, data-driven prediction and planning.

---

## Sources

- [Ha & Schmidhuber 2018 - World Models (arXiv)](https://arxiv.org/abs/1803.10122)
- [DreamerV3 - Mastering Diverse Domains (Nature 2025)](https://www.nature.com/articles/s41586-025-08744-2)
- [DreamerV3 - Technical Summary](https://vitalab.github.io/article/2023/01/19/DreamerV3.html)
- [DreamerV3 - GitHub](https://github.com/danijar/dreamerv3)
- [V-JEPA - Meta AI Blog](https://ai.meta.com/blog/v-jepa-yann-lecun-ai-model-video-joint-embedding-predictive-architecture/)
- [V-JEPA 2 - World Model for Robotics (Meta)](https://ai.meta.com/blog/v-jepa-2-world-model-benchmarks/)
- [V-JEPA 2 - arXiv Paper](https://arxiv.org/abs/2506.09985)
- [I-JEPA - Meta AI Blog](https://ai.meta.com/blog/yann-lecun-ai-model-i-jepa/)
- [VL-JEPA - arXiv](https://arxiv.org/abs/2512.10942)
- [IRIS - Transformers as World Models (arXiv)](https://arxiv.org/abs/2209.00588)
- [IRIS - GitHub](https://github.com/eloialonso/iris)
- [DIAMOND - Diffusion World Model (NeurIPS 2024)](https://diamond-wm.github.io/)
- [DIAMOND - arXiv Paper](https://arxiv.org/abs/2405.12399)
- [DIAMOND - GitHub](https://github.com/eloialonso/diamond)
- [Genie 2 - DeepMind Blog](https://deepmind.google/blog/genie-2-a-large-scale-foundation-world-model/)
- [Genie 3 - DeepMind Blog](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/)
- [JEPA Deep Dive - Turing Post](https://www.turingpost.com/p/jepa)
- [JEPA Deep Dive - Rohit Bandaru](https://rohitbandaru.github.io/blog/JEPA-Deep-Dive/)
- [Free Energy Principle - Wikipedia](https://en.wikipedia.org/wiki/Free_energy_principle)
- [Predictive Coding under Free Energy (Friston)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2666703/)
- [Shanahan - GWT + Internal Simulation (2005)](https://www.sciencedirect.com/science/article/abs/pii/S1053810005001510)
- [World Models Overview - rewire.it](https://rewire.it/blog/what-are-world-models-ai-path-to-understanding-reality/)
- [DreamerV3 Evolution Deep Dive](https://www.findingtheta.com/blog/the-evolution-of-imagination-a-deep-dive-into-dreamerv3-and-its-conquest-of-minecraft)
