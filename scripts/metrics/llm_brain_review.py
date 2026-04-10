#!/usr/bin/env python3
"""
llm_brain_review.py — LLM-judged brain quality review.

Adds the missing LLM judgement layer on top of the deterministic daily_brain_eval.
Runs retrieval probes, samples actual query→result pairs, and asks Claude Code
to assess quality, usefulness, and improvement trajectory.

Design principle (inherited from daily_brain_eval):
  QUALITY OVER SPEED. A 2s query returning the right memory beats a 200ms query
  returning noise. This script explicitly encodes that: do NOT recommend speed
  optimizations that sacrifice retrieval quality.

Two-phase architecture:
  Phase 1 (prepare): Pure Python — runs probes, reads history, builds prompt.
    Output: prompt file for Claude Code.
  Phase 2 (process): Pure Python — parses Claude's response, stores structured
    results, writes digest entry, pushes queue recommendations.

The cron wrapper (cron_llm_brain_review.sh) orchestrates:
  prepare → Claude Code → process

Usage:
    python3 scripts/llm_brain_review.py prepare           # → /tmp/brain_review_prompt.txt
    python3 scripts/llm_brain_review.py process <file>    # Parse Claude output → store + wire
    python3 scripts/llm_brain_review.py report             # Print latest review
    python3 scripts/llm_brain_review.py history             # Print review history summary

Output:
    data/llm_brain_review/latest.json     — structured review result
    data/llm_brain_review/history.jsonl   — rolling history (max 90)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))

REVIEW_DIR = os.path.join(WORKSPACE, "data/llm_brain_review")
LATEST_FILE = os.path.join(REVIEW_DIR, "latest.json")
HISTORY_FILE = os.path.join(REVIEW_DIR, "history.jsonl")
PROMPT_FILE = "/tmp/brain_review_prompt.txt"
MAX_HISTORY = 90

# ── Diverse probe queries for LLM review ─────────────────────────────
# These test different retrieval aspects: factual recall, procedural,
# cross-domain, temporal, and abstract reasoning queries.
REVIEW_PROBES = [
    # Factual recall
    {"q": "What is the dual-layer architecture of Clarvis?",
     "intent": "Should explain conscious (M2.5) + subconscious (Claude Code) layers",
     "domain": "identity"},
    # Procedural
    {"q": "How do I add a new cron job to the schedule safely?",
     "intent": "Should reference crontab, cron_env.sh, lock_helper.sh, testing procedure",
     "domain": "procedures"},
    # Infrastructure
    {"q": "What graph backends does ClarvisDB support and which is active?",
     "intent": "Should mention JSON legacy + SQLite+WAL, dual-write soak, CLARVIS_GRAPH_BACKEND",
     "domain": "infrastructure"},
    # Goals / strategic
    {"q": "What are the current priorities for cognitive improvement?",
     "intent": "Should surface active goals, queue tasks, or roadmap items",
     "domain": "goals"},
    # Cross-domain
    {"q": "How does the heartbeat pipeline use the brain for task selection?",
     "intent": "Should connect heartbeat_preflight → attention.py → brain.recall → task routing",
     "domain": "cross-domain"},
    # Temporal / recent
    {"q": "What did Clarvis accomplish in the last 24 hours?",
     "intent": "Should surface recent episodes, digest entries, or autonomous results",
     "domain": "temporal"},
    # Abstract / meta
    {"q": "Is the brain actually helping Clarvis make better decisions?",
     "intent": "Should reference CLR value-add, episode success rates, or reasoning chain outcomes",
     "domain": "meta"},
    # Edge case: vague query
    {"q": "memory stuff",
     "intent": "Vague query — should still return relevant memory subsystem info, not random noise",
     "domain": "robustness"},
]


def _ensure_dirs():
    os.makedirs(REVIEW_DIR, exist_ok=True)


def _run_probes():
    """Run retrieval probes and collect actual results for LLM review."""
    from clarvis.brain import brain

    probe_results = []
    for item in REVIEW_PROBES:
        t0 = time.time()
        try:
            hits = brain.recall(item["q"], n=5)
            elapsed_ms = round((time.time() - t0) * 1000)

            # Extract actual result texts
            result_texts = []
            for h in hits[:3]:
                if isinstance(h, dict):
                    doc = h.get("document", h.get("text", str(h)))
                    collection = h.get("collection", "unknown")
                    distance = h.get("distance", None)
                else:
                    doc = str(h)
                    collection = "unknown"
                    distance = None
                result_texts.append({
                    "text": doc[:500],
                    "collection": collection,
                    "distance": round(distance, 3) if distance is not None else None,
                })

            probe_results.append({
                "query": item["q"],
                "intent": item["intent"],
                "domain": item["domain"],
                "speed_ms": elapsed_ms,
                "n_results": len(hits),
                "top_results": result_texts,
            })
        except Exception as e:
            probe_results.append({
                "query": item["q"],
                "intent": item["intent"],
                "domain": item["domain"],
                "speed_ms": 0,
                "n_results": 0,
                "top_results": [],
                "error": str(e),
            })

    return probe_results


def _load_deterministic_eval():
    """Load latest deterministic eval results if available."""
    eval_file = os.path.join(WORKSPACE, "data/daily_brain_eval/latest.json")
    if os.path.exists(eval_file):
        try:
            with open(eval_file) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _load_review_history():
    """Load recent LLM review history for trend analysis."""
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


def _load_metric_snapshot():
    """Load current CLR/PI/Phi for context."""
    snapshot = {}

    clr_file = os.path.join(WORKSPACE, "data/clr_benchmark.json")
    if os.path.exists(clr_file):
        try:
            with open(clr_file) as f:
                clr = json.load(f)
            snapshot["clr"] = clr.get("clr")
            snapshot["clr_value_add"] = clr.get("value_add")
            snapshot["clr_gate"] = clr.get("gate", {}).get("pass")
        except Exception:
            pass

    pi_file = os.path.join(WORKSPACE, "data/performance_metrics.json")
    if os.path.exists(pi_file):
        try:
            with open(pi_file) as f:
                pi = json.load(f)
            snapshot["pi"] = pi.get("pi", pi.get("score"))
        except Exception:
            pass

    return snapshot


def _format_probe_section(probe_results):
    """Format probe results into prompt section lines."""
    lines = []
    for i, p in enumerate(probe_results, 1):
        lines.append(f"### Probe {i}: {p['query']}")
        lines.append(f"Intent: {p['intent']}")
        lines.append(f"Domain: {p['domain']}")
        lines.append(f"Speed: {p['speed_ms']}ms | Results: {p['n_results']}")
        if p.get("error"):
            lines.append(f"ERROR: {p['error']}")
        for j, r in enumerate(p.get("top_results", []), 1):
            dist_str = f" (dist={r['distance']})" if r.get("distance") is not None else ""
            lines.append(f"  Result {j} [{r['collection']}{dist_str}]:")
            lines.append(f"    {r['text'][:300]}")
        lines.append("")
    return "\n".join(lines)


def _format_det_eval_section(det_eval):
    """Format deterministic evaluation summary."""
    if not det_eval:
        return "No deterministic evaluation available."
    assessment = det_eval.get("assessment", {})
    retrieval = det_eval.get("retrieval", {})
    return (
        f"Quality Score: {assessment.get('quality_score', '?')}\n"
        f"Useful Rate: {retrieval.get('useful_rate', '?')}\n"
        f"Avg Speed: {retrieval.get('avg_speed_ms', '?')}ms\n"
        f"Failures: {retrieval.get('failures', [])}\n"
        f"Recommendations: {assessment.get('recommendations', [])}"
    )


def _format_history_section(history):
    """Format review history for prompt."""
    if not history:
        return "No prior LLM reviews."
    lines = []
    for h in history:
        lines.append(
            f"  {h.get('timestamp', '?')[:10]}: "
            f"overall={h.get('overall_score', '?')}, "
            f"retrieval_quality={h.get('retrieval_quality', '?')}, "
            f"usefulness={h.get('usefulness', '?')}, "
            f"improving={h.get('improving', '?')}"
        )
    return "\n".join(lines)


# Prompt template — kept as a constant to separate structure from data
_REVIEW_PROMPT_TEMPLATE = """You are reviewing the brain (memory retrieval system) quality of Clarvis, a cognitive AI agent.

## Your Task

Evaluate the brain's retrieval quality based on the probe results below. For each probe, judge whether the returned results are actually useful for answering the query — not just keyword-matching, but genuinely helpful context that would improve task execution.

## Critical Principle: QUALITY OVER SPEED

A 2-second query returning the right memory is worth more than a 200ms query returning noise. Do NOT recommend speed optimizations that would sacrifice retrieval quality. Only flag speed as a concern if queries exceed 10 seconds.

## Probe Results

{probe_section}

## Deterministic Evaluation (keyword-based)

{det_section}

## Current Metrics

{metrics_section}

## Prior LLM Review History (last 7 days)

{history_section}

## Required Output Format

You MUST respond with a JSON block (```json ... ```) containing exactly these fields:

```json
{{
  "overall_score": <float 0.0-1.0>,
  "retrieval_quality": <float 0.0-1.0>,
  "usefulness": <float 0.0-1.0>,
  "context_coherence": <float 0.0-1.0>,
  "improving": <"yes"|"no"|"unclear">,
  "quality_over_speed_adherence": <float 0.0-1.0>,
  "probe_judgements": [
    {{
      "query": "<query text>",
      "useful": <true|false>,
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

- **overall_score**: Holistic quality. 0.9+ = excellent, 0.7-0.9 = good, 0.5-0.7 = needs work, <0.5 = concerning.
- **retrieval_quality**: Are the right memories being surfaced? Is the ranking sensible?
- **usefulness**: Would these results actually help an agent complete the task implied by each query?
- **context_coherence**: Do the results form a coherent context, or are they disconnected fragments?
- **quality_over_speed_adherence**: Is the system correctly prioritizing quality? 1.0 = yes, no speed-chasing.
- **improving**: Compare to prior reviews if available. "unclear" if no history or too few data points.

Be honest and specific. Vague praise is not helpful. Point out concrete weaknesses with actionable fixes.
"""


def build_review_prompt(probe_results, det_eval, history, metrics):
    """Build the Claude Code review prompt with all context."""
    metrics_section = ", ".join(f"{k}={v}" for k, v in metrics.items()) if metrics else "No metrics available."

    return _REVIEW_PROMPT_TEMPLATE.format(
        probe_section=_format_probe_section(probe_results),
        det_section=_format_det_eval_section(det_eval),
        metrics_section=metrics_section,
        history_section=_format_history_section(history),
    )


def prepare():
    """Phase 1: Run probes, build prompt, write to file."""
    _ensure_dirs()
    print("Running retrieval probes for LLM review...")
    probe_results = _run_probes()
    print(f"  {len(probe_results)} probes complete")

    det_eval = _load_deterministic_eval()
    history = _load_review_history()
    metrics = _load_metric_snapshot()

    prompt = build_review_prompt(probe_results, det_eval, history, metrics)

    with open(PROMPT_FILE, "w") as f:
        f.write(prompt)
    print(f"Prompt written to {PROMPT_FILE} ({len(prompt)} chars)")

    # Also save probe data for the process phase
    probe_cache = os.path.join(REVIEW_DIR, "_probe_cache.json")
    with open(probe_cache, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "probes": probe_results,
            "det_eval_score": det_eval.get("assessment", {}).get("quality_score") if det_eval else None,
            "metrics": metrics,
        }, f, indent=2)

    return PROMPT_FILE


def process(claude_output_file):
    """Phase 2: Parse Claude's output, store results, wire to digest + queue."""
    _ensure_dirs()

    # Read Claude's output
    with open(claude_output_file) as f:
        raw_output = f.read()

    # Extract JSON block
    review = _extract_json(raw_output)
    if not review:
        print(f"ERROR: Could not extract JSON from Claude output ({len(raw_output)} chars)")
        print("First 500 chars:", raw_output[:500])
        # Store failure
        _store_result({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "parse_error",
            "raw_output_chars": len(raw_output),
        })
        return None

    # Load probe cache for enrichment
    probe_cache_file = os.path.join(REVIEW_DIR, "_probe_cache.json")
    probe_cache = {}
    if os.path.exists(probe_cache_file):
        try:
            with open(probe_cache_file) as f:
                probe_cache = json.load(f)
        except Exception:
            pass

    # Build full result
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "review": review,
        "det_eval_score": probe_cache.get("det_eval_score"),
        "metrics_at_review": probe_cache.get("metrics", {}),
        "probe_count": len(probe_cache.get("probes", [])),
    }

    # Store
    _store_result(result)

    # Wire: digest entry
    _write_digest(result)

    # Wire: queue recommendations
    _push_recommendations(result)

    # Print summary
    _print_summary(result)

    return result


def _extract_json(text):
    """Extract JSON block from Claude's response."""
    # Try ```json ... ``` first
    match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try bare JSON object
    match = re.search(r'\{[^{}]*"overall_score"[^{}]*\}', text, re.DOTALL)
    if match:
        # Find the full JSON object by tracking braces
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

    # History entry (compact)
    review = result.get("review", {})
    history_entry = {
        "timestamp": result["timestamp"],
        "status": result["status"],
        "overall_score": review.get("overall_score"),
        "retrieval_quality": review.get("retrieval_quality"),
        "usefulness": review.get("usefulness"),
        "context_coherence": review.get("context_coherence"),
        "improving": review.get("improving"),
        "n_recommendations": len(review.get("recommendations", [])),
        "det_eval_score": result.get("det_eval_score"),
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
        from digest_writer import write_digest

        review = result.get("review", {})
        summary = (
            f"LLM brain quality review: overall={review.get('overall_score', '?')}, "
            f"retrieval={review.get('retrieval_quality', '?')}, "
            f"usefulness={review.get('usefulness', '?')}, "
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
                task_text = f"[LLM_BRAIN_REVIEW] {action}"
                if rationale:
                    task_text += f" — {rationale}"
                add_task(task_text, priority=priority, source="llm_brain_review")
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
    print("\n=== LLM Brain Quality Review ===")
    print(f"Timestamp: {result['timestamp']}")
    print(f"Status:    {result['status']}")
    print()

    if result["status"] != "success":
        print("Review failed — see latest.json for details.")
        return

    print(f"Overall Score:     {review.get('overall_score', '?')}")
    print(f"Retrieval Quality: {review.get('retrieval_quality', '?')}")
    print(f"Usefulness:        {review.get('usefulness', '?')}")
    print(f"Context Coherence: {review.get('context_coherence', '?')}")
    print(f"Quality>Speed:     {review.get('quality_over_speed_adherence', '?')}")
    print(f"Improving:         {review.get('improving', '?')}")
    print()

    # Per-probe summary
    judgements = review.get("probe_judgements", [])
    if judgements:
        print("Probe Judgements:")
        for j in judgements:
            status = "OK" if j.get("useful") else "MISS"
            print(f"  [{status}] {j.get('query', '?')[:50]:50s} score={j.get('score', '?')}")
        print()

    # Strengths / weaknesses
    for label, key in [("Strengths", "strengths"), ("Weaknesses", "weaknesses")]:
        items = review.get(key, [])
        if items:
            print(f"{label}:")
            for item in items:
                print(f"  - {item}")
            print()

    # Recommendations
    recs = review.get("recommendations", [])
    if recs:
        print("Recommendations:")
        for rec in recs:
            print(f"  [{rec.get('priority', '?')}] {rec.get('action', '?')}")
        print()

    # Narrative
    narrative = review.get("narrative", "")
    if narrative:
        print(f"Narrative: {narrative}")
        print()


def print_report():
    """Print latest review."""
    if not os.path.exists(LATEST_FILE):
        print("No LLM brain review found. Run the cron job or: cron_llm_brain_review.sh")
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

    print("=== LLM Brain Review History ===")
    print(f"{'Date':12s} {'Overall':>8s} {'Retrieval':>10s} {'Useful':>8s} {'Improving':>10s}")
    print("-" * 52)
    for e in entries:
        ts = e.get("timestamp", "?")[:10]
        overall = e.get("overall_score")
        retrieval = e.get("retrieval_quality")
        useful = e.get("usefulness")
        improving = e.get("improving", "?")
        print(
            f"{ts:12s} "
            f"{overall if overall is not None else '?':>8} "
            f"{retrieval if retrieval is not None else '?':>10} "
            f"{useful if useful is not None else '?':>8} "
            f"{improving:>10s}"
        )

    # Trend
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
            print("Usage: llm_brain_review.py process <claude_output_file>")
            sys.exit(1)
        process(sys.argv[2])
    elif cmd == "report":
        print_report()
    elif cmd == "history":
        print_history()
    else:
        print("Usage: llm_brain_review.py [prepare|process <file>|report|history]")
        sys.exit(1)
