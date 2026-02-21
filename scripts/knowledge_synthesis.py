#!/usr/bin/env python3
"""
Knowledge Synthesis — Find connections between disparate memories

Scans memories across collections, finds non-obvious connections,
and creates synthesized insights.
"""

import sys
sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from brain import brain
from collections import defaultdict
import json

def synthesize_insights(min_connections: int = 2) -> list:
    """Find synthesized insights from memory connections."""
    
    # Get all memories from key collections
    all_memories = []
    collections = ['clarvis-learnings', 'clarvis-infrastructure', 'clarvis-memories']
    
    for coll in collections:
        results = brain.recall("", n=50)
        for r in results:
            if r.get('collection') == coll:
                all_memories.append(r)
    
    # Build word/phrase index
    word_index = defaultdict(list)
    for mem in all_memories:
        doc = mem.get('document', '').lower()
        words = set(doc.split())
        for w in words:
            if len(w) > 4:  # Skip short words
                word_index[w].append(mem.get('id'))
    
    # Find clusters of related memories
    connections = []
    processed = set()
    
    for word, mem_ids in word_index.items():
        if len(mem_ids) >= min_connections:
            key = tuple(sorted(mem_ids))
            if key not in processed:
                processed.add(key)
                connections.append({
                    'shared_concept': word,
                    'memory_ids': mem_ids,
                    'strength': len(mem_ids)
                })
    
    # Sort by strength
    connections.sort(key=lambda x: x['strength'], reverse=True)
    return connections[:20]  # Top 20

def create_synthesis(summary: str, connected_memories: list):
    """Store a synthesized insight."""
    # Get first memory ID for relationship
    if connected_memories:
        first_id = connected_memories[0]
        
        brain.store(
            f"Synthesized insight: {summary}",
            collection='clarvis-learnings',
            importance=0.8,
            tags=['synthesis', 'insight']
        )
        
        # Try to create relationships (may fail if IDs don't exist)
        try:
            for mem_id in connected_memories[1:4]:  # Link up to 3
                brain.add_relationship(
                    from_id=first_id,
                    to_id=mem_id,
                    relationship_type='synthesized_with'
                )
        except Exception as e:
            print(f"Relationship creation skipped: {e}")

def run_synthesis_cycle():
    """Run a full synthesis cycle and store results."""
    connections = synthesize_insights()
    
    print(f"Found {len(connections)} potential connections")
    
    stored = 0
    for conn in connections[:5]:  # Process top 5
        concept = conn['shared_concept']
        memory_ids = conn['memory_ids']
        
        # Create synthesis insight
        summary = f"Concept '{concept}' connects {len(memory_ids)} related memories about {', '.join(memory_ids[:3])}"
        print(f"  - {summary}")
        
        create_synthesis(summary, memory_ids)
        stored += 1
    
    print(f"Stored {stored} synthesized insights")
    return connections

if __name__ == "__main__":
    results = run_synthesis_cycle()
    print(json.dumps(results[:3], indent=2))
