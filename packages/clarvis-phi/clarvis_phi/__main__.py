"""CLI interface for ClarvisPhi.

Usage:
    python -m clarvis_phi compute <nodes.json> <edges.json>
    python -m clarvis_phi history <history.json>
    python -m clarvis_phi trend <history.json>
    python -m clarvis_phi demo
"""

import json
import sys

from clarvis_phi.core import compute_phi, PhiConfig


def _demo():
    """Run a demo with synthetic data to show what ClarvisPhi does."""
    nodes = {
        "id_1": "identity", "id_2": "identity", "id_3": "identity",
        "goal_1": "goals", "goal_2": "goals",
        "mem_1": "memories", "mem_2": "memories", "mem_3": "memories",
        "inf_1": "infra", "inf_2": "infra",
    }
    edges = [
        # Intra-partition
        ("id_1", "id_2", "similar"), ("id_2", "id_3", "similar"),
        ("goal_1", "goal_2", "similar"),
        ("mem_1", "mem_2", "similar"), ("mem_2", "mem_3", "similar"),
        ("inf_1", "inf_2", "similar"),
        # Cross-partition bridges
        ("id_1", "goal_1", "cross"), ("goal_2", "mem_1", "cross"),
        ("mem_3", "inf_1", "cross"), ("id_3", "mem_2", "cross"),
    ]

    result = compute_phi(nodes, edges)
    _print_result(result, len(nodes), len(edges))


def _print_result(result, n_nodes=None, n_edges=None):
    """Pretty-print a Phi result."""
    print(f"Phi (Integrated Information) = {result['phi']}")
    print()
    print("Components:")
    for k, v in result["components"].items():
        bar = "\u2588" * int(v * 20) + "\u2591" * (20 - int(v * 20))
        print(f"  {k:35s} {bar} {v:.4f}")

    if result.get("details", {}).get("intra_density_per_partition"):
        print()
        print("Intra-partition density:")
        for part, d in result["details"]["intra_density_per_partition"].items():
            print(f"  {part:35s} {d:.4f}")

    if result.get("details", {}).get("semantic_pairs"):
        print()
        print("Semantic cross-partition pairs:")
        for pair, sim in result["details"]["semantic_pairs"].items():
            print(f"  {pair:50s} {sim:.4f}")

    if n_nodes is not None:
        print()
        print(f"Nodes: {n_nodes}  Edges: {n_edges}")

    mip = result.get("partition_analysis", {})
    if mip.get("mip_partition"):
        print()
        print(f"MIP (Minimum Information Partition): {mip['mip_partition']}")
        print(f"  MIP loss: {mip['mip_loss']:.4f} (lower = weaker link to system)")
        for p, loss in sorted(mip["per_partition_loss"].items(), key=lambda x: x[1]):
            print(f"    {p:30s} loss={loss:.4f}")

    print()
    print(result["interpretation"])


def main():
    if len(sys.argv) < 2:
        print("ClarvisPhi -- IIT-inspired information integration metric")
        print()
        print("Usage: python -m clarvis_phi <command> [args]")
        print()
        print("Commands:")
        print("  demo                           Run with synthetic data")
        print("  compute <nodes.json> <edges.json>  Compute Phi from JSON files")
        print("  history <history.json>         Show Phi history")
        print("  trend <history.json>           Analyze Phi trend")
        print()
        print("JSON formats:")
        print('  nodes.json: {"node_id": "partition_name", ...}')
        print('  edges.json: [["from", "to", "type"], ...]')
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "demo":
        _demo()

    elif cmd == "compute":
        if len(sys.argv) < 4:
            print("Usage: compute <nodes.json> <edges.json>")
            sys.exit(1)
        with open(sys.argv[2]) as f:
            nodes = json.load(f)
        with open(sys.argv[3]) as f:
            raw_edges = json.load(f)
        edges = [(e[0], e[1], e[2] if len(e) > 2 else "unknown") for e in raw_edges]
        result = compute_phi(nodes, edges)
        _print_result(result, len(nodes), len(edges))

    elif cmd == "history":
        if len(sys.argv) < 3:
            print("Usage: history <history.json>")
            sys.exit(1)
        with open(sys.argv[2]) as f:
            history = json.load(f)
        if not history:
            print("No history found.")
            sys.exit(0)
        print(f"Phi History ({len(history)} measurements):")
        for h in history:
            ts = h["timestamp"][:19]
            phi = h["phi"]
            bar = "\u2588" * int(phi * 20) + "\u2591" * (20 - int(phi * 20))
            mem = h.get("total_memories", "?")
            edg = h.get("total_edges", "?")
            print(f"  {ts}  {bar}  Phi={phi:.4f}  (nodes={mem}, edges={edg})")

    elif cmd == "trend":
        if len(sys.argv) < 3:
            print("Usage: trend <history.json>")
            sys.exit(1)
        from clarvis_phi.tracker import PhiTracker
        tracker = PhiTracker(sys.argv[2])
        result = tracker.trend()
        print(json.dumps(result, indent=2))

    elif cmd == "json":
        # Machine-readable output
        if len(sys.argv) < 4:
            print("Usage: json <nodes.json> <edges.json>")
            sys.exit(1)
        with open(sys.argv[2]) as f:
            nodes = json.load(f)
        with open(sys.argv[3]) as f:
            raw_edges = json.load(f)
        edges = [(e[0], e[1], e[2] if len(e) > 2 else "unknown") for e in raw_edges]
        result = compute_phi(nodes, edges)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
