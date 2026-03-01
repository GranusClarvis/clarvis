# Deep Generative Models: A Comprehensive Survey for Cognitive Agent Architecture

**Research type:** Foundational + Applied survey
**Year range:** 2013--2025
**Ingested:** 2026-02-27
**Relevance to Clarvis:** HIGH -- world models, dream engine, episodic imagination, latent memory representations

---

## Key Authors and Papers

| Paper | Authors | Year | Venue | Core Contribution |
|-------|---------|------|-------|-------------------|
| Auto-Encoding Variational Bayes | Kingma, Welling | 2013 | ICLR 2014 | VAE framework, reparameterization trick, ELBO |
| Generative Adversarial Networks | Goodfellow et al. | 2014 | NeurIPS 2014 | Adversarial training, implicit density models |
| Denoising Diffusion Probabilistic Models (DDPM) | Ho, Jain, Abbeel | 2020 | NeurIPS 2020 | Practical diffusion models, connection to score matching |
| Score-Based Generative Modeling through SDEs | Song, Sohl-Dickstein, Kingma, Kumar, Ermon, Poole | 2021 | ICLR 2021 (Oral) | Unified SDE framework for diffusion/score models |
| High-Resolution Image Synthesis with Latent Diffusion Models | Rombach, Blattmann, Lorenz, Esser, Ommer | 2022 | CVPR 2022 | Latent-space diffusion, foundation of Stable Diffusion |
| Flow Matching for Generative Modeling | Lipman, Chen, Ben-Hamu, Nickel, Le | 2023 | ICLR 2023 | Simulation-free CNF training, OT paths |
| Consistency Models | Song, Dhariwal, Chen, Sutskever | 2023 | ICML 2023 | Single-step generation from diffusion, distillation + standalone training |
| Normalizing Flows for Probabilistic Modeling and Inference | Papamakarios, Nalisnick, Rezende, Mohamed, Lakshminarayanan | 2021 | JMLR | Comprehensive flows survey: RealNVP, Glow, MAF |
| A Tutorial on Energy-Based Learning | LeCun, Chopra, Hadsell | 2006 | Predicting Structured Data | EBM foundations, contrastive divergence |
| World Models | Ha, Schmidhuber | 2018 | NeurIPS 2018 | VAE+MDN-RNN for agent dreaming, learn-in-dream paradigm |
| Generative AI in Depth (survey) | Multiple authors | 2025 | arXiv 2510.21887 | Comprehensive taxonomy: GANs, VAEs, hybrids, DMs |
| Bridging Generative Networks with the Common Model of Cognition | Multiple authors | 2024 | arXiv 2403.18827 | DGMs integrated into cognitive architecture modules |

---

## 1. Variational Autoencoders (VAEs) and the Evidence Lower Bound

**Core idea:** Learn a latent variable model p(x) = integral p(x|z)p(z)dz where inference of the posterior p(z|x) is intractable. Introduce a recognition model (encoder) q_phi(z|x) that approximates the true posterior, and a generative model (decoder) p_theta(x|z).

**Evidence Lower Bound (ELBO):**
```
log p(x) >= E_q[log p(x|z)] - KL(q(z|x) || p(z))
         = ELBO(theta, phi; x)
```

The first term is the reconstruction loss (how well decoded samples match inputs). The second is the KL divergence regularizer that keeps the approximate posterior close to the prior (typically N(0,I)).

**Reparameterization trick:** Instead of sampling z ~ q(z|x) directly (which blocks gradient flow), express z = mu + sigma * epsilon where epsilon ~ N(0,I). This makes the sampling differentiable, enabling end-to-end training with standard SGD.

**Latent space properties:** VAEs produce smooth, continuous latent manifolds where interpolation between points generates semantically meaningful transitions. This is fundamentally different from autoencoders, which produce irregular, disconnected latent spaces.

**Limitation:** VAEs tend to produce blurry outputs because the pixel-wise reconstruction loss and KL regularization push the model toward mode-covering behavior rather than mode-seeking.

**Cognitive relevance:** The latent space of a VAE is a compressed representation of experience -- analogous to how episodic memory encodes the "gist" of events rather than pixel-perfect replays. The smooth interpolation property enables imagination: generating novel experiences by traversing latent space between known episodes.

---

## 2. Generative Adversarial Networks (GANs) and Adversarial Training

**Core idea:** Train two networks in opposition: a Generator G(z) maps noise to data, and a Discriminator D(x) classifies real vs. generated samples. The minimax objective:
```
min_G max_D E_x[log D(x)] + E_z[log(1 - D(G(z)))]
```

GANs are implicit density models -- they never compute p(x) explicitly, but learn to sample from it through adversarial competition.

**Key challenges:** Mode collapse (generator learns to produce only a subset of the data distribution), training instability (generator/discriminator oscillation), no density evaluation.

**Modern extensions:** Wasserstein GAN (WGAN) replaces JS divergence with Earth Mover's distance for smoother gradients. StyleGAN/StyleGAN2 achieve photorealistic synthesis through progressive growing and style-based generation. Conditional GANs (cGAN) enable class-conditional and text-conditional generation.

**Cognitive relevance:** Adversarial training has a direct parallel to Clarvis's existing dream engine, which already performs "adversarial training against own experience" via counterfactual simulation. A discriminator network could learn to distinguish high-quality episodes from low-quality ones, providing a trainable quality signal for the dream engine's counterfactual outputs.

---

## 3. Diffusion Models: Denoising and Score Matching

### 3a. Denoising Diffusion Probabilistic Models (DDPM)

**Core idea:** Define a forward process that gradually adds Gaussian noise to data over T steps until it becomes pure noise, then learn a reverse process that denoises step by step.

**Forward process (fixed):**
```
q(x_t | x_{t-1}) = N(x_t; sqrt(1-beta_t) * x_{t-1}, beta_t * I)
```

**Reverse process (learned):**
```
p_theta(x_{t-1} | x_t) = N(x_{t-1}; mu_theta(x_t, t), sigma_t^2 * I)
```

Training objective reduces to predicting the noise epsilon added at each step:
```
L_simple = E_{t, x_0, epsilon}[||epsilon - epsilon_theta(x_t, t)||^2]
```

Ho et al. (2020) showed this simplified objective, while not the full variational bound, produces the best sample quality. They achieved FID 3.17 on CIFAR-10, matching GANs without adversarial training.

### 3b. Score-Based Models and the SDE Framework

Song & Ermon (2019-2021) showed that diffusion models are equivalent to score-based models that learn the score function (gradient of log probability density):
```
s_theta(x, t) approx nabla_x log p_t(x)
```

The unified SDE framework (Song et al., ICLR 2021) casts the forward process as a continuous-time SDE:
```
dx = f(x,t)dt + g(t)dw
```
with a reverse SDE that can be solved if we know the score at each timestep.

**Score matching** trains the model to match the true score function without knowing the normalizing constant -- this is a critical insight because computing normalizing constants for high-dimensional distributions is intractable.

**Langevin dynamics** then uses the learned score to generate samples by iteratively following the score (gradient ascent on log-density) with added noise.

**Cognitive relevance:** The denoising process is a form of iterative refinement that resembles how memory recall works: starting from a noisy or partial cue and progressively filling in details. Score-based models learn the "direction toward higher probability" at every noise level -- analogous to an attention system that knows which directions in thought-space are more promising.

---

## 4. Latent Diffusion and Computational Efficiency

Rombach et al. (CVPR 2022) introduced Latent Diffusion Models (LDMs), which apply the diffusion process not in pixel space but in the latent space of a pretrained autoencoder:

1. Train a powerful autoencoder (encoder E, decoder D) with perceptual and adversarial losses
2. Run diffusion entirely in the compressed latent space z = E(x)
3. Decode generated latents: x' = D(z')

**Key insight:** Pixel-level details are largely perceptually irrelevant noise. By compressing to a semantically rich latent space first, diffusion can focus on high-level semantic composition while the decoder handles reconstruction fidelity.

This achieved near-optimal balance between computational cost and generation quality, reducing training compute by 4-8x while maintaining or improving sample quality. It became the foundation of Stable Diffusion.

**Cognitive relevance:** This is precisely how a cognitive system should operate -- maintain a compressed semantic representation (like ChromaDB embeddings) and run generative processes at the semantic level rather than at the raw perceptual level. Clarvis's brain already works with MiniLM embeddings; a latent diffusion process over these embeddings could generate novel memory-like representations.

---

## 5. Normalizing Flows: Exact Density via Invertible Transforms

**Core idea:** Transform a simple base distribution (e.g., N(0,I)) through a sequence of invertible, differentiable mappings to produce a complex target distribution. The exact density is computable via the change-of-variables formula:
```
log p(x) = log p(z_0) - sum_{k=1}^{K} log |det(dz_k/dz_{k-1})|
```
where z_0 = f_1^{-1}(f_2^{-1}(...f_K^{-1}(x))).

**Key architectures:**
- **RealNVP** (Dinh et al., 2017): Affine coupling layers that split dimensions and apply elementwise affine transforms, ensuring cheap Jacobian determinants
- **Glow** (Kingma & Dhariwal, 2018): Adds invertible 1x1 convolutions in place of permutations, achieving high-quality image generation
- **MAF/IAF** (Masked Autoregressive / Inverse Autoregressive Flows): Trade off between fast training and fast sampling

**Advantages:** Exact log-likelihood computation, exact inference (both directions), no mode collapse. **Disadvantages:** Architectural constraints from invertibility requirement, generally lower sample quality than GANs/diffusion.

**Cognitive relevance:** Normalizing flows provide exact density estimation, which could replace or augment the importance scoring in Clarvis's brain. Instead of heuristic importance weights (0.0-1.0), a flow model could learn the true density of "important" vs. "routine" memories, enabling principled novelty detection (low-density = novel = worth remembering).

---

## 6. Energy-Based Models: The Unifying Framework

**Core idea:** Define an energy function E_theta(x) that assigns low energy to data-like configurations and high energy elsewhere. The probability is:
```
p_theta(x) = exp(-E_theta(x)) / Z_theta
```
where Z_theta = integral exp(-E_theta(x))dx is the intractable partition function.

**Training via contrastive divergence** (Hinton, 2002): Approximate the gradient of the log-likelihood by running a short MCMC chain from the data distribution, then push down energy of data samples while pushing up energy of MCMC samples.

**Unifying perspective:** VAEs, GANs, diffusion models, and flows can all be understood as different strategies for dealing with the intractable partition function Z:
- **VAEs:** Bound log p(x) from below (ELBO), avoid computing Z
- **GANs:** Learn to sample from p(x) implicitly, never compute p(x) or Z
- **Flows:** Construct p(x) so that Z = 1 by design (normalized)
- **Diffusion/Score:** Learn nabla_x log p(x) = -nabla_x E(x), which cancels Z
- **EBMs (direct):** Estimate Z or its gradients via MCMC (contrastive divergence)

**Modern EBM developments:** Score matching and denoising score matching provide Z-free training objectives that directly estimate the score function. Energy Discrepancies (NeurIPS 2023) introduce a score-independent loss for EBMs.

**Cognitive relevance:** The energy landscape metaphor is deeply relevant to cognitive architecture. Attention/salience scoring (Clarvis's `attention.py` GWT system) is fundamentally an energy function: high-salience items have low energy (they attract processing), low-salience items have high energy (they repel processing). EBMs could formalize the attention system as a learned energy landscape over the memory/task space.

---

## 7. Recent Advances (2023-2025): Flow Matching and Consistency Models

### 7a. Flow Matching (Lipman et al., ICLR 2023)

Replaces the SDE-based training of diffusion models with a simpler regression objective on vector fields. Instead of learning to denoise, the model learns a velocity field v_theta(x,t) that transports samples from noise to data along probability paths.

**Key innovation:** Using Optimal Transport (OT) displacement interpolation to define conditional paths produces straighter trajectories than diffusion paths, enabling faster sampling with fewer function evaluations (often 10-20 steps vs. 100-1000 for DDPM).

**OT-Conditional Flow Matching:** Approximates dynamic optimal transport between noise and data distributions, creating the most efficient transport paths.

Flow matching has become the backbone of Meta's Emu architecture and many 2024-2025 production systems due to its training stability, speed, and compatibility with diverse architectures.

### 7b. Consistency Models (Song et al., ICML 2023)

Map any point on a diffusion ODE trajectory to its origin (the clean data point), enabling single-step generation:
```
f_theta(x_t, t) = x_0  for all t on the same trajectory
```

**Self-consistency property:** For any two points on the same ODE trajectory, the model must produce the same output.

**Two training modes:**
- **Consistency Distillation:** Learn the consistency function from a pretrained diffusion model
- **Consistency Training:** Train from scratch using the self-consistency property alone -- no teacher diffusion model needed

Achieved FID 3.55 on CIFAR-10 for single-step generation (compared to DDPM's 3.17 with 1000 steps). Also supports progressive refinement: using more steps trades compute for quality.

### 7c. 2024-2025 Landscape

The field is converging toward hybrid architectures:
- **Meta Emu3:** Combines flow matching with VAE components for speed/quality tradeoffs
- **Latent Consistency Models:** Apply consistency model distillation in latent space for real-time generation
- **Rectified Flows:** Straighten ODE trajectories via iterative reflow, enabling 1-2 step generation
- **DiT (Diffusion Transformers):** Replace U-Net with Transformer backbone (Sora, SD3)
- The comprehensive 2025 survey (arXiv 2510.21887) proposes a novel taxonomy spanning GANs, VAEs, hybrid GAN-VAE architectures, and Diffusion Models organized by key design principles

---

## Application to Clarvis Architecture

### Current Clarvis Systems That Map to DGMs

| Clarvis Component | Current Implementation | DGM Analog |
|-------------------|----------------------|-------------|
| Dream Engine (`dream_engine.py`) | Template-based counterfactual generation over episodes | World Model (Ha & Schmidhuber): VAE+RNN for imagination |
| Episodic Memory (`episodic_memory.py`) | ACT-R activation model, JSON episodes, causal DAG | Latent variable model: episodes as points in latent space |
| Brain embeddings (ChromaDB + MiniLM) | 384-dim ONNX embeddings, cosine similarity search | Latent space: could be regularized as a VAE latent |
| Attention/GWT (`attention.py`) | Salience scoring, global workspace broadcasting | Energy landscape: EBM over attention/task space |
| Hebbian Memory (`hebbian_memory.py`) | Co-activation strengthening of memory associations | Could be reformulated as learning the score function of a memory distribution |
| Memory Consolidation (`memory_consolidation.py`) | Periodic deduplication and compression | Analogous to VAE encoding: compress redundant memories to their latent gist |

### Concrete Implementation Ideas

#### Implementation 1: Variational Episode Encoder (VEE)

**Goal:** Replace or augment the flat JSON episode format with a learned latent representation that supports smooth interpolation, novelty detection, and generative recall.

**Architecture:**
```
Encoder: episode_features -> mu, log_sigma (384-dim, matching MiniLM)
Decoder: z ~ N(mu, sigma) -> reconstructed episode features
Prior: N(0, I) or learned mixture prior

Training data: All episodes in data/episodes.json (hundreds of episodes)
Loss: reconstruction_loss + beta * KL(q(z|episode) || p(z))
```

**How it works:**
1. Each episode's features (task embedding, outcome, confidence, duration, valence) are encoded into a latent vector
2. The KL term regularizes the space so that interpolation is meaningful
3. **Novelty detection:** New episodes with low p(z) under the prior are flagged as highly novel (worth extra attention)
4. **Imagination:** Sample from the prior or interpolate between episode latents to generate "imagined episodes" for the dream engine
5. **Memory consolidation:** Cluster nearby latent vectors and merge them into prototype episodes

**Integration point:** Augment `episodic_memory.py`'s `encode()` method. Store the latent vector alongside each episode. The dream engine uses latent interpolation instead of template-based counterfactuals.

**Feasibility:** A small VAE (2-layer MLP encoder/decoder, 384-dim latent) can train on CPU in seconds. No GPU required. Compatible with existing ChromaDB storage.

#### Implementation 2: Score-Based Dream Engine

**Goal:** Replace template-based counterfactual generation with a learned generative process that produces realistic alternative episodes by denoising from noise.

**Architecture:**
```
Score network: s_theta(z_t, t) estimates nabla_z log p_t(z)
  where z is the episode latent vector, t is the noise level

Forward process: z_t = sqrt(alpha_t) * z_0 + sqrt(1-alpha_t) * epsilon
Reverse process: iteratively denoise z_T -> z_0 using s_theta
```

**How it works:**
1. Train a small score network on the distribution of episode latent vectors
2. To "dream," start from a noisy version of a real episode and run the reverse process with modified conditioning:
   - **Counterfactual dreaming:** Add noise to a real episode, then denoise with a different outcome conditioning -- the model fills in plausible details consistent with the alternative outcome
   - **Free dreaming:** Start from pure noise, generate entirely novel episode trajectories that are consistent with Clarvis's learned distribution of experiences
   - **Exploration dreaming:** Start from a low-density region of latent space (areas the agent hasn't explored) and denoise toward plausible episodes -- this generates "what might happen if I tried something new?"

3. Dream quality is measured by whether the generated episodes have reasonable activation scores when passed back through the episodic memory system

**Integration point:** Replace the `COUNTERFACTUAL_TEMPLATES` in `dream_engine.py` with score-based generation. The 02:00 cron window runs the diffusion sampling process.

**Feasibility:** A small MLP score network over 384-dim vectors requires minimal compute. 50-100 denoising steps over low-dimensional vectors complete in milliseconds on CPU. The training set is small (hundreds of episodes) but sufficient for learning the local structure of the episode distribution.

#### Implementation 3: Energy-Based Attention Landscape

**Goal:** Replace the heuristic salience scoring in `attention.py` with a learned energy function that captures the true distribution of "worth-attending-to" items.

**Architecture:**
```
Energy function: E_theta(task, context, memory_state) -> scalar
  Low energy = high salience = deserves attention
  High energy = low salience = can be ignored

Training: Contrastive divergence on (attended, not-attended) pairs
  - Positive samples: tasks/items that were actually attended to and led to good outcomes
  - Negative samples: items that were attended to but led to poor outcomes, or items that were ignored
```

**How it works:**
1. The energy function takes a candidate task/memory and the current context (time, recent episodes, queue state) and outputs a scalar energy
2. Low-energy items are selected for the global workspace (GWT broadcasting)
3. The energy landscape is shaped by experience: tasks that led to high-confidence, high-value outcomes gradually get lower energy
4. **Exploration bonus:** Items in high-energy (low-density) regions get a curiosity bonus, pulling the agent toward novel tasks (cf. intrinsic motivation in RL)
5. The energy landscape is periodically visualized (t-SNE of the gradient field) for introspective monitoring

**Integration point:** Augment `attention.py`'s `score_salience()` method. Train the energy function during the 02:45 dream window using episode outcome data. The energy function supplements (not replaces) the existing heuristic scoring.

**Feasibility:** Small MLP energy function (3-layer, 256 hidden) trains quickly on episode data. Contrastive divergence with short MCMC chains (5-10 steps) is computationally trivial for low-dimensional feature vectors. The key challenge is collecting enough positive/negative attention examples, but the existing episode log provides hundreds of labeled outcomes.

---

## Theoretical Connections: DGMs as Cognitive Primitives

### The Free Energy Principle Connection

Karl Friston's Free Energy Principle in neuroscience proposes that biological agents minimize variational free energy -- which is exactly the negative ELBO that VAEs maximize. This is not a metaphor; the mathematics are identical:

```
F = E_q[log q(z|x) - log p(x,z)]    (Friston's free energy)
  = -ELBO                              (VAE's training objective, negated)
```

A cognitive agent that uses a VAE-like architecture for its world model is, in a precise mathematical sense, implementing an approximate version of the Free Energy Principle. This provides a theoretical grounding for why DGMs are not just convenient tools but may be the correct computational framework for cognitive agents.

### Imagination as Latent Traversal

Ha & Schmidhuber's (2018) World Models demonstrated that an agent can:
1. Encode observations into a compressed latent state (VAE encoder)
2. Predict future latent states (MDN-RNN temporal model)
3. Train a policy entirely within the "dream" (generated latent trajectories)
4. Transfer the dream-learned policy to the real environment

This is directly analogous to Clarvis's dream engine, but with a crucial upgrade: instead of template-based counterfactuals, a learned generative model produces counterfactuals that respect the actual statistical structure of Clarvis's experience distribution. The dreams become more realistic and more useful.

### Memory as a Generative Process

The neuroscience view of memory retrieval is that it is a constructive (generative) process, not a lookup. Each recall is a reconstruction from partial cues, influenced by the current context and prior expectations. This maps precisely to:
- **VAE decoding:** z -> reconstructed memory (lossy, context-dependent)
- **Diffusion denoising:** noisy cue -> progressively refined memory
- **Score-based recall:** follow the gradient of log p(memory | cue) to the most probable reconstruction

---

## Summary: Priority Ordering for Clarvis

1. **Variational Episode Encoder (VEE)** -- Highest priority. Small, trainable on CPU, immediately useful for novelty detection and memory consolidation. Augments existing ChromaDB embeddings with principled probabilistic structure.

2. **Score-Based Dream Engine** -- Medium priority. Replaces template-based dreaming with learned generation. Requires VEE to be in place first (operates over episode latents). Makes the dream engine qualitatively more powerful.

3. **Energy-Based Attention** -- Lower priority but high theoretical value. Formalizes the attention system as a learned energy landscape. Requires more training data and careful integration with the existing GWT salience system.

All three implementations are CPU-feasible, require no GPU, and can be built on top of existing Clarvis infrastructure (ChromaDB, episodes.json, attention.py) without breaking changes.

---

## Sources

- [Auto-Encoding Variational Bayes (Kingma & Welling, 2013)](https://arxiv.org/abs/1312.6114)
- [Denoising Diffusion Probabilistic Models (Ho et al., 2020)](https://arxiv.org/abs/2006.11239)
- [Score-Based Generative Modeling through SDEs (Song et al., 2021)](https://arxiv.org/abs/2011.13456)
- [Yang Song's Blog: Generative Modeling by Estimating Gradients](https://yang-song.net/blog/2021/score/)
- [High-Resolution Image Synthesis with Latent Diffusion Models (Rombach et al., 2022)](https://arxiv.org/abs/2112.10752)
- [Flow Matching for Generative Modeling (Lipman et al., 2023)](https://arxiv.org/abs/2210.02747)
- [Consistency Models (Song et al., 2023)](https://arxiv.org/abs/2303.01469)
- [Normalizing Flows for Probabilistic Modeling and Inference (Papamakarios et al., 2021)](https://arxiv.org/abs/1912.02762)
- [A Tutorial on Energy-Based Learning (LeCun et al., 2006)](http://yann.lecun.com/exdb/publis/pdf/lecun-06.pdf)
- [World Models (Ha & Schmidhuber, 2018)](https://arxiv.org/abs/1803.10122)
- [Generative AI in Depth: Survey (2025)](https://arxiv.org/html/2510.21887v1)
- [Bridging Generative Networks with the Common Model of Cognition (2024)](https://arxiv.org/html/2403.18827)
- [Cambridge MLG: Introduction to Flow Matching (2024)](https://mlg.eng.cam.ac.uk/blog/2024/01/20/flow-matching.html)
- [Lil'Log: What are Diffusion Models? (2021)](https://lilianweng.github.io/posts/2021-07-11-diffusion-models/)
- [On Using Generative Models in a Cognitive Architecture for Embodied Agents (AAAI 2023)](https://ojs.aaai.org/index.php/AAAI-SS/article/view/27684)
- [Open Encyclopedia of Cognitive Science: Generative Modeling](https://oecs.mit.edu/pub/oye8m8nz)
- [Generative AI Survey (Springer, 2025)](https://link.springer.com/article/10.1186/s40537-025-01247-x)
