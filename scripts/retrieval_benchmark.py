#!/usr/bin/env python3
"""
Retrieval Benchmark — Ground-truth evaluation of memory retrieval quality.

20 known query→expected-result pairs derived from actual memory content.
Measures precision@3 and recall per query, tracks trends over time.
Replaces heuristic distance thresholds in retrieval_quality.py with real ground truth.

Run nightly via cron_evening.sh. Results appended to data/retrieval_benchmark/history.jsonl.

Usage:
    python3 retrieval_benchmark.py              # Run benchmark, print report
    python3 retrieval_benchmark.py trend         # Show precision/recall trend over time
    python3 retrieval_benchmark.py trend 14      # Show last 14 days
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain, GOALS, PROCEDURES, CONTEXT, LEARNINGS, MEMORIES, \
    IDENTITY, PREFERENCES, INFRASTRUCTURE

try:
    from retrieval_experiment import smart_recall
except ImportError:
    smart_recall = None

# === DATA PATHS ===
DATA_DIR = "/home/agent/.openclaw/workspace/data/retrieval_benchmark"
HISTORY_FILE = os.path.join(DATA_DIR, "history.jsonl")
LATEST_FILE = os.path.join(DATA_DIR, "latest.json")
os.makedirs(DATA_DIR, exist_ok=True)

# Max history entries (one per nightly run, ~1 year)
MAX_HISTORY = 400


# === GROUND-TRUTH BENCHMARK PAIRS ===
# Each pair: query, expected substring(s) that MUST appear in a correct result,
# and the collection(s) where the result should come from.
#
# "expected_substrings" = list of substrings; a result is a HIT if ANY substring
# matches (case-insensitive) in the document text. This is ground truth — not
# heuristic distance.

BENCHMARK_PAIRS = [
    # --- Identity & self-knowledge ---
    {
        "id": "B01",
        "query": "Who created Clarvis?",
        "expected_substrings": ["patrick", "inverse", "granus"],
        "expected_collections": [IDENTITY],
        "category": "identity",
    },
    {
        "id": "B02",
        "query": "What capabilities does Clarvis have?",
        "expected_substrings": ["capability", "git", "web search", "code"],
        "expected_collections": [IDENTITY],
        "category": "identity",
    },
    # --- Goals ---
    {
        "id": "B03",
        "query": "What are my current goals?",
        "expected_substrings": ["goal", "clarvisdb", "agi", "consciousness", "north star"],
        "expected_collections": [GOALS],
        "category": "goals",
    },
    {
        "id": "B04",
        "query": "Progress on session continuity",
        "expected_substrings": ["session continuity"],
        "expected_collections": [GOALS],
        "category": "goals",
    },
    {
        "id": "B05",
        "query": "AGI and consciousness goal progress",
        "expected_substrings": ["agi", "consciousness"],
        "expected_collections": [GOALS, LEARNINGS, MEMORIES],
        "category": "goals",
    },
    # --- Infrastructure ---
    {
        "id": "B06",
        "query": "What is the gateway address?",
        "expected_substrings": ["127.0.0.1", "18789", "gateway"],
        "expected_collections": [INFRASTRUCTURE],
        "category": "infrastructure",
    },
    {
        "id": "B07",
        "query": "ClarvisDB architecture and components",
        "expected_substrings": ["brain.py", "chromadb", "clarvisdb"],
        "expected_collections": [INFRASTRUCTURE, LEARNINGS],
        "category": "infrastructure",
    },
    {
        "id": "B08",
        "query": "Security configuration and access control",
        "expected_substrings": ["security", "loopback", "tailscale", "auth"],
        "expected_collections": [INFRASTRUCTURE],
        "category": "infrastructure",
    },
    # --- Learnings & knowledge ---
    {
        "id": "B09",
        "query": "How does the attention mechanism work?",
        "expected_substrings": ["attention", "spotlight", "gwt", "salience", "global workspace"],
        "expected_collections": [LEARNINGS, MEMORIES],
        "category": "knowledge",
    },
    {
        "id": "B10",
        "query": "What did I learn about using brain.search instead of memory_search?",
        "expected_substrings": ["brain.search", "memory_search", "clarvisdb"],
        "expected_collections": [LEARNINGS],
        "category": "knowledge",
    },
    {
        "id": "B11",
        "query": "Autonomy framework and when to act vs ask",
        "expected_substrings": ["autonomy", "act first", "ask first"],
        "expected_collections": [LEARNINGS],
        "category": "knowledge",
    },
    {
        "id": "B12",
        "query": "Consciousness metrics and phi measurement",
        "expected_substrings": ["phi", "consciousness", "iit", "metric"],
        "expected_collections": [LEARNINGS, MEMORIES],
        "category": "knowledge",
    },
    {
        "id": "B13",
        "query": "Lessons about integrating ClarvisDB",
        "expected_substrings": ["clarvisdb", "integrate", "wire", "built but didn't"],
        "expected_collections": [LEARNINGS],
        "category": "knowledge",
    },
    # --- Procedures ---
    {
        "id": "B14",
        "query": "How to fix cron_autonomous",
        "expected_substrings": ["cron_autonomous", "fix"],
        "expected_collections": [PROCEDURES, LEARNINGS],
        "category": "procedures",
    },
    {
        "id": "B15",
        "query": "Procedure for reasoning chain outcomes",
        "expected_substrings": ["reasoning chain", "outcome"],
        "expected_collections": [PROCEDURES, LEARNINGS],
        "category": "procedures",
    },
    # --- Preferences ---
    {
        "id": "B16",
        "query": "Communication style preferences",
        "expected_substrings": ["direct", "no fluff", "communication"],
        "expected_collections": [PREFERENCES, MEMORIES],
        "category": "preferences",
    },
    {
        "id": "B17",
        "query": "What timezone should I use?",
        "expected_substrings": ["cet", "timezone"],
        "expected_collections": [PREFERENCES],
        "category": "preferences",
    },
    # --- Context & episodic ---
    {
        "id": "B18",
        "query": "What happened in the last heartbeat?",
        "expected_substrings": ["heartbeat", "brain healthy", "verified"],
        "expected_collections": [CONTEXT, MEMORIES],
        "category": "context",
    },
    # --- Autonomous learning ---
    {
        "id": "B19",
        "query": "Success rate across sessions",
        "expected_substrings": ["success rate", "sessions"],
        "expected_collections": [LEARNINGS, MEMORIES],
        "category": "meta",
    },
    {
        "id": "B20",
        "query": "What recurring themes appear in my sessions?",
        "expected_substrings": ["theme", "recurring", "session"],
        "expected_collections": [LEARNINGS, MEMORIES],
        "category": "meta",
    },
]


def check_hit(result: dict, pair: dict) -> bool:
    """Check if a single result is a ground-truth hit for this benchmark pair."""
    doc = result.get("document", "").lower()
    for sub in pair["expected_substrings"]:
        if sub.lower() in doc:
            return True
    return False


def run_benchmark(use_smart=True, k=3) -> dict:
    """
    Run all 20 benchmark queries. Measure precision@k and recall.

    precision@k = (# of hits in top-k results) / k
    recall = 1 if at least one hit in top-k, else 0

    Returns dict with per-query and aggregate metrics.
    """
    recall_fn = smart_recall if (use_smart and smart_recall) else brain.recall
    method_name = "smart_recall" if (use_smart and smart_recall) else "brain.recall"

    query_results = []
    total_precision = 0.0
    total_recall = 0
    category_stats = {}

    for pair in BENCHMARK_PAIRS:
        query = pair["query"]
        bid = pair["id"]
        category = pair["category"]

        # Run retrieval
        if recall_fn == brain.recall:
            results = recall_fn(query, n=k, caller="benchmark")
        else:
            results = recall_fn(query, n=k, caller="benchmark")

        # Score each result
        hits_in_k = 0
        result_details = []
        for i, r in enumerate(results[:k]):
            is_hit = check_hit(r, pair)
            if is_hit:
                hits_in_k += 1
            result_details.append({
                "rank": i + 1,
                "hit": is_hit,
                "collection": r.get("collection"),
                "distance": round(r.get("distance", 999), 4),
                "text_preview": r.get("document", "")[:80],
            })

        precision_at_k = hits_in_k / k if k > 0 else 0
        recall_hit = 1 if hits_in_k > 0 else 0

        total_precision += precision_at_k
        total_recall += recall_hit

        # Category tracking
        if category not in category_stats:
            category_stats[category] = {"precision_sum": 0.0, "recall_sum": 0, "count": 0}
        category_stats[category]["precision_sum"] += precision_at_k
        category_stats[category]["recall_sum"] += recall_hit
        category_stats[category]["count"] += 1

        query_results.append({
            "id": bid,
            "query": query,
            "category": category,
            "precision_at_k": round(precision_at_k, 3),
            "recall": recall_hit,
            "hits_in_k": hits_in_k,
            "results": result_details,
        })

    n = len(BENCHMARK_PAIRS)
    avg_precision = round(total_precision / n, 4) if n > 0 else 0
    avg_recall = round(total_recall / n, 4) if n > 0 else 0

    # Per-category aggregates
    category_report = {}
    for cat, stats in category_stats.items():
        c = stats["count"]
        category_report[cat] = {
            "count": c,
            "avg_precision_at_k": round(stats["precision_sum"] / c, 3) if c > 0 else 0,
            "avg_recall": round(stats["recall_sum"] / c, 3) if c > 0 else 0,
        }

    # Failed queries (recall=0, i.e. no hit in top-k)
    failures = [q for q in query_results if q["recall"] == 0]

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": method_name,
        "k": k,
        "num_queries": n,
        "avg_precision_at_k": avg_precision,
        "avg_recall": avg_recall,
        "total_hits": total_recall,
        "total_misses": n - total_recall,
        "by_category": category_report,
        "failures": [{"id": f["id"], "query": f["query"], "category": f["category"]} for f in failures],
        "details": query_results,
    }

    return report


def save_report(report: dict):
    """Save report to latest.json and append summary to history.jsonl."""
    # Save full latest report
    with open(LATEST_FILE, "w") as f:
        json.dump(report, f, indent=2)

    # Append summary line to history (for trend tracking)
    summary = {
        "timestamp": report["timestamp"],
        "method": report["method"],
        "k": report["k"],
        "avg_precision_at_k": report["avg_precision_at_k"],
        "avg_recall": report["avg_recall"],
        "total_hits": report["total_hits"],
        "total_misses": report["total_misses"],
        "by_category": report["by_category"],
        "failure_ids": [f["id"] for f in report["failures"]],
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(summary) + "\n")

    # Truncate history if too long
    _maybe_truncate_history()


def _maybe_truncate_history():
    """Keep history bounded."""
    if not os.path.exists(HISTORY_FILE):
        return
    try:
        with open(HISTORY_FILE, "r") as f:
            lines = f.readlines()
        if len(lines) > MAX_HISTORY:
            keep = lines[len(lines) - MAX_HISTORY:]
            with open(HISTORY_FILE, "w") as f:
                f.writelines(keep)
    except Exception:
        pass


def load_history() -> list:
    """Load history entries from JSONL."""
    if not os.path.exists(HISTORY_FILE):
        return []
    entries = []
    with open(HISTORY_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def show_trend(days: int = 30):
    """Show precision/recall trend over recent history."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    history = load_history()
    recent = [h for h in history if h.get("timestamp", "") >= cutoff]

    if not recent:
        print(f"No benchmark history in the last {days} days.")
        return

    print(f"=== Retrieval Benchmark Trend ({days} days, {len(recent)} runs) ===\n")
    print(f"{'Date':>12s}  {'P@3':>6s}  {'Recall':>6s}  {'Hits':>4s}  {'Miss':>4s}  Failures")
    print("-" * 70)

    for h in recent:
        ts = h.get("timestamp", "")[:10]
        p = h.get("avg_precision_at_k", 0)
        r = h.get("avg_recall", 0)
        hits = h.get("total_hits", 0)
        misses = h.get("total_misses", 0)
        fails = ",".join(h.get("failure_ids", []))
        print(f"{ts:>12s}  {p:>6.3f}  {r:>6.3f}  {hits:>4d}  {misses:>4d}  {fails or '-'}")

    # Summary
    if len(recent) >= 2:
        first_p = recent[0].get("avg_precision_at_k", 0)
        last_p = recent[-1].get("avg_precision_at_k", 0)
        first_r = recent[0].get("avg_recall", 0)
        last_r = recent[-1].get("avg_recall", 0)
        print(f"\nTrend: P@3 {first_p:.3f} -> {last_p:.3f} ({last_p - first_p:+.3f})")
        print(f"       Recall {first_r:.3f} -> {last_r:.3f} ({last_r - first_r:+.3f})")


def print_report(report: dict):
    """Pretty-print benchmark results."""
    print("=" * 65)
    print("  RETRIEVAL BENCHMARK — Ground Truth Evaluation")
    print("=" * 65)
    print(f"  Method: {report['method']}  |  k={report['k']}  |  Queries: {report['num_queries']}")
    print(f"  Precision@{report['k']}: {report['avg_precision_at_k']:.3f}")
    print(f"  Recall:       {report['avg_recall']:.3f}  ({report['total_hits']}/{report['num_queries']} queries hit)")
    print()

    # Per-category
    print("  By category:")
    for cat, stats in sorted(report["by_category"].items()):
        print(f"    {cat:16s}  P@3={stats['avg_precision_at_k']:.3f}  "
              f"Recall={stats['avg_recall']:.3f}  (n={stats['count']})")

    # Details
    print()
    print("  Per-query results:")
    for q in report["details"]:
        marker = "HIT" if q["recall"] else "MISS"
        print(f"    [{marker:4s}] {q['id']} P@3={q['precision_at_k']:.2f}  {q['query'][:50]}")
        if not q["recall"]:
            # Show what we got for misses
            for r in q["results"][:2]:
                print(f"           got: [{r['collection']}] d={r['distance']}  {r['text_preview'][:60]}")

    # Failures summary
    if report["failures"]:
        print(f"\n  FAILURES ({len(report['failures'])}):")
        for f in report["failures"]:
            print(f"    {f['id']}: {f['query']}")


# === CLI ===
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        report = run_benchmark(use_smart=True, k=3)
        print_report(report)
        save_report(report)
        print(f"\n  Results saved to {LATEST_FILE}")
        print(f"  History appended to {HISTORY_FILE}")

    elif cmd == "trend":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        show_trend(days)

    elif cmd == "baseline":
        # Run with raw brain.recall for comparison
        report = run_benchmark(use_smart=False, k=3)
        print_report(report)

    else:
        print("Usage:")
        print("  retrieval_benchmark.py              Run benchmark (smart_recall)")
        print("  retrieval_benchmark.py baseline      Run benchmark (raw brain.recall)")
        print("  retrieval_benchmark.py trend [days]  Show precision/recall trend")
