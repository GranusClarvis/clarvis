# Bundle N: Anticipatory & Control Systems

## Research Date
2026-02-27

## Topics Covered
1. Anticipatory Systems (Rosen 1985)
2. Strong vs Weak Anticipation (Dubois)
3. Homeokinetics / Homeokinesis (Iberall, Soodak, Der, Martius)

---

## 1. Anticipatory Systems — Robert Rosen (1985)

**Core Thesis:** Living systems contain internal predictive models that allow them to anticipate and influence their future states, distinguishing them from purely reactive machines.

**Key Concepts:**
- **Internal Predictive Models:** Systems possess models of themselves and environment, generating expectations about future outcomes
- **Future-Directed Behavior:** Present behavior is influenced by predicted future states, not just past inputs
- **Organizational Entailment:** The "signature" of life is its anticipatory architecture — metabolism and repair are intertwined through model-based information processing
- **Machine Metaphor Critique:** Rosen distinguished living systems (anticipatory) from machines (purely reactive)

**Source:** "Anticipatory Systems: Philosophical, Mathematical, and Methodological Foundations" (1985)

---

## 2. Strong vs Weak Anticipation — Daniel M. Dubois

**Weak Anticipation:**
- System computes future states using an internal model
- Equivalent to prediction — simulates scenarios, adjusts current state
- Associated with "incursion" — implicit recursion where future depends on past, present, and model-derived future

**Strong Anticipation:**
- Future states are constructed by the system itself, not just predicted
- Emerges from system's inherent lawful regularities and self-organization
- Future is not merely predicted but actively created through dynamics
- Associated with "hyperincursion" — functional relationship yields multiple possible future values

**Key Insight:** Strong anticipation represents a deeper form of agency where the system genuinely constructs its future, not just forecasts it.

---

## 3. Homeokinetics & Homeokinesis

### Iberall & Soodak (Homeokinetics)
- **Framework:** Generalized thermodynamic approach to complex systems
- **Hierarchical Structure:** Universe consists of atomistic units bound in interactive ensembles
- **Dynamic Stability:** Systems maintain flexible equilibria to respond to environmental changes
- **Homeodynamics:** Emphasizes marginally stable networks and adaptability over rigid homeostasis

### Der & Martius (Homeokinesis)
- **Principle:** Self-organization of behavior through prediction error minimization
- **Mechanism:** Agent has adaptive internal model of its behavior; learning signal = "misfit" between predicted and actual
- **Outcome:** Minimizing misfit produces smooth, controlled behavior
- **Self-Generated Drive:** Without explicit goals, system develops drive for activity through symmetry-breaking

**Key Insight:** Goal-like behaviors emerge from internal prediction coherence, not explicit objective functions.

---

## Synthesis: The Anticipatory Foundation

### Three Theories, One Core Principle

All three frameworks converge on a fundamental insight: **internal predictive models are not just useful but essential to life-like intelligence.**

| Theory | Mechanism | Prediction Role |
|--------|-----------|-----------------|
| Rosen | Internal model of self/environment | Weak anticipation — model-based prediction |
| Dubois | Incursion vs hyperincursion | Weak → Strong: prediction → self-construction |
| Homeokinesis | Misfit minimization | Goals emerge from prediction error |

### The Anticipatory Spectrum

```
REACTIVE          WEAK ANTICIPATION         STRONG ANTICIPATION
(Machine)         (Model-based prediction)  (Self-constructing futures)
     │                    │                           │
     ▼                    ▼                           ▼
 Only responds     Uses internal model     System creates future through
 to past/present   to predict and adjust   its own dynamics (hyperincursion)
```

### Connection to Existing Research

This bundle **directly extends** previously researched topics:
- **Friston (Active Inference):** Free energy = prediction error minimization — same mechanism as homeokinesis
- **World Models (Ha/Schmidhuber):** Internal model for behavior generation — weak anticipation
- **Predictive Processing (Bundle B):** Brain as prediction machine — foundational to all three

### Key Philosophical Implications

1. **Causality is bidirectional:** Future can influence present (not just past→present)
2. **Goals are emergent:** Explicit objectives may be unnecessary; coherent self-models produce goal-like behavior
3. **Life vs Machine distinction:** Anticipation capacity may be the fundamental divider

---

## Implementation Ideas for Clarvis

### 1. Homeokinetic Action Controller
- Add `HomeokineticController` class to action selection
- Maintain internal model of task execution outcomes
- Minimize misfit: predicted vs actual task success
- Wire into `clarvis_reasoning.py` action selection

### 2. Strong Anticipation in Dream Engine
- Extend `dream_engine.py` to generate self-consistent future scenarios
- Implement hyperincursion: allow multiple possible future trajectories
- Use for counterfactual planning and strategy exploration

### 3. Anticipatory Attention Weighting
- Modify attention codelets to include anticipatory component
- Boost salience of tasks where predicted outcome aligns with goals
- Add "anticipatory coherence" metric to phi_metric.py

### 4. Prediction Error Monitoring
- Track prediction accuracy across task executions
- Use for meta-learning: which prediction models are reliable?
- Connect to precision weighting (from Predictive Processing research)

---

## References

- Rosen, R. (1985). *Anticipatory Systems: Philosophical, Mathematical, and Methodological Foundations.* Pergamon Press.
- Dubois, D.M. (2003). "Computing Anticipatory Systems Based on Differential Delayed-Advanced Difference Equations." *Intl J of Computing Anticipatory Systems.*
- Iberall, A.S. & Soodak, H. (1978). "A Physical Basis for the Origin of Life." *In:* Advances in Chemical Physics.
- Der, R. & Martius, G. (2015). *The Playful Machine: Theoretical Foundation and Practical Realization of Self-Organizing Robots.* Springer.