#!/usr/bin/env python3
"""
Knowledge Synthesis — Find cross-domain connections between memories

Scans all brain collections, finds connections that span collection boundaries,
and creates synthesized insights about non-obvious relationships.
"""

import sys
sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from brain import brain, ALL_COLLECTIONS
from collections import defaultdict
import re

# Stopwords to ignore in keyword extraction
STOPWORDS = {
    'about', 'after', 'again', 'also', 'been', 'before', 'being', 'between',
    'both', 'could', 'does', 'doing', 'during', 'each', 'every', 'first',
    'from', 'have', 'having', 'here', 'into', 'just', 'like', 'make', 'many',
    'more', 'most', 'much', 'must', 'need', 'only', 'other', 'over', 'same',
    'should', 'some', 'such', 'than', 'that', 'their', 'them', 'then',
    'there', 'these', 'they', 'this', 'those', 'through', 'under', 'very',
    'want', 'well', 'were', 'what', 'when', 'where', 'which', 'while', 'will',
    'with', 'would', 'your', 'already', 'using', 'used', 'based', 'added',
    'created', 'stored', 'updated', 'tested', 'working', 'across', 'within',
}


def extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text, skipping stopwords and short words."""
    words = re.findall(r'[a-z_]+', text.lower())
    return {w for w in words if len(w) > 4 and w not in STOPWORDS}


def load_all_memories() -> list:
    """Load all memories from all collections with collection labels."""
    all_memories = []
    for coll in ALL_COLLECTIONS:
        memories = brain.get(coll, n=200)
        for mem in memories:
            mem['collection'] = coll
            all_memories.append(mem)
    return all_memories


def find_cross_domain_connections(min_collections: int = 2) -> list:
    """
    Find concepts that appear across multiple collections.

    This is the core cross-domain synthesis: a keyword appearing in
    both 'learnings' and 'procedures' represents a bridge between
    abstract knowledge and executable skill.

    Args:
        min_collections: Minimum number of different collections a concept
                        must appear in to count as cross-domain.

    Returns:
        List of cross-domain connection dicts sorted by cross-domain strength.
    """
    all_memories = load_all_memories()
    print(f"Loaded {len(all_memories)} memories from {len(ALL_COLLECTIONS)} collections")

    # Build keyword → list of (memory_id, collection) index
    keyword_index = defaultdict(list)
    for mem in all_memories:
        doc = mem.get('document', '')
        keywords = extract_keywords(doc)
        for kw in keywords:
            keyword_index[kw].append({
                'id': mem.get('id', ''),
                'collection': mem['collection'],
                'snippet': doc[:100]
            })

    # Find keywords that span multiple collections
    connections = []
    for keyword, entries in keyword_index.items():
        collections_hit = set(e['collection'] for e in entries)
        if len(collections_hit) >= min_collections:
            connections.append({
                'concept': keyword,
                'collections': sorted(collections_hit),
                'cross_domain_strength': len(collections_hit),
                'total_memories': len(entries),
                'entries': entries
            })

    # Sort by cross-domain strength first, then by total memory count
    connections.sort(key=lambda x: (x['cross_domain_strength'], x['total_memories']), reverse=True)
    return connections


def find_semantic_bridges(top_n: int = 5) -> list:
    """
    Use brain.recall() to find memories in one collection that are
    semantically similar to memories in a different collection.

    This catches connections that keyword overlap misses.
    """
    bridges = []
    # Pick representative memories from each collection
    key_collections = ['clarvis-learnings', 'clarvis-procedures', 'clarvis-goals', 'clarvis-memories']

    for source_coll in key_collections:
        source_memories = brain.get(source_coll, n=10)
        for mem in source_memories[:5]:  # Top 5 from each collection
            doc = mem.get('document', '')
            if len(doc) < 20:
                continue

            # Search other collections for semantic matches
            target_colls = [c for c in key_collections if c != source_coll]
            results = brain.recall(doc, collections=target_colls, n=3)

            for r in results:
                if r.get('collection') != source_coll:
                    bridges.append({
                        'source_collection': source_coll,
                        'source_id': mem.get('id', ''),
                        'source_snippet': doc[:80],
                        'target_collection': r.get('collection', ''),
                        'target_id': r.get('id', ''),
                        'target_snippet': r.get('document', '')[:80],
                    })

    # Deduplicate by (source_id, target_id) pairs
    seen = set()
    unique_bridges = []
    for b in bridges:
        pair = tuple(sorted([b['source_id'], b['target_id']]))
        if pair not in seen:
            seen.add(pair)
            unique_bridges.append(b)

    return unique_bridges[:top_n * 3]  # Return more for selection


def create_synthesis(summary: str, connected_memories: list):
    """Store a synthesized insight and link related memories."""
    mem_id = brain.store(
        f"Cross-domain insight: {summary}",
        collection='clarvis-learnings',
        importance=0.8,
        tags=['synthesis', 'cross-domain', 'insight']
    )

    # Create relationships between connected memories
    if len(connected_memories) >= 2:
        try:
            for i, mid in enumerate(connected_memories[:4]):
                for j_mid in connected_memories[i+1:4]:
                    brain.add_relationship(
                        from_id=mid,
                        to_id=j_mid,
                        relationship_type='synthesized_with'
                    )
        except Exception as e:
            print(f"  Relationship creation note: {e}")

    return mem_id


def run_synthesis_cycle():
    """Run a full cross-domain synthesis cycle."""
    print("=== Knowledge Synthesis: Cross-Domain Connections ===\n")

    # Phase 1: Keyword-based cross-domain connections
    print("Phase 1: Keyword cross-domain analysis")
    connections = find_cross_domain_connections(min_collections=2)
    print(f"  Found {len(connections)} cross-domain concepts\n")

    # Phase 2: Semantic bridges
    print("Phase 2: Semantic bridge detection")
    bridges = find_semantic_bridges(top_n=5)
    print(f"  Found {len(bridges)} semantic bridges\n")

    # Phase 3: Synthesize and store insights
    print("Phase 3: Storing synthesized insights")
    stored = 0

    # Store top keyword connections
    for conn in connections[:5]:
        concept = conn['concept']
        colls = ', '.join(c.replace('clarvis-', '') for c in conn['collections'])
        mem_ids = [e['id'] for e in conn['entries'][:4]]
        summary = (
            f"Concept '{concept}' bridges {conn['cross_domain_strength']} domains "
            f"({colls}), connecting {conn['total_memories']} memories"
        )
        print(f"  [keyword] {summary}")
        create_synthesis(summary, mem_ids)
        stored += 1

    # Store top semantic bridges
    for bridge in bridges[:3]:
        src = bridge['source_collection'].replace('clarvis-', '')
        tgt = bridge['target_collection'].replace('clarvis-', '')
        summary = (
            f"Semantic bridge between {src} and {tgt}: "
            f"'{bridge['source_snippet'][:50]}...' connects to "
            f"'{bridge['target_snippet'][:50]}...'"
        )
        print(f"  [semantic] {summary}")
        create_synthesis(summary, [bridge['source_id'], bridge['target_id']])
        stored += 1

    print(f"\nStored {stored} synthesized insights total")
    return {'keyword_connections': connections[:10], 'semantic_bridges': bridges[:5], 'stored': stored}


if __name__ == "__main__":
    results = run_synthesis_cycle()
    print("\n--- Top 3 Cross-Domain Concepts ---")
    for c in results['keyword_connections'][:3]:
        colls = ', '.join(c['collections'])
        print(f"  '{c['concept']}' → {c['cross_domain_strength']} collections, "
              f"{c['total_memories']} memories ({colls})")
