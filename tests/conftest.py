"""Shared fixtures for clarvis spine tests."""

import hashlib
import os
import tempfile
import pytest

from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from clarvis.brain.constants import ALL_COLLECTIONS
from clarvis.brain.factory import get_chroma_client, reset_singletons


class _FastHashEmbedding(EmbeddingFunction):
    """Deterministic hash-based embedding for fast tests (no ML model needed)."""

    def __init__(self):
        pass

    def name(self) -> str:
        return "fast_hash_test"

    def __call__(self, input: Documents) -> Embeddings:
        result = []
        for doc in input:
            h = hashlib.sha256(doc.encode()).digest()
            # 384-dim to match MiniLM output size
            vec = [((b % 200) - 100) / 100.0 for b in (h * 12)[:384]]
            result.append(vec)
        return result


@pytest.fixture
def tmp_brain():
    """Create an isolated ClarvisBrain with a temp ChromaDB directory.

    Avoids touching production data. Tears down after test.
    Uses factory singleton for ChromaDB client consistency.
    Uses hash-based embeddings for speed (no ONNX/sentence-transformer).
    """
    from clarvis.brain import ClarvisBrain

    fast_ef = _FastHashEmbedding()

    with tempfile.TemporaryDirectory(prefix="clarvis_test_") as tmpdir:
        graph_file = os.path.join(tmpdir, "relationships.json")
        # Patch constants for this instance
        brain = ClarvisBrain.__new__(ClarvisBrain)
        brain.use_local_embeddings = False
        brain.data_dir = tmpdir
        brain.graph_file = graph_file
        brain.embedding_function = fast_ef
        brain.client = get_chroma_client(tmpdir)
        brain.collections = {}
        for name in ALL_COLLECTIONS:
            brain.collections[name] = brain.client.get_or_create_collection(
                name, embedding_function=fast_ef
            )
        brain._load_graph()
        # Caches
        brain._stats_cache = None
        brain._stats_cache_time = 0
        brain._stats_cache_ttl = 30
        brain._collection_cache = {}
        brain._collection_cache_ttl = 60
        brain._embedding_cache = {}
        brain._embedding_cache_ttl = 60
        brain._recall_cache = {}
        brain._recall_cache_ttl = 30
        brain._labile_memories = {}
        brain._lability_window = 300
        brain._failure_counters = {
            "dedup_failures": 0,
            "store_link_failures": 0,
            "temporal_fallbacks": 0,
            "search_query_failures": 0,
            "expansion_failures": 0,
            "hook_timeouts": 0,
        }
        brain._recall_scorers = []
        brain._recall_boosters = []
        brain._recall_observers = []
        brain._optimize_hooks = []
        yield brain
        reset_singletons()
