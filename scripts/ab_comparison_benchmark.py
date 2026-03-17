#!/usr/bin/env python3
"""A/B Comparison Benchmark — Clarvis-augmented vs baseline Claude Code.

Compares task outcomes when Claude Code receives Clarvis brain context
(memories, episodes, procedures) vs bare prompts. Measures the value
of the cognitive architecture.

All prompts are written to temp files (never passed as shell args) to
avoid quoting/escaping issues.

Usage:
    python3 ab_comparison_benchmark.py list              # Show task pairs
    python3 ab_comparison_benchmark.py dry-run [N]       # Generate prompt pairs (no execution)
    python3 ab_comparison_benchmark.py run [N]            # Run pair N (both A and B)
    python3 ab_comparison_benchmark.py run-all            # Run all pairs (expensive!)
    python3 ab_comparison_benchmark.py score <N>          # Score results for pair N
    python3 ab_comparison_benchmark.py score-all          # Score all completed pairs
    python3 ab_comparison_benchmark.py report             # Summary report
"""

import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

WORKSPACE = "/home/agent/.openclaw/workspace"
RESULTS_DIR = Path(WORKSPACE) / "data" / "ab_benchmark"
RESULTS_FILE = RESULTS_DIR / "results.json"
CLAUDE_BIN = "/home/agent/.local/bin/claude"
TIMEOUT = 600  # 10 min per task (>=600s required for Claude Code)

# === TASK PAIRS ===
# Each pair is a short, evaluable task with clear success criteria.
# Tasks are designed to complete within the timeout and have deterministic scoring.
TASK_PAIRS = [
    {
        "id": 1,
        "name": "brain_search_function",
        "task": "Write a Python function `search_memories(query, n=5)` that searches ChromaDB collections and returns the top-n results sorted by relevance. Include proper error handling.",
        "eval_criteria": ["function_defined", "chromadb_usage", "error_handling", "returns_sorted"],
        "category": "code_generation",
    },
    {
        "id": 2,
        "name": "fix_import_error",
        "task": "The following Python code has an import error. Fix it:\n```python\nfrom clarvis.brain import search, remember\nresult = search('test query')\nremember(result, importance=0.8)\n```\nExplain what was wrong and provide the corrected version.",
        "eval_criteria": ["identifies_issue", "provides_fix", "explanation"],
        "category": "debugging",
    },
    {
        "id": 3,
        "name": "cron_schedule_analysis",
        "task": "Analyze the cron schedule and identify any time conflicts or gaps. What time slots between 00:00-06:00 CET are unused? List them.",
        "eval_criteria": ["identifies_slots", "correct_analysis", "actionable"],
        "category": "analysis",
    },
    {
        "id": 4,
        "name": "episodic_memory_query",
        "task": "Write a function that retrieves the last 10 episodes, filters to only 'success' outcomes, and returns a summary dict with: count, avg_valence, most_common_task_type.",
        "eval_criteria": ["function_defined", "correct_filtering", "summary_dict", "valence_calc"],
        "category": "code_generation",
    },
    {
        "id": 5,
        "name": "graph_health_check",
        "task": "Write a health check function for a graph database stored in SQLite+WAL. It should verify: WAL file size, journal mode, integrity check, and edge count. Return a dict with status='healthy'|'degraded'|'critical'.",
        "eval_criteria": ["function_defined", "wal_check", "integrity", "status_levels"],
        "category": "code_generation",
    },
    {
        "id": 6,
        "name": "shell_script_fix",
        "task": "Fix this bash script that has a quoting bug:\n```bash\n#!/bin/bash\nTASK=$1\necho Starting task: $TASK\ntimeout 600 claude -p $TASK > /tmp/output.txt 2>&1\n```\nExplain the bug and provide the corrected version.",
        "eval_criteria": ["identifies_quoting", "uses_double_quotes", "explains_word_splitting"],
        "category": "debugging",
    },
    {
        "id": 7,
        "name": "metric_decay_function",
        "task": "Implement an ACT-R power-law decay function: A(t) = ln(sum(t_j^(-d))) where t_j are access times and d=0.5. Include a test with 3 access times.",
        "eval_criteria": ["correct_formula", "math_import", "test_case", "handles_zero"],
        "category": "code_generation",
    },
    {
        "id": 8,
        "name": "json_schema_validation",
        "task": "Write a function that validates an episode JSON object against this schema: must have 'task' (str), 'outcome' (str, one of success/failure/soft_failure), 'valence' (float, -1 to 1), 'timestamp' (ISO format str). Return list of validation errors.",
        "eval_criteria": ["function_defined", "validates_types", "validates_ranges", "returns_errors"],
        "category": "code_generation",
    },
    {
        "id": 9,
        "name": "log_rotation_script",
        "task": "Write a bash function that rotates log files: if a .log file is >10MB, compress it to .log.1.gz, shift existing .gz files up by 1, and keep only 5 rotations.",
        "eval_criteria": ["size_check", "compression", "rotation_shift", "max_kept"],
        "category": "code_generation",
    },
    {
        "id": 10,
        "name": "performance_regression_detector",
        "task": "Write a Python function that reads a JSONL file of performance records (each with 'timestamp' and 'value' fields), detects if the last 3 values show a >10% regression from the rolling 10-value average, and returns a dict with 'regression': bool, 'delta_pct': float.",
        "eval_criteria": ["reads_jsonl", "rolling_average", "regression_detection", "returns_dict"],
        "category": "code_generation",
    },
    {
        "id": 11,
        "name": "context_relevance_scorer",
        "task": "Write a function that scores how relevant a piece of context is to a query using keyword overlap (Jaccard similarity). Input: query string, context string. Output: float 0-1.",
        "eval_criteria": ["jaccard_formula", "tokenization", "returns_float", "handles_empty"],
        "category": "code_generation",
    },
    {
        "id": 12,
        "name": "error_classification",
        "task": "Given this Python traceback, classify the error type and suggest a fix:\n```\nTraceback (most recent call last):\n  File 'brain.py', line 45, in recall\n    results = collection.query(query_texts=[query], n_results=n)\nchromadb.errors.InvalidDimensionException: Embedding dimension 384 does not match collection dimension 768\n```",
        "eval_criteria": ["identifies_dimension_mismatch", "suggests_model_check", "actionable_fix"],
        "category": "debugging",
    },
]


def _get_clarvis_context(task: str) -> str:
    """Build Clarvis brain context for a task (the 'A' condition)."""
    context_parts = []

    # Brain search
    try:
        from clarvis.brain import brain
        results = brain.recall(task, n=5)
        if results:
            context_parts.append("## Relevant Brain Memories")
            for r in results[:5]:
                doc = r.get("document", r) if isinstance(r, dict) else str(r)
                context_parts.append(f"- {str(doc)[:200]}")
    except Exception:
        pass

    # Episodic memory
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        recent = em.get_recent(limit=5)
        if recent:
            context_parts.append("\n## Recent Episodes")
            for ep in recent[:3]:
                context_parts.append(
                    f"- [{ep.get('outcome', '?')}] {ep.get('task', '?')[:100]}"
                )
    except Exception:
        pass

    # Procedural memory
    try:
        from procedural_memory import search_procedures
        procs = search_procedures(task, n=2)
        if procs:
            context_parts.append("\n## Relevant Procedures")
            for p in procs[:2]:
                name = p.get("name", "?") if isinstance(p, dict) else str(p)[:100]
                context_parts.append(f"- {name}")
    except Exception:
        pass

    return "\n".join(context_parts) if context_parts else ""


def _build_prompt(task: str, with_context: bool) -> str:
    """Build a prompt — with or without Clarvis context."""
    if with_context:
        context = _get_clarvis_context(task)
        if context:
            return (
                f"You have access to the following context from your memory system:\n\n"
                f"{context}\n\n"
                f"---\n\n"
                f"TASK: {task}\n\n"
                f"Use the context above if relevant. Provide a complete, working solution."
            )
    return (
        f"TASK: {task}\n\n"
        f"Provide a complete, working solution."
    )


def _run_claude_via_shell(prompt: str, label: str) -> dict:
    """Run Claude Code using shell + temp file. Prompt is written to a temp file
    and read via $(cat ...) in a shell command to avoid arg-length/quoting issues."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix=f"ab_{label}_", delete=False, dir="/tmp"
    ) as pf:
        pf.write(prompt)
        prompt_file = pf.name

    output_file = f"/tmp/ab_output_{label}_{os.getpid()}.txt"

    # Use shell to cat the prompt file — avoids all arg-length and quoting issues
    cmd = (
        f'timeout {TIMEOUT} env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT '
        f'{CLAUDE_BIN} -p "$(cat {prompt_file})" '
        f'--dangerously-skip-permissions --model claude-opus-4-6 '
        f'> {output_file} 2>&1'
    )

    start = time.monotonic()
    try:
        exit_code = os.system(cmd)
        exit_code = os.waitstatus_to_exitcode(exit_code) if hasattr(os, 'waitstatus_to_exitcode') else exit_code >> 8
        elapsed = time.monotonic() - start

        output = ""
        if os.path.exists(output_file):
            with open(output_file, "r", errors="replace") as f:
                output = f.read()
    except Exception as e:
        elapsed = time.monotonic() - start
        output = f"ERROR: {e}"
        exit_code = 1
    finally:
        for f in [prompt_file, output_file]:
            try:
                os.unlink(f)
            except OSError:
                pass

    return {
        "output": output[:5000],
        "exit_code": exit_code,
        "elapsed_s": round(elapsed, 1),
        "output_length": len(output),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _score_output(output: str, criteria: list) -> dict:
    """Score an output against eval criteria using simple heuristic checks."""
    scores = {}
    text = output.lower()

    criterion_checks = {
        # Code generation checks
        "function_defined": lambda t: bool(re.search(r'def \w+\(', t)),
        "chromadb_usage": lambda t: "chromadb" in t or "collection" in t or "query" in t,
        "error_handling": lambda t: "try" in t and "except" in t,
        "returns_sorted": lambda t: "sort" in t or "sorted" in t or "order" in t,
        "correct_filtering": lambda t: "filter" in t or "== " in t or "if " in t,
        "summary_dict": lambda t: "dict" in t or "{" in t,
        "valence_calc": lambda t: "valence" in t,
        "correct_formula": lambda t: "ln" in t or "log" in t or "math.log" in t,
        "math_import": lambda t: "import math" in t or "from math" in t,
        "test_case": lambda t: "test" in t or "assert" in t or "print(" in t,
        "handles_zero": lambda t: "zero" in t or "== 0" in t or "> 0" in t or "max(" in t,
        "validates_types": lambda t: "isinstance" in t or "type(" in t or "str" in t,
        "validates_ranges": lambda t: ">=" in t or "<=" in t or "between" in t or "range" in t,
        "returns_errors": lambda t: "error" in t and ("list" in t or "append" in t or "[]" in t),
        "reads_jsonl": lambda t: "jsonl" in t or "readline" in t or "json.loads" in t,
        "rolling_average": lambda t: "average" in t or "mean" in t or "sum(" in t,
        "regression_detection": lambda t: "regression" in t or "decrease" in t or "drop" in t,
        "returns_dict": lambda t: "dict" in t or "return {" in t or "return{" in t,
        "jaccard_formula": lambda t: "jaccard" in t or "intersection" in t or "union" in t,
        "tokenization": lambda t: "split" in t or "token" in t or "word" in t,
        "returns_float": lambda t: "float" in t or "return " in t,
        "handles_empty": lambda t: "empty" in t or "not " in t or "len(" in t or "if " in t,
        # Debugging checks
        "identifies_issue": lambda t: "issue" in t or "problem" in t or "error" in t or "bug" in t,
        "provides_fix": lambda t: "fix" in t or "correct" in t or "solution" in t,
        "explanation": lambda t: "because" in t or "reason" in t or "the " in t,
        "identifies_quoting": lambda t: "quot" in t or "expand" in t or "split" in t,
        "uses_double_quotes": lambda t: '"$' in t or '"${' in t,
        "explains_word_splitting": lambda t: "split" in t or "glob" in t or "whitespace" in t or "space" in t,
        "identifies_dimension_mismatch": lambda t: "dimension" in t or "384" in t or "768" in t,
        "suggests_model_check": lambda t: "model" in t or "embedding" in t,
        "actionable_fix": lambda t: "change" in t or "use" in t or "switch" in t or "update" in t,
        # Analysis checks
        "identifies_slots": lambda t: any(f"{h}:" in t or f"{h}:00" in t for h in ["00", "01", "02", "03", "04", "05"]),
        "correct_analysis": lambda t: "gap" in t or "unused" in t or "available" in t or "free" in t,
        "actionable": lambda t: "could" in t or "suggest" in t or "recommend" in t or "use" in t,
        # Shell checks
        "size_check": lambda t: "size" in t or "stat" in t or "-gt" in t or "du " in t,
        "compression": lambda t: "gzip" in t or "gz" in t or "compress" in t,
        "rotation_shift": lambda t: "mv " in t or "rename" in t or "shift" in t or "rotate" in t,
        "max_kept": lambda t: "5" in t or "keep" in t or "rm " in t or "remove" in t,
        # WAL checks
        "wal_check": lambda t: "wal" in t,
        "integrity": lambda t: "integrity" in t or "pragma" in t,
        "status_levels": lambda t: "healthy" in t or "critical" in t or "degraded" in t,
    }

    met = 0
    for c in criteria:
        check = criterion_checks.get(c)
        if check:
            passed = check(text)
            scores[c] = passed
            if passed:
                met += 1
        else:
            scores[c] = False

    return {
        "criteria_met": met,
        "criteria_total": len(criteria),
        "score": round(met / max(len(criteria), 1), 3),
        "details": scores,
    }


def _load_results() -> dict:
    """Load existing results."""
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return {"pairs": {}, "summary": {}, "last_updated": None}


def _save_results(results: dict):
    """Save results."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, default=str)


def cmd_list():
    """List all task pairs."""
    print(f"{'ID':>3}  {'Name':<35}  {'Category':<15}  Criteria")
    print("-" * 75)
    for pair in TASK_PAIRS:
        print(f"{pair['id']:>3}  {pair['name']:<35}  {pair['category']:<15}  {len(pair['eval_criteria'])}")
    print(f"\nTotal: {len(TASK_PAIRS)} task pairs")


def cmd_dry_run(pair_id=None):
    """Generate prompt pairs without execution."""
    pairs = TASK_PAIRS if pair_id is None else [p for p in TASK_PAIRS if p["id"] == pair_id]
    if not pairs:
        print(f"No task pair with id={pair_id}")
        return

    for pair in pairs:
        prompt_a = _build_prompt(pair["task"], with_context=True)
        prompt_b = _build_prompt(pair["task"], with_context=False)

        print(f"\n{'='*60}")
        print(f"PAIR {pair['id']}: {pair['name']} ({pair['category']})")
        print(f"{'='*60}")
        print(f"\n--- A (Clarvis-augmented) [{len(prompt_a)} chars] ---")
        print(prompt_a[:500])
        if len(prompt_a) > 500:
            print(f"  ... [{len(prompt_a) - 500} more chars]")
        print(f"\n--- B (Baseline) [{len(prompt_b)} chars] ---")
        print(prompt_b[:500])
        print(f"\nEval criteria: {', '.join(pair['eval_criteria'])}")


def cmd_run(pair_id: int):
    """Run a single pair (both A and B)."""
    pair = next((p for p in TASK_PAIRS if p["id"] == pair_id), None)
    if not pair:
        print(f"No task pair with id={pair_id}")
        return

    results = _load_results()

    print(f"Running pair {pair_id}: {pair['name']}")

    # Run A (Clarvis-augmented)
    print(f"  Running A (Clarvis-augmented)...")
    prompt_a = _build_prompt(pair["task"], with_context=True)
    result_a = _run_claude_via_shell(prompt_a, f"A_{pair_id}")
    print(f"  A: exit={result_a['exit_code']}, {result_a['elapsed_s']}s, {result_a['output_length']} chars")

    # Run B (baseline)
    print(f"  Running B (baseline)...")
    prompt_b = _build_prompt(pair["task"], with_context=False)
    result_b = _run_claude_via_shell(prompt_b, f"B_{pair_id}")
    print(f"  B: exit={result_b['exit_code']}, {result_b['elapsed_s']}s, {result_b['output_length']} chars")

    # Score both
    score_a = _score_output(result_a["output"], pair["eval_criteria"])
    score_b = _score_output(result_b["output"], pair["eval_criteria"])

    results["pairs"][str(pair_id)] = {
        "name": pair["name"],
        "category": pair["category"],
        "a_clarvis": {**result_a, "score": score_a},
        "b_baseline": {**result_b, "score": score_b},
        "delta": round(score_a["score"] - score_b["score"], 3),
        "clarvis_wins": score_a["score"] > score_b["score"],
    }

    _save_results(results)
    print(f"  Score A: {score_a['score']:.3f} ({score_a['criteria_met']}/{score_a['criteria_total']})")
    print(f"  Score B: {score_b['score']:.3f} ({score_b['criteria_met']}/{score_b['criteria_total']})")
    print(f"  Delta: {score_a['score'] - score_b['score']:+.3f} ({'Clarvis wins' if score_a['score'] > score_b['score'] else 'Baseline wins' if score_b['score'] > score_a['score'] else 'Tie'})")


def cmd_run_all():
    """Run all pairs (expensive — uses ~24 Claude Code invocations)."""
    print(f"WARNING: This will run {len(TASK_PAIRS) * 2} Claude Code invocations.")
    print(f"Estimated cost: ~$2-4, time: ~{len(TASK_PAIRS) * 10} minutes")
    confirm = input("Continue? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    for pair in TASK_PAIRS:
        cmd_run(pair["id"])
        print()


def cmd_score(pair_id: int):
    """Re-score a completed pair."""
    results = _load_results()
    key = str(pair_id)
    if key not in results["pairs"]:
        print(f"No results for pair {pair_id}. Run it first.")
        return

    pair = next((p for p in TASK_PAIRS if p["id"] == pair_id), None)
    if not pair:
        print(f"No task pair definition for id={pair_id}")
        return

    r = results["pairs"][key]
    score_a = _score_output(r["a_clarvis"]["output"], pair["eval_criteria"])
    score_b = _score_output(r["b_baseline"]["output"], pair["eval_criteria"])

    r["a_clarvis"]["score"] = score_a
    r["b_baseline"]["score"] = score_b
    r["delta"] = round(score_a["score"] - score_b["score"], 3)
    r["clarvis_wins"] = score_a["score"] > score_b["score"]

    _save_results(results)
    print(f"Pair {pair_id} ({pair['name']}):")
    print(f"  A (Clarvis): {score_a['score']:.3f} — {score_a['details']}")
    print(f"  B (Baseline): {score_b['score']:.3f} — {score_b['details']}")
    print(f"  Delta: {r['delta']:+.3f}")


def cmd_score_all():
    """Re-score all completed pairs."""
    results = _load_results()
    for key in results["pairs"]:
        cmd_score(int(key))
        print()


def cmd_report():
    """Generate summary report."""
    results = _load_results()
    pairs = results.get("pairs", {})

    if not pairs:
        print("No results yet. Run some task pairs first.")
        print(f"Available: {len(TASK_PAIRS)} task pairs")
        print("Use: python3 ab_comparison_benchmark.py run <N>")
        return

    print("=" * 60)
    print("A/B COMPARISON BENCHMARK REPORT")
    print("=" * 60)

    wins_a = sum(1 for p in pairs.values() if p.get("clarvis_wins"))
    wins_b = sum(1 for p in pairs.values() if not p.get("clarvis_wins") and p.get("delta", 0) < 0)
    ties = len(pairs) - wins_a - wins_b

    print(f"\nCompleted: {len(pairs)}/{len(TASK_PAIRS)} pairs")
    print(f"Clarvis wins: {wins_a}  |  Baseline wins: {wins_b}  |  Ties: {ties}")

    avg_delta = sum(p.get("delta", 0) for p in pairs.values()) / max(len(pairs), 1)
    print(f"Average delta: {avg_delta:+.3f}")

    # Per-category breakdown
    categories = {}
    for p in pairs.values():
        cat = p.get("category", "unknown")
        categories.setdefault(cat, []).append(p.get("delta", 0))

    if categories:
        print(f"\nPer-category:")
        for cat, deltas in sorted(categories.items()):
            avg = sum(deltas) / len(deltas)
            print(f"  {cat:<20} avg_delta={avg:+.3f}  n={len(deltas)}")

    # Per-pair details
    print(f"\n{'ID':>3}  {'Name':<30}  {'A':>6}  {'B':>6}  {'Delta':>7}  Winner")
    print("-" * 70)
    for key in sorted(pairs.keys(), key=int):
        p = pairs[key]
        sa = p.get("a_clarvis", {}).get("score", {}).get("score", "?")
        sb = p.get("b_baseline", {}).get("score", {}).get("score", "?")
        delta = p.get("delta", 0)
        winner = "Clarvis" if delta > 0 else "Baseline" if delta < 0 else "Tie"
        name = p.get("name", "?")[:30]
        print(f"{key:>3}  {name:<30}  {sa:>6}  {sb:>6}  {delta:>+7.3f}  {winner}")

    print(f"\nLast updated: {results.get('last_updated', 'never')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        cmd_list()
    elif cmd == "dry-run":
        pair_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
        cmd_dry_run(pair_id)
    elif cmd == "run":
        if len(sys.argv) < 3:
            print("Usage: ab_comparison_benchmark.py run <pair_id>")
            sys.exit(1)
        cmd_run(int(sys.argv[2]))
    elif cmd == "run-all":
        cmd_run_all()
    elif cmd == "score":
        if len(sys.argv) < 3:
            print("Usage: ab_comparison_benchmark.py score <pair_id>")
            sys.exit(1)
        cmd_score(int(sys.argv[2]))
    elif cmd == "score-all":
        cmd_score_all()
    elif cmd == "report":
        cmd_report()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
