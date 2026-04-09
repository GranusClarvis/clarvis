"""
CLR-Internal (Clarvis Rating) — Composite Architecture Health Score.

CLR-Internal measures the value that Clarvis's cognitive architecture adds
on top of a bare Claude Code agent. It combines 7 dimensions into a single
0-1 score for internal health monitoring and regression detection.

NOTE: This is the INTERNAL operational metric. For external task-based
evaluation (LongMemEval, MemBench, BEAM), use CLR-Benchmark
(clarvis.metrics.clr_benchmark).

Dimensions:
  1. Memory Quality          (w=0.18) — recall accuracy, retrieval precision, hit rate
  2. Retrieval Precision     (w=0.17) — context relevance, noise ratio, eval verdict
  3. Prompt/Context          (w=0.18) — brief quality, context_relevance score, compression
  4. Task Success            (w=0.18) — episode success rate, quality score, reasoning depth
  5. Autonomy                (w=0.11) — unattended success, cost efficiency
  6. Efficiency              (w=0.06) — query speed, token economy, brain bloat
  7. Integration Dynamics    (w=0.12) — ΦID-inspired: redundancy, unique contribution, synergy

Baseline (no brain, no memory) is estimated at ~0.215 CLR.
"""

import json
import math
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
CLR_FILE = os.path.join(WORKSPACE, "data/clr_benchmark.json")
CLR_HISTORY = os.path.join(WORKSPACE, "data/clr_history.jsonl")
MAX_HISTORY = 400
CLR_SCHEMA_VERSION = "1.0"

# Dimension weights — must sum to 1.0
# 2026-03-21: prompt_context raised 0.13→0.18 (context relevance is weakest metric).
# Rebalanced: efficiency 0.08→0.06, integration_dynamics 0.14→0.12, autonomy 0.12→0.11.
WEIGHTS = {
    "memory_quality": 0.18,
    "retrieval_precision": 0.17,
    "prompt_context": 0.18,
    "task_success": 0.18,
    "autonomy": 0.11,
    "efficiency": 0.06,
    "integration_dynamics": 0.12,
}

GATE_THRESHOLDS = {
    "min_clr": 0.40,
    "min_value_add": 0.05,
    "min_dimensions": {
        "memory_quality": 0.25,
        "retrieval_precision": 0.25,
        "prompt_context": 0.20,
        "task_success": 0.35,
    },
}

# Estimated baseline scores (bare Claude Code, no Clarvis brain)
BASELINE = {
    "memory_quality": 0.0,       # No persistent memory
    "retrieval_precision": 0.0,  # No retrieval
    "prompt_context": 0.30,      # Basic context from files only
    "task_success": 0.50,        # Claude is still good at tasks
    "autonomy": 0.20,            # No autonomous loop (w=0.11)
    "efficiency": 0.40,          # No optimization, but no overhead either (w=0.06)
    "integration_dynamics": 0.0, # No integration without cognitive architecture (w=0.12)
}


def _get_commit_sha() -> str:
    """Get current git commit SHA (short), or 'unknown' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=WORKSPACE,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def validate_weights(weights: dict[str, float] | None = None) -> tuple[bool, float]:
    """Validate that CLR dimension weights sum to 1.0 (within tolerance)."""
    ws = weights or WEIGHTS
    total = sum(ws.values())
    valid = abs(total - 1.0) <= 1e-6
    return valid, total


def evaluate_clr_gates(
    result: dict[str, Any],
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate CLR quality gates for release/benchmark decisions."""
    cfg = thresholds or GATE_THRESHOLDS
    failures: list[str] = []
    details: dict[str, Any] = {
        "min_clr": cfg.get("min_clr"),
        "min_value_add": cfg.get("min_value_add"),
        "min_dimensions": cfg.get("min_dimensions", {}),
    }

    clr = float(result.get("clr", 0.0))
    value_add = float(result.get("value_add", 0.0))
    if clr < cfg.get("min_clr", 0.0):
        failures.append(f"clr<{cfg['min_clr']} ({clr:.3f})")
    if value_add < cfg.get("min_value_add", 0.0):
        failures.append(f"value_add<{cfg['min_value_add']} ({value_add:.3f})")

    min_dims = cfg.get("min_dimensions", {})
    dims = result.get("dimensions", {})
    for dim, min_score in min_dims.items():
        score = dims.get(dim, {}).get("score")
        if score is None:
            failures.append(f"{dim}=missing")
            continue
        if float(score) < float(min_score):
            failures.append(f"{dim}<{min_score} ({float(score):.3f})")

    return {
        "pass": len(failures) == 0,
        "failures": failures,
        "details": details,
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
    """Dimension 2: Retrieval Precision — context relevance and noise filtering.

    Uses cross-collection discriminative queries that test whether the brain
    returns genuinely relevant results.  Includes an adversarial query that
    SHOULD score low (Clarvis has no Kubernetes content), ensuring precision
    is < 1.0 when retrieval is working correctly.

    Fixed 2026-04-09 (Phase 2 Measurement Integrity): replaced trivial
    per-collection queries that always returned precision=1.0.
    """
    evidence = []
    scores = []

    try:
        from clarvis.brain import brain
        from clarvis.brain.retrieval_eval import evaluate_retrieval

        # Cross-collection queries: no collection filter, require genuine matching.
        # Mix of specific technical queries (should match) and one adversarial
        # query (should NOT match), producing real dynamic range.
        test_queries = [
            # Should match: heartbeat pipeline is well-documented
            "heartbeat pipeline preflight postflight episode encoding",
            # Should match: graph store is core infra
            "SQLite graph store WAL checkpoint compaction",
            # Should match: context assembly is a key subsystem
            "context assembly token budget section relevance scoring",
            # Should match: secret redaction was recently fixed
            "secret redaction pattern API key Bearer token",
            # Adversarial: Clarvis does NOT use Kubernetes — should score low
            "kubernetes pod horizontal autoscaler helm chart deployment",
        ]

        for query in test_queries:
            try:
                results = brain.recall(query, n=5)
                if results:
                    eval_result = evaluate_retrieval(results, query)
                    n_above = eval_result.get("n_above_threshold", 0)
                    n_total = eval_result.get("n_results", 0)
                    max_score = eval_result.get("max_score", 0.0)
                    precision = n_above / max(n_total, 1)
                    scores.append(precision)
                    verdict = eval_result.get("verdict", "INCORRECT")
                    short_q = query[:40]
                    evidence.append(
                        f"{short_q}: {verdict} (p={precision:.2f}, max={max_score:.2f})"
                    )
                else:
                    scores.append(0.0)
                    short_q = query[:40]
                    evidence.append(f"{short_q}: no results")
            except Exception as e:
                short_q = query[:40]
                evidence.append(f"{short_q}: error={e}")

    except ImportError as e:
        evidence.append(f"import error: {e}")
        return 0.0, evidence
    except Exception as e:
        evidence.append(f"error: {e}")
        return 0.0, evidence

    score = sum(scores) / len(scores) if scores else 0.0
    return round(score, 3), evidence


def _score_prompt_context():
    """Dimension 3: Prompt/Context Quality — brief quality, context_relevance, compression."""
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
            quality = tqs.get("quality_score", tqs.get("score", 0.5))
        else:
            quality = float(tqs) if tqs else 0.5
        scores.append(min(1.0, quality))
        evidence.append(f"task_quality_7d={quality:.2f}")

    except Exception as e:
        evidence.append(f"error: {e}")

    # Sub-score: direct context_relevance from episode feedback loop.
    # This gives CLR direct visibility into how relevant the assembled
    # brief sections actually are to downstream task outputs.
    cr_score = _get_context_relevance_score()
    if cr_score is not None:
        scores.append(cr_score)
        evidence.append(f"context_relevance={cr_score:.3f}")

    score = sum(scores) / len(scores) if scores else 0.3
    return round(score, 3), evidence


def _get_context_relevance_score() -> float | None:
    """Read aggregate context_relevance and return a 0-1 score.

    Uses the mean of per-section relevance scores (not the overall episode
    score) because per-section scores have useful dynamic range (0.08-0.33
    typically) while the overall score saturates near 0.8.

    This score is also exposed via get_latest_context_relevance() for
    assembly adaptive thresholds to consume.
    """
    try:
        from clarvis.cognition.context_relevance import aggregate_relevance
        agg = aggregate_relevance(days=14, recency_boost=5)
        if agg.get("episodes", 0) < 3:
            return None
        per_section = agg.get("per_section_mean", {})
        if not per_section:
            return None
        # Mean of per-section scores — typically 0.10-0.25 range.
        # Normalize: map [0, 0.35] → [0, 1.0] for useful CLR dynamic range.
        section_mean = sum(per_section.values()) / len(per_section)
        return min(1.0, round(section_mean / 0.35, 3))
    except Exception:
        return None


def get_latest_context_relevance() -> dict:
    """Get the latest context_relevance data for assembly feedback.

    Returns dict with:
        score: normalized 0-1 context relevance score (from per-section mean)
        raw_section_mean: raw mean of per-section scores
        per_section: per-section mean scores
        episodes: number of episodes in window

    Assembly can use 'score' to adjust adaptive thresholds — e.g.,
    if score < 0.5 (section_mean < 0.175), boost high-relevance sections.
    """
    try:
        from clarvis.cognition.context_relevance import aggregate_relevance
        agg = aggregate_relevance(days=14, recency_boost=5)
        eps = agg.get("episodes", 0)
        if eps < 3:
            return {"score": None, "raw_section_mean": None, "per_section": {}, "episodes": eps}
        per_section = agg.get("per_section_mean", {})
        if not per_section:
            return {"score": None, "raw_section_mean": None, "per_section": {}, "episodes": eps}
        section_mean = sum(per_section.values()) / len(per_section)
        return {
            "score": min(1.0, round(section_mean / 0.35, 3)),
            "raw_section_mean": round(section_mean, 4),
            "per_section": per_section,
            "episodes": eps,
        }
    except Exception:
        return {"score": None, "raw_section_mean": None, "per_section": {}, "episodes": 0}


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
        costs_file = os.path.join(WORKSPACE, "data/costs.jsonl")
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
                            daily_cost += entry.get("cost_usd", entry.get("cost", 0.0))
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


def _score_integration_dynamics():
    """Dimension 7: Integration Dynamics (ΦID-inspired).

    Sub-metrics:
      - redundancy_ratio: how much repeated content across brief sections
      - unique_contribution_score: how many distinct modules contribute useful info
      - synergy_gain: whether combined modules outperform individual ones

    Data source: data/retrieval_quality/context_relevance.jsonl (per-section scores)
    and data/episodes.json (outcome/valence).
    """
    evidence = []
    scores = []

    # Load recent context relevance entries (per-section data)
    cr_file = os.path.join(WORKSPACE, "data/retrieval_quality/context_relevance.jsonl")
    cr_entries = []
    if os.path.exists(cr_file):
        try:
            with open(cr_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            cr_entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            cr_entries = cr_entries[-30:]  # Last 30 entries
        except Exception:
            pass

    # Load recent episodes for outcome data
    ep_file = os.path.join(WORKSPACE, "data/episodes.json")
    episodes = []
    if os.path.exists(ep_file):
        try:
            with open(ep_file) as f:
                episodes = json.load(f)
            episodes = episodes[-30:]
        except Exception:
            pass

    # Known brief sections (modules that contribute to context)
    expected_sections = [
        "decision_context", "knowledge", "related_tasks", "metrics",
        "reasoning", "brain_context", "working_memory", "attention",
    ]

    # --- Sub-metric 1: Redundancy Ratio ---
    # High per-section scores across many sections = each provides unique value (low redundancy)
    # Low variance in section scores = even contribution = good integration
    if cr_entries:
        try:
            redundancy_samples = []
            for entry in cr_entries:
                per_section = entry.get("per_section", {})
                if len(per_section) < 2:
                    continue
                section_scores = list(per_section.values())
                # Redundancy proxy: if many sections have very similar scores,
                # they might be providing overlapping info.
                # Use coefficient of variation — higher = more differentiated (less redundant)
                mean_s = sum(section_scores) / len(section_scores)
                if mean_s > 0:
                    variance_s = sum((s - mean_s) ** 2 for s in section_scores) / len(section_scores)
                    cv = (variance_s ** 0.5) / mean_s
                    # CV > 0.5 means well-differentiated sections (low redundancy)
                    # CV < 0.2 means sections are too similar (high redundancy)
                    r_score = min(1.0, cv / 0.6)
                    redundancy_samples.append(r_score)

            if redundancy_samples:
                avg_r = sum(redundancy_samples) / len(redundancy_samples)
                scores.append(avg_r)
                evidence.append(f"redundancy_ratio={avg_r:.3f} (n={len(redundancy_samples)})")
            else:
                evidence.append("redundancy_ratio=no_data")
        except Exception as e:
            evidence.append(f"redundancy_ratio error: {e}")
    else:
        evidence.append("redundancy_ratio=no_cr_data")

    # --- Sub-metric 2: Unique Contribution Score ---
    # Blend of: (a) fraction of sections referenced, and (b) mean containment
    # across sections.  Pure referenced/total is coarse (binary per section);
    # mean containment gives proportional credit for partial overlap.
    if cr_entries:
        try:
            unique_samples = []
            containment_samples = []
            for entry in cr_entries:
                per_section = entry.get("per_section", {})
                total_sections = entry.get("sections_total", len(per_section))
                referenced = entry.get("sections_referenced", 0)
                if total_sections > 0:
                    unique_samples.append(referenced / total_sections)
                if per_section:
                    mean_cont = sum(per_section.values()) / len(per_section)
                    # Normalize: containment 0.25+ = full score
                    containment_samples.append(min(1.0, mean_cont / 0.25))

            if unique_samples:
                avg_unique = sum(unique_samples) / len(unique_samples)
                avg_cont = (sum(containment_samples) / len(containment_samples)
                            if containment_samples else avg_unique)
                # Blend: 50% reference ratio, 50% mean containment depth
                blended = 0.5 * avg_unique + 0.5 * avg_cont
                scores.append(min(1.0, blended))
                evidence.append(
                    f"unique_contribution={blended:.3f} "
                    f"(ref={avg_unique:.3f}, cont={avg_cont:.3f}, n={len(unique_samples)})"
                )
            else:
                evidence.append("unique_contribution=no_data")
        except Exception as e:
            evidence.append(f"unique_contribution error: {e}")
    else:
        evidence.append("unique_contribution=no_cr_data")

    # --- Sub-metric 3: Synergy Gain ---
    # Compare: episodes with more referenced sections should have better outcomes
    if cr_entries and episodes:
        try:
            # Build a lookup from timestamp prefix to outcome
            ep_outcomes = {}
            for ep in episodes:
                ts = ep.get("timestamp", "")[:16]
                ep_outcomes[ts] = ep.get("outcome", "")

            rich_success = []
            sparse_success = []
            for entry in cr_entries:
                ts = entry.get("ts", "")[:16]
                outcome = entry.get("outcome", ep_outcomes.get(ts, ""))
                is_success = outcome == "success"
                referenced = entry.get("sections_referenced", 0)
                total = entry.get("sections_total", 1)
                if total == 0:
                    continue
                ratio = referenced / total
                if ratio >= 0.7:
                    rich_success.append(1.0 if is_success else 0.0)
                elif ratio <= 0.4:
                    sparse_success.append(1.0 if is_success else 0.0)

            if rich_success and sparse_success:
                rich_rate = sum(rich_success) / len(rich_success)
                sparse_rate = sum(sparse_success) / len(sparse_success)
                synergy = rich_rate - sparse_rate
                # Base: 0.5 + differential.  But when both rates are high,
                # that indicates the cognitive architecture consistently
                # delivers good outcomes — reward that (min of the two rates
                # serves as a floor so universally-high success ≥ 0.8).
                base_synergy = max(0, min(1.0, 0.5 + synergy))
                floor_from_rates = min(rich_rate, sparse_rate)
                synergy_score = max(base_synergy, floor_from_rates)
                scores.append(synergy_score)
                evidence.append(
                    f"synergy_gain={synergy:.3f} "
                    f"(rich={rich_rate:.2f}[n={len(rich_success)}], "
                    f"sparse={sparse_rate:.2f}[n={len(sparse_success)}])"
                )
            elif rich_success:
                rich_rate = sum(rich_success) / len(rich_success)
                scores.append(min(1.0, rich_rate))
                evidence.append(f"synergy_gain=rich_only ({rich_rate:.2f}, n={len(rich_success)})")
            else:
                evidence.append("synergy_gain=insufficient_data")
        except Exception as e:
            evidence.append(f"synergy_gain error: {e}")
    else:
        evidence.append("synergy_gain=no_data")

    score = sum(scores) / len(scores) if scores else 0.0
    return round(score, 3), evidence


ASSESSORS = {
    "memory_quality": _score_memory_quality,
    "retrieval_precision": _score_retrieval_precision,
    "prompt_context": _score_prompt_context,
    "task_success": _score_task_success,
    "autonomy": _score_autonomy,
    "efficiency": _score_efficiency,
    "integration_dynamics": _score_integration_dynamics,
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

    weights_valid, weights_total = validate_weights()
    weighted_sum = 0.0
    total_weight = 0.0
    for dim, weight in WEIGHTS.items():
        if results[dim]["score"] is not None:
            weighted_sum += weight * results[dim]["score"]
            total_weight += weight

    clr = round(weighted_sum / total_weight, 3) if total_weight > 0 else 0.0
    baseline_clr = sum(WEIGHTS[d] * BASELINE[d] for d in WEIGHTS)
    value_add = round(clr - baseline_clr, 3)

    # Count dimensions using real data vs fallback defaults
    dims_with_real_data = 0
    dims_total = 0
    for dim, data in results.items():
        if data["score"] is None:
            continue  # skipped in quick mode
        dims_total += 1
        # A dimension uses real data if it has evidence beyond just errors/fallbacks
        has_real = any(
            not e.startswith("error") and e != "no_data"
            for e in data.get("evidence", [])
        )
        if has_real:
            dims_with_real_data += 1

    result = {
        "clr": clr,
        "baseline_clr": round(baseline_clr, 3),
        "value_add": value_add,
        "dimensions": results,
        "dims_with_real_data": dims_with_real_data,
        "dims_total": dims_total,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_sha": _get_commit_sha(),
        "quick": quick,
        "schema_version": CLR_SCHEMA_VERSION,
        "weights_valid": weights_valid,
        "weights_total": round(weights_total, 6),
    }
    result["gate"] = evaluate_clr_gates(result)
    return result


def _get_previous_entry():
    """Load the most recent history entry (if any) for delta computation."""
    if not os.path.exists(CLR_HISTORY):
        return None
    try:
        with open(CLR_HISTORY) as f:
            lines = f.readlines()
        for line in reversed(lines):
            line = line.strip()
            if line:
                return json.loads(line)
    except Exception:
        pass
    return None


def _compute_deltas(current_entry, previous_entry):
    """Compute per-dimension and overall deltas between two history entries.

    Returns dict with 'clr_delta', 'value_add_delta', 'dimension_deltas',
    and 'previous_commit'.
    """
    if previous_entry is None:
        return None

    clr_delta = round(current_entry["clr"] - previous_entry.get("clr", 0.0), 4)
    va_delta = round(
        current_entry["value_add"] - previous_entry.get("value_add", 0.0), 4
    )

    dim_deltas = {}
    prev_dims = previous_entry.get("dimensions", {})
    curr_dims = current_entry.get("dimensions", {})
    for dim in set(list(curr_dims.keys()) + list(prev_dims.keys())):
        c = curr_dims.get(dim)
        p = prev_dims.get(dim)
        if c is not None and p is not None:
            dim_deltas[dim] = round(c - p, 4)
        elif c is not None:
            dim_deltas[dim] = None  # no previous data

    return {
        "clr_delta": clr_delta,
        "value_add_delta": va_delta,
        "dimension_deltas": dim_deltas,
        "previous_commit": previous_entry.get("commit_sha", "unknown"),
        "previous_timestamp": previous_entry.get("timestamp", "unknown"),
    }


def record_clr(result):
    """Record CLR result to history with before/after deltas."""
    os.makedirs(os.path.dirname(CLR_HISTORY), exist_ok=True)

    entry = {
        "timestamp": result["timestamp"],
        "commit_sha": result.get("commit_sha", "unknown"),
        "clr": result["clr"],
        "baseline_clr": result["baseline_clr"],
        "value_add": result["value_add"],
        "schema_version": result.get("schema_version", CLR_SCHEMA_VERSION),
        "gate_pass": bool(result.get("gate", {}).get("pass", False)),
        "dimensions": {d: result["dimensions"][d]["score"] for d in result["dimensions"]},
    }

    # Compute deltas from previous run
    previous = _get_previous_entry()
    deltas = _compute_deltas(entry, previous)
    if deltas:
        entry["deltas"] = deltas

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

    return deltas


def format_clr(result):
    """Format CLR benchmark results as a string."""
    lines = []
    lines.append("=== CLR-Internal — Clarvis Architecture Health ===")
    lines.append(f"Timestamp: {result['timestamp']}")
    lines.append(f"Commit:    {result.get('commit_sha', 'unknown')}")
    lines.append(f"Schema:    {result.get('schema_version', CLR_SCHEMA_VERSION)}")
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
    lines.append(
        f"  Weights:      {'OK' if result.get('weights_valid') else 'INVALID'} "
        f"(sum={result.get('weights_total', '?')})"
    )
    gate = result.get("gate", {})
    lines.append(f"  Gate:         {'PASS' if gate.get('pass') else 'FAIL'}")
    if gate.get("failures"):
        for failure in gate["failures"]:
            lines.append(f"    - {failure}")

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
        entries = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [e for e in entries if e["timestamp"] >= cutoff]


def evaluate_clr_stability(
    entries: list[dict[str, Any]] | None = None,
    *,
    days: int = 14,
    min_runs: int = 14,
    max_stddev: float = 0.12,
    max_regression: float = 0.08,
) -> dict[str, Any]:
    """Evaluate CLR trend stability across recent history.

    This is a governance gate intended for release readiness:
    - enough benchmark samples exist in the analysis window
    - CLR volatility remains bounded
    - latest CLR does not regress materially from earliest sample
    """

    trend = entries if entries is not None else get_clr_trend(days=days)
    failures: list[str] = []
    stats: dict[str, Any] = {
        "days": days,
        "runs": len(trend),
        "min_runs": min_runs,
        "max_stddev": max_stddev,
        "max_regression": max_regression,
    }

    if len(trend) < min_runs:
        failures.append(f"insufficient_runs<{min_runs} ({len(trend)})")
        return {
            "pass": False,
            "failures": failures,
            "stats": stats,
        }

    clr_values = [float(e.get("clr", 0.0)) for e in trend]
    mean = sum(clr_values) / len(clr_values)
    variance = sum((v - mean) ** 2 for v in clr_values) / len(clr_values)
    stddev = math.sqrt(variance)
    delta = clr_values[-1] - clr_values[0]

    stats.update(
        {
            "mean": round(mean, 4),
            "stddev": round(stddev, 4),
            "delta": round(delta, 4),
            "min": round(min(clr_values), 4),
            "max": round(max(clr_values), 4),
        }
    )

    if stddev > max_stddev:
        failures.append(f"stddev>{max_stddev} ({stddev:.4f})")
    if delta < -max_regression:
        failures.append(f"regression>{max_regression} ({delta:.4f})")

    return {
        "pass": len(failures) == 0,
        "failures": failures,
        "stats": stats,
    }


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    quick = "--quick" in sys.argv or "-q" in sys.argv
    do_record = "--record" in sys.argv or "-r" in sys.argv

    if cmd in ("run", "compute"):
        result = compute_clr(quick=quick)
        print(format_clr(result))
        if do_record:
            deltas = record_clr(result)
            print(f"\nRecorded to {CLR_HISTORY}")
            if deltas:
                d = deltas["clr_delta"]
                print(f"Delta from previous: CLR {d:+.4f} (prev commit: {deltas['previous_commit']})")
                dim_d = deltas.get("dimension_deltas", {})
                changed = [(k, v) for k, v in dim_d.items() if v is not None and abs(v) > 0.005]
                if changed:
                    changed.sort(key=lambda x: abs(x[1]), reverse=True)
                    for k, v in changed:
                        print(f"  {k}: {v:+.4f}")
    elif cmd == "json":
        result = compute_clr(quick=quick)
        print(json.dumps(result, indent=2))
        if do_record:
            record_clr(result)
    elif cmd == "trend":
        days = 14
        for arg in sys.argv[2:]:
            if arg.isdigit():
                days = int(arg)
        entries = get_clr_trend(days=days)
        if not entries:
            print("No CLR history. Run with --record first.")
        else:
            for e in entries:
                ts = e["timestamp"][:10]
                sha = e.get("commit_sha", "?")[:7]
                d = e.get("deltas", {})
                delta_str = f" d={d['clr_delta']:+.3f}" if d.get("clr_delta") is not None else ""
                print(f"  {ts} [{sha}] CLR={e['clr']:.3f} +{e['value_add']:.3f}{delta_str}")
    elif cmd == "delta":
        entries = get_clr_trend(days=30)
        entries_with_deltas = [e for e in entries if e.get("deltas")]
        if not entries_with_deltas:
            print("No entries with delta data. Run with --record to start tracking.")
        else:
            print(f"{'Date':<12} {'Commit':<9} {'CLR':>6} {'Delta':>8} {'Dimensions with biggest change'}")
            print("-" * 75)
            for e in entries_with_deltas[-20:]:
                ts = e["timestamp"][:10]
                sha = e.get("commit_sha", "?")[:7]
                d = e["deltas"]
                dim_d = d.get("dimension_deltas", {})
                # Show top 2 changed dimensions
                changed = [(k, v) for k, v in dim_d.items() if v is not None and abs(v) > 0.005]
                changed.sort(key=lambda x: abs(x[1]), reverse=True)
                dim_str = ", ".join(f"{k}:{v:+.3f}" for k, v in changed[:2]) if changed else "stable"
                print(f"{ts:<12} [{sha}] {e['clr']:>6.3f} {d['clr_delta']:>+8.4f}  {dim_str}")
    elif cmd == "stability":
        result = evaluate_clr_stability()
        print(json.dumps(result, indent=2))
    else:
        print(f"Usage: python3 -m clarvis.metrics.clr [run|json|trend|delta|stability] [--quick] [--record]")
