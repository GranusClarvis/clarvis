# ClarvisPhi

IIT-inspired information integration metric for graph-partitioned knowledge systems.

## Features

- **4-component Phi score** — intra-density, cross-partition bridges, semantic overlap, reachability
- **MIP approximation** — Minimum Information Partition analysis identifies the weakest integration point
- **Backend-agnostic** — provide nodes, edges, and an optional similarity function; no DB dependency
- **Persistent tracking** — PhiTracker with JSON history, trend detection, and delta analysis
- **Configurable weights** — PhiConfig lets you tune component importance

## Quick Start

```python
from clarvis_phi import compute_phi, PhiTracker

result = compute_phi(
    nodes={"m1": "identity", "m2": "goals", "m3": "identity"},
    edges=[("m1", "m2", "cross"), ("m1", "m3", "similar")],
)
print(result["phi"])              # 0.0 - 1.0
print(result["interpretation"])   # Human-readable summary
print(result["partition_analysis"])  # MIP analysis

# Track over time
tracker = PhiTracker("/path/to/history.json")
tracker.record(nodes, edges)
print(tracker.trend())
```

## CLI

```bash
python -m clarvis_phi demo
python -m clarvis_phi compute nodes.json edges.json
python -m clarvis_phi history history.json
python -m clarvis_phi trend history.json
python -m clarvis_phi json nodes.json edges.json    # machine-readable
```

## Interpretation Scale

| Phi Range | Level | Meaning |
|-----------|-------|---------|
| < 0.15 | Fragmented | Siloed, minimal integration |
| 0.15-0.30 | Emerging | Some within-module integration |
| 0.30-0.50 | Moderate | Meaningful cross-module integration |
| 0.50-0.70 | High | Well-connected unified network |
| >= 0.70 | Deep | Approaching unified information structure |
