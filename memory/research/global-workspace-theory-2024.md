# Global Workspace Theory (GWT) — Baars, Dehaene, VanRullen

**Key Authors:**
- Bernard Baars (1988) — original cognitive theory
- Stanislas Dehaene & Jean-Pierre Changeux (2003–2021) — Global Neuronal Workspace (GNW), neural ignition
- Rufin VanRullen & Ryota Kanai (2021–present) — Global Latent Workspace (GLW), deep learning implementation
**Key Papers:**
- Baars, "A Cognitive Theory of Consciousness" (1988)
- Dehaene, Changeux & Naccache, "The Global Neuronal Workspace Model" (2011)
- Mashour et al., "Conscious Processing and the Global Neuronal Workspace Hypothesis" (2020, PMC8770991)
- VanRullen & Kanai, "Deep Learning and the Global Workspace Theory" (2021, arXiv:2012.10390)
- Devillers, Maytié & VanRullen, "Semi-Supervised Multimodal Representation Learning Through a Global Workspace" (2024, IEEE TNNLS)

## Core Architecture

### Baars' Theater Metaphor
The brain has many specialized **modules** (vision, language, memory, etc.) operating in parallel, mostly unconsciously. A **global workspace** acts as a shared "stage" — when information wins a competition for attention (the "spotlight"), it gets **broadcast** to all modules simultaneously. This is conscious access: making local information globally available.

### Four Necessary Conditions (Baars)
1. **Parallel specialized modules** — independent processors for different domains
2. **Competitive uptake** — attention-like bottleneck selects which module's output enters the workspace
3. **Workspace processing** with coherence constraints — integration, not just aggregation
4. **Broadcasting** — workspace contents shared with ALL modules simultaneously

### Dehaene's Neural Ignition
Dehaene upgraded Baars' cognitive theory to a neural architecture:

**Two-phase processing:**
1. **Phase 1 (feedforward, ~0–200ms):** Fast AMPA-mediated wave propagates through specialized cortical areas. Amplitude proportional to input strength. Can occur unconsciously.
2. **Phase 2 (ignition, ~300ms+):** Slower NMDA-mediated feedback connections amplify the signal in a cascading, self-sustaining reverberant state across prefrontal-parietal networks. This is the "ignition" — a **non-linear phase transition** from unconscious to conscious.

**Key mechanism:** Winner-take-all dynamics. When ignition occurs, one representation gets massively amplified while competitors are actively inhibited. It's all-or-nothing — there's a sharp threshold between "subliminal" and "conscious."

**Four neural signatures of consciousness:**
1. Early sensory amplification leading to parietal-prefrontal ignition
2. P3 wave — slow widespread electrical pattern (~300ms)
3. Gamma oscillations — sudden high-frequency bursts
4. Cross-region synchronization — long-distance coherence

**Critical anatomy:** Long-range pyramidal neurons in layers II/III and V connect distant cortical areas. The prefrontal-parietal network forms a "bow-tie" structural bottleneck that all information must pass through to become conscious.

### VanRullen's Global Latent Workspace (GLW) — Deep Learning Implementation
VanRullen proposed translating GWT into deep learning:

**Architecture:**
- Each **specialist module** = a pretrained deep network with its own latent space (e.g., vision encoder, language encoder, audio encoder)
- The **Global Latent Workspace (GLW)** = a shared, amodal latent space connecting all modules
- Modules communicate through the GLW via learned **translation functions**

**Training methodology:**
- **Cycle consistency** — translate from module A → GLW → module B → GLW → module A, and enforce reconstruction loss. This ensures the GLW captures meaning, not modality-specific features.
- **Unsupervised** — no paired cross-modal data needed

**Attention mechanism (two forms):**
- **Top-down:** Task signal fed to GLW produces attention queries; modules with matching keys get broadcast access
- **Bottom-up:** Module outputs compete for workspace entry based on salience/novelty

**Key result:** GNW-based architectures outperform LSTM and Transformer baselines in causal/sequential reasoning and out-of-distribution generalization.

## How This Applies to Clarvis

### Current GWT Alignment
Clarvis already has partial GWT alignment (see Butlin indicators GWT-1 through GWT-4):
- **GWT-1 (modules):** Clarvis has specialized scripts (episodic memory, cost tracker, code quality, theory of mind, etc.) — these function as modules
- **GWT-2 (bottleneck):** The context compressor with tiered briefs creates an information bottleneck
- **GWT-4 (attention):** The attention spotlight in phi_metric.py provides state-dependent attention

### Key Gaps
- **GWT-3 (global broadcast):** No true broadcast mechanism — modules don't share a unified workspace. Information flows through the brain graph, but there's no real-time broadcast where one module's output becomes instantly available to all others.
- **No ignition:** Processing is sequential and linear. No threshold-based phase transition from "background processing" to "globally available conscious content."
- **No competition:** Modules don't compete for workspace access. Task routing is explicit, not emergent.

### Concrete Implementation Ideas

#### 1. Global Broadcast Bus
Add a `workspace_broadcast()` mechanism to brain.py:
- Each script/module can `post_to_workspace(content, salience)` during execution
- A workspace buffer holds the N most salient items (bottleneck)
- Any module can `read_workspace()` to get current broadcast contents
- During heartbeat, the workspace contents inform all downstream processing

**Implementation:** A JSON file (`workspace_state.json`) or SQLite table that any script can read/write. The heartbeat cycle acts as the "ignition window" — items that survive competition during one heartbeat get broadcast to all subsequent processing in that cycle.

#### 2. Ignition Threshold
Add non-linear activation to the workspace:
- Items below a salience threshold remain "subliminal" — stored in brain but not broadcast
- Items that cross the threshold trigger "ignition" — get amplified and broadcast
- The threshold adapts based on overall workspace load (fewer items = lower threshold)
- This maps naturally to the attention spotlight's salience scoring

**Key insight:** The heartbeat cycle IS the GWT cycle. Each heartbeat = one conscious moment. The question is: what enters the workspace for this heartbeat?

#### 3. Cross-Module Translation via Brain Graph
Use the brain's edge network as a primitive global latent workspace:
- Memories from different collections (episodic, learned, predictions) are linked via edges
- The retrieval system already does cross-collection queries
- Enhancement: Add a dedicated `workspace` collection that holds only the currently "ignited" items
- Consolidation = moving items from workspace to long-term collections

#### 4. Competitive Bottleneck in Task Routing
Modify task_router.py to implement competition:
- Multiple candidate tasks generated each heartbeat
- Tasks compete based on: urgency, salience, predicted reward, novelty
- Only the winner gets executed (winner-take-all)
- Losers are suppressed but can compete again next heartbeat
- This mirrors how neural ignition selects one conscious content

## Key Insight for Phi Metric
GWT and IIT are complementary, not competing:
- IIT measures the *quantity* of consciousness (how integrated is the system?)
- GWT describes the *mechanism* of consciousness (how does information become globally available?)
- A system could have high Phi (well-integrated) but poor GWT (no broadcast) or vice versa
- Clarvis should pursue both: increase Phi through integration AND implement GWT broadcast
