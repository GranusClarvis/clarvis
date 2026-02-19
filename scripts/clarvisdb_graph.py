#!/usr/bin/env python3
"""
ClarvisDB - Graph Layer
Phase 3: Track relationships between memories
"""

import json
import os
from datetime import datetime, timezone

GRAPH_FILE = "/home/agent/.openclaw/workspace/data/clarvisdb/relationships.json"

def load_graph():
    if os.path.exists(GRAPH_FILE):
        with open(GRAPH_FILE, "r") as f:
            return json.load(f)
    return {"nodes": {}, "edges": []}

def save_graph(graph):
    os.makedirs(os.path.dirname(GRAPH_FILE), exist_ok=True)
    with open(GRAPH_FILE, "w") as f:
        json.dump(graph, f, indent=2)

def add_node(memory_id, text, tags):
    """Add a memory node"""
    graph = load_graph()
    if memory_id not in graph["nodes"]:
        graph["nodes"][memory_id] = {
            "text": text,
            "tags": tags,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        save_graph(graph)
    return graph

def add_relationship(from_id, to_id, relationship_type):
    """Link two memories together"""
    graph = load_graph()
    
    # Ensure nodes exist
    if from_id not in graph["nodes"]:
        return {"error": f"Node {from_id} not found"}
    if to_id not in graph["nodes"]:
        return {"error": f"Node {to_id} not found"}
    
    # Add edge
    edge = {
        "from": from_id,
        "to": to_id,
        "type": relationship_type,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Avoid duplicates
    if edge not in graph["edges"]:
        graph["edges"].append(edge)
        save_graph(graph)
    
    return {"status": "added", "edge": edge}

def get_related(memory_id, depth=1):
    """Find all related memories"""
    graph = load_graph()
    related = []
    visited = set()
    
    def traverse(node_id, current_depth):
        if current_depth > depth or node_id in visited:
            return
        visited.add(node_id)
        
        for edge in graph["edges"]:
            if edge["from"] == node_id:
                related.append({
                    "id": edge["to"],
                    "relationship": edge["type"],
                    "node": graph["nodes"].get(edge["to"], {}),
                    "depth": current_depth
                })
                traverse(edge["to"], current_depth + 1)
            elif edge["to"] == node_id:
                related.append({
                    "id": edge["from"],
                    "relationship": f"inverse-{edge['type']}",
                    "node": graph["nodes"].get(edge["from"], {}),
                    "depth": current_depth
                })
                traverse(edge["from"], current_depth + 1)
    
    traverse(memory_id, 1)
    return related

def bootstrap_graph():
    """Create initial relationships"""
    graph = load_graph()
    
    # Add key nodes if not exist
    add_node("identity_1", "I am Clarvis", ["identity", "self"])
    add_node("identity_2", "My creator is Patrick (Inverse)", ["identity", "human"])
    add_node("infra_1", "I run on NUC", ["infrastructure", "hardware"])
    add_node("pref_1", "Inverse prefers direct communication", ["preference", "human"])
    
    # Create relationships
    add_relationship("identity_1", "identity_2", "created_by")
    add_relationship("identity_1", "infra_1", "runs_on")
    add_relationship("identity_2", "pref_1", "has_preference")
    
    print("✅ Graph layer bootstrapped")

def query_with_context(query_text):
    """Query memory AND get related context"""
    # First get vector results
    from clarvisdb import query_memory, IDENTITY
    
    results = query_memory(IDENTITY, query_text, n=2)
    
    # Then get related memories
    context = []
    if results["ids"] and results["ids"][0]:
        for mem_id in results["ids"][0]:
            related = get_related(mem_id, depth=2)
            context.extend(related)
    
    return {
        "direct_results": results["documents"][0] if results["documents"] else [],
        "related_context": context
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "bootstrap":
            bootstrap_graph()
        elif sys.argv[1] == "related" and len(sys.argv) > 2:
            related = get_related(sys.argv[2])
            print(f"Related to {sys.argv[2]}:")
            for r in related:
                print(f"  - {r['id']} ({r['relationship']}): {r['node'].get('text', 'N/A')}")
    else:
        bootstrap_graph()