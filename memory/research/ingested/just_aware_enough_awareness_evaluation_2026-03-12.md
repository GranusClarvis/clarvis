# Research: Just Aware Enough — Evaluating Awareness Across Artificial Systems

**Paper**: arXiv:2601.14901, Meertens, Lee & Deroy (2026)
**Ingested**: 2026-03-12

## Core Thesis

Shift from evaluating AI "consciousness" to assessing practical "awareness" — defined as a system's capabilities to process, store, retrieve, and utilize information in the service of goal-directed action. The key insight: **optimal awareness exists per task** — highest information ≠ best performance. Systems should be "just aware enough" for their specific operational domain.

## Five Awareness Dimensions

| Dimension | Definition | Clarvis Mapping |
|-----------|-----------|-----------------|
| **Spatial** | Detect, differentiate, exploit spatial relations (navigation, localization, mapping) | Limited: browser navigation, file system |
| **Temporal** | Detect, differentiate, exploit temporal relations (sequencing, prediction, anticipation) | episodic_memory.py, temporal_self.py |
| **Self** | Monitor own physical/internal states (interoception, proprioception) | self_model.py, phi_metric.py |
| **Metacognitive** | Monitor, assess, regulate own processing (confidence, calibration) | confidence.py, self_model.py assess |
| **Agentive** | Identify, evaluate, modulate own actions (affordances, action selection) | attention.py, heartbeat gate, task routing |

## Four Framework Requirements

1. **Domain-sensitive**: Evaluation must account for the system's operational niche
2. **Multidimensional**: Multiple independent awareness aspects, no hierarchical ranking
3. **Deployable across scales**: Works for individual agents and multi-agent systems
4. **Ability-focused**: Evaluate underlying capacities, not isolated task performance

## Three-Element Evaluation Pipeline

1. **Dimensions of awareness** — gradable, conceptually distinct categories; "separable" (independent) vs "integral" (interdependent)
2. **Action-perception abilities** — general capacities graded by: number of distinct abilities, reliability, robustness, flexibility
3. **Evaluation tasks** — adapted to system constraints; battery of tasks required, not single measures

## Awareness Profiles

Structured comparison framework across:
- Same system with varying configurations
- Congruent systems (similar architectures)
- Heterogeneous systems (different architectures)
- Artificial vs biological systems

## Key Finding: Optimal Awareness

A thermostat is NOT aware despite goal-directed processing because it lacks "reliable, non-coincidental, and generalizable dispositional profile." Genuine awareness = consistent success across varied contexts.

**Implication**: Don't maximize ALL dimensions — calibrate awareness depth per task category. Research tasks need high metacognitive + temporal. Code tasks need high agentive + spatial (codebase navigation). Maintenance tasks need moderate across the board.

## Implementation Ideas for Clarvis

### Idea 1: Formalize Awareness Dimensions in self_model.py
Map the 5 dimensions to measurable proxies:
- **Spatial**: file/codebase navigation success rate (already in code_generation capability)
- **Temporal**: episodic recall quality, temporal prediction accuracy (temporal_self.py)
- **Self**: phi metric, calibration accuracy (confidence.py hit rate)
- **Metacognitive**: reasoning chain depth, confidence-outcome correlation
- **Agentive**: task selection accuracy (heartbeat gate precision), action success rate

### Idea 2: Task-Calibrated Awareness Depth
Use adaptive_mmr.py's category system to calibrate heartbeat depth:
- Research → full introspection + broad retrieval (high metacognitive)
- Code → focused retrieval + code templates (high agentive)
- Maintenance → minimal brief (just aware enough)

### Idea 3: Awareness Profile Dashboard
Add `awareness_profile()` to self_model.py that returns a 5-dimension radar chart:
```python
{
    "spatial": 0.65,      # from code_generation + navigation metrics
    "temporal": 0.72,     # from episodic recall + prediction accuracy
    "self": 0.83,         # from phi + calibration
    "metacognitive": 0.78, # from reasoning depth + confidence correlation
    "agentive": 0.81,     # from task selection + action success
}
```

### Idea 4: "Just Aware Enough" Gate
Extend retrieval_gate classifier: instead of just NO/LIGHT/DEEP retrieval, add an awareness-budget per dimension based on task category. Prevents over-retrieval and over-introspection on simple tasks.

## Connections to Existing Research

- **IIT/Phi**: Paper explicitly avoids IIT's hard problem — focuses on functional awareness (what the system CAN DO) rather than phenomenal consciousness (what it FEELS). Complementary to phi_metric.py.
- **GWT**: Global Workspace maps to metacognitive + agentive dimensions — the broadcast mechanism enables awareness across processing modules.
- **Cognitive Workspace (Agarwal 2025)**: Active/Working/Dormant buffers implement temporal awareness through memory tiering.
- **CRAG/Adaptive-RAG**: Context relevance optimization is a metacognitive ability — the system assessing the quality of its own retrieval.
