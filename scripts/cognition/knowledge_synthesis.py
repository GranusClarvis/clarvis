#!/usr/bin/env python3
"""
Knowledge Synthesis — Batch cross-domain connection finder (reflection pipeline).

Scans all brain collections, finds connections that span collection boundaries,
and creates synthesized insights about non-obvious relationships.

NOTE: This is the *batch* synthesis module, run by cron_reflection.sh step 3.
It stores new cross-domain insights into the brain.
The *query-time* module is clarvis/context/knowledge_synthesis.py — that one
synthesizes knowledge for context briefs without storing anything.
"""

import sys
import os
import logging
from clarvis.brain import brain, ALL_COLLECTIONS
from collections import defaultdict
import re

logger = logging.getLogger(__name__)

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
        try:
            memories = brain.get(coll, n=200)
        except Exception as e:
            logger.error("Failed to load collection '%s': %s", coll, e)
            continue
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
        try:
            source_memories = brain.get(source_coll, n=10)
        except Exception as e:
            logger.error("Failed to get memories from '%s': %s", source_coll, e)
            continue
        for mem in source_memories[:5]:  # Top 5 from each collection
            doc = mem.get('document', '')
            if len(doc) < 20:
                continue

            # Search other collections for semantic matches
            target_colls = [c for c in key_collections if c != source_coll]
            try:
                results = brain.recall(doc, collections=target_colls, n=3)
            except Exception as e:
                logger.error("Semantic recall failed for '%s': %s", doc[:40], e)
                continue

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
    """Store a synthesized insight and link related memories.

    Returns mem_id on success, None on failure.
    """
    try:
        mem_id = brain.store(
            f"Cross-domain insight: {summary}",
            collection='clarvis-learnings',
            importance=0.8,
            tags=['synthesis', 'cross-domain', 'insight']
        )
    except Exception as e:
        logger.error("Failed to store synthesis '%s': %s", summary[:60], e)
        return None

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
            logger.warning("Relationship creation note: %s", e)

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
    failed = 0
    for conn in connections[:5]:
        concept = conn['concept']
        colls = ', '.join(c.replace('clarvis-', '') for c in conn['collections'])
        mem_ids = [e['id'] for e in conn['entries'][:4]]
        summary = (
            f"Concept '{concept}' bridges {conn['cross_domain_strength']} domains "
            f"({colls}), connecting {conn['total_memories']} memories"
        )
        print(f"  [keyword] {summary}")
        result = create_synthesis(summary, mem_ids)
        if result is not None:
            stored += 1
        else:
            failed += 1

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
        result = create_synthesis(summary, [bridge['source_id'], bridge['target_id']])
        if result is not None:
            stored += 1
        else:
            failed += 1

    if failed:
        logger.warning("Synthesis pipeline: %d/%d insights failed to store", failed, failed + stored)
    print(f"\nStored {stored} synthesized insights total ({failed} failed)")
    return {'keyword_connections': connections[:10], 'semantic_bridges': bridges[:5], 'stored': stored, 'failed': failed}


# ---------------------------------------------------------------------------
# Learning Strategy Analysis — weekly review of learning source effectiveness
# ---------------------------------------------------------------------------

# Source categories: map metadata 'source' values + tags to human-readable buckets
_SOURCE_BUCKETS = {
    'episodes': {'episodic_memory', 'episode'},
    'research': {'research', 'research_discovery'},
    'reflection': {'reflection', 'self_reflection', 'meta_learning',
                   'synthesis', 'self-assessment', 'self_representation',
                   'phi_metric', 'phi', 'internal'},
    'coding': {'conversation', 'code', 'implementation', 'tool_extraction',
               'procedural_memory', 'manual'},
    'system': {'system', 'canonical', 'migration', 'seed',
               'workspace_broadcast', 'refresh_priorities.py'},
}


def _classify_source(metadata: dict) -> str:
    """Classify a memory into a learning source bucket."""
    source = (metadata.get('source') or '').lower()
    tags_raw = metadata.get('tags', '[]')
    if isinstance(tags_raw, str):
        try:
            import json as _json
            tags = set(t.lower() for t in _json.loads(tags_raw))
        except (ValueError, TypeError):
            tags = set()
    elif isinstance(tags_raw, list):
        tags = set(t.lower() for t in tags_raw)
    else:
        tags = set()

    all_signals = {source} | tags

    for bucket, keywords in _SOURCE_BUCKETS.items():
        if all_signals & keywords:
            return bucket
    return 'other'


def _quality_score(metadata: dict) -> float:
    """Compute a quality score for a memory based on usage signals.

    Higher = more useful memory. Combines:
    - importance (current, after decay)
    - access_count (how often retrieved)
    - recall_success (how often it actually helped)
    """
    importance = float(metadata.get('importance', 0.5))
    access_count = int(metadata.get('access_count', 0))
    recall_success = int(metadata.get('recall_success', 0))

    # Normalize: importance 0-1, access log-scaled, recall log-scaled
    import math
    access_score = min(1.0, math.log1p(access_count) / 5.0)  # ~150 accesses = 1.0
    recall_score = min(1.0, math.log1p(recall_success) / 2.5)  # ~12 recalls = 1.0

    return 0.4 * importance + 0.35 * access_score + 0.25 * recall_score


def _build_strategy_paragraph(days, total, bucket_stats):
    """Build strategy recommendation paragraph from bucket statistics."""
    ranked = sorted(bucket_stats.items(), key=lambda x: -x[1]['avg_quality'])
    best_name, best_data = ranked[0] if ranked else ('none', {'avg_quality': 0, 'count': 0})
    worst_name, worst_data = ranked[-1] if len(ranked) > 1 else ('none', {'avg_quality': 0, 'count': 0})

    parts = [f"Weekly learning review ({days}d window, {total} new memories)."]

    if best_data['avg_quality'] > 0:
        parts.append(
            f"Highest-quality source: {best_name} "
            f"(avg={best_data['avg_quality']:.3f}, {best_data['count']} memories, "
            f"{best_data['share_pct']}% of total)."
        )

    if worst_name != best_name and worst_data['count'] > 0:
        parts.append(
            f"Lowest-quality source: {worst_name} "
            f"(avg={worst_data['avg_quality']:.3f}, {worst_data['count']} memories)."
        )

    _STRATEGY_ADVICE = {
        'episodes': "Strategy: episodes are the strongest learning channel — "
                    "continue prioritizing task execution with clear success/failure encoding.",
        'research': "Strategy: research sessions produce high-quality memories — "
                    "consider increasing research frequency or depth.",
        'reflection': "Strategy: reflection is the top learning source — "
                      "the synthesis pipeline is working well. Maintain current reflection depth.",
        'coding': "Strategy: coding/conversation sessions produce the best memories — "
                  "continue hands-on implementation focus.",
    }
    if best_name == 'episodes' and best_data['avg_quality'] <= 0.3:
        parts.append(f"Strategy: {best_name} leads quality. Investigate why other channels lag.")
    else:
        parts.append(_STRATEGY_ADVICE.get(
            best_name,
            f"Strategy: {best_name} leads quality. Investigate why other channels lag."
        ))

    if len(ranked) >= 2 and ranked[0][1]['share_pct'] > 70:
        parts.append(
            f"Warning: {ranked[0][0]} dominates at {ranked[0][1]['share_pct']}% — "
            "diversify learning sources for more robust knowledge."
        )

    return " ".join(parts), best_name, worst_name


def _compute_bucket_stats(recent):
    """Classify recent memories into source buckets and compute per-bucket stats."""
    buckets = defaultdict(lambda: {'count': 0, 'quality_scores': [], 'collections': set()})
    for mem in recent:
        meta = mem.get('metadata', {})
        bucket = _classify_source(meta)
        quality = _quality_score(meta)
        buckets[bucket]['count'] += 1
        buckets[bucket]['quality_scores'].append(quality)
        buckets[bucket]['collections'].add(mem.get('collection', 'unknown'))

    stats = {}
    for bucket, data in sorted(buckets.items(), key=lambda x: -x[1]['count']):
        scores = data['quality_scores']
        avg_quality = sum(scores) / len(scores) if scores else 0
        stats[bucket] = {
            'count': data['count'],
            'avg_quality': round(avg_quality, 3),
            'max_quality': round(max(scores), 3) if scores else 0,
            'collections': sorted(data['collections']),
            'share_pct': round(100 * data['count'] / len(recent), 1),
        }
        print(f"  {bucket:12s}: {data['count']:3d} memories, "
              f"avg_quality={avg_quality:.3f}, "
              f"share={stats[bucket]['share_pct']}%")
    return stats


def learning_strategy_analysis(days: int = 7) -> dict:
    """Analyze learning effectiveness over the past N days."""
    import time

    cutoff_epoch = time.time() - (days * 86400)
    print(f"=== Learning Strategy Analysis (past {days} days) ===\n")

    all_memories = load_all_memories()
    recent = []
    for mem in all_memories:
        meta = mem.get('metadata', {})
        created_epoch = meta.get('created_epoch', 0)
        if isinstance(created_epoch, str):
            try:
                created_epoch = float(created_epoch)
            except (ValueError, TypeError):
                created_epoch = 0
        if created_epoch >= cutoff_epoch:
            recent.append(mem)

    print(f"Total memories: {len(all_memories)}, recent ({days}d): {len(recent)}\n")

    if not recent:
        return {
            'recent_count': 0, 'buckets': {},
            'strategy': f"No new memories created in the past {days} days. "
                        "Learning pipeline may be stalled — check cron execution and brain.store() calls.",
        }

    bucket_stats = _compute_bucket_stats(recent)
    paragraph, best_name, worst_name = _build_strategy_paragraph(days, len(recent), bucket_stats)
    print(f"\n--- Strategy ---\n{paragraph}\n")

    return {
        'recent_count': len(recent),
        'buckets': dict(bucket_stats),
        'best_source': best_name,
        'worst_source': worst_name,
        'strategy': paragraph,
    }


def run_learning_strategy_and_digest(days: int = 7):
    """Run learning strategy analysis and write results to digest + brain."""
    results = learning_strategy_analysis(days)

    # Write strategy to digest
    try:
        sys.path.insert(0, os.path.join(os.environ.get('CLARVIS_WORKSPACE',
            os.path.expanduser('~/.openclaw/workspace')), 'scripts'))
        from tools.digest_writer import write_digest
        write_digest('reflection', results['strategy'])
        print("Strategy written to digest.md")
    except Exception as e:
        logger.warning("Could not write to digest: %s", e)

    # Store analysis insight in brain
    if results['recent_count'] > 0:
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            insight = (
                f"Learning strategy analysis ({now}): "
                f"{results['recent_count']} memories in {days}d. "
                f"Best source: {results.get('best_source', 'unknown')} "
                f"(avg quality {results.get('buckets', {}).get(results.get('best_source', ''), {}).get('avg_quality', '?')}). "
                f"Worst: {results.get('worst_source', 'unknown')}."
            )
            brain.store(
                insight,
                collection='clarvis-learnings',
                importance=0.7,
                tags=['meta-learning', 'learning-strategy', 'weekly-analysis'],
            )
            print(f"Stored insight in brain: {insight[:80]}...")
        except Exception as e:
            logger.warning("Could not store brain insight: %s", e)

    return results


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == 'learning-strategy':
        days = int(_sys.argv[2]) if len(_sys.argv) > 2 else 7
        run_learning_strategy_and_digest(days)
    else:
        results = run_synthesis_cycle()
        print("\n--- Top 3 Cross-Domain Concepts ---")
        for c in results['keyword_connections'][:3]:
            colls = ', '.join(c['collections'])
            print(f"  '{c['concept']}' → {c['cross_domain_strength']} collections, "
                  f"{c['total_memories']} memories ({colls})")
