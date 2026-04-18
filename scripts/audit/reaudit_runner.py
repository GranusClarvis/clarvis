#!/usr/bin/env python3
"""Phase 15 — Longitudinal Re-Audit Runner.

Reads data/audit/longitudinal_schedule.json and executes the measurements
for a given cadence (weekly / monthly / quarterly).  Compares results
against thresholds, emits structured JSON output, and prints a human-
readable summary.

CLI:
    python3 scripts/audit/reaudit_runner.py weekly
    python3 scripts/audit/reaudit_runner.py monthly
    python3 scripts/audit/reaudit_runner.py quarterly
    python3 scripts/audit/reaudit_runner.py weekly --dry-run   # show what would run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEDULE_PATH = ROOT / "data" / "audit" / "longitudinal_schedule.json"
RESULTS_DIR = ROOT / "data" / "audit"

def _count_jsonl_lines(path: Path) -> int:
    """Count lines in a JSONL file, return 0 if missing."""
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


STATUS_PASS = "PASS"
STATUS_DRIFT = "DRIFT"
STATUS_REGRESSION = "REGRESSION"
STATUS_ERROR = "ERROR"


def load_schedule() -> dict:
    with open(SCHEDULE_PATH) as f:
        return json.load(f)


def measurements_for_cadence(schedule: dict, cadence: str) -> list[dict]:
    """Return measurements matching the requested cadence."""
    ids_for_cadence = schedule.get("cadence_summary", {}).get(cadence, [])
    if isinstance(ids_for_cadence, str):
        # "annually" is a string description, not a list
        return []
    by_id = {m["id"]: m for m in schedule.get("measurements", [])}
    return [by_id[mid] for mid in ids_for_cadence if mid in by_id]


def run_measurement(m: dict, dry_run: bool = False) -> dict:
    """Execute a single measurement and return a result dict."""
    result = {
        "id": m["id"],
        "phase": m["phase"],
        "metric": m["metric"],
        "pass_threshold": m["pass_threshold"],
        "fail_threshold": m["fail_threshold"],
    }

    cmd = m.get("command")
    if not cmd:
        result["status"] = STATUS_ERROR
        result["output"] = "No command defined"
        result["action"] = "Define measurement command"
        return result

    if dry_run:
        result["status"] = "DRY_RUN"
        result["output"] = f"Would run: {cmd}"
        result["action"] = None
        return result

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
        )
        output = (proc.stdout.strip() + "\n" + proc.stderr.strip()).strip()
        result["output"] = output[:2000]  # cap output size
        result["exit_code"] = proc.returncode

        # Classify result
        if proc.returncode != 0:
            result["status"] = STATUS_REGRESSION
            result["action"] = f"Command failed (exit {proc.returncode}). Investigate."
        else:
            result["status"] = STATUS_PASS
            result["action"] = None

            # Per-metric numeric checks for metrics that output a count
            mid = m["id"]
            if mid == "P10_LOCK_HEALTH":
                # Output is a number: 0 = good, > 0 = stale locks
                try:
                    count = int(output.strip().split("\n")[0])
                    if count > 0:
                        result["status"] = STATUS_REGRESSION
                        result["action"] = f"{count} stale lock(s) found (> 2h old). Investigate."
                except ValueError:
                    pass
            elif mid == "P6_PROJECT_LANE_SLOT_SHARE":
                # Output from grep -c: 0 = no SWO heartbeats
                try:
                    count = int(output.strip().split("\n")[0])
                    total_lines = _count_jsonl_lines(
                        ROOT / "data" / "audit" / "heartbeat_outcomes.jsonl"
                    )
                    if total_lines > 0 and count / total_lines < 0.25:
                        result["status"] = STATUS_DRIFT
                        result["action"] = (
                            f"Project slot share {count}/{total_lines} "
                            f"({count/total_lines:.0%}) < 25% target."
                        )
                except (ValueError, ZeroDivisionError):
                    pass

            # General heuristic: check for obvious failure signals in output
            if result["status"] == STATUS_PASS:
                lower_out = output.lower()
                if any(w in lower_out for w in ["error", "fail", "critical", "unavailable"]):
                    if "0 findings" not in lower_out and "pass" not in lower_out:
                        result["status"] = STATUS_DRIFT
                        result["action"] = "Output contains warning signals. Review manually."

    except subprocess.TimeoutExpired:
        result["status"] = STATUS_ERROR
        result["output"] = "Command timed out (120s)"
        result["action"] = "Investigate timeout"
    except Exception as e:
        result["status"] = STATUS_ERROR
        result["output"] = str(e)[:500]
        result["action"] = "Fix measurement command"

    return result


def print_summary(results: list[dict], cadence: str) -> None:
    """Print human-readable summary."""
    counts = {STATUS_PASS: 0, STATUS_DRIFT: 0, STATUS_REGRESSION: 0, STATUS_ERROR: 0}
    for r in results:
        s = r.get("status", STATUS_ERROR)
        if s in counts:
            counts[s] += 1

    print(f"\n{'='*60}")
    print(f"  Re-Audit Summary — {cadence.upper()} — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    print(f"{'='*60}")
    print(f"  PASS: {counts[STATUS_PASS]}  |  DRIFT: {counts[STATUS_DRIFT]}  |  REGRESSION: {counts[STATUS_REGRESSION]}  |  ERROR: {counts[STATUS_ERROR]}")
    print(f"{'='*60}\n")

    for r in results:
        status = r.get("status", "?")
        marker = {"PASS": "+", "DRIFT": "~", "REGRESSION": "!", "ERROR": "?", "DRY_RUN": "-"}.get(status, "?")
        print(f"  [{marker}] {r['id']}")
        print(f"      Metric: {r['metric']}")
        if r.get("output"):
            # Show first line of output only
            first_line = r["output"].split("\n")[0][:100]
            print(f"      Output: {first_line}")
        if r.get("action"):
            print(f"      ACTION: {r['action']}")
        print()


def save_results(results: list[dict], cadence: str) -> Path:
    """Save results to a dated JSON file."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = RESULTS_DIR / f"reaudit_results_{cadence}_{date_str}.json"

    payload = {
        "cadence": cadence,
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "measurement_count": len(results),
        "summary": {
            "pass": sum(1 for r in results if r.get("status") == STATUS_PASS),
            "drift": sum(1 for r in results if r.get("status") == STATUS_DRIFT),
            "regression": sum(1 for r in results if r.get("status") == STATUS_REGRESSION),
            "error": sum(1 for r in results if r.get("status") == STATUS_ERROR),
        },
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    return out_path


def load_result_files(cadence: str, last_n: int = 10) -> list[dict]:
    """Load the most recent N result files for a given cadence."""
    pattern = f"reaudit_results_{cadence}_*.json"
    files = sorted(RESULTS_DIR.glob(pattern))
    results = []
    for f in files[-last_n:]:
        try:
            with open(f) as fh:
                results.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            continue
    return results


def run_trend(cadence: str, last_n: int = 10) -> None:
    """Compare last N results and detect cross-metric regression patterns."""
    snapshots = load_result_files(cadence, last_n)

    if len(snapshots) < 2:
        print(f"Need at least 2 result files for trend analysis, found {len(snapshots)}.")
        print("Trend analysis will be available after more re-audit runs accumulate.")
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"  Trend Analysis — {cadence.upper()} — last {len(snapshots)} runs")
    print(f"{'='*60}\n")

    # Track per-measurement status history
    measurement_history: dict[str, list[tuple[str, str]]] = {}  # id -> [(date, status)]
    for snap in snapshots:
        date = snap.get("date", "?")
        for r in snap.get("results", []):
            mid = r.get("id", "?")
            status = r.get("status", "?")
            measurement_history.setdefault(mid, []).append((date, status))

    # Detect patterns
    regressions = []
    improving = []
    stable_pass = []
    chronic_drift = []

    for mid, history in sorted(measurement_history.items()):
        statuses = [s for _, s in history]
        recent = statuses[-3:] if len(statuses) >= 3 else statuses

        # Chronic drift: DRIFT or REGRESSION in all recent entries
        if all(s in (STATUS_DRIFT, STATUS_REGRESSION, STATUS_ERROR) for s in recent) and len(recent) >= 2:
            chronic_drift.append((mid, history))
        # Regression trend: last entry worse than first
        elif len(statuses) >= 2 and statuses[-1] in (STATUS_REGRESSION, STATUS_ERROR) and statuses[0] == STATUS_PASS:
            regressions.append((mid, history))
        # Improving: moved from non-PASS to PASS
        elif len(statuses) >= 2 and statuses[-1] == STATUS_PASS and statuses[0] != STATUS_PASS:
            improving.append((mid, history))
        # Stable pass
        elif all(s == STATUS_PASS for s in recent):
            stable_pass.append((mid, history))

    # Print chronic drift (most important)
    if chronic_drift:
        print("  CHRONIC DRIFT (non-PASS in all recent runs):")
        for mid, history in chronic_drift:
            timeline = " → ".join(f"{s}({d})" for d, s in history[-5:])
            print(f"    ! {mid}: {timeline}")
        print()

    # Print regressions
    if regressions:
        print("  REGRESSIONS (was PASS, now failing):")
        for mid, history in regressions:
            timeline = " → ".join(f"{s}({d})" for d, s in history[-5:])
            print(f"    ! {mid}: {timeline}")
        print()

    # Print improving
    if improving:
        print("  IMPROVING (recovered to PASS):")
        for mid, history in improving:
            timeline = " → ".join(f"{s}({d})" for d, s in history[-5:])
            print(f"    + {mid}: {timeline}")
        print()

    # Print stable
    if stable_pass:
        print(f"  STABLE PASS: {len(stable_pass)} measurements consistently passing")
        print()

    # Summary counts across snapshots
    print("  Run-over-run summary counts:")
    print(f"  {'Date':<12} {'PASS':>5} {'DRIFT':>6} {'REGR':>5} {'ERR':>5}")
    for snap in snapshots:
        s = snap.get("summary", {})
        print(f"  {snap.get('date', '?'):<12} {s.get('pass', 0):>5} {s.get('drift', 0):>6} {s.get('regression', 0):>5} {s.get('error', 0):>5}")
    print()

    # Overall verdict
    if chronic_drift:
        print(f"  VERDICT: {len(chronic_drift)} chronic issue(s) need attention")
    elif regressions:
        print(f"  VERDICT: {len(regressions)} regression(s) detected")
    else:
        print("  VERDICT: No cross-metric regression patterns detected")


def main():
    parser = argparse.ArgumentParser(
        description="Longitudinal Re-Audit Runner (Phase 15)"
    )
    parser.add_argument(
        "cadence",
        choices=["weekly", "monthly", "quarterly", "trend"],
        help="Which cadence tier to run, or 'trend' for trend analysis",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing",
    )
    parser.add_argument(
        "--last-n",
        type=int,
        default=10,
        help="Number of recent results to compare (trend mode only)",
    )
    parser.add_argument(
        "--trend-cadence",
        choices=["weekly", "monthly", "quarterly"],
        default="weekly",
        help="Cadence to analyze in trend mode (default: weekly)",
    )
    args = parser.parse_args()

    if args.cadence == "trend":
        run_trend(args.trend_cadence, args.last_n)
        return

    if not SCHEDULE_PATH.exists():
        print(f"ERROR: Schedule not found at {SCHEDULE_PATH}", file=sys.stderr)
        sys.exit(1)

    schedule = load_schedule()
    measurements = measurements_for_cadence(schedule, args.cadence)

    if not measurements:
        print(f"No measurements defined for cadence '{args.cadence}'")
        sys.exit(0)

    print(f"Running {len(measurements)} {args.cadence} re-audit checks...")

    results = []
    for m in measurements:
        r = run_measurement(m, dry_run=args.dry_run)
        results.append(r)

    print_summary(results, args.cadence)

    if not args.dry_run:
        out_path = save_results(results, args.cadence)
        print(f"Results saved to: {out_path}")

    # Exit with non-zero if any regressions
    regressions = sum(1 for r in results if r.get("status") == STATUS_REGRESSION)
    if regressions > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
