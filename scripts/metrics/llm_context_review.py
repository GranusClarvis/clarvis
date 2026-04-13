#!/usr/bin/env python3
"""
llm_context_review.py — LLM-judged context & prompt quality review.

Parallels llm_brain_review.py but evaluates the context assembly pipeline
instead of brain retrieval. Samples recent context briefs, analyzes section
relevance patterns, prompt variant performance, and asks Claude Code to
judge: was the right information included? was anything critical missing?
was there noise that shouldn't have been there?

Two-phase architecture:
  Phase 1 (prepare): Pure Python — reads recent briefs, aggregates context
    relevance data, loads prompt optimizer stats, builds prompt.
    Output: prompt file for Claude Code.
  Phase 2 (process): Pure Python — parses Claude's response, stores structured
    results, writes digest entry, pushes queue recommendations.

The cron wrapper (cron_llm_context_review.sh) orchestrates:
  prepare → Claude Code → process

Usage:
    python3 scripts/metrics/llm_context_review.py prepare         # → /tmp/context_review_prompt.txt
    python3 scripts/metrics/llm_context_review.py process <file>  # Parse Claude output → store + wire
    python3 scripts/metrics/llm_context_review.py report          # Print latest review
    python3 scripts/metrics/llm_context_review.py history         # Print review history summary

Output:
    data/llm_context_review/latest.json     — structured review result
    data/llm_context_review/history.jsonl   — rolling history (max 90)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))

REVIEW_DIR = os.path.join(WORKSPACE, "data/llm_context_review")
LATEST_FILE = os.path.join(REVIEW_DIR, "latest.json")
HISTORY_FILE = os.path.join(REVIEW_DIR, "history.jsonl")
PROMPT_FILE = "/tmp/context_review_prompt.txt"
MAX_HISTORY = 90


def _ensure_dirs():
    os.makedirs(REVIEW_DIR, exist_ok=True)


# ── Data Collection ─────────────────────────────────────────────────────

def _load_recent_relevance(days=7):
    """Load per-section context relevance data from recent episodes."""
    cr_file = os.path.join(WORKSPACE, "data/retrieval_quality/context_relevance.jsonl")
    if not os.path.exists(cr_file):
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    entries = []
    try:
        with open(cr_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("timestamp", "") >= cutoff:
                        entries.append(entry)
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return entries[-50:]  # Cap at 50 most recent


def _aggregate_section_scores(entries):
    """Aggregate per-section relevance scores across episodes."""
    section_scores = {}
    for entry in entries:
        per_section = entry.get("per_section", {})
        for section, score in per_section.items():
            if section not in section_scores:
                section_scores[section] = []
            if isinstance(score, (int, float)):
                section_scores[section].append(score)

    result = {}
    for section, scores in section_scores.items():
        if scores:
            result[section] = {
                "mean": round(sum(scores) / len(scores), 3),
                "min": round(min(scores), 3),
                "max": round(max(scores), 3),
                "count": len(scores),
            }
    return result


def _load_prompt_optimizer_stats():
    """Load prompt variant performance stats."""
    stats_file = os.path.join(WORKSPACE, "data/prompt_optimization/variant_stats.json")
    if not os.path.exists(stats_file):
        return None
    try:
        with open(stats_file) as f:
            return json.load(f)
    except Exception:
        return None


def _load_brief_benchmark():
    """Load latest brief benchmark results."""
    report_file = os.path.join(WORKSPACE, "data/benchmarks/brief_v2_report.json")
    if not os.path.exists(report_file):
        return None
    try:
        with open(report_file) as f:
            return json.load(f)
    except Exception:
        return None


def _load_recent_brief_samples(n=5):
    """Load the most recent context briefs from heartbeat preflight data."""
    preflight_file = os.path.join(WORKSPACE, "data/heartbeat_preflight.json")
    if not os.path.exists(preflight_file):
        return []

    try:
        with open(preflight_file) as f:
            data = json.load(f)
        brief = data.get("context_brief", "")
        task = data.get("next_task", data.get("task", ""))
        tier = data.get("brief_tier", "unknown")
        if brief:
            return [{
                "task": task[:200] if isinstance(task, str) else str(task)[:200],
                "tier": tier,
                "brief_chars": len(brief),
                "brief_preview": brief[:1500],
                "sections_found": _detect_sections(brief),
            }]
    except Exception:
        pass
    return []


def _detect_sections(brief_text):
    """Detect which sections are present in a brief."""
    section_patterns = {
        "decision_context": r"SUCCESS CRITERIA|CONSTRAINTS|DECISION CONTEXT",
        "knowledge": r"RELEVANT KNOWLEDGE:",
        "working_memory": r"WORKING MEMORY|COGNITIVE WORKSPACE|ACTIVE BUFFER",
        "related_tasks": r"RELATED TASKS:",
        "metrics": r"METRICS:",
        "episodes": r"EPISODIC LESSONS|EPISODIC HINTS|LESSONS FROM",
        "reasoning": r"REASONING|THINK BEFORE|APPROACH:",
        "brain_goals": r"BRAIN GOALS",
        "failure_avoidance": r"FAILURE AVOIDANCE|AVOID THESE FAILURE PATTERNS",
        "attention": r"ATTENTION CODELETS",
        "gwt_broadcast": r"GWT BROADCAST",
    }
    found = []
    for name, pattern in section_patterns.items():
        if re.search(pattern, brief_text, re.IGNORECASE | re.MULTILINE):
            found.append(name)
    return found


def _load_dycp_stats():
    """Load DYCP suppression stats if available."""
    try:
        from clarvis.context.dycp import get_suppression_stats
        return get_suppression_stats()
    except Exception:
        return None


def _load_metric_snapshot():
    """Load current CLR context dimension + PI context quality."""
    snapshot = {}

    clr_file = os.path.join(WORKSPACE, "data/clr_benchmark.json")
    if os.path.exists(clr_file):
        try:
            with open(clr_file) as f:
                clr = json.load(f)
            snapshot["clr"] = clr.get("clr")
            dims = clr.get("dimensions", {})
            snapshot["clr_context_dim"] = dims.get("prompt_context", dims.get("context"))
        except Exception:
            pass

    pi_file = os.path.join(WORKSPACE, "data/performance_metrics.json")
    if os.path.exists(pi_file):
        try:
            with open(pi_file) as f:
                pi = json.load(f)
            snapshot["pi"] = pi.get("pi", pi.get("score"))
            snapshot["pi_context_quality"] = pi.get("context_quality")
        except Exception:
            pass

    return snapshot


def _load_review_history():
    """Load recent LLM context review history for trend analysis."""
    if not os.path.exists(HISTORY_FILE):
        return []
    entries = []
    try:
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return entries[-7:]  # Last week


# ── Prompt Building ─────────────────────────────────────────────────────

_REVIEW_PROMPT_TEMPLATE = """You are reviewing the context assembly and prompt quality of Clarvis, a cognitive AI agent.

## Your Task

Evaluate whether the context assembly pipeline is putting the right information in front of the executor (Claude Code). Judge: is the right information included? Is anything critical missing? Is there noise that shouldn't be there? Are the prompt variants effective?

## How Context Assembly Works

1. **Retrieval Gate** classifies tasks as NO/LIGHT/DEEP retrieval
2. **Brain recall** fetches semantically relevant memories (ACT-R scored)
3. **Token budgets** allocate per-section limits based on 14-day relevance
4. **DYCP** suppresses low-relevance sections (< 0.12 mean relevance)
5. **Adaptive MMR** reranks results (code: λ=0.7 relevance, research: λ=0.4 diversity)
6. **Prompt optimizer** selects approach/framing variants via Thompson sampling
7. The assembled brief is passed to Claude Code as execution context

## Recent Context Briefs

{brief_section}

## Per-Section Relevance Scores (7-day aggregate)

{relevance_section}

## Prompt Variant Performance

{optimizer_section}

## Brief Benchmark Results

{benchmark_section}

## Current Metrics

{metrics_section}

## Prior Context Review History (last 7 days)

{history_section}

## Required Output Format

You MUST respond with a JSON block (```json ... ```) containing exactly these fields:

```json
{{
  "overall_score": <float 0.0-1.0>,
  "information_completeness": <float 0.0-1.0>,
  "noise_level": <float 0.0-1.0>,
  "section_balance": <float 0.0-1.0>,
  "prompt_variant_effectiveness": <float 0.0-1.0>,
  "improving": <"yes"|"no"|"unclear">,
  "sections_analysis": [
    {{
      "section": "<section name>",
      "verdict": <"essential"|"useful"|"marginal"|"noise">,
      "score": <float 0.0-1.0>,
      "reasoning": "<1-2 sentences>"
    }}
  ],
  "strengths": ["<strength 1>", "<strength 2>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>"],
  "recommendations": [
    {{
      "action": "<specific actionable recommendation>",
      "priority": "<P0|P1|P2>",
      "rationale": "<why this matters>"
    }}
  ],
  "narrative": "<3-5 sentence overall assessment>"
}}
```

## Scoring Guidance

- **overall_score**: Holistic context quality. 0.9+ = excellent, 0.7-0.9 = good, 0.5-0.7 = needs work, <0.5 = concerning.
- **information_completeness**: Does the brief contain what the executor needs? 1.0 = nothing critical missing.
- **noise_level**: How much irrelevant content is included? 1.0 = zero noise, 0.0 = mostly noise.
- **section_balance**: Are tokens allocated well across sections? 1.0 = optimal distribution.
- **prompt_variant_effectiveness**: Are the prompt approach/framing variants helping? 1.0 = clear positive signal.
- **improving**: Compare to prior reviews if available.

Focus on actionable insights. "The failure_avoidance section is wasting tokens on generic advice" is useful. "Could be better" is not.
"""


def _format_brief_section(samples):
    """Format recent brief samples for the prompt."""
    if not samples:
        return "No recent context briefs available."
    lines = []
    for i, s in enumerate(samples, 1):
        lines.append(f"### Brief {i}")
        lines.append(f"Task: {s['task']}")
        lines.append(f"Tier: {s['tier']} | Size: {s['brief_chars']} chars")
        lines.append(f"Sections present: {', '.join(s['sections_found'])}")
        lines.append(f"\n```\n{s['brief_preview']}\n```\n")
    return "\n".join(lines)


def _format_relevance_section(section_scores):
    """Format aggregated relevance scores."""
    if not section_scores:
        return "No relevance data available."
    lines = [f"{'Section':<25s} {'Mean':>6s} {'Min':>6s} {'Max':>6s} {'N':>4s}"]
    lines.append("-" * 50)
    for section, stats in sorted(section_scores.items(), key=lambda x: -x[1]["mean"]):
        lines.append(
            f"{section:<25s} {stats['mean']:>6.3f} {stats['min']:>6.3f} "
            f"{stats['max']:>6.3f} {stats['count']:>4d}"
        )
    return "\n".join(lines)


def _format_optimizer_section(stats):
    """Format prompt optimizer stats."""
    if not stats:
        return "No prompt optimizer data available."
    lines = []
    for dim, variants in stats.items():
        if not isinstance(variants, dict):
            continue
        lines.append(f"\n**{dim}**:")
        for name, data in variants.items():
            if isinstance(data, dict):
                n = data.get("n", data.get("count", 0))
                wins = data.get("wins", data.get("successes", 0))
                rate = wins / n if n > 0 else 0
                lines.append(f"  {name}: {wins}/{n} ({rate:.0%})")
    return "\n".join(lines) if lines else "No variant data."


def _format_benchmark_section(bench):
    """Format brief benchmark results."""
    if not bench:
        return "No brief benchmark results available."
    bq = bench.get("brief_quality", bench)
    lines = []
    for key in ("mean_jaccard", "mean_rouge_l", "mean_section_coverage", "tasks_tested"):
        if key in bq:
            lines.append(f"{key}: {bq[key]}")
    return "\n".join(lines) if lines else json.dumps(bq, indent=2)[:500]


def _format_history_section(history):
    """Format review history."""
    if not history:
        return "No prior context reviews."
    lines = []
    for h in history:
        lines.append(
            f"  {h.get('timestamp', '?')[:10]}: "
            f"overall={h.get('overall_score', '?')}, "
            f"completeness={h.get('information_completeness', '?')}, "
            f"noise={h.get('noise_level', '?')}, "
            f"improving={h.get('improving', '?')}"
        )
    return "\n".join(lines)


def build_review_prompt(brief_samples, section_scores, optimizer_stats,
                        bench_results, metrics, history):
    """Build the Claude Code review prompt with all context."""
    metrics_section = (
        ", ".join(f"{k}={v}" for k, v in metrics.items()) if metrics
        else "No metrics available."
    )
    return _REVIEW_PROMPT_TEMPLATE.format(
        brief_section=_format_brief_section(brief_samples),
        relevance_section=_format_relevance_section(section_scores),
        optimizer_section=_format_optimizer_section(optimizer_stats),
        benchmark_section=_format_benchmark_section(bench_results),
        metrics_section=metrics_section,
        history_section=_format_history_section(history),
    )


# ── Phase 1: Prepare ────────────────────────────────────────────────────

def prepare():
    """Phase 1: Collect data, build prompt, write to file."""
    _ensure_dirs()
    print("Collecting context assembly data for LLM review...")

    relevance_entries = _load_recent_relevance(days=7)
    section_scores = _aggregate_section_scores(relevance_entries)
    print(f"  {len(relevance_entries)} relevance episodes, {len(section_scores)} sections tracked")

    brief_samples = _load_recent_brief_samples(n=5)
    print(f"  {len(brief_samples)} recent brief sample(s)")

    optimizer_stats = _load_prompt_optimizer_stats()
    print(f"  Prompt optimizer: {'loaded' if optimizer_stats else 'no data'}")

    bench_results = _load_brief_benchmark()
    print(f"  Brief benchmark: {'loaded' if bench_results else 'no data'}")

    metrics = _load_metric_snapshot()
    history = _load_review_history()

    prompt = build_review_prompt(
        brief_samples, section_scores, optimizer_stats,
        bench_results, metrics, history,
    )

    with open(PROMPT_FILE, "w") as f:
        f.write(prompt)
    print(f"Prompt written to {PROMPT_FILE} ({len(prompt)} chars)")

    # Save cache for process phase
    cache_file = os.path.join(REVIEW_DIR, "_prepare_cache.json")
    with open(cache_file, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_relevance_episodes": len(relevance_entries),
            "n_sections_tracked": len(section_scores),
            "n_brief_samples": len(brief_samples),
            "has_optimizer": optimizer_stats is not None,
            "has_benchmark": bench_results is not None,
            "metrics": metrics,
        }, f, indent=2)

    return PROMPT_FILE


# ── Phase 2: Process ────────────────────────────────────────────────────

def process(claude_output_file):
    """Phase 2: Parse Claude's output, store results, wire to digest + queue."""
    _ensure_dirs()

    with open(claude_output_file) as f:
        raw_output = f.read()

    review = _extract_json(raw_output)
    if not review:
        print(f"ERROR: Could not extract JSON from Claude output ({len(raw_output)} chars)")
        print("First 500 chars:", raw_output[:500])
        _store_result({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "parse_error",
            "raw_output_chars": len(raw_output),
        })
        return None

    # Load prepare cache
    cache_file = os.path.join(REVIEW_DIR, "_prepare_cache.json")
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
        except Exception:
            pass

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "review": review,
        "metrics_at_review": cache.get("metrics", {}),
        "n_relevance_episodes": cache.get("n_relevance_episodes", 0),
        "n_sections_tracked": cache.get("n_sections_tracked", 0),
    }

    _store_result(result)
    _write_digest(result)
    _push_recommendations(result)
    _print_summary(result)

    return result


def _extract_json(text):
    """Extract JSON block from Claude's response."""
    match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r'\{[^{}]*"overall_score"[^{}]*\}', text, re.DOTALL)
    if match:
        start = text.find('{', match.start())
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def _store_result(result):
    """Save to latest.json and append to history."""
    with open(LATEST_FILE, "w") as f:
        json.dump(result, f, indent=2)

    review = result.get("review", {})
    history_entry = {
        "timestamp": result["timestamp"],
        "status": result["status"],
        "overall_score": review.get("overall_score"),
        "information_completeness": review.get("information_completeness"),
        "noise_level": review.get("noise_level"),
        "section_balance": review.get("section_balance"),
        "prompt_variant_effectiveness": review.get("prompt_variant_effectiveness"),
        "improving": review.get("improving"),
        "n_recommendations": len(review.get("recommendations", [])),
    }

    entries = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    entries.append(history_entry)
    entries = entries[-MAX_HISTORY:]

    with open(HISTORY_FILE, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _write_digest(result):
    """Write review summary to daily digest."""
    try:
        from clarvis._script_loader import load as _load_script
        _dw = _load_script("digest_writer", "tools")
        write_digest = _dw.write_digest

        review = result.get("review", {})
        summary = (
            f"LLM context quality review: overall={review.get('overall_score', '?')}, "
            f"completeness={review.get('information_completeness', '?')}, "
            f"noise={review.get('noise_level', '?')}, "
            f"improving={review.get('improving', '?')}. "
        )
        narrative = review.get("narrative", "")
        if narrative:
            summary += narrative[:300]

        write_digest("evolution", summary)
        print("Digest entry written.")
    except Exception as e:
        print(f"Warning: could not write digest: {e}")


def _push_recommendations(result):
    """Push high-priority recommendations to QUEUE.md."""
    try:
        from clarvis.queue.writer import add_task

        review = result.get("review", {})
        recs = review.get("recommendations", [])

        pushed = 0
        for rec in recs:
            priority = rec.get("priority", "P2")
            if priority in ("P0", "P1"):
                action = rec.get("action", "")
                rationale = rec.get("rationale", "")
                task_text = f"[LLM_CONTEXT_REVIEW] {action}"
                if rationale:
                    task_text += f" — {rationale}"
                add_task(task_text, priority=priority, source="llm_context_review")
                pushed += 1

        if pushed:
            print(f"Pushed {pushed} recommendation(s) to QUEUE.md")
        else:
            print("No high-priority recommendations to push.")
    except Exception as e:
        print(f"Warning: could not push recommendations: {e}")


def _print_summary(result):
    """Print human-readable summary."""
    review = result.get("review", {})
    print("\n=== LLM Context Quality Review ===")
    print(f"Timestamp: {result['timestamp']}")
    print(f"Status:    {result['status']}")
    print()

    if result["status"] != "success":
        print("Review failed — see latest.json for details.")
        return

    print(f"Overall Score:         {review.get('overall_score', '?')}")
    print(f"Completeness:          {review.get('information_completeness', '?')}")
    print(f"Noise Level:           {review.get('noise_level', '?')}")
    print(f"Section Balance:       {review.get('section_balance', '?')}")
    print(f"Variant Effectiveness: {review.get('prompt_variant_effectiveness', '?')}")
    print(f"Improving:             {review.get('improving', '?')}")
    print()

    # Per-section analysis
    sections = review.get("sections_analysis", [])
    if sections:
        print("Section Analysis:")
        for s in sections:
            verdict = s.get("verdict", "?")
            marker = {"essential": "+", "useful": "~", "marginal": "-", "noise": "!!"}.get(verdict, "?")
            print(f"  [{marker}] {s.get('section', '?'):<25s} {verdict:<10s} score={s.get('score', '?')}")
        print()

    for label, key in [("Strengths", "strengths"), ("Weaknesses", "weaknesses")]:
        items = review.get(key, [])
        if items:
            print(f"{label}:")
            for item in items:
                print(f"  - {item}")
            print()

    recs = review.get("recommendations", [])
    if recs:
        print("Recommendations:")
        for rec in recs:
            print(f"  [{rec.get('priority', '?')}] {rec.get('action', '?')}")
        print()

    narrative = review.get("narrative", "")
    if narrative:
        print(f"Narrative: {narrative}")
        print()


def print_report():
    """Print latest review."""
    if not os.path.exists(LATEST_FILE):
        print("No LLM context review found. Run: cron_llm_context_review.sh")
        return
    with open(LATEST_FILE) as f:
        result = json.load(f)
    _print_summary(result)


def print_history():
    """Print review history summary."""
    if not os.path.exists(HISTORY_FILE):
        print("No review history.")
        return

    entries = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not entries:
        print("No review history entries.")
        return

    print("=== LLM Context Review History ===")
    print(f"{'Date':12s} {'Overall':>8s} {'Complete':>9s} {'Noise':>6s} {'Balance':>8s} {'Improving':>10s}")
    print("-" * 58)
    for e in entries:
        ts = e.get("timestamp", "?")[:10]
        print(
            f"{ts:12s} "
            f"{e.get('overall_score', '?'):>8} "
            f"{e.get('information_completeness', '?'):>9} "
            f"{e.get('noise_level', '?'):>6} "
            f"{e.get('section_balance', '?'):>8} "
            f"{e.get('improving', '?'):>10s}"
        )

    scores = [e["overall_score"] for e in entries if e.get("overall_score") is not None]
    if len(scores) >= 2:
        delta = scores[-1] - scores[0]
        direction = "up" if delta > 0.02 else "down" if delta < -0.02 else "stable"
        print(f"\nTrend: {direction} (delta={delta:+.3f} over {len(scores)} reviews)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"

    if cmd == "prepare":
        prepare()
    elif cmd == "process":
        if len(sys.argv) < 3:
            print("Usage: llm_context_review.py process <claude_output_file>")
            sys.exit(1)
        process(sys.argv[2])
    elif cmd == "report":
        print_report()
    elif cmd == "history":
        print_history()
    else:
        print("Usage: llm_context_review.py [prepare|process <file>|report|history]")
        sys.exit(1)
