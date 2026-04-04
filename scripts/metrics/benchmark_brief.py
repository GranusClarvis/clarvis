#!/usr/bin/env python3
"""
Benchmark: Context Brief v2 Quality Impact

Tracks autonomous execution success rate across heartbeats, comparing
v1 (legacy) and v2 (tiered) context briefs.

Key metrics tracked per heartbeat:
  - success/failure/timeout outcome
  - brief_version (v1 or v2)
  - brief_tier (minimal/standard/full)
  - brief_bytes
  - executor (claude/gemini/openrouter)
  - route_tier (simple/medium/complex/reasoning)
  - duration_s
  - escalated (bool)

Aggregated reports:
  - success_rate by brief version
  - timeout_rate by brief version
  - escalation_rate by brief version
  - avg duration by brief version
  - rolling window (last N heartbeats)

Usage:
  python3 benchmark_brief.py record <preflight_json> <exit_code> <duration_s>
  python3 benchmark_brief.py report
  python3 benchmark_brief.py seed-from-log   # backfill from autonomous.log
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "benchmarks"
BENCHMARK_FILE = DATA_DIR / "brief_v2_benchmark.jsonl"
REPORT_FILE = DATA_DIR / "brief_v2_report.json"
LOG_FILE = Path(__file__).parent.parent / "memory" / "cron" / "autonomous.log"

TARGET_HEARTBEATS = 10
TARGET_SUCCESS_RATE = 0.60
BASELINE_SUCCESS_RATE = 0.50


def record(preflight_data, exit_code, duration_s):
    """Record a single heartbeat execution result."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Detect brief version from preflight data
    context_brief = preflight_data.get("context_brief", "")
    brief_bytes = len(context_brief.encode('utf-8')) if context_brief else 0

    # v2 tiered briefs have structured sections; v1 is flat text
    # Check for v2 markers: presence of tiered sections
    has_v2_markers = any(marker in context_brief for marker in [
        "SUCCESS CRITERIA:", "AVOID THESE FAILURE PATTERNS:",
        "WORKING MEMORY:", "APPROACH:", "EPISODIC HINTS:",
        "RELATED TASKS:", "METRICS:"
    ])

    brief_version = "v2" if has_v2_markers else "v1"

    # Determine brief tier from the preflight log
    # The preflight logs "Tiered brief (full)" for v2 or "Context brief" for v1
    route_executor = preflight_data.get("route_executor", "claude")
    route_tier = preflight_data.get("route_tier", "complex")

    if brief_version == "v2":
        # Infer tier from executor mapping (same logic as heartbeat_preflight.py)
        if route_executor in ("openrouter", "gemini"):
            brief_tier = "minimal"
        elif route_tier in ("complex", "reasoning"):
            brief_tier = "full"
        else:
            brief_tier = "standard"
    else:
        brief_tier = "legacy"

    # Determine outcome
    if exit_code == 0:
        outcome = "success"
    elif exit_code == 124:
        outcome = "timeout"
    else:
        outcome = "failure"

    # Check for escalation (OpenRouter/Gemini → Claude)
    escalated = preflight_data.get("escalated", False)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": preflight_data.get("task", "unknown")[:120],
        "brief_version": brief_version,
        "brief_tier": brief_tier,
        "brief_bytes": brief_bytes,
        "executor": route_executor,
        "route_tier": route_tier,
        "route_score": preflight_data.get("route_score", 0.5),
        "exit_code": exit_code,
        "outcome": outcome,
        "duration_s": duration_s,
        "escalated": escalated,
    }

    with open(BENCHMARK_FILE, 'a') as f:
        f.write(json.dumps(entry) + "\n")

    # Auto-generate report after each record
    _generate_report()

    return entry


def seed_from_log():
    """Backfill benchmark data from autonomous.log.

    Parses EXECUTION lines and the preceding PREFLIGHT brief info to
    reconstruct historical heartbeat records.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not LOG_FILE.exists():
        print("No autonomous.log found", file=sys.stderr)
        return

    lines = LOG_FILE.read_text().splitlines()

    # Parse execution entries paired with their preceding brief info
    entries = []
    current_brief_version = "v1"
    current_brief_bytes = 0
    current_brief_tier = "legacy"
    current_task = ""
    current_route_tier = "complex"
    current_route_score = 0.5

    for line in lines:
        # Track brief version from PREFLIGHT lines
        brief_match = re.search(r'PREFLIGHT: Context brief: (\d+) bytes', line)
        if brief_match:
            current_brief_version = "v1"
            current_brief_bytes = int(brief_match.group(1))
            current_brief_tier = "legacy"
            continue

        tiered_match = re.search(r'PREFLIGHT: Tiered brief \((\w+)\): (\d+) bytes', line)
        if tiered_match:
            current_brief_version = "v2"
            current_brief_tier = tiered_match.group(1)
            current_brief_bytes = int(tiered_match.group(2))
            continue

        # Track route info
        route_match = re.search(r'PREFLIGHT: Route: tier=(\w+) executor=(\w+) score=([0-9.]+)', line)
        if route_match:
            current_route_tier = route_match.group(1)
            current_route_score = float(route_match.group(3))
            continue

        # Track task from EXECUTING line
        exec_start = re.search(r'EXECUTING.*?: (.+)', line)
        if exec_start:
            current_task = exec_start.group(1)[:120]
            continue

        # Parse EXECUTION result lines
        exec_match = re.search(
            r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\] EXECUTION: '
            r'executor=(\w+) exit=(\d+) duration=(\d+)s',
            line
        )
        if exec_match:
            timestamp = exec_match.group(1) + "+00:00"
            executor = exec_match.group(2)
            exit_code = int(exec_match.group(3))
            duration = int(exec_match.group(4))

            if exit_code == 0:
                outcome = "success"
            elif exit_code == 124:
                outcome = "timeout"
            else:
                outcome = "failure"

            entry = {
                "timestamp": timestamp,
                "task": current_task,
                "brief_version": current_brief_version,
                "brief_tier": current_brief_tier,
                "brief_bytes": current_brief_bytes,
                "executor": executor,
                "route_tier": current_route_tier,
                "route_score": current_route_score,
                "exit_code": exit_code,
                "outcome": outcome,
                "duration_s": duration,
                "escalated": False,
            }
            entries.append(entry)

    # Write entries (overwrite to avoid duplicates on re-seed)
    with open(BENCHMARK_FILE, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    print(f"Seeded {len(entries)} entries from autonomous.log")

    # Also some pre-v1 entries from Feb 22 that didn't have brief logging
    # These are v0 (no brief at all) - we'll skip them as they predate both versions

    _generate_report()
    return entries


def _load_entries():
    """Load all benchmark entries."""
    if not BENCHMARK_FILE.exists():
        return []
    entries = []
    for line in BENCHMARK_FILE.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _generate_report():
    """Generate aggregate benchmark report."""
    entries = _load_entries()
    if not entries:
        return {}

    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_heartbeats": len(entries),
        "target_heartbeats": TARGET_HEARTBEATS,
        "target_success_rate": TARGET_SUCCESS_RATE,
        "baseline_success_rate": BASELINE_SUCCESS_RATE,
        "by_version": {},
        "timeline": [],
        "conclusion": "",
    }

    # Group by brief version
    for version in ("v1", "v2"):
        version_entries = [e for e in entries if e["brief_version"] == version]
        n = len(version_entries)
        if n == 0:
            continue

        successes = sum(1 for e in version_entries if e["outcome"] == "success")
        timeouts = sum(1 for e in version_entries if e["outcome"] == "timeout")
        failures = sum(1 for e in version_entries if e["outcome"] == "failure")
        escalations = sum(1 for e in version_entries if e.get("escalated", False))
        durations = [e["duration_s"] for e in version_entries if e["duration_s"] > 0]

        report["by_version"][version] = {
            "heartbeats": n,
            "success": successes,
            "failure": failures,
            "timeout": timeouts,
            "success_rate": round(successes / n, 3) if n else 0,
            "timeout_rate": round(timeouts / n, 3) if n else 0,
            "failure_rate": round(failures / n, 3) if n else 0,
            "escalation_rate": round(escalations / n, 3) if n else 0,
            "avg_duration_s": round(sum(durations) / len(durations), 1) if durations else 0,
            "by_tier": {},
        }

        # Sub-group by route tier
        for tier in set(e.get("route_tier", "unknown") for e in version_entries):
            tier_entries = [e for e in version_entries if e.get("route_tier") == tier]
            t_n = len(tier_entries)
            t_success = sum(1 for e in tier_entries if e["outcome"] == "success")
            report["by_version"][version]["by_tier"][tier] = {
                "heartbeats": t_n,
                "success_rate": round(t_success / t_n, 3) if t_n else 0,
            }

    # Timeline: running success rate
    running_success = 0
    for i, entry in enumerate(entries):
        if entry["outcome"] == "success":
            running_success += 1
        report["timeline"].append({
            "heartbeat": i + 1,
            "timestamp": entry["timestamp"],
            "version": entry["brief_version"],
            "outcome": entry["outcome"],
            "running_success_rate": round(running_success / (i + 1), 3),
        })

    # Conclusion
    v2_data = report["by_version"].get("v2", {})
    v1_data = report["by_version"].get("v1", {})
    v2_n = v2_data.get("heartbeats", 0)
    v2_rate = v2_data.get("success_rate", 0)
    v1_rate = v1_data.get("success_rate", 0)

    if v2_n >= TARGET_HEARTBEATS:
        if v2_rate >= TARGET_SUCCESS_RATE:
            report["conclusion"] = (
                f"BENCHMARK PASSED: v2 success rate {v2_rate:.0%} >= {TARGET_SUCCESS_RATE:.0%} target "
                f"(v1 baseline: {v1_rate:.0%}, delta: +{v2_rate - v1_rate:.0%}). "
                f"Sample size: {v2_n} heartbeats."
            )
        else:
            report["conclusion"] = (
                f"BENCHMARK FAILED: v2 success rate {v2_rate:.0%} < {TARGET_SUCCESS_RATE:.0%} target "
                f"(v1 baseline: {v1_rate:.0%}, delta: {v2_rate - v1_rate:+.0%}). "
                f"Sample size: {v2_n} heartbeats. Investigate v2 failure modes."
            )
    else:
        remaining = TARGET_HEARTBEATS - v2_n
        report["conclusion"] = (
            f"IN PROGRESS: {v2_n}/{TARGET_HEARTBEATS} v2 heartbeats recorded. "
            f"Current v2 rate: {v2_rate:.0%} (v1 baseline: {v1_rate:.0%}). "
            f"Need {remaining} more heartbeats to conclude."
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2)

    return report


def report():
    """Print the current benchmark report."""
    report = _generate_report()
    if not report:
        print("No benchmark data yet. Run 'seed-from-log' first.")
        return

    print("=" * 60)
    print("  CONTEXT BRIEF v2 BENCHMARK REPORT")
    print("=" * 60)
    print()

    for version, data in report.get("by_version", {}).items():
        print(f"  {version.upper()}: {data['heartbeats']} heartbeats")
        print(f"    Success rate:    {data['success_rate']:.0%} ({data['success']}/{data['heartbeats']})")
        print(f"    Timeout rate:    {data['timeout_rate']:.0%} ({data['timeout']}/{data['heartbeats']})")
        print(f"    Failure rate:    {data['failure_rate']:.0%} ({data['failure']}/{data['heartbeats']})")
        print(f"    Escalation rate: {data['escalation_rate']:.0%}")
        print(f"    Avg duration:    {data['avg_duration_s']}s")
        if data.get("by_tier"):
            print("    By route tier:")
            for tier, td in sorted(data["by_tier"].items()):
                print(f"      {tier}: {td['success_rate']:.0%} ({td['heartbeats']} tasks)")
        print()

    print("  TIMELINE:")
    for t in report.get("timeline", []):
        marker = {
            "success": "+",
            "failure": "X",
            "timeout": "T",
        }.get(t["outcome"], "?")
        print(f"    [{marker}] HB#{t['heartbeat']:2d} {t['version']} "
              f"running={t['running_success_rate']:.0%} "
              f"({t['timestamp'][:19]})")
    print()

    print(f"  {report.get('conclusion', 'No conclusion yet.')}")
    print()

    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: benchmark_brief.py <record|report|seed-from-log>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "record":
        if len(sys.argv) < 5:
            print("Usage: benchmark_brief.py record <preflight_json> <exit_code> <duration_s>")
            sys.exit(1)
        with open(sys.argv[2]) as f:
            pf = json.load(f)
        entry = record(pf, int(sys.argv[3]), int(sys.argv[4]))
        print(json.dumps(entry))

    elif cmd == "report":
        report()

    elif cmd == "seed-from-log":
        seed_from_log()
        report()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
