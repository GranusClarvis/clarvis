"""CLI interface for ClarvisEpisodic.

Usage:
    python -m clarvis_episodic encode <task> <section> <salience> <outcome> [duration] [error]
    python -m clarvis_episodic recall [query]
    python -m clarvis_episodic failures [n]
    python -m clarvis_episodic stats
    python -m clarvis_episodic synthesize
    python -m clarvis_episodic export [path]
    python -m clarvis_episodic import <path> [--replace]
"""

import json
import sys

from clarvis_episodic.core import EpisodicStore


def main():
    if len(sys.argv) < 2:
        print("ClarvisEpisodic — ACT-R episodic memory system")
        print()
        print("Usage: python -m clarvis_episodic <command> [args]")
        print()
        print("Commands:")
        print("  encode <task> <section> <salience> <outcome> [duration] [error]")
        print("  recall [query]          — Recall similar episodes")
        print("  failures [n]            — Recall failure episodes")
        print("  stats                   — Memory statistics")
        print("  synthesize              — Pattern analysis report")
        print("  export [path]           — Export episodes to JSON")
        print("  import <path> [--replace] — Import episodes from JSON")
        print()
        print("Environment:")
        print("  EPISODIC_DATA_DIR       — Data directory (default: ./data)")
        print("  EPISODIC_MAX_EPISODES   — Max episodes to retain (default: 500)")
        sys.exit(1)

    import os

    data_dir = os.environ.get("EPISODIC_DATA_DIR", "./data")
    max_eps = int(os.environ.get("EPISODIC_MAX_EPISODES", "500"))
    store = EpisodicStore(data_dir=data_dir, max_episodes=max_eps)

    cmd = sys.argv[1]

    if cmd == "encode":
        if len(sys.argv) < 6:
            print("Usage: encode <task> <section> <salience> <outcome> [duration] [error]")
            sys.exit(1)
        ep = store.encode(
            task=sys.argv[2],
            section=sys.argv[3],
            salience=float(sys.argv[4]),
            outcome=sys.argv[5],
            duration_s=int(sys.argv[6]) if len(sys.argv) > 6 else 0,
            error_msg=sys.argv[7] if len(sys.argv) > 7 else None,
        )
        print(json.dumps(ep, indent=2))

    elif cmd == "recall":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        episodes = store.recall(query, n=n)
        if not episodes:
            print("No matching episodes found.")
        for ep in episodes:
            print(f"  [{ep['outcome']}] (act={ep['activation']:.2f}) {ep['task'][:80]}")

    elif cmd == "failures":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        fails = store.failures(n=n)
        if not fails:
            print("No failure episodes recorded.")
        for ep in fails:
            print(f"  (act={ep['activation']:.2f}, val={ep['valence']:.2f}) {ep['task'][:70]}")
            if ep.get("error"):
                print(f"    Error: {ep['error'][:100]}")

    elif cmd == "stats":
        stats = store.stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "synthesize":
        result = store.synthesize()
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)

        print("=" * 60)
        print("EPISODIC MEMORY SYNTHESIS REPORT")
        print("=" * 60)
        print(f"\nEpisodes analyzed : {result['total_episodes']}")
        print("Outcome breakdown :")
        for outcome, count in sorted(result["outcomes"].items()):
            print(f"  {outcome:15s} {count}")
        print(f"Success rate      : {result['success_rate']:.0%}")

        print("\nTop action verbs (successes):")
        for verb, count in result["top_success_actions"]:
            print(f"  {count:2d}x  {verb}")

        if result["top_failure_actions"]:
            print("\nTop action verbs (failures):")
            for verb, count in result["top_failure_actions"]:
                print(f"  {count:2d}x  {verb}")

        print("\nSection outcomes:")
        for sec, counts in sorted(result["section_outcomes"].items()):
            s = counts.get("success", 0)
            f = sum(v for k, v in counts.items() if k != "success")
            bar = "#" * s + "." * f
            print(f"  {sec:22s}  {bar}  ({s}ok {f}fail)")

        if result["error_types"]:
            print("\nError type breakdown:")
            for etype, count in result["error_types"].items():
                print(f"  {count:2d}x  {etype}")

        if result["recommendations"]:
            print(f"\nRecommendations ({len(result['recommendations'])}):")
            for rec in result["recommendations"]:
                print(f"  -> {rec}")
        else:
            print("\nNo recommendations — patterns look healthy.")

    elif cmd == "export":
        path = sys.argv[2] if len(sys.argv) > 2 else None
        data = store.export(path)
        if not path:
            print(data)
        else:
            print(f"Exported {len(store.episodes)} episodes to {path}")

    elif cmd == "import":
        if len(sys.argv) < 3:
            print("Usage: import <path> [--replace]")
            sys.exit(1)
        path = sys.argv[2]
        merge = "--replace" not in sys.argv
        imported = store.import_episodes(path, merge=merge)
        print(f"Imported {imported} episodes (merge={'yes' if merge else 'no, replaced'})")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
