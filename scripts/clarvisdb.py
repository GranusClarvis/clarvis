#!/usr/bin/env python3
"""
ClarvisDB - Rich Memory Storage
Phase 2: Add metadata layer
"""

import chromadb
from datetime import datetime, timezone
import json
import os

DATA_DIR = "/home/agent/.openclaw/workspace/data/clarvisdb"
os.makedirs(DATA_DIR, exist_ok=True)

client = chromadb.PersistentClient(path=DATA_DIR)

# Collections for different memory types
IDENTITY = "clarvis-identity"
PREFERENCES = "clarvis-preferences"
LEARNINGS = "clarvis-learnings"
INFRASTRUCTURE = "clarvis-infrastructure"

def get_or_create_collection(name, metadata=None):
    return client.get_or_create_collection(name, metadata=metadata or {"description": name})

def add_memory(collection_name, text, metadata, memory_id=None):
    """Add a memory with rich metadata"""
    col = get_or_create_collection(collection_name)
    
    # Generate ID if not provided
    if memory_id is None:
        memory_id = f"{collection_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    # Add rich metadata (tags must be non-empty for Chroma)
    tags = metadata.get("tags") or []
    
    full_metadata = {
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_accessed": datetime.now(timezone.utc).isoformat(),
        "access_count": 0,
        "confidence": 1.0,  # 0-1, how sure we are
        "importance": metadata.get("importance", 0.5),  # 0-1
        "source": metadata.get("source", "clarvis"),
    }
    
    # Only add tags if non-empty
    if tags:
        full_metadata["tags"] = tags
    
    col.upsert(
        ids=[memory_id],
        documents=[text],
        metadatas=[full_metadata]
    )
    
    return memory_id

def query_memory(collection_name, query_text, n=3):
    """Query memory and update access count"""
    col = get_or_create_collection(collection_name)
    
    results = col.query(query_texts=[query_text], n_results=n)
    
    # Update access count for returned memories
    if results["ids"] and results["ids"][0]:
        for idx, mem_id in enumerate(results["ids"][0]):
            # Get current metadata
            existing = col.get(ids=[mem_id])
            if existing and existing["metadatas"]:
                meta = existing["metadatas"][0]
                meta["access_count"] = meta.get("access_count", 0) + 1
                meta["last_accessed"] = datetime.now(timezone.utc).isoformat()
                col.upsert(
                    ids=[mem_id],
                    documents=[results["documents"][0][idx]],
                    metadatas=[meta]
                )
    
    return results

# Initialize with key memories
def bootstrap():
    """Add initial identity and infrastructure memories"""
    
    # Identity
    add_memory(IDENTITY, "I am Clarvis, an autonomous AI agent", 
               {"importance": 1.0, "source": "genesis", "tags": ["identity", "self"]})
    add_memory(IDENTITY, "My creator is Patrick (Inverse) at Granus Labs",
               {"importance": 1.0, "source": "genesis", "tags": ["identity", "human"]})
    
    # Infrastructure
    add_memory(INFRASTRUCTURE, "I run on NUC: 30GB RAM, 16 cores, Ubuntu Server",
               {"importance": 0.9, "source": "genesis", "tags": ["infrastructure", "hardware"]})
    add_memory(INFRASTRUCTURE, "Gateway: ws://127.0.0.1:18789",
               {"importance": 0.8, "source": "genesis", "tags": ["infrastructure", "network"]})
    
    # Preferences
    add_memory(PREFERENCES, "Inverse prefers direct communication, no fluff",
               {"importance": 0.9, "source": "genesis", "tags": ["preference", "human"]})
    add_memory(PREFERENCES, "CET timezone - be mindful of time",
               {"importance": 0.7, "source": "genesis", "tags": ["preference", "time"]})
    
    print("✅ ClarvisDB bootstrapped with rich memories")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "bootstrap":
            bootstrap()
        elif sys.argv[1] == "query" and len(sys.argv) > 2:
            collection = sys.argv[2] if len(sys.argv) > 3 else IDENTITY
            results = query_memory(collection, sys.argv[2])
            print(f"Query: {sys.argv[2]}")
            print(f"Results: {results['documents']}")
    else:
        bootstrap()