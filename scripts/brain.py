#!/usr/bin/env python3
"""Clarvis Brain — thin wrapper. Implementation in clarvis/brain/.

Usage:
    from brain import brain
    brain.store("important fact", importance=0.9, tags=["learning"])
    brain.recall("what do I know about X")
"""

import sys
import os

# Ensure clarvis package is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Re-export everything from clarvis.brain for backward compatibility
from clarvis.brain import (  # noqa: F401
    # Classes
    ClarvisBrain, LocalBrain, _LazyBrain,
    # Singletons
    brain, local_brain, get_brain, get_local_brain,
    # Constants
    DATA_DIR, LOCAL_DATA_DIR, GRAPH_FILE, LOCAL_GRAPH_FILE,
    IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS,
    CONTEXT, MEMORIES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES,
    ALL_COLLECTIONS, DEFAULT_COLLECTIONS,
    # Functions
    route_query, get_local_embedding_function,
    store_important, recall, remember, capture, search, global_search,
)

import json

if __name__ == "__main__":
    print("DEPRECATION: Use 'python3 -m clarvis brain <command>' instead of 'python3 scripts/brain.py'.", file=sys.stderr)

    # Register hooks for CLI usage (so optimize-full, recall scoring etc. work)
    b = get_brain()
    try:
        from clarvis.brain.hooks import register_default_hooks
        register_default_hooks(b)
    except Exception:
        pass  # Hooks are optional for CLI

    if len(sys.argv) < 2:
        print("Usage: brain.py <command> [args]")
        print("Commands:")
        print("  stats              - Show brain statistics")
        print("  health             - Full health report (stats + consolidation + graph)")
        print("  recall <query>     - Search memories")
        print("  recent [days]      - Recent memories (default 7 days)")
        print("  store <text>       - Store a memory")
        print("  optimize           - Run decay and prune")
        print("  optimize-full      - Run decay, prune, dedup, noise clean, archive")
        print("  backfill           - Backfill missing graph nodes from edges")
        print("  stale              - Show stale memories")
        print("  context            - Show current context")
        print("  crosslink          - Build cross-collection edges for all memories")
        print("  remember <text>    - High-importance store (--importance 0.8 --collection clarvis-learnings --tags t1,t2)")
        print("  global <query>     - GraphRAG global search (holistic queries)")
        print("  ingest-research [file] - Ingest research markdown into brain (all files if no arg)")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "stats":
        print(json.dumps(b.stats(), indent=2))
    elif cmd == "health":
        print("=== Clarvis Brain Health Report ===\n")

        s = b.stats()
        print(f"Memories: {s['total_memories']} across {len(s['collections'])} collections")
        for name, count in s["collections"].items():
            print(f"  {name}: {count}")
        print(f"\nGraph: {s['graph_nodes']} nodes, {s['graph_edges']} edges")

        referenced_nodes = set()
        for e in b.graph.get("edges", []):
            referenced_nodes.add(e.get("from", ""))
            referenced_nodes.add(e.get("to", ""))
        referenced_nodes.discard("")
        orphan_count = len(referenced_nodes - set(b.graph.get("nodes", {}).keys()))
        if orphan_count > 0:
            print(f"  WARNING: {orphan_count} nodes referenced by edges but not in graph (run: clarvis brain backfill)")
        else:
            print("  Graph nodes: OK (all edge references resolved)")

        try:
            from memory_consolidation import get_consolidation_stats
            cs = get_consolidation_stats()
            print("\nConsolidation status:")
            print(f"  Potential duplicates: {cs['potential_duplicates']}")
            print(f"  Potential noise: {cs['potential_noise']}")
            print(f"  Stale (archivable): {cs['stale_archivable']}")
            print(f"  Archived: {cs['archive_count']}")
            if cs['potential_duplicates'] > 0 or cs['potential_noise'] > 0:
                print("  Recommendation: run 'clarvis brain optimize-full' to clean")
        except Exception as e:
            print(f"\nConsolidation check failed: {e}")

        stale = b.get_stale_memories(days=30)
        print(f"\nStale memories (>30 days unaccessed): {len(stale)}")

        hc = b.health_check()
        print(f"\nStore/recall test: {hc['status']}")
        print("\n=== Health check complete ===")
    elif cmd == "recall" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        results = b.recall(query, include_related=True)
        for r in results:
            print(f"[{r['collection']}] {r['document'][:80]}...")
            if r.get('related'):
                print(f"  └─ Related: {len(r['related'])} memories")
    elif cmd == "recent":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        results = b.recall_recent(days=days)
        print(f"Memories from last {days} days:")
        for r in results:
            print(f"  [{r['collection']}] {r['document'][:60]}...")
    elif cmd == "store" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        mem_id = b.store(text)
        print(f"Stored: {mem_id}")
    elif cmd == "optimize":
        result = b.optimize()
        print("Optimization complete:")
        print(f"  Decayed: {result['decayed']}")
        print(f"  Pruned: {result['pruned']}")
        print(f"  Stale: {result['stale_count']}")
        print(f"  Total memories: {result['stats']['total_memories']}")
    elif cmd == "optimize-full":
        result = b.optimize(full=True)
        print("Full optimization complete:")
        print(f"  Decayed: {result['decayed']}")
        print(f"  Pruned: {result['pruned']}")
        print(f"  Stale: {result['stale_count']}")
        print(f"  Duplicates removed: {result.get('duplicates_removed', 'N/A')}")
        print(f"  Noise pruned: {result.get('noise_pruned', 'N/A')}")
        print(f"  Archived: {result.get('archived', 'N/A')}")
        if result.get('consolidation_error'):
            print(f"  WARNING: {result['consolidation_error']}")
        print(f"  Total memories: {result['stats']['total_memories']}")
    elif cmd == "backfill":
        count = b.backfill_graph_nodes()
        s = b.stats()
        print("Graph node backfill complete:")
        print(f"  Nodes backfilled: {count}")
        print(f"  Total nodes now: {s['graph_nodes']}")
        print(f"  Total edges: {s['graph_edges']}")
    elif cmd == "stale":
        stale = b.get_stale_memories(days=30)
        print(f"Memories not accessed in 30 days: {len(stale)}")
        for s in stale[:10]:
            print(f"  {s['last_accessed']} [{s['collection']}] {s['document']}...")
    elif cmd == "context":
        print(f"Current context: {b.get_context()}")
    elif cmd == "crosslink":
        result = b.bulk_cross_link(verbose=True)
        print("\nCross-linking complete:")
        print(f"  New edges: {result['new_edges']}")
        print(f"  Scanned: {result['memories_scanned']} memories")
        print(f"  Total edges: {result['total_edges']}")
    elif cmd == "remember" and len(sys.argv) > 2:
        text_parts = []
        importance = 0.9
        collection = LEARNINGS
        tags = None
        source = "research"
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--importance" and i + 1 < len(sys.argv):
                try:
                    importance = float(sys.argv[i + 1])
                except ValueError:
                    pass
                i += 2
            elif sys.argv[i] == "--collection" and i + 1 < len(sys.argv):
                collection = sys.argv[i + 1]
                if not collection.startswith("clarvis-"):
                    collection = f"clarvis-{collection}"
                i += 2
            elif sys.argv[i] == "--tags" and i + 1 < len(sys.argv):
                tags = [t.strip() for t in sys.argv[i + 1].split(",")]
                i += 2
            elif sys.argv[i] == "--source" and i + 1 < len(sys.argv):
                source = sys.argv[i + 1]
                i += 2
            else:
                text_parts.append(sys.argv[i])
                i += 1
        text = " ".join(text_parts)
        if text:
            mem_id = b.store(text, collection=collection, importance=importance,
                             tags=tags, source=source)
            print(f"Remembered: {mem_id} (importance={importance}, collection={collection})")
        else:
            print("Error: no text provided")
            sys.exit(1)
    elif cmd == "global":
        query = sys.argv[2] if len(sys.argv) > 2 else "What are the main themes?"
        level = sys.argv[3] if len(sys.argv) > 3 else "C1"
        results = global_search(query, level=level)
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r['score']:.3f}] {r['community_id']} ({r['size']} mem)")
            print(f"   {', '.join(r.get('keywords', [])[:6])}")
            print(f"   {r['summary'][:150]}")
    elif cmd == "ingest-research":
        import glob as glob_mod
        import hashlib
        research_dir = "/home/agent/.openclaw/workspace/memory/research"
        tracker_file = "/home/agent/.openclaw/workspace/data/research_ingested.json"
        force = "--force" in sys.argv

        tracker = {}
        if os.path.exists(tracker_file):
            try:
                with open(tracker_file) as tf:
                    tracker = json.load(tf)
            except Exception:
                tracker = {}

        if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
            files = [sys.argv[2]]
        else:
            files = sorted(glob_mod.glob(os.path.join(research_dir, "*.md")))

        if not files:
            print("No research files found")
            sys.exit(0)

        total_stored = 0
        for filepath in files:
            if not os.path.exists(filepath):
                print(f"File not found: {filepath}")
                continue

            filename = os.path.basename(filepath)

            with open(filepath, "rb") as hf:
                file_hash = hashlib.sha256(hf.read()).hexdigest()[:16]

            prev = tracker.get(filename, {})
            if not force and prev.get("hash") == file_hash:
                print(f"\nSkipping: {filename} (already ingested, hash match)")
                continue

            with open(filepath) as f:
                content = f.read()

            print(f"\nIngesting: {filename} (hash={file_hash})")

            sections = content.split("\n## ")
            title = sections[0].strip().split("\n")[0].replace("# ", "")
            memory_ids = []

            for section in sections[1:]:
                section_lines = section.strip().split("\n")
                section_title = section_lines[0].strip()
                section_body = "\n".join(section_lines[1:]).strip()

                if len(section_body) < 30:
                    continue

                memory_text = f"[RESEARCH: {title}] {section_title}: {section_body[:500]}"
                mem_id = b.store(
                    memory_text,
                    collection=LEARNINGS,
                    importance=0.8,
                    tags=["research", "paper", filename.replace(".md", "")],
                    source="research_ingest"
                )
                memory_ids.append(mem_id)
                total_stored += 1
                print(f"  Stored: {section_title[:60]} → {mem_id}")

            summary = f"[RESEARCH SUMMARY] {title} — ingested from {filename}, {len(memory_ids)} sections"
            mid = b.store(summary, collection=LEARNINGS, importance=0.85,
                    tags=["research", "summary"], source="research_ingest")
            memory_ids.append(mid)
            total_stored += 1

            import time as _time
            tracker[filename] = {
                "hash": file_hash,
                "ingested_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
                "memory_count": len(memory_ids),
                "memory_ids": memory_ids,
            }

        import shutil as _shutil
        ingested_dir = os.path.join(research_dir, "ingested")
        os.makedirs(ingested_dir, exist_ok=True)
        for filepath in files:
            filename = os.path.basename(filepath)
            if filename in tracker and tracker[filename].get("memory_count", 0) > 0:
                dest = os.path.join(ingested_dir, filename)
                if os.path.exists(filepath) and not os.path.exists(dest):
                    _shutil.move(filepath, dest)
                    print(f"  Moved {filename} → ingested/")

        os.makedirs(os.path.dirname(tracker_file), exist_ok=True)
        with open(tracker_file, "w") as tf:
            json.dump(tracker, tf, indent=2)
        print(f"\nIngestion complete: {total_stored} memories stored (tracker updated)")
    else:
        print(f"Unknown command: {cmd}")
