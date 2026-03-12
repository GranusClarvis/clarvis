#!/usr/bin/env python3
"""Subagent Brain Maturation — Soak Evaluation Harness.

Tests the matured subagent brain + PR-factory pipeline end-to-end across
multiple task classes WITHOUT spawning Claude Code. Evaluates:

1. **Brain health** — store/recall, stats, collection integrity
2. **Retrieval quality** — golden QA benchmark (P@1, P@3, MRR)
3. **Artifact freshness** — staleness check for all intake artifacts
4. **Index coverage** — precision indexes completeness and richness
5. **Brief compilation** — per-task-class brief quality across 6 task types
6. **Recon grounding** — relevant files, facts, episodes filled vs empty
7. **Writeback pipeline** — simulated A2A result → writeback → retrieval
8. **Typed edges** — graph edge density, route/symbol/test coverage
9. **Trust trajectory** — trust score trend, tier, stability
10. **Orchestration benchmark** — composite score (latency, isolation, PR, retrieval, cost)

Produces a JSON trust/quality report saved to:
  data/orchestration_benchmarks/<agent>_soak_report.json

Usage:
    python3 subagent_soak_eval.py <agent_name>     # Full soak eval
    python3 subagent_soak_eval.py <agent_name> --summary  # One-line summary
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

CLARVIS_WORKSPACE = Path("/home/agent/.openclaw/workspace")
AGENTS_ROOT_PRIMARY = Path("/opt/clarvis-agents")
AGENTS_ROOT_FALLBACK = Path("/home/agent/agents")

# Task class test scenarios — representative tasks for each class
SOAK_TASKS = {
    "docs": "Add JSDoc comments to the governance API route handlers and document the voting power verification flow",
    "feature": "Implement a new REST endpoint for user profile settings with input validation and rate limiting",
    "hardening": "Harden the authentication middleware: add CSRF protection, validate session tokens, sanitize user input",
    "tests": "Add unit tests for the database query functions in lib/db.ts covering edge cases and error paths",
    "bugfix": "Fix the race condition in claimQuestReward where concurrent claims can double-spend rewards",
    "investigation": "Investigate and profile the governance voting endpoint performance under concurrent load",
}


def _agent_dir(name: str) -> Path:
    primary = AGENTS_ROOT_PRIMARY / name
    if primary.exists():
        return primary
    return AGENTS_ROOT_FALLBACK / name


def eval_brain_health(agent_dir: Path) -> dict:
    """Test 1: Brain health — store/recall cycle, stats, collections."""
    from lite_brain import LiteBrain
    lb = LiteBrain(str(agent_dir / "data" / "brain"))

    health = lb.health_check()
    stats = lb.stats()

    # Check that all 5 collections exist with content
    empty_collections = [k for k, v in stats.get("collections", {}).items() if v == 0]
    populated = sum(1 for v in stats.get("collections", {}).values() if v > 0)

    return {
        "test": "brain_health",
        "pass": health.get("status") == "healthy",
        "status": health.get("status"),
        "total_memories": stats.get("total_memories", 0),
        "populated_collections": populated,
        "empty_collections": empty_collections,
        "graph_edges": stats.get("graph_edges", 0),
        "score": 1.0 if health.get("status") == "healthy" and populated >= 3 else 0.5,
    }


def eval_retrieval_quality(agent_dir: Path) -> dict:
    """Test 2: Retrieval quality — golden QA benchmark."""
    from lite_brain import LiteBrain
    lb = LiteBrain(str(agent_dir / "data" / "brain"))

    golden_path = agent_dir / "data" / "golden_qa.json"
    if not golden_path.exists():
        return {"test": "retrieval_quality", "pass": False, "note": "no golden_qa.json", "score": 0.0}

    result = lb.benchmark_retrieval(str(golden_path))
    p_at_3 = result.get("p_at_3", 0)

    return {
        "test": "retrieval_quality",
        "pass": result.get("pass", False),
        "p_at_1": result.get("p_at_1", 0),
        "p_at_3": p_at_3,
        "mrr": result.get("mrr", 0),
        "total_queries": result.get("total_queries", 0),
        "score": min(1.0, p_at_3 / 0.6) if p_at_3 > 0 else 0.0,
        "details": result.get("details", [])[:5],  # first 5 for report
    }


def eval_artifact_freshness(agent_dir: Path, workspace: Path) -> dict:
    """Test 3: Artifact freshness — all 5 artifacts present and not stale."""
    from clarvis.orch.pr_intake import is_stale, _load_artifact

    expected = ["project_brief", "stack_detect", "commands",
                "architecture_map", "trust_boundaries"]

    results = {}
    for name in expected:
        artifact = _load_artifact(agent_dir, name)
        if artifact is None:
            results[name] = {"present": False, "stale": True}
        else:
            stale = is_stale(agent_dir, workspace, name)
            data = artifact.get("data", artifact)
            # Quality: check if data has content
            has_content = bool(data) and len(json.dumps(data)) > 20
            results[name] = {"present": True, "stale": stale, "has_content": has_content}

    present = sum(1 for v in results.values() if v["present"])
    fresh = sum(1 for v in results.values() if v["present"] and not v["stale"])
    with_content = sum(1 for v in results.values() if v.get("has_content"))

    return {
        "test": "artifact_freshness",
        "pass": present == 5 and fresh >= 3,
        "present": present,
        "fresh": fresh,
        "with_content": with_content,
        "artifacts": results,
        "score": (present / 5) * 0.5 + (with_content / 5) * 0.5,
    }


def eval_index_coverage(agent_dir: Path, workspace: Path) -> dict:
    """Test 4: Precision index completeness and richness."""
    from clarvis.orch.pr_indexes import load_all_indexes

    indexes = load_all_indexes(agent_dir)
    expected = ["file_index", "symbol_index", "route_index", "config_index", "test_index"]

    results = {}
    for name in expected:
        idx = indexes.get(name)
        if idx is None:
            results[name] = {"present": False, "count": 0}
        else:
            # Count entries
            if name == "file_index":
                count = len(idx.get("files", []))
            elif name == "symbol_index":
                count = idx.get("files_with_symbols", 0)
            elif name == "route_index":
                count = len(idx.get("routes", []))
            elif name == "config_index":
                count = len(idx.get("configs", []))
            elif name == "test_index":
                count = len(idx.get("tests", []))
            else:
                count = 0
            results[name] = {"present": True, "count": count}

    present = sum(1 for v in results.values() if v["present"])
    with_data = sum(1 for v in results.values() if v.get("count", 0) > 0)

    return {
        "test": "index_coverage",
        "pass": present == 5 and with_data >= 3,
        "present": present,
        "with_data": with_data,
        "indexes": results,
        "score": (present / 5) * 0.4 + (with_data / max(present, 1)) * 0.6,
    }


def eval_brief_compilation(agent_dir: Path) -> dict:
    """Test 5: Brief quality across 6 task classes.

    Compiles a brief for each task class and measures field population.
    """
    from pr_factory import build_execution_brief, classify_task

    agent_name = agent_dir.name
    results = {}

    for task_class, task_text in SOAK_TASKS.items():
        brief = build_execution_brief(agent_name, task_text, agent_dir)

        # Measure field population
        fields = {
            "task_class": bool(brief.get("task_class")),
            "success_criteria": len(brief.get("success_criteria", [])) > 0,
            "non_negotiables": len(brief.get("non_negotiables", [])) > 0,
            "relevant_files": len(brief.get("relevant_files", [])) > 0,
            "relevant_facts": len(brief.get("relevant_facts", [])) > 0,
            "relevant_episodes": len(brief.get("relevant_episodes", [])) > 0,
            "required_validations": len(brief.get("required_validations", [])) > 0,
            "artifact_excerpts": len(brief.get("artifact_excerpts", {})) > 0,
        }

        filled = sum(1 for v in fields.values() if v)
        total = len(fields)

        # Check classification accuracy
        classified = classify_task(task_text)
        classification_correct = classified == task_class

        results[task_class] = {
            "fill_rate": round(filled / total, 2),
            "filled": filled,
            "total": total,
            "fields": fields,
            "classified_as": classified,
            "classification_correct": classification_correct,
            "relevant_files_count": len(brief.get("relevant_files", [])),
            "relevant_facts_count": len(brief.get("relevant_facts", [])),
        }

    avg_fill = sum(r["fill_rate"] for r in results.values()) / max(len(results), 1)
    classification_accuracy = sum(1 for r in results.values() if r["classification_correct"]) / max(len(results), 1)

    return {
        "test": "brief_compilation",
        "pass": avg_fill >= 0.5,
        "avg_fill_rate": round(avg_fill, 3),
        "classification_accuracy": round(classification_accuracy, 2),
        "per_class": results,
        "score": avg_fill * 0.6 + classification_accuracy * 0.4,
    }


def eval_recon_grounding(agent_dir: Path) -> dict:
    """Test 6: Recon grounding — do briefs surface actionable file/fact/episode data?

    Measures the ratio of briefs that have at least 1 relevant file AND
    at least 1 relevant fact or episode. This is the key recon quality signal.
    """
    from pr_factory import build_execution_brief

    agent_name = agent_dir.name
    grounded = 0
    with_files = 0
    with_facts = 0
    with_episodes = 0
    with_validations = 0

    for task_class, task_text in SOAK_TASKS.items():
        brief = build_execution_brief(agent_name, task_text, agent_dir)

        has_files = len(brief.get("relevant_files", [])) > 0
        has_facts = len(brief.get("relevant_facts", [])) > 0
        has_episodes = len(brief.get("relevant_episodes", [])) > 0
        has_validations = len(brief.get("required_validations", [])) > 0

        if has_files:
            with_files += 1
        if has_facts:
            with_facts += 1
        if has_episodes:
            with_episodes += 1
        if has_validations:
            with_validations += 1

        # Grounded = has files AND (facts OR episodes)
        if has_files and (has_facts or has_episodes):
            grounded += 1

    total = len(SOAK_TASKS)
    grounding_rate = grounded / max(total, 1)

    return {
        "test": "recon_grounding",
        "pass": grounding_rate >= 0.5,
        "grounding_rate": round(grounding_rate, 2),
        "with_files": with_files,
        "with_facts": with_facts,
        "with_episodes": with_episodes,
        "with_validations": with_validations,
        "total_tasks": total,
        "score": grounding_rate,
    }


def eval_writeback_pipeline(agent_dir: Path) -> dict:
    """Test 7: Writeback pipeline — simulate A2A result → writeback → retrieval.

    Creates a fake A2A result, runs writeback, then verifies the stored data
    is retrievable. Cleans up after.
    """
    from pr_factory import run_writeback
    from lite_brain import LiteBrain

    lb = LiteBrain(str(agent_dir / "data" / "brain"))

    # Simulate A2A result
    test_task = "Soak test: verify writeback pipeline stores facts correctly"
    test_result = {
        "protocol": "a2a/v1",
        "status": "success",
        "summary": "SOAK_TEST_WRITEBACK_MARKER: Verified that writeback stores episodes and facts",
        "files_changed": ["test/soak_eval_marker.ts"],
        "procedures": ["npm run test -- --soak-marker"],
        "follow_ups": [],
        "tests_passed": True,
        "confidence": 0.85,
        "pr_class": "A",
    }

    # Run writeback
    try:
        run_writeback(agent_dir.name, agent_dir, test_result, test_task)

        # Verify retrieval
        time.sleep(0.5)  # ChromaDB settle
        results = lb.recall("SOAK_TEST_WRITEBACK_MARKER", n_results=3)

        found_episode = any("SOAK_TEST_WRITEBACK_MARKER" in r["document"] for r in results)
        found_fact = any("soak_eval_marker" in r["document"] for r in results)

        # Verify golden QA was updated (confidence >= 0.8)
        qa_path = agent_dir / "data" / "golden_qa.json"
        qa_updated = False
        if qa_path.exists():
            qa = json.loads(qa_path.read_text())
            qa_updated = any("soak test" in q.get("query", "").lower() for q in qa)

        # Cleanup: remove soak test entries from golden_qa if added
        if qa_updated and qa_path.exists():
            qa = json.loads(qa_path.read_text())
            qa = [q for q in qa if "soak test" not in q.get("query", "").lower()]
            qa_path.write_text(json.dumps(qa, indent=2, default=str))

        return {
            "test": "writeback_pipeline",
            "pass": found_episode,
            "episode_stored": found_episode,
            "fact_stored": found_fact,
            "golden_qa_updated": qa_updated,
            "score": (0.5 if found_episode else 0) + (0.3 if found_fact else 0) + (0.2 if qa_updated else 0),
        }

    except Exception as e:
        return {
            "test": "writeback_pipeline",
            "pass": False,
            "error": str(e),
            "score": 0.0,
        }


def eval_typed_edges(agent_dir: Path) -> dict:
    """Test 8: Graph typed edge density and coverage."""
    from lite_brain import LiteBrain
    lb = LiteBrain(str(agent_dir / "data" / "brain"))

    graph = lb._load_graph()
    edges = graph.get("edges", [])
    nodes = graph.get("nodes", {})

    # Count by type
    type_counts = {}
    for e in edges:
        etype = e.get("type", "unknown")
        type_counts[etype] = type_counts.get(etype, 0) + 1

    total_edges = len(edges)
    typed_coverage = len(type_counts)
    has_route = type_counts.get("route_file", 0) > 0
    has_symbol = type_counts.get("symbol_file", 0) > 0
    has_test = type_counts.get("test_module", 0) > 0
    has_task_class = type_counts.get("task_class_file", 0) > 0

    return {
        "test": "typed_edges",
        "pass": total_edges > 10 and typed_coverage >= 2,
        "total_edges": total_edges,
        "total_nodes": len(nodes),
        "edge_types": type_counts,
        "coverage": {
            "route_file": has_route,
            "symbol_file": has_symbol,
            "test_module": has_test,
            "task_class_file": has_task_class,
        },
        "score": min(1.0, total_edges / 100) * 0.5 + min(1.0, typed_coverage / 4) * 0.5,
    }


def eval_trust_trajectory(agent_dir: Path) -> dict:
    """Test 9: Trust score trend and tier stability."""
    config_path = agent_dir / "configs" / "agent.json"
    if not config_path.exists():
        return {"test": "trust_trajectory", "pass": False, "score": 0.0}

    config = json.loads(config_path.read_text())
    trust = config.get("trust_score", 0)
    history = config.get("trust_history", [])
    total_tasks = config.get("total_tasks", 0)
    total_successes = config.get("total_successes", 0)
    total_prs = config.get("total_pr_count", 0)

    # Trust tier
    if trust >= 0.80:
        tier = "autonomous"
    elif trust >= 0.50:
        tier = "supervised"
    elif trust >= 0.20:
        tier = "restricted"
    else:
        tier = "suspended"

    # Trend: last 5 adjustments
    recent = history[-5:] if history else []
    deltas = [h.get("delta", 0) for h in recent]
    trend = "up" if all(d >= 0 for d in deltas) else "mixed" if any(d > 0 for d in deltas) else "down"

    success_rate = total_successes / max(total_tasks, 1)
    pr_rate = total_prs / max(total_tasks, 1)

    return {
        "test": "trust_trajectory",
        "pass": trust >= 0.50 and success_rate >= 0.5,
        "trust_score": trust,
        "tier": tier,
        "trend": trend,
        "total_tasks": total_tasks,
        "total_successes": total_successes,
        "success_rate": round(success_rate, 2),
        "pr_rate": round(pr_rate, 2),
        "total_prs": total_prs,
        "recent_adjustments": recent[-3:],
        "score": min(1.0, trust),
    }


def eval_orchestration_benchmark(name: str) -> dict:
    """Test 10: Run the orchestration benchmark for composite score."""
    from orchestration_benchmark import run_full_benchmark

    result = run_full_benchmark(name)
    if "error" in result:
        return {"test": "orchestration_benchmark", "pass": False, "error": result["error"], "score": 0.0}

    composite = result.get("composite_score", 0)
    dims = result.get("dimension_scores", {})

    return {
        "test": "orchestration_benchmark",
        "pass": composite >= 0.5,
        "composite_score": composite,
        "dimension_scores": dims,
        "score": composite,
    }


# ── Main soak evaluation ──

def run_soak_eval(name: str) -> dict:
    """Run full soak evaluation for a project agent. Returns trust/quality report."""
    agent_dir = _agent_dir(name)
    workspace = agent_dir / "workspace"

    if not agent_dir.exists():
        return {"error": f"Agent '{name}' not found at {agent_dir}"}

    report = {
        "agent": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "evaluations": {},
        "summary": {},
    }

    # Run all evaluations
    evaluations = [
        ("brain_health", lambda: eval_brain_health(agent_dir)),
        ("retrieval_quality", lambda: eval_retrieval_quality(agent_dir)),
        ("artifact_freshness", lambda: eval_artifact_freshness(agent_dir, workspace)),
        ("index_coverage", lambda: eval_index_coverage(agent_dir, workspace)),
        ("brief_compilation", lambda: eval_brief_compilation(agent_dir)),
        ("recon_grounding", lambda: eval_recon_grounding(agent_dir)),
        ("writeback_pipeline", lambda: eval_writeback_pipeline(agent_dir)),
        ("typed_edges", lambda: eval_typed_edges(agent_dir)),
        ("trust_trajectory", lambda: eval_trust_trajectory(agent_dir)),
        ("orchestration_benchmark", lambda: eval_orchestration_benchmark(name)),
    ]

    scores = {}
    passes = {}
    for eval_name, eval_fn in evaluations:
        try:
            result = eval_fn()
            report["evaluations"][eval_name] = result
            scores[eval_name] = result.get("score", 0)
            passes[eval_name] = result.get("pass", False)
        except Exception as e:
            report["evaluations"][eval_name] = {
                "test": eval_name, "pass": False, "error": str(e), "score": 0.0
            }
            scores[eval_name] = 0
            passes[eval_name] = False

    # Compute weighted soak score
    weights = {
        "brain_health": 0.10,
        "retrieval_quality": 0.20,
        "artifact_freshness": 0.05,
        "index_coverage": 0.10,
        "brief_compilation": 0.15,
        "recon_grounding": 0.15,
        "writeback_pipeline": 0.10,
        "typed_edges": 0.05,
        "trust_trajectory": 0.05,
        "orchestration_benchmark": 0.05,
    }

    soak_score = sum(scores.get(k, 0) * w for k, w in weights.items())
    passed = sum(1 for v in passes.values() if v)
    total = len(passes)

    # Determine verdict
    if soak_score >= 0.8 and passed >= 8:
        verdict = "PRODUCTION_READY"
    elif soak_score >= 0.6 and passed >= 6:
        verdict = "SUPERVISED_OK"
    elif soak_score >= 0.4 and passed >= 4:
        verdict = "NEEDS_IMPROVEMENT"
    else:
        verdict = "NOT_READY"

    report["summary"] = {
        "soak_score": round(soak_score, 3),
        "verdict": verdict,
        "tests_passed": passed,
        "tests_total": total,
        "dimension_scores": {k: round(v, 3) for k, v in scores.items()},
        "weakest": min(scores, key=scores.get) if scores else "none",
        "strongest": max(scores, key=scores.get) if scores else "none",
    }

    # Save report
    report_dir = CLARVIS_WORKSPACE / "data" / "orchestration_benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"{name}_soak_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))

    # Append to history
    history_path = report_dir / f"{name}_soak_history.jsonl"
    with open(history_path, "a") as f:
        f.write(json.dumps({
            "timestamp": report["timestamp"],
            "soak_score": report["summary"]["soak_score"],
            "verdict": report["summary"]["verdict"],
            "passed": passed,
            "total": total,
        }) + "\n")

    return report


def print_summary(report: dict):
    """Print human-readable soak summary."""
    summary = report.get("summary", {})
    print(f"\n{'='*60}")
    print(f"  SOAK EVALUATION: {report.get('agent', '?')}")
    print(f"{'='*60}")
    print(f"  Verdict:    {summary.get('verdict', '?')}")
    print(f"  Soak Score: {summary.get('soak_score', 0):.3f}")
    print(f"  Passed:     {summary.get('tests_passed', 0)}/{summary.get('tests_total', 0)}")
    print(f"  Weakest:    {summary.get('weakest', '?')}")
    print(f"  Strongest:  {summary.get('strongest', '?')}")
    print()

    scores = summary.get("dimension_scores", {})
    for dim, score in sorted(scores.items(), key=lambda x: -x[1]):
        evl = report.get("evaluations", {}).get(dim, {})
        status = "PASS" if evl.get("pass") else "FAIL"
        bar = "#" * int(score * 20)
        print(f"  {status:4s} {score:.3f} [{bar:<20s}] {dim}")

    print(f"\n  Report: data/orchestration_benchmarks/{report.get('agent', '?')}_soak_report.json")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: subagent_soak_eval.py <agent_name> [--summary]")
        sys.exit(1)

    agent_name = sys.argv[1]
    summary_only = "--summary" in sys.argv

    report = run_soak_eval(agent_name)

    if "error" in report:
        print(f"ERROR: {report['error']}")
        sys.exit(1)

    if summary_only:
        s = report["summary"]
        print(f"{s['verdict']} score={s['soak_score']:.3f} passed={s['tests_passed']}/{s['tests_total']} "
              f"weakest={s['weakest']}")
    else:
        print_summary(report)
        # Full JSON to stdout for piping
        if "--json" in sys.argv:
            print(json.dumps(report, indent=2, default=str))
