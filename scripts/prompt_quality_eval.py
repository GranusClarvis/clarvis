#!/usr/bin/env python3
"""Prompt/Context Quality Evaluation Matrix.

Evaluates Claude prompt/context variants across real Clarvis task types.
Compares current routes on structural quality metrics (static) and
optionally via LLM-judged scoring (PROMPT_LLM_REVIEW_BENCH).

Usage:
    # Static eval matrix — no LLM calls
    python3 scripts/prompt_quality_eval.py matrix

    # LLM-judged eval (uses OpenRouter for cost-effective evaluation)
    python3 scripts/prompt_quality_eval.py llm-review

    # Both
    python3 scripts/prompt_quality_eval.py full

Output: data/prompt_eval/eval_results.json
"""

import json
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WORKSPACE = "/home/agent/.openclaw/workspace"
TASKSET_PATH = os.path.join(WORKSPACE, "data/prompt_eval/taskset.json")
POLICY_PATH = os.path.join(WORKSPACE, "data/prompt_eval/context_budget_policy.json")
RESULTS_PATH = os.path.join(WORKSPACE, "data/prompt_eval/eval_results.json")


def load_taskset():
    with open(TASKSET_PATH) as f:
        return json.load(f)["tasks"]


def load_policy():
    with open(POLICY_PATH) as f:
        return json.load(f)["task_classes"]


# ---------------------------------------------------------------------------
# Static Quality Metrics
# ---------------------------------------------------------------------------

def _check_section_presence(brief: str, expected_sections: list[str]) -> dict:
    """Check which expected sections are present in the brief."""
    section_markers = {
        "decision_context": ["CURRENT TASK:", "SUCCESS CRITERIA:"],
        "failure_avoidance": ["AVOID THESE FAILURE PATTERNS:", "FAILURE"],
        "procedures": ["Recommended approach", "Procedure"],
        "episodic_lessons": ["EPISODIC LESSONS:", "EPISODIC"],
        "knowledge": ["RELEVANT KNOWLEDGE:", "KNOWLEDGE"],
        "working_memory": ["WORKING MEMORY:", "WORKING CONTEXT:"],
        "metrics": ["METRICS:", "Phi="],
        "related_tasks": ["RELATED TASKS:"],
        "completions": ["RECENT:"],
        "wire_guidance": ["WIRE GUIDANCE:", "SUB-STEPS:"],
        "reasoning_scaffold": ["REASONING SCAFFOLD:"],
        "goals": ["ACTIVE GOALS:", "BRAIN GOALS"],
        "architecture": ["ARCHITECTURE:", "INFRA"],
        "code_templates": ["CODE TEMPLATE:"],
    }
    present = {}
    for sec in expected_sections:
        markers = section_markers.get(sec, [sec.upper()])
        found = any(m in brief for m in markers)
        present[sec] = found
    return present


def _check_duplication(brief: str) -> dict:
    """Detect duplicate content blocks in the brief."""
    dupes = {}
    check_patterns = [
        ("failure_patterns", "AVOID THESE FAILURE PATTERNS"),
        ("procedures", "Recommended approach (from procedural memory)"),
        ("episodic", "EPISODIC LESSONS"),
        ("goals", "ACTIVE GOALS"),
    ]
    for name, pattern in check_patterns:
        count = brief.count(pattern)
        if count > 1:
            dupes[name] = count
    return dupes


def _check_ordering(brief: str) -> dict:
    """Check if high-value sections are in attention-optimal positions."""
    lines = brief.split("\n")
    total = len(lines)
    if total == 0:
        return {"ordering_score": 0.0}

    # Find positions of key sections
    positions = {}
    for i, line in enumerate(lines):
        for key, marker in [
            ("decision_context", "CURRENT TASK:"),
            ("failure_avoidance", "AVOID THESE FAILURE"),
            ("procedures", "Recommended approach"),
            ("episodic", "EPISODIC LESSONS"),
        ]:
            if marker in line and key not in positions:
                positions[key] = i / max(total, 1)

    # Primacy/recency: decision context should be early (<0.3), episodic late (>0.6)
    score = 0.0
    checks = 0
    if "decision_context" in positions:
        score += 1.0 if positions["decision_context"] < 0.3 else 0.5
        checks += 1
    if "episodic" in positions:
        score += 1.0 if positions["episodic"] > 0.6 else 0.5
        checks += 1
    if "failure_avoidance" in positions:
        score += 1.0 if positions["failure_avoidance"] < 0.4 else 0.5
        checks += 1

    return {
        "ordering_score": round(score / max(checks, 1), 2),
        "section_positions": positions,
    }


def _measure_density(brief: str) -> dict:
    """Measure information density — ratio of content to boilerplate."""
    lines = brief.strip().split("\n")
    total = len(lines)
    empty = sum(1 for l in lines if not l.strip())
    separator = sum(1 for l in lines if l.strip() == "---")
    content = total - empty - separator
    return {
        "total_lines": total,
        "content_lines": content,
        "density": round(content / max(total, 1), 2),
        "total_chars": len(brief),
    }


def evaluate_static(task: dict, brief: str) -> dict:
    """Run all static quality checks on a brief for a given task."""
    expected = task.get("expected_context_needs", [])
    priority = task.get("priority_sections", [])

    presence = _check_section_presence(brief, expected + priority)
    duplication = _check_duplication(brief)
    ordering = _check_ordering(brief)
    density = _measure_density(brief)

    # Coverage score: % of expected sections present
    if expected:
        coverage = sum(1 for s in expected if presence.get(s, False)) / len(expected)
    else:
        coverage = 1.0

    # Priority coverage: % of high-priority sections present
    if priority:
        priority_coverage = sum(1 for s in priority if presence.get(s, False)) / len(priority)
    else:
        priority_coverage = 1.0

    return {
        "task_id": task["id"],
        "task_class": task["class"],
        "coverage": round(coverage, 2),
        "priority_coverage": round(priority_coverage, 2),
        "duplicates": duplication,
        "has_duplicates": len(duplication) > 0,
        "ordering": ordering,
        "density": density,
        "section_presence": presence,
    }


# ---------------------------------------------------------------------------
# Route generators
# ---------------------------------------------------------------------------

def _generate_via_tiered_brief(task_text: str, tier: str) -> str:
    """Generate brief via assembly.generate_tiered_brief (spine route)."""
    try:
        from clarvis.context.assembly import generate_tiered_brief
        return generate_tiered_brief(current_task=task_text, tier=tier)
    except Exception as e:
        return f"[ERROR: {e}]"


def _generate_via_prompt_builder(task_text: str, tier: str) -> str:
    """Generate brief via prompt_builder.get_context_brief (unified route)."""
    try:
        from prompt_builder import get_context_brief
        return get_context_brief(tier=tier, task=task_text)
    except Exception as e:
        return f"[ERROR: {e}]"


# ---------------------------------------------------------------------------
# Matrix evaluation
# ---------------------------------------------------------------------------

def run_eval_matrix():
    """Run static quality evaluation across all tasks and routes."""
    tasks = load_taskset()
    results = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "type": "static_matrix", "evaluations": []}

    for task in tasks:
        task_text = task["task_text"]
        task_results = {"task_id": task["id"], "task_class": task["class"], "routes": {}}

        for route_name, generator, tier in [
            ("tiered_brief_standard", _generate_via_tiered_brief, "standard"),
            ("tiered_brief_full", _generate_via_tiered_brief, "full"),
            ("prompt_builder_standard", _generate_via_prompt_builder, "standard"),
            ("prompt_builder_full", _generate_via_prompt_builder, "full"),
        ]:
            brief = generator(task_text, tier)
            eval_result = evaluate_static(task, brief)
            eval_result["brief_chars"] = len(brief)
            task_results["routes"][route_name] = eval_result

        results["evaluations"].append(task_results)

    # Aggregate scores
    agg = {"by_route": {}, "by_class": {}}
    for eval_item in results["evaluations"]:
        cls = eval_item["task_class"]
        for route, scores in eval_item["routes"].items():
            if route not in agg["by_route"]:
                agg["by_route"][route] = {"coverage": [], "priority": [], "ordering": [], "dupes": 0}
            agg["by_route"][route]["coverage"].append(scores["coverage"])
            agg["by_route"][route]["priority"].append(scores["priority_coverage"])
            agg["by_route"][route]["ordering"].append(scores["ordering"]["ordering_score"])
            agg["by_route"][route]["dupes"] += 1 if scores["has_duplicates"] else 0

    for route, vals in agg["by_route"].items():
        n = len(vals["coverage"])
        agg["by_route"][route] = {
            "mean_coverage": round(sum(vals["coverage"]) / n, 3),
            "mean_priority_coverage": round(sum(vals["priority"]) / n, 3),
            "mean_ordering": round(sum(vals["ordering"]) / n, 3),
            "duplicate_count": vals["dupes"],
            "n_tasks": n,
        }

    results["aggregate"] = agg
    return results


# ---------------------------------------------------------------------------
# LLM-Judged Evaluation
# ---------------------------------------------------------------------------

LLM_RESULTS_PATH = os.path.join(WORKSPACE, "data/prompt_eval/llm_review_results.json")

# Evaluation model — cheap, fast, good at structured scoring
LLM_EVAL_MODEL = "minimax/minimax-m2.5"

LLM_EVAL_RUBRIC = """\
You are evaluating the quality of an AI agent's context brief for a specific task.

TASK:
{task_text}

TASK CLASS: {task_class}
EXPECTED CONTEXT NEEDS: {expected_needs}
KNOWN FAILURE MODES: {failure_modes}

CONTEXT BRIEF TO EVALUATE:
---
{brief}
---

Score each dimension 1-5 (1=poor, 5=excellent). Respond with ONLY valid JSON, no markdown fences.

Dimensions:
- task_fit: Does the brief contain information directly relevant to THIS specific task?
- relevance: Is the included context useful, or is it generic filler?
- completeness: Are the expected context needs (listed above) adequately covered?
- ordering: Are the most important sections placed early (primacy) or late (recency)?
- noise: How much irrelevant or duplicated content is present? (5=no noise, 1=mostly noise)
- execution_usefulness: If an AI agent received this brief, how likely is it to succeed at the task?

Output format:
{{"task_fit": N, "relevance": N, "completeness": N, "ordering": N, "noise": N, "execution_usefulness": N, "rationale": "one sentence"}}
"""


def _get_openrouter_key() -> str | None:
    """Resolve OpenRouter API key from env or auth profile."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    auth_file = "/home/agent/.openclaw/agents/main/agent/auth-profiles.json"
    try:
        with open(auth_file) as f:
            auth = json.load(f)
        return auth.get("profiles", {}).get("openrouter:default", {}).get("key")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def _llm_score_brief(task: dict, brief: str, api_key: str) -> dict | None:
    """Send a single brief to LLM evaluator and return parsed scores."""
    import requests

    prompt = LLM_EVAL_RUBRIC.format(
        task_text=task["task_text"],
        task_class=task["class"],
        expected_needs=", ".join(task.get("expected_context_needs", [])),
        failure_modes=", ".join(task.get("failure_modes", [])),
        brief=brief[:8000],  # Cap brief length to stay within budget
    )

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": LLM_EVAL_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.0,
            },
            timeout=30,
        )
        resp.raise_for_status()

        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"  LLM eval error: {e}")
        return None


def run_llm_review(dry_run: bool = False) -> dict:
    """Run LLM-judged evaluation across all tasks and routes.

    Args:
        dry_run: If True, generate briefs and rubrics but skip API calls.
                 Useful for validating the pipeline without spending tokens.
    """
    api_key = None
    if not dry_run:
        api_key = _get_openrouter_key()
        if not api_key:
            print("ERROR: No OpenRouter API key found.")
            print("Set OPENROUTER_API_KEY env var or configure auth-profiles.json.")
            print("Use 'llm-review --dry-run' to validate the pipeline without API calls.")
            sys.exit(1)

    tasks = load_taskset()
    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "llm_review",
        "model": LLM_EVAL_MODEL,
        "evaluations": [],
    }

    total_calls = 0
    for task in tasks:
        task_text = task["task_text"]
        task_results = {"task_id": task["id"], "task_class": task["class"], "routes": {}}

        for route_name, generator, tier in [
            ("tiered_brief_standard", _generate_via_tiered_brief, "standard"),
            ("tiered_brief_full", _generate_via_tiered_brief, "full"),
            ("prompt_builder_standard", _generate_via_prompt_builder, "standard"),
            ("prompt_builder_full", _generate_via_prompt_builder, "full"),
        ]:
            brief = generator(task_text, tier)
            if brief.startswith("[ERROR"):
                task_results["routes"][route_name] = {"error": brief}
                continue

            if dry_run:
                print(f"  [dry-run] {task['id']} / {route_name}: brief={len(brief)} chars")
                scores = {"task_fit": 0, "relevance": 0, "completeness": 0,
                          "ordering": 0, "noise": 0, "execution_usefulness": 0,
                          "rationale": "dry-run placeholder", "brief_chars": len(brief)}
                task_results["routes"][route_name] = scores
                continue

            print(f"  Scoring {task['id']} / {route_name}...")
            scores = _llm_score_brief(task, brief, api_key)
            total_calls += 1

            if scores:
                # Validate score ranges
                dims = ["task_fit", "relevance", "completeness", "ordering", "noise", "execution_usefulness"]
                for d in dims:
                    if d in scores and isinstance(scores[d], (int, float)):
                        scores[d] = max(1, min(5, int(scores[d])))

                scores["brief_chars"] = len(brief)
                task_results["routes"][route_name] = scores
            else:
                task_results["routes"][route_name] = {"error": "LLM scoring failed"}

        results["evaluations"].append(task_results)

    # Aggregate by route
    agg = {}
    dims = ["task_fit", "relevance", "completeness", "ordering", "noise", "execution_usefulness"]
    for eval_item in results["evaluations"]:
        for route, scores in eval_item["routes"].items():
            if "error" in scores:
                continue
            if route not in agg:
                agg[route] = {d: [] for d in dims}
            for d in dims:
                if d in scores:
                    agg[route][d].append(scores[d])

    aggregate = {}
    for route, vals in agg.items():
        route_agg = {}
        for d in dims:
            if vals[d]:
                route_agg[f"mean_{d}"] = round(sum(vals[d]) / len(vals[d]), 2)
        # Composite: average of all dimension means
        means = [v for k, v in route_agg.items() if k.startswith("mean_")]
        route_agg["composite"] = round(sum(means) / len(means), 2) if means else 0.0
        route_agg["n_tasks"] = len(vals[dims[0]])
        aggregate[route] = route_agg

    results["aggregate"] = aggregate
    results["total_llm_calls"] = total_calls

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: prompt_quality_eval.py matrix|llm-review|full")
        sys.exit(1)

    cmd = sys.argv[1]
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

    if cmd in ("matrix", "full"):
        print("Running static eval matrix...")
        results = run_eval_matrix()
        with open(RESULTS_PATH, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results: {RESULTS_PATH}")
        print("\nAggregate scores by route:")
        for route, scores in results["aggregate"]["by_route"].items():
            print(f"  {route}: coverage={scores['mean_coverage']:.1%} "
                  f"priority={scores['mean_priority_coverage']:.1%} "
                  f"ordering={scores['mean_ordering']:.1%} "
                  f"dupes={scores['duplicate_count']}")

    if cmd in ("llm-review", "full"):
        dry_run = "--dry-run" in sys.argv
        print(f"\nRunning LLM-judged review{'  [DRY RUN]' if dry_run else ''}...")
        llm_results = run_llm_review(dry_run=dry_run)
        with open(LLM_RESULTS_PATH, "w") as f:
            json.dump(llm_results, f, indent=2)
        print(f"Results: {LLM_RESULTS_PATH}")
        print(f"Total LLM calls: {llm_results['total_llm_calls']}")
        print("\nAggregate scores by route (1-5 scale):")
        for route, scores in llm_results["aggregate"].items():
            print(f"  {route}: composite={scores['composite']:.1f} "
                  f"fit={scores.get('mean_task_fit', 0):.1f} "
                  f"useful={scores.get('mean_execution_usefulness', 0):.1f} "
                  f"noise={scores.get('mean_noise', 0):.1f} "
                  f"(n={scores['n_tasks']})")


if __name__ == "__main__":
    main()
