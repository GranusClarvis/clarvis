"""clarvis brain — ClarvisDB brain operations.

Delegates to clarvis.brain (spine) which is the canonical implementation.
The old scripts/brain.py is a thin re-export wrapper.
"""

import json
import os
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))


def _get_brain():
    """Lazy-load brain singleton with hooks registered."""
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
        from clarvis.memory.memory_consolidation import get_consolidation_stats
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


@app.command("search-json")
def search_json(query: str, n: int = 10):
    """Search memories and emit structured JSON."""
    b = _get_brain()
    print(json.dumps(b.recall(query, n=n, include_related=True), indent=2))


@app.command()
def inspect(memory_id: str, collection: Optional[str] = None):
    """Inspect one memory by id."""
    b = _get_brain()
    mem = b.get_memory(memory_id, collection=collection)
    if not mem:
        print(json.dumps({"success": False, "message": f"Memory '{memory_id}' not found"}, indent=2))
        raise typer.Exit(1)
    print(json.dumps(mem, indent=2))


@app.command("list-collection")
def list_collection(
    collection: str,
    limit: int = 50,
    contains: Optional[str] = None,
):
    """List memories from a collection, optionally filtered by substring."""
    b = _get_brain()
    rows = b.get(collection, n=max(limit * 5, limit))
    if contains:
        needle = contains.lower()
        rows = [r for r in rows if needle in (r.get("document", "").lower())]
    print(json.dumps(rows[:limit], indent=2))


@app.command()
def revise(
    memory_id: str,
    new_text: str,
    reason: str = "updated",
    confidence: Optional[float] = None,
    valid_until: Optional[str] = None,
    collection: Optional[str] = None,
):
    """Revise a memory; old version becomes superseded."""
    b = _get_brain()
    print(json.dumps(
        b.revise(memory_id, new_text, collection=collection, reason=reason, confidence=confidence, valid_until=valid_until),
        indent=2,
    ))


@app.command("update-meta")
def update_meta(
    memory_id: str,
    collection: Optional[str] = None,
    confidence: Optional[float] = None,
    valid_until: Optional[str] = None,
    status: Optional[str] = None,
):
    """Patch selected metadata fields on a memory."""
    b = _get_brain()
    patch = {}
    if confidence is not None:
        patch["confidence"] = confidence
    if valid_until is not None:
        patch["valid_until"] = valid_until
    if status is not None:
        patch["status"] = status
    if not patch:
        print(json.dumps({"success": False, "message": "No metadata fields provided"}, indent=2))
        raise typer.Exit(1)
    print(json.dumps(b.update_memory(memory_id, collection=collection, metadata_patch=patch), indent=2))


@app.command()
def delete(
    memory_id: str,
    collection: Optional[str] = None,
    reason: str = "manual",
    hard: bool = False,
):
    """Delete or retire a memory. Default is safe soft-delete."""
    b = _get_brain()
    print(json.dumps(b.delete_memory(memory_id, collection=collection, reason=reason, hard=hard), indent=2))


@app.command()
def supersede(
    keep_id: str,
    duplicate_ids: list[str] = typer.Argument(..., help="Duplicate memory ids to supersede"),
    collection: Optional[str] = None,
    reason: str = "duplicate_cluster",
):
    """Mark duplicate memories as superseded by a canonical keeper."""
    b = _get_brain()
    print(json.dumps(b.supersede_duplicates(keep_id, duplicate_ids, collection=collection, reason=reason), indent=2))


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
def seed(force: bool = False):
    """Seed brain with initial memories for fresh installs."""
    from clarvis.brain.seed import seed_initial_memories

    result = seed_initial_memories(force=force)
    if result["status"] == "already_seeded":
        print("Brain already seeded — use --force to re-seed.")
        return
    print(f"Seeded {result['seeded']}/{result['total']} memories "
          f"({result['skipped']} skipped)")
    if result.get("errors"):
        for err in result["errors"]:
            print(f"  WARNING: {err}")


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


@app.command("backfill-epochs")
def backfill_epochs(dry_run: bool = False):
    """Backfill created_epoch for memories with created_at but missing/zero epoch."""
    b = _get_brain()
    result = b.backfill_epochs(dry_run=dry_run)
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"Epoch backfill ({mode}):")
    for col, info in result.items():
        if col == "total_fixed":
            continue
        if isinstance(info, dict) and info.get("fixable", 0) > 0:
            fixed = info.get("fixed", "-")
            print(f"  {col}: {info['fixable']} fixable, {fixed} fixed")
    print(f"  Total fixed: {result.get('total_fixed', 0)}")


@app.command()
def recent(days: int = 7):
    """Show recent memories (default: last 7 days)."""
    b = _get_brain()
    results = b.recall_recent(days=days)
    print(f"Memories from last {days} days:")
    for r in results:
        print(f"  [{r['collection']}] {r['document'][:60]}...")


@app.command()
def goals(
    top_n: int = typer.Option(10, "--top", "-n", help="Max goals to show."),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),
):
    """Show active goals — clean, deduped, sorted by progress."""
    b = _get_brain()
    summary = b.get_goals_summary(top_n=top_n)
    if as_json:
        print(json.dumps(summary, indent=2))
        return
    if not summary:
        print("No active goals found.")
        return
    print(f"{'Goal':<40} {'Progress':>8}  {'Importance':>10}  Updated")
    print("-" * 85)
    for g in summary:
        updated = g["updated"][:10] if g["updated"] else "—"
        print(f"{g['name'][:40]:<40} {g['progress']:>7}%  {g['importance']:>10.3f}  {updated}")


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


@app.command()
def intralink(
    max_distance: float = 1.2,
    max_links: int = 5,
):
    """Build intra-collection edges between similar memories."""
    b = _get_brain()
    result = b.bulk_intra_link(
        max_distance=max_distance,
        max_links_per_memory=max_links,
        verbose=True,
    )
    print("\nIntra-linking complete:")
    print(f"  New edges: {result['new_edges']}")
    print(f"  Collections processed: {result['collections_processed']}")
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


@app.command("graph-verify")
def graph_verify(
    sample_n: int = 100,
):
    """Verify SQLite graph store integrity."""
    b = _get_brain()
    result = b.verify_graph_parity(sample_n=sample_n)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        raise typer.Exit(1)

    print("=== Graph Integrity Verification ===\n")
    print(f"Nodes:  {result['sqlite_nodes']}")
    print(f"Edges:  {result['sqlite_edges']}")

    edge_types = result.get('sqlite_edge_types', {})
    if edge_types:
        print(f"\nEdge type distribution:")
        for t in sorted(edge_types):
            print(f"  {t}: {edge_types[t]}")

    status = "PASS" if result['parity_ok'] else "FAIL"
    print(f"\nIntegrity: {status}")

    if not result['parity_ok']:
        raise typer.Exit(1)
