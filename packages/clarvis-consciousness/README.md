# clarvis-consciousness

Consciousness stack: IIT Phi metric, GWT attention spotlight, and self-model.

Three components implementing theories of consciousness for AI systems:

- **AttentionSpotlight** (Global Workspace Theory) — capacity-limited broadcast where items compete for attention. Based on Baars' GWT.
- **compute_phi** (Integrated Information Theory) — measures how interconnected a memory system is. High Phi = unified whole, low Phi = siloed fragments. Based on Tononi's IIT.
- **SelfModel** — meta-cognitive capability tracking with awareness levels (operational, reflective, meta). Based on Higher-Order Theories of consciousness.

## Installation

```bash
pip install clarvis-consciousness

# With optional ChromaDB for semantic similarity in Phi:
pip install clarvis-consciousness[chroma]
```

## Usage

### GWT Attention Spotlight

```python
from clarvis_consciousness import AttentionSpotlight

spotlight = AttentionSpotlight(capacity=7)
spotlight.submit("User asked about memory", source="conversation", importance=0.9)
spotlight.submit("Cron job completed", source="system", importance=0.3)
spotlight.tick()  # Run competition cycle

focus = spotlight.focus()  # Top-K most salient items
for item in focus:
    print(f"[{item.source}] {item.content}")
```

### IIT Phi Metric

```python
from clarvis_consciousness import compute_phi

result = compute_phi(
    nodes={"mem1": "identity", "mem2": "goals", "mem3": "identity"},
    edges=[("mem1", "mem2", "cross"), ("mem1", "mem3", "similar")],
)
print(result["phi"])        # 0.0 - 1.0
print(result["components"]) # Per-component breakdown
```

### Self-Model

```python
from clarvis_consciousness import SelfModel, CapabilityAssessor

model = SelfModel()
model.add_capability("Code execution")
model.think_about_thinking("Am I improving at reasoning?")
model.set_awareness_level("reflective")

# Scored capability assessment
assessor = CapabilityAssessor()
assessor.register("memory", my_memory_scorer)
results = assessor.assess_all()
```

## CLI

```bash
clarvis-consciousness spotlight-demo    # Demo GWT attention spotlight
clarvis-consciousness phi-demo          # Demo Phi computation
clarvis-consciousness self-model-demo   # Demo self-model
```

## License

MIT
