#!/usr/bin/env python3
"""
daily_brain_eval.py — Daily brain quality evaluation (no LLM required).

Runs a structured probe of brain retrieval quality, context assembly,
and metric trends, producing a narrative report with actionable findings.

Design principle: QUALITY OVER SPEED. A 2s query that returns the right
memory is worth more than a 200ms query that returns noise. This script
explicitly does NOT penalize retrieval latency unless it exceeds 10s,
and it treats usefulness as the primary signal.

Usage:
    python3 scripts/daily_brain_eval.py             # Full evaluation + report
    python3 scripts/daily_brain_eval.py quick        # Metrics summary only
    python3 scripts/daily_brain_eval.py report       # Print last report
    python3 scripts/daily_brain_eval.py cron         # Cron mode: eval + digest entry

Output:
    data/daily_brain_eval/latest.json    — structured results
    data/daily_brain_eval/history.jsonl  — rolling history (max 90 entries)
    memory/cron/brain_eval.log           — log output (cron mode)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))

EVAL_DIR = os.path.join(WORKSPACE, "data/daily_brain_eval")
LATEST_FILE = os.path.join(EVAL_DIR, "latest.json")
HISTORY_FILE = os.path.join(EVAL_DIR, "history.jsonl")
MAX_HISTORY = 90

# ── Judged query set ──────────────────────────────────────────────────
# Each query has: text, domain, expected keywords (ANY match = useful),
# and a category for grouping results.
# Quality > speed: we do NOT penalize latency < 10s.
JUDGED_QUERIES = [
    # Identity
    {"q": "Who created Clarvis?", "domain": "identity",
     "expect": ["patrick", "inverse", "granus"], "cat": "identity"},
    {"q": "What model does the conscious layer use?", "domain": "identity",
     "expect": ["minimax", "m2.5", "m2"], "cat": "identity"},
    # Preferences
    {"q": "What timezone does Clarvis operate in?", "domain": "preferences",
     "expect": ["cet", "europe", "timezone"], "cat": "preferences"},
    {"q": "How should changes be measured?", "domain": "preferences",
     "expect": ["before and after", "measure", "phi_metric", "benchmark"], "cat": "preferences"},
    # Goals
    {"q": "What are the active long-term goals?", "domain": "goals",
     "expect": ["goal", "performance", "self-improvement", "heartbeat"], "cat": "goals"},
    {"q": "What is the Performance Index target?", "domain": "goals",
     "expect": ["pi", "performance index", "0.9", "excellent"], "cat": "goals"},
    # Procedures
    {"q": "How to spawn Claude Code from cron?", "domain": "procedures",
     "expect": ["spawn_claude", "claude", "cron_env", "timeout"], "cat": "procedures"},
    {"q": "How does the retrieval gate classify tasks?", "domain": "procedures",
     "expect": ["tier", "light", "deep", "no_retrieval", "retrieval_gate"], "cat": "procedures"},
    # Infrastructure
    {"q": "What port does the OpenClaw gateway run on?", "domain": "infrastructure",
     "expect": ["18789"], "cat": "infrastructure"},
    {"q": "Why does spawn_claude unset CLAUDECODE?", "domain": "infrastructure",
     "expect": ["nesting", "guard", "recursive", "loop"], "cat": "infrastructure"},
    # Context / recent
    {"q": "What was the last heartbeat task?", "domain": "context",
     "expect": ["heartbeat", "task", "episode", "success", "fail"], "cat": "context"},
    {"q": "What is the current Phi metric value?", "domain": "context",
     "expect": ["phi", "0.7", "0.8", "integration"], "cat": "context"},
    # CLR / benchmarks
    {"q": "What is CLR and what dimensions does it measure?", "domain": "learnings",
     "expect": ["clr", "clarvis rating", "dimension", "memory quality", "retrieval"], "cat": "benchmarks"},
    {"q": "How does the CRAG retrieval evaluator work?", "domain": "learnings",
     "expect": ["crag", "correct", "ambiguous", "incorrect", "retrieval_eval"], "cat": "benchmarks"},
    # Cross-domain
    {"q": "What queue tasks are pending for evolution?", "domain": "goals",
     "expect": ["queue", "pending", "task", "p1", "p2"], "cat": "cross-domain"},
    {"q": "What did Clarvis learn recently?", "domain": "learnings",
     "expect": ["learn", "insight", "discover"], "cat": "cross-domain"},
]


def _ensure_dirs():
    os.makedirs(EVAL_DIR, exist_ok=True)


def _extract_hit_texts(hits, max_len=300):
    """Extract text snippets from brain recall hits."""
    texts = []
    for h in hits[:3]:
        if isinstance(h, str):
            doc = h
        elif isinstance(h, dict):
            doc = h.get("document", h.get("text", str(h)))
        else:
            doc = str(h)
        texts.append(doc[:max_len])
    return texts


def _probe_single_query(brain, item):
    """Run a single retrieval probe query. Returns result dict."""
    t0 = time.time()
    try:
        hits = brain.recall(item["q"], n=5)
        elapsed = time.time() - t0
        top_texts = _extract_hit_texts(hits)

        # Judge: any expected keyword in any top-3 result?
        combined = " ".join(top_texts).lower()
        useful = any(kw in combined for kw in item["expect"])

        return {
            "query": item["q"],
            "domain": item["domain"],
            "category": item["cat"],
            "speed_ms": round(elapsed * 1000),
            "n_results": len(hits),
            "useful": useful,
            "top_snippets": [t[:150] for t in top_texts],
        }
    except Exception as e:
        return {
            "query": item["q"],
            "domain": item["domain"],
            "category": item["cat"],
            "speed_ms": 0,
            "n_results": 0,
            "useful": False,
            "error": str(e),
        }


def _aggregate_probe_results(results):
    """Aggregate per-query results into summary with category breakdown."""
    speeds = [r["speed_ms"] for r in results if r["speed_ms"] > 0]
    useful_count = sum(1 for r in results if r["useful"])
    total = len(results)

    # Per-category breakdown
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "useful": 0, "speeds": []}
        categories[cat]["total"] += 1
        if r["useful"]:
            categories[cat]["useful"] += 1
        if r["speed_ms"] > 0:
            categories[cat]["speeds"].append(r["speed_ms"])

    cat_summary = {}
    for cat, data in categories.items():
        cat_summary[cat] = {
            "useful_rate": round(data["useful"] / data["total"], 2) if data["total"] else 0,
            "avg_speed_ms": round(sum(data["speeds"]) / len(data["speeds"])) if data["speeds"] else 0,
            "total": data["total"],
            "useful": data["useful"],
        }

    failures = [
        {"query": r["query"], "domain": r["domain"], "top_snippets": r.get("top_snippets", [])}
        for r in results if not r["useful"]
    ]

    return {
        "total_queries": total,
        "useful_count": useful_count,
        "useful_rate": round(useful_count / total, 3) if total else 0,
        "avg_speed_ms": round(sum(speeds) / len(speeds)) if speeds else 0,
        "p95_speed_ms": sorted(speeds)[int(len(speeds) * 0.95)] if speeds else 0,
        "max_speed_ms": max(speeds) if speeds else 0,
        # Quality-first: only flag speed if truly problematic (>10s)
        "speed_concern": any(s > 10000 for s in speeds),
        "categories": cat_summary,
        "failures": failures,
    }


def _run_retrieval_probe():
    """Run judged retrieval probe. Returns per-query results and summary."""
    from clarvis.brain import brain

    results = [_probe_single_query(brain, item) for item in JUDGED_QUERIES]
    summary = _aggregate_probe_results(results)
    return results, summary


def _read_metric_trends():
    """Read recent PI, CLR, Phi trends for context."""
    trends = {}

    # CLR history
    clr_hist_path = os.path.join(WORKSPACE, "data/clr_history.jsonl")
    if os.path.exists(clr_hist_path):
        entries = []
        with open(clr_hist_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        recent = entries[-7:]  # Last week
        if recent:
            scores = [e.get("clr", 0) for e in recent]
            trends["clr"] = {
                "current": scores[-1],
                "7d_avg": round(sum(scores) / len(scores), 3),
                "7d_min": round(min(scores), 3),
                "7d_max": round(max(scores), 3),
                "trend": "up" if len(scores) > 1 and scores[-1] > scores[0] else "stable" if len(scores) <= 1 else "down",
            }

    # Phi history
    phi_hist_path = os.path.join(WORKSPACE, "data/phi_history.jsonl")
    if os.path.exists(phi_hist_path):
        entries = []
        with open(phi_hist_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        recent = entries[-7:]
        if recent:
            scores = [e.get("phi", e.get("score", 0)) for e in recent]
            trends["phi"] = {
                "current": round(scores[-1], 3),
                "7d_avg": round(sum(scores) / len(scores), 3),
                "trend": "up" if len(scores) > 1 and scores[-1] > scores[0] else "stable" if len(scores) <= 1 else "down",
            }

    # Latest PI
    pi_path = os.path.join(WORKSPACE, "data/performance_metrics.json")
    if os.path.exists(pi_path):
        try:
            with open(pi_path) as f:
                pi = json.load(f)
            trends["pi"] = {
                "current": pi.get("pi", pi.get("score", 0)),
                "timestamp": pi.get("timestamp", ""),
            }
        except Exception:
            pass

    return trends


def _score_usefulness(useful_rate):
    """Score retrieval usefulness (weight 0.50). Returns (finding, component)."""
    if useful_rate >= 0.85:
        finding = f"Retrieval usefulness is strong ({useful_rate:.0%})."
    elif useful_rate >= 0.70:
        finding = f"Retrieval usefulness is acceptable ({useful_rate:.0%}) but has room to improve."
    else:
        finding = f"CONCERN: Retrieval usefulness is below target ({useful_rate:.0%}, target ≥70%)."
    return finding, {"score": min(1.0, useful_rate / 0.85), "weight": 0.50}


def _score_failures(failures):
    """Score failure rate (weight 0.20). Returns (findings, component)."""
    findings = []
    if failures:
        weak_domains = {}
        for f in failures:
            d = f["domain"]
            weak_domains[d] = weak_domains.get(d, 0) + 1
        worst = max(weak_domains, key=weak_domains.get)
        findings.append(f"Weakest domain: {worst} ({weak_domains[worst]} misses). Consider adding/updating memories in this collection.")
        score = max(0.0, 1.0 - len(failures) / len(JUDGED_QUERIES))
    else:
        score = 1.0
    return findings, {"score": score, "weight": 0.20}


def _score_trends(trends):
    """Score metric trends (weight 0.20). Returns (findings, component)."""
    findings = []
    clr = trends.get("clr", {})
    phi = trends.get("phi", {})
    if clr:
        if clr.get("trend") == "down":
            findings.append(f"CLR trending down (current={clr['current']:.3f}, 7d_avg={clr['7d_avg']:.3f}). Investigate which dimension dropped.")
        else:
            findings.append(f"CLR stable/up (current={clr['current']:.3f}).")
    if phi:
        if phi.get("trend") == "down":
            findings.append(f"Phi trending down (current={phi['current']:.3f}). Cross-collection integration may be weakening.")

    score = 1.0
    if clr.get("trend") == "down":
        score -= 0.3
    if phi.get("trend") == "down":
        score -= 0.2
    return findings, {"score": max(0.0, score), "weight": 0.20}


def _score_speed(avg_ms):
    """Score speed (weight 0.10). Only penalize >10s. Returns (finding, component)."""
    if avg_ms > 10000:
        finding = f"SPEED CONCERN: avg query latency {avg_ms}ms exceeds 10s threshold. This may cause timeouts."
        score = max(0.0, 1.0 - (avg_ms - 10000) / 20000)
    elif avg_ms > 5000:
        finding = f"Query latency elevated ({avg_ms}ms avg) but within acceptable range. Quality is primary."
        score = 0.8
    else:
        finding = None
        score = 1.0
    return finding, {"score": score, "weight": 0.10}


def _build_recommendations(useful_rate, failures, trends):
    """Build actionable recommendations from assessment results."""
    recommendations = []
    if useful_rate < 0.85:
        for f in failures:
            if not f.get("top_snippets"):
                recommendations.append(f"Add memories for: '{f['query']}' (empty results)")
            else:
                recommendations.append(f"Improve retrieval for: '{f['query']}' (results exist but off-topic)")

    clr = trends.get("clr", {})
    if clr and clr.get("current", 0) < 0.80:
        recommendations.append("CLR below 0.80 — review dimension subscores for specific weaknesses.")
    return recommendations


def _assess_quality(retrieval_summary, trends):
    """Produce qualitative assessment with actionable findings.

    DESIGN NOTE: We deliberately do NOT recommend chasing speed at the
    expense of quality. A 600ms query returning useful results is fine.
    Only flag speed if it's >10s (causing real UX or timeout problems).
    """
    findings = []
    score_components = {}

    useful_rate = retrieval_summary["useful_rate"]
    finding, comp = _score_usefulness(useful_rate)
    findings.append(finding)
    score_components["usefulness"] = comp

    fail_findings, comp = _score_failures(retrieval_summary["failures"])
    findings.extend(fail_findings)
    score_components["failure_rate"] = comp

    trend_findings, comp = _score_trends(trends)
    findings.extend(trend_findings)
    score_components["trends"] = comp

    speed_finding, comp = _score_speed(retrieval_summary["avg_speed_ms"])
    if speed_finding:
        findings.append(speed_finding)
    score_components["speed"] = comp

    total_score = sum(c["score"] * c["weight"] for c in score_components.values())
    recommendations = _build_recommendations(useful_rate, retrieval_summary["failures"], trends)

    return {
        "quality_score": round(total_score, 3),
        "components": score_components,
        "findings": findings,
        "recommendations": recommendations,
    }


def _print_eval_report(probe_summary, trends, assessment):
    """Print the evaluation report to stdout."""
    # Findings
    print("Findings:")
    for f in assessment["findings"]:
        print(f"  - {f}")
    print()

    if assessment["recommendations"]:
        print("Recommendations:")
        for r in assessment["recommendations"]:
            print(f"  → {r}")
        print()

    # Per-category breakdown
    print("Category Breakdown:")
    for cat, data in probe_summary["categories"].items():
        status = "OK" if data["useful_rate"] >= 0.80 else "WEAK" if data["useful_rate"] >= 0.50 else "FAIL"
        print(f"  [{status}] {cat:15s}: {data['useful']}/{data['total']} useful, "
              f"avg {data['avg_speed_ms']}ms")
    print()

    # Failures detail
    if probe_summary["failures"]:
        print("Failure Details:")
        for f in probe_summary["failures"]:
            print(f"  MISS: {f['query']} ({f['domain']})")
            for i, s in enumerate(f.get("top_snippets", [])[:2]):
                print(f"    got-{i+1}: {s[:100]}")
        print()


def _save_eval_result(result, assessment, probe_summary, trends):
    """Save evaluation result to latest.json and append to history."""
    with open(LATEST_FILE, "w") as f:
        json.dump(result, f, indent=2)

    history_entry = {
        "timestamp": result["timestamp"],
        "quality_score": assessment["quality_score"],
        "useful_rate": probe_summary["useful_rate"],
        "avg_speed_ms": probe_summary["avg_speed_ms"],
        "clr": trends.get("clr", {}).get("current"),
        "phi": trends.get("phi", {}).get("current"),
        "n_failures": len(probe_summary["failures"]),
    }
    _append_history(history_entry)


def run_full_eval():
    """Run complete daily brain quality evaluation."""
    _ensure_dirs()
    t0 = time.time()

    print("=== Daily Brain Quality Evaluation ===")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()

    # 1. Retrieval probe
    print("Running retrieval probe...")
    probe_results, probe_summary = _run_retrieval_probe()
    print(f"  Queries: {probe_summary['total_queries']}, "
          f"Useful: {probe_summary['useful_count']}/{probe_summary['total_queries']} "
          f"({probe_summary['useful_rate']:.0%})")
    print(f"  Speed: avg={probe_summary['avg_speed_ms']}ms, "
          f"P95={probe_summary['p95_speed_ms']}ms")
    print()

    # 2. Metric trends
    print("Reading metric trends...")
    trends = _read_metric_trends()
    for name, data in trends.items():
        current = data.get("current", "?")
        trend = data.get("trend", "?")
        print(f"  {name}: {current} (trend: {trend})")
    print()

    # 3. Quality assessment
    print("Assessing quality...")
    assessment = _assess_quality(probe_summary, trends)
    print(f"  Quality Score: {assessment['quality_score']:.3f}")
    print()

    _print_eval_report(probe_summary, trends, assessment)

    elapsed = time.time() - t0
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 1),
        "retrieval": probe_summary,
        "trends": trends,
        "assessment": assessment,
    }

    _save_eval_result(result, assessment, probe_summary, trends)

    print(f"Evaluation complete in {elapsed:.1f}s")
    print(f"Quality Score: {assessment['quality_score']:.3f}")
    print(f"Saved to: {LATEST_FILE}")

    return result


def _append_history(entry):
    """Append to rolling history file."""
    entries = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    entries.append(entry)
    # Keep only recent entries
    entries = entries[-MAX_HISTORY:]

    with open(HISTORY_FILE, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def print_report():
    """Print last evaluation report."""
    if not os.path.exists(LATEST_FILE):
        print("No evaluation found. Run: python3 scripts/daily_brain_eval.py")
        return

    with open(LATEST_FILE) as f:
        result = json.load(f)

    ts = result.get("timestamp", "?")
    assessment = result.get("assessment", {})
    retrieval = result.get("retrieval", {})

    print(f"=== Last Brain Evaluation ({ts}) ===")
    print(f"Quality Score: {assessment.get('quality_score', '?')}")
    print(f"Useful Rate:   {retrieval.get('useful_rate', '?'):.0%}")
    print(f"Avg Speed:     {retrieval.get('avg_speed_ms', '?')}ms")
    print()
    for f in assessment.get("findings", []):
        print(f"  - {f}")
    for r in assessment.get("recommendations", []):
        print(f"  → {r}")


def run_quick():
    """Quick metrics summary without full probe."""
    trends = _read_metric_trends()
    print("=== Quick Brain Metrics ===")
    for name, data in trends.items():
        current = data.get("current", "?")
        trend = data.get("trend", "?")
        print(f"  {name}: {current} (trend: {trend})")

    if os.path.exists(LATEST_FILE):
        with open(LATEST_FILE) as f:
            last = json.load(f)
        print(f"\nLast eval: quality={last['assessment']['quality_score']:.3f}, "
              f"useful={last['retrieval']['useful_rate']:.0%}, "
              f"at {last['timestamp'][:19]}")


def run_cron():
    """Cron mode: run eval and write digest entry."""
    result = run_full_eval()

    # Write digest entry
    try:
        from digest_writer import write_digest
        assessment = result["assessment"]
        retrieval = result["retrieval"]
        summary = (
            f"Brain quality evaluation: score={assessment['quality_score']:.3f}, "
            f"retrieval usefulness={retrieval['useful_rate']:.0%} "
            f"({retrieval['useful_count']}/{retrieval['total_queries']}), "
            f"avg speed={retrieval['avg_speed_ms']}ms. "
        )
        if assessment["recommendations"]:
            summary += "Top recommendation: " + assessment["recommendations"][0]
        write_digest("evolution", summary)
    except Exception as e:
        print(f"Warning: could not write digest entry: {e}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    if mode == "quick":
        run_quick()
    elif mode == "report":
        print_report()
    elif mode == "cron":
        run_cron()
    else:
        run_full_eval()
