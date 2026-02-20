#!/usr/bin/env python3
"""Test Chroma vector storage for my brain"""

import chromadb

# Use persistent storage in my workspace
client = chromadb.PersistentClient(path="/home/agent/.openclaw/workspace/data/chroma")

# Create a collection for my memory
collection = client.get_or_create_collection("clarvis-memory")

# Test: Add some "memories"
test_memories = [
    {"id": "1", "text": "I am Clarvis, an AI agent created by Granus Labs", "metadata": {"type": "identity"}},
    {"id": "2", "text": "My human is Patrick (Inverse), prefers direct communication", "metadata": {"type": "preference"}},
    {"id": "3", "text": "I run on a NUC with 30GB RAM, Ubuntu Server", "metadata": {"type": "infrastructure"}},
]

# Add them
for m in test_memories:
    collection.add(ids=[m["id"]], documents=[m["text"]], metadatas=[{"type": m["metadata"]["type"]}])

print(f"Added {len(test_memories)} memories")

# Test: Query my memory
query = "who am I and where do I run?"
results = collection.query(query_texts=[query], n_results=2)

print(f"\nQuery: {query}")
print(f"Results: {results['documents'][0]}")

# Test: Query by metadata
results2 = collection.get(where={"type": "identity"})
print(f"\nIdentity memories: {results2['documents']}")

print("\n✅ Chroma memory test PASSED!")
