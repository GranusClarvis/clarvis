#!/usr/bin/env python3
"""A/B Comparison Benchmark — compare two brief generation approaches.

Runs 12 task pairs through two brief generators (compressor vs assembly),
scoring each on token coverage, section coverage, Jaccard, ROUGE-L, and
overall quality. Measures wall-clock duration per generation. Reports
which approach wins per task and aggregated.

Prompts are written to temp files (matching spawn_claude pattern) before
evaluation — no actual Claude invocations.

Results: data/benchmarks/ab_comparison_latest.json
History: data/benchmarks/ab_comparison_history.jsonl

Usage:
    python3 ab_comparison_benchmark.py              # Full benchmark
    python3 ab_comparison_benchmark.py --dry-run    # Run without persisting
    python3 ab_comparison_benchmark.py --json       # Raw JSON output
    python3 ab_comparison_benchmark.py trend [days] # Show trend
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = os.path.join(WORKSPACE, "data", "benchmarks")
RESULT_FILE = os.path.join(DATA_DIR, "ab_comparison_latest.json")
HISTORY_FILE = os.path.join(DATA_DIR, "ab_comparison_history.jsonl")


# ── Scoring functions (shared with brief_benchmark) ─────────────────────

import re

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
    """Extract meaningful lowercase tokens as ordered sequence."""
    return [w for w in re.findall(r"[a-z][a-z0-9_]{2,}", text.lower()) if w not in _STOPWORDS]


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _rouge_l_f1(reference: list[str], candidate: list[str]) -> float:
    if not reference or not candidate:
        return 0.0
    m, n = len(reference), len(candidate)
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


def _score_brief(brief: str, task_text: str, expected_kw: set, expected_sec: set) -> dict:
    """Score a brief against ground-truth expectations."""
    brief_tokens = _tokenize(brief)

    found_kw = expected_kw & brief_tokens
    token_cov = len(found_kw) / len(expected_kw) if expected_kw else 1.0

    if expected_sec:
        present = _detect_sections(brief)
        found_sec = expected_sec & present
        section_cov = len(found_sec) / len(expected_sec)
    else:
        found_sec = set()
        section_cov = 1.0

    task_tokens = _tokenize(task_text)
    jac = _jaccard(task_tokens, brief_tokens)

    task_seq = _tokenize_seq(task_text)
    brief_seq = _tokenize_seq(brief)
    rl = _rouge_l_f1(task_seq, brief_seq)

    overall = 0.30 * section_cov + 0.30 * token_cov + 0.20 * jac + 0.20 * rl

    return {
        "token_coverage": round(token_cov, 4),
        "section_coverage": round(section_cov, 4),
        "jaccard": round(jac, 4),
        "rouge_l": round(rl, 4),
        "overall": round(overall, 4),
        "found_keywords": sorted(found_kw),
        "found_sections": sorted(found_sec),
        "brief_bytes": len(brief),
    }


# ── A/B Test pairs ──────────────────────────────────────────────────────
# 12 tasks covering code, research, maintenance across tiers.
# Each: (task_text, category, tier, expected_keywords, expected_sections)

AB_TASKS = [
    # CODE
    (
        "Implement adaptive MMR lambda tuning for context_compressor.py",
        "code", "full",
        {"implement", "lambda", "context", "compressor", "mmr", "success"},
        {"decision_context", "reasoning", "metrics"},
    ),
    (
        "Fix broken regex in queue_writer.py causing task parsing failures",
        "code", "standard",
        {"fix", "regex", "queue", "parsing", "success"},
        {"decision_context", "reasoning"},
    ),
    (
        "Add pytest coverage for clarvis.brain.search module",
        "code", "full",
        {"test", "pytest", "brain", "search", "coverage", "success"},
        {"decision_context", "reasoning", "metrics"},
    ),
    (
        "Refactor heartbeat_postflight.py to extract episode encoding",
        "code", "standard",
        {"refactor", "heartbeat", "postflight", "episode", "success"},
        {"decision_context", "reasoning"},
    ),
    (
        "Implement bloom filter for fast duplicate detection in brain.store()",
        "code", "full",
        {"implement", "bloom", "filter", "duplicate", "brain", "store"},
        {"decision_context", "reasoning", "metrics"},
    ),
    # RESEARCH
    (
        "Research CRAG retrieval-augmented generation patterns for adaptive retrieval",
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
    (
        "Survey LLM self-reflection techniques for autonomous agents",
        "research", "full",
        {"survey", "reflection", "techniques", "agents"},
        {"decision_context", "reasoning"},
    ),
    # MAINTENANCE
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
        set(),
    ),
    (
        "Cron watchdog check — verify all scheduled jobs ran successfully",
        "maintenance", "standard",
        {"cron", "watchdog", "success"},
        {"decision_context", "reasoning"},
    ),
]


def _load_generator(name: str):
    """Load a brief generator by name. Returns (generate_fn, label)."""
    if name == "compressor":
        try:
            from clarvis.context.compressor import generate_tiered_brief
            return generate_tiered_brief, "compressor"
        except ImportError:
            try:
                from context_compressor import generate_tiered_brief
                return generate_tiered_brief, "compressor(legacy)"
            except ImportError:
                return None, "compressor(missing)"
    elif name == "assembly":
        try:
            from clarvis.context.assembly import generate_tiered_brief
            return generate_tiered_brief, "assembly"
        except ImportError:
            try:
                from context_compressor import generate_tiered_brief as _gtb
                # Fall back to same generator but with different params
                return None, "assembly(missing)"
            except ImportError:
                return None, "assembly(missing)"
    return None, f"{name}(unknown)"


def _write_prompt_to_tempfile(task_text: str, brief: str) -> str:
    """Write assembled prompt to a temp file (matches spawn_claude pattern).

    Returns the temp file path. Caller should clean up.
    """
    fd, path = tempfile.mkstemp(prefix="ab_bench_", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("You are Clarvis's executive function (Claude Code Opus).\n\n")
            if brief:
                f.write(f"CONTEXT:\n{brief}\n\n")
            f.write(f"TASK: {task_text}\n\n")
            f.write("Be thorough. Write code if needed. Test it. Report what you did concisely.\n")
    except Exception:
        os.close(fd)
        raise
    return path


def run_benchmark(dry_run: bool = False) -> dict:
    """Run A/B comparison benchmark. Returns results dict."""
    gen_a_fn, label_a = _load_generator("compressor")
    gen_b_fn, label_b = _load_generator("assembly")

    if not gen_a_fn and not gen_b_fn:
        return {"error": "Neither brief generator could be imported"}

    pairs = []
    temp_files = []

    for task_text, category, tier, expected_kw, expected_sec in AB_TASKS:
        pair = {
            "task": task_text[:80],
            "category": category,
            "tier": tier,
        }

        # --- Approach A ---
        if gen_a_fn:
            try:
                t0 = time.monotonic()
                brief_a = gen_a_fn(current_task=task_text, tier=tier)
                dur_a = time.monotonic() - t0
                # Write to temp file (verify temp-file prompt pattern works)
                tf_a = _write_prompt_to_tempfile(task_text, brief_a)
                temp_files.append(tf_a)
                score_a = _score_brief(brief_a, task_text, expected_kw, expected_sec)
                pair["a"] = {
                    "label": label_a,
                    "duration_ms": round(dur_a * 1000, 1),
                    "success": True,
                    "prompt_file": tf_a,
                    **score_a,
                }
            except Exception as e:
                pair["a"] = {
                    "label": label_a,
                    "success": False,
                    "error": str(e)[:200],
                    "overall": 0.0,
                    "duration_ms": 0,
                }
        else:
            pair["a"] = {"label": label_a, "success": False, "error": "import failed", "overall": 0.0, "duration_ms": 0}

        # --- Approach B ---
        if gen_b_fn:
            try:
                t0 = time.monotonic()
                brief_b = gen_b_fn(current_task=task_text, tier=tier)
                dur_b = time.monotonic() - t0
                tf_b = _write_prompt_to_tempfile(task_text, brief_b)
                temp_files.append(tf_b)
                score_b = _score_brief(brief_b, task_text, expected_kw, expected_sec)
                pair["b"] = {
                    "label": label_b,
                    "duration_ms": round(dur_b * 1000, 1),
                    "success": True,
                    "prompt_file": tf_b,
                    **score_b,
                }
            except Exception as e:
                pair["b"] = {
                    "label": label_b,
                    "success": False,
                    "error": str(e)[:200],
                    "overall": 0.0,
                    "duration_ms": 0,
                }
        else:
            pair["b"] = {"label": label_b, "success": False, "error": "import failed", "overall": 0.0, "duration_ms": 0}

        # Winner
        oa = pair["a"].get("overall", 0)
        ob = pair["b"].get("overall", 0)
        if oa > ob + 0.01:
            pair["winner"] = "a"
        elif ob > oa + 0.01:
            pair["winner"] = "b"
        else:
            pair["winner"] = "tie"

        pairs.append(pair)

    # Cleanup temp files
    for tf in temp_files:
        try:
            os.unlink(tf)
        except OSError:
            pass

    # Aggregate
    a_scores = [p["a"]["overall"] for p in pairs if p["a"].get("success")]
    b_scores = [p["b"]["overall"] for p in pairs if p["b"].get("success")]
    a_durations = [p["a"]["duration_ms"] for p in pairs if p["a"].get("success")]
    b_durations = [p["b"]["duration_ms"] for p in pairs if p["b"].get("success")]

    a_wins = sum(1 for p in pairs if p["winner"] == "a")
    b_wins = sum(1 for p in pairs if p["winner"] == "b")
    ties = sum(1 for p in pairs if p["winner"] == "tie")

    result = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "pairs_total": len(AB_TASKS),
        "approach_a": label_a,
        "approach_b": label_b,
        "a_mean_overall": round(sum(a_scores) / len(a_scores), 4) if a_scores else 0.0,
        "b_mean_overall": round(sum(b_scores) / len(b_scores), 4) if b_scores else 0.0,
        "a_mean_duration_ms": round(sum(a_durations) / len(a_durations), 1) if a_durations else 0.0,
        "b_mean_duration_ms": round(sum(b_durations) / len(b_durations), 1) if b_durations else 0.0,
        "a_success_count": len(a_scores),
        "b_success_count": len(b_scores),
        "a_wins": a_wins,
        "b_wins": b_wins,
        "ties": ties,
        "per_pair": pairs,
    }

    # By category breakdown
    for key_name, approach_key in [("a", "a"), ("b", "b")]:
        by_cat: dict[str, list[float]] = {}
        for p in pairs:
            if p[approach_key].get("success"):
                by_cat.setdefault(p["category"], []).append(p[approach_key]["overall"])
        result[f"{key_name}_by_category"] = {
            c: round(sum(v) / len(v), 4) for c, v in by_cat.items()
        }

    if not dry_run:
        _persist(result)

    return result


def _persist(result: dict) -> None:
    """Save latest result and append to history."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Strip prompt_file paths from persisted data (temp files are cleaned up)
    clean = json.loads(json.dumps(result))
    for p in clean.get("per_pair", []):
        for k in ("a", "b"):
            p.get(k, {}).pop("prompt_file", None)

    with open(RESULT_FILE, "w") as f:
        json.dump(clean, f, indent=2)

    summary = {
        "ts": result["generated"],
        "pairs": result["pairs_total"],
        "a_label": result["approach_a"],
        "b_label": result["approach_b"],
        "a_mean": result["a_mean_overall"],
        "b_mean": result["b_mean_overall"],
        "a_wins": result["a_wins"],
        "b_wins": result["b_wins"],
        "ties": result["ties"],
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(summary) + "\n")


def show_trend(days: int = 30) -> None:
    """Show A/B comparison trend from history."""
    if not os.path.exists(HISTORY_FILE):
        print("No history found. Run benchmark first.")
        return

    entries = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        print("No entries in history.")
        return

    print(f"=== A/B Comparison Trend — Last {len(entries)} Runs ===")
    for e in entries[-days:]:
        ts = e.get("ts", "?")[:10]
        a_m = e.get("a_mean", 0)
        b_m = e.get("b_mean", 0)
        aw = e.get("a_wins", 0)
        bw = e.get("b_wins", 0)
        t = e.get("ties", 0)
        leader = "A" if a_m > b_m else ("B" if b_m > a_m else "=")
        print(f"  {ts}  A={a_m:.3f} B={b_m:.3f}  wins: A={aw} B={bw} tie={t}  leader={leader}")


def _format_result(result: dict) -> None:
    """Pretty-print benchmark result."""
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return

    print(f"A/B Comparison Benchmark: {result['pairs_total']} pairs")
    print(f"  Approach A: {result['approach_a']}")
    print(f"  Approach B: {result['approach_b']}")
    print()
    print(f"  A mean quality: {result['a_mean_overall']:.3f}  ({result['a_success_count']} succeeded)")
    print(f"  B mean quality: {result['b_mean_overall']:.3f}  ({result['b_success_count']} succeeded)")
    print(f"  A mean duration: {result['a_mean_duration_ms']:.1f}ms")
    print(f"  B mean duration: {result['b_mean_duration_ms']:.1f}ms")
    print(f"  Wins: A={result['a_wins']} B={result['b_wins']} tie={result['ties']}")
    print()

    # By category
    a_cat = result.get("a_by_category", {})
    b_cat = result.get("b_by_category", {})
    cats = sorted(set(list(a_cat.keys()) + list(b_cat.keys())))
    if cats:
        print("  By category:")
        for c in cats:
            a_v = a_cat.get(c, 0)
            b_v = b_cat.get(c, 0)
            delta = a_v - b_v
            print(f"    {c:15s}  A={a_v:.3f}  B={b_v:.3f}  delta={'+' if delta >= 0 else ''}{delta:.3f}")
        print()

    # Per-pair detail
    for p in result.get("per_pair", []):
        w = p.get("winner", "?")
        oa = p["a"].get("overall", 0)
        ob = p["b"].get("overall", 0)
        da = p["a"].get("duration_ms", 0)
        db = p["b"].get("duration_ms", 0)
        err_a = " ERR" if not p["a"].get("success") else ""
        err_b = " ERR" if not p["b"].get("success") else ""
        print(f"  [{p['category']:12s}] A={oa:.2f}{err_a} B={ob:.2f}{err_b}  "
              f"d={da:.0f}/{db:.0f}ms  win={w}  {p['task'][:40]}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "trend" in args:
        idx = args.index("trend")
        days = int(args[idx + 1]) if idx + 1 < len(args) else 30
        show_trend(days)
        sys.exit(0)

    dry_run = "--dry-run" in args
    json_out = "--json" in args

    result = run_benchmark(dry_run=dry_run)

    if json_out:
        print(json.dumps(result, indent=2))
    else:
        _format_result(result)
        if not dry_run and "error" not in result:
            print(f"\nResults: {RESULT_FILE}")
            print(f"History: {HISTORY_FILE}")
