#!/usr/bin/env python3
"""Graph edge-type distribution audit.

Produces a diagnostic report of edge-type balance, cross-collection
coverage, and integration gaps. Outputs JSON to stdout for programmatic
consumption, or a human-readable summary with --summary.

Usage:
    python3 scripts/audit/graph_edge_audit.py           # JSON report
    python3 scripts/audit/graph_edge_audit.py --summary  # Human-readable
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_WS = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_WS))

from clarvis.brain.graph_store_sqlite import GraphStoreSQLite

DB_PATH = _WS / "data" / "clarvisdb" / "graph.db"


def audit(db_path: str | None = None) -> dict:
    """Run full edge-type distribution audit. Returns structured report."""
    store = GraphStoreSQLite(str(db_path or DB_PATH))
    conn = store._conn

    # 1. Edge type distribution
    cur = conn.execute(
        "SELECT type, COUNT(*) as cnt FROM edges GROUP BY type ORDER BY cnt DESC"
    )
    type_rows = cur.fetchall()
    total_edges = sum(r[1] for r in type_rows)
    edge_types = {t: {"count": c, "pct": round(100 * c / total_edges, 2) if total_edges else 0}
                  for t, c in type_rows}

    # 2. Cross-collection ratio per type
    cur2 = conn.execute("""
        SELECT type, COUNT(*) as cnt,
               SUM(CASE WHEN source_collection != target_collection
                        AND source_collection IS NOT NULL
                        AND target_collection IS NOT NULL THEN 1 ELSE 0 END) as cross_cnt
        FROM edges GROUP BY type ORDER BY cnt DESC
    """)
    for t, cnt, cc in cur2.fetchall():
        if t in edge_types:
            edge_types[t]["cross_collection_count"] = cc
            edge_types[t]["cross_collection_pct"] = round(100 * cc / cnt, 1) if cnt else 0

    # 3. Node distribution
    cur3 = conn.execute(
        "SELECT collection, COUNT(*) as cnt FROM nodes GROUP BY collection ORDER BY cnt DESC"
    )
    node_dist = {r[0]: r[1] for r in cur3.fetchall()}

    # 4. Intra-collection density per collection
    cur4 = conn.execute("""
        SELECT source_collection, COUNT(*) as cnt
        FROM edges
        WHERE source_collection = target_collection AND source_collection IS NOT NULL
        GROUP BY source_collection ORDER BY cnt DESC
    """)
    intra_per_col = {r[0]: r[1] for r in cur4.fetchall()}

    # 5. Cross-collection pair coverage
    cur5 = conn.execute("""
        SELECT source_collection, target_collection, COUNT(*) as cnt
        FROM edges
        WHERE source_collection IS NOT NULL AND target_collection IS NOT NULL
          AND source_collection != target_collection
        GROUP BY source_collection, target_collection ORDER BY cnt DESC
    """)
    pair_rows = cur5.fetchall()
    collections = sorted(node_dist.keys())
    possible_pairs = len(collections) * (len(collections) - 1)
    connected_pairs = len(set((r[0], r[1]) for r in pair_rows))

    # Identify weakest pairs (bottom 10)
    pair_counts = {f"{r[0]} -> {r[1]}": r[2] for r in pair_rows}
    weakest_pairs = sorted(pair_counts.items(), key=lambda x: x[1])[:10]

    # 6. Integration balance score (Gini coefficient of edge types)
    counts = [c for _, c in type_rows if c > 0]
    if len(counts) > 1:
        n = len(counts)
        counts_sorted = sorted(counts)
        gini = sum((2 * (i + 1) - n - 1) * c for i, c in enumerate(counts_sorted))
        gini /= n * sum(counts_sorted)
        gini = round(gini, 4)
    else:
        gini = 0.0

    # 7. Flag near-zero types (< 0.5% of total)
    near_zero = [t for t, info in edge_types.items() if info["pct"] < 0.5]

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_edges": total_edges,
        "total_nodes": sum(node_dist.values()),
        "edge_types": edge_types,
        "node_distribution": node_dist,
        "intra_edges_per_collection": intra_per_col,
        "cross_collection_coverage": {
            "connected_pairs": connected_pairs,
            "possible_pairs": possible_pairs,
            "coverage_pct": round(100 * connected_pairs / possible_pairs, 1) if possible_pairs else 0,
        },
        "weakest_cross_pairs": dict(weakest_pairs),
        "gini_coefficient": gini,
        "near_zero_types": near_zero,
        "findings": [],
    }

    # Generate findings
    if gini > 0.7:
        report["findings"].append(
            f"High Gini coefficient ({gini}) — edge types are heavily imbalanced. "
            f"Top 2 types account for {sum(c['pct'] for t, c in list(edge_types.items())[:2]):.0f}% of edges."
        )
    if near_zero:
        report["findings"].append(
            f"Near-zero edge types ({', '.join(near_zero)}) — "
            f"these pipelines may be inactive or broken."
        )
    # Check for collections with very low intra-density
    for col, cnt in node_dist.items():
        intra = intra_per_col.get(col, 0)
        if cnt >= 5:
            avg_degree = 2 * intra / cnt  # approximate bidirectional
            if avg_degree < 10:
                report["findings"].append(
                    f"{col}: low intra-density (avg_degree≈{avg_degree:.1f}, "
                    f"{intra} intra-edges for {cnt} nodes)"
                )

    return report


def print_summary(report: dict):
    """Print human-readable summary."""
    print(f"=== Graph Edge Audit ({report['timestamp'][:10]}) ===")
    print(f"Total: {report['total_edges']} edges, {report['total_nodes']} nodes")
    print(f"Gini coefficient: {report['gini_coefficient']} (0=even, 1=concentrated)")
    print()

    print("Edge type distribution:")
    for t, info in sorted(report["edge_types"].items(), key=lambda x: -x[1]["count"]):
        cross = info.get("cross_collection_pct", 0)
        print(f"  {t:25s}: {info['count']:6d} ({info['pct']:5.1f}%)  cross={cross:.0f}%")

    print()
    print(f"Cross-collection coverage: {report['cross_collection_coverage']['coverage_pct']}% "
          f"({report['cross_collection_coverage']['connected_pairs']}/{report['cross_collection_coverage']['possible_pairs']})")

    if report["near_zero_types"]:
        print(f"\nNear-zero types: {', '.join(report['near_zero_types'])}")

    if report["findings"]:
        print("\nFindings:")
        for f in report["findings"]:
            print(f"  - {f}")


if __name__ == "__main__":
    report = audit()
    if "--summary" in sys.argv:
        print_summary(report)
    else:
        print(json.dumps(report, indent=2))
