# clarvis-db

Local vector memory with Hebbian learning, STDP synapses, ChromaDB + ONNX embeddings.

A standalone memory system combining:
- **ChromaDB + ONNX MiniLM** embeddings (fully local, no cloud)
- **Hebbian learning**: co-retrieval strengthening, power-law decay
- **STDP synapses**: memristor-inspired bounded weights, spreading activation
- **Relationship graph** for associative memory

## Installation

```bash
pip install clarvis-db

# With optional backends:
pip install clarvis-db[chroma]    # ChromaDB support
pip install clarvis-db[onnx]      # ONNX MiniLM embeddings
pip install clarvis-db[all]       # Everything
```

## Usage

```python
from clarvis_db import VectorStore

db = VectorStore("/path/to/data", collections=["facts", "episodes"])

# Store memories
db.store("The Earth orbits the Sun", collection="facts", importance=0.9)
db.store("Debug session: fixed auth timeout", collection="episodes")

# Recall by semantic similarity
results = db.recall("planetary motion")

# Run Hebbian + STDP evolution (strengthens frequently-accessed memories)
db.evolve()

# Spreading activation (find associated memories)
associated = db.associative_recall(["mem_id_1"])

# Stats
print(db.stats())
```

### Hebbian Engine (standalone)

```python
from clarvis_db import HebbianEngine

heb = HebbianEngine(data_dir="./data/hebbian")
importance = heb.reinforce("memory_id", current_importance=0.5, access_count=3)
decayed = heb.compute_decay(0.8, days_since_access=10, access_count=5)
```

### STDP Synaptic Engine (standalone)

```python
from clarvis_db import SynapticEngine

syn = SynapticEngine(db_path="./data/synapses.db")
weight = syn.potentiate("mem_a", "mem_b", delta_t=0)
spread = syn.spread("hub_memory", n=5)
```

## CLI

```bash
clarvis-db stats [data_dir]          # Show store statistics
clarvis-db store <text> [data_dir]   # Store a memory
clarvis-db recall <query> [data_dir] # Search memories
clarvis-db evolve [data_dir]         # Run Hebbian + STDP evolution
clarvis-db consolidate [data_dir]    # Run STDP consolidation
clarvis-db hubs [data_dir]           # Show hub memories
clarvis-db strongest [data_dir]      # Show strongest synapses
clarvis-db test                      # Run self-test
```

## License

MIT
