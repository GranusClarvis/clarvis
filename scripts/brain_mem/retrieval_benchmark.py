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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path
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
        "expected_substrings": ["operator", "granus"],
        "expected_collections": [IDENTITY],
        "category": "identity",
        "gold_evidence": "Clarvis was created by the operator (GranusClarvis). The operator is the sole creator and maintainer of the Clarvis cognitive agent system.",
    },
    {
        "id": "B02",
        "query": "What capabilities does Clarvis have?",
        "expected_substrings": ["capability", "git", "web search", "code"],
        "expected_collections": [IDENTITY],
        "category": "identity",
        "gold_evidence": "Clarvis capabilities include: code generation and review, git operations, web search and browsing, memory storage and retrieval via ClarvisDB, autonomous task execution, research ingestion, and self-reflection.",
    },
    # --- Goals ---
    {
        "id": "B03",
        "query": "What are my current goals?",
        "expected_substrings": ["goal", "clarvisdb", "agi", "consciousness", "north star"],
        "expected_collections": [GOALS],
        "category": "goals",
        "gold_evidence": "North star goal: evolve toward AGI-like consciousness. Current goals include ClarvisDB brain improvement, performance tracking, agent orchestration, and autonomous self-improvement.",
    },
    {
        "id": "B04",
        "query": "Progress on session continuity",
        "expected_substrings": ["session continuity"],
        "expected_collections": [GOALS],
        "category": "goals",
        "gold_evidence": "Session continuity goal: maintain coherent identity and memory across conversation sessions. Progress tracked via episodic memory persistence and working memory carryover.",
    },
    {
        "id": "B05",
        "query": "AGI and consciousness goal progress",
        "expected_substrings": ["agi", "consciousness"],
        "expected_collections": [GOALS, LEARNINGS, MEMORIES],
        "category": "goals",
        "gold_evidence": "AGI and consciousness progress: Phi (IIT) metric implemented, GWT attention mechanism active, episodic memory with causal links, self-model with 7 capability domains, meta-cognitive reflection pipeline.",
    },
    # --- Infrastructure ---
    {
        "id": "B06",
        "query": "What is the gateway address?",
        "expected_substrings": ["127.0.0.1", "18789", "gateway"],
        "expected_collections": [INFRASTRUCTURE],
        "category": "infrastructure",
        "gold_evidence": "OpenClaw gateway runs on 127.0.0.1:18789. Managed via systemd (systemctl --user). MiniMax M2.5 model for conscious layer chat.",
    },
    {
        "id": "B07",
        "query": "ClarvisDB architecture and components",
        "expected_substrings": ["brain.py", "chromadb", "clarvisdb"],
        "expected_collections": [INFRASTRUCTURE, LEARNINGS],
        "category": "infrastructure",
        "gold_evidence": "ClarvisDB: ChromaDB + ONNX MiniLM embeddings, fully local. 10 collections. API through clarvis.brain spine module (CLI: python3 -m clarvis brain; legacy: scripts/brain.py). Graph supports dual backends: JSON + SQLite+WAL.",
    },
    {
        "id": "B08",
        "query": "Security rules and permissions policy",
        "expected_substrings": ["security", "permission", "grouppolicy", "credential"],
        "expected_collections": [LEARNINGS, INFRASTRUCTURE],
        "category": "infrastructure",
        "gold_evidence": "Security policy: credentials stored in auth.json, never committed. Permission boundaries enforced. GroupPolicy-like security model. Claude Code spawned with --dangerously-skip-permissions for cron automation.",
    },
    # --- Learnings & knowledge ---
    {
        "id": "B09",
        "query": "How does the attention mechanism work?",
        "expected_substrings": ["attention", "spotlight", "gwt", "salience", "global workspace"],
        "expected_collections": [LEARNINGS, MEMORIES],
        "category": "knowledge",
        "gold_evidence": "Attention mechanism implements Global Workspace Theory (GWT). Codelets submit items with importance/relevance scores. Spotlight selects top items for broadcast. Implements salience-based filtering for heartbeat task selection.",
    },
    {
        "id": "B10",
        "query": "What did I learn about using brain.search instead of memory_search?",
        "expected_substrings": ["brain.search", "memory_search", "clarvisdb"],
        "expected_collections": [LEARNINGS],
        "category": "knowledge",
        "gold_evidence": "Learned: use brain.search (ClarvisDB) instead of deprecated memory_search. brain.search queries all collections, returns structured results with distances. memory_search was the old interface before ClarvisDB consolidation.",
    },
    {
        "id": "B11",
        "query": "Autonomy framework and when to act vs ask",
        "expected_substrings": ["autonomy", "act first", "ask first"],
        "expected_collections": [LEARNINGS],
        "category": "knowledge",
        "gold_evidence": "Autonomy framework: act first on reversible, low-risk tasks. Ask first on irreversible, high-risk, or ambiguous tasks. Bias toward action for cron/heartbeat tasks. Always ask for git push, destructive ops, external communications.",
    },
    {
        "id": "B12",
        "query": "Consciousness metrics and phi measurement",
        "expected_substrings": ["phi", "consciousness", "iit", "metric"],
        "expected_collections": [LEARNINGS, MEMORIES],
        "category": "knowledge",
        "gold_evidence": "Phi metric based on IIT (Integrated Information Theory). Computed via phi_metric.py. Measures information integration across brain collections and graph connectivity. Higher phi = more integrated consciousness proxy.",
    },
    {
        "id": "B13",
        "query": "Lessons about integrating ClarvisDB",
        "expected_substrings": ["clarvisdb", "integrate", "wire", "built but didn't"],
        "expected_collections": [LEARNINGS],
        "category": "knowledge",
        "gold_evidence": "Key lesson: we built ClarvisDB but didn't wire it into enough consumers. Integration requires connecting brain.search/recall into preflight context, postflight storage, and cron scripts. Integration debt = capability that exists but isn't used.",
    },
    # --- Procedures ---
    {
        "id": "B14",
        "query": "How to fix cron_autonomous",
        "expected_substrings": ["cron_autonomous", "fix"],
        "expected_collections": [PROCEDURES, LEARNINGS],
        "category": "procedures",
        "gold_evidence": "Fixing cron_autonomous: check lockfile /tmp/clarvis_claude_global.lock for stale locks. Verify cron_env.sh sources correctly. Check Claude Code binary path. Review exit codes in /tmp/clarvis_heartbeat_*.log.",
    },
    {
        "id": "B15",
        "query": "Procedure for reasoning chain outcomes",
        "expected_substrings": ["reasoning chain", "outcome"],
        "expected_collections": [PROCEDURES, LEARNINGS],
        "category": "procedures",
        "gold_evidence": "Reasoning chain outcome procedure: reasoning_chain_hook.py close_chain() records outcome (success/failure) and confidence. Chain stored in data/reasoning_chains/. Postflight §2 calls close_chain with task status and output evidence.",
    },
    # --- Preferences ---
    {
        "id": "B16",
        "query": "Communication style preferences",
        "expected_substrings": ["direct", "no fluff", "communication"],
        "expected_collections": [PREFERENCES, MEMORIES],
        "category": "preferences",
        "gold_evidence": "Communication preferences: direct, no fluff, concise. Lead with the answer. Skip preamble and unnecessary transitions. Prefer short sentences. Only add comments where logic isn't self-evident.",
    },
    {
        "id": "B17",
        "query": "What timezone should I use?",
        "expected_substrings": ["cet", "timezone"],
        "expected_collections": [PREFERENCES],
        "category": "preferences",
        "gold_evidence": "Timezone: CET (Central European Time). All cron schedules in CET. The operator is in CET timezone.",
    },
    # --- Context & episodic ---
    {
        "id": "B18",
        "query": "What happened in the last heartbeat?",
        "expected_substrings": ["heartbeat", "brain healthy", "verified"],
        "expected_collections": [CONTEXT, MEMORIES],
        "category": "context",
        "gold_evidence": "Last heartbeat: brain healthy, task executed successfully, episode recorded, verified session continuity. Brain health check passed with expected memory count.",
    },
    # --- Autonomous learning ---
    {
        "id": "B19",
        "query": "Success rate across sessions",
        "expected_substrings": ["success rate", "sessions"],
        "expected_collections": [LEARNINGS, MEMORIES],
        "category": "meta",
        "gold_evidence": "Success rate across sessions tracked via episodic memory. Action accuracy computed as successes/(total - timeouts - soft_failures). Current trailing-20 action accuracy monitored by postflight regression guard.",
    },
    {
        "id": "B20",
        "query": "What recurring themes appear in my sessions?",
        "expected_substrings": ["theme", "recurring", "session"],
        "expected_collections": [LEARNINGS, MEMORIES],
        "category": "meta",
        "gold_evidence": "Recurring session themes: brain maintenance, cron reliability, memory quality improvement, code quality gates, performance benchmarking, autonomous evolution. Themes synthesized via periodic episodic synthesis.",
    },
]


def check_hit(result: dict, pair: dict) -> bool:
    """Check if a single result is a ground-truth hit for this benchmark pair."""
    doc = result.get("document", "").lower()
    for sub in pair["expected_substrings"]:
        if sub.lower() in doc:
            return True
    return False


# Patterns that indicate synthetic/bridge/boost memories (not organic user content)
_SYNTHETIC_PATTERNS = [
    "bridge", "sbridge", "BRIDGE", "Sbridge",
    "Connection between", "connection between",
    "boost_", "fresh_mirror", "INTRA_DENSITY",
    "Synthesized insight:", "SEMANTIC_BRIDGE",
]


def is_synthetic(result: dict) -> bool:
    """Detect if a result is a synthetic bridge/boost memory rather than canonical."""
    doc = result.get("document", "")
    rid = result.get("id", "")
    # Check ID prefixes
    if rid.startswith(("bridge_", "sbridge_", "boost_", "fresh_mirror_")):
        return True
    # Check document content for synthetic markers
    for pat in _SYNTHETIC_PATTERNS:
        if pat in doc:
            return True
    return False


def _usefulness_score(result: dict, query: str) -> float:
    """Compute per-result usefulness score using CRAG composite scoring.

    Combines semantic similarity, keyword overlap, importance, and recency
    into a single 0-1 score indicating how useful this result is for the query.
    """
    try:
        from clarvis.brain.retrieval_eval import score_result
        return score_result(result, query)
    except ImportError:
        # Fallback: simple distance-based score
        d = result.get("distance", 2.0)
        return round(1.0 / (1.0 + d), 4)


def _oracle_recall(query: str, pair: dict, n: int = 3) -> list:
    """Synthesize perfect retrieval results from gold_evidence.

    Returns a list of fake results that perfectly match the benchmark pair,
    simulating ideal retrieval. Used in oracle mode to isolate reasoning
    failures from retrieval failures.
    """
    gold = pair.get("gold_evidence", "")
    if not gold:
        return []  # no gold evidence → empty (treated as retrieval miss)
    collections = pair.get("expected_collections", ["clarvis-memories"])
    return [{
        "document": gold,
        "id": f"oracle_{pair['id']}",
        "collection": collections[0] if collections else "oracle",
        "distance": 0.0,
        "metadata": {"source": "oracle", "benchmark_id": pair["id"]},
    }]


def _evaluate_pair(pair: dict, recall_fn, k: int, oracle: bool) -> dict:
    """Evaluate a single benchmark pair and return scored result."""
    query = pair["query"]
    if oracle:
        results = _oracle_recall(query, pair, n=k)
    else:
        results = recall_fn(query, n=k, caller="benchmark")

    hits_in_k = 0
    first_hit_rank = 0
    query_synthetic = 0
    query_usefulness = 0.0
    canonical_hits = 0
    result_details = []
    for i, r in enumerate(results[:k]):
        is_hit = check_hit(r, pair)
        synthetic = is_synthetic(r)
        useful = _usefulness_score(r, query)
        if is_hit:
            hits_in_k += 1
            if first_hit_rank == 0:
                first_hit_rank = i + 1
            if not synthetic:
                canonical_hits += 1
        if synthetic:
            query_synthetic += 1
        query_usefulness += useful
        result_details.append({
            "rank": i + 1, "hit": is_hit, "synthetic": synthetic,
            "usefulness": round(useful, 4), "collection": r.get("collection"),
            "distance": round(r.get("distance", 999), 4),
            "text_preview": r.get("document", "")[:80],
        })

    n_results = len(results[:k])
    precision_at_k = hits_in_k / k if k > 0 else 0
    precision_at_1 = 1.0 if first_hit_rank == 1 else 0.0
    recall_hit = 1 if hits_in_k > 0 else 0
    rr = 1.0 / first_hit_rank if first_hit_rank > 0 else 0.0
    avg_useful = query_usefulness / n_results if n_results > 0 else 0.0

    return {
        "id": pair["id"], "query": query, "category": pair["category"],
        "precision_at_k": round(precision_at_k, 3), "precision_at_1": precision_at_1,
        "recall": recall_hit, "reciprocal_rank": round(rr, 4),
        "hits_in_k": hits_in_k, "first_hit_rank": first_hit_rank,
        "synthetic_count": query_synthetic, "canonical_hits": canonical_hits,
        "n_results": n_results, "avg_usefulness": round(avg_useful, 4),
        "results": result_details,
    }


def _aggregate_benchmark(query_results: list, category_stats: dict, n: int) -> dict:
    """Aggregate per-query results into a summary report body."""
    total_precision = sum(q["precision_at_k"] for q in query_results)
    total_precision1 = sum(q["precision_at_1"] for q in query_results)
    total_recall = sum(q["recall"] for q in query_results)
    total_mrr = sum(q["reciprocal_rank"] for q in query_results)
    total_synthetic = sum(q["synthetic_count"] for q in query_results)
    total_results_seen = sum(q["n_results"] for q in query_results)
    total_canonical_hits = sum(q["canonical_hits"] for q in query_results)
    total_usefulness = sum(q["avg_usefulness"] for q in query_results)

    category_report = {}
    for cat, stats in category_stats.items():
        c = stats["count"]
        category_report[cat] = {
            "count": c,
            "avg_precision_at_k": round(stats["precision_sum"] / c, 3) if c > 0 else 0,
            "avg_precision_at_1": round(stats["precision1_sum"] / c, 3) if c > 0 else 0,
            "avg_recall": round(stats["recall_sum"] / c, 3) if c > 0 else 0,
            "mrr": round(stats["mrr_sum"] / c, 3) if c > 0 else 0,
        }

    contamination_rate = round(total_synthetic / total_results_seen, 4) if total_results_seen > 0 else 0.0
    total_hits_all = sum(q["hits_in_k"] for q in query_results)
    canonical_hit_rate = round(total_canonical_hits / total_hits_all, 4) if total_hits_all > 0 else 0.0
    failures = [q for q in query_results if q["recall"] == 0]

    return {
        "avg_precision_at_k": round(total_precision / n, 4) if n > 0 else 0,
        "avg_precision_at_1": round(total_precision1 / n, 4) if n > 0 else 0,
        "avg_recall": round(total_recall / n, 4) if n > 0 else 0,
        "mrr": round(total_mrr / n, 4) if n > 0 else 0,
        "contamination_rate": contamination_rate,
        "canonical_hit_rate": canonical_hit_rate,
        "avg_usefulness": round(total_usefulness / n, 4) if n > 0 else 0.0,
        "total_hits": sum(1 for q in query_results if q["recall"]),
        "total_misses": sum(1 for q in query_results if not q["recall"]),
        "total_synthetic": total_synthetic,
        "total_results": total_results_seen,
        "by_category": category_report,
        "failures": [{"id": f["id"], "query": f["query"], "category": f["category"]} for f in failures],
    }


def run_benchmark(use_smart=True, k=3, oracle=False) -> dict:
    """Run all 20 benchmark queries. Measure precision@k, recall, P@1, and MRR.

    Args:
        use_smart: Use smart_recall if available (ignored in oracle mode).
        k: Number of results to evaluate.
        oracle: If True, bypass retrieval and inject gold_evidence as results.

    Returns dict with per-query and aggregate metrics.
    """
    if oracle:
        method_name = "oracle"
        recall_fn = None
    else:
        recall_fn = smart_recall if (use_smart and smart_recall) else brain.recall
        method_name = "smart_recall" if (use_smart and smart_recall) else "brain.recall"

    query_results = []
    category_stats = {}

    for pair in BENCHMARK_PAIRS:
        qr = _evaluate_pair(pair, recall_fn, k, oracle)
        query_results.append(qr)

        cat = pair["category"]
        if cat not in category_stats:
            category_stats[cat] = {
                "precision_sum": 0.0, "precision1_sum": 0.0,
                "recall_sum": 0, "mrr_sum": 0.0, "count": 0,
            }
        category_stats[cat]["precision_sum"] += qr["precision_at_k"]
        category_stats[cat]["precision1_sum"] += qr["precision_at_1"]
        category_stats[cat]["recall_sum"] += qr["recall"]
        category_stats[cat]["mrr_sum"] += qr["reciprocal_rank"]
        category_stats[cat]["count"] += 1

    n = len(BENCHMARK_PAIRS)
    agg = _aggregate_benchmark(query_results, category_stats, n)

    # Strip internal fields from query_results before including in report
    for qr in query_results:
        qr.pop("canonical_hits", None)
        qr.pop("n_results", None)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": method_name, "k": k, "oracle_mode": oracle,
        "num_queries": n, **agg, "details": query_results,
    }


def run_oracle_comparison(use_smart=True, k=3) -> dict:
    """Run both normal and oracle benchmarks, compute retrieval gap.

    The retrieval gap = oracle_score - normal_score. A large gap means
    retrieval is the bottleneck. A small gap means the gold evidence
    itself doesn't improve scores (queries may be hard to answer even
    with perfect evidence).

    Returns dict with normal, oracle, and gap analysis.
    """
    normal = run_benchmark(use_smart=use_smart, k=k, oracle=False)
    oracle = run_benchmark(use_smart=use_smart, k=k, oracle=True)

    gap = {
        "precision_at_k_gap": round(oracle["avg_precision_at_k"] - normal["avg_precision_at_k"], 4),
        "precision_at_1_gap": round(oracle["avg_precision_at_1"] - normal["avg_precision_at_1"], 4),
        "recall_gap": round(oracle["avg_recall"] - normal["avg_recall"], 4),
        "mrr_gap": round(oracle["mrr"] - normal["mrr"], 4),
    }

    # Per-category gap
    category_gap = {}
    for cat in oracle["by_category"]:
        o = oracle["by_category"][cat]
        n = normal["by_category"].get(cat, {})
        category_gap[cat] = {
            "recall_gap": round(o.get("avg_recall", 0) - n.get("avg_recall", 0), 3),
            "mrr_gap": round(o.get("mrr", 0) - n.get("mrr", 0), 3),
        }

    # Queries that fail in normal mode but pass in oracle → pure retrieval failures
    normal_fail_ids = {f["id"] for f in normal["failures"]}
    oracle_fail_ids = {f["id"] for f in oracle["failures"]}
    retrieval_failures = sorted(normal_fail_ids - oracle_fail_ids)
    # Queries that fail in both → evidence/gold quality issues
    shared_failures = sorted(normal_fail_ids & oracle_fail_ids)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "normal": normal,
        "oracle": oracle,
        "gap": gap,
        "category_gap": category_gap,
        "retrieval_failures": retrieval_failures,
        "shared_failures": shared_failures,
        "diagnosis": (
            f"{len(retrieval_failures)} pure retrieval failures, "
            f"{len(shared_failures)} evidence-quality failures"
        ),
    }


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
        "avg_precision_at_1": report.get("avg_precision_at_1", 0),
        "avg_recall": report["avg_recall"],
        "mrr": report.get("mrr", 0),
        "contamination_rate": report.get("contamination_rate", 0),
        "canonical_hit_rate": report.get("canonical_hit_rate", 0),
        "avg_usefulness": report.get("avg_usefulness", 0),
        "total_hits": report["total_hits"],
        "total_misses": report["total_misses"],
        "total_synthetic": report.get("total_synthetic", 0),
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
    print(f"{'Date':>12s}  {'P@1':>6s}  {'P@3':>6s}  {'MRR':>6s}  {'Recall':>6s}  {'Contam':>6s}  {'Useful':>6s}  {'Hits':>4s}  Failures")
    print("-" * 100)

    for h in recent:
        ts = h.get("timestamp", "")[:10]
        p1 = h.get("avg_precision_at_1", 0)
        p = h.get("avg_precision_at_k", 0)
        m = h.get("mrr", 0)
        r = h.get("avg_recall", 0)
        contam = h.get("contamination_rate", 0)
        useful = h.get("avg_usefulness", 0)
        hits = h.get("total_hits", 0)
        fails = ",".join(h.get("failure_ids", []))
        print(f"{ts:>12s}  {p1:>6.3f}  {p:>6.3f}  {m:>6.3f}  {r:>6.3f}  {contam:>6.3f}  {useful:>6.3f}  {hits:>4d}  {fails or '-'}")

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
    print(f"  P@1:              {report.get('avg_precision_at_1', 0):.3f}")
    print(f"  P@{report['k']}:              {report['avg_precision_at_k']:.3f}")
    print(f"  MRR:              {report.get('mrr', 0):.3f}")
    print(f"  Recall:           {report['avg_recall']:.3f}  ({report['total_hits']}/{report['num_queries']} queries hit)")
    print(f"  Contamination:    {report.get('contamination_rate', 0):.3f}  ({report.get('total_synthetic', 0)}/{report.get('total_results', 0)} synthetic)")
    print(f"  Canonical hits:   {report.get('canonical_hit_rate', 0):.3f}  (organic hits / total hits)")
    print(f"  Avg usefulness:   {report.get('avg_usefulness', 0):.3f}  (CRAG composite)")
    print()

    # Per-category
    print("  By category:")
    for cat, stats in sorted(report["by_category"].items()):
        print(f"    {cat:16s}  P@1={stats.get('avg_precision_at_1', 0):.2f}  "
              f"P@3={stats['avg_precision_at_k']:.3f}  "
              f"MRR={stats.get('mrr', 0):.3f}  "
              f"Recall={stats['avg_recall']:.3f}  (n={stats['count']})")

    # Details
    print()
    print("  Per-query results:")
    for q in report["details"]:
        marker = "HIT" if q["recall"] else "MISS"
        rr_str = f"RR={q.get('reciprocal_rank', 0):.2f}" if q["recall"] else "RR=0.00"
        print(f"    [{marker:4s}] {q['id']} P@1={q.get('precision_at_1', 0):.0f} P@3={q['precision_at_k']:.2f} {rr_str}  {q['query'][:45]}")
        if not q["recall"]:
            # Show what we got for misses
            for r in q["results"][:2]:
                print(f"           got: [{r['collection']}] d={r['distance']}  {r['text_preview'][:60]}")

    # Failures summary
    if report["failures"]:
        print(f"\n  FAILURES ({len(report['failures'])}):")
        for f in report["failures"]:
            print(f"    {f['id']}: {f['query']}")


GOLDEN_QA_FILE = os.path.join(
    "/home/agent/.openclaw/workspace/data/benchmarks", "golden_qa_results.json"
)


def run_golden_qa():
    """Run golden QA benchmark and save results to data/benchmarks/.

    This is the main brain quality evaluation — P@1, P@3, MRR against
    20 ground-truth query-answer pairs. Use periodically to track
    retrieval quality regression.
    """
    report = run_benchmark(use_smart=True, k=3)
    save_report(report)

    # Save to data/benchmarks/ for cross-benchmark visibility
    os.makedirs(os.path.dirname(GOLDEN_QA_FILE), exist_ok=True)
    golden_summary = {
        "timestamp": report["timestamp"],
        "num_queries": report["num_queries"],
        "precision_at_1": report.get("avg_precision_at_1", 0),
        "precision_at_3": report["avg_precision_at_k"],
        "mrr": report.get("mrr", 0),
        "recall": report["avg_recall"],
        "contamination_rate": report.get("contamination_rate", 0),
        "canonical_hit_rate": report.get("canonical_hit_rate", 0),
        "avg_usefulness": report.get("avg_usefulness", 0),
        "total_hits": report["total_hits"],
        "total_misses": report["total_misses"],
        "total_synthetic": report.get("total_synthetic", 0),
        "by_category": report["by_category"],
        "failures": report["failures"],
    }
    with open(GOLDEN_QA_FILE, "w") as f:
        json.dump(golden_summary, f, indent=2)

    return report


# === CLI ===
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        report = run_benchmark(use_smart=True, k=3)
        print_report(report)
        save_report(report)
        print(f"\n  Results saved to {LATEST_FILE}")
        print(f"  History appended to {HISTORY_FILE}")

    elif cmd == "golden_qa":
        report = run_golden_qa()
        print_report(report)
        print(f"\n  Golden QA results saved to {GOLDEN_QA_FILE}")
        print(f"  Full results saved to {LATEST_FILE}")

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
        print("  retrieval_benchmark.py golden_qa     Run + save golden QA results")
        print("  retrieval_benchmark.py baseline      Run benchmark (raw brain.recall)")
        print("  retrieval_benchmark.py trend [days]  Show precision/recall trend")
