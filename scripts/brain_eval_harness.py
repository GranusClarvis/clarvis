#!/usr/bin/env python3
"""
Brain Eval Harness — repeatable benchmark suite for memory quality.

Metrics:
  - P@k (Precision at k=1,3,5): fraction of top-k results containing expected IDs
  - MRR (Mean Reciprocal Rank): 1/rank of first expected result
  - False-link rate: fraction of graph edges pointing to non-existent memory IDs
  - Context usefulness: fraction of top results with distance < threshold

Ground truth: golden QA pairs mapping query → expected memory IDs.
Outputs JSON report + appends to trendline history.
Gates regressions against stored baseline.

Usage:
    python3 brain_eval_harness.py run          # Full benchmark
    python3 brain_eval_harness.py baseline     # Set current as baseline
    python3 brain_eval_harness.py trend        # Show trendline
    python3 brain_eval_harness.py gate         # Check for regressions (exit 1 if fail)
    python3 brain_eval_harness.py golden       # Show golden QA set
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

DATA_DIR = "/home/agent/.openclaw/workspace/data/brain_eval"
RESULTS_FILE = os.path.join(DATA_DIR, "latest.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.jsonl")
BASELINE_FILE = os.path.join(DATA_DIR, "baseline.json")
GOLDEN_QA_FILE = os.path.join(DATA_DIR, "golden_qa.json")
os.makedirs(DATA_DIR, exist_ok=True)

# Distance threshold for "useful" context
USEFUL_DISTANCE = 1.3

# Regression gate thresholds (absolute minimums)
GATE_THRESHOLDS = {
    "p_at_1": 0.40,
    "p_at_3": 0.50,
    "mrr": 0.50,
    "context_usefulness": 0.50,
    "false_link_rate_max": 0.10,  # max allowed
}

# Regression delta: fail if metric drops by more than this vs baseline
REGRESSION_DELTA = 0.10


def _load_golden_qa() -> list[dict]:
    """Load golden QA pairs. Create default set if missing."""
    if os.path.exists(GOLDEN_QA_FILE):
        with open(GOLDEN_QA_FILE) as f:
            return json.load(f)

    # Default golden QA — stable memories unlikely to change
    golden = [
        {
            "query": "Who created Clarvis?",
            "expected_ids": ["clarvis-identity_20260219_030852"],
            "expected_collections": ["clarvis-identity"],
            "description": "Creator identity (Patrick/Inverse)",
        },
        {
            "query": "AGI and consciousness goal",
            "expected_ids": ["AGI/consciousness"],
            "expected_collections": ["clarvis-goals"],
            "description": "Primary AGI goal",
        },
        {
            "query": "session continuity across conversations",
            "expected_ids": ["Session Continuity"],
            "expected_collections": ["clarvis-goals"],
            "description": "Session continuity goal",
        },
        {
            "query": "heartbeat efficiency optimization",
            "expected_ids": ["Heartbeat Efficiency"],
            "expected_collections": ["clarvis-goals"],
            "description": "Heartbeat efficiency goal",
        },
        {
            "query": "self-reflection and self-awareness goal",
            "expected_ids": ["Self-Reflection"],
            "expected_collections": ["clarvis-goals"],
            "description": "Self-reflection goal",
        },
        {
            "query": "prediction outcome feedback loop",
            "expected_ids": ["Feedback Loop"],
            "expected_collections": ["clarvis-goals"],
            "description": "Feedback loop goal",
        },
        {
            "query": "use brain.search not memory_search ClarvisDB faster",
            "expected_ids": ["clarvis-learnings_20260220_133944"],
            "expected_collections": ["clarvis-learnings"],
            "description": "Key learning: use brain.search",
        },
        {
            "query": "autonomy framework act first ask first",
            "expected_ids": ["clarvis-learnings_20260220_134221"],
            "expected_collections": ["clarvis-learnings"],
            "description": "Autonomy framework learning",
        },
        {
            "query": "ClarvisDB is the only brain no external dependency",
            "expected_ids": ["clarvis-learnings_20260220_140034"],
            "expected_collections": ["clarvis-learnings"],
            "description": "Self-sufficiency learning",
        },
        {
            "query": "user criticized not integrating ClarvisDB",
            "expected_ids": ["clarvis-learnings_20260219_102708"],
            "expected_collections": ["clarvis-learnings"],
            "description": "Critical feedback on integration",
        },
        {
            "query": "wire brain.py auto_link cross-collection",
            "expected_ids": ["clarvis-episodes_20260222_003733"],
            "expected_collections": ["clarvis-episodes"],
            "description": "Auto-link wiring episode",
        },
        {
            "query": "build procedural memory system episode",
            "expected_ids": ["clarvis-episodes_20260222_003744"],
            "expected_collections": ["clarvis-episodes"],
            "description": "Procedural memory build episode",
        },
        {
            "query": "fix retrieval hit rate smart_recall wiring",
            "expected_ids": ["clarvis-episodes_20260222_005640"],
            "expected_collections": ["clarvis-episodes"],
            "description": "Retrieval fix episode",
        },
        {
            "query": "goal progress tracker build episode",
            "expected_ids": ["clarvis-episodes_20260222_013639"],
            "expected_collections": ["clarvis-episodes"],
            "description": "Goal tracker build episode",
        },
        {
            "query": "fix cron_autonomous.sh procedure",
            "expected_ids": ["proc_fix_cron_autonomous_sh"],
            "expected_collections": ["clarvis-procedures"],
            "description": "Cron fix procedure",
        },
        {
            "query": "ClarvisDB v1.0 complete 89 memories ONNX",
            "expected_ids": ["clarvis-learnings_20260220_140345"],
            "expected_collections": ["clarvis-learnings"],
            "description": "ClarvisDB v1.0 milestone",
        },
        {
            "query": "massive cognitive architecture build day 27 commits",
            "expected_ids": ["clarvis-memories_20260221_210039"],
            "expected_collections": ["clarvis-memories"],
            "description": "Build day memory",
        },
        {
            "query": "meta-cognition awareness level changed",
            "expected_ids": [
                "bridge_clarvis-identity_20260221_1032_autonomous-learning_20260222_0"
            ],
            "expected_collections": ["clarvis-identity"],
            "description": "Meta-cognition awareness bridge",
        },
        {
            "query": "episodic memory system ACT-R build",
            "expected_ids": ["proc_episodic_memory_system"],
            "expected_collections": ["clarvis-procedures"],
            "description": "Episodic memory procedure",
        },
        {
            "query": "self-improvement from prediction outcomes procedure",
            "expected_ids": ["proc_self_improvement_from_prediction_outcomes"],
            "expected_collections": ["clarvis-procedures"],
            "description": "Self-improvement procedure",
        },
    ]

    with open(GOLDEN_QA_FILE, "w") as f:
        json.dump(golden, f, indent=2)
    return golden


def compute_p_at_k(result_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Precision at k: 1 if any expected ID in top-k results, else 0."""
    top_k = set(result_ids[:k])
    return 1.0 if top_k & set(expected_ids) else 0.0


def compute_mrr(result_ids: list[str], expected_ids: list[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of first expected ID found."""
    expected_set = set(expected_ids)
    for i, rid in enumerate(result_ids):
        if rid in expected_set:
            return 1.0 / (i + 1)
    return 0.0


def compute_collection_hit(
    results: list[dict], expected_collections: list[str], k: int
) -> float:
    """Check if any of top-k results are from expected collections."""
    for r in results[:k]:
        if r.get("collection") in expected_collections:
            return 1.0
    return 0.0


def compute_false_link_rate(brain_obj) -> dict:
    """Check what fraction of graph edges reference non-existent memory IDs."""
    edges = brain_obj.graph.get("edges", [])
    if not edges:
        return {"false_link_rate": 0.0, "total_edges": 0, "broken_edges": 0}

    # Build set of all memory IDs across all collections
    all_ids = set()
    for coll_name, coll in brain_obj.collections.items():
        try:
            data = coll.get(limit=10000, include=[])
            all_ids.update(data["ids"])
        except Exception:
            pass

    # Also include graph node keys
    node_keys = set(brain_obj.graph.get("nodes", {}).keys())
    valid_ids = all_ids | node_keys

    broken = 0
    sampled = min(len(edges), 2000)  # Sample for speed
    import random

    sample = random.sample(edges, sampled) if len(edges) > sampled else edges

    for e in sample:
        from_id = e.get("from", "")
        to_id = e.get("to", "")
        if from_id and from_id not in valid_ids:
            broken += 1
        elif to_id and to_id not in valid_ids:
            broken += 1

    return {
        "false_link_rate": round(broken / sampled, 4) if sampled > 0 else 0.0,
        "total_edges": len(edges),
        "sampled_edges": sampled,
        "broken_edges": broken,
    }


def run_benchmark(verbose: bool = True) -> dict:
    """Run full benchmark suite. Returns metrics dict."""
    from brain import brain

    golden = _load_golden_qa()
    t0 = time.time()

    # Per-query metrics
    query_results = []
    p1_scores = []
    p3_scores = []
    p5_scores = []
    mrr_scores = []
    coll_hit_scores = []
    context_useful_scores = []

    for qa in golden:
        query = qa["query"]
        expected_ids = qa["expected_ids"]
        expected_colls = qa.get("expected_collections", [])

        results = brain.recall(query, n=5)
        result_ids = [r["id"] for r in results]
        result_distances = [r.get("distance") for r in results]

        # P@k
        p1 = compute_p_at_k(result_ids, expected_ids, 1)
        p3 = compute_p_at_k(result_ids, expected_ids, 3)
        p5 = compute_p_at_k(result_ids, expected_ids, 5)

        # MRR
        mrr = compute_mrr(result_ids, expected_ids)

        # Collection hit at k=3
        coll_hit = compute_collection_hit(results, expected_colls, 3)

        # Context usefulness: top result distance < threshold
        top_dist = result_distances[0] if result_distances else None
        ctx_useful = 1.0 if top_dist is not None and top_dist < USEFUL_DISTANCE else 0.0

        p1_scores.append(p1)
        p3_scores.append(p3)
        p5_scores.append(p5)
        mrr_scores.append(mrr)
        coll_hit_scores.append(coll_hit)
        context_useful_scores.append(ctx_useful)

        qr = {
            "query": query,
            "description": qa.get("description", ""),
            "expected_ids": expected_ids,
            "result_ids": result_ids[:5],
            "result_distances": [round(d, 4) if d else None for d in result_distances[:5]],
            "p_at_1": p1,
            "p_at_3": p3,
            "p_at_5": p5,
            "mrr": mrr,
            "collection_hit": coll_hit,
            "context_useful": ctx_useful,
            "hit": p3 > 0,
        }
        query_results.append(qr)

        if verbose:
            status = "HIT" if p3 > 0 else "MISS"
            print(f"  [{status}] {qa.get('description', query)[:55]:<55}  "
                  f"P@1={p1:.0f} P@3={p3:.0f} MRR={mrr:.2f} d={top_dist:.3f}" if top_dist else
                  f"  [{status}] {qa.get('description', query)[:55]:<55}  "
                  f"P@1={p1:.0f} P@3={p3:.0f} MRR={mrr:.2f} d=N/A")

    n = len(golden)
    elapsed = time.time() - t0

    # Aggregate metrics
    metrics = {
        "p_at_1": round(sum(p1_scores) / n, 4),
        "p_at_3": round(sum(p3_scores) / n, 4),
        "p_at_5": round(sum(p5_scores) / n, 4),
        "mrr": round(sum(mrr_scores) / n, 4),
        "collection_hit_at_3": round(sum(coll_hit_scores) / n, 4),
        "context_usefulness": round(sum(context_useful_scores) / n, 4),
    }

    # False-link rate
    if verbose:
        print("\n  Checking graph edge integrity...")
    fl = compute_false_link_rate(brain)
    metrics["false_link_rate"] = fl["false_link_rate"]
    metrics["graph_edges_total"] = fl["total_edges"]
    metrics["graph_edges_broken"] = fl["broken_edges"]

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "golden_queries": n,
        "elapsed_seconds": round(elapsed, 2),
        "metrics": metrics,
        "query_results": query_results,
    }

    # Save latest
    with open(RESULTS_FILE, "w") as f:
        json.dump(report, f, indent=2)

    # Append to history
    history_entry = {
        "timestamp": report["timestamp"],
        **metrics,
        "golden_queries": n,
        "elapsed_s": report["elapsed_seconds"],
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(history_entry) + "\n")

    return report


def set_baseline():
    """Set current results as the regression baseline."""
    if not os.path.exists(RESULTS_FILE):
        print("No results yet. Run 'brain_eval_harness.py run' first.")
        return

    with open(RESULTS_FILE) as f:
        results = json.load(f)

    baseline = {
        "set_at": datetime.now(timezone.utc).isoformat(),
        "from_run": results["timestamp"],
        "metrics": results["metrics"],
    }

    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"Baseline set from run at {results['timestamp']}")
    _print_metrics(results["metrics"])


def check_gate() -> bool:
    """Check for regressions. Returns True if pass, False if fail."""
    if not os.path.exists(RESULTS_FILE):
        print("GATE: No results. Run 'brain_eval_harness.py run' first.")
        return False

    with open(RESULTS_FILE) as f:
        results = json.load(f)

    metrics = results["metrics"]
    failures = []

    # Absolute threshold gates
    for metric, threshold in GATE_THRESHOLDS.items():
        if metric == "false_link_rate_max":
            val = metrics.get("false_link_rate", 0)
            if val > threshold:
                failures.append(
                    f"false_link_rate={val:.3f} > max={threshold:.3f}"
                )
        else:
            val = metrics.get(metric, 0)
            if val < threshold:
                failures.append(f"{metric}={val:.3f} < min={threshold:.3f}")

    # Regression delta check vs baseline
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE) as f:
            baseline = json.load(f)

        bl_metrics = baseline["metrics"]
        for metric in ["p_at_1", "p_at_3", "p_at_5", "mrr", "context_usefulness"]:
            bl_val = bl_metrics.get(metric, 0)
            cur_val = metrics.get(metric, 0)
            delta = bl_val - cur_val
            if delta > REGRESSION_DELTA:
                failures.append(
                    f"REGRESSION {metric}: {cur_val:.3f} (was {bl_val:.3f}, "
                    f"drop={delta:.3f} > {REGRESSION_DELTA:.3f})"
                )

        # False-link rate regression
        bl_fl = bl_metrics.get("false_link_rate", 0)
        cur_fl = metrics.get("false_link_rate", 0)
        if cur_fl - bl_fl > 0.05:
            failures.append(
                f"REGRESSION false_link_rate: {cur_fl:.3f} (was {bl_fl:.3f})"
            )

    if failures:
        print("GATE: FAIL")
        for f in failures:
            print(f"  - {f}")
        return False

    print("GATE: PASS")
    _print_metrics(metrics)
    return True


def show_trend():
    """Show trendline from history."""
    if not os.path.exists(HISTORY_FILE):
        print("No history yet. Run 'brain_eval_harness.py run' first.")
        return

    entries = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not entries:
        print("Empty history.")
        return

    print(f"=== Brain Eval Trendline ({len(entries)} runs) ===")
    print(f"{'Date':<22} {'P@1':>5} {'P@3':>5} {'P@5':>5} {'MRR':>5} "
          f"{'CtxU':>5} {'FLR':>5} {'Time':>6}")
    print("-" * 78)

    for e in entries[-20:]:  # Last 20
        ts = e.get("timestamp", "")[:19]
        print(f"{ts:<22} "
              f"{e.get('p_at_1', 0):>5.2f} "
              f"{e.get('p_at_3', 0):>5.2f} "
              f"{e.get('p_at_5', 0):>5.2f} "
              f"{e.get('mrr', 0):>5.2f} "
              f"{e.get('context_usefulness', 0):>5.2f} "
              f"{e.get('false_link_rate', 0):>5.3f} "
              f"{e.get('elapsed_s', 0):>5.1f}s")

    # Show delta if >1 entry
    if len(entries) >= 2:
        prev = entries[-2]
        curr = entries[-1]
        print("\nDelta (latest vs previous):")
        for m in ["p_at_1", "p_at_3", "mrr", "context_usefulness", "false_link_rate"]:
            d = (curr.get(m, 0) or 0) - (prev.get(m, 0) or 0)
            arrow = "+" if d >= 0 else ""
            good = (d >= 0) if m != "false_link_rate" else (d <= 0)
            indicator = "OK" if good else "WARN"
            print(f"  {m}: {arrow}{d:.3f} [{indicator}]")


def show_golden():
    """Show the golden QA dataset."""
    golden = _load_golden_qa()
    print(f"=== Golden QA ({len(golden)} queries) ===\n")
    for i, qa in enumerate(golden, 1):
        print(f"{i:2d}. {qa['description']}")
        print(f"    Query: \"{qa['query']}\"")
        print(f"    Expected: {qa['expected_ids']}")
        print(f"    Collections: {qa.get('expected_collections', [])}")
        print()


def _print_metrics(metrics: dict):
    """Pretty-print metrics."""
    print(f"  P@1={metrics.get('p_at_1', 0):.2f}  "
          f"P@3={metrics.get('p_at_3', 0):.2f}  "
          f"P@5={metrics.get('p_at_5', 0):.2f}  "
          f"MRR={metrics.get('mrr', 0):.2f}")
    print(f"  Collection-hit@3={metrics.get('collection_hit_at_3', 0):.2f}  "
          f"Context-useful={metrics.get('context_usefulness', 0):.2f}")
    print(f"  False-link-rate={metrics.get('false_link_rate', 0):.3f} "
          f"({metrics.get('graph_edges_broken', 0)}/{metrics.get('graph_edges_total', 0)} edges)")


# === CLI ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Brain Eval Harness — repeatable memory quality benchmarks")
        print("Usage:")
        print("  run       — Run full benchmark (P@k, MRR, false-link, context usefulness)")
        print("  baseline  — Set current results as regression baseline")
        print("  gate      — Check for regressions (exit 1 if fail)")
        print("  trend     — Show trendline history")
        print("  golden    — Show golden QA dataset")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "run":
        print("=== Brain Eval Harness ===\n")
        report = run_benchmark(verbose=True)
        m = report["metrics"]
        print(f"\n=== Results ({report['golden_queries']} queries, {report['elapsed_seconds']:.1f}s) ===")
        _print_metrics(m)

        # Misses summary
        misses = [q for q in report["query_results"] if not q["hit"]]
        if misses:
            print(f"\nMisses ({len(misses)}):")
            for q in misses:
                print(f"  - {q['description']}: expected {q['expected_ids'][0]}, "
                      f"got {q['result_ids'][0] if q['result_ids'] else 'EMPTY'}")

        # Auto-gate
        print()
        passed = check_gate()
        sys.exit(0 if passed else 1)

    elif cmd == "baseline":
        set_baseline()

    elif cmd == "gate":
        passed = check_gate()
        sys.exit(0 if passed else 1)

    elif cmd == "trend":
        show_trend()

    elif cmd == "golden":
        show_golden()

    elif cmd == "latency":
        print("=== Brain Search Latency Benchmark ===\n")
        from brain import brain
        brain.stats()  # warm up ONNX + collections
        queries = [
            ("routed-narrow", "heartbeat efficiency"),
            ("routed-wide", "brain architecture"),
            ("cached-repeat", "brain architecture"),
            ("identity", "Who created Clarvis?"),
            ("goal-search", "AGI consciousness goal"),
        ]
        timings = []
        for label, q in queries:
            t0 = time.monotonic()
            results = brain.recall(q, n=5)
            ms = (time.monotonic() - t0) * 1000
            timings.append({"label": label, "query": q, "ms": round(ms, 1), "results": len(results)})
            print(f"  {label:20s}: {ms:8.1f}ms  ({len(results)} results)")
        avg = sum(t["ms"] for t in timings) / len(timings)
        p95 = sorted(t["ms"] for t in timings)[int(0.95 * len(timings))]
        summary = {"avg_ms": round(avg, 1), "p95_ms": round(p95, 1), "queries": timings}
        print(f"\n  Average: {avg:.1f}ms   P95: {p95:.1f}ms")
        # Append to history
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "latency_benchmark",
            "avg_ms": summary["avg_ms"],
            "p95_ms": summary["p95_ms"],
            "detail": timings,
        }
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"\n  Recorded to {HISTORY_FILE}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
