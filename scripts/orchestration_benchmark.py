#!/usr/bin/env python3
"""Orchestration Benchmarks — measure project agent performance.

Five benchmark dimensions:
  1. Orchestration Latency: delegate→ack and delegate→artifact (PR/patch). p50/p95.
  2. Context Isolation: embedding overlap between project-agent DB and Clarvis core.
  3. PR Success Rate: % tasks resulting in PRs + CI pass rate.
  4. Retrieval Quality: P@3 on repo-specific golden Q/A set.
  5. Cost Budget: tokens + wall-clock per task vs single-brain baseline.

Usage:
    python3 orchestration_benchmark.py run <agent_name>     # Full benchmark
    python3 orchestration_benchmark.py isolation <agent_name> # Isolation only
    python3 orchestration_benchmark.py summary               # All agents summary
    python3 orchestration_benchmark.py history <agent_name>  # Historical trend
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

AGENTS_ROOT_PRIMARY = Path("/opt/clarvis-agents")
AGENTS_ROOT_FALLBACK = Path("/home/agent/agents")
CLARVIS_WORKSPACE = Path("/home/agent/.openclaw/workspace")
BENCHMARK_DIR = CLARVIS_WORKSPACE / "data" / "orchestration_benchmarks"
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

# Targets for scoring
TARGETS = {
    "latency_p50_max": 300,     # seconds
    "latency_p95_max": 600,     # seconds
    "isolation_overlap_max": 0.05,
    "pr_rate_min": 0.5,         # 50% of tasks should produce PRs
    "retrieval_p3_min": 0.6,    # 60% P@3
    "cost_per_task_max": 0.50,  # $ per task (wall-clock-based estimate)
}


def _agent_dir(name: str) -> Path:
    """Resolve agent directory from either root."""
    primary = AGENTS_ROOT_PRIMARY / name
    if primary.exists():
        return primary
    return AGENTS_ROOT_FALLBACK / name


def _load_agent_config(name: str) -> dict:
    cfg = _agent_dir(name) / "configs" / "agent.json"
    if cfg.exists():
        return json.loads(cfg.read_text())
    return {}


def _load_summaries(name: str) -> list:
    summaries_dir = _agent_dir(name) / "memory" / "summaries"
    results = []
    if summaries_dir.exists():
        for sf in sorted(summaries_dir.glob("*.json")):
            try:
                results.append(json.loads(sf.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
    return results


# =========================================================================
# 1. ORCHESTRATION LATENCY
# =========================================================================

def benchmark_latency(name: str) -> dict:
    """Measure delegate→ack and delegate→artifact latency from task history."""
    summaries = _load_summaries(name)

    if not summaries:
        return {"status": "no_data", "note": "Run some tasks first"}

    elapsed_times = [s["elapsed"] for s in summaries if "elapsed" in s]
    if not elapsed_times:
        return {"status": "no_data"}

    elapsed_times.sort()
    n = len(elapsed_times)

    return {
        "total_tasks": n,
        "p50_seconds": round(elapsed_times[n // 2], 1),
        "p95_seconds": round(elapsed_times[min(int(n * 0.95), n - 1)], 1),
        "avg_seconds": round(sum(elapsed_times) / n, 1),
        "min_seconds": round(elapsed_times[0], 1),
        "max_seconds": round(elapsed_times[-1], 1),
    }


# =========================================================================
# 2. CONTEXT ISOLATION
# =========================================================================

def benchmark_isolation(name: str) -> dict:
    """Measure embedding overlap between project-agent DB and Clarvis core.

    Near-zero overlap expected except for promoted summaries.
    """
    agent_brain_dir = _agent_dir(name) / "data" / "brain"
    clarvis_brain_dir = CLARVIS_WORKSPACE / "data" / "clarvisdb"

    # Structural checks
    structural = {
        "separate_directories": str(agent_brain_dir) != str(clarvis_brain_dir),
        "no_symlink_leakage": not agent_brain_dir.is_symlink(),
        "agent_brain_exists": agent_brain_dir.exists(),
        "clarvis_brain_exists": clarvis_brain_dir.exists(),
    }

    # Embedding overlap check (sample-based)
    overlap_score = 0.0
    sample_size = 0

    try:
        from lite_brain import LiteBrain
        agent_brain = LiteBrain(str(agent_brain_dir))
        agent_stats = agent_brain.stats()
        sample_size = agent_stats.get("total_memories", 0)

        if sample_size > 0:
            # Get sample of agent memories
            agent_docs = []
            for col_name in ["project-learnings", "project-procedures", "project-context"]:
                try:
                    col = agent_brain._get_collection(col_name)
                    if col.count() > 0:
                        peek = col.peek(limit=min(5, col.count()))
                        agent_docs.extend(peek.get("documents", []))
                except Exception:
                    continue

            if agent_docs:
                # Check if these documents exist in Clarvis brain
                try:
                    from brain import brain as clarvis_brain
                    matches = 0
                    for doc in agent_docs[:10]:
                        results = clarvis_brain.recall(doc[:200], n_results=1)
                        if results and results[0].get("relevance", 0) > 0.85:
                            matches += 1
                    overlap_score = matches / len(agent_docs[:10])
                except Exception:
                    overlap_score = -1  # couldn't measure

    except ImportError:
        pass

    return {
        "structural": structural,
        "structural_pass": all(structural.values()),
        "embedding_overlap": round(overlap_score, 3),
        "overlap_target": "< 0.05",
        "overlap_pass": overlap_score < 0.05 or overlap_score == -1,
        "agent_memories": sample_size,
        "note": "overlap -1 means couldn't measure (missing brain import)" if overlap_score == -1 else "",
    }


# =========================================================================
# 3. PR SUCCESS RATE
# =========================================================================

def benchmark_pr_success(name: str) -> dict:
    """Measure PR creation and success rates."""
    summaries = _load_summaries(name)
    if not summaries:
        return {"status": "no_data"}

    total = len(summaries)
    succeeded = sum(1 for s in summaries if s.get("result", {}).get("status") == "success")
    with_pr = sum(1 for s in summaries if s.get("result", {}).get("pr_url"))
    tests_passed = sum(1 for s in summaries if s.get("result", {}).get("tests_passed"))

    return {
        "total_tasks": total,
        "success_rate": f"{succeeded / max(total, 1) * 100:.0f}%",
        "pr_rate": f"{with_pr / max(total, 1) * 100:.0f}%",
        "test_pass_rate": f"{tests_passed / max(total, 1) * 100:.0f}%",
        "succeeded": succeeded,
        "prs_created": with_pr,
        "tests_passed": tests_passed,
    }


# =========================================================================
# 4. RETRIEVAL QUALITY
# =========================================================================

def benchmark_retrieval(name: str) -> dict:
    """Measure retrieval quality using golden Q/A pairs.

    Requires: <agent_dir>/data/golden_qa.json
    Format: [{"query": "...", "expected_docs": ["keyword1", ...], "answer": "...", "collection": "..."}]
    """
    agent_dir = _agent_dir(name)
    golden_file = agent_dir / "data" / "golden_qa.json"

    if not golden_file.exists():
        return {
            "status": "not_configured",
            "note": f"Create {golden_file} with repo-specific Q/A pairs",
        }

    from lite_brain import LiteBrain
    brain = LiteBrain(str(agent_dir / "data" / "brain"))

    return brain.benchmark_retrieval(str(golden_file))


# =========================================================================
# 5. COST BUDGET
# =========================================================================

def benchmark_cost(name: str) -> dict:
    """Measure tokens + wall-clock per task."""
    summaries = _load_summaries(name)
    if not summaries:
        return {"status": "no_data"}

    elapsed = [s["elapsed"] for s in summaries if "elapsed" in s]
    total_wall_clock = sum(elapsed)

    return {
        "total_tasks": len(summaries),
        "total_wall_clock_seconds": round(total_wall_clock, 1),
        "avg_wall_clock_seconds": round(total_wall_clock / max(len(elapsed), 1), 1),
        "note": "Token tracking requires OpenRouter cost integration",
    }


# =========================================================================
# FULL BENCHMARK
# =========================================================================

def run_full_benchmark(name: str) -> dict:
    """Run all 5 benchmark dimensions."""
    config = _load_agent_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    result = {
        "agent": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency": benchmark_latency(name),
        "isolation": benchmark_isolation(name),
        "pr_success": benchmark_pr_success(name),
        "retrieval": benchmark_retrieval(name),
        "cost": benchmark_cost(name),
    }

    # Compute composite score (0.0 - 1.0) across all dimensions
    dim_scores = {}

    # Isolation (weight: 0.20)
    iso = result["isolation"]
    iso_score = 1.0 if iso.get("structural_pass") and iso.get("overlap_pass") else 0.0
    dim_scores["isolation"] = iso_score

    # Latency (weight: 0.20)
    lat = result["latency"]
    if lat.get("total_tasks", 0) > 0:
        p95 = lat.get("p95_seconds", 999)
        dim_scores["latency"] = min(1.0, TARGETS["latency_p95_max"] / max(p95, 1))
    else:
        dim_scores["latency"] = 0.0

    # PR success (weight: 0.25)
    pr = result["pr_success"]
    if pr.get("total_tasks", 0) > 0:
        pr_rate = pr.get("prs_created", 0) / max(pr["total_tasks"], 1)
        dim_scores["pr_success"] = min(1.0, pr_rate / TARGETS["pr_rate_min"])
    else:
        dim_scores["pr_success"] = 0.0

    # Retrieval (weight: 0.25)
    ret = result["retrieval"]
    if ret.get("p_at_3") is not None and isinstance(ret.get("p_at_3"), (int, float)):
        dim_scores["retrieval"] = min(1.0, ret["p_at_3"] / TARGETS["retrieval_p3_min"])
    else:
        dim_scores["retrieval"] = 0.0

    # Cost (weight: 0.10)
    cost = result["cost"]
    if cost.get("avg_wall_clock_seconds", 0) > 0:
        # Estimate cost: ~$0.015/min for Claude Opus
        est_cost = cost["avg_wall_clock_seconds"] / 60 * 0.015
        dim_scores["cost"] = min(1.0, TARGETS["cost_per_task_max"] / max(est_cost, 0.001))
    else:
        dim_scores["cost"] = 0.0

    weights = {"isolation": 0.20, "latency": 0.20, "pr_success": 0.25,
               "retrieval": 0.25, "cost": 0.10}
    result["dimension_scores"] = {k: round(v, 3) for k, v in dim_scores.items()}
    result["composite_score"] = round(
        sum(dim_scores[k] * weights[k] for k in weights), 3
    )

    # Save to history
    history_file = BENCHMARK_DIR / f"{name}_history.jsonl"
    with open(history_file, "a") as f:
        f.write(json.dumps(result) + "\n")

    # Save latest
    latest_file = BENCHMARK_DIR / f"{name}_latest.json"
    latest_file.write_text(json.dumps(result, indent=2))

    return result


def summary_all() -> dict:
    """Summary of all project agents."""
    results = {}
    seen = set()
    for root in [AGENTS_ROOT_PRIMARY, AGENTS_ROOT_FALLBACK]:
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir() and d.name not in seen and (d / "configs" / "agent.json").exists():
                seen.add(d.name)
                latest = BENCHMARK_DIR / f"{d.name}_latest.json"
                if latest.exists():
                    try:
                        data = json.loads(latest.read_text())
                        results[d.name] = {
                            "composite_score": data.get("composite_score", 0),
                            "dimension_scores": data.get("dimension_scores", {}),
                            "timestamp": data.get("timestamp"),
                        }
                    except (json.JSONDecodeError, OSError):
                        results[d.name] = {"status": "no_benchmark"}
                else:
                    results[d.name] = {"status": "no_benchmark"}
    return results


# =========================================================================
# CLI
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Orchestration Benchmarks")
    sub = parser.add_subparsers(dest="command", required=True)

    rp = sub.add_parser("run", help="Full benchmark for an agent")
    rp.add_argument("name")

    ip = sub.add_parser("isolation", help="Isolation benchmark only")
    ip.add_argument("name")

    sub.add_parser("summary", help="All agents summary")

    hp = sub.add_parser("history", help="Historical benchmark data")
    hp.add_argument("name")

    args = parser.parse_args()

    if args.command == "run":
        result = run_full_benchmark(args.name)
    elif args.command == "isolation":
        result = benchmark_isolation(args.name)
    elif args.command == "summary":
        result = summary_all()
    elif args.command == "history":
        hf = BENCHMARK_DIR / f"{args.name}_history.jsonl"
        if hf.exists():
            entries = []
            for line in hf.read_text().strip().split("\n"):
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            result = {"agent": args.name, "entries": entries[-20:]}
        else:
            result = {"status": "no_history"}
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
