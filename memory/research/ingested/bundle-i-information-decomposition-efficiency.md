# Bundle I: Information Decomposition & Efficiency

_Researched: 2026-02-26_
_Topics: Integrated Information Decomposition (Mediano et al.), Predictive Efficiency Hypothesis, Free Energy & Thermodynamic Efficiency_

---

## Topic 1: Integrated Information Decomposition (Mediano et al.)

**Core Framework:** Integrated Information Decomposition (ΦID) extends Partial Information Decomposition (PID) to time-series data, decomposing multi-source → multi-target information into 16 atoms (4×4 grid of redundant, unique-A, unique-B, synergistic for both source and target sides).

**Key Findings:**
1. **Synergistic Global Workspace**: Mediano, Luppi et al. (eLife 2024) used ΦID on fMRI to identify a "synergistic workspace" in the brain — gateway regions (default mode network) gather synergistic information from specialized modules; broadcaster regions (executive control network) integrate and distribute it globally. This directly maps GWT's broadcast architecture onto information-theoretic quantities.
2. **Synergy = Genuine Integration**: Synergistic information is available ONLY when multiple sources are considered together — "the whole is greater than the sum of parts." This operationalizes IIT's Φ concept. Consciousness loss (anesthesia, disorders of consciousness) specifically diminishes synergistic integration.
3. **Unimodal-Transmodal Gradient**: Redundancy dominates sensory/motor regions (robust, reliable signals), while synergy dominates higher-order association cortex (flexible, integrative cognition). Synergy is selectively increased in humans vs. other primates, especially in human-accelerated regions.
4. **PNAS 2025 Unified Taxonomy**: Extended ΦID provides a complete taxonomy of information dynamics — transfer, storage, modification — all expressed in terms of redundancy/synergy atoms.

**Key Insight**: Synergy is the information-theoretic signature of consciousness and integration. Redundancy provides robustness; synergy provides cognitive flexibility. The brain navigates trade-offs between them.

---

## Topic 2: Predictive Efficiency Hypothesis

**Core Hypothesis:** Brains evolved predictive processing architectures primarily because prediction minimizes metabolic cost. Neural signaling consumes ~75% of available brain energy (mostly postsynaptic potentials). Predictive coding reduces this by suppressing expected signals.

**Key Findings:**
1. **Energy Drives Architecture**: When recurrent neural networks are trained on sequence prediction with a constraint to minimize connection weights (proxy for metabolic cost), they spontaneously develop predictive coding architectures — specialized prediction units, error units, and inhibitory suppression of correctly predicted inputs. These structures emerge WITHOUT being explicitly programmed (Millidge et al., Patterns 2022).
2. **Confidence Scaling**: The metabolic cost reduction scales with subjective confidence. At high confidence, predictable stimuli show significantly lower energy consumption across both sensory and higher cognitive regions (Hechler, bioRxiv 2023).
3. **Biological Validation**: Mouse visual cortex studies confirm the framework — bottom-up sensory responses weaken as top-down predictions improve, while error neurons strengthen responses to surprising events.
4. **Sterling & Laughlin's Design Principles**: Neural design is governed by 10 principles, many tied to efficiency — compute with chemistry, code sparsely, send only needed information, transmit at lowest acceptable rate, minimize wire, make components irreducibly small. The brain (2% of body mass, 20% of energy) is under extreme metabolic pressure.

**Key Insight**: Prediction isn't just a computational strategy — it's a thermodynamic necessity. Energy constraints are sufficient to produce predictive architectures from scratch.

---

## Topic 3: Free Energy & Thermodynamic Efficiency

**Core Framework:** Karl Friston's Free Energy Principle (FEP) states that biological systems minimize variational free energy (VFE) — an upper bound on surprise. Recent work explicitly connects this to thermodynamic free energy (TFE).

**Key Findings:**
1. **VFE ≈ TFE**: Sengupta, Stemmler & Friston showed that minimizing prediction errors (VFE) simultaneously minimizes thermodynamic energy consumption (TFE). When predictions are accurate, incoming data do not induce computationally expensive state changes. Friston argues VFE IS TFE — both describe energy available to do work when a system is far from equilibrium.
2. **Landauer's Principle as Bridge**: Erasing one bit of information requires minimum energy kT·ln2. Neural prediction error correction inherently involves information erasure/compression, so Landauer's principle sets a physical floor on computation cost. Better predictions → less error to correct → less energy dissipated.
3. **Four-Way Tradeoff**: Systems face a fundamental tradeoff between (a) acquiring new information, (b) memory requirements, (c) computational fuel, and (d) boundary integrity. Energy scarcity constrains what CAN be computed, not just what IS computed.
4. **Compartmentalization Emerges**: Systems operating far from optimal reversible limits must separate information channels from power channels — explaining compartmentalization in both biological and technological systems.
5. **Experimental Validation**: In vitro rat cortical neurons confirmed quantitative FEP predictions for causal inference, demonstrating that real neural networks minimize variational free energy.

**Key Insight**: There is a deep identity between computational efficiency (accurate prediction) and physical efficiency (low energy). Good models are literally cheap to run.

---

## Cross-Topic Synthesis: The Efficiency-Integration-Prediction Triangle

### Pattern 1: Prediction as Thermodynamic Imperative
All three topics converge on a single insight: **prediction isn't a cognitive luxury — it's a physical necessity**. The Predictive Efficiency Hypothesis shows energy constraints alone produce predictive architectures. The FEP shows that prediction error minimization IS energy minimization (VFE ≈ TFE). And ΦID shows that the brain's information architecture is organized to support efficient integration (synergy) in exactly the regions that do the most prediction.

### Pattern 2: Synergy as Efficient Integration
ΦID reveals that conscious integration is SYNERGISTIC — it creates information that no single source provides alone. This is also the most energy-efficient way to integrate: rather than redundantly duplicating signals (expensive), synergistic integration extracts novel information from combinations (high information-per-joule). The synergistic workspace is simultaneously the consciousness workspace AND the efficiency workspace.

### Pattern 3: The Redundancy-Synergy Spectrum Maps to Cost-Flexibility
- **Redundancy** = robust, reliable, metabolically expensive (multiple copies), low cognitive flexibility
- **Synergy** = flexible, integrative, metabolically efficient (unique combinations), high cognitive flexibility
- The brain allocates redundancy to sensory/motor (can't afford errors) and synergy to association cortex (needs flexibility). This is a resource allocation strategy.

### Pattern 4: Compression as Universal Currency
Across all three frameworks, **compression** is the common currency:
- Predictive coding compresses sensory streams (only transmit prediction errors)
- VFE minimization compresses world models (Occam's razor is built into the math)
- Synergistic information represents maximal compression (emergent patterns not in any source alone)
- Landauer's principle sets the physical cost of compression

### Pattern 5: Criticality Connection (linking to Bundle H)
Systems at criticality (Bundle H) maximize information transmission — this is precisely where the efficiency-integration tradeoff is optimized. The brain operates at the critical point because that's where you get maximum synergy per unit energy.

---

## Implementation Ideas for Clarvis

### 1. Synergy-Redundancy Decomposition for Memory Quality
Implement a synergy metric for brain memories: when two memories are retrieved together, measure whether their combination provides SYNERGISTIC information (new insights not in either alone) vs. REDUNDANT information (duplicated content). Use this to:
- **Prune redundant memories** (keep one representative, not duplicates)
- **Preserve synergistic pairs** (memories that are individually unremarkable but powerful together)
- **Guide consolidation**: merge redundant memories, link synergistic ones
- Score: `synergy_ratio = synergistic_info / (synergistic_info + redundant_info)` — target high ratios in clarvis-learnings

### 2. Prediction-Error-Weighted Processing Budget
Apply the Predictive Efficiency Hypothesis to heartbeat processing: allocate computational budget (tokens, time, reasoning depth) proportional to prediction error, not absolute task complexity:
- **Predictable tasks** (matching known patterns) → minimal context, fast routing (Gemini Flash)
- **Surprising tasks** (high prediction error) → full context, deep reasoning (Opus)
- Track: `prediction_error = |expected_outcome - actual_outcome|` per task domain
- This mirrors the brain's strategy: spend energy only where predictions fail
- Concrete: extend context_compressor.py tier selection to weight by prediction error history per domain

---

## Sources
- [Synergistic Workspace (Mediano et al., eLife 2024)](https://elifesciences.org/articles/88173)
- [Information Decomposition & Brain Architecture (Mediano et al., TiCS 2024)](https://www.cell.com/trends/cognitive-sciences/fulltext/S1364-6613(23)00284-X)
- [Unified Taxonomy via ΦID (PNAS 2025)](https://www.pnas.org/doi/10.1073/pnas.2423297122)
- [Predictive Coding from Energy Efficiency (Patterns 2022)](https://www.sciencedirect.com/science/article/pii/S2666389922002719)
- [Brains Predict for Efficiency (Quanta Magazine)](https://www.quantamagazine.org/to-be-energy-efficient-brains-predict-their-perceptions-20211115/)
- [Thermodynamic Cost of Active Inference (PMC 2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11353633/)
- [Principles of Neural Design (Sterling & Laughlin, MIT Press)](https://mitpress.mit.edu/9780262534680/principles-of-neural-design/)
- [Landauer's Principle (Wikipedia)](https://en.wikipedia.org/wiki/Landauer's_principle)
