#!/usr/bin/env python3
"""
Clarvis Memory Provider
A drop-in replacement for OpenClaw's memory_search that uses ClarvisDB

This provides the same interface as OpenClaw's Gemini-based memory_search
but uses the local ClarvisDB brain instead.

Usage:
    # Instead of memory_search tool, use:
    from clarvis_memory import clarvis_search, clarvis_store
    
    results = clarvis_search("query")
    clarvis_store("important fact", importance=0.9)
"""

import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")


def clarvis_search(query, max_results=5, min_importance=None, collections=None):
    """
    Search ClarvisDB for memories matching query.
    
    This is the ClarvisDB equivalent of memory_search tool.
    
    Args:
        query: Search query
        max_results: Maximum results to return
        min_importance: Filter by minimum importance (0-1)
        collections: List of collections to search (None = all)
    
    Returns:
        dict with results, similar to memory_search format
    """
    from brain import brain
    
    results = brain.recall(
        query,
        n=max_results,
        min_importance=min_importance,
        collections=collections,
        include_related=True
    )
    
    # Format like memory_search output
    formatted = {
        "results": [],
        "query": query,
        "total": len(results),
        "provider": "clarvisdb"
    }
    
    for r in results:
        formatted["results"].append({
            "path": r.get("collection", "unknown"),
            "document": r["document"],
            "metadata": r.get("metadata", {}),
            "importance": r.get("metadata", {}).get("importance", 0.5),
            "related": r.get("related", [])
        })
    
    return formatted


def clarvis_store(text, collection=None, importance=0.7, tags=None, source="manual"):
    """
    Store a memory in ClarvisDB.
    
    Args:
        text: Memory content
        collection: Target collection (auto-detected if None)
        importance: Importance score (0-1)
        tags: List of tags
        source: Source identifier
    
    Returns:
        Memory ID
    """
    from brain import brain
    from smart_capture import detect_category_smart, extract_tags_smart
    
    if collection is None:
        collection = detect_category_smart(text)
    
    if tags is None:
        tags = extract_tags_smart(text)
    
    return brain.store(
        text,
        collection=collection,
        importance=importance,
        tags=tags,
        source=source
    )


def clarvis_capture(message, role="user", context=None):
    """
    Smart capture - automatically decide if message is worth remembering.
    
    Args:
        message: Message text
        role: "user" or "assistant"
        context: Conversation context
    
    Returns:
        Capture result
    """
    from smart_capture import smart_capture
    
    return smart_capture(message, source=f"{role}_message", context=context)


def clarvis_context():
    """
    Get current context and recent important memories.
    Good for session startup.
    """
    from brain import brain
    
    context = brain.get_context()
    recent = brain.recall_recent(days=7, n=10)
    goals = brain.get_goals()[:5]
    stats = brain.stats()
    
    return {
        "current_context": context,
        "recent_memories": len(recent),
        "active_goals": len(goals),
        "total_memories": stats["total_memories"],
        "collections": stats["collections"]
    }


def clarvis_forget(query, dry_run=True):
    """
    Find and optionally remove memories matching query.
    
    Args:
        query: What to forget
        dry_run: If True, only show what would be deleted
    
    Returns:
        List of memories that match
    """
    from brain import brain
    
    results = brain.recall(query, n=20)
    
    to_forget = []
    for r in results:
        # Check if it's a close match
        text_lower = r["document"].lower()
        query_lower = query.lower()
        
        if query_lower in text_lower:
            to_forget.append(r)
    
    if not dry_run and to_forget:
        for r in to_forget:
            col = brain.collections[r["collection"]]
            col.delete(ids=[r["id"]])
    
    return {
        "found": len(to_forget),
        "deleted": 0 if dry_run else len(to_forget),
        "dry_run": dry_run,
        "memories": [r["document"][:50] for r in to_forget[:5]]
    }


# Convenience aliases matching OpenClaw patterns
search = clarvis_search
store = clarvis_store
capture = clarvis_capture


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clarvis Memory Provider")
    parser.add_argument("action", choices=["search", "store", "context", "capture"])
    parser.add_argument("--query", "-q", help="Search query")
    parser.add_argument("--text", "-t", help="Text to store")
    parser.add_argument("--importance", "-i", type=float, default=0.7)
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    
    args = parser.parse_args()
    
    if args.action == "search" and args.query:
        results = clarvis_search(args.query)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Found {results['total']} results for '{args.query}':")
            for r in results["results"]:
                print(f"  [{r['path']}] {r['document'][:60]}...")
    
    elif args.action == "store" and args.text:
        mem_id = clarvis_store(args.text, importance=args.importance)
        print(f"Stored: {mem_id}")
    
    elif args.action == "context":
        ctx = clarvis_context()
        if args.json:
            print(json.dumps(ctx, indent=2))
        else:
            print(f"Context: {ctx['current_context']}")
            print(f"Recent memories: {ctx['recent_memories']}")
            print(f"Total: {ctx['total_memories']}")
    
    elif args.action == "capture" and args.text:
        result = clarvis_capture(args.text)
        status = "captured" if result["captured"] else "skipped"
        print(f"{status}: {result.get('reason', result.get('memory_id', ''))}")
    
    else:
        parser.print_help()
