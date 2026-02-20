#!/usr/bin/env python3
"""
ClarvisDB Integration Layer
Wire ClarvisDB into my actual workflow
"""

import sys
import os

# Add scripts to path
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

from clarvisdb import add_memory, query_memory, IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE

def store_important(text, collection, importance=0.7, source="conversation", tags=None):
    """Store important info into my brain"""
    if tags is None:
        tags = []
    add_memory(collection, text, {"importance": importance, "source": source, "tags": tags})
    return f"Stored to {collection}: {text[:50]}..."

def recall(query, collection=None):
    """Query my brain"""
    if collection:
        results = query_memory(collection, query, n=3)
    else:
        # Query all collections
        all_results = []
        for col in [IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE]:
            r = query_memory(col, query, n=2)
            if r["documents"] and r["documents"][0]:
                all_results.extend(r["documents"][0])
        results = {"documents": [all_results[:3]]}
    
    return results["documents"][0] if results["documents"] else []

# CLI for testing
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["store", "recall"])
    parser.add_argument("--text", help="Text to store")
    parser.add_argument("--collection", default=LEARNINGS, help="Collection")
    parser.add_argument("--importance", type=float, default=0.7)
    parser.add_argument("--source", default="manual")
    parser.add_argument("--query", help="Query to recall")
    args = parser.parse_args()
    
    if args.action == "store" and args.text:
        print(store_important(args.text, args.collection, args.importance, args.source))
    elif args.action == "recall" and args.query:
        results = recall(args.query, args.collection if args.collection != LEARNINGS else None)
        for r in results:
            print(f"- {r}")
