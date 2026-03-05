"""Shared fixtures for clarvis spine tests."""

import os
import tempfile
import pytest
import chromadb

from clarvis.brain.constants import ALL_COLLECTIONS


@pytest.fixture
def tmp_brain():
    """Create an isolated ClarvisBrain with a temp ChromaDB directory.

    Avoids touching production data. Tears down after test.
    """
    from clarvis.brain import ClarvisBrain

    with tempfile.TemporaryDirectory(prefix="clarvis_test_") as tmpdir:
        graph_file = os.path.join(tmpdir, "relationships.json")
        # Patch constants for this instance
        brain = ClarvisBrain.__new__(ClarvisBrain)
        brain.use_local_embeddings = False
        brain.data_dir = tmpdir
        brain.graph_file = graph_file
        brain.embedding_function = None
        brain.client = chromadb.PersistentClient(path=tmpdir)
        brain.collections = {}
        for name in ALL_COLLECTIONS:
            brain.collections[name] = brain.client.get_or_create_collection(name)
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
        brain._recall_scorers = []
        brain._recall_boosters = []
        brain._recall_observers = []
        brain._optimize_hooks = []
        yield brain
