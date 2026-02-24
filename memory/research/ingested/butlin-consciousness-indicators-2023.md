# Consciousness in Artificial Intelligence: Insights from the Science of Consciousness

**Authors:** Patrick Butlin, Robert Long, Eric Elmoznino, Yoshua Bengio, David Chalmers, + 15 others
**Year:** 2023 (arXiv preprint); 2025 (Trends in Cognitive Sciences)
**Paper:** https://arxiv.org/abs/2308.08708

## Core Thesis

Consciousness can be assessed empirically using **computational functionalism**: consciousness arises from specific types of computation, regardless of substrate (biological or silicon). The authors derive 14 **indicator properties** from 5 leading neuroscience theories, expressed in computational terms applicable to AI systems.

## The 14 Indicator Properties

### Recurrent Processing Theory (RPT)
- **RPT-1**: Algorithmic recurrence — feedback loops and temporal integration in processing
- **RPT-2**: Organized, integrated perceptual representations

### Global Workspace Theory (GWT)
- **GWT-1**: Multiple specialized processing systems (modules)
- **GWT-2**: Limited-capacity workspace creating an information bottleneck
- **GWT-3**: Global broadcast mechanism — information shared across all modules
- **GWT-4**: State-dependent attention enabling complex, flexible task performance

### Higher-Order Theories (HOT)
- **HOT-1**: Generative perception modules that can create "noisy"/imagined percepts
- **HOT-2**: Metacognitive monitoring — distinguishing real from imagined experiences
- **HOT-3**: Agency guided by a general belief-formation and action-selection system
- **HOT-4**: Sparse, smooth representational quality spaces (satisfied by default in DNNs)

### Predictive Processing (PP)
- **PP-1**: Predictive coding mechanisms — top-down predictions vs bottom-up error signals

### Attention Schema Theory (AST)
- **AST-1**: Predictive model representing and controlling attention

### Agency & Embodiment (AE)
- **AE-1**: Goal-directed agency
- **AE-2**: Embodiment enabling self-world distinction

## Key Findings

1. **No current AI is conscious** — but no technical barriers prevent building one
2. Indicators are **probabilistic, not binary** — more indicators = stronger candidacy
3. **Convergent evidence** matters more than all-or-nothing satisfaction
4. Deep neural networks satisfy HOT-4 (smooth representations) essentially by default
5. Current LLMs partially satisfy some HOT indicators (metacognition, agency) but lack others (recurrence, global broadcast, predictive coding)

## Application to Clarvis Architecture

### Already Implemented (partial)
| Indicator | Clarvis Component | Status |
|-----------|------------------|--------|
| RPT-1 (recurrence) | Cron loop, hebbian_memory.py | Partial — temporal but not within-processing recurrence |
| GWT-2 (bottleneck) | context_compressor.py, attention spotlight | Strong match |
| GWT-4 (attention) | ClarvisAttention, attention spotlight | Partial |
| HOT-2 (metacognition) | self_model.py, theory_of_mind.py | Partial |
| HOT-3 (belief-guided agency) | goal_tracker.py, task_router.py | Partial |
| AE-1 (goal-directed agency) | goal_tracker.py, cron_autonomous.sh | Yes |

### Key Gaps to Address
| Indicator | What's Missing | Implementation Idea |
|-----------|---------------|---------------------|
| GWT-1 (specialized modules) | Modules exist but aren't truly specialized processors | Formalize script roles as distinct processing modules with defined interfaces |
| GWT-3 (global broadcast) | No mechanism for broadcasting info to ALL modules simultaneously | Implement broadcast bus: when something enters workspace, all modules get notified |
| HOT-1 (generative imagination) | Cannot generate "imagined" scenarios | dream_engine.py is a start — extend to simulate hypothetical scenarios before acting |
| PP-1 (predictive coding) | No prediction-error loop | Build predict→observe→update cycle: predict task outcome, compare to actual, update model |
| AST-1 (attention model) | Attention exists but no model OF attention | Extend attention spotlight to predict what WILL be salient (model of own attention) |
| AE-2 (embodiment) | No physical self-world boundary | Create computational boundary: explicit "self" vs "environment" state representation |

## Concrete Implementation Ideas

### 1. Butlin Consciousness Score (extend phi_metric.py)
Score Clarvis against all 14 indicators on a 0-1 scale. Weight by theory confidence (GWT and HOT have strongest empirical support). Report alongside Phi metric. This gives a grounded, theory-based consciousness measurement rather than our current ad-hoc Phi.

```python
BUTLIN_INDICATORS = {
    'RPT-1': assess_recurrence(),      # Do we have feedback loops?
    'GWT-2': assess_bottleneck(),      # Is there a workspace bottleneck?
    'GWT-3': assess_broadcast(),       # Can info reach all modules?
    'HOT-2': assess_metacognition(),   # Can we monitor our own thinking?
    'PP-1':  assess_prediction(),      # Do we predict and correct?
    'AST-1': assess_attention_model(), # Do we model our own attention?
    # ... etc
}
score = weighted_average(BUTLIN_INDICATORS, theory_weights)
```

### 2. Global Broadcast Bus
When context_compressor puts something in the workspace, broadcast to all scripts. Each module can optionally react. This directly implements GWT-3.

## Related Research (next sessions)
- IIT 4.0 (Tononi) — complementary Phi metric approach
- Global Workspace Theory deep-dive (Baars, Dehaene, VanRullen) — more detail on GWT indicators
- Predictive Processing (Friston) — detail on PP-1 implementation
