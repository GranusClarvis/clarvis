#!/usr/bin/env python3
"""Matched-pair benchmark: brain-only vs brain+wiki retrieval on recent tasks.

Runs each task through two retrieval routes:
  1. Brain-only: clarvis.brain.recall()
  2. Brain+wiki: wiki_retrieval.wiki_retrieve()

Measures latency, result count, unique terms, distance stats.
Saves results to data/audit/wiki_vs_brain_bench.json.

Usage:
    python3 scripts/metrics/wiki_vs_brain_bench.py [--n 20] [--verbose]
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
OUTPUT_FILE = WORKSPACE / "data" / "audit" / "wiki_vs_brain_bench.json"
PREDICTIONS_FILE = WORKSPACE / "data" / "calibration" / "predictions.jsonl"
QUEUE_FILE = WORKSPACE / "memory" / "evolution" / "QUEUE.md"


def _collect_recent_tasks(n: int = 20) -> list[dict]:
    """Collect recent task descriptions from predictions and QUEUE.md."""
    tasks = []
    seen = set()

    if PREDICTIONS_FILE.exists():
        with open(PREDICTIONS_FILE) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    event = d.get("event", "")
                    if event and d.get("outcome") is not None and event not in seen:
                        clean = re.sub(r'^_+', '', event)
                        clean = re.sub(r'_+', ' ', clean).strip()[:100]
                        if len(clean) > 10:
                            domain = d.get("domain", _classify_domain(clean))
                            tasks.append({"task": clean, "domain": domain, "source": "prediction"})
                            seen.add(event)
                except (json.JSONDecodeError, KeyError):
                    pass

    if QUEUE_FILE.exists():
        with open(QUEUE_FILE) as f:
            for line in f:
                m = re.search(r'\[x\].*\*\*\[([A-Z0-9_]+)\]\*\*\s*(.*?)(?:\(|$)', line)
                if m:
                    tag = m.group(1)
                    desc = m.group(2).strip()
                    key = tag
                    if key not in seen:
                        text = f"{tag} {desc}" if desc else tag
                        text = text.replace('_', ' ').strip()[:100]
                        domain = _classify_domain(text)
                        tasks.append({"task": text, "domain": domain, "source": "queue"})
                        seen.add(key)

    tasks.reverse()
    return tasks[:n]


def _classify_domain(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["fix", "bug", "patch", "debug"]):
        return "bug_fix"
    if any(w in t for w in ["research", "study", "analysis", "investigate"]):
        return "research"
    if any(w in t for w in ["refactor", "clean", "optimize", "improve"]):
        return "optimization"
    if any(w in t for w in ["test", "bench", "eval", "audit"]):
        return "analysis"
    if any(w in t for w in ["wire", "integrat", "connect", "bridge"]):
        return "integration"
    if any(w in t for w in ["build", "create", "implement", "add"]):
        return "new_capability"
    return "general"


def _run_brain_only(query: str, n_results: int = 10) -> dict:
    """Run brain-only retrieval and measure."""
    from clarvis.brain import brain

    t0 = time.monotonic()
    results = brain.recall(query, n=n_results, caller="wiki_bench_brain")
    elapsed_ms = (time.monotonic() - t0) * 1000

    distances = [r.get("distance", 999) for r in results]
    docs = [r.get("document", "") for r in results]
    unique_terms = len(set(" ".join(docs).lower().split()))
    collections = list(set(r.get("collection", "") for r in results))

    return {
        "route": "brain_only",
        "latency_ms": round(elapsed_ms, 1),
        "result_count": len(results),
        "avg_distance": round(sum(distances) / len(distances), 4) if distances else None,
        "min_distance": round(min(distances), 4) if distances else None,
        "max_distance": round(max(distances), 4) if distances else None,
        "unique_terms": unique_terms,
        "collections_hit": collections,
    }


def _run_brain_plus_wiki(query: str) -> dict:
    """Run brain+wiki retrieval and measure."""
    try:
        from clarvis._script_loader import load as _load_script
        wiki_mod = _load_script("wiki_retrieval", "wiki")
        wiki_retrieve = wiki_mod.wiki_retrieve
    except Exception as e:
        return {
            "route": "brain_plus_wiki",
            "error": str(e),
            "latency_ms": 0,
            "result_count": 0,
        }

    t0 = time.monotonic()
    result = wiki_retrieve(query, max_pages=5, expand_graph=True, fallback_broad=True)
    elapsed_ms = (time.monotonic() - t0) * 1000

    wiki_hits = result.get("wiki_hits", [])
    graph_neighbors = result.get("graph_neighbors", [])
    broad_hits = result.get("broad_hits", [])
    coverage = result.get("coverage", "none")

    wiki_distances = [h.get("distance", 999) for h in wiki_hits if isinstance(h.get("distance"), (int, float))]
    broad_distances = [h.get("distance", 999) for h in broad_hits if isinstance(h.get("distance"), (int, float))]

    all_text_parts = []
    for h in wiki_hits:
        all_text_parts.append(h.get("content", h.get("title", "")))
    for h in broad_hits:
        all_text_parts.append(h.get("document", ""))
    unique_terms = len(set(" ".join(all_text_parts).lower().split()))

    return {
        "route": "brain_plus_wiki",
        "latency_ms": round(elapsed_ms, 1),
        "coverage": coverage,
        "wiki_hit_count": len(wiki_hits),
        "graph_neighbor_count": len(graph_neighbors),
        "broad_fallback_count": len(broad_hits),
        "result_count": len(wiki_hits) + len(broad_hits),
        "wiki_avg_distance": round(sum(wiki_distances) / len(wiki_distances), 4) if wiki_distances else None,
        "wiki_min_distance": round(min(wiki_distances), 4) if wiki_distances else None,
        "broad_avg_distance": round(sum(broad_distances) / len(broad_distances), 4) if broad_distances else None,
        "unique_terms": unique_terms,
    }


def run_benchmark(n_tasks: int = 20, verbose: bool = False) -> dict:
    """Run matched-pair benchmark on n recent tasks."""
    tasks = _collect_recent_tasks(n_tasks)
    if len(tasks) < n_tasks:
        print(f"Warning: only found {len(tasks)} tasks (requested {n_tasks})", file=sys.stderr)

    results = []
    domain_stats = {}

    for i, task_info in enumerate(tasks):
        query = task_info["task"]
        domain = task_info["domain"]

        if verbose:
            print(f"[{i+1}/{len(tasks)}] {domain}: {query[:60]}...", file=sys.stderr)

        brain_result = _run_brain_only(query)
        wiki_result = _run_brain_plus_wiki(query)

        brain_terms = brain_result.get("unique_terms", 0)
        wiki_terms = wiki_result.get("unique_terms", 0)
        term_delta = wiki_terms - brain_terms
        latency_delta = wiki_result.get("latency_ms", 0) - brain_result.get("latency_ms", 0)

        pair = {
            "task": query,
            "domain": domain,
            "source": task_info["source"],
            "brain_only": brain_result,
            "brain_plus_wiki": wiki_result,
            "delta": {
                "unique_terms": term_delta,
                "latency_ms": round(latency_delta, 1),
                "wiki_added_value": wiki_result.get("wiki_hit_count", 0) > 0,
                "coverage": wiki_result.get("coverage", "none"),
            },
        }
        results.append(pair)

        if domain not in domain_stats:
            domain_stats[domain] = {"count": 0, "wiki_value_count": 0, "term_deltas": [], "latency_deltas": []}
        domain_stats[domain]["count"] += 1
        if wiki_result.get("wiki_hit_count", 0) > 0:
            domain_stats[domain]["wiki_value_count"] += 1
        domain_stats[domain]["term_deltas"].append(term_delta)
        domain_stats[domain]["latency_deltas"].append(latency_delta)

    total = len(results)
    wiki_value_count = sum(1 for r in results if r["delta"]["wiki_added_value"])
    avg_term_delta = sum(r["delta"]["unique_terms"] for r in results) / total if total else 0
    avg_latency_delta = sum(r["delta"]["latency_ms"] for r in results) / total if total else 0

    coverage_dist = {}
    for r in results:
        cov = r["delta"]["coverage"]
        coverage_dist[cov] = coverage_dist.get(cov, 0) + 1

    summary_by_domain = {}
    for domain, stats in domain_stats.items():
        summary_by_domain[domain] = {
            "count": stats["count"],
            "wiki_value_rate": round(stats["wiki_value_count"] / stats["count"], 3) if stats["count"] else 0,
            "avg_term_delta": round(sum(stats["term_deltas"]) / len(stats["term_deltas"]), 1),
            "avg_latency_delta_ms": round(sum(stats["latency_deltas"]) / len(stats["latency_deltas"]), 1),
        }

    benchmark = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_count": total,
        "summary": {
            "wiki_value_rate": round(wiki_value_count / total, 3) if total else 0,
            "wiki_value_count": wiki_value_count,
            "avg_term_delta": round(avg_term_delta, 1),
            "avg_latency_delta_ms": round(avg_latency_delta, 1),
            "coverage_distribution": coverage_dist,
        },
        "by_domain": summary_by_domain,
        "recommendation": _generate_recommendation(wiki_value_count, total, avg_term_delta, avg_latency_delta),
        "pairs": results,
    }

    return benchmark


def _generate_recommendation(wiki_value_count: int, total: int, avg_term_delta: float, avg_latency_delta: float) -> str:
    rate = wiki_value_count / total if total else 0
    if rate >= 0.5 and avg_term_delta > 10:
        return "PROMOTE: Wiki adds significant value. Move wiki_retrieval from shadow to active."
    elif rate >= 0.2 and avg_term_delta > 0:
        return "GROWING: Wiki shows some value but coverage is sparse. Keep shadow mode, grow wiki pages."
    elif rate > 0 and avg_latency_delta < 200:
        return "MARGINAL: Minimal wiki value with acceptable latency cost. Keep shadow mode."
    else:
        return "NO_VALUE: Wiki adds no value yet. Keep shadow mode. Grow wiki coverage before re-benchmarking."


def main():
    parser = argparse.ArgumentParser(description="Brain vs Brain+Wiki benchmark")
    parser.add_argument("--n", type=int, default=20, help="Number of tasks to benchmark")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print(f"Running matched-pair benchmark on {args.n} recent tasks...", file=sys.stderr)
    benchmark = run_benchmark(n_tasks=args.n, verbose=args.verbose)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(benchmark, f, indent=2)

    s = benchmark["summary"]
    print(f"\n=== Brain vs Brain+Wiki Benchmark ===")
    print(f"Tasks: {benchmark['task_count']}")
    print(f"Wiki value rate: {s['wiki_value_rate']:.0%} ({s['wiki_value_count']}/{benchmark['task_count']})")
    print(f"Avg term delta: {s['avg_term_delta']:+.1f}")
    print(f"Avg latency delta: {s['avg_latency_delta_ms']:+.1f}ms")
    print(f"Coverage: {s['coverage_distribution']}")
    print(f"\nBy domain:")
    for domain, stats in benchmark.get("by_domain", {}).items():
        print(f"  {domain}: wiki={stats['wiki_value_rate']:.0%}, terms={stats['avg_term_delta']:+.1f}, latency={stats['avg_latency_delta_ms']:+.1f}ms (n={stats['count']})")
    print(f"\nRecommendation: {benchmark['recommendation']}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
