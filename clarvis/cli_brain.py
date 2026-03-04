"""clarvis brain — ClarvisDB brain operations.

Delegates to clarvis.brain (spine) which is the canonical implementation.
The old scripts/brain.py is a thin re-export wrapper.
"""

import json
import sys
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = "/home/agent/.openclaw/workspace"


def _get_brain():
    """Lazy-load brain singleton with hooks registered."""
    sys.path.insert(0, f"{WORKSPACE}/scripts")
    from clarvis.brain import get_brain
    b = get_brain()
    try:
        from clarvis.brain.hooks import register_default_hooks
        register_default_hooks(b)
    except Exception:
        pass
    return b


@app.command()
def health():
    """Full health report — stats, consolidation, graph, store/recall test."""
    b = _get_brain()
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


@app.command()
def stats():
    """Quick brain statistics as JSON."""
    b = _get_brain()
    print(json.dumps(b.stats(), indent=2))


@app.command()
def search(query: str, n: int = 5):
    """Search memories by query."""
    b = _get_brain()
    results = b.recall(query, n=n, include_related=True)
    for r in results:
        print(f"[{r['collection']}] {r['document'][:80]}...")
        if r.get("related"):
            print(f"  └─ Related: {len(r['related'])} memories")


@app.command()
def optimize():
    """Run decay and prune (quick optimization)."""
    b = _get_brain()
    result = b.optimize()
    print("Optimization complete:")
    print(f"  Decayed: {result['decayed']}")
    print(f"  Pruned: {result['pruned']}")
    print(f"  Stale: {result['stale_count']}")
    print(f"  Total memories: {result['stats']['total_memories']}")


@app.command("optimize-full")
def optimize_full():
    """Full optimization — decay, prune, dedup, noise clean, archive."""
    b = _get_brain()
    result = b.optimize(full=True)
    print("Full optimization complete:")
    print(f"  Decayed: {result['decayed']}")
    print(f"  Pruned: {result['pruned']}")
    print(f"  Stale: {result['stale_count']}")
    print(f"  Duplicates removed: {result.get('duplicates_removed', 'N/A')}")
    print(f"  Noise pruned: {result.get('noise_pruned', 'N/A')}")
    print(f"  Archived: {result.get('archived', 'N/A')}")
    if result.get("consolidation_error"):
        print(f"  WARNING: {result['consolidation_error']}")
    print(f"  Total memories: {result['stats']['total_memories']}")


@app.command()
def backfill():
    """Backfill missing graph nodes from edges."""
    b = _get_brain()
    count = b.backfill_graph_nodes()
    s = b.stats()
    print("Graph node backfill complete:")
    print(f"  Nodes backfilled: {count}")
    print(f"  Total nodes now: {s['graph_nodes']}")
    print(f"  Total edges: {s['graph_edges']}")


@app.command()
def recent(days: int = 7):
    """Show recent memories (default: last 7 days)."""
    b = _get_brain()
    results = b.recall_recent(days=days)
    print(f"Memories from last {days} days:")
    for r in results:
        print(f"  [{r['collection']}] {r['document'][:60]}...")


@app.command()
def stale():
    """Show memories not accessed in 30+ days."""
    b = _get_brain()
    stale_mems = b.get_stale_memories(days=30)
    print(f"Memories not accessed in 30 days: {len(stale_mems)}")
    for s in stale_mems[:10]:
        print(f"  {s['last_accessed']} [{s['collection']}] {s['document']}...")


@app.command()
def crosslink():
    """Build cross-collection edges for all memories."""
    b = _get_brain()
    result = b.bulk_cross_link(verbose=True)
    print("\nCross-linking complete:")
    print(f"  New edges: {result['new_edges']}")
    print(f"  Scanned: {result['memories_scanned']} memories")
    print(f"  Total edges: {result['total_edges']}")


@app.command("edge-decay")
def edge_decay(
    half_life: int = 30,
    prune_below: float = 0.02,
    dry_run: bool = False,
):
    """Decay Hebbian edge weights by age and prune weak ones."""
    b = _get_brain()
    result = b.decay_edges(
        half_life_days=half_life,
        prune_below=prune_below,
        dry_run=dry_run,
    )
    mode = "DRY RUN" if dry_run else "Applied"
    print(f"Edge decay ({mode}):")
    print(f"  Decayed: {result['decayed']}")
    print(f"  Pruned: {result['pruned']}")
    print(f"  Edges: {result['total_before']} → {result['total_after']}")
    print(f"  Avg weight (hebbian): {result['avg_weight']}")
