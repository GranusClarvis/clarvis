#!/usr/bin/env python3
"""Wiki Retrieval Evaluation Suite — compare wiki-assisted vs baseline retrieval.

Measures 5 dimensions:
  1. Citation quality  — do returned results cite traceable sources?
  2. Consistency       — do repeated queries return stable results?
  3. Coverage          — what fraction of gold questions get relevant hits?
  4. Latency           — wall-clock time for each retrieval path
  5. Operator usefulness — substring match against gold evidence

Usage:
    python3 wiki_eval.py run              # Full eval, print report
    python3 wiki_eval.py run --json       # Machine-readable JSON output
    python3 wiki_eval.py compare          # Side-by-side wiki vs baseline
    python3 wiki_eval.py trend [N]        # Show last N eval runs
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
GOLD_FILE = WORKSPACE / "data" / "wiki_eval" / "gold_questions.json"
HISTORY_FILE = WORKSPACE / "data" / "wiki_eval" / "history.jsonl"
LATEST_FILE = WORKSPACE / "data" / "wiki_eval" / "latest.json"

sys.path.insert(0, str(WORKSPACE / "scripts"))


def _load_gold():
    with open(GOLD_FILE) as f:
        return json.load(f)["questions"]


# ── Retrieval backends ────────────────────────────────────────────


def _wiki_retrieve(query: str, max_pages: int = 5) -> dict:
    """Wiki-first retrieval via wiki_retrieval.py."""
    from wiki_retrieval import wiki_retrieve
    t0 = time.monotonic()
    result = wiki_retrieve(query, max_pages=max_pages, expand_graph=True,
                           include_raw=True, fallback_broad=True)
    elapsed = time.monotonic() - t0
    result["latency_ms"] = round(elapsed * 1000, 1)
    return result


def _baseline_retrieve(query: str, n: int = 10) -> dict:
    """Baseline brain.recall across all collections."""
    from clarvis.brain import brain
    t0 = time.monotonic()
    results = brain.recall(query, n=n, caller="wiki_eval_baseline")
    elapsed = time.monotonic() - t0
    hits = []
    for r in results:
        hits.append({
            "id": r.get("id", ""),
            "document": r.get("document", "")[:500],
            "distance": r.get("distance", 999),
            "collection": r.get("collection", ""),
            "source": r.get("metadata", {}).get("source", ""),
        })
    return {
        "query": query,
        "hits": hits,
        "latency_ms": round(elapsed * 1000, 1),
    }


# ── Scoring functions ─────────────────────────────────────────────


def score_citation_quality(result: dict) -> float:
    """Fraction of wiki hits that have traceable citation sources."""
    wiki_hits = result.get("wiki_hits", [])
    if not wiki_hits:
        return 0.0
    cited = sum(1 for h in wiki_hits if h.get("sources"))
    return cited / len(wiki_hits)


def score_citation_quality_baseline(result: dict) -> float:
    """Fraction of baseline hits with a non-empty source metadata."""
    hits = result.get("hits", [])
    if not hits:
        return 0.0
    cited = sum(1 for h in hits if h.get("source"))
    return cited / len(hits)


def score_coverage(result: dict, gold: dict) -> float:
    """Check if any expected slug appears in the wiki results."""
    expected_slugs = set(gold.get("expected_slugs", []))
    if not expected_slugs:
        return 1.0  # no expectation = pass
    found_slugs = {h.get("slug", "") for h in result.get("wiki_hits", [])}
    # Also check graph neighbors
    for n in result.get("graph_neighbors", []):
        if n.get("slug"):
            found_slugs.add(n["slug"])
    overlap = expected_slugs & found_slugs
    return len(overlap) / len(expected_slugs)


def score_coverage_baseline(result: dict, gold: dict) -> float:
    """Check if expected substrings appear in baseline results."""
    expected = gold.get("expected_substrings", [])
    if not expected:
        return 1.0
    all_text = " ".join(h.get("document", "") for h in result.get("hits", [])).lower()
    found = sum(1 for s in expected if s.lower() in all_text)
    return found / len(expected)


def score_usefulness(result: dict, gold: dict) -> float:
    """Substring match: how many gold evidence substrings found in wiki content."""
    expected = gold.get("expected_substrings", [])
    if not expected:
        return 1.0
    all_content = ""
    for h in result.get("wiki_hits", []):
        all_content += " " + h.get("content", "") + " " + h.get("title", "")
    for n in result.get("graph_neighbors", []):
        all_content += " " + n.get("title", "")
    for s in result.get("raw_sources", []):
        all_content += " " + s.get("content", "")
    for b in result.get("broad_hits", []):
        all_content += " " + b.get("document", "")
    all_content = all_content.lower()
    found = sum(1 for s in expected if s.lower() in all_content)
    return found / len(expected)


def score_usefulness_baseline(result: dict, gold: dict) -> float:
    """Substring match for baseline results."""
    expected = gold.get("expected_substrings", [])
    if not expected:
        return 1.0
    all_text = " ".join(h.get("document", "") for h in result.get("hits", [])).lower()
    found = sum(1 for s in expected if s.lower() in all_text)
    return found / len(expected)


def score_consistency(results_a: dict, results_b: dict) -> float:
    """Jaccard similarity of returned slugs/IDs between two runs of the same query."""
    def _ids(r):
        ids = set()
        for h in r.get("wiki_hits", []):
            ids.add(h.get("slug") or h.get("memory_id", ""))
        for h in r.get("hits", []):
            ids.add(h.get("id", ""))
        return ids
    a, b = _ids(results_a), _ids(results_b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── Evaluation runner ─────────────────────────────────────────────


def run_eval(gold_questions: list[dict] | None = None) -> dict:
    """Run full evaluation. Returns structured results dict."""
    if gold_questions is None:
        gold_questions = _load_gold()

    results = []
    wiki_latencies = []
    baseline_latencies = []

    for gold in gold_questions:
        query = gold["query"]
        qid = gold["id"]

        # Run wiki retrieval
        wiki_result = _wiki_retrieve(query)
        wiki_latencies.append(wiki_result["latency_ms"])

        # Run baseline retrieval
        baseline_result = _baseline_retrieve(query)
        baseline_latencies.append(baseline_result["latency_ms"])

        # Run wiki again for consistency check
        wiki_result_2 = _wiki_retrieve(query)

        # Score wiki path
        wiki_scores = {
            "citation_quality": score_citation_quality(wiki_result),
            "coverage": score_coverage(wiki_result, gold),
            "usefulness": score_usefulness(wiki_result, gold),
            "consistency": score_consistency(wiki_result, wiki_result_2),
            "latency_ms": wiki_result["latency_ms"],
        }

        # Score baseline path
        baseline_scores = {
            "citation_quality": score_citation_quality_baseline(baseline_result),
            "coverage": score_coverage_baseline(baseline_result, gold),
            "usefulness": score_usefulness_baseline(baseline_result, gold),
            "latency_ms": baseline_result["latency_ms"],
        }

        results.append({
            "id": qid,
            "query": query,
            "category": gold.get("category", ""),
            "difficulty": gold.get("difficulty", ""),
            "wiki": wiki_scores,
            "baseline": baseline_scores,
            "wiki_coverage_level": wiki_result.get("coverage", "none"),
            "wiki_hit_count": len(wiki_result.get("wiki_hits", [])),
            "baseline_hit_count": len(baseline_result.get("hits", [])),
        })

    # Aggregate
    n = len(results)
    agg = {
        "wiki": {
            "citation_quality": sum(r["wiki"]["citation_quality"] for r in results) / n,
            "coverage": sum(r["wiki"]["coverage"] for r in results) / n,
            "usefulness": sum(r["wiki"]["usefulness"] for r in results) / n,
            "consistency": sum(r["wiki"]["consistency"] for r in results) / n,
            "latency_avg_ms": sum(wiki_latencies) / n,
            "latency_p95_ms": sorted(wiki_latencies)[int(n * 0.95)] if n > 1 else wiki_latencies[0],
        },
        "baseline": {
            "citation_quality": sum(r["baseline"]["citation_quality"] for r in results) / n,
            "coverage": sum(r["baseline"]["coverage"] for r in results) / n,
            "usefulness": sum(r["baseline"]["usefulness"] for r in results) / n,
            "latency_avg_ms": sum(baseline_latencies) / n,
            "latency_p95_ms": sorted(baseline_latencies)[int(n * 0.95)] if n > 1 else baseline_latencies[0],
        },
    }

    # Compute deltas (wiki - baseline, positive = wiki is better)
    deltas = {}
    for dim in ["citation_quality", "coverage", "usefulness"]:
        deltas[dim] = round(agg["wiki"][dim] - agg["baseline"][dim], 4)
    deltas["latency_ms"] = round(agg["baseline"]["latency_avg_ms"] - agg["wiki"]["latency_avg_ms"], 1)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_questions": n,
        "aggregate": agg,
        "deltas": deltas,
        "per_question": results,
    }
    return report


def save_report(report: dict):
    """Save report to latest.json and append to history.jsonl."""
    os.makedirs(HISTORY_FILE.parent, exist_ok=True)

    with open(LATEST_FILE, "w") as f:
        json.dump(report, f, indent=2)

    # Append summary to history
    summary = {
        "timestamp": report["timestamp"],
        "n": report["n_questions"],
        **{f"wiki_{k}": round(v, 4) for k, v in report["aggregate"]["wiki"].items()},
        **{f"base_{k}": round(v, 4) for k, v in report["aggregate"]["baseline"].items()},
        **{f"delta_{k}": v for k, v in report["deltas"].items()},
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(summary) + "\n")

    # Trim history to 400 entries
    try:
        lines = HISTORY_FILE.read_text().strip().split("\n")
        if len(lines) > 400:
            HISTORY_FILE.write_text("\n".join(lines[-400:]) + "\n")
    except Exception:
        pass


def print_report(report: dict):
    """Print human-readable report."""
    agg = report["aggregate"]
    deltas = report["deltas"]

    print(f"=== Wiki Eval Suite — {report['timestamp'][:19]} ===")
    print(f"Gold questions: {report['n_questions']}")
    print()

    header = f"{'Dimension':<22} {'Wiki':>8} {'Baseline':>10} {'Delta':>8}"
    print(header)
    print("-" * len(header))
    for dim in ["citation_quality", "coverage", "usefulness"]:
        w = agg["wiki"][dim]
        b = agg["baseline"][dim]
        d = deltas[dim]
        marker = "+" if d > 0 else ("-" if d < 0 else " ")
        print(f"{dim:<22} {w:>8.3f} {b:>10.3f} {marker}{abs(d):>7.4f}")

    if "consistency" in agg["wiki"]:
        print(f"{'consistency':<22} {agg['wiki']['consistency']:>8.3f} {'n/a':>10}")

    print(f"{'latency_avg_ms':<22} {agg['wiki']['latency_avg_ms']:>8.1f} {agg['baseline']['latency_avg_ms']:>10.1f} {deltas['latency_ms']:>+8.1f}")
    print(f"{'latency_p95_ms':<22} {agg['wiki']['latency_p95_ms']:>8.1f} {agg['baseline']['latency_p95_ms']:>10.1f}")
    print()

    # Per-question coverage failures
    failures = [r for r in report["per_question"] if r["wiki"]["coverage"] < 1.0]
    if failures:
        print(f"Coverage gaps ({len(failures)}/{report['n_questions']}):")
        for r in failures:
            print(f"  [{r['id']}] {r['query'][:60]} (wiki={r['wiki']['coverage']:.2f}, base={r['baseline']['coverage']:.2f})")
    else:
        print("All gold questions covered by wiki retrieval.")

    # Wiki wins/losses
    wiki_wins = sum(1 for r in report["per_question"]
                    if r["wiki"]["usefulness"] > r["baseline"]["usefulness"])
    ties = sum(1 for r in report["per_question"]
               if r["wiki"]["usefulness"] == r["baseline"]["usefulness"])
    wiki_losses = report["n_questions"] - wiki_wins - ties
    print(f"\nUsefulness: wiki wins {wiki_wins}, ties {ties}, baseline wins {wiki_losses}")


def show_trend(n_days: int = 14):
    """Show trend from history."""
    if not HISTORY_FILE.exists():
        print("No history yet. Run 'wiki_eval.py run' first.")
        return
    lines = HISTORY_FILE.read_text().strip().split("\n")[-n_days:]
    print(f"{'Date':<22} {'W-Cit':>6} {'W-Cov':>6} {'W-Use':>6} {'B-Cov':>6} {'B-Use':>6} {'Δ-Use':>6}")
    print("-" * 76)
    for line in lines:
        d = json.loads(line)
        ts = d.get("timestamp", "?")[:16]
        print(f"{ts:<22} {d.get('wiki_citation_quality', 0):>6.3f} {d.get('wiki_coverage', 0):>6.3f} "
              f"{d.get('wiki_usefulness', 0):>6.3f} {d.get('base_coverage', 0):>6.3f} "
              f"{d.get('base_usefulness', 0):>6.3f} {d.get('delta_usefulness', 0):>+6.4f}")


# ── Programmatic API for pytest ───────────────────────────────────


def evaluate_single(query: str, gold: dict) -> dict:
    """Evaluate a single query. Returns per-question scores dict.

    Useful for pytest parametrized tests.
    """
    wiki_result = _wiki_retrieve(query)
    baseline_result = _baseline_retrieve(query)

    return {
        "wiki": {
            "citation_quality": score_citation_quality(wiki_result),
            "coverage": score_coverage(wiki_result, gold),
            "usefulness": score_usefulness(wiki_result, gold),
            "latency_ms": wiki_result["latency_ms"],
            "hit_count": len(wiki_result.get("wiki_hits", [])),
            "coverage_level": wiki_result.get("coverage", "none"),
        },
        "baseline": {
            "citation_quality": score_citation_quality_baseline(baseline_result),
            "coverage": score_coverage_baseline(baseline_result, gold),
            "usefulness": score_usefulness_baseline(baseline_result, gold),
            "latency_ms": baseline_result["latency_ms"],
            "hit_count": len(baseline_result.get("hits", [])),
        },
    }


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Wiki retrieval evaluation suite")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run full evaluation")
    p_run.add_argument("--json", action="store_true", help="Output JSON instead of report")
    p_run.add_argument("--save", action="store_true", default=True, help="Save results (default)")
    p_run.add_argument("--no-save", action="store_true", help="Skip saving results")

    p_trend = sub.add_parser("trend", help="Show evaluation trend")
    p_trend.add_argument("days", type=int, nargs="?", default=14)

    p_compare = sub.add_parser("compare", help="Side-by-side comparison")

    args = parser.parse_args()

    if args.command == "run":
        report = run_eval()
        if not args.no_save:
            save_report(report)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
    elif args.command == "trend":
        show_trend(args.days)
    elif args.command == "compare":
        report = run_eval()
        print_report(report)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
