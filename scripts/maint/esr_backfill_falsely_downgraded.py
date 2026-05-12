#!/usr/bin/env python3
"""ESR backfill — flip falsely-downgraded `action.unverified` episodes to success.

One-shot maintenance script for `[ESR_BACKFILL_FALSELY_DOWNGRADED]`.

Reads the ESR triage report (`data/audit/esr_unverified_triage_YYYY-MM-DD.json`)
produced by `scripts/audit/esr_unverified_triage.py`, then for every episode the
triage classified as `falsely-downgraded` (and optionally `infra-failure`):

  1. Re-asserts the bucket signature by re-running the live triage predicate
     (`classify()` from the audit script) against the current episode record.
     This is defense-in-depth: if the underlying episode mutated between
     triage and backfill, we refuse to flip it.
  2. Flips `outcome=success`, clears `failure_type`, and appends a
     `backfill_provenance` field with the triage report URI, timestamp, reason,
     and the bucket that produced the flip.

Idempotent: episodes that already carry `backfill_provenance` are skipped on
re-run, so this script can be re-invoked safely.

Outputs:
  - Backup of original episodes at `data/episodes_backfill_<date>.json.bak`
    written BEFORE any mutation.
  - In-place rewrite of `data/episodes.json`.
  - Refresh of `data/performance_metrics.json` via the existing benchmark
    rebuild path (`scripts/metrics/performance_benchmark.py refresh`).

Acceptance (per task spec):
  - Dry-run prints exactly 56 falsely-downgraded episodes targeted.
  - Live-run flips 56 falsely + 1 infra-failure (the §2 "falsely + infra" row).
  - Post-run ESR ≥ 0.92 in `data/performance_metrics.json`.

Usage:
    python3 scripts/maint/esr_backfill_falsely_downgraded.py --dry-run
    python3 scripts/maint/esr_backfill_falsely_downgraded.py --apply
    python3 scripts/maint/esr_backfill_falsely_downgraded.py --apply \
        --triage data/audit/esr_unverified_triage_2026-05-12.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
EPISODES_FILE = WORKSPACE / "data" / "episodes.json"
AUDIT_DIR = WORKSPACE / "data" / "audit"
DOCS_DIR = WORKSPACE / "docs" / "internal" / "audits"
METRICS_FILE = WORKSPACE / "data" / "performance_metrics.json"
TRIAGE_SCRIPT = WORKSPACE / "scripts" / "audit" / "esr_unverified_triage.py"

DEFAULT_TRIAGE_DATE = "2026-05-12"
FLIP_BUCKETS = ("falsely-downgraded", "infra-failure")


def _load_classify():
    """Import `classify()` from the audit script without sys.path mutation."""
    spec = importlib.util.spec_from_file_location("esr_unverified_triage", TRIAGE_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load triage classifier at {TRIAGE_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.classify


def load_triage(triage_path: Path) -> dict:
    if not triage_path.exists():
        raise FileNotFoundError(f"Triage report not found: {triage_path}")
    return json.loads(triage_path.read_text())


def load_episodes(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Episodes file not found: {path}")
    return json.loads(path.read_text())


def is_falsely_downgraded(ep: dict, classify) -> tuple[bool, str]:
    """Predicate the unit test pins: returns (matches, reason).

    Matches iff the live triage classifier puts this episode in the
    `falsely-downgraded` bucket. Wraps `classify()` so callers can use a
    single boolean predicate instead of unpacking the (bucket, reason) tuple.
    """
    bucket, reason = classify(ep)
    return bucket == "falsely-downgraded", reason


def is_infra_failure(ep: dict, classify) -> tuple[bool, str]:
    bucket, reason = classify(ep)
    return bucket == "infra-failure", reason


def make_provenance(reason: str, bucket: str, triage_uri: str) -> dict:
    return {
        "source": "scripts/maint/esr_backfill_falsely_downgraded.py",
        "triage_report": triage_uri,
        "bucket": bucket,
        "reason": reason,
        "flipped_at": datetime.now(timezone.utc).isoformat(),
        "previous_outcome": "partial_success",
    }


def atomic_write_json(path: Path, data) -> None:
    """Atomic JSON write (tempfile + rename) matching EpisodicMemory._save."""
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def rebuild_metrics(workspace: Path) -> tuple[bool, str]:
    """Refresh `data/performance_metrics.json` via the canonical benchmark path."""
    bench_script = workspace / "scripts" / "metrics" / "performance_benchmark.py"
    if not bench_script.exists():
        return False, f"benchmark script missing: {bench_script}"
    try:
        proc = subprocess.run(
            [sys.executable, str(bench_script), "refresh"],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "CLARVIS_WORKSPACE": str(workspace)},
            cwd=str(workspace),
        )
        ok = proc.returncode == 0
        msg = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return ok, msg.strip()
    except subprocess.TimeoutExpired:
        return False, "performance_benchmark refresh timed out"
    except Exception as e:
        return False, f"performance_benchmark refresh raised: {e!r}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--triage",
        type=Path,
        default=AUDIT_DIR / f"esr_unverified_triage_{DEFAULT_TRIAGE_DATE}.json",
        help="path to the triage report JSON (default: 2026-05-12 report)",
    )
    ap.add_argument(
        "--episodes",
        type=Path,
        default=EPISODES_FILE,
        help=f"path to episodes.json (default: {EPISODES_FILE})",
    )
    ap.add_argument(
        "--backup-suffix",
        default=DEFAULT_TRIAGE_DATE,
        help="suffix for the backup file: data/episodes_backfill_<suffix>.json.bak",
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report targets, do not write")
    mode.add_argument("--apply", action="store_true", help="execute the backfill")
    ap.add_argument(
        "--no-rebuild",
        action="store_true",
        help="skip the performance_metrics.json refresh step",
    )
    ap.add_argument(
        "--falsely-only",
        action="store_true",
        help="flip only the falsely-downgraded bucket (skip the 1 infra-failure)",
    )
    args = ap.parse_args()

    if not args.dry_run and not args.apply:
        # Default to dry-run for safety.
        args.dry_run = True

    classify = _load_classify()
    triage = load_triage(args.triage)
    episodes = load_episodes(args.episodes)

    triage_uri = str(args.triage.relative_to(WORKSPACE)) if args.triage.is_absolute() else str(args.triage)
    by_id = {ep.get("id"): ep for ep in episodes}

    classifications = triage.get("classifications", [])
    targeted_falsely = []
    targeted_infra = []
    rejected = []
    already_done = []
    missing = []

    flip_buckets = ("falsely-downgraded",) if args.falsely_only else FLIP_BUCKETS

    for rec in classifications:
        if rec.get("bucket") not in flip_buckets:
            continue
        ep_id = rec.get("id")
        ep = by_id.get(ep_id)
        if ep is None:
            missing.append(ep_id)
            continue
        if ep.get("backfill_provenance"):
            already_done.append(ep_id)
            continue
        # Defense-in-depth: re-run the live predicate. We will not flip an
        # episode whose current shape no longer matches the triage bucket.
        bucket, reason = classify(ep)
        if bucket != rec.get("bucket"):
            rejected.append((ep_id, rec.get("bucket"), bucket))
            continue
        target = {"id": ep_id, "ep": ep, "bucket": bucket, "reason": reason}
        if bucket == "falsely-downgraded":
            targeted_falsely.append(target)
        elif bucket == "infra-failure":
            targeted_infra.append(target)

    total_targeted = len(targeted_falsely) + len(targeted_infra)

    print(f"Triage report:      {args.triage}")
    print(f"Episodes file:      {args.episodes}")
    print(f"Mode:               {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print(f"Falsely-downgraded targeted: {len(targeted_falsely)}")
    print(f"Infra-failure targeted:      {len(targeted_infra)}")
    print(f"Already backfilled:          {len(already_done)}")
    print(f"Rejected (bucket mismatch):  {len(rejected)}")
    print(f"Missing from episodes.json:  {len(missing)}")
    print(f"Total to flip this run:      {total_targeted}")

    if rejected:
        print("\nREJECTED episodes (live predicate disagrees with triage):")
        for ep_id, expected, actual in rejected[:10]:
            print(f"  {ep_id}: triage={expected!r} live={actual!r}")
        if len(rejected) > 10:
            print(f"  ... ({len(rejected) - 10} more)")

    if missing:
        print("\nMISSING episodes (in triage but not in episodes.json):")
        for ep_id in missing[:10]:
            print(f"  {ep_id}")
        if len(missing) > 10:
            print(f"  ... ({len(missing) - 10} more)")

    if args.dry_run:
        print("\nDry-run: no files written.")
        # Print the first few targets so an operator can spot-check.
        if targeted_falsely:
            print("\nSample falsely-downgraded targets:")
            for t in targeted_falsely[:3]:
                print(f"  {t['id']}: {t['reason']}")
        if targeted_infra:
            print("\nSample infra-failure targets:")
            for t in targeted_infra[:3]:
                print(f"  {t['id']}: {t['reason']}")
        return 0

    if total_targeted == 0:
        print("\nNothing to flip — exiting cleanly (idempotent no-op).")
        return 0

    # Backup BEFORE mutation.
    backup_path = args.episodes.parent / f"episodes_backfill_{args.backup_suffix}.json.bak"
    shutil.copy2(args.episodes, backup_path)
    print(f"\nBackup written: {backup_path}")

    # Apply flips.
    flipped = []
    for target in targeted_falsely + targeted_infra:
        ep = target["ep"]
        ep["outcome"] = "success"
        if ep.get("failure_type"):
            ep["failure_type"] = None
        ep["backfill_provenance"] = make_provenance(
            reason=target["reason"],
            bucket=target["bucket"],
            triage_uri=triage_uri,
        )
        flipped.append(target["id"])

    atomic_write_json(args.episodes, episodes)
    print(f"Wrote {len(flipped)} flipped episodes to {args.episodes}")

    if args.no_rebuild:
        print("Skipped metrics rebuild (--no-rebuild).")
    else:
        print("\nRefreshing performance_metrics.json via benchmark refresh ...")
        ok, msg = rebuild_metrics(WORKSPACE)
        for line in msg.splitlines():
            print(f"  bench: {line}")
        if not ok:
            print("WARN: benchmark refresh failed — re-run manually.", file=sys.stderr)

        # Surface the new ESR for the acceptance check.
        try:
            metrics = json.loads(METRICS_FILE.read_text())
            new_esr = metrics.get("metrics", {}).get("episode_success_rate")
            print(f"\nPost-run ESR: {new_esr}")
            if isinstance(new_esr, (int, float)) and new_esr >= 0.92:
                print("ACCEPTANCE PASS: ESR ≥ 0.92")
            else:
                print("ACCEPTANCE WARN: ESR did not reach 0.92 — investigate.")
        except Exception as e:
            print(f"WARN: could not read post-run ESR: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
