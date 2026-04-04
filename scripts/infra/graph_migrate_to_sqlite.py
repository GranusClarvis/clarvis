#!/usr/bin/env python3
"""Migrate graph from relationships.json to SQLite + WAL.

Reads the existing JSON graph, populates the SQLite database, and verifies
the migration with edge/node counts, random sampling, and integrity check.

Usage:
    python3 scripts/graph_migrate_to_sqlite.py                  # Migrate
    python3 scripts/graph_migrate_to_sqlite.py --verify-only    # Verify existing migration
    python3 scripts/graph_migrate_to_sqlite.py --dry-run        # Show what would be migrated

Environment:
    CLARVIS_WORKSPACE — workspace root (default: os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
"""

import argparse
import json
import os
import random
import sys
import time

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
import _paths  # noqa: F401 — registers all script subdirs on sys.path
sys.path.insert(0, WORKSPACE)

from clarvis.brain.constants import GRAPH_FILE, GRAPH_SQLITE_FILE
from clarvis.brain.graph_store_sqlite import GraphStoreSQLite


def load_json_graph(json_path: str) -> dict:
    """Load the JSON graph file."""
    with open(json_path, "r") as f:
        return json.load(f)


def migrate(json_path: str, sqlite_path: str, dry_run: bool = False) -> dict:
    """Migrate JSON graph to SQLite. Returns migration report."""
    print(f"Loading JSON graph from {json_path}...")
    t0 = time.time()
    data = load_json_graph(json_path)
    load_time = time.time() - t0

    nodes = data.get("nodes", {})
    edges = data.get("edges", [])
    json_node_count = len(nodes)
    json_edge_count = len(edges)
    expected_edge_count = data.get("_edge_count")

    print(f"  JSON loaded in {load_time:.2f}s: {json_node_count} nodes, {json_edge_count} edges")

    if expected_edge_count is not None and json_edge_count != expected_edge_count:
        print(f"  WARNING: _edge_count header ({expected_edge_count}) != actual ({json_edge_count})")

    if dry_run:
        print("\n[DRY RUN] Would migrate to:", sqlite_path)
        print(f"  Nodes: {json_node_count}")
        print(f"  Edges: {json_edge_count}")
        return {"dry_run": True, "json_nodes": json_node_count, "json_edges": json_edge_count}

    # Remove existing DB if present (clean migration)
    if os.path.exists(sqlite_path):
        print(f"  Removing existing SQLite DB: {sqlite_path}")
        os.unlink(sqlite_path)
        # Remove WAL and SHM files too
        for suffix in ("-wal", "-shm"):
            p = sqlite_path + suffix
            if os.path.exists(p):
                os.unlink(p)

    print(f"Creating SQLite DB at {sqlite_path}...")
    store = GraphStoreSQLite(sqlite_path)

    # Bulk insert via import_from_json
    t0 = time.time()
    result = store.import_from_json(json_path)
    migrate_time = time.time() - t0

    print(f"  Migration completed in {migrate_time:.2f}s")
    print(f"  Nodes imported: {result['nodes_imported']} / {result['nodes_in_json']}")
    print(f"  Edges imported: {result['edges_imported']} / {result['edges_in_json']}")
    if result["duplicates_skipped"] > 0:
        print(f"  Duplicates skipped: {result['duplicates_skipped']}")

    # Verify
    report = verify(store, data)
    report["migrate_time_s"] = round(migrate_time, 3)
    report["json_path"] = json_path
    report["sqlite_path"] = sqlite_path

    store.close()
    return report


def verify(store: GraphStoreSQLite, json_data: dict | None = None) -> dict:
    """Verify SQLite graph against JSON data (if provided) or just check integrity."""
    print("\n=== Verification ===")
    report = {"passed": True, "checks": []}

    sqlite_nodes = store.node_count()
    sqlite_edges = store.edge_count()
    print(f"  SQLite: {sqlite_nodes} nodes, {sqlite_edges} edges")

    # 1. Integrity check
    integrity_ok = store.integrity_check()
    report["checks"].append(("integrity_check", integrity_ok))
    print(f"  PRAGMA integrity_check: {'OK' if integrity_ok else 'FAILED'}")
    if not integrity_ok:
        report["passed"] = False

    if json_data is not None:
        json_nodes = len(json_data.get("nodes", {}))
        json_edges = len(json_data.get("edges", []))

        # 2. Node count match
        nodes_match = sqlite_nodes == json_nodes
        report["checks"].append(("node_count", nodes_match,
                                 {"json": json_nodes, "sqlite": sqlite_nodes}))
        print(f"  Node count: JSON={json_nodes}, SQLite={sqlite_nodes} {'OK' if nodes_match else 'MISMATCH'}")
        if not nodes_match:
            report["passed"] = False

        # 3. Edge count — SQLite may have fewer due to UNIQUE dedup
        edges_deduped = json_edges - sqlite_edges
        edges_ok = sqlite_edges <= json_edges
        report["checks"].append(("edge_count", edges_ok,
                                 {"json": json_edges, "sqlite": sqlite_edges,
                                  "deduped": edges_deduped}))
        print(f"  Edge count: JSON={json_edges}, SQLite={sqlite_edges} "
              f"(deduped: {edges_deduped}) {'OK' if edges_ok else 'MISMATCH'}")
        if not edges_ok:
            report["passed"] = False

        # 4. Random edge sampling
        edges = json_data.get("edges", [])
        if edges:
            sample_size = min(100, len(edges))
            sample = random.sample(edges, sample_size)
            found = 0
            missing = []

            for e in sample:
                result = store.get_edges(
                    from_id=e["from"], to_id=e["to"],
                    edge_type=e.get("type", "unknown")
                )
                if result:
                    found += 1
                else:
                    missing.append(e)

            sample_ok = found == sample_size
            report["checks"].append(("random_sample", sample_ok,
                                     {"sampled": sample_size, "found": found}))
            print(f"  Random edge sample: {found}/{sample_size} found "
                  f"{'OK' if sample_ok else 'MISSING EDGES'}")
            if not sample_ok:
                report["passed"] = False
                for m in missing[:5]:
                    print(f"    Missing: {m['from']} -> {m['to']} ({m.get('type')})")

        # 5. Edge type distribution comparison
        stats = store.stats()
        print(f"\n  Edge type distribution (SQLite):")
        for etype, count in stats["edge_types"].items():
            print(f"    {etype}: {count}")

    # DB size
    db_size = os.path.getsize(store.db_path) if os.path.exists(store.db_path) else 0
    report["db_size_bytes"] = db_size
    print(f"\n  SQLite DB size: {db_size / 1024 / 1024:.2f} MB")

    if report["passed"]:
        print("\n  ALL CHECKS PASSED")
    else:
        print("\n  SOME CHECKS FAILED — review report")

    return report


def verify_only(sqlite_path: str, json_path: str | None = None) -> dict:
    """Verify an existing SQLite migration."""
    if not os.path.exists(sqlite_path):
        print(f"ERROR: SQLite DB not found at {sqlite_path}")
        return {"passed": False, "error": "db_not_found"}

    store = GraphStoreSQLite(sqlite_path)

    json_data = None
    if json_path and os.path.exists(json_path):
        json_data = load_json_graph(json_path)
        print(f"Loaded JSON for comparison: {json_path}")

    report = verify(store, json_data)
    store.close()
    return report


def safe_migrate(json_path: str, sqlite_path: str) -> dict:
    """Safe migration: snapshot JSON first, then migrate, then verify parity.

    Steps:
      1. Copy relationships.json to relationships.pre-migration.json (atomic snapshot)
      2. Run full migration (import_from_json)
      3. Run graph-verify parity check
      4. Report results

    Returns dict with migration report + parity results.
    """
    import shutil

    if not os.path.exists(json_path):
        print(f"ERROR: JSON graph not found at {json_path}")
        return {"passed": False, "error": "json_not_found"}

    # 1. Snapshot
    snapshot_path = json_path.replace(".json", ".pre-migration.json")
    print(f"Step 1: Snapshotting {json_path} -> {snapshot_path}")
    shutil.copy2(json_path, snapshot_path)
    snap_hash = None
    import hashlib
    with open(snapshot_path, "rb") as f:
        snap_hash = hashlib.sha256(f.read()).hexdigest()[:16]
    print(f"  Snapshot SHA256 prefix: {snap_hash}")

    # Verify snapshot matches source
    with open(json_path, "rb") as f:
        src_hash = hashlib.sha256(f.read()).hexdigest()[:16]
    if snap_hash != src_hash:
        print("ERROR: Snapshot hash mismatch — JSON changed during copy")
        return {"passed": False, "error": "snapshot_mismatch"}
    print("  Snapshot verified: matches source")

    # 2. Migrate
    print(f"\nStep 2: Migrating to SQLite...")
    report = migrate(json_path, sqlite_path)

    if not report.get("passed", False):
        print("\nMigration verification FAILED — see report above")
        print(f"Snapshot preserved at: {snapshot_path}")
        return report

    # 3. Parity check via brain's verify_graph_parity
    print(f"\nStep 3: Running graph-verify parity check...")
    try:
        import os as _os
        old_backend = _os.environ.get("CLARVIS_GRAPH_BACKEND")
        _os.environ["CLARVIS_GRAPH_BACKEND"] = "sqlite"

        # Force constants module AND brain __init__ module to see new backend
        import clarvis.brain.constants as _cmod
        _cmod.GRAPH_BACKEND = "sqlite"
        import clarvis.brain as _bmod
        _bmod.GRAPH_BACKEND = "sqlite"  # Patch the imported name in brain.__init__
        _bmod._brain = None  # Force fresh singleton

        brain = _bmod.get_brain()
        parity = brain.verify_graph_parity(sample_n=200)

        # Restore
        if old_backend is not None:
            _os.environ["CLARVIS_GRAPH_BACKEND"] = old_backend
        else:
            _os.environ.pop("CLARVIS_GRAPH_BACKEND", None)
        restored = old_backend or "json"
        _cmod.GRAPH_BACKEND = restored
        _bmod.GRAPH_BACKEND = restored
        _bmod._brain = None
    except Exception as exc:
        print(f"  Parity check error: {exc}")
        parity = {"parity_ok": False, "error": str(exc)}

    report["parity"] = parity
    if parity.get("parity_ok"):
        print("  Parity: OK")
    else:
        print(f"  Parity: FAILED — {parity}")
        print(f"Snapshot preserved at: {snapshot_path}")
        report["passed"] = False
        return report

    # 4. Run invariants check (Ouroboros drift detection)
    print(f"\nStep 4: Running invariants check...")
    try:
        import subprocess
        inv_result = subprocess.run(
            [sys.executable, os.path.join(WORKSPACE, "scripts", "invariants_check.py")],
            capture_output=True, text=True, timeout=600, cwd=WORKSPACE,
        )
        inv_output = (inv_result.stdout + inv_result.stderr).strip()
        for line in inv_output.splitlines():
            print(f"  {line}")
        if inv_result.returncode != 0:
            print("\n  WARNING: Invariants check FAILED after migration.")
            print("  Migration data is intact but review failures before cutover.")
            report["invariants_passed"] = False
        else:
            report["invariants_passed"] = True
    except Exception as exc:
        print(f"  Invariants check error: {exc}")
        report["invariants_passed"] = False

    print(f"\nSafe migration COMPLETE. Snapshot at: {snapshot_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Migrate graph from JSON to SQLite")
    parser.add_argument("--json-path", default=GRAPH_FILE,
                        help=f"Path to relationships.json (default: {GRAPH_FILE})")
    parser.add_argument("--sqlite-path", default=GRAPH_SQLITE_FILE,
                        help=f"Path to graph.db (default: {GRAPH_SQLITE_FILE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be migrated without doing it")
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify existing migration without re-migrating")
    parser.add_argument("--safe", action="store_true",
                        help="Safe migration: snapshot JSON, migrate, verify parity")
    args = parser.parse_args()

    if args.verify_only:
        report = verify_only(args.sqlite_path, args.json_path)
    elif args.safe:
        report = safe_migrate(args.json_path, args.sqlite_path)
    else:
        if not os.path.exists(args.json_path):
            print(f"ERROR: JSON graph not found at {args.json_path}")
            sys.exit(1)
        report = migrate(args.json_path, args.sqlite_path, dry_run=args.dry_run)

    # Print summary
    print(f"\n{'='*40}")
    print(f"Result: {'PASS' if report.get('passed', True) else 'FAIL'}")

    return 0 if report.get("passed", True) else 1


if __name__ == "__main__":
    sys.exit(main())
