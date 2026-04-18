#!/usr/bin/env python3
"""Audit trace retention sweeper — prunes trace directories older than 45 days.

Runs daily at 05:05 CET. Idempotent, fail-open (never raises).
Logs to monitoring/audit_retention.log.

CLI:
    python3 scripts/audit/audit_retention_sweeper.py          # prune
    python3 scripts/audit/audit_retention_sweeper.py --dry-run # preview
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
TRACES_DIR = WORKSPACE / "data" / "audit" / "traces"
LOGFILE = WORKSPACE / "monitoring" / "audit_retention.log"
RETENTION_DAYS = 45


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        LOGFILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOGFILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass  # fail-open


def run(dry_run: bool = False) -> None:
    if not TRACES_DIR.is_dir():
        _log(f"SKIP: traces dir does not exist: {TRACES_DIR}")
        return

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=RETENTION_DAYS)
    pruned = 0
    errors = 0

    for entry in sorted(TRACES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        # Expect directory names like 2026-04-16
        try:
            dir_date = datetime.strptime(entry.name, "%Y-%m-%d").date()
        except ValueError:
            continue  # skip non-date directories

        if dir_date >= cutoff:
            continue

        if dry_run:
            _log(f"DRY-RUN: would prune {entry.name} (age {(datetime.now(timezone.utc).date() - dir_date).days}d)")
            pruned += 1
        else:
            try:
                shutil.rmtree(entry)
                _log(f"PRUNED: {entry.name} (age {(datetime.now(timezone.utc).date() - dir_date).days}d)")
                pruned += 1
            except Exception as e:
                _log(f"ERROR: failed to prune {entry.name}: {e}")
                errors += 1

    mode = "DRY-RUN" if dry_run else "COMPLETE"
    _log(f"{mode}: pruned={pruned}, errors={errors}, cutoff={cutoff}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit trace retention sweeper")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    args = parser.parse_args()

    try:
        run(dry_run=args.dry_run)
    except Exception as e:
        # Fail-open: log but never crash the cron
        _log(f"FATAL (fail-open): {e}")
        sys.exit(0)  # exit 0 even on error — fail-open


if __name__ == "__main__":
    main()
