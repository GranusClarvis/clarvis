#!/usr/bin/env python3
"""Brief Benchmark — measure context brief quality against ground-truth tasks.

Generates tiered briefs for 10 known tasks and scores them against expected
content (token intersection + ROUGE-L + section coverage). Results update
data/benchmarks/brief_v2_report.json with a `brief_quality` block and append
to data/benchmarks/brief_benchmark_history.jsonl for trend tracking.

Monthly cron: 1st of month at 03:45 UTC.

Usage:
    python3 scripts/brief_benchmark.py              # run + update report
    python3 scripts/brief_benchmark.py --dry-run    # run without updating
    python3 scripts/brief_benchmark.py --json       # output raw JSON results
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
REPORT_FILE = os.path.join(WORKSPACE, "data", "benchmarks", "brief_v2_report.json")
HISTORY_FILE = os.path.join(WORKSPACE, "data", "benchmarks", "brief_benchmark_history.jsonl")

# Stopwords for tokenization (matches context_compressor / context_relevance pattern)
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could to of in for on with at by from as into "
    "through during before after above below between under again further then "
    "once here there when where why how all each every both few more most other "
    "some such no nor not only own same so than too very and but if or because "
    "until while that this these those it its he she they them their what which "
    "who whom".split()
)


def _tokenize(text: str) -> set[str]:
    """Extract meaningful lowercase tokens (3+ chars, no stopwords)."""
    return {w for w in re.findall(r"[a-z][a-z0-9_]{2,}", text.lower()) if w not in _STOPWORDS}


def _tokenize_seq(text: str) -> list[str]:
    """Extract meaningful lowercase tokens as ordered sequence (for ROUGE-L)."""
    return [w for w in re.findall(r"[a-z][a-z0-9_]{2,}", text.lower()) if w not in _STOPWORDS]


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _rouge_l_f1(reference: list[str], candidate: list[str]) -> float:
    """ROUGE-L F1 score via longest common subsequence."""
    if not reference or not candidate:
        return 0.0
    m, n = len(reference), len(candidate)
    # O(m) space DP
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if reference[i - 1] == candidate[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)
    lcs = prev[n]
    if lcs == 0:
        return 0.0
    p = lcs / n
    r = lcs / m
    return 2 * p * r / (p + r)


def _detect_sections(text: str) -> set[str]:
    """Detect which named sections are present in a brief."""
    markers = {
        "decision_context": r"(?:SUCCESS CRITERIA|FAILURE AVOIDANCE|CONSTRAINTS|DECISION CONTEXT)",
        "knowledge": r"RELEVANT KNOWLEDGE:",
        "working_memory": r"(?:WORKING MEMORY|COGNITIVE WORKSPACE|ACTIVE BUFFER):",
        "related_tasks": r"RELATED TASKS:",
        "metrics": r"METRICS:",
        "completions": r"RECENT:",
        "episodes": r"(?:EPISODIC LESSONS|FAILURE PATTERNS|LESSONS FROM):",
        "reasoning": r"(?:REASONING|THINK BEFORE|APPROACH):",
    }
    found = set()
    for name, pattern in markers.items():
        if re.search(pattern, text, re.I | re.M):
            found.add(name)
    return found


# ── Ground-truth benchmark tasks ──────────────────────────────────────────
# (task_text, category, tier, expected_keywords, expected_sections)
# expected_keywords: tokens that should appear in a well-generated brief.
# expected_sections: brief sections that should be present for this tier.

BENCHMARK_TASKS = [
    # --- CODE tasks ---
    (
        "Implement adaptive MMR lambda tuning for context_compressor.py",
        "code", "full",
        {"implement", "lambda", "context", "compressor", "mmr", "success", "constraint"},
        {"decision_context", "reasoning", "metrics"},
    ),
    (
        "Fix broken regex in queue_writer.py causing task parsing failures",
        "code", "standard",
        {"fix", "regex", "queue", "parsing", "success", "constraint"},
        {"decision_context", "reasoning"},
    ),
    (
        "Add pytest coverage for clarvis.brain.search module",
        "code", "full",
        {"test", "pytest", "brain", "search", "coverage", "success"},
        {"decision_context", "reasoning", "metrics"},
    ),
    (
        "Refactor heartbeat_postflight.py to extract episode encoding into separate function",
        "code", "standard",
        {"refactor", "heartbeat", "postflight", "episode", "success"},
        {"decision_context", "reasoning"},
    ),
    # --- RESEARCH tasks ---
    (
        "Research: CRAG retrieval-augmented generation patterns for adaptive retrieval",
        "research", "full",
        {"research", "retrieval", "patterns", "success"},
        {"decision_context", "reasoning"},
    ),
    (
        "Analyze memory consolidation strategies from cognitive science literature",
        "research", "full",
        {"analyze", "memory", "consolidation", "success"},
        {"decision_context", "reasoning"},
    ),
    # --- MAINTENANCE tasks ---
    (
        "Run health monitoring checks and generate status report",
        "maintenance", "standard",
        {"health", "monitor", "status", "report", "success"},
        {"decision_context", "reasoning"},
    ),
    (
        "Graph compaction — remove orphan edges and deduplicate",
        "maintenance", "standard",
        {"graph", "compaction", "orphan", "deduplicate", "success"},
        {"decision_context", "reasoning"},
    ),
    (
        "Daily backup verification and integrity check",
        "maintenance", "minimal",
        {"backup", "success"},
        set(),  # minimal tier has no sections
    ),
    (
        "Cron watchdog check — verify all scheduled jobs ran successfully",
        "maintenance", "standard",
        {"cron", "watchdog", "success"},
        {"decision_context", "reasoning"},
    ),
]


def _score_task(brief: str, task_text: str, expected_kw: set, expected_sec: set) -> dict:
    """Score a single brief against ground-truth expectations.

    Returns dict with token_coverage, section_coverage, jaccard, rouge_l, overall.
    """
    brief_tokens = _tokenize(brief)

    # 1. Token coverage: fraction of expected keywords found
    found_kw = expected_kw & brief_tokens
    missing_kw = expected_kw - brief_tokens
    token_cov = len(found_kw) / len(expected_kw) if expected_kw else 1.0

    # 2. Section coverage: fraction of expected sections present
    if expected_sec:
        present = _detect_sections(brief)
        found_sec = expected_sec & present
        section_cov = len(found_sec) / len(expected_sec)
    else:
        found_sec = set()
        section_cov = 1.0  # no sections expected for minimal tier

    # 3. Jaccard similarity (task vs brief)
    task_tokens = _tokenize(task_text)
    jac = _jaccard(task_tokens, brief_tokens)

    # 4. ROUGE-L (task vs brief)
    task_seq = _tokenize_seq(task_text)
    brief_seq = _tokenize_seq(brief)
    rl = _rouge_l_f1(task_seq, brief_seq)

    # Weighted overall (section coverage & token coverage matter most)
    overall = (
        0.30 * section_cov
        + 0.30 * token_cov
        + 0.20 * jac
        + 0.20 * rl
    )

    return {
        "token_coverage": round(token_cov, 4),
        "section_coverage": round(section_cov, 4),
        "jaccard": round(jac, 4),
        "rouge_l": round(rl, 4),
        "overall": round(overall, 4),
        "found_keywords": sorted(found_kw),
        "missing_keywords": sorted(missing_kw),
        "found_sections": sorted(found_sec),
        "brief_bytes": len(brief),
    }


def run_benchmark(dry_run: bool = False) -> dict:
    """Run the brief benchmark and return results."""
    # Import brief generator
    try:
        from context_compressor import generate_tiered_brief
    except ImportError:
        try:
            from clarvis.context import generate_tiered_brief
        except ImportError:
            return {"error": "Cannot import generate_tiered_brief"}

    results = []
    for task_text, category, tier, expected_kw, expected_sec in BENCHMARK_TASKS:
        try:
            brief = generate_tiered_brief(task_text, tier=tier)
        except Exception as e:
            results.append({
                "task": task_text[:80],
                "category": category,
                "tier": tier,
                "error": str(e)[:200],
                "overall": 0.0,
            })
            continue

        scores = _score_task(brief, task_text, expected_kw, expected_sec)
        scores["task"] = task_text[:80]
        scores["category"] = category
        scores["tier"] = tier
        results.append(scores)

    # Aggregate
    scored = [r for r in results if "error" not in r]
    n = len(scored)
    _mean = lambda key: round(sum(r[key] for r in scored) / n, 4) if n else 0.0

    by_category: dict[str, list[float]] = {}
    by_tier: dict[str, list[float]] = {}
    for r in scored:
        by_category.setdefault(r["category"], []).append(r["overall"])
        by_tier.setdefault(r["tier"], []).append(r["overall"])

    cat_means = {c: round(sum(v) / len(v), 4) for c, v in by_category.items()}
    tier_means = {t: round(sum(v) / len(v), 4) for t, v in by_tier.items()}
    brief_sizes = [r["brief_bytes"] for r in scored]

    benchmark_result = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "tasks_total": len(BENCHMARK_TASKS),
        "tasks_scored": n,
        "mean_overall": _mean("overall"),
        "mean_token_coverage": _mean("token_coverage"),
        "mean_section_coverage": _mean("section_coverage"),
        "mean_jaccard": _mean("jaccard"),
        "mean_rouge_l": _mean("rouge_l"),
        "by_category": cat_means,
        "by_tier": tier_means,
        "avg_brief_bytes": round(sum(brief_sizes) / len(brief_sizes)) if brief_sizes else 0,
        "per_task": results,
    }

    if not dry_run and n > 0:
        _update_report(benchmark_result)
        _append_history(benchmark_result)

    return benchmark_result


def _update_report(benchmark_result: dict) -> None:
    """Merge benchmark results into brief_v2_report.json."""
    report = {}
    if os.path.exists(REPORT_FILE):
        try:
            with open(REPORT_FILE) as f:
                report = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    report["brief_quality"] = {
        "mean_overall": benchmark_result["mean_overall"],
        "mean_token_coverage": benchmark_result["mean_token_coverage"],
        "mean_section_coverage": benchmark_result["mean_section_coverage"],
        "mean_jaccard": benchmark_result["mean_jaccard"],
        "mean_rouge_l": benchmark_result["mean_rouge_l"],
        "tasks_scored": benchmark_result["tasks_scored"],
        "by_category": benchmark_result["by_category"],
        "by_tier": benchmark_result["by_tier"],
        "avg_brief_bytes": benchmark_result["avg_brief_bytes"],
        "generated": benchmark_result["generated"],
    }

    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)


def _append_history(benchmark_result: dict) -> None:
    """Append summary to JSONL history for trend tracking."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    entry = {
        "ts": benchmark_result["generated"],
        "mean_overall": benchmark_result["mean_overall"],
        "mean_token_coverage": benchmark_result["mean_token_coverage"],
        "mean_section_coverage": benchmark_result["mean_section_coverage"],
        "mean_jaccard": benchmark_result["mean_jaccard"],
        "mean_rouge_l": benchmark_result["mean_rouge_l"],
        "by_category": benchmark_result["by_category"],
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    json_out = "--json" in sys.argv

    result = run_benchmark(dry_run=dry_run)

    if json_out:
        print(json.dumps(result, indent=2))
    else:
        if "error" in result:
            print(f"ERROR: {result['error']}")
            sys.exit(1)

        print(f"Brief Benchmark: {result['tasks_scored']}/{result['tasks_total']} tasks scored")
        print(f"  Overall:  {result['mean_overall']:.3f}")
        print(f"  Tokens:   {result['mean_token_coverage']:.3f}")
        print(f"  Sections: {result['mean_section_coverage']:.3f}")
        print(f"  Jaccard:  {result['mean_jaccard']:.3f}")
        print(f"  ROUGE-L:  {result['mean_rouge_l']:.3f}")
        print(f"  By category: {result['by_category']}")
        print(f"  By tier:     {result['by_tier']}")
        print(f"  Avg brief:   {result['avg_brief_bytes']} bytes")
        print()
        for r in result.get("per_task", []):
            if "error" in r:
                print(f"  [{r['category']:12s}] ERROR {r['task'][:55]}")
                continue
            miss = f" miss={r['missing_keywords']}" if r.get("missing_keywords") else ""
            print(f"  [{r['category']:12s}] {r['overall']:.2f}  "
                  f"tok={r['token_coverage']:.2f} sec={r['section_coverage']:.2f} "
                  f"jac={r['jaccard']:.2f} rl={r['rouge_l']:.2f}  "
                  f"{r['task'][:45]}{miss}")

        if not dry_run and result.get("tasks_scored", 0) > 0:
            print(f"\nReport updated: {REPORT_FILE}")
            print(f"History appended: {HISTORY_FILE}")
