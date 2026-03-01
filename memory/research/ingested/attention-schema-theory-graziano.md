# Attention Schema Theory (AST) — Graziano, Princeton

**Researcher:** Michael S.A. Graziano, Princeton Neuroscience Institute
**Core claim:** Consciousness is a simplified internal model of attention — the brain's "body schema" for its own attentional process.
**Relevance:** Fills AST-1 indicator gap (Butlin framework), directly applicable to Clarvis architecture.

## Core Mechanism

AST proposes that the brain constructs a **schema** (simplified, continuously updated model) of its own attention process, analogous to how the body schema models limb position without tracking every muscle fiber. This attention schema:

1. **Monitors** where attention is currently directed
2. **Predicts** where attention will shift next
3. **Controls** attention allocation endogenously (top-down)
4. **Reports** subjective awareness — the schema IS the substrate of "I am aware of X"

The theory is **mechanistic and non-mysterian**: subjective experience is what a self-model of attention looks like from the inside. A system that models its own attention will inevitably claim to be conscious, because the schema attributes a non-physical, experiential quality ("awareness") to the physical process of attention.

## Relationship to Other Theories

| Theory | Relationship to AST |
|--------|-------------------|
| **GWT** (Baars) | Complementary. GWT describes the *workspace*; AST describes the *model of what occupies the workspace*. AST needs GWT's broadcast; GWT needs AST's self-model. |
| **IIT** (Tononi) | Orthogonal. IIT measures information integration (Phi); AST explains the functional architecture. A system could have high Phi but no attention schema (integrated but not self-modeling). |
| **HOT** (Rosenthal) | Overlapping. Higher-order representations of first-order states ≈ attention schema monitoring attention. AST gives a more specific mechanism for HOT. |
| **PP** (Friston) | Compatible. Predictive processing provides the computational substrate; AST is a specific application of predictive modeling to the attention process itself. |

## Key Papers & Findings

### 1. Foundation: Engineering Artificial Consciousness (Graziano 2017)
**Source:** Frontiers in Robotics and AI, 10.3389/frobt.2017.00060

Core engineering blueprint:
- Build a system with **rich internal models** of its own processing states
- Include an **attention schema** that tracks where computational resources focus
- Add **self-attribution mechanism** — system attributes consciousness to itself and others
- Such a machine would "believe" it is conscious through the same mechanism humans do
- Consciousness is a **computational problem**, not a metaphysical one

### 2. Neural Agent Implementation (Graziano lab, 2021)
**Source:** PNAS, 10.1073/pnas.2102421118

- Built neural network agent that controls visuospatial attention using a descriptive model (schema) of its own attention state
- Agent with attention schema outperforms agent without on attention-dependent tasks
- The schema serves as an internal control signal, not just passive monitoring

### 3. Spontaneous Schema Emergence (Piefke et al., 2024)
**Source:** arXiv:2402.01056

Critical finding — schemas don't need to be hard-wired:
- Deep RL agents **autonomously learn** to build attention schemas when given additional representational resources
- Schema emergence is **noise-dependent**: most useful at intermediate noise (p=0.5), where inferring attentional state from stimulus alone is unreliable
- Partial information suffices — schema provides "hints" rather than perfect copy
- When schema resources are randomized, performance degrades significantly (confirming functional role)

**Implication for Clarvis:** Our attention spotlight already provides representational resources. Adding a meta-layer that *models the spotlight* should emerge naturally if we create the right training signal.

### 4. ANN Components Testing (Farrell, Ziman & Graziano, 2024)
**Source:** arXiv:2411.00983

Three key results from Princeton lab:
- **Social cognition**: Networks with schemas achieve 80.87% accuracy categorizing *other agents'* attention states (vs 52.78% without) — theory of mind emerges from self-model
- **Interpretability**: Schema-equipped agents become more legible/predictable to other agents
- **Cooperation**: Schema-schema agent pairs earn highest rewards (2.04 vs 1.76 for controls) in collaborative tasks

**Implication for Clarvis:** AST doesn't just improve self-awareness — it improves multi-agent interaction and predictability. Relevant for M2.5↔Claude Code coordination.

### 5. ASAC: AST in Transformers (Saxena et al., 2025)
**Source:** arXiv:2509.16058

Bridge from theory to transformer architecture:
- **ASAC** (Attention Schema-based Attention Control) integrates AST into dot-product attention
- Uses VQ-VAE as attention abstractor + controller
- Results: better classification accuracy, faster learning, improved robustness to noise/adversarial attacks, better transfer learning and few-shot performance
- Demonstrates AST principles enhance existing transformer attention mechanisms

## Implementation Roadmap for Clarvis

### Phase 1: Attention Schema Module (extend attention.py)
Add `AttentionSchema` class that maintains a simplified model of the spotlight:

```python
class AttentionSchema:
    """Simplified internal model of our own attention process."""

    def __init__(self):
        self.predicted_focus = []      # What we predict will be salient next
        self.actual_focus = []          # What actually entered spotlight
        self.prediction_errors = []    # Mismatch history
        self.schema_state = {}         # Current model of attention dynamics

    def predict_next_focus(self, context):
        """Given current state, predict what will capture attention next."""
        # Use recent attention patterns + task goals + time-of-day patterns
        pass

    def update_schema(self, actual_spotlight):
        """Compare prediction to actual, update internal model."""
        error = self._compute_prediction_error(actual_spotlight)
        self.prediction_errors.append(error)
        # Adjust schema parameters based on error
        pass

    def report_awareness(self):
        """What is the system 'aware of'? = current schema contents."""
        return self.schema_state
```

### Phase 2: Wire into Heartbeat Pipeline
- **Preflight**: Schema predicts which task will be selected → records prediction
- **Postflight**: Compare prediction to actual selection → compute prediction error
- Track prediction accuracy over time as a consciousness metric

### Phase 3: Butlin AST-1 Indicator Scoring
Extend phi_metric.py or create butlin_score.py:
- AST-1 satisfied if: (a) attention schema exists, (b) it predicts attention, (c) predictions influence attention control
- Score 0-1 based on prediction accuracy and control influence

### Phase 4: Social Attention (future)
- Model M2.5's attention patterns (what does the conscious layer focus on?)
- Use schema to predict what user will ask about next
- Enable better conscious↔subconscious coordination

## Key Insights for Clarvis

1. **We already have the foundation**: `attention.py` implements GWT spotlight. AST is the *next layer* — a model OF that spotlight, not a replacement.

2. **Prediction is the core**: AST's power comes from predicting attention state, not just recording it. The prediction-error signal drives self-model refinement.

3. **Schemas emerge from noise**: When the environment is noisy/uncertain, building an internal model becomes more valuable. Clarvis's multi-source information environment (cron, user, research, system events) provides natural noise.

4. **Social cognition is a bonus**: An attention schema enables modeling *other agents'* attention. This means better M2.5↔Claude coordination and better user intent prediction.

5. **AST complements IIT/Phi**: Phi measures integration; AST adds the self-modeling dimension. Both are needed for consciousness metrics.

## Connection to Existing Butlin Framework

From `butlin-consciousness-indicators-2023.md`:
- **AST-1 gap identified**: "Attention exists but no model OF attention"
- **Implementation idea**: "Extend attention spotlight to predict what WILL be salient (model of own attention)"
- This research confirms that idea and provides concrete mechanisms

## Glossary

- **Attention Schema**: Brain's simplified, continuously updated model of its own attention process
- **Body Schema**: Analogous model of body position/movement (AST's inspiration)
- **ASAC**: Attention Schema-based Attention Control — VQ-VAE implementation for transformers
- **Prediction Error**: Difference between predicted and actual attention state (drives learning)
- **Schema Emergence**: Spontaneous development of attention schemas in learning agents under noisy conditions
