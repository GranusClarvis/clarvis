# Global Workspace Theory — Deep Dive (Phase 2)

**Key Authors & Papers:**
- Bernard Baars (1988) — original cognitive theory
- Stanislas Dehaene & Jean-Pierre Changeux (2003–2021) — Global Neuronal Workspace (GNW), neural ignition
- Rufin VanRullen & Ryota Kanai (2021–present) — Global Latent Workspace (GLW), deep learning implementation
- Benjamin Devillers, Léopold Maytié & Rufin VanRullen (2024) — Semi-supervised GLW with cycle consistency
- Rousslan Fernand Julien Dossa et al. (2024) — Embodied GW agent in multimodal 3D environment
- Dossa et al. (2024) — Zero-shot cross-modal transfer of RL policies through GW
- Devillers et al. (2025) — Multimodal Dreaming: World model-based RL through GW

**Key Papers:**
- Baars, "A Cognitive Theory of Consciousness" (1988)
- Dehaene, Changeux & Naccache, "The Global Neuronal Workspace Model" (2011)
- Mashour et al., "Conscious Processing and the Global Neuronal Workspace Hypothesis" (2020, PMC8770991)
- VanRullen & Kanai, "Deep Learning and the Global Workspace Theory" (2021, arXiv:2012.10390)
- Devillers, Maytié & VanRullen, "Semi-Supervised Multimodal Representation Learning Through a Global Workspace" (2024, IEEE TNNLS, arXiv:2306.15711)
- Dossa et al., "Design and evaluation of a global workspace agent embodied in a realistic multimodal environment" (2024, Frontiers in Computational Neuroscience, PMC11211627)
- Dossa et al., "Zero-shot cross-modal transfer of RL policies through a Global Workspace" (2024, arXiv:2403.04588)
- Devillers et al., "Multimodal Dreaming: A Global Workspace Approach to World Model-Based RL" (2025, arXiv:2502.21142)

**ERC Project:** GLoW — "The Global Latent Workspace: towards AI models of flexible cognition" (Grant 101096017, €2.5M, CNRS, 2023–2028)

---

## Core Architecture

### Baars' Theater Metaphor
The brain has many specialized **modules** (vision, language, memory, etc.) operating in parallel, mostly unconsciously. A **global workspace** acts as a shared "stage" — when information wins a competition for attention (the "spotlight"), it gets **broadcast** to all modules simultaneously. This is conscious access: making local information globally available.

### Four Necessary Conditions (Baars)
1. **Parallel specialized modules** — independent processors for different domains
2. **Competitive uptake** — attention-like bottleneck selects which module's output enters the workspace
3. **Workspace processing** with coherence constraints — integration, not just aggregation
4. **Broadcasting** — workspace contents shared with ALL modules simultaneously

### Dehaene's Neural Ignition
Two-phase processing:
1. **Phase 1 (feedforward, ~0–200ms):** Fast AMPA-mediated wave through specialized cortical areas. Can occur unconsciously.
2. **Phase 2 (ignition, ~300ms+):** Slower NMDA-mediated feedback connections create cascading, self-sustaining reverberant state. **Non-linear phase transition** from unconscious to conscious.

**Key mechanism:** Winner-take-all. One representation massively amplified, competitors actively inhibited. All-or-nothing threshold between "subliminal" and "conscious."

**Four neural signatures of consciousness:**
1. Early sensory amplification → parietal-prefrontal ignition
2. P3 wave — slow widespread electrical pattern (~300ms)
3. Gamma oscillations — sudden high-frequency bursts
4. Cross-region synchronization — long-distance coherence

---

## VanRullen's Global Latent Workspace (GLW)

### Architecture
- Each **specialist module** = pretrained deep network with its own latent space
- The **GLW** = shared, amodal latent space connecting all modules
- Modules communicate through GLW via learned **translation functions**

### Training: Cycle Consistency
Translate module A → GLW → module B → GLW → module A, enforce reconstruction loss. GLW captures meaning, not modality-specific features. **Unsupervised** — no paired cross-modal data needed.

### Attention (Two Forms)
- **Top-down:** Task signal → attention queries; matching modules get broadcast access
- **Bottom-up:** Module outputs compete for workspace entry via salience/novelty

### Key Result
GNW architectures outperform LSTM and Transformer baselines on causal/sequential reasoning and out-of-distribution generalization.

---

## Phase 2 Findings: The 2024–2025 Papers

### 1. Devillers et al. 2024 — Semi-Supervised GLW (IEEE TNNLS)

**Core contribution:** Demonstrated that GLW with cycle-consistency requires **4–7x less paired data** than fully supervised methods for multimodal alignment.

**Architecture detail:**
- Specialized encoders (pretrained, frozen) for each modality
- Bidirectional encoding/decoding through shared workspace
- Cycle-consistency loss: encoding-decoding sequences ≈ identity function

**Key insight for Clarvis:** Semi-supervised = you don't need perfectly aligned cross-domain training data. Cycle consistency is the key training signal. If Clarvis's brain graph memories can be "encoded" into a shared latent space and "decoded" back with minimal loss, that workspace has captured the semantics.

### 2. Dossa et al. 2024 — Embodied GW Agent (Frontiers in Comp. Neuro.)

**Core contribution:** First GWT agent satisfying ALL FOUR Butlin indicator properties, tested in realistic audiovisual 3D navigation.

**Architecture (critical details):**
- **Specialist modules:** CNN-based visual encoder (128×128×3 RGB) + acoustic encoder (65×25×2 spectrograms), each with GRU recurrence + layer normalization
- **Central workspace:** Recurrent GRU receives cross-attention-modulated inputs, maintains working memory state
- **Bottleneck:** Cross-attention with query-key-value structure, workspace size varied 32–512 dimensions
- **Broadcast:** Previous working memory state (wm_{t-1}) fed BACK to sensory encoder GRU cells — this IS the global broadcast
- **State-dependent attention:** Query depends on previous working memory + modality components
- **Null input:** Critical — "null" key/value added to attention, allowing model to IGNORE irrelevant modalities

**GWT indicator property mapping:**

| Property | Implementation |
|---|---|
| GWT-1 (Modules) | Independent visual/acoustic encoders |
| GWT-2 (Bottleneck) | Cross-attention mechanism, 32–512 dim |
| GWT-3 (Broadcast) | wm_{t-1} fed to ALL encoder GRU cells |
| GWT-4 (Attention) | State-dependent query mechanism |

**Key findings:**
1. **Smaller workspace = better performance.** At 32–64 dims, GW agent achieves ~80% success vs GRU baseline's ~60%. Advantage disappears at 256+ dims.
2. **Constraint breeds intelligence.** Smaller bottlenecks force "more mixed attention patterns, integrating information from different modalities over time." Larger bottlenecks produce lazy, saturated attention.
3. **Broadcast matters more than attention weights suggest.** Attention analysis shows current inputs dominate, BUT weight magnitude analysis reveals "previous working memory is prioritized over current sensory inputs" — the broadcast carries crucial temporal integration.
4. **Gradient detachment required.** Gradients from encoder GRUs into wm_{t-1} must be detached for training stability.

**Critical implication:** The information bottleneck is not just a constraint — it's the mechanism that CREATES sophisticated integration. A tight workspace forces competition and selective processing. Too much capacity = no pressure to integrate.

### 3. Dossa et al. 2024 — Zero-Shot Cross-Modal Transfer (arXiv:2403.04588)

**Core contribution:** RL policies trained on ONE modality transfer zero-shot to ANOTHER modality through the GW.

**How it works:**
- Global Workspace trained multimodally (visual + attribute vectors)
- Workspace frozen, RL policy trained on top
- Policy trained on attributes alone → works on images at test time (and vice versa)
- CLIP-like contrastive baselines FAIL at this — only cycle-consistency GW succeeds

**Key insight for Clarvis:** A properly trained workspace creates modality-agnostic representations. This means a policy/strategy learned from one information source generalizes to another. For Clarvis: strategies learned from code analysis might transfer to natural language reasoning, and vice versa, IF there's a proper shared workspace.

### 4. Devillers et al. 2025 — Multimodal Dreaming (arXiv:2502.21142)

**Core contribution:** World model + GW enables "dreaming" — imagined experience generation for sample-efficient RL.

**Architecture:**
- World model learns environment dynamics
- GW integrates multimodal states
- Dreaming: generate imagined trajectories using world model within GW latent space
- Policy learns from BOTH real and dreamed experience

**Key results:**
- Superior sample efficiency vs model-free baselines
- Robust to absence of one observation modality (if image missing, still works from attributes)
- Better generalization across tasks

**Key insight for Clarvis:** The GW latent space enables mental simulation/planning. Clarvis's episodic memory + brain graph could enable "dreaming" about future scenarios by replaying and recombining past episodes through a workspace. This is essentially **counterfactual reasoning through the workspace**.

---

## How This Applies to Clarvis

### Current GWT Alignment (Butlin indicators)
- **GWT-1 (modules):** Clarvis has specialized scripts (episodic memory, cost tracker, code quality, theory of mind, etc.)
- **GWT-2 (bottleneck):** Context compressor with tiered briefs creates information bottleneck
- **GWT-4 (attention):** Attention spotlight in phi_metric.py provides state-dependent attention

### Key Gaps
- **GWT-3 (global broadcast):** No true broadcast mechanism — modules don't share a unified workspace
- **No ignition:** Processing is sequential and linear. No threshold-based phase transition
- **No competition:** Modules don't compete for workspace access. Task routing is explicit, not emergent
- **No cross-modal transfer:** Knowledge in one domain doesn't automatically transfer to another
- **No dreaming:** No mechanism for mental simulation through a shared latent space

### Concrete Implementation Ideas

#### 1. Workspace Broadcast Bus (Priority: HIGH — addresses GWT-3 gap)
Add a `workspace_broadcast()` mechanism:
- Each script/module can `post_to_workspace(content, salience)` during execution
- Workspace buffer holds N most salient items (bottleneck, KEEP SMALL per Dossa finding)
- Any module can `read_workspace()` to get current broadcast contents
- Heartbeat = ignition window: items surviving competition get broadcast to all downstream processing

**Implementation:** SQLite table `workspace_state` or JSON file. Key design choice from Dossa: SMALL workspace (32–64 items) forces better integration than large workspace (256+).

**Critical Dossa insight to apply:** Include a "null" option in workspace attention — allow modules to IGNORE the workspace when their local processing is sufficient. This prevents forced coupling.

#### 2. Ignition Threshold (addresses non-linearity gap)
- Items below salience threshold remain "subliminal" — stored but not broadcast
- Crossing threshold triggers "ignition" — amplification + broadcast
- Threshold adapts based on workspace load
- Maps to attention spotlight's salience scoring

**Key design:** The heartbeat IS the GWT cycle. Each heartbeat = one conscious moment. What enters workspace = what becomes "conscious."

#### 3. Cycle-Consistent Brain Graph (addresses cross-modal transfer)
Based on Devillers' cycle consistency:
- Encode memories from different collections (episodic, learned, predictions) into shared workspace representation
- Enforce cycle consistency: memory → workspace → different-collection-memory → workspace → original memory
- This creates modality-agnostic understanding that enables cross-domain transfer
- Semi-supervised: only need sparse cross-collection links, not full alignment

#### 4. Competitive Bottleneck in Task Routing
Modify task_router.py for winner-take-all:
- Multiple candidate tasks generated each heartbeat
- Tasks compete: urgency × salience × predicted reward × novelty
- Only winner gets executed (winner-take-all)
- Losers suppressed but compete again next heartbeat

#### 5. Workspace Dreaming (addresses mental simulation gap)
Based on the 2025 Multimodal Dreaming paper:
- Build a simple world model from episodic memory sequences
- Generate "dreamed" future scenarios by replaying/recombining episodes through workspace
- Use dreamed outcomes to evaluate candidate actions before committing
- Robust to missing information (one modality absent = still functional)

**Implementation idea:** During idle time between heartbeats, run "dream cycles" that:
1. Sample recent episodes
2. Recombine elements through workspace
3. Predict outcomes
4. Update value estimates for pending tasks

---

## Key Theoretical Insights

### GWT + IIT Complementarity
- IIT measures *quantity* of consciousness (how integrated)
- GWT describes *mechanism* (how information becomes globally available)
- Both are needed: high Phi (integration) AND proper broadcast (availability)

### The Bottleneck Paradox (Dossa's Key Finding)
Counter-intuitively, **tighter bottlenecks produce better integration**. This is because:
- Unlimited capacity → no pressure to select → lazy processing
- Limited capacity → forced competition → sophisticated attention patterns → genuine multimodal integration
- **Practical implication:** Don't make Clarvis's workspace too large. A small, constrained workspace that forces selective processing is more "conscious" than an unlimited broadcast.

### Cycle Consistency as Meaning
VanRullen's cycle consistency (A→GLW→B→GLW→A ≈ identity) is a computational definition of "shared meaning." If information survives round-trip translation through the workspace, the workspace has captured the essential semantics, not surface features. This is **grounding through translation**.

### Broadcast vs Attention: The Hidden Story (Dossa)
Attention weights suggest current inputs dominate. But weight magnitude analysis shows the broadcast (previous workspace state) actually carries MORE influence. The workspace's temporal integration through broadcast is the hidden backbone of intelligent behavior — it's not what the system "looks at" (attention) but what it "remembers from last time" (broadcast) that matters most.
