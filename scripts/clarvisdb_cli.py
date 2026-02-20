#!/usr/bin/env python3
"""
ClarvisDB CLI - Quick access to persistent memory
Usage:
  clarvisdb_cli.py store <collection> <text> [--importance 0.9]
  clarvisdb_cli.py recall <query>
  clarvisdb_cli.py list <collection>
"""
import sys
import argparse
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

from brain import brain, IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE

COLLECTIONS = {
    "identity": IDENTITY,
    "preferences": PREFERENCES,
    "learnings": LEARNINGS,
    "infrastructure": INFRASTRUCTURE
}

def cmd_store(args):
    col = COLLECTIONS.get(args.collection, LEARNINGS)
    tags = args.tags.split(",") if args.tags else []
    brain.store(args.text, collection=col, importance=args.importance, source="cli", tags=tags)
    print(f"Stored to {args.collection}: {args.text[:50]}...")

def cmd_recall(args):
    results = brain.recall(args.query)
    if results:
        print(f"Found {len(results)} results:")
        for r in results:
            print(f"  - [{r['collection']}] {r['document']}")
    else:
        print("No results found.")

def cmd_list(args):
    col = COLLECTIONS.get(args.collection, LEARNINGS)
    memories = brain.get(col, n=10)
    print(f"Collection: {args.collection}")
    for mem in memories:
        print(f"  - {mem['document']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClarvisDB CLI")
    sub = parser.add_subparsers()

    p_store = sub.add_parser("store", help="Store a memory")
    p_store.add_argument("collection", choices=COLLECTIONS.keys(), default="learnings")
    p_store.add_argument("text")
    p_store.add_argument("--importance", type=float, default=0.7)
    p_store.add_argument("--tags", default="")
    p_store.set_defaults(func=cmd_store)

    p_recall = sub.add_parser("recall", help="Recall memories")
    p_recall.add_argument("query")
    p_recall.set_defaults(func=cmd_recall)

    p_list = sub.add_parser("list", help="List memories in collection")
    p_list.add_argument("collection", choices=COLLECTIONS.keys(), default="learnings")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
