"""
CLR (Clarvis Rating) — Composite Agent Intelligence Score.

CLR measures the value that Clarvis's cognitive architecture adds on top of
a bare Claude Code agent. It combines 6 dimensions into a single 0-1 score:

  1. Memory Quality      (w=0.20) — recall accuracy, retrieval precision, hit rate
  2. Retrieval Precision (w=0.20) — context relevance, noise ratio, eval verdict
  3. Prompt/Context      (w=0.15) — brief quality, compression ratio, relevance
  4. Task Success        (w=0.20) — episode success rate, quality score, reasoning depth
  5. Autonomy            (w=0.15) — unattended success, cost efficiency
  6. Efficiency          (w=0.10) — query speed, token economy, brain bloat

Baseline (no brain, no memory) is estimated at ~0.215 CLR.
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE = "/home/agent/.openclaw/workspace"
CLR_FILE = os.path.join(WORKSPACE, "data/clr_benchmark.json")
CLR_HISTORY = os.path.join(WORKSPACE, "data/clr_history.jsonl")
MAX_HISTORY = 400

# Dimension weights — must sum to 1.0
WEIGHTS = {
    "memory_quality": 0.20,
    "retrieval_precision": 0.20,
    "prompt_context": 0.15,
    "task_success": 0.20,
    "autonomy": 0.15,
    "efficiency": 0.10,
}

# Estimated baseline scores (bare Claude Code, no Clarvis brain)
BASELINE = {
    "memory_quality": 0.0,       # No persistent memory
    "retrieval_precision": 0.0,  # No retrieval
    "prompt_context": 0.30,      # Basic context from files only
    "task_success": 0.50,        # Claude is still good at tasks
    "autonomy": 0.20,            # No autonomous loop
    "efficiency": 0.40,          # No optimization, but no overhead either
}


def _score_memory_quality():
    """Dimension 1: Memory Quality — how good is the brain at storing/recalling?"""
    evidence = []
    scores = []

    try:
        from clarvis.brain import brain
        stats = brain.stats()

        # Sub-metric: brain is populated
        total_memories = stats.get("total_memories", 0)
        mem_score = min(1.0, total_memories / 3000)  # 3000+ = full score
        scores.append(mem_score)
        evidence.append(f"memories={total_memories}")

        # Sub-metric: graph density
        edges = stats.get("graph_edges", stats.get("total_edges", 0))
        density = edges / max(total_memories, 1)
        density_score = min(1.0, density / 40)  # 40 edges/mem = full
        scores.append(density_score)
        evidence.append(f"graph_density={density:.1f}")

        # Sub-metric: recall test (quick known-answer)
        test_queries = [
            ("What is Clarvis?", ["cognitive", "agent", "dual"]),
            ("How does the heartbeat work?", ["heartbeat", "preflight", "postflight"]),
            ("What is ClarvisDB?", ["chromadb", "vector", "memory"]),
        ]
        hits = 0
        for query, keywords in test_queries:
            try:
                results = brain.recall(query, n=3)
                text = " ".join(r.get("document", "") for r in results).lower()
                if any(kw in text for kw in keywords):
                    hits += 1
            except Exception:
                pass
        recall_score = hits / len(test_queries)
        scores.append(recall_score)
        evidence.append(f"recall_hit={hits}/{len(test_queries)}")

    except Exception as e:
        evidence.append(f"error: {e}")
        return 0.0, evidence

    score = sum(scores) / len(scores) if scores else 0.0
    return round(score, 3), evidence


def _score_retrieval_precision():
    """Dimension 2: Retrieval Precision — context relevance and noise filtering."""
    evidence = []
    scores = []

    try:
        from clarvis.brain import brain
        from clarvis.brain.retrieval_eval import evaluate_retrieval

        test_cases = [
            ("current evolution goals", "clarvis-goals"),
            ("infrastructure details", "clarvis-infrastructure"),
            ("recent learnings", "clarvis-learnings"),
        ]

        for query, collection in test_cases:
            try:
                results = brain.recall(query, n=5, collections=[collection])
                if results:
                    eval_result = evaluate_retrieval(results, query)
                    n_above = eval_result.get("n_above_threshold", 0)
                    n_total = eval_result.get("n_results", 0)
                    max_score = eval_result.get("max_score", 0.0)
                    precision = n_above / max(n_total, 1)
                    scores.append(precision)
                    verdict = eval_result.get("verdict", "INCORRECT")
                    evidence.append(f"{collection}: {verdict} (p={precision:.2f}, max={max_score:.2f})")
                else:
                    scores.append(0.0)
                    evidence.append(f"{collection}: no results")
            except Exception as e:
                evidence.append(f"{collection}: error={e}")

    except ImportError as e:
        evidence.append(f"import error: {e}")
        return 0.0, evidence
    except Exception as e:
        evidence.append(f"error: {e}")
        return 0.0, evidence

    score = sum(scores) / len(scores) if scores else 0.0
    return round(score, 3), evidence


def _score_prompt_context():
    """Dimension 3: Prompt/Context Quality — brief quality, compression."""
    evidence = []
    scores = []

    try:
        episodes_dir = os.path.join(WORKSPACE, "data/episodes")
        if os.path.isdir(episodes_dir):
            episode_files = sorted(Path(episodes_dir).glob("*.json"), reverse=True)[:10]
            context_sizes = []
            for ep_file in episode_files:
                try:
                    with open(ep_file) as f:
                        ep = json.load(f)
                    ctx = ep.get("context", {})
                    brain_results = ctx.get("brain_results", 0)
                    if isinstance(brain_results, int):
                        context_sizes.append(brain_results)
                    elif isinstance(brain_results, list):
                        context_sizes.append(len(brain_results))
                except Exception:
                    pass

            if context_sizes:
                avg_ctx = sum(context_sizes) / len(context_sizes)
                if 5 <= avg_ctx <= 15:
                    ctx_score = 1.0
                elif avg_ctx < 5:
                    ctx_score = avg_ctx / 5
                else:
                    ctx_score = max(0.3, 1.0 - (avg_ctx - 15) / 30)
                scores.append(ctx_score)
                evidence.append(f"avg_brain_results={avg_ctx:.1f}")

        from clarvis.metrics.quality import compute_task_quality_score
        tqs = compute_task_quality_score(days=7)
        if isinstance(tqs, dict):
            quality = tqs.get("score", 0.5)
        else:
            quality = float(tqs) if tqs else 0.5
        scores.append(min(1.0, quality))
        evidence.append(f"task_quality_7d={quality:.2f}")

    except Exception as e:
        evidence.append(f"error: {e}")

    score = sum(scores) / len(scores) if scores else 0.3
    return round(score, 3), evidence


def _score_task_success():
    """Dimension 4: Task Success — episode outcomes, reasoning depth."""
    evidence = []
    scores = []

    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        stats = em.get_stats()

        outcomes = stats.get("outcomes", {})
        total = stats.get("total", 0)
        successes = outcomes.get("success", 0)
        if total > 0:
            rate = successes / total
            scores.append(rate)
            evidence.append(f"success_rate={rate:.2f} ({successes}/{total})")

        avg_valence = stats.get("avg_valence", 0.0)
        valence_norm = max(0, min(1, (avg_valence + 1) / 2))
        scores.append(valence_norm)
        evidence.append(f"avg_valence={avg_valence:.2f}")

    except Exception as e:
        evidence.append(f"error: {e}")

    try:
        chains_file = os.path.join(WORKSPACE, "data/reasoning_chains.jsonl")
        if os.path.exists(chains_file):
            recent_chains = 0
            with_outcomes = 0
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            with open(chains_file) as f:
                for line in f:
                    try:
                        chain = json.loads(line.strip())
                        if chain.get("started", "") >= cutoff:
                            recent_chains += 1
                            if chain.get("outcome"):
                                with_outcomes += 1
                    except Exception:
                        pass
            if recent_chains > 0:
                chain_score = with_outcomes / recent_chains
                scores.append(chain_score)
                evidence.append(f"reasoning_chains_7d={recent_chains}, with_outcome={with_outcomes}")
    except Exception:
        pass

    score = sum(scores) / len(scores) if scores else 0.5
    return round(score, 3), evidence


def _score_autonomy():
    """Dimension 5: Autonomy — unattended success, cost efficiency."""
    evidence = []
    scores = []

    try:
        auto_log = os.path.join(WORKSPACE, "memory/cron/autonomous.log")
        if os.path.exists(auto_log):
            with open(auto_log) as f:
                lines = f.readlines()[-50:]
            successes = sum(1 for l in lines if "SUCCESS" in l or "success" in l)
            failures = sum(1 for l in lines if "FAIL" in l or "fail" in l.lower())
            total = successes + failures
            if total > 0:
                auto_rate = successes / total
                scores.append(auto_rate)
                evidence.append(f"autonomous_rate={auto_rate:.2f} ({successes}/{total})")

        digest_file = os.path.join(WORKSPACE, "memory/cron/digest.md")
        if os.path.exists(digest_file):
            mtime = os.path.getmtime(digest_file)
            age_hours = (time.time() - mtime) / 3600
            freshness = max(0, min(1.0, 1.0 - age_hours / 24))
            scores.append(freshness)
            evidence.append(f"digest_age={age_hours:.1f}h")

    except Exception as e:
        evidence.append(f"error: {e}")

    try:
        costs_file = os.path.join(WORKSPACE, "data/costs_real.jsonl")
        if os.path.exists(costs_file):
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
            daily_cost = 0.0
            with open(costs_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        ts = entry.get("timestamp", "")
                        if ts.startswith(today) or ts.startswith(yesterday):
                            daily_cost += entry.get("cost", 0.0)
                    except Exception:
                        pass
            cost_score = max(0, min(1.0, 1.0 - daily_cost / 10))
            scores.append(cost_score)
            evidence.append(f"daily_cost=${daily_cost:.2f}")
    except Exception:
        pass

    score = sum(scores) / len(scores) if scores else 0.2
    return round(score, 3), evidence


def _score_efficiency():
    """Dimension 6: Efficiency — query speed, brain bloat."""
    evidence = []
    scores = []

    try:
        from clarvis.brain import brain

        start = time.time()
        brain.recall("test query for speed", n=3)
        elapsed_ms = (time.time() - start) * 1000
        speed_score = max(0, min(1.0, 1.0 - elapsed_ms / 10000))
        scores.append(speed_score)
        evidence.append(f"query_speed={elapsed_ms:.0f}ms")

        stats = brain.stats()
        total = stats.get("total_memories", 0)
        if 1000 <= total <= 5000:
            bloat_score = 1.0
        elif total < 1000:
            bloat_score = total / 1000
        else:
            bloat_score = max(0.3, 1.0 - (total - 5000) / 5000)
        scores.append(bloat_score)
        evidence.append(f"brain_size={total}")

    except Exception as e:
        evidence.append(f"error: {e}")

    score = sum(scores) / len(scores) if scores else 0.4
    return round(score, 3), evidence


ASSESSORS = {
    "memory_quality": _score_memory_quality,
    "retrieval_precision": _score_retrieval_precision,
    "prompt_context": _score_prompt_context,
    "task_success": _score_task_success,
    "autonomy": _score_autonomy,
    "efficiency": _score_efficiency,
}


def compute_clr(quick=False):
    """Compute the CLR (Clarvis Rating) composite score.

    Args:
        quick: If True, skip slow assessments (retrieval_precision, prompt_context).

    Returns:
        Dict with clr score, dimension scores, evidence, and baseline comparison.
    """
    results = {}
    skip_if_quick = {"retrieval_precision", "prompt_context"}

    for dim, assessor in ASSESSORS.items():
        if quick and dim in skip_if_quick:
            results[dim] = {"score": None, "evidence": ["skipped (quick mode)"]}
            continue
        score, evidence = assessor()
        results[dim] = {"score": score, "evidence": evidence}

    weighted_sum = 0.0
    total_weight = 0.0
    for dim, weight in WEIGHTS.items():
        if results[dim]["score"] is not None:
            weighted_sum += weight * results[dim]["score"]
            total_weight += weight

    clr = round(weighted_sum / total_weight, 3) if total_weight > 0 else 0.0
    baseline_clr = sum(WEIGHTS[d] * BASELINE[d] for d in WEIGHTS)
    value_add = round(clr - baseline_clr, 3)

    return {
        "clr": clr,
        "baseline_clr": round(baseline_clr, 3),
        "value_add": value_add,
        "dimensions": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "quick": quick,
    }


def record_clr(result):
    """Record CLR result to history."""
    os.makedirs(os.path.dirname(CLR_HISTORY), exist_ok=True)

    entry = {
        "timestamp": result["timestamp"],
        "clr": result["clr"],
        "baseline_clr": result["baseline_clr"],
        "value_add": result["value_add"],
        "dimensions": {d: result["dimensions"][d]["score"] for d in result["dimensions"]},
    }

    with open(CLR_HISTORY, "a") as f:
        f.write(json.dumps(entry) + "\n")

    if os.path.exists(CLR_HISTORY):
        with open(CLR_HISTORY) as f:
            lines = f.readlines()
        if len(lines) > MAX_HISTORY:
            with open(CLR_HISTORY, "w") as f:
                f.writelines(lines[-MAX_HISTORY:])

    with open(CLR_FILE, "w") as f:
        json.dump(result, f, indent=2)


def format_clr(result):
    """Format CLR benchmark results as a string."""
    lines = []
    lines.append("=== CLR Benchmark — Clarvis Rating ===")
    lines.append(f"Timestamp: {result['timestamp']}")
    if result.get("quick"):
        lines.append("(Quick mode — some dimensions skipped)")
    lines.append("")

    for dim, data in result["dimensions"].items():
        weight = WEIGHTS[dim]
        score_str = f"{data['score']:.3f}" if data["score"] is not None else "skipped"
        baseline_str = f"{BASELINE[dim]:.2f}"
        lines.append(f"  {dim:25s}  score={score_str:>7s}  weight={weight:.2f}  baseline={baseline_str}")
        for e in data["evidence"]:
            lines.append(f"    {e}")

    lines.append("")
    lines.append(f"  CLR Score:    {result['clr']:.3f}")
    lines.append(f"  Baseline:     {result['baseline_clr']:.3f}")
    lines.append(f"  Value Add:    +{result['value_add']:.3f}")

    clr = result["clr"]
    if clr >= 0.80:
        interp = "Excellent — all cognitive systems contributing strongly"
    elif clr >= 0.60:
        interp = "Good — brain adds clear value, room for improvement"
    elif clr >= 0.40:
        interp = "Acceptable — meeting targets, optimization needed"
    elif clr >= 0.20:
        interp = "Poor — brain under-contributing, check retrieval"
    else:
        interp = "Critical — cognitive systems need attention"
    lines.append(f"  Rating:       {interp}")

    return "\n".join(lines)


def get_clr_trend(days=14):
    """Get CLR trend data over recent days.

    Returns list of dicts with timestamp, clr, value_add, dimensions.
    """
    if not os.path.exists(CLR_HISTORY):
        return []

    with open(CLR_HISTORY) as f:
        entries = [json.loads(line.strip()) for line in f if line.strip()]

    if not entries:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [e for e in entries if e["timestamp"] >= cutoff]
