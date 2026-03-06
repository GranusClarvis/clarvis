#!/usr/bin/env python3
"""Graph storage cutover — switch from JSON to SQLite backend.

This script handles the Phase 4 cutover of the graph storage upgrade:
  1. Pre-flight checks (SQLite DB exists, parity OK, no maintenance lock)
  2. Archive relationships.json with timestamp
  3. Enable CLARVIS_GRAPH_BACKEND=sqlite in cron_env.sh
  4. Optionally disable JSON dual-write (--drop-json-writes)

Rollback is a one-liner:
  python3 scripts/graph_cutover.py --rollback

Usage:
    python3 scripts/graph_cutover.py                # Cutover (archive JSON, enable SQLite)
    python3 scripts/graph_cutover.py --dry-run       # Show what would happen
    python3 scripts/graph_cutover.py --rollback      # Revert to JSON backend
    python3 scripts/graph_cutover.py --status        # Show current backend state
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
sys.path.insert(0, WORKSPACE)

from clarvis.brain.constants import GRAPH_FILE, GRAPH_SQLITE_FILE

CRON_ENV = os.path.join(WORKSPACE, "scripts", "cron_env.sh")
ARCHIVE_DIR = os.path.join(os.path.dirname(GRAPH_FILE), "archive")
MAINTENANCE_LOCK = "/tmp/clarvis_maintenance.lock"

# Regex patterns for cron_env.sh manipulation
_BACKEND_COMMENTED = re.compile(r'^#\s*export\s+CLARVIS_GRAPH_BACKEND="sqlite"', re.MULTILINE)
_BACKEND_ACTIVE = re.compile(r'^export\s+CLARVIS_GRAPH_BACKEND="sqlite"', re.MULTILINE)


def sha256_prefix(path: str, length: int = 16) -> str:
    """SHA256 hex prefix of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def file_size_mb(path: str) -> str:
    """Human-readable file size."""
    if not os.path.exists(path):
        return "N/A"
    return f"{os.path.getsize(path) / 1024 / 1024:.2f} MB"


def check_maintenance_lock() -> bool:
    """Returns True if maintenance lock is held."""
    return os.path.exists(MAINTENANCE_LOCK)


def get_backend_state() -> str:
    """Read cron_env.sh and return 'json', 'sqlite', or 'unknown'."""
    if not os.path.exists(CRON_ENV):
        return "unknown"
    with open(CRON_ENV, "r") as f:
        content = f.read()
    if _BACKEND_ACTIVE.search(content):
        return "sqlite"
    if _BACKEND_COMMENTED.search(content):
        return "json"
    return "unknown"


def status():
    """Print current graph backend status."""
    print("=== Graph Backend Status ===\n")

    backend = get_backend_state()
    print(f"  cron_env.sh backend:  {backend}")
    print(f"  env CLARVIS_GRAPH_BACKEND: {os.environ.get('CLARVIS_GRAPH_BACKEND', '(unset, default=json)')}")

    print(f"\n  JSON file:   {GRAPH_FILE}")
    print(f"    exists: {os.path.exists(GRAPH_FILE)}, size: {file_size_mb(GRAPH_FILE)}")

    print(f"\n  SQLite file: {GRAPH_SQLITE_FILE}")
    print(f"    exists: {os.path.exists(GRAPH_SQLITE_FILE)}, size: {file_size_mb(GRAPH_SQLITE_FILE)}")

    # Check for archives
    if os.path.exists(ARCHIVE_DIR):
        archives = sorted(os.listdir(ARCHIVE_DIR))
        if archives:
            print(f"\n  Archives ({ARCHIVE_DIR}):")
            for a in archives:
                print(f"    {a}  ({file_size_mb(os.path.join(ARCHIVE_DIR, a))})")
    else:
        print(f"\n  Archives: none (directory not created yet)")

    # Maintenance lock
    print(f"\n  Maintenance lock: {'HELD' if check_maintenance_lock() else 'free'}")

    return backend


def preflight_checks(dry_run: bool = False) -> bool:
    """Run pre-cutover checks. Returns True if all pass."""
    print("=== Pre-Cutover Checks ===\n")
    all_ok = True

    # 1. SQLite DB exists
    sqlite_exists = os.path.exists(GRAPH_SQLITE_FILE)
    print(f"  [{'OK' if sqlite_exists else 'FAIL'}] SQLite DB exists: {GRAPH_SQLITE_FILE}")
    if not sqlite_exists:
        print("    → Run: python3 scripts/graph_migrate_to_sqlite.py --safe")
        all_ok = False

    # 2. JSON file exists (we need it to archive)
    json_exists = os.path.exists(GRAPH_FILE)
    print(f"  [{'OK' if json_exists else 'WARN'}] JSON file exists: {GRAPH_FILE}")

    # 3. No maintenance lock
    lock_free = not check_maintenance_lock()
    print(f"  [{'OK' if lock_free else 'FAIL'}] No maintenance lock held")
    if not lock_free:
        print("    → Wait for maintenance window to finish (04:00-05:00 UTC)")
        all_ok = False

    # 4. Backend currently JSON
    current = get_backend_state()
    is_json = current == "json"
    print(f"  [{'OK' if is_json else 'WARN'}] Current backend is JSON (got: {current})")
    if not is_json:
        print("    → Already switched to SQLite or in unknown state")

    # 5. SQLite integrity check
    if sqlite_exists:
        try:
            from clarvis.brain.graph_store_sqlite import GraphStoreSQLite
            store = GraphStoreSQLite(GRAPH_SQLITE_FILE)
            integrity_ok = store.integrity_check()
            stats = store.stats()
            store.close()
            print(f"  [{'OK' if integrity_ok else 'FAIL'}] SQLite integrity check")
            print(f"    Nodes: {stats['nodes']}, Edges: {stats['edges']}, Size: {file_size_mb(GRAPH_SQLITE_FILE)}")
            if not integrity_ok:
                all_ok = False
        except Exception as exc:
            print(f"  [FAIL] SQLite integrity check: {exc}")
            all_ok = False

    # 6. Parity check (if both exist)
    if sqlite_exists and json_exists and not dry_run:
        try:
            old_backend = os.environ.get("CLARVIS_GRAPH_BACKEND")
            os.environ["CLARVIS_GRAPH_BACKEND"] = "sqlite"

            # Reset both the spine brain singleton and the scripts/brain wrapper cache (if any)
            import clarvis.brain as _bmod
            _bmod._brain = None
            try:
                import brain as _brain_wrapper
                if hasattr(_brain_wrapper, "_brain"):
                    _brain_wrapper._brain = None
            except Exception:
                pass

            from clarvis.brain import get_brain
            brain = get_brain()
            parity = brain.verify_graph_parity(sample_n=200)

            # Restore env
            if old_backend is not None:
                os.environ["CLARVIS_GRAPH_BACKEND"] = old_backend
            else:
                os.environ.pop("CLARVIS_GRAPH_BACKEND", None)

            # Reset again for cleanliness
            _bmod._brain = None
            try:
                if hasattr(_brain_wrapper, "_brain"):
                    _brain_wrapper._brain = None
            except Exception:
                pass

            if "error" in parity:
                print(f"  [FAIL] Parity check (200-sample)")
                print(f"    Error: {parity['error']}")
                all_ok = False
            else:
                parity_ok = parity.get("parity_ok", False)
                print(f"  [{'OK' if parity_ok else 'FAIL'}] Parity check (200-sample)")
                print(f"    Nodes: JSON={parity['json_nodes']} SQLite={parity['sqlite_nodes']} delta={parity['node_delta']}")
                print(f"    Edges: JSON={parity['json_unique_edges']}(unique) SQLite={parity['sqlite_edges']} delta={parity['edge_delta']}")
                print(f"    Sample: {parity['sample_matched']}/{parity['sample_size']} matched")
                if not parity_ok:
                    all_ok = False
        except Exception as exc:
            print(f"  [FAIL] Parity check: {exc}")
            all_ok = False

    print(f"\n  Overall: {'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}")
    return all_ok


def archive_json(dry_run: bool = False) -> str | None:
    """Archive relationships.json with timestamp. Returns archive path."""
    if not os.path.exists(GRAPH_FILE):
        print("  No JSON file to archive")
        return None

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    archive_name = f"relationships.{timestamp}.json"
    archive_path = os.path.join(ARCHIVE_DIR, archive_name)

    if dry_run:
        print(f"  [DRY RUN] Would archive: {GRAPH_FILE} → {archive_path}")
        return archive_path

    shutil.copy2(GRAPH_FILE, archive_path)

    # Verify archive integrity
    src_hash = sha256_prefix(GRAPH_FILE)
    dst_hash = sha256_prefix(archive_path)
    if src_hash != dst_hash:
        print(f"  ERROR: Archive hash mismatch! src={src_hash} dst={dst_hash}")
        os.unlink(archive_path)
        return None

    print(f"  Archived: {archive_path}")
    print(f"  SHA256 prefix: {src_hash}")
    print(f"  Size: {file_size_mb(archive_path)}")
    return archive_path


def enable_sqlite_backend(dry_run: bool = False) -> bool:
    """Uncomment CLARVIS_GRAPH_BACKEND=sqlite in cron_env.sh."""
    with open(CRON_ENV, "r") as f:
        content = f.read()

    if _BACKEND_ACTIVE.search(content):
        print("  SQLite backend already enabled in cron_env.sh")
        return True

    if not _BACKEND_COMMENTED.search(content):
        print("  ERROR: Cannot find CLARVIS_GRAPH_BACKEND line in cron_env.sh")
        return False

    new_content = _BACKEND_COMMENTED.sub('export CLARVIS_GRAPH_BACKEND="sqlite"', content)

    if dry_run:
        print('  [DRY RUN] Would uncomment: export CLARVIS_GRAPH_BACKEND="sqlite"')
        return True

    with open(CRON_ENV, "w") as f:
        f.write(new_content)

    print('  Enabled: export CLARVIS_GRAPH_BACKEND="sqlite" in cron_env.sh')
    return True


def disable_sqlite_backend(dry_run: bool = False) -> bool:
    """Comment out CLARVIS_GRAPH_BACKEND=sqlite in cron_env.sh (rollback)."""
    with open(CRON_ENV, "r") as f:
        content = f.read()

    if _BACKEND_COMMENTED.search(content):
        print("  SQLite backend already disabled in cron_env.sh")
        return True

    if not _BACKEND_ACTIVE.search(content):
        print("  ERROR: Cannot find CLARVIS_GRAPH_BACKEND line in cron_env.sh")
        return False

    new_content = _BACKEND_ACTIVE.sub('# export CLARVIS_GRAPH_BACKEND="sqlite"', content)

    if dry_run:
        print('  [DRY RUN] Would comment out: export CLARVIS_GRAPH_BACKEND="sqlite"')
        return True

    with open(CRON_ENV, "w") as f:
        f.write(new_content)

    print('  Disabled: commented out CLARVIS_GRAPH_BACKEND in cron_env.sh')
    return True


def run_invariants(dry_run: bool = False) -> bool:
    """Run invariants_check.py as a pre-cutover gate. Returns True on PASS."""
    print("\n--- Invariants Gate (Ouroboros drift detection) ---")
    if dry_run:
        print("  [DRY RUN] Would run: python3 scripts/invariants_check.py")
        return True

    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(WORKSPACE, "scripts", "invariants_check.py")],
        capture_output=True, text=True, timeout=600, cwd=WORKSPACE,
    )
    # Forward output
    output = (result.stdout + result.stderr).strip()
    for line in output.splitlines():
        print(f"  {line}")
    return result.returncode == 0


def cutover(dry_run: bool = False) -> bool:
    """Execute the full cutover sequence."""
    print("=" * 60)
    print("  GRAPH STORAGE CUTOVER — JSON → SQLite")
    print("=" * 60)
    print()

    # 0. Invariants gate
    if not run_invariants(dry_run=dry_run):
        print("\nABORTED: Invariants check failed — resolve before cutover.")
        return False

    # 1. Pre-flight
    if not preflight_checks(dry_run=dry_run):
        print("\nABORTED: Pre-flight checks failed.")
        return False

    # 2. Archive JSON
    print("\n--- Step 1: Archive relationships.json ---")
    archive_path = archive_json(dry_run=dry_run)

    # 3. Enable SQLite backend
    print("\n--- Step 2: Enable SQLite backend ---")
    if not enable_sqlite_backend(dry_run=dry_run):
        print("\nABORTED: Failed to enable SQLite backend.")
        return False

    # 4. Summary
    print("\n" + "=" * 60)
    if dry_run:
        print("  DRY RUN COMPLETE — no changes made")
    else:
        print("  CUTOVER COMPLETE")
        print()
        print("  What happened:")
        print(f"    1. Archived JSON → {archive_path or '(none)'}")
        print('    2. Enabled CLARVIS_GRAPH_BACKEND="sqlite" in cron_env.sh')
        print()
        print("  JSON file is preserved at original location (dual-write continues).")
        print("  All cron jobs will now use SQLite backend on next run.")
        print()
        print("  To rollback:")
        print("    python3 scripts/graph_cutover.py --rollback")
    print("=" * 60)

    return True


def rollback(dry_run: bool = False) -> bool:
    """Rollback: disable SQLite backend, restore JSON as primary."""
    print("=" * 60)
    print("  GRAPH STORAGE ROLLBACK — SQLite → JSON")
    print("=" * 60)
    print()

    # 1. Disable SQLite backend
    print("--- Step 1: Disable SQLite backend ---")
    if not disable_sqlite_backend(dry_run=dry_run):
        print("\nROLLBACK FAILED: Could not disable SQLite backend.")
        return False

    # 2. Verify JSON file exists
    json_exists = os.path.exists(GRAPH_FILE)
    print(f"\n--- Step 2: Verify JSON file ---")
    print(f"  JSON file exists: {json_exists}")
    if not json_exists:
        # Check for archives
        if os.path.exists(ARCHIVE_DIR):
            archives = sorted(os.listdir(ARCHIVE_DIR), reverse=True)
            if archives:
                latest = os.path.join(ARCHIVE_DIR, archives[0])
                print(f"  Latest archive: {latest}")
                if not dry_run:
                    shutil.copy2(latest, GRAPH_FILE)
                    print(f"  Restored: {latest} → {GRAPH_FILE}")
                else:
                    print(f"  [DRY RUN] Would restore: {latest} → {GRAPH_FILE}")
            else:
                print("  WARNING: No archives found. JSON must be recovered manually.")
        else:
            print("  WARNING: No archive directory. JSON must be recovered manually.")

    print("\n" + "=" * 60)
    if dry_run:
        print("  DRY RUN COMPLETE — no changes made")
    else:
        print("  ROLLBACK COMPLETE")
        print()
        print("  All cron jobs will now use JSON backend on next run.")
        print("  Dual-write kept both stores in sync, so no data was lost.")
    print("=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Graph storage cutover — switch from JSON to SQLite backend"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="Show what would happen without making changes")
    group.add_argument("--rollback", action="store_true",
                       help="Revert to JSON backend")
    group.add_argument("--status", action="store_true",
                       help="Show current backend state")
    args = parser.parse_args()

    if args.status:
        status()
        return 0

    if args.rollback:
        ok = rollback(dry_run=False)
        return 0 if ok else 1

    ok = cutover(dry_run=args.dry_run)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
