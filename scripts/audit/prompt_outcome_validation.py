#!/usr/bin/env python3
"""Prompt Assembly Outcome Validation — Phase 9 quality gate.

Correlates context-brief quality signals with task execution outcomes
to identify where prompt assembly is under-serving execution or
introducing noise.

Requires Phase 0 traces with captured context_brief. Re-run as more
traces accumulate — meaningful analysis needs n>=30 briefs.

Usage:
    python3 scripts/audit/prompt_outcome_validation.py run
    python3 scripts/audit/prompt_outcome_validation.py summary
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

_WS = Path(os.environ.get("CLARVIS_WORKSPACE",
                           os.path.expanduser("~/.openclaw/workspace")))
TRACES_ROOT = _WS / "data" / "audit" / "traces"
RESULTS_FILE = _WS / "data" / "audit" / "prompt_outcome_validation.json"

# Section keywords used to identify prompt sections in the context brief.
SECTION_MARKERS = {
    "decision_context": ["SUCCESS CRITERIA", "FAILURE PATTERNS", "WIRE TASK GUIDANCE"],
    "knowledge": ["KNOWLEDGE SYNTHESIS", "CONCEPTUAL FRAMEWORKS"],
    "episodes": ["EPISODIC LESSONS"],
    "working_memory": ["GWT BROADCAST", "ATTENTION CODELETS"],
    "related_tasks": ["RELATED TASKS"],
    "reasoning_scaffold": ["APPROACH", "CODE GENERATION TEMPLATES"],
    "obligations": ["OBLIGATION VIOLATIONS", "GIT HYGIENE"],
}


def _detect_sections(brief: str) -> dict:
    """Detect which prompt sections are present in a brief."""
    found = {}
    for section, markers in SECTION_MARKERS.items():
        present = any(m in brief for m in markers)
        found[section] = present
    return found


def _load_traces() -> list:
    """Load all traces that have both context_brief and outcome."""
    results = []
    if not TRACES_ROOT.exists():
        return results
    for date_dir in sorted(TRACES_ROOT.iterdir()):
        if not date_dir.is_dir():
            continue
        for trace_file in date_dir.glob("*.json"):
            try:
                t = json.loads(trace_file.read_text())
                brief = t.get("prompt", {}).get("context_brief", "")
                outcome_status = t.get("outcome", {}).get("status", "")
                if not brief or not outcome_status:
                    continue
                results.append({
                    "trace_id": t.get("audit_trace_id", ""),
                    "task": t.get("task", {}).get("text", "")[:120],
                    "outcome": outcome_status,
                    "exit_code": t.get("outcome", {}).get("exit_code"),
                    "duration_s": t.get("outcome", {}).get("duration_s", 0),
                    "brief_chars": len(brief),
                    "sections": _detect_sections(brief),
                    "confidence_tier": t.get("preflight", {}).get(
                        "confidence_tier", ""),
                    "completeness": t.get("postflight", {}).get(
                        "completeness", 0),
                    "toggles_shadowed": t.get("toggles_shadowed", []),
                })
            except Exception:
                continue
    return results


def run_validation() -> dict:
    """Run full validation and emit results."""
    traces = _load_traces()
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "traces_with_brief": len(traces),
        "sufficient_data": len(traces) >= 30,
    }

    if not traces:
        report["verdict"] = "NO_DATA"
        report["notes"] = "No traces with context_brief found. Wait for Phase 0 trace window."
        _save(report)
        return report

    # --- Outcome distribution ---
    outcomes = Counter(t["outcome"] for t in traces)
    report["outcome_distribution"] = dict(outcomes)

    # --- Brief size vs outcome ---
    by_outcome = defaultdict(list)
    for t in traces:
        by_outcome[t["outcome"]].append(t)

    size_analysis = {}
    for outcome, entries in by_outcome.items():
        chars = [e["brief_chars"] for e in entries]
        size_analysis[outcome] = {
            "count": len(entries),
            "avg_chars": round(sum(chars) / len(chars)),
            "min_chars": min(chars),
            "max_chars": max(chars),
        }
    report["brief_size_by_outcome"] = size_analysis

    # --- Section presence vs outcome ---
    section_success = defaultdict(lambda: {"present": 0, "absent": 0})
    successes = [t for t in traces if t["outcome"] == "success"]
    failures = [t for t in traces if t["outcome"] in ("failure", "crash", "timeout")]

    for section in SECTION_MARKERS:
        for t in successes:
            if t["sections"].get(section):
                section_success[section]["present"] += 1
            else:
                section_success[section]["absent"] += 1

    report["section_presence_in_successes"] = dict(section_success)

    # --- Undersized brief detection ---
    undersized = [t for t in traces if t["brief_chars"] < 500]
    report["undersized_briefs"] = {
        "count": len(undersized),
        "threshold_chars": 500,
        "traces": [{"trace_id": t["trace_id"], "chars": t["brief_chars"],
                     "outcome": t["outcome"]} for t in undersized],
    }

    # --- Noise signal: very large briefs correlated with failure ---
    large_failures = [t for t in failures if t["brief_chars"] > 5000]
    report["oversized_failures"] = {
        "count": len(large_failures),
        "threshold_chars": 5000,
        "notes": "Large briefs that still resulted in failure may contain noise.",
        "traces": [{"trace_id": t["trace_id"], "chars": t["brief_chars"],
                     "task": t["task"][:80]} for t in large_failures],
    }

    # --- Shadow feature tracking ---
    shadow_traces = [t for t in traces if t["toggles_shadowed"]]
    report["shadow_traces"] = {
        "count": len(shadow_traces),
        "features": Counter(
            f for t in shadow_traces for f in t["toggles_shadowed"]
        ),
    }

    # --- Verdict ---
    if len(traces) < 30:
        report["verdict"] = "INSUFFICIENT_DATA"
        report["notes"] = (
            f"Only {len(traces)} traces with context_brief. "
            "Need >=30 for meaningful analysis. Re-run after 2026-04-23."
        )
    else:
        # Compute quality score
        success_rate = len(successes) / len(traces) if traces else 0
        avg_completeness = (sum(t["completeness"] or 0 for t in successes) /
                            len(successes) if successes else 0)
        if success_rate >= 0.85 and avg_completeness >= 0.8:
            report["verdict"] = "PASS"
        elif success_rate >= 0.70:
            report["verdict"] = "REVISE"
        else:
            report["verdict"] = "FAIL"
        report["success_rate"] = round(success_rate, 3)
        report["avg_completeness"] = round(avg_completeness, 3)

    _save(report)
    return report


def _save(report: dict) -> None:
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = RESULTS_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(report, f, indent=2, default=str)
    os.replace(tmp, RESULTS_FILE)


def print_summary():
    """Print the last validation result."""
    if not RESULTS_FILE.exists():
        print("No validation results. Run: prompt_outcome_validation.py run")
        return
    report = json.loads(RESULTS_FILE.read_text())
    print(f"Prompt Outcome Validation — {report.get('timestamp', '?')}")
    print(f"  Traces with brief: {report.get('traces_with_brief', 0)}")
    print(f"  Verdict: {report.get('verdict', '?')}")
    if "outcome_distribution" in report:
        print(f"  Outcomes: {report['outcome_distribution']}")
    if "brief_size_by_outcome" in report:
        for outcome, stats in report["brief_size_by_outcome"].items():
            print(f"  {outcome}: n={stats['count']} avg={stats['avg_chars']}ch "
                  f"[{stats['min_chars']}–{stats['max_chars']}]")
    if "undersized_briefs" in report:
        ub = report["undersized_briefs"]
        print(f"  Undersized (<{ub['threshold_chars']}ch): {ub['count']}")
    if "shadow_traces" in report:
        st = report["shadow_traces"]
        if st["count"]:
            print(f"  Shadow traces: {st['count']} ({dict(st['features'])})")
    if report.get("notes"):
        print(f"  Notes: {report['notes']}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "summary":
        if RESULTS_FILE.exists():
            print_summary()
        else:
            report = run_validation()
            print_summary()
    elif sys.argv[1] == "run":
        report = run_validation()
        print_summary()
    else:
        print("Usage: prompt_outcome_validation.py [run|summary]")
        sys.exit(1)
