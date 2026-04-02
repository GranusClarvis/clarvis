#!/usr/bin/env python3
"""Benchmark: Context Window Utilization Efficiency

Measures how efficiently the heartbeat context brief uses tokens by analyzing:
  (a) Total tokens generated per brief section
  (b) Tokens actually relevant to the selected task (via containment scores)
  (c) Wasted tokens (irrelevant/noise sections)

Data source: data/retrieval_quality/context_relevance.jsonl — per-section
relevance scores recorded by heartbeat_postflight.py after each execution.

The benchmark reconstructs token estimates from section containment scores
and the known brief structure, then computes utilization efficiency.

Usage:
    python3 bench_context_utilization.py              # Last 10 heartbeats
    python3 bench_context_utilization.py --n 20       # Last 20 heartbeats
    python3 bench_context_utilization.py --live        # Generate fresh brief + analyze
    python3 bench_context_utilization.py --json        # Machine-readable output
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
RELEVANCE_FILE = os.path.join(WORKSPACE, "data", "retrieval_quality", "context_relevance.jsonl")
RESULTS_FILE = os.path.join(WORKSPACE, "data", "bench_context_utilization.json")

# Reference threshold: sections scoring below this are considered "not referenced"
REFERENCE_THRESHOLD = 0.12
BRIEF_TOKEN_STATS_FILE = os.path.join(WORKSPACE, "data", "brief_token_stats.jsonl")

# Approximate token-per-word ratio for LLM tokenizers
TOKENS_PER_WORD = 1.3


def _estimate_section_tokens(section_name):
    """Estimate typical token count for a section based on empirical brief sizes.

    These are calibrated from actual tiered brief outputs (standard/full tiers).
    The brief assembly budget caps each section, so sizes are fairly stable.
    """
    # Empirical median token counts per section (measured from 20 briefs)
    section_token_estimates = {
        "decision_context": 120,
        "knowledge":        180,
        "working_memory":   100,
        "related_tasks":     80,
        "metrics":           30,
        "completions":       50,
        "episodes":         100,
        "reasoning":         60,
        "brain_goals":       80,
        "brain_context":     40,
        "world_model":       25,
        "failure_avoidance": 90,
        "synaptic":          60,
        "attention":         50,
        "gwt_broadcast":    100,
        "introspection":    150,
        "confidence_gate":   40,
        "meta_gradient":     20,
        "procedures":       120,
    }
    return section_token_estimates.get(section_name, 60)


def _load_relevance_entries(n=10, relevance_file=RELEVANCE_FILE):
    """Load the last N context_relevance entries from JSONL."""
    if not os.path.exists(relevance_file):
        return []
    entries = []
    with open(relevance_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-n:]


def _load_ground_truth_stats():
    """Load ground-truth brief token stats indexed by timestamp (±60s match).

    Returns dict mapping truncated timestamp → {section_name: tokens}.
    """
    if not os.path.exists(BRIEF_TOKEN_STATS_FILE):
        return {}
    index = {}
    with open(BRIEF_TOKEN_STATS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("ts", "")[:16]  # match by minute
                sections = entry.get("sections", {})
                index[ts] = {name: info["tokens"] for name, info in sections.items()}
            except (json.JSONDecodeError, KeyError):
                continue
    return index


def analyze_entry(entry, ground_truth=None):
    """Analyze a single context_relevance entry for token utilization.

    Returns dict with:
        total_tokens: estimated total tokens in the brief
        relevant_tokens: tokens in sections that were actually referenced
        wasted_tokens: tokens in unreferenced sections
        utilization: relevant_tokens / total_tokens
        per_section: list of {name, tokens, score, referenced}
    """
    per_section = entry.get("per_section", {})
    if not per_section:
        return None

    # Try ground-truth token counts first (from brief_token_stats.jsonl)
    gt_tokens = None
    if ground_truth:
        entry_ts = entry.get("ts", "")[:16]
        gt_tokens = ground_truth.get(entry_ts)

    total_tokens = 0
    relevant_tokens = 0
    wasted_tokens = 0
    section_details = []
    token_source = "ground_truth" if gt_tokens else "estimate"

    for name, score in per_section.items():
        tokens = gt_tokens.get(name, _estimate_section_tokens(name)) if gt_tokens else _estimate_section_tokens(name)
        referenced = score >= REFERENCE_THRESHOLD
        total_tokens += tokens

        # Weight tokens by containment score for proportional accounting
        effective_tokens = int(tokens * min(score / REFERENCE_THRESHOLD, 1.0)) if REFERENCE_THRESHOLD > 0 else tokens
        if referenced:
            relevant_tokens += effective_tokens
            wasted_tokens += (tokens - effective_tokens)
        else:
            wasted_tokens += tokens

        section_details.append({
            "name": name,
            "tokens": tokens,
            "score": round(score, 4),
            "referenced": referenced,
            "effective_tokens": effective_tokens,
        })

    # Sort by score descending
    section_details.sort(key=lambda x: x["score"], reverse=True)

    utilization = relevant_tokens / total_tokens if total_tokens > 0 else 0.0

    return {
        "ts": entry.get("ts", ""),
        "task": entry.get("task", "")[:80],
        "outcome": entry.get("outcome", ""),
        "total_tokens": total_tokens,
        "relevant_tokens": relevant_tokens,
        "wasted_tokens": wasted_tokens,
        "utilization": round(utilization, 4),
        "noise_ratio": entry.get("noise_ratio", round(1.0 - entry.get("overall", 0), 4)),
        "sections_total": entry.get("sections_total", 0),
        "sections_referenced": entry.get("sections_referenced", 0),
        "per_section": section_details,
    }


def analyze_live_brief():
    """Generate a fresh brief and analyze its actual token distribution.

    Returns dict with actual token counts per section (not estimates).
    """
    try:
        from context_compressor import generate_tiered_brief
        from clarvis.cognition.context_relevance import parse_brief_sections
    except ImportError as e:
        return {"error": f"Import failed: {e}"}

    # Generate a brief for a sample task
    sample_task = "[BENCHMARK] Context utilization benchmark — measuring token distribution"
    brief = generate_tiered_brief(current_task=sample_task, tier="full")

    sections = parse_brief_sections(brief)
    total_tokens = 0
    section_details = []

    for name, content in sections.items():
        # Count actual tokens (words * ratio)
        word_count = len(content.split())
        tokens = int(word_count * TOKENS_PER_WORD)
        total_tokens += tokens
        section_details.append({
            "name": name,
            "tokens": tokens,
            "word_count": word_count,
            "char_count": len(content),
        })

    section_details.sort(key=lambda x: x["tokens"], reverse=True)

    return {
        "total_tokens": total_tokens,
        "total_chars": len(brief),
        "sections": len(sections),
        "per_section": section_details,
        "brief_preview": brief[:500],
    }


def run_benchmark(n=10, relevance_file=RELEVANCE_FILE):
    """Run the full benchmark across the last N heartbeats.

    Returns a comprehensive results dict.
    """
    entries = _load_relevance_entries(n=n, relevance_file=relevance_file)
    if not entries:
        return {"error": "No context_relevance data found", "entries": 0}

    ground_truth = _load_ground_truth_stats()

    analyses = []
    for entry in entries:
        result = analyze_entry(entry, ground_truth=ground_truth)
        if result:
            analyses.append(result)

    if not analyses:
        return {"error": "No analyzable entries", "entries": len(entries)}

    # Aggregate stats
    total_tokens_sum = sum(a["total_tokens"] for a in analyses)
    relevant_tokens_sum = sum(a["relevant_tokens"] for a in analyses)
    wasted_tokens_sum = sum(a["wasted_tokens"] for a in analyses)

    utilizations = [a["utilization"] for a in analyses]
    noise_ratios = [a["noise_ratio"] for a in analyses]

    # Per-section aggregation: which sections waste the most tokens?
    section_waste = {}
    section_counts = {}
    for a in analyses:
        for s in a["per_section"]:
            name = s["name"]
            if name not in section_waste:
                section_waste[name] = {"total_tokens": 0, "effective_tokens": 0,
                                       "wasted": 0, "times_referenced": 0, "times_present": 0}
            section_waste[name]["total_tokens"] += s["tokens"]
            section_waste[name]["effective_tokens"] += s["effective_tokens"]
            section_waste[name]["wasted"] += s["tokens"] - s["effective_tokens"]
            section_waste[name]["times_present"] += 1
            if s["referenced"]:
                section_waste[name]["times_referenced"] += 1

    # Rank sections by waste
    waste_ranking = []
    for name, data in section_waste.items():
        ref_rate = data["times_referenced"] / max(data["times_present"], 1)
        waste_ranking.append({
            "section": name,
            "total_tokens": data["total_tokens"],
            "wasted_tokens": data["wasted"],
            "reference_rate": round(ref_rate, 2),
            "utilization": round(data["effective_tokens"] / max(data["total_tokens"], 1), 4),
        })
    waste_ranking.sort(key=lambda x: x["wasted_tokens"], reverse=True)

    results = {
        "benchmark": "context_window_utilization",
        "ts": datetime.now(timezone.utc).isoformat(),
        "heartbeats_analyzed": len(analyses),
        "date_range": {
            "first": analyses[0]["ts"][:10] if analyses else "",
            "last": analyses[-1]["ts"][:10] if analyses else "",
        },
        "summary": {
            "total_tokens_across_heartbeats": total_tokens_sum,
            "relevant_tokens": relevant_tokens_sum,
            "wasted_tokens": wasted_tokens_sum,
            "mean_utilization": round(sum(utilizations) / len(utilizations), 4),
            "min_utilization": round(min(utilizations), 4),
            "max_utilization": round(max(utilizations), 4),
            "mean_noise_ratio": round(sum(noise_ratios) / len(noise_ratios), 4),
            "mean_tokens_per_brief": round(total_tokens_sum / len(analyses)),
            "mean_wasted_per_brief": round(wasted_tokens_sum / len(analyses)),
        },
        "section_waste_ranking": waste_ranking,
        "per_heartbeat": [{
            "ts": a["ts"][:19],
            "task": a["task"],
            "outcome": a["outcome"],
            "total_tokens": a["total_tokens"],
            "relevant_tokens": a["relevant_tokens"],
            "wasted_tokens": a["wasted_tokens"],
            "utilization": a["utilization"],
            "sections": f"{a['sections_referenced']}/{a['sections_total']}",
        } for a in analyses],
    }

    return results


def print_report(results):
    """Print a human-readable report."""
    if "error" in results:
        print(f"ERROR: {results['error']}")
        return

    s = results["summary"]
    print("=" * 70)
    print("CONTEXT WINDOW UTILIZATION BENCHMARK")
    print(f"  Heartbeats analyzed: {results['heartbeats_analyzed']}")
    print(f"  Date range: {results['date_range']['first']} → {results['date_range']['last']}")
    print("=" * 70)

    print(f"\n{'METRIC':<35} {'VALUE':>10}")
    print("-" * 50)
    print(f"{'Mean utilization':<35} {s['mean_utilization']:.1%}")
    print(f"{'Min utilization':<35} {s['min_utilization']:.1%}")
    print(f"{'Max utilization':<35} {s['max_utilization']:.1%}")
    print(f"{'Mean noise ratio':<35} {s['mean_noise_ratio']:.1%}")
    print(f"{'Mean tokens per brief':<35} {s['mean_tokens_per_brief']:>10}")
    print(f"{'Mean wasted tokens per brief':<35} {s['mean_wasted_per_brief']:>10}")
    print(f"{'Total tokens (all heartbeats)':<35} {s['total_tokens_across_heartbeats']:>10}")
    print(f"{'Total wasted tokens':<35} {s['wasted_tokens']:>10}")

    print(f"\n{'SECTION WASTE RANKING'}")
    print(f"{'Section':<25} {'Wasted':>8} {'Ref Rate':>10} {'Util':>8}")
    print("-" * 55)
    for sw in results["section_waste_ranking"]:
        print(f"  {sw['section']:<23} {sw['wasted_tokens']:>6} {sw['reference_rate']:>9.0%} {sw['utilization']:>7.1%}")

    print(f"\n{'PER-HEARTBEAT BREAKDOWN'}")
    print(f"{'Timestamp':<20} {'Tokens':>7} {'Relevant':>9} {'Wasted':>7} {'Util':>6} {'Secs':>5} {'Outcome':>8}")
    print("-" * 70)
    for hb in results["per_heartbeat"]:
        print(f"  {hb['ts']:<18} {hb['total_tokens']:>5} {hb['relevant_tokens']:>9} "
              f"{hb['wasted_tokens']:>7} {hb['utilization']:>5.1%} {hb['sections']:>5} {hb['outcome']:>8}")

    # Actionable insights
    print(f"\n{'ACTIONABLE INSIGHTS'}")
    print("-" * 50)
    # Find consistently wasted sections
    never_ref = [sw for sw in results["section_waste_ranking"] if sw["reference_rate"] < 0.3]
    if never_ref:
        print("  Sections rarely referenced (candidates for suppression):")
        for sw in never_ref[:5]:
            print(f"    - {sw['section']}: {sw['reference_rate']:.0%} ref rate, "
                  f"{sw['wasted_tokens']} tokens wasted across {results['heartbeats_analyzed']} heartbeats")

    high_util = [sw for sw in results["section_waste_ranking"] if sw["reference_rate"] >= 0.9]
    if high_util:
        print("  Sections always referenced (high value):")
        for sw in high_util[:5]:
            print(f"    - {sw['section']}: {sw['reference_rate']:.0%} ref rate, {sw['utilization']:.1%} utilization")


def save_results(results):
    """Save benchmark results to disk."""
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {RESULTS_FILE}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Context window utilization benchmark")
    parser.add_argument("--n", type=int, default=10, help="Number of heartbeats to analyze")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of report")
    parser.add_argument("--live", action="store_true", help="Also analyze a freshly generated brief")
    parser.add_argument("--save", action="store_true", help="Save results to disk")
    args = parser.parse_args()

    results = run_benchmark(n=args.n)

    if args.live:
        live = analyze_live_brief()
        results["live_brief_analysis"] = live

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)
        if args.live and "live_brief_analysis" in results:
            live = results["live_brief_analysis"]
            if "error" not in live:
                print(f"\nLIVE BRIEF ANALYSIS:")
                print(f"  Total tokens: {live['total_tokens']}, Sections: {live['sections']}")
                for s in live["per_section"]:
                    print(f"    {s['name']:<25} {s['tokens']:>5} tokens ({s['word_count']} words)")

    if args.save or not args.json:
        save_results(results)


if __name__ == "__main__":
    main()
