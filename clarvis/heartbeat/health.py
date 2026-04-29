"""Heartbeat health analyzer — detect silent failures across recent autonomous cycles.

Parses memory/cron/autonomous.log to reconstruct the per-heartbeat outcome:

    executed       — preflight ok, task ran (success or fail)
    no_task        — preflight returned all_filtered_by_v2, no_tasks, queue_empty
    deferred       — should_defer=true (cognitive load / all candidates deferred)
    gate_skip      — heartbeat gate decided to skip
    crash          — instant-fail (<10s exit non-zero) or preflight crash
    timeout        — outer 124 / kill
    unknown        — couldn't classify

The shallow evening grep ("error|fail|warn") completely missed the recurring
all_filtered_by_v2 cycle, so this module turns log content into structured
metrics that downstream review prompts and the watchdog can act on.

Usage
-----
    from clarvis.heartbeat.health import analyze, format_report

    report = analyze(window=24)              # last 24 heartbeat starts
    print(format_report(report))             # human-readable

    report["consecutive_no_task"]            # int — for watchdog
    report["execution_rate"]                 # float — for digest

CLI:

    python3 -m clarvis.heartbeat.health [--window N] [--json|--report]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
LOG_PATH = WORKSPACE / "memory" / "cron" / "autonomous.log"

_TS_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]")
_GATE_WAKE = re.compile(r"GATE: wake")
_GATE_SKIP = re.compile(r"GATE: skip")
_HB_START = re.compile(r"=== Heartbeat starting")
_HB_DONE = re.compile(r"=== Heartbeat complete \(preflight=([\d.?]+)s \+ exec=(\d+)s \+ postflight=([\d.?]+)s\)")
_PF_STATUS = re.compile(r"PREFLIGHT: status=(\S+)\s+task_salience=(\S+)\s+route=(\S+)")
_NO_TASK = re.compile(r"No task selected — exiting")
_DEFERRED = re.compile(r"COGNITIVE LOAD: DEFERRING task")
_QUEUE_EMPTY = re.compile(r"Queue empty — spawning task generation")
_EXEC = re.compile(r"EXECUTION: executor=(\S+) exit=(\S+) duration=(\d+)s timeout=(\d+)s tier=(\S+)")
_CRASH_GUARD = re.compile(r"CRASH_GUARD:.*Instant-fail")
_TASK_TIMEOUT = re.compile(r"executor=\S+ exit=124")

# Bucket boundaries (P0 = critical, surfaces in alerts)
NO_TASK_RUN_RATIO_P0 = 0.50   # >50% of recent cycles executed nothing → critical
NO_TASK_RUN_RATIO_P1 = 0.25   # >25% → warn
CONSECUTIVE_NO_TASK_P0 = 3    # 3 in a row → critical
EXEC_FAIL_RATE_P0 = 0.50      # >50% executed cycles ended exit!=0 → critical
INSTANT_FAIL_RATE_P1 = 0.20   # >20% executed cycles instant-fail → warn


@dataclass
class HeartbeatRecord:
    """One heartbeat cycle reconstructed from autonomous.log."""
    timestamp: str = ""
    gate: Optional[str] = None         # "wake" | "skip" | None (no gate line)
    preflight_status: Optional[str] = None  # ok|all_filtered_by_v2|no_tasks|queue_empty|...
    salience: Optional[float] = None
    route: Optional[str] = None
    deferred: bool = False
    queue_replenish: bool = False
    no_task: bool = False
    executor: Optional[str] = None
    exec_exit: Optional[int] = None
    exec_duration_s: Optional[int] = None
    exec_timeout_s: Optional[int] = None
    exec_tier: Optional[str] = None
    crash_guard_instant_fail: bool = False
    completed: bool = False             # saw "Heartbeat complete"

    @property
    def outcome(self) -> str:
        """Classify into a single bucket."""
        if self.gate == "skip":
            return "gate_skip"
        if self.preflight_status in ("all_filtered_by_v2", "no_tasks"):
            return "no_task"
        if self.preflight_status in ("queue_empty",):
            return "queue_empty"
        if self.deferred:
            return "deferred"
        if self.exec_exit is None:
            # Gate woke but neither preflight status nor execution recorded
            return "unknown"
        if self.crash_guard_instant_fail:
            return "crash"
        if self.exec_exit == 124:
            return "timeout"
        if self.exec_exit == 0:
            return "executed_ok"
        return "executed_fail"


def _iter_log_lines(path: Path = LOG_PATH, max_bytes: int = 5_000_000) -> Iterable[str]:
    if not path.exists():
        return
    size = path.stat().st_size
    with open(path, "rb") as fh:
        if size > max_bytes:
            fh.seek(size - max_bytes)
            fh.readline()  # drop the partial line we just landed in the middle of
        for raw in fh:
            try:
                yield raw.decode("utf-8", errors="replace").rstrip("\n")
            except Exception:
                continue


def parse_records(lines: Iterable[str]) -> list[HeartbeatRecord]:
    """Walk lines, emit one record per gate-wake (or per heartbeat-starting block).

    A 'cycle' begins on either:
      • "GATE: wake" — gate ran and decided to proceed
      • "GATE: skip" — gate decided to skip (still its own record)
      • "Heartbeat starting" — fallback if no gate line was logged

    A cycle ends when we see the next cycle marker or EOF.
    """
    records: list[HeartbeatRecord] = []
    cur: Optional[HeartbeatRecord] = None

    def _flush():
        nonlocal cur
        if cur is not None:
            records.append(cur)
            cur = None

    def _ts(line: str) -> str:
        m = _TS_RE.search(line)
        return m.group(1) if m else ""

    for line in lines:
        # Gate decisions create new records (skip is its own record; wake starts execution one)
        if _GATE_WAKE.search(line):
            _flush()
            cur = HeartbeatRecord(timestamp=_ts(line), gate="wake")
            continue
        if _GATE_SKIP.search(line):
            _flush()
            cur = HeartbeatRecord(timestamp=_ts(line), gate="skip")
            _flush()
            continue
        if _HB_START.search(line) and cur is None:
            cur = HeartbeatRecord(timestamp=_ts(line))
            continue

        if cur is None:
            continue

        m = _PF_STATUS.search(line)
        if m:
            cur.preflight_status = m.group(1)
            try:
                cur.salience = float(m.group(2))
            except ValueError:
                pass
            cur.route = m.group(3)
            continue

        if _NO_TASK.search(line):
            cur.no_task = True
            continue

        if _DEFERRED.search(line):
            cur.deferred = True
            continue

        if _QUEUE_EMPTY.search(line):
            cur.queue_replenish = True
            continue

        m = _EXEC.search(line)
        if m:
            cur.executor = m.group(1)
            try:
                cur.exec_exit = int(m.group(2))
            except ValueError:
                cur.exec_exit = None
            try:
                cur.exec_duration_s = int(m.group(3))
                cur.exec_timeout_s = int(m.group(4))
            except ValueError:
                pass
            cur.exec_tier = m.group(5)
            continue

        if _CRASH_GUARD.search(line):
            cur.crash_guard_instant_fail = True
            continue

        if _HB_DONE.search(line):
            cur.completed = True
            continue

    _flush()
    return records


def _consecutive(records: list[HeartbeatRecord], predicate) -> int:
    """Count tail records (most recent) where predicate is true."""
    n = 0
    for r in reversed(records):
        if predicate(r):
            n += 1
        else:
            break
    return n


@dataclass
class HealthReport:
    """Roll-up over a window of heartbeat records."""
    window: int
    total_cycles: int
    counts: dict = field(default_factory=dict)
    rates: dict = field(default_factory=dict)
    consecutive_no_task: int = 0
    consecutive_no_execution: int = 0
    last_executed_ts: Optional[str] = None
    last_no_task_ts: Optional[str] = None
    severity: str = "ok"          # ok | warn | critical
    findings: list[str] = field(default_factory=list)
    recent_outcomes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def analyze(window: int = 24, log_path: Path | str = LOG_PATH) -> HealthReport:
    """Analyze the last `window` heartbeat cycles.

    `window` is interpreted as cycles, not hours — autonomous fires ~12x/day so
    24 cycles ≈ 2 days of heartbeats. The default is intentionally large enough
    to catch slow-drift problems but small enough to ignore long-resolved events.
    """
    path = Path(log_path)
    records = parse_records(_iter_log_lines(path))
    if window > 0:
        records = records[-window:]

    counts: dict[str, int] = {}
    last_executed_ts: Optional[str] = None
    last_no_task_ts: Optional[str] = None
    for r in records:
        b = r.outcome
        counts[b] = counts.get(b, 0) + 1
        if b in ("executed_ok", "executed_fail") and r.timestamp:
            last_executed_ts = r.timestamp
        if b in ("no_task", "queue_empty") and r.timestamp:
            last_no_task_ts = r.timestamp

    n = len(records) or 1
    rates = {k: round(v / n, 4) for k, v in counts.items()}

    no_task_buckets = {"no_task", "queue_empty", "deferred"}
    consec_no_task = _consecutive(records, lambda r: r.outcome in no_task_buckets)
    consec_no_exec = _consecutive(
        records, lambda r: r.outcome not in ("executed_ok", "executed_fail")
    )

    findings: list[str] = []
    severity = "ok"

    no_task_rate = sum(counts.get(b, 0) for b in no_task_buckets) / n
    if consec_no_task >= CONSECUTIVE_NO_TASK_P0:
        severity = "critical"
        findings.append(
            f"{consec_no_task} consecutive heartbeats without execution "
            f"(no_task/deferred/queue_empty)"
        )
    elif no_task_rate >= NO_TASK_RUN_RATIO_P0:
        severity = "critical"
        findings.append(
            f"no-task rate {no_task_rate:.0%} of last {n} cycles — queue selector likely stuck"
        )
    elif no_task_rate >= NO_TASK_RUN_RATIO_P1:
        severity = max(severity, "warn", key=_sev_rank)
        findings.append(
            f"no-task rate {no_task_rate:.0%} of last {n} cycles — investigate queue filters"
        )

    executed = counts.get("executed_ok", 0) + counts.get("executed_fail", 0)
    if executed:
        fail_rate = counts.get("executed_fail", 0) / executed
        if fail_rate >= EXEC_FAIL_RATE_P0:
            severity = max(severity, "critical", key=_sev_rank)
            findings.append(
                f"executed-cycle failure rate {fail_rate:.0%} ({counts.get('executed_fail', 0)}/{executed})"
            )
        instant = counts.get("crash", 0)
        if instant / executed >= INSTANT_FAIL_RATE_P1:
            severity = max(severity, "warn", key=_sev_rank)
            findings.append(
                f"instant-fail rate {instant/executed:.0%} ({instant}/{executed}) — infra/auth issue likely"
            )
    elif n > 0:
        # Zero executions across the entire window is a P0 silent failure
        severity = "critical"
        findings.append(f"0 executions across last {n} cycles")

    if counts.get("timeout", 0) >= max(2, n // 10):
        severity = max(severity, "warn", key=_sev_rank)
        findings.append(f"{counts.get('timeout', 0)} timeout(s) in last {n} cycles")

    recent = [
        {
            "timestamp": r.timestamp,
            "outcome": r.outcome,
            "preflight_status": r.preflight_status,
            "executor": r.executor,
            "exec_exit": r.exec_exit,
            "exec_duration_s": r.exec_duration_s,
            "route": r.route,
        }
        for r in records[-min(10, n):]
    ]

    return HealthReport(
        window=window,
        total_cycles=len(records),
        counts=counts,
        rates=rates,
        consecutive_no_task=consec_no_task,
        consecutive_no_execution=consec_no_exec,
        last_executed_ts=last_executed_ts,
        last_no_task_ts=last_no_task_ts,
        severity=severity,
        findings=findings,
        recent_outcomes=recent,
    )


def _sev_rank(s: str) -> int:
    return {"ok": 0, "warn": 1, "critical": 2}.get(s, 0)


def format_report(report: HealthReport) -> str:
    lines = [
        f"# Heartbeat Health — last {report.total_cycles} cycle(s)",
        f"Severity: {report.severity.upper()}",
        "",
        "## Outcomes",
    ]
    if report.counts:
        for bucket, count in sorted(report.counts.items(), key=lambda kv: -kv[1]):
            rate = report.rates.get(bucket, 0)
            lines.append(f"  {bucket:16s} {count:3d}  ({rate:.0%})")
    else:
        lines.append("  (no records)")

    lines.extend(["", "## Trailing state"])
    lines.append(f"  consecutive non-execution cycles: {report.consecutive_no_execution}")
    lines.append(f"  consecutive no-task cycles:       {report.consecutive_no_task}")
    if report.last_executed_ts:
        lines.append(f"  last executed:  {report.last_executed_ts}")
    if report.last_no_task_ts:
        lines.append(f"  last no-task:   {report.last_no_task_ts}")

    if report.findings:
        lines.extend(["", "## Findings"])
        for f in report.findings:
            lines.append(f"  - {f}")

    if report.recent_outcomes:
        lines.extend(["", "## Recent cycles (oldest → newest)"])
        for r in report.recent_outcomes:
            extra = []
            if r.get("preflight_status"):
                extra.append(f"pf={r['preflight_status']}")
            if r.get("executor"):
                extra.append(f"exec={r['executor']}")
            if r.get("exec_exit") is not None:
                extra.append(f"exit={r['exec_exit']}")
            if r.get("exec_duration_s") is not None:
                extra.append(f"dur={r['exec_duration_s']}s")
            tail = " ".join(extra)
            lines.append(f"  {r.get('timestamp','?')} {r['outcome']:14s}  {tail}")

    return "\n".join(lines) + "\n"


def digest_summary(report: HealthReport) -> str:
    """One-paragraph digest for digest_writer (≤ ~280 chars)."""
    parts = [
        f"Heartbeat health [{report.severity}]: {report.total_cycles} cycles, "
        f"{report.counts.get('executed_ok',0)} ok / {report.counts.get('executed_fail',0)} fail"
    ]
    no_task = sum(report.counts.get(k, 0) for k in ("no_task", "queue_empty", "deferred"))
    if no_task:
        parts.append(f"{no_task} no-task")
    if report.counts.get("timeout"):
        parts.append(f"{report.counts['timeout']} timeout")
    if report.counts.get("crash"):
        parts.append(f"{report.counts['crash']} crash")
    if report.consecutive_no_execution:
        parts.append(f"streak={report.consecutive_no_execution} non-exec")
    if report.findings:
        parts.append("findings: " + "; ".join(report.findings[:2]))
    return ". ".join(parts) + "."


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Heartbeat health analyzer")
    p.add_argument("--window", type=int, default=24, help="number of recent cycles to analyze")
    p.add_argument("--log", default=str(LOG_PATH), help="path to autonomous.log")
    p.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p.add_argument("--digest", action="store_true", help="emit one-line digest summary only")
    args = p.parse_args(argv)

    report = analyze(window=args.window, log_path=args.log)
    if args.json:
        print(json.dumps(report.to_dict(), default=str))
    elif args.digest:
        print(digest_summary(report))
    else:
        print(format_report(report))
    # Exit code conveys severity for shell usage
    return {"ok": 0, "warn": 1, "critical": 2}.get(report.severity, 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
