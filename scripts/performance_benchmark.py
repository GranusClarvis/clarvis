#!/usr/bin/env python3
"""
Performance Benchmark — Comprehensive performance tracking for Clarvis.

Tracks 8 performance dimensions with measurable targets, a composite
Performance Index (PI) spectrum, self-optimization triggers, and
heartbeat integration.

Dimensions:
  1. Brain Query Speed      — target: <100ms avg, <200ms P95
  2. Semantic Retrieval      — target: >80% hit rate, >60% precision@3
  3. Efficiency              — tokens/operation, response latency
  4. Accuracy                — retrieval hit rate, action success rate
  5. Results Quality         — context relevance, output quality score
  6. Brain Bloat Prevention  — memory count growth, pruning frequency
  7. Context/Prompt Quality  — inject relevance, brief compression ratio
  8. Load Scaling            — query speed at N memories, degradation rate

Performance Index (PI): 0.0-1.0 composite score across all dimensions.
  0.00-0.20  Critical    — multiple systems degraded, immediate action
  0.20-0.40  Poor        — below targets, optimization needed
  0.40-0.60  Acceptable  — meeting minimum targets
  0.60-0.80  Good        — above targets, healthy system
  0.80-1.00  Excellent   — all systems optimal, room for growth

Self-optimization: When PI drops >0.05 or a metric regresses, triggers
are written to the evolution queue for autonomous correction.

Usage:
    python3 performance_benchmark.py              # Full benchmark + report
    python3 performance_benchmark.py quick         # Fast check (speed + stats, ~2s)
    python3 performance_benchmark.py record        # Full + record to history
    python3 performance_benchmark.py trend [days]  # Show trend analysis
    python3 performance_benchmark.py check         # Full + exit 1 on failures
    python3 performance_benchmark.py heartbeat     # Quick check for heartbeat integration
    python3 performance_benchmark.py pi            # Just compute and print PI
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure clarvis package is importable
_workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

# Import canonical TARGETS, compute_pi, and check_self_optimization from spine
from clarvis.metrics.benchmark import (  # noqa: E402
    TARGETS, compute_pi, check_self_optimization,
)

# === PATHS ===
WORKSPACE = "/home/agent/.openclaw/workspace"
METRICS_FILE = os.path.join(WORKSPACE, "data/performance_metrics.json")
HISTORY_FILE = os.path.join(WORKSPACE, "data/performance_history.jsonl")
ALERTS_FILE = os.path.join(WORKSPACE, "data/performance_alerts.jsonl")
os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)

# Rolling history cap
MAX_HISTORY = 400
MAX_ALERTS = 200

# === TEST QUERIES ===
TIMING_QUERIES = [
    "What are my current goals?",
    "How does the heartbeat work?",
    "What is ClarvisDB?",
    "Recent failures in autonomous execution",
    "Who created Clarvis?",
    "What infrastructure do I run on?",
    "How to spawn Claude Code?",
    "Active inference and free energy",
    "Memory consolidation strategy",
    "What happened yesterday?",
]

# Queries with known expected answers for accuracy testing (20+ ground-truth pairs)
ACCURACY_QUERIES = [
    # Identity
    ("Who created Clarvis?", ["patrick", "inverse"]),
    ("What capabilities does Clarvis have?", ["capability", "git", "code"]),
    # Infrastructure
    ("What port does the gateway run on?", ["18789", "gateway"]),
    ("ClarvisDB architecture and components", ["brain.py", "chromadb", "clarvisdb"]),
    ("Security rules and permissions policy", ["security", "permission", "grouppolicy", "credential"]),
    ("What are the ONNX embeddings?", ["minilm", "onnx", "embedding"]),
    # Knowledge
    ("How to run brain health?", ["health", "brain.py"]),
    ("What is the Phi metric?", ["integration", "consciousness", "iit"]),
    ("How does the attention mechanism work?", ["attention", "spotlight", "gwt", "salience"]),
    ("Lessons about integrating ClarvisDB", ["clarvisdb", "integrate", "wire"]),
    # Goals
    ("What are my current goals?", ["goal", "clarvisdb", "agi", "consciousness"]),
    ("Progress on session continuity", ["session continuity"]),
    ("AGI and consciousness goal progress", ["agi", "consciousness"]),
    # Procedures
    ("How to fix cron_autonomous", ["cron_autonomous", "fix"]),
    ("Procedure for reasoning chain outcomes", ["reasoning chain", "outcome"]),
    # Preferences
    ("What model does the conscious layer use?", ["minimax", "m2.5", "conscious"]),
    ("What timezone should I use?", ["cet", "timezone"]),
    ("Communication style preferences", ["direct", "no fluff", "communication"]),
    # Context
    ("What happened in the last heartbeat?", ["heartbeat", "brain healthy", "verified"]),
    ("What backup system does Clarvis use?", ["backup", "incremental", "clarvisdb"]),
    # Meta
    ("Success rate across sessions", ["success rate", "sessions"]),
    ("What recurring themes appear in my sessions?", ["theme", "recurring", "session"]),
]


# ============================================================
# BENCHMARK FUNCTIONS
# ============================================================

def benchmark_brain_speed():
    """Dimension 1: Measure brain.recall() latency across representative queries."""
    from brain import brain

    # Warm up (first query loads ChromaDB/ONNX)
    brain.recall("warmup", n=1)

    timings = []
    for query in TIMING_QUERIES:
        t0 = time.monotonic()
        brain.recall(query, n=3)
        elapsed_ms = (time.monotonic() - t0) * 1000
        timings.append({"query": query, "ms": round(elapsed_ms, 2)})

    timings.sort(key=lambda x: x["ms"])
    avg_ms = sum(t["ms"] for t in timings) / len(timings)
    p50_ms = timings[len(timings) // 2]["ms"]
    p95_idx = int(len(timings) * 0.95)
    p95_ms = timings[min(p95_idx, len(timings) - 1)]["ms"]
    slowest = timings[-1]

    return {
        "avg_ms": round(avg_ms, 2),
        "p50_ms": round(p50_ms, 2),
        "p95_ms": round(p95_ms, 2),
        "min_ms": round(timings[0]["ms"], 2),
        "max_ms": round(slowest["ms"], 2),
        "slowest_query": slowest["query"],
        "n_queries": len(timings),
        "all_timings": timings,
    }


def benchmark_retrieval_quality():
    """Dimension 2: Semantic retrieval accuracy and precision.

    Prefers reading the latest retrieval_benchmark result file (from cron_evening.sh)
    to avoid re-running the expensive 20-query benchmark and risking contention.
    Falls back to running it live, then to a lightweight accuracy check.
    """
    # Prefer cached results from the most recent retrieval_benchmark run (cron_evening.sh)
    latest_file = os.path.join(WORKSPACE, "data/retrieval_benchmark/latest.json")
    if os.path.exists(latest_file):
        try:
            with open(latest_file) as f:
                report = json.load(f)
            # Only use if less than 72 hours old (cron_evening runs daily; 72h tolerates a missed run)
            ts = report.get("timestamp", "")
            if ts:
                from datetime import datetime, timezone
                age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds() / 3600
                if age_h < 72:
                    return {
                        "hit_rate": report.get("avg_recall", 0.0),
                        "precision_at_3": report.get("avg_precision_at_k", 0.0),
                        "n_pairs": report.get("num_queries", 0),
                        "category_scores": report.get("by_category", {}),
                        "source": "retrieval_benchmark_cached",
                    }
        except Exception:
            pass

    # Live run if no cache available
    try:
        from retrieval_benchmark import run_benchmark, save_report
        report = run_benchmark()
        # Cache results so next benchmark_retrieval_quality() call can use cached path
        try:
            save_report(report)
        except Exception:
            pass
        return {
            "hit_rate": report.get("avg_recall", 0.0),
            "precision_at_3": report.get("avg_precision_at_k", 0.0),
            "n_pairs": report.get("num_queries", 0),
            "category_scores": report.get("by_category", {}),
            "source": "retrieval_benchmark",
        }
    except Exception as e1:
        # Fallback: test against known-answer pairs
        try:
            from brain import brain
            hits = 0
            for query, expected in ACCURACY_QUERIES:
                results = brain.recall(query, n=3)
                for r in results:
                    doc = r.get("document", "").lower()
                    if any(exp.lower() in doc for exp in expected):
                        hits += 1
                        break
            hit_rate = round(hits / len(ACCURACY_QUERIES), 3) if ACCURACY_QUERIES else 0.0
            precision_hits = 0
            precision_total = 0
            for query, expected in ACCURACY_QUERIES[:5]:
                results = brain.recall(query, n=3)
                for r in results:
                    precision_total += 1
                    doc = r.get("document", "").lower()
                    if any(exp.lower() in doc for exp in expected):
                        precision_hits += 1
            precision_at_3 = round(precision_hits / max(precision_total, 1), 3)
            return {
                "hit_rate": hit_rate,
                "precision_at_3": precision_at_3,
                "n_pairs": len(ACCURACY_QUERIES),
                "source": "accuracy_fallback",
            }
        except Exception as e2:
            # Both paths failed — return error state instead of crashing
            return {
                "hit_rate": None,
                "precision_at_3": None,
                "n_pairs": 0,
                "source": "error",
                "error": f"primary: {e1}, fallback: {e2}",
            }


def benchmark_efficiency():
    """Dimension 3: Token efficiency and heartbeat overhead."""
    result = {"avg_tokens_per_op": None, "heartbeat_overhead_s": None}

    # Estimate heartbeat overhead from recent postflight timings
    try:
        if os.path.exists(METRICS_FILE):
            with open(METRICS_FILE) as f:
                prev = json.load(f)
            result["heartbeat_overhead_s"] = prev.get("details", {}).get(
                "efficiency", {}
            ).get("heartbeat_overhead_s")
    except Exception:
        pass

    # Cost tracking: costs.jsonl removed (was deprecated).
    # Real cost data available via cost_tracker.py telegram / cost_api.py

    return result


def benchmark_brain_stats():
    """Dimension 6: Brain size, graph health, bloat detection."""
    from brain import brain
    stats = brain.stats()
    total_mem = stats["total_memories"]
    total_edges = stats["graph_edges"]
    graph_density = round(total_edges / max(total_mem, 1), 2)

    # Bloat detection: compare memory count growth vs useful retrieval
    bloat_score = 0.0
    if total_mem > 500:
        # More memories with lower density = bloat
        # Ideal: density stays >1.0 as memories grow
        if graph_density < 0.5:
            bloat_score += 0.3
        if total_mem > 2000:
            bloat_score += 0.2
        if total_mem > 3000:
            bloat_score += 0.2

    # Check collection balance (heavily skewed = bloat sign)
    collections = stats.get("collections", {})
    if collections:
        counts = [v for v in collections.values() if isinstance(v, (int, float))]
        if counts:
            max_c = max(counts)
            avg_c = sum(counts) / len(counts)
            if avg_c > 0 and max_c / avg_c > 5:
                bloat_score += 0.1  # One collection is 5x the average

    bloat_score = min(round(bloat_score, 2), 1.0)

    return {
        "total_memories": total_mem,
        "graph_nodes": stats["graph_nodes"],
        "graph_edges": total_edges,
        "graph_density": graph_density,
        "bloat_score": bloat_score,
        "collections": collections,
    }


def benchmark_phi():
    """Dimension 5 (partial): Consciousness integration metric."""
    try:
        from phi_metric import compute_phi
        result = compute_phi()
        return {
            "phi": result["phi"],
            "interpretation": result["interpretation"],
            "components": result.get("components", {}),
        }
    except Exception as e:
        return {"phi": 0.0, "error": str(e)}


def benchmark_episodes():
    """Dimension 4: Episode success rate and action accuracy.

    IMPORTANT: Excludes soft_failures from success rate calculation.
    soft_failures are manufactured by failure_amplifier (observational annotations),
    not real execution failures. Including them inflates the failure rate.
    """
    try:
        from episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        stats = em.get_stats()
        outcomes = stats.get("outcomes", {})
        total = stats.get("total", 0)
        successes = outcomes.get("success", 0)

        # Exclude soft_failures (manufactured by failure_amplifier, not real failures)
        soft_failures = outcomes.get("soft_failure", 0)
        real_total = max(total - soft_failures, 1)
        success_rate = round(successes / real_total, 3)

        # Action accuracy = success / (real total - timeouts)
        timeouts = outcomes.get("timeout", 0)
        non_timeout = max(real_total - timeouts, 1)
        action_accuracy = round(successes / non_timeout, 3)

        return {
            "total_episodes": total,
            "real_episodes": real_total,
            "soft_failures_excluded": soft_failures,
            "success_rate": success_rate,
            "action_accuracy": action_accuracy,
            "outcomes": outcomes,
            "avg_valence": stats.get("avg_valence", 0.0),
            "strong_memories": stats.get("strong_memories", 0),
            "forgotten_memories": stats.get("forgotten_memories", 0),
        }
    except Exception as e:
        return {"total_episodes": 0, "success_rate": 0.0, "action_accuracy": 0.0, "error": str(e)}


def benchmark_context_quality():
    """Dimension 7: Context/prompt quality — measures actual compression ratio.

    brief_compression = 1 - (compressed_output / raw_input), higher is better.
    A value of 0.7 means 70% compression (output is 30% of input).
    Target: >= 0.5 (at least 50% compression).
    """
    brief_report = os.path.join(WORKSPACE, "data/benchmarks/brief_v2_report.json")
    result = {"brief_compression": 0.0, "context_relevance": 0.0}

    if os.path.exists(brief_report):
        try:
            with open(brief_report) as f:
                report = json.load(f)
            # Use stored compression ratio if available
            if "compression_ratio" in report:
                result["brief_compression"] = round(1.0 - report["compression_ratio"], 3)
            elif "avg_brief_bytes" in report:
                avg_bytes = report.get("avg_brief_bytes", 0)
                raw_bytes = report.get("avg_raw_bytes", avg_bytes * 3)
                if raw_bytes > 0:
                    result["brief_compression"] = round(1.0 - avg_bytes / raw_bytes, 3)

            # Context relevance: prefer episode-based data (CONTEXT_RELEVANCE_FEEDBACK)
            try:
                from clarvis.cognition.context_relevance import aggregate_relevance
                agg = aggregate_relevance(days=7)
                if agg.get("episodes", 0) >= 5:
                    result["context_relevance"] = round(agg["mean_relevance"], 3)
            except Exception:
                pass

            # Fallback: static proxy from v2 success rate vs v1
            if result["context_relevance"] == 0.0:
                v2_rate = report.get("v2_success_rate", 0)
                v1_rate = report.get("baseline_success_rate", 0.5)
                by_ver = report.get("by_version", {})
                v2_data = by_ver.get("v2", {})
                v1_data = by_ver.get("v1", {})
                if not v2_rate:
                    v2_rate = v2_data.get("success_rate", 0)
                    if v1_data.get("success_rate"):
                        v1_rate = v1_data["success_rate"]
                if v2_rate > 0:
                    result["context_relevance"] = round(min(v2_rate / max(v1_rate, 0.01), 1.5) / 1.5, 3)
        except Exception:
            pass

    # Fallback: measure compression quality directly
    if result["brief_compression"] == 0.0:
        try:
            from context_compressor import generate_tiered_brief, compress_text
            # Build raw input (uncompressed context sources)
            raw_parts = []
            try:
                from context_compressor import compress_queue, get_latest_scores
                raw_parts.append(compress_queue())
                scores = get_latest_scores()
                if scores:
                    raw_parts.append(json.dumps(scores))
            except Exception:
                pass
            try:
                from attention import attention
                attention._load()
                focused = attention.focus()
                for item in focused[:10]:
                    raw_parts.append(item.get("content", ""))
            except Exception:
                pass
            raw_input = "\n".join(raw_parts)

            # Generate compressed brief
            brief = generate_tiered_brief("Test task for benchmark", "standard", [])
            if brief and len(brief) > 100:
                if result["context_relevance"] == 0.0:
                    result["context_relevance"] = 0.6
                if raw_input and len(raw_input) > len(brief):
                    result["brief_compression"] = round(
                        1.0 - len(brief) / len(raw_input), 3
                    )
                else:
                    # Fallback: measure compression of the brief itself
                    _, stats = compress_text(brief, ratio=0.3)
                    result["brief_compression"] = round(1.0 - stats["ratio"], 3)
        except Exception:
            pass

    # Clamp to [0, 1]
    result["brief_compression"] = max(0.0, min(1.0, result["brief_compression"]))
    return result


def benchmark_load_scaling():
    """Dimension 8: Performance under load / degradation as brain grows."""
    from brain import brain

    # Warm up
    brain.recall("warmup", n=1)

    # Measure with increasing result counts (simulating load)
    load_levels = [1, 3, 5, 10]
    timings = {}
    for n in load_levels:
        t0 = time.monotonic()
        brain.recall("How does the heartbeat work?", n=n)
        elapsed_ms = (time.monotonic() - t0) * 1000
        timings[n] = round(elapsed_ms, 2)

    # Degradation: how much slower is n=10 vs n=1
    base = timings.get(1, 1)
    peak = timings.get(10, base)
    degradation_pct = round(((peak - base) / max(base, 0.1)) * 100, 1)

    return {
        "timings_by_n": timings,
        "degradation_pct": max(degradation_pct, 0),
        "base_ms": base,
        "peak_ms": peak,
    }


# ============================================================
# NEW BENCHMARK DIMENSIONS (added 2026-02-27)
# ============================================================

def benchmark_autonomy():
    """Autonomy benchmarks: cron success, spawn success, queue throughput, self-recovery."""
    result = {
        "cron_success_rate_24h": 0.0,
        "queue_throughput_day": 0,
        "self_recovery_rate": 0.0,
    }

    # Cron job success rate (last 24h) from autonomous.log
    cron_log = os.path.join(WORKSPACE, "memory/cron/autonomous.log")
    if os.path.exists(cron_log):
        try:
            import subprocess
            # Count recent heartbeat completions vs failures (last 24h)
            out = subprocess.run(
                ["grep", "-c", "Heartbeat complete", cron_log],
                capture_output=True, text=True, timeout=5
            )
            completions = int(out.stdout.strip()) if out.returncode == 0 else 0
            out = subprocess.run(
                ["grep", "-c", "WARN.*failed\\|ERROR", cron_log],
                capture_output=True, text=True, timeout=5
            )
            failures = int(out.stdout.strip()) if out.returncode == 0 else 0
            total = completions + failures
            if total > 0:
                result["cron_success_rate_24h"] = round(completions / total, 3)
        except Exception:
            pass

    # Queue throughput: completed items per day (from archive)
    archive_file = os.path.join(WORKSPACE, "memory/evolution/QUEUE_ARCHIVE.md")
    if os.path.exists(archive_file):
        try:
            import re
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            with open(archive_file) as f:
                content = f.read()
            # Count [x] items with today's date
            result["queue_throughput_day"] = len(re.findall(
                rf'\[x\].*{today}', content
            ))
        except Exception:
            pass

    # Self-recovery rate from cron_doctor
    doctor_log = os.path.join(WORKSPACE, "memory/cron/doctor.log")
    if os.path.exists(doctor_log):
        try:
            with open(doctor_log) as f:
                lines = f.readlines()[-50:]
            fixes = sum(1 for l in lines if "FIXED" in l or "recovered" in l.lower())
            failures = sum(1 for l in lines if "FAILED" in l or "unrecoverable" in l.lower())
            total = fixes + failures
            if total > 0:
                result["self_recovery_rate"] = round(fixes / total, 3)
        except Exception:
            pass

    return result


def benchmark_consciousness(phi_data=None):
    """Consciousness benchmarks: Phi composite, goal progress velocity.

    Accepts pre-computed phi data to avoid duplicate compute_phi() call.
    """
    result = {
        "phi_composite": 0.0,
        "cross_collection_overlap": 0.0,
        "goal_progress_velocity": 0.0,
    }

    # Phi — use passed-in data (no duplicate call)
    if phi_data:
        result["phi_composite"] = phi_data.get("phi", 0.0)
        components = phi_data.get("components", {})
        result["cross_collection_overlap"] = components.get("semantic_cross_collection", 0.0)
    else:
        try:
            from phi_metric import compute_phi
            phi_result = compute_phi()
            result["phi_composite"] = phi_result.get("phi", 0.0)
            components = phi_result.get("components", {})
            result["cross_collection_overlap"] = components.get("semantic_cross_collection", 0.0)
        except Exception:
            pass

    # Goal progress velocity (avg weekly delta)
    try:
        history_file = os.path.join(WORKSPACE, "data/goal_history.json")
        if os.path.exists(history_file):
            with open(history_file) as f:
                history = json.load(f)
            if len(history) >= 2:
                latest = history[-1].get("avg_progress", 0)
                prev = history[-2].get("avg_progress", 0)
                result["goal_progress_velocity"] = round(latest - prev, 3)
    except Exception:
        pass

    return result


def benchmark_intelligence(retrieval_data=None, speed_data=None):
    """Intelligence benchmarks: retrieval, query speed, confidence calibration, context compression.

    Accepts pre-computed retrieval and speed data to avoid duplicate benchmark calls.
    """
    result = {
        "retrieval_hit_rate": 0.0,
        "retrieval_precision3": 0.0,
        "brain_query_speed_avg_s": 0.0,
        "confidence_brier": 1.0,
        "context_compression_ratio": 0.0,
    }

    # Retrieval — use passed-in data (no duplicate call)
    if retrieval_data:
        result["retrieval_hit_rate"] = retrieval_data.get("hit_rate", 0.0) or 0.0
        result["retrieval_precision3"] = retrieval_data.get("precision_at_3", 0.0) or 0.0

    # Brain query speed — use passed-in data (no duplicate call)
    if speed_data:
        result["brain_query_speed_avg_s"] = round(speed_data.get("avg_ms", 0) / 1000, 3)

    # Confidence calibration Brier score
    try:
        cal_file = os.path.join(WORKSPACE, "data/confidence_calibration.json")
        if os.path.exists(cal_file):
            with open(cal_file) as f:
                cal = json.load(f)
            result["confidence_brier"] = cal.get("brier_score", 1.0)
    except Exception:
        pass

    # Context compression ratio
    try:
        from context_compressor import generate_tiered_brief
        brief = generate_tiered_brief("benchmark test task", "standard")
        if brief:
            # Compare to full queue size
            queue_file = os.path.join(WORKSPACE, "memory/evolution/QUEUE.md")
            if os.path.exists(queue_file):
                full_size = os.path.getsize(queue_file)
                if full_size > 0:
                    result["context_compression_ratio"] = round(
                        1.0 - (len(brief) / full_size), 3
                    )
    except Exception:
        pass

    return result


def benchmark_self_improvement():
    """Self-improvement benchmarks: queue sustainability, research rate, episode learning, goal quality."""
    result = {
        "queue_items_pending": 0,
        "research_bundles_completed": 0,
        "episodes_per_day": 0,
        "goal_non_zombie_rate": 1.0,
    }

    # Queue sustainability: how many pending items
    try:
        import re
        queue_file = os.path.join(WORKSPACE, "memory/evolution/QUEUE.md")
        if os.path.exists(queue_file):
            with open(queue_file) as f:
                content = f.read()
            result["queue_items_pending"] = len(re.findall(r'^- \[ \]', content, re.MULTILINE))
    except Exception:
        pass

    # Research bundles completed (count from queue archive)
    try:
        archive_file = os.path.join(WORKSPACE, "memory/evolution/QUEUE_ARCHIVE.md")
        if os.path.exists(archive_file):
            with open(archive_file) as f:
                content = f.read()
            result["research_bundles_completed"] = len(
                [l for l in content.split("\n") if "Bundle" in l and "[x]" in l]
            )
    except Exception:
        pass

    # Episodes per day (recent)
    try:
        ep_file = os.path.join(WORKSPACE, "data/episodes.json")
        if os.path.exists(ep_file):
            with open(ep_file) as f:
                episodes = json.load(f)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            result["episodes_per_day"] = sum(
                1 for ep in episodes if ep.get("timestamp", "").startswith(today)
            )
    except Exception:
        pass

    # Goal non-zombie rate
    try:
        from brain import brain
        goals = brain.get_goals(include_archived=True)
        if goals:
            non_zombie = sum(
                1 for g in goals
                if g.get("metadata", {}).get("progress", 0) > 0
                or str(g.get("metadata", {}).get("archived", "")).lower() != "true"
            )
            result["goal_non_zombie_rate"] = round(non_zombie / len(goals), 3)
    except Exception:
        pass

    return result


# ============================================================
# QUALITY METRICS (added 2026-03-13) — Beyond binary success
# ============================================================

def benchmark_quality():
    """Quality metrics: task quality, code quality, semantic depth.

    Addresses audit finding that "88% success could mean 88% mediocre".
    These metrics measure HOW WELL we do things, not just completion.
    """
    try:
        from clarvis.metrics.quality import (
            compute_task_quality_score,
            compute_code_quality_score,
            compute_semantic_depth,
        )

        task_quality = compute_task_quality_score(days=7)
        code_quality = compute_code_quality_score(days=7)
        semantic_depth = compute_semantic_depth()

        return {
            "task_quality_score": task_quality.get("quality_score", 0.5),
            "task_quality_components": task_quality.get("components", {}),
            "code_quality_score": code_quality.get("quality_score", 0.5),
            "code_quality_components": code_quality.get("components", {}),
            "semantic_depth_score": semantic_depth.get("depth_score", 0.5),
            "semantic_depth_components": semantic_depth.get("components", {}),
            "raw": {
                "task": task_quality,
                "code": code_quality,
                "semantic": semantic_depth,
            }
        }
    except ImportError as e:
        # Quality module not yet available - return placeholders
        return {
            "task_quality_score": 0.5,
            "code_quality_score": 0.5,
            "semantic_depth_score": 0.5,
            "error": f"quality module not available: {e}",
        }
    except Exception as e:
        return {
            "task_quality_score": 0.5,
            "code_quality_score": 0.5,
            "semantic_depth_score": 0.5,
            "error": str(e),
        }


# ============================================================
# PERFORMANCE INDEX (PI) — imported from clarvis.metrics.benchmark
# ============================================================
# compute_pi() is imported at module top from clarvis.metrics.benchmark


# ============================================================
# SELF-OPTIMIZATION — imported from clarvis.metrics.benchmark
# ============================================================
# check_self_optimization() is imported at module top from clarvis.metrics.benchmark


def write_alerts(alerts):
    """Append alerts to the alerts log."""
    if not alerts:
        return
    timestamp = datetime.now(timezone.utc).isoformat()
    entries = []
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass

    for alert in alerts:
        alert["timestamp"] = timestamp
        entries.append(alert)

    if len(entries) > MAX_ALERTS:
        entries = entries[-MAX_ALERTS:]

    tmp = ALERTS_FILE + ".tmp"
    with open(tmp, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    os.replace(tmp, ALERTS_FILE)


def _safe_bench(fn, name):
    """Run a benchmark function safely, returning empty dict on failure."""
    try:
        result = fn()
        return result if isinstance(result, dict) else {}
    except Exception as e:
        print(f"  WARN: benchmark_{name} failed: {e}", file=sys.stderr)
        return {}


def push_optimization_tasks(alerts):
    """Push critical/high alerts to the evolution queue for autonomous fix."""
    actionable = [a for a in alerts if a.get("severity") in ("critical", "high")]
    if not actionable:
        return 0

    try:
        from queue_writer import add_task
    except ImportError:
        return 0

    added = 0
    for alert in actionable:
        action = alert.get("action", "investigate")
        msg = alert.get("message", "Performance regression detected")
        task_text = f"[PERF] {msg}. Action: {action}"
        try:
            if add_task(task_text, priority="P1", source="performance_benchmark"):
                added += 1
        except Exception:
            pass
    return added


# ============================================================
# MAIN BENCHMARK RUNNERS
# ============================================================

def run_full_benchmark():
    """Run all benchmarks and return unified report with PI.

    Each benchmark is individually wrapped in try/except so one failure
    doesn't prevent others from running. Duplicate calls are eliminated
    by passing pre-computed data to composite benchmarks.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    # Core benchmarks (run once, results shared with composite benchmarks)
    speed = _safe_bench(benchmark_brain_speed, "brain_speed")
    retrieval = _safe_bench(benchmark_retrieval_quality, "retrieval")
    efficiency = _safe_bench(benchmark_efficiency, "efficiency")
    brain_stats = _safe_bench(benchmark_brain_stats, "brain_stats")
    phi = _safe_bench(benchmark_phi, "phi")
    episodes = _safe_bench(benchmark_episodes, "episodes")
    context = _safe_bench(benchmark_context_quality, "context")
    load = _safe_bench(benchmark_load_scaling, "load")

    # Composite benchmarks — pass pre-computed data to avoid duplicate calls
    autonomy = _safe_bench(benchmark_autonomy, "autonomy")
    consciousness = _safe_bench(lambda: benchmark_consciousness(phi_data=phi), "consciousness")
    intelligence = _safe_bench(lambda: benchmark_intelligence(retrieval_data=retrieval, speed_data=speed), "intelligence")
    self_improvement = _safe_bench(benchmark_self_improvement, "self_improvement")

    # Quality metrics (beyond binary success) — added 2026-03-13
    quality = _safe_bench(benchmark_quality, "quality")

    bench_duration = round(time.monotonic() - t0, 2)

    # Flatten key metrics (use .get() with defaults for resilience)
    metrics = {
        "brain_query_avg_ms":   speed.get("avg_ms", 0),
        "brain_query_p95_ms":   speed.get("p95_ms", 0),
        "retrieval_hit_rate":   retrieval.get("hit_rate") or 0.0,  # None → 0.0
        "retrieval_precision3": retrieval.get("precision_at_3") or 0.0,
        "avg_tokens_per_op":    efficiency.get("avg_tokens_per_op"),
        "heartbeat_overhead_s": efficiency.get("heartbeat_overhead_s"),
        "episode_success_rate": episodes["success_rate"],
        "action_accuracy":      episodes.get("action_accuracy", 0.0),
        "phi":                  phi["phi"],
        "context_relevance":    context.get("context_relevance", 0.0),
        "graph_density":        brain_stats["graph_density"],
        "brain_total_memories": brain_stats["total_memories"],
        "bloat_score":          brain_stats.get("bloat_score", 0.0),
        "brief_compression":    context.get("brief_compression", 0.0),
        "load_degradation_pct": load.get("degradation_pct", 0.0),
        # New quality metrics (beyond binary success)
        "task_quality_score":   quality.get("task_quality_score", 0.5),
        "code_quality_score":   quality.get("code_quality_score", 0.5),
    }

    # Evaluate each metric against targets
    results = {}
    for key, meta in TARGETS.items():
        value = metrics.get(key)
        target = meta["target"]
        direction = meta["direction"]

        if value is None or direction == "monitor":
            status = "tracking"
        elif direction == "lower":
            status = "PASS" if value <= target else "FAIL"
        else:
            status = "PASS" if value >= target else "FAIL"

        results[key] = {
            "value": value,
            "target": target,
            "status": status,
            "label": meta["label"],
        }

    pass_count = sum(1 for r in results.values() if r["status"] == "PASS")
    fail_count = sum(1 for r in results.values() if r["status"] == "FAIL")
    total_scored = pass_count + fail_count

    # Compute PI
    pi_data = compute_pi(metrics)

    report = {
        "timestamp": timestamp,
        "bench_duration_s": bench_duration,
        "metrics": metrics,
        "results": results,
        "pi": pi_data,
        "summary": {
            "pass": pass_count,
            "fail": fail_count,
            "total_scored": total_scored,
            "score": round(pass_count / max(total_scored, 1), 3),
            "pi": pi_data["pi"],
        },
        "details": {
            "speed": speed,
            "retrieval": retrieval,
            "efficiency": efficiency,
            "brain_stats": brain_stats,
            "phi": phi,
            "episodes": episodes,
            "context": context,
            "load": load,
            "autonomy": autonomy,
            "consciousness": consciousness,
            "intelligence": intelligence,
            "self_improvement": self_improvement,
            "quality": quality,  # Beyond binary success
        },
    }

    return report


def run_quick_benchmark():
    """Fast subset: brain speed + stats + PI estimate (~2s)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    speed = benchmark_brain_speed()
    brain_stats = benchmark_brain_stats()

    # Quick PI estimate from available metrics
    quick_metrics = {
        "brain_query_avg_ms": speed["avg_ms"],
        "brain_query_p95_ms": speed["p95_ms"],
        "graph_density": brain_stats["graph_density"],
        "bloat_score": brain_stats.get("bloat_score", 0.0),
    }
    pi_data = compute_pi(quick_metrics)

    duration = round(time.monotonic() - t0, 2)

    return {
        "timestamp": timestamp,
        "type": "quick",
        "bench_duration_s": duration,
        "speed": speed,
        "brain_stats": brain_stats,
        "pi_estimate": pi_data,
    }


def run_heartbeat_check():
    """Lightweight check for heartbeat integration.

    Returns JSON with quick health indicators. Designed to run in <3s.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    from brain import brain

    # Quick speed check (3 queries only)
    brain.recall("warmup", n=1)
    timings = []
    for q in TIMING_QUERIES[:3]:
        t = time.monotonic()
        brain.recall(q, n=3)
        timings.append(round((time.monotonic() - t) * 1000, 2))

    avg_ms = round(sum(timings) / len(timings), 2)

    # Quick stats
    stats = brain.stats()
    total_mem = stats["total_memories"]
    density = round(stats["graph_edges"] / max(total_mem, 1), 2)

    # Load previous PI
    prev_pi = None
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE) as f:
                prev = json.load(f)
            prev_pi = prev.get("pi", {}).get("pi")
        except Exception:
            pass

    duration = round(time.monotonic() - t0, 2)

    return {
        "timestamp": timestamp,
        "type": "heartbeat",
        "duration_s": duration,
        "brain_query_avg_ms": avg_ms,
        "brain_memories": total_mem,
        "graph_density": density,
        "prev_pi": prev_pi,
        "speed_ok": avg_ms < TARGETS["brain_query_avg_ms"]["critical"],
    }


# ============================================================
# RECORDING & TRENDS
# ============================================================

def record(report=None):
    """Record benchmark to history and check for self-optimization."""
    if report is None:
        report = run_full_benchmark()

    # Load previous report for comparison (with staleness guard)
    prev_report = None
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE) as f:
                prev_report = json.load(f)
            # Staleness guard: skip regression comparison if prev_report > 3 days old
            prev_ts = prev_report.get("timestamp", "")
            if prev_ts:
                from datetime import datetime as _dt
                try:
                    prev_time = _dt.fromisoformat(prev_ts.replace("Z", "+00:00"))
                    age = datetime.now(timezone.utc) - prev_time
                    if age.total_seconds() > 3 * 86400:
                        prev_report = None  # Too stale for regression comparison
                except (ValueError, TypeError):
                    prev_report = None
        except Exception:
            pass

    # Write latest snapshot
    with open(METRICS_FILE, "w") as f:
        json.dump(report, f, indent=2)

    # Append to history
    entry = {
        "timestamp": report["timestamp"],
        "metrics": report["metrics"],
        "summary": report.get("summary", {}),
        "pi": report.get("pi", {}),
    }

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        parsed = json.loads(line)
                        # Filter out foreign entries (e.g. structural_health)
                        if parsed.get("type") and parsed["type"] != "performance":
                            continue
                        history.append(parsed)
                    except json.JSONDecodeError:
                        continue

    history.append(entry)
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    tmp = HISTORY_FILE + ".tmp"
    with open(tmp, "w") as f:
        for h in history:
            f.write(json.dumps(h) + "\n")
    os.replace(tmp, HISTORY_FILE)

    # Self-optimization check
    alerts = check_self_optimization(report, prev_report)
    if alerts:
        write_alerts(alerts)
        pushed = push_optimization_tasks(alerts)
        report["_alerts"] = alerts
        report["_optimization_tasks_pushed"] = pushed

    return report


def show_trend(days=30):
    """Show performance trend with PI trajectory."""
    if not os.path.exists(HISTORY_FILE):
        return {"error": "No history yet. Run 'record' first."}

    history = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    # Skip foreign entries (e.g. structural_health) that lack performance metrics
                    if entry.get("type") and entry["type"] != "performance":
                        continue
                    history.append(entry)
                except json.JSONDecodeError:
                    continue

    if not history:
        return {"error": "Empty history."}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    recent = [h for h in history if h["timestamp"] >= cutoff]

    if not recent:
        recent = history[-5:]

    # Metric trends
    trends = {}
    for key in TARGETS:
        values = [v for h in recent for v in [h.get("metrics", {}).get(key)] if v is not None]
        if len(values) < 2:
            trends[key] = {"trend": "insufficient_data", "values": values}
            continue

        first_half = values[:len(values) // 2]
        second_half = values[len(values) // 2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 4)

        direction = TARGETS[key]["direction"]
        if direction == "lower":
            improving = delta < 0
        elif direction == "higher":
            improving = delta > 0
        else:
            improving = None

        trends[key] = {
            "trend": "improving" if improving else ("degrading" if improving is False else "stable"),
            "delta": delta,
            "latest": values[-1],
            "earliest": values[0],
            "n_points": len(values),
        }

    # PI trajectory
    pi_values = [h.get("pi", {}).get("pi", 0) for h in recent if h.get("pi")]
    pi_trend = None
    if len(pi_values) >= 2:
        first_pi = sum(pi_values[:len(pi_values)//2]) / len(pi_values[:len(pi_values)//2])
        last_pi = sum(pi_values[len(pi_values)//2:]) / len(pi_values[len(pi_values)//2:])
        pi_delta = round(last_pi - first_pi, 4)
        pi_trend = {
            "trend": "improving" if pi_delta > 0 else ("degrading" if pi_delta < 0 else "stable"),
            "delta": pi_delta,
            "latest": pi_values[-1],
            "earliest": pi_values[0],
            "n_points": len(pi_values),
        }

    return {
        "period_days": days,
        "n_entries": len(recent),
        "trends": trends,
        "pi_trend": pi_trend,
        "first_timestamp": recent[0]["timestamp"],
        "last_timestamp": recent[-1]["timestamp"],
    }


# ============================================================
# PRETTY PRINTING
# ============================================================

def print_report(report):
    """Pretty-print a full benchmark report."""
    print("=" * 65)
    print("  CLARVIS PERFORMANCE BENCHMARK")
    print(f"  {report['timestamp'][:19]} UTC  ({report.get('bench_duration_s', '?')}s)")
    print("=" * 65)

    # PI header
    pi_data = report.get("pi", {})
    pi = pi_data.get("pi", 0)
    interp = pi_data.get("interpretation", "")
    bar_len = int(pi * 20)
    bar = "#" * bar_len + "." * (20 - bar_len)
    print(f"\n  Performance Index (PI): {pi:.4f}  [{bar}]")
    print(f"  {interp}")

    # Results table
    print(f"\n  {'Metric':<32s} {'Value':>10s}  {'Target':>10s}  Status")
    print("  " + "-" * 61)

    results = report.get("results", {})
    for key, r in results.items():
        status = r["status"]
        value = r["value"]
        target = r["target"]
        label = r["label"]

        if status == "PASS":
            icon = "[PASS]"
        elif status == "FAIL":
            icon = "[FAIL]"
        else:
            icon = "[----]"

        val_str = f"{value}" if value is not None else "N/A"
        tgt_str = f"{target}" if target is not None else "monitor"
        print(f"  {label:<32s} {val_str:>10s}  {tgt_str:>10s}  {icon}")

    # Summary
    summary = report.get("summary", {})
    print("\n  " + "-" * 61)
    score_pct = round(summary.get("score", 0) * 100)
    print(f"  Score: {summary.get('pass', 0)}/{summary.get('total_scored', 0)} "
          f"passed ({score_pct}%)  |  PI: {pi:.4f}")

    # Speed breakdown
    speed = report.get("details", {}).get("speed", {})
    if speed:
        print(f"\n  Speed: Avg={speed['avg_ms']:.1f}ms  "
              f"P50={speed['p50_ms']:.1f}ms  "
              f"P95={speed['p95_ms']:.1f}ms  "
              f"Max={speed['max_ms']:.1f}ms")
        print(f"    Slowest: \"{speed.get('slowest_query', 'N/A')}\"")

    # Brain
    bs = report.get("details", {}).get("brain_stats", {})
    if bs:
        print(f"\n  Brain: {bs['total_memories']} memories, "
              f"{bs['graph_edges']} edges, "
              f"density={bs['graph_density']}, "
              f"bloat={bs.get('bloat_score', 0):.2f}")

    # Phi
    phi_d = report.get("details", {}).get("phi", {})
    if phi_d and "phi" in phi_d:
        print(f"  Phi: {phi_d['phi']:.4f} — {phi_d.get('interpretation', '')}")

    # Episodes
    ep = report.get("details", {}).get("episodes", {})
    if ep and ep.get("total_episodes"):
        print(f"\n  Episodes: {ep['total_episodes']} total, "
              f"{ep['success_rate']*100:.0f}% success, "
              f"{ep.get('action_accuracy', 0)*100:.0f}% action accuracy")
        outcomes = ep.get("outcomes", {})
        if outcomes:
            parts = [f"{k}={v}" for k, v in outcomes.items()]
            print(f"    Outcomes: {', '.join(parts)}")

    # Load scaling
    load = report.get("details", {}).get("load", {})
    if load:
        print(f"\n  Load: base={load.get('base_ms', '?')}ms, "
              f"peak(n=10)={load.get('peak_ms', '?')}ms, "
              f"degradation={load.get('degradation_pct', '?')}%")

    # Alerts
    alerts = report.get("_alerts", [])
    if alerts:
        print(f"\n  ALERTS ({len(alerts)}):")
        for a in alerts:
            print(f"    [{a['severity'].upper()}] {a['message']}")

    print("=" * 65)


def print_trend(trend_data):
    """Pretty-print trend data with PI trajectory."""
    if "error" in trend_data:
        print(f"Error: {trend_data['error']}")
        return

    print(f"Performance Trend ({trend_data['period_days']}d, "
          f"{trend_data['n_entries']} entries)")
    print(f"  From: {trend_data['first_timestamp'][:19]}")
    print(f"  To:   {trend_data['last_timestamp'][:19]}")

    # PI trend
    pi_trend = trend_data.get("pi_trend")
    if pi_trend:
        arrow = "^" if pi_trend["trend"] == "improving" else ("v" if pi_trend["trend"] == "degrading" else "-")
        print(f"\n  PI Trajectory: [{arrow}] {pi_trend['earliest']:.4f} -> {pi_trend['latest']:.4f} "
              f"(delta: {pi_trend['delta']:+.4f})")

    print("-" * 55)

    for key, t in trend_data.get("trends", {}).items():
        label = TARGETS.get(key, {}).get("label", key)
        trend = t["trend"]
        if trend == "improving":
            icon = "^"
        elif trend == "degrading":
            icon = "v"
        elif trend == "insufficient_data":
            icon = "?"
        else:
            icon = "-"

        latest = t.get("latest", "?")
        delta = t.get("delta", 0)
        delta_str = f"({delta:+.4f})" if isinstance(delta, (int, float)) else ""
        print(f"  [{icon}] {label:32s} {str(latest):>10}  {delta_str}")


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("DEPRECATION: Use 'python3 -m clarvis bench <command>' instead of 'python3 scripts/performance_benchmark.py'.", file=sys.stderr)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd in ("run", "full"):
        report = run_full_benchmark()
        print_report(report)

    elif cmd == "quick":
        report = run_quick_benchmark()
        print(json.dumps(report, indent=2))

    elif cmd == "record":
        report = record()
        print_report(report)
        print(f"\nRecorded to {METRICS_FILE}")
        print(f"Appended to {HISTORY_FILE}")
        alerts = report.get("_alerts", [])
        if alerts:
            print(f"Self-optimization: {len(alerts)} alert(s), "
                  f"{report.get('_optimization_tasks_pushed', 0)} task(s) pushed")

    elif cmd == "trend":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        trend_data = show_trend(days)
        print_trend(trend_data)

    elif cmd == "check":
        report = run_full_benchmark()
        print_report(report)
        fails = report["summary"]["fail"]
        if fails:
            print(f"\n{fails} metric(s) below target.")
            sys.exit(1)
        else:
            print("\nAll metrics within targets.")

    elif cmd == "heartbeat":
        result = run_heartbeat_check()
        print(json.dumps(result))

    elif cmd == "pi":
        fresh = "--fresh" in sys.argv
        if not fresh and os.path.exists(METRICS_FILE):
            # Fast path: read cached PI from last recorded benchmark
            try:
                with open(METRICS_FILE) as f:
                    stored = json.load(f)
                pi = stored.get("pi", {})
                ts = stored.get("timestamp", "?")[:19]
                age_h = 0
                try:
                    from datetime import datetime as _dt
                    stored_time = _dt.fromisoformat(ts.replace("Z", "+00:00") if "Z" in ts else ts)
                    age_h = (datetime.now(timezone.utc) - stored_time.replace(
                        tzinfo=timezone.utc) if stored_time.tzinfo is None else stored_time
                    ).total_seconds() / 3600
                except Exception:
                    pass
                pi_val = pi.get("pi", 0)
                interp = pi.get("interpretation", "")
                stale = " (stale — use --fresh)" if age_h > 48 else ""
                print(f"PI: {pi_val:.4f} — {interp}")
                print(f"  Last recorded: {ts} ({age_h:.0f}h ago){stale}")
                sys.exit(0)
            except Exception:
                pass
        # Fresh computation
        report = run_full_benchmark()
        pi = report.get("pi", {})
        print(f"PI: {pi.get('pi', 0):.4f} — {pi.get('interpretation', '')}")

    elif cmd == "weakest":
        # Fast: reads last recorded metrics, no re-benchmark
        if os.path.exists(METRICS_FILE):
            with open(METRICS_FILE) as f:
                stored = json.load(f)
            metrics = stored.get("metrics", {})
            # Compute margin-to-target ratio for each scored metric
            worst_name, worst_margin = None, float("inf")
            for key, meta in TARGETS.items():
                target = meta.get("target")
                if target is None or meta.get("direction") == "monitor":
                    continue
                val = metrics.get(key)
                if val is None:
                    continue
                if meta["direction"] == "higher":
                    margin = (val - target) / max(target, 0.001)
                else:  # lower is better
                    margin = (target - val) / max(target, 0.001)
                if margin < worst_margin:
                    worst_margin = margin
                    worst_name = key
            if worst_name:
                meta = TARGETS[worst_name]
                val = metrics[worst_name]
                print(f"{meta['label']}={val:.3f} (target: {meta['target']})")
            else:
                print("unknown")
        else:
            print("unknown")

    else:
        print(__doc__)
        sys.exit(1)
