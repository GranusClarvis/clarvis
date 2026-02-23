"""CLI interface for ClarvisAttention.

Usage:
    python -m clarvis_attention submit <content> [--source SRC] [--importance 0.5]
    python -m clarvis_attention add <content> [--importance 0.5]
    python -m clarvis_attention focus
    python -m clarvis_attention tick
    python -m clarvis_attention broadcast
    python -m clarvis_attention query <text>
    python -m clarvis_attention activate <text>
    python -m clarvis_attention stats
    python -m clarvis_attention clear

Environment:
    ATTENTION_DATA_DIR  — Directory for persistence (default: ./data/attention)
    ATTENTION_CAPACITY  — Spotlight capacity (default: 7)
"""

import json
import os
import sys

from clarvis_attention.spotlight import AttentionSpotlight


def _get_spotlight() -> AttentionSpotlight:
    data_dir = os.environ.get("ATTENTION_DATA_DIR", "./data/attention")
    capacity = int(os.environ.get("ATTENTION_CAPACITY", "7"))
    persist_path = os.path.join(data_dir, "spotlight.json")
    return AttentionSpotlight(capacity=capacity, persist_path=persist_path)


def main():
    if len(sys.argv) < 2:
        print("ClarvisAttention — GWT attention spotlight")
        print()
        print("Usage: clarvis-attention <command> [args]")
        print()
        print("Commands:")
        print("  submit <content> [--source SRC] [--importance N] [--relevance N] [--boost N]")
        print("  add <content> [--importance N]     — Working-memory-compatible add")
        print("  focus                              — Show current spotlight")
        print("  tick                               — Run competition cycle")
        print("  broadcast                          — Show broadcast summary")
        print("  query <text>                       — Find relevant items")
        print("  activate <text>                    — Spreading activation")
        print("  stats                              — Attention statistics")
        print("  clear                              — Reset spotlight")
        print("  export                             — Export state as JSON")
        print("  import <path>                      — Import state from JSON")
        print()
        print("Environment:")
        print("  ATTENTION_DATA_DIR  — Persistence directory (default: ./data/attention)")
        print("  ATTENTION_CAPACITY  — Spotlight capacity (default: 7)")
        sys.exit(1)

    spotlight = _get_spotlight()
    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "submit":
        if not args:
            print("Usage: submit <content> [--source SRC] [--importance N]")
            sys.exit(1)
        content_parts = []
        source = "cli"
        importance = 0.7
        relevance = 0.8
        boost = 0.0
        i = 0
        while i < len(args):
            if args[i] == "--source" and i + 1 < len(args):
                source = args[i + 1]
                i += 2
            elif args[i] == "--importance" and i + 1 < len(args):
                importance = float(args[i + 1])
                i += 2
            elif args[i] == "--relevance" and i + 1 < len(args):
                relevance = float(args[i + 1])
                i += 2
            elif args[i] == "--boost" and i + 1 < len(args):
                boost = float(args[i + 1])
                i += 2
            else:
                content_parts.append(args[i])
                i += 1
        content = " ".join(content_parts)
        item = spotlight.submit(content, source=source, importance=importance,
                                relevance=relevance, boost=boost)
        print(f"Submitted: {item.id} (salience={item.salience():.3f})")

    elif cmd == "add":
        if not args:
            print("Usage: add <content> [--importance N]")
            sys.exit(1)
        content_parts = []
        importance = 0.5
        i = 0
        while i < len(args):
            if args[i] == "--importance" and i + 1 < len(args):
                importance = float(args[i + 1])
                i += 2
            else:
                content_parts.append(args[i])
                i += 1
        content = " ".join(content_parts)
        item = spotlight.add(content, importance=importance, source="cli")
        print(f"Added: {item.id} (salience={item.salience():.3f})")

    elif cmd == "focus":
        items = spotlight.focus()
        if not items:
            print("Spotlight is empty.")
        else:
            print(f"=== Attention Spotlight ({len(items)}/{spotlight.capacity}) ===")
            for i, item in enumerate(items):
                print(f"  {i + 1}. [{item['salience']:.3f}] {item['content'][:80]}")
                print(f"     src={item['source']}  access={item['access_count']}  "
                      f"ticks={item['ticks_in_spotlight']}/{item['ticks_total']}")

    elif cmd == "tick":
        result = spotlight.tick()
        print(f"Tick: spotlight={result['spotlight']}  decayed={result['decayed']}  "
              f"evicted={result['evicted']}  total={result['total']}")

    elif cmd == "broadcast":
        summary = spotlight.broadcast()
        print(summary)

    elif cmd == "query":
        if not args:
            print("Usage: query <text>")
            sys.exit(1)
        query = " ".join(args)
        results = spotlight.query_relevant(query)
        if not results:
            print("No relevant items found.")
        else:
            for r in results:
                print(f"  [{r['salience']:.3f}] {r['content'][:80]}")

    elif cmd == "activate":
        if not args:
            print("Usage: activate <text>")
            sys.exit(1)
        query = " ".join(args)
        results = spotlight.spreading_activation(query)
        if not results:
            print("No items activated.")
        else:
            print(f"Activated {len(results)} items:")
            for r in results:
                print(f"  [{r['salience']:.3f}] {r['content'][:80]}")

    elif cmd == "stats":
        s = spotlight.stats()
        print(json.dumps(s, indent=2))

    elif cmd == "clear":
        spotlight.clear()
        print("Spotlight cleared.")

    elif cmd == "export":
        data = spotlight.to_dict()
        print(json.dumps(data, indent=2))

    elif cmd == "import":
        if not args:
            print("Usage: import <path>")
            sys.exit(1)
        path = args[0]
        with open(path) as f:
            data = json.load(f)
        restored = AttentionSpotlight.from_dict(data)
        # Merge into current spotlight
        for item_id, item in restored.items.items():
            if item_id not in spotlight.items:
                spotlight.items[item_id] = item
        spotlight._save()
        print(f"Imported {len(restored.items)} items (merged into current state)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
