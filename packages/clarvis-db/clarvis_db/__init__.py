"""
ClarvisDB — Local vector memory with Hebbian learning and STDP synapses.

A standalone memory system combining:
- ChromaDB + ONNX MiniLM embeddings (fully local, no cloud)
- Hebbian learning: co-retrieval strengthening, power-law decay
- STDP synapses: memristor-inspired bounded weights, spreading activation
- Relationship graph for associative memory

Usage:
    from clarvis_db import VectorStore

    db = VectorStore("/path/to/data", collections=["facts", "episodes"])
    db.store("The Earth orbits the Sun", collection="facts", importance=0.9)
    results = db.recall("planetary motion")
    db.evolve()  # run Hebbian + STDP evolution

    # Spreading activation (find associated memories)
    associated = db.associative_recall(["mem_id_1", "mem_id_2"])

    # Stats
    print(db.stats())
"""

from clarvis_db.store import VectorStore
from clarvis_db.hebbian import HebbianEngine
from clarvis_db.stdp import SynapticEngine

__version__ = "1.0.0"
__all__ = ["VectorStore", "HebbianEngine", "SynapticEngine"]
