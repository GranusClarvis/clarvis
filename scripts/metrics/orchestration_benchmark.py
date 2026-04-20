#!/usr/bin/env python3
"""Orchestration Benchmark — per-agent 5-dimension composite scoring.

Called by cron_orchestrator.sh (Stage 3) for each active project agent.
Computes isolation, latency, PR success, retrieval, and cost scores,
then writes results to data/orchestration_benchmarks/<agent>_latest.json
and appends to <agent>_history.jsonl.

Dimensions and weights (from MEMORY.md):
  isolation  0.20 — structural separation from Clarvis brain
  latency    0.20 — task execution speed (p50, p95 targets)
  pr_success 0.25 — task success rate + PR creation rate
  retrieval  0.25 — golden QA retrieval quality (P@1, P@3, MRR)
  cost       0.10 — cost efficiency (wall-clock estimate)

Usage:
    python3 orchestration_benchmark.py run <agent>
    python3 orchestration_benchmark.py run-all
    python3 orchestration_benchmark.py show <agent>
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE",
                                os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))))
SCRIPTS = WORKSPACE / "scripts"
DATA_DIR = WORKSPACE / "data" / "orchestration_benchmarks"

# Dimension weights
WEIGHTS = {
    "isolation":  0.20,
    "latency":    0.20,
    "pr_success": 0.25,
    "retrieval":  0.25,
    "cost":       0.10,
}

# Thresholds
LATENCY_P50_TARGET = 300.0   # seconds — p50 should be under this
LATENCY_P95_TARGET = 900.0   # seconds — p95 should be under this
COST_PER_TASK_TARGET = 0.50  # USD — avg cost per task target



def _get_agent_dir(name: str) -> Path:
    """Resolve agent directory (same logic as project_agent.py)."""
    primary = Path("/opt/clarvis-agents") / name
    fallback = Path("~/agents").expanduser() / name
    if primary.exists():
        return primary
    return fallback


def _load_config(name: str) -> dict:
    """Load agent config.json."""
    agent_dir = _get_agent_dir(name)
    config_file = agent_dir / "configs" / "agent.json"
    if config_file.exists():
        return json.loads(config_file.read_text())
    return {}


def _score_isolation(name: str) -> tuple[float, dict]:
    """Score isolation dimension (0.0 - 1.0)."""
    agent_dir = _get_agent_dir(name)
    clarvis_brain = WORKSPACE / "data" / "clarvisdb"
    agent_brain = agent_dir / "data" / "brain"

    clarvis_path = str(clarvis_brain.resolve()) if clarvis_brain.exists() else ""
    agent_path = str(agent_brain.resolve()) if agent_brain.exists() else ""

    paths_isolated = bool(
        clarvis_path and agent_path
        and not agent_path.startswith(clarvis_path)
        and not clarvis_path.startswith(agent_path)
    )

    # Structural checks
    checks = {
        "separate_directories": paths_isolated,
        "no_symlink_leakage": not agent_brain.is_symlink() if agent_brain.exists() else True,
        "agent_brain_exists": agent_brain.exists(),
        "clarvis_brain_exists": clarvis_brain.exists(),
    }

    passed = sum(1 for v in checks.values() if v)
    score = passed / len(checks)

    details = {
        "structural": checks,
        "structural_pass": all(checks.values()),
        "embedding_overlap": -1,
        "overlap_target": "< 0.05",
        "overlap_pass": True,  # assume pass when can't measure
        "agent_brain": agent_path,
        "note": "overlap -1 means couldn't measure (missing brain import)",
    }

    # Try to count agent memories
    try:
        from clarvis._script_loader import load as _load_script
        LiteBrain = _load_script("lite_brain", "brain_mem").LiteBrain
        lb = LiteBrain(str(agent_brain))
        details["agent_memories"] = lb.stats().get("total_memories", 0)
    except Exception:
        details["agent_memories"] = -1

    return score, details


def _score_latency(name: str) -> tuple[float, dict]:
    """Score latency dimension (0.0 - 1.0)."""
    agent_dir = _get_agent_dir(name)
    summaries_dir = agent_dir / "memory" / "summaries"

    elapsed_times = []
    if summaries_dir.exists():
        for sf in summaries_dir.glob("*.json"):
            try:
                s = json.loads(sf.read_text())
                if "elapsed" in s:
                    elapsed_times.append(float(s["elapsed"]))
            except (json.JSONDecodeError, OSError, ValueError):
                continue

    config = _load_config(name)
    total_tasks = config.get("total_tasks", len(elapsed_times))

    if not elapsed_times:
        return 0.5, {
            "total_tasks": total_tasks,
            "p50_seconds": 0,
            "p95_seconds": 0,
            "avg_seconds": 0,
            "note": "no elapsed data available",
        }

    elapsed_sorted = sorted(elapsed_times)
    p50 = elapsed_sorted[len(elapsed_sorted) // 2]
    p95_idx = min(int(len(elapsed_sorted) * 0.95), len(elapsed_sorted) - 1)
    p95 = elapsed_sorted[p95_idx]
    avg = sum(elapsed_times) / len(elapsed_times)

    # Score: 1.0 if both p50 and p95 under target, degrade linearly
    p50_score = min(1.0, max(0.0, 1.0 - (p50 - LATENCY_P50_TARGET) / LATENCY_P50_TARGET)) if p50 > LATENCY_P50_TARGET else 1.0
    p95_score = min(1.0, max(0.0, 1.0 - (p95 - LATENCY_P95_TARGET) / LATENCY_P95_TARGET)) if p95 > LATENCY_P95_TARGET else 1.0
    score = round((p50_score * 0.6 + p95_score * 0.4), 3)

    return score, {
        "total_tasks": total_tasks,
        "p50_seconds": round(p50, 1),
        "p95_seconds": round(p95, 1),
        "avg_seconds": round(avg, 1),
        "min_seconds": round(min(elapsed_times), 1),
        "max_seconds": round(max(elapsed_times), 1),
    }


def _score_pr_success(name: str) -> tuple[float, dict]:
    """Score PR success dimension (0.0 - 1.0)."""
    config = _load_config(name)
    total = config.get("total_tasks", 0)
    successes = config.get("total_successes", 0)

    agent_dir = _get_agent_dir(name)
    summaries_dir = agent_dir / "memory" / "summaries"

    pr_count = 0
    tests_passed = 0
    if summaries_dir.exists():
        for sf in summaries_dir.glob("*.json"):
            try:
                s = json.loads(sf.read_text())
                result = s.get("result", {})
                if result.get("pr_url"):
                    pr_count += 1
                if result.get("tests_passed"):
                    tests_passed += 1
            except (json.JSONDecodeError, OSError):
                continue

    if total == 0:
        return 0.0, {
            "total_tasks": 0,
            "success_rate": "0%",
            "pr_rate": "0%",
            "test_pass_rate": "0%",
            "note": "no tasks yet",
        }

    success_rate = successes / total
    pr_rate = pr_count / total
    test_rate = tests_passed / max(total, 1)

    # Composite: 50% success rate, 30% PR rate, 20% test rate
    score = round(success_rate * 0.5 + pr_rate * 0.3 + test_rate * 0.2, 3)

    return score, {
        "total_tasks": total,
        "success_rate": f"{success_rate * 100:.0f}%",
        "pr_rate": f"{pr_rate * 100:.0f}%",
        "test_pass_rate": f"{test_rate * 100:.0f}%",
        "succeeded": successes,
        "prs_created": pr_count,
        "tests_passed": tests_passed,
    }


def _score_retrieval(name: str) -> tuple[float, dict]:
    """Score retrieval dimension using golden QA (0.0 - 1.0)."""
    agent_dir = _get_agent_dir(name)
    golden_file = agent_dir / "data" / "golden_qa.json"

    if not golden_file.exists():
        return 0.5, {
            "status": "not_configured",
            "note": "Create data/golden_qa.json with repo-specific Q/A pairs to enable",
        }

    try:
        qa_pairs = json.loads(golden_file.read_text())
    except Exception as e:
        return 0.0, {"status": "error", "error": str(e)}

    if not qa_pairs:
        return 0.5, {"status": "empty", "note": "golden_qa.json has no entries"}

    try:
        from lite_brain import LiteBrain
        brain = LiteBrain(str(agent_dir / "data" / "brain"))
    except Exception as e:
        return 0.0, {"status": "error", "error": f"Cannot load brain: {e}"}

    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks = []
    details_list = []

    for qa in qa_pairs:
        query = qa.get("query", "")
        expected = [e.lower() for e in qa.get("expected_docs", [])]
        collection = qa.get("collection")

        try:
            results = brain.recall(query, n_results=5, collection=collection)
            docs = [(r.get("document") or r.get("text") or "").lower()
                    for r in results] if results else []
        except Exception:
            docs = []

        found_rank = None
        for rank, doc in enumerate(docs):
            if any(exp in doc for exp in expected):
                found_rank = rank + 1
                break

        hit1 = found_rank == 1 if found_rank else False
        hit3 = found_rank is not None and found_rank <= 3
        rr = 1.0 / found_rank if found_rank else 0.0

        if found_rank is not None:
            reciprocal_ranks.append(rr)
            if found_rank <= 1:
                hits_at_1 += 1
                hits_at_3 += 1
            elif found_rank <= 3:
                hits_at_3 += 1
        else:
            reciprocal_ranks.append(0.0)

        details_list.append({
            "query": query[:80],
            "hit_at_1": hit1,
            "hit_at_3": hit3,
            "rr": round(rr, 3),
        })

    total = len(qa_pairs)
    p_at_1 = hits_at_1 / total if total else 0
    p_at_3 = hits_at_3 / total if total else 0
    mrr = sum(reciprocal_ranks) / total if total else 0

    # Score: weighted combination of MRR and P@3
    score = round(mrr * 0.6 + p_at_3 * 0.4, 3)
    # Pass if MRR >= 0.5
    passing = mrr >= 0.5

    return score, {
        "total_queries": total,
        "p_at_1": round(p_at_1, 3),
        "p_at_3": round(p_at_3, 3),
        "mrr": round(mrr, 3),
        "pass": passing,
        "details": details_list,
    }


def _score_cost(name: str) -> tuple[float, dict]:
    """Score cost efficiency dimension (0.0 - 1.0)."""
    agent_dir = _get_agent_dir(name)
    summaries_dir = agent_dir / "memory" / "summaries"
    config = _load_config(name)
    total_tasks = config.get("total_tasks", 0)

    elapsed_times = []
    if summaries_dir.exists():
        for sf in summaries_dir.glob("*.json"):
            try:
                s = json.loads(sf.read_text())
                if "elapsed" in s:
                    elapsed_times.append(float(s["elapsed"]))
            except (json.JSONDecodeError, OSError, ValueError):
                continue

    total_wall = sum(elapsed_times)
    avg_wall = total_wall / len(elapsed_times) if elapsed_times else 0

    # Estimate cost: ~$0.25/1000s of wall clock (rough Claude Code rate)
    est_cost = total_wall * 0.00025
    avg_cost = avg_wall * 0.00025

    # Score: 1.0 if avg cost under target, degrade linearly
    if avg_cost <= 0:
        score = 1.0 if total_tasks == 0 else 0.5
    elif avg_cost <= COST_PER_TASK_TARGET:
        score = 1.0
    else:
        score = max(0.0, 1.0 - (avg_cost - COST_PER_TASK_TARGET) / COST_PER_TASK_TARGET)

    return round(score, 3), {
        "total_tasks": total_tasks,
        "total_wall_clock_seconds": round(total_wall, 1),
        "avg_wall_clock_seconds": round(avg_wall, 1),
        "estimated_cost_usd": round(est_cost, 4),
        "avg_estimated_cost_usd": round(avg_cost, 4),
        "cost_source": "wall_clock_estimate",
        "note": "No actual cost data yet. Run tasks to collect OpenRouter cost snapshots." if not elapsed_times else None,
    }


def run_benchmark(name: str) -> dict:
    """Run full 5-dimension benchmark for an agent. Returns result dict."""
    agent_dir = _get_agent_dir(name)
    if not agent_dir.exists():
        return {"error": f"Agent '{name}' not found at {agent_dir}"}

    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' has no config"}

    ts = datetime.now(timezone.utc).isoformat()

    # Score all dimensions
    iso_score, iso_details = _score_isolation(name)
    lat_score, lat_details = _score_latency(name)
    pr_score, pr_details = _score_pr_success(name)
    ret_score, ret_details = _score_retrieval(name)
    cost_score, cost_details = _score_cost(name)

    dimension_scores = {
        "isolation": round(iso_score, 3),
        "latency": round(lat_score, 3),
        "pr_success": round(pr_score, 3),
        "retrieval": round(ret_score, 3),
        "cost": round(cost_score, 3),
    }

    # Weighted composite
    composite = sum(dimension_scores[d] * WEIGHTS[d] for d in WEIGHTS)

    result = {
        "agent": name,
        "timestamp": ts,
        "latency": lat_details,
        "isolation": iso_details,
        "pr_success": pr_details,
        "retrieval": ret_details,
        "cost": cost_details,
        "dimension_scores": dimension_scores,
        "composite_score": round(composite, 3),
    }

    # Write latest + append history
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    latest_file = DATA_DIR / f"{name}_latest.json"
    history_file = DATA_DIR / f"{name}_history.jsonl"

    latest_file.write_text(json.dumps(result, indent=2))
    with open(history_file, "a") as f:
        f.write(json.dumps(result) + "\n")

    return result


def show_benchmark(name: str) -> dict:
    """Show latest benchmark for an agent."""
    latest_file = DATA_DIR / f"{name}_latest.json"
    if not latest_file.exists():
        return {"error": f"No benchmark data for '{name}'. Run: orchestration_benchmark.py run {name}"}
    return json.loads(latest_file.read_text())


def run_all() -> list[dict]:
    """Run benchmarks for all agents."""
    try:
        from project_agent import cmd_list
        agents = cmd_list()
    except ImportError:
        # Fallback: scan agent directories
        agents = []
        for root in [Path("/opt/clarvis-agents"), Path("~/agents").expanduser()]:
            if root.exists():
                for d in sorted(root.iterdir()):
                    cfg = d / "configs" / "config.json"
                    if cfg.exists():
                        agents.append({"name": d.name})

    results = []
    for agent in agents:
        name = agent["name"] if isinstance(agent, dict) else agent
        result = run_benchmark(name)
        results.append(result)
        status = "error" if "error" in result else f"composite={result['composite_score']}"
        print(f"  {name}: {status}")

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: orchestration_benchmark.py run <agent> | run-all | show <agent>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "run" and len(sys.argv) >= 3:
        name = sys.argv[2]
        result = run_benchmark(name)
        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result, indent=2))

    elif cmd == "run-all":
        results = run_all()
        print(f"\nBenchmarked {len(results)} agents")
        for r in results:
            if "error" not in r:
                print(f"  {r['agent']}: {r['composite_score']:.3f}")

    elif cmd == "show" and len(sys.argv) >= 3:
        name = sys.argv[2]
        result = show_benchmark(name)
        print(json.dumps(result, indent=2))

    else:
        print("Usage: orchestration_benchmark.py run <agent> | run-all | show <agent>")
        sys.exit(1)


if __name__ == "__main__":
    main()
