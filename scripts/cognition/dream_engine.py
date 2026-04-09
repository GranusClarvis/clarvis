#!/usr/bin/env python3
"""
Counterfactual Dreaming Engine — Adversarial training against own experience.

During idle time (02:00 window), this engine:
1. Selects 10 random episodes from episodic memory
2. Generates counterfactual variations ("what if this failed/succeeded differently?")
3. Runs counterfactuals through the reasoning chain framework
4. Stores dream-sourced insights with lower activation in episodic memory

This is mental simulation: by imagining alternative outcomes for real experiences,
Clarvis stress-tests its own assumptions and discovers blind spots.

Usage:
    python3 dream_engine.py dream          # Run full dream cycle (10 episodes)
    python3 dream_engine.py dream 5        # Dream on 5 episodes
    python3 dream_engine.py stats          # Show dream history stats
    python3 dream_engine.py insights       # List stored dream insights

Integration:
    - Runs in the 02:00 backup window (low-activity period)
    - Add to crontab: 15 2 * * * python3 dream_engine.py dream >> dream.log 2>&1
"""

import json
import random
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

from brain import brain
from clarvis.memory.episodic_memory import episodic
from reasoning_chains import create_chain, add_step, complete_step

DREAM_LOG = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/dream_log.json"
DREAM_LOG.parent.mkdir(parents=True, exist_ok=True)

# Counterfactual templates: each flips an assumption about the episode
COUNTERFACTUAL_TEMPLATES = [
    {
        "id": "failure_flip",
        "label": "What if this task had failed?",
        "applies_to": "success",
        "transform": lambda ep: {
            "scenario": f"Counterfactual: '{ep['task'][:80]}' FAILED instead of succeeding",
            "question": "What would have broken? What dependency would have been exposed?",
            "flipped_outcome": "failure",
        },
    },
    {
        "id": "success_flip",
        "label": "What if this failure had succeeded?",
        "applies_to": "failure",
        "transform": lambda ep: {
            "scenario": f"Counterfactual: '{ep['task'][:80]}' SUCCEEDED despite the error",
            "question": "What conditions would have needed to be different? What was the real blocker?",
            "flipped_outcome": "success",
        },
    },
    {
        "id": "cascading_failure",
        "label": "What if this triggered a cascading failure?",
        "applies_to": "success",
        "transform": lambda ep: {
            "scenario": f"Counterfactual: '{ep['task'][:80]}' succeeded but caused a downstream failure",
            "question": "What other systems depend on this? What could break silently?",
            "flipped_outcome": "cascade_failure",
        },
    },
    {
        "id": "slow_path",
        "label": "What if this took 10x longer?",
        "applies_to": "any",
        "transform": lambda ep: {
            "scenario": f"Counterfactual: '{ep['task'][:80]}' took {ep.get('duration_s', 60) * 10}s instead of {ep.get('duration_s', 60)}s",
            "question": "Would we have timed out? What bottleneck would have emerged?",
            "flipped_outcome": "timeout",
        },
    },
    {
        "id": "wrong_approach",
        "label": "What if we used the wrong approach entirely?",
        "applies_to": "success",
        "transform": lambda ep: {
            "scenario": f"Counterfactual: The approach used for '{ep['task'][:80]}' was fundamentally wrong",
            "question": "What alternative approach exists? Why might the current approach be fragile?",
            "flipped_outcome": "wrong_approach",
        },
    },
    {
        "id": "data_corruption",
        "label": "What if the data was corrupted?",
        "applies_to": "any",
        "transform": lambda ep: {
            "scenario": f"Counterfactual: Data fed into '{ep['task'][:80]}' was silently corrupted",
            "question": "Would we detect it? What validation is missing?",
            "flipped_outcome": "silent_failure",
        },
    },
    {
        "id": "pearl_intervention",
        "label": "Pearl SCM: What if strategy had been different?",
        "applies_to": "any",
        "transform": lambda ep: _pearl_scm_counterfactual(ep),
    },
]


def _pearl_scm_counterfactual(episode):
    """Generate a counterfactual using Pearl's structural causal model.

    Uses the causal_model.py SCM engine for principled do-calculus reasoning
    (Rung 3 of the Ladder of Causation) rather than template-based what-ifs.
    """
    try:
        from causal_model import run_counterfactual
        # Try different strategy intervention
        strategies = ["implement", "fix", "research", "optimize", "test"]
        task_lower = episode.get("task", "").lower()
        # Pick a strategy different from what was actually used
        alt_strategies = [s for s in strategies if s not in task_lower]
        alt = alt_strategies[0] if alt_strategies else "research"

        result = run_counterfactual(episode["id"], {"strategy": alt}, "outcome")
        prediction = result.get("counterfactual_answer", {})
        est = prediction.get("estimate", "unknown")
        conf = prediction.get("confidence", 0)

        return {
            "scenario": (f"Pearl SCM counterfactual: '{episode['task'][:60]}' "
                         f"with do(strategy={alt}) → P(outcome={est})={conf:.0%}"),
            "question": (f"The SCM predicts {est} with {conf:.0%} confidence. "
                         f"Does this match intuition? What confounders might invalidate this?"),
            "flipped_outcome": est,
            "scm_detail": result,
        }
    except Exception as e:
        return {
            "scenario": f"Counterfactual: '{episode['task'][:80]}' with a different strategy",
            "question": f"SCM unavailable ({e}). What strategy would have changed the outcome?",
            "flipped_outcome": "unknown",
        }


def _load_dream_log():
    """Load dream history."""
    if DREAM_LOG.exists():
        with open(DREAM_LOG) as f:
            return json.load(f)
    return {"dreams": [], "total_insights": 0, "sessions": 0}


def _save_dream_log(log):
    """Save dream history (cap at 200 entries)."""
    log["dreams"] = log["dreams"][-200:]
    with open(DREAM_LOG, "w") as f:
        json.dump(log, f, indent=2)


def compute_surprise(episode, all_episodes):
    """Compute SuRe-inspired surprise score for an episode.

    Adapted from SuRe (arXiv:2511.22367): Surprise = how poorly the system
    "predicted" this episode's outcome, measured as semantic distance from
    nearest neighbors (analog to NLL in neural systems).

    High surprise = episode violates expectations → most valuable for replay.

    Components:
      1. Outcome surprise: failures are more surprising than successes
      2. Duration anomaly: unusually fast/slow episodes are surprising
      3. Semantic novelty: episodes unlike their neighbors carry more information
      4. Confidence gap: low-confidence outcomes are more surprising

    Returns:
        float: surprise score (0.0 to 1.0, higher = more surprising)
    """
    outcome = episode.get("outcome", "success")
    duration = episode.get("duration_s", 60)
    confidence = episode.get("confidence", 0.5)
    task = episode.get("task", "")

    # Component 1: Outcome surprise — failures are rarer, hence more surprising
    outcome_surprise = 0.7 if outcome != "success" else 0.2

    # Component 2: Duration anomaly — how far from the mean duration?
    durations = [ep.get("duration_s", 60) for ep in all_episodes if ep.get("duration_s")]
    if durations:
        mean_dur = sum(durations) / len(durations)
        std_dur = max(1.0, (sum((d - mean_dur)**2 for d in durations) / len(durations)) ** 0.5)
        duration_anomaly = min(1.0, abs(duration - mean_dur) / (2 * std_dur))
    else:
        duration_anomaly = 0.0

    # Component 3: Semantic novelty — task text distance from neighbors
    # (proxy for NLL: novel content = high "prediction error")
    task_lower = task.lower()
    similarities = []
    for other in all_episodes:
        if other["id"] == episode["id"]:
            continue
        other_task = other.get("task", "").lower()
        if not other_task:
            continue
        # Jaccard similarity on word sets as fast proxy
        words_a = set(task_lower.split())
        words_b = set(other_task.split())
        if words_a or words_b:
            jaccard = len(words_a & words_b) / max(1, len(words_a | words_b))
            similarities.append(jaccard)
    # Novelty = 1 - max_similarity (most unique episodes are most novel)
    semantic_novelty = 1.0 - max(similarities[:10]) if similarities else 1.0

    # Component 4: Confidence gap — low confidence = high surprise
    confidence_surprise = 1.0 - min(1.0, max(0.0, confidence))

    # Weighted combination (SuRe emphasizes prediction error most)
    surprise = (
        0.30 * outcome_surprise
        + 0.15 * duration_anomaly
        + 0.35 * semantic_novelty  # Heaviest weight — analog to NLL
        + 0.20 * confidence_surprise
    )
    return round(min(1.0, surprise), 4)


def select_episodes(n=10):
    """Select n episodes for dreaming, prioritized by SuRe-style surprise.

    Adapted from SuRe (arXiv:2511.22367): instead of random selection,
    prioritize episodes that the system "predicted poorly" (high surprise).
    These carry the most learning signal for counterfactual reasoning.

    The top 70% of slots go to highest-surprise episodes.
    The remaining 30% are sampled proportional to recency × valence
    to maintain exploration diversity.
    """
    episodes = episodic.episodes
    if not episodes:
        return []

    # Compute surprise scores for all episodes
    surprise_scores = {}
    for ep in episodes:
        surprise_scores[ep["id"]] = compute_surprise(ep, episodes)

    # Split budget: 70% surprise-driven, 30% exploration
    n_surprise = max(1, int(n * 0.7))
    n_explore = n - n_surprise

    # Top surprise episodes
    sorted_eps = sorted(episodes, key=lambda ep: surprise_scores.get(ep["id"], 0), reverse=True)
    surprise_picks = sorted_eps[:n_surprise]
    picked_ids = {ep["id"] for ep in surprise_picks}

    # Exploration: recency × valence weighted sampling from remainder
    remaining = [ep for ep in episodes if ep["id"] not in picked_ids]
    if remaining and n_explore > 0:
        weights = []
        for i, ep in enumerate(remaining):
            recency = (episodes.index(ep) + 1) / len(episodes)
            valence = ep.get("valence", 0.5)
            weight = recency * 0.6 + valence * 0.4
            weights.append(weight)
        k = min(n_explore, len(remaining))
        explore_picks = random.choices(remaining, weights=weights, k=k)
    else:
        explore_picks = []

    # Combine and deduplicate
    selected = surprise_picks + explore_picks
    seen = set()
    unique = []
    for ep in selected:
        if ep["id"] not in seen:
            seen.add(ep["id"])
            unique.append(ep)

    return unique[:n]


def generate_counterfactual(episode):
    """Generate a counterfactual variation for an episode.

    Picks the most applicable template based on the episode's outcome.
    Returns a counterfactual dict or None if no template applies.
    """
    outcome = episode.get("outcome", "success")

    # Filter templates that apply to this outcome
    applicable = [
        t for t in COUNTERFACTUAL_TEMPLATES
        if t["applies_to"] == outcome or t["applies_to"] == "any"
    ]

    if not applicable:
        # Fallback: use any template
        applicable = COUNTERFACTUAL_TEMPLATES

    template = random.choice(applicable)
    counterfactual = template["transform"](episode)
    counterfactual["template_id"] = template["id"]
    counterfactual["template_label"] = template["label"]
    counterfactual["source_episode_id"] = episode["id"]
    counterfactual["source_task"] = episode["task"]
    counterfactual["original_outcome"] = outcome

    return counterfactual


def reason_about_counterfactual(counterfactual):
    """Run a counterfactual through the reasoning chain framework.

    Creates a 3-step reasoning chain:
    1. Scenario setup (what changed)
    2. Consequence analysis (what would happen)
    3. Insight extraction (what we learn)

    Returns the insight string.
    """
    scenario = counterfactual["scenario"]
    question = counterfactual["question"]
    original = counterfactual["original_outcome"]
    flipped = counterfactual["flipped_outcome"]
    task = counterfactual["source_task"]

    # Step 1: Create the reasoning chain
    chain_id = create_chain(
        title=f"Dream: {counterfactual['template_label']}",
        initial_thought=f"Scenario: {scenario}. Original outcome was '{original}'. "
                        f"Exploring counterfactual outcome '{flipped}'."
    )

    # Step 2: Analyze consequences
    # Pull related memories to ground the reasoning
    related = brain.recall(task, n=3, collections=["clarvis-learnings", "clarvis-episodes"])
    context_snippets = [r["document"][:100] for r in related[:3]]
    context_str = "; ".join(context_snippets) if context_snippets else "no related context found"

    add_step(
        chain_id,
        thought=f"Consequence analysis: {question} "
                f"Related context: [{context_str}]. "
                f"If outcome were '{flipped}', the impact would depend on "
                f"downstream dependencies and whether error detection exists.",
        previous_outcome="scenario_established"
    )

    # Step 3: Extract insight
    insight = _synthesize_insight(counterfactual, context_snippets)

    complete_step(chain_id, outcome=f"Dream insight: {insight}")

    return chain_id, insight


def _synthesize_insight(counterfactual, context_snippets):
    """Synthesize a concrete insight from the counterfactual analysis.

    This is rule-based — no LLM call needed. Insights come from
    pattern-matching the counterfactual type against known risk categories.
    """
    template_id = counterfactual["template_id"]
    task = counterfactual["source_task"]
    task_lower = task.lower()

    # Extract domain keywords from the task
    domains_found = []
    domain_map = {
        "memory": ["brain", "memory", "recall", "store", "retrieval", "episodic"],
        "cron": ["cron", "schedule", "heartbeat", "autonomous", "evening", "morning"],
        "metrics": ["phi", "capability", "score", "benchmark", "metric", "assessment"],
        "reasoning": ["reasoning", "chain", "thought", "analysis", "synthesis"],
        "code": ["script", "function", "ast", "import", "module", "code"],
        "data": ["json", "file", "database", "chromadb", "collection", "data"],
    }
    for domain, keywords in domain_map.items():
        if any(kw in task_lower for kw in keywords):
            domains_found.append(domain)

    domain_str = ", ".join(domains_found) if domains_found else "general"

    # Template-specific insight generation
    insights_by_template = {
        "failure_flip": (
            f"Vulnerability identified in {domain_str}: if '{task[:60]}' had failed, "
            f"the system lacks a fallback path. Consider adding error recovery or "
            f"graceful degradation for this operation."
        ),
        "success_flip": (
            f"Blocked capability in {domain_str}: the failure in '{task[:60]}' may be "
            f"hiding a simpler fix. Re-examine the error conditions — the path to "
            f"success might require only removing one blocker."
        ),
        "cascading_failure": (
            f"Dependency risk in {domain_str}: '{task[:60]}' could cascade to downstream "
            f"systems. Map the dependency chain and add isolation boundaries or health "
            f"checks between components."
        ),
        "slow_path": (
            f"Performance fragility in {domain_str}: '{task[:60]}' could degrade under "
            f"load. The current timing assumes normal conditions — add timeout guards "
            f"and consider what happens at 10x data volume."
        ),
        "wrong_approach": (
            f"Approach fragility in {domain_str}: the method used for '{task[:60]}' works "
            f"now but may be the wrong abstraction. Consider if a simpler or more robust "
            f"alternative exists that wouldn't require this specific approach."
        ),
        "data_corruption": (
            f"Silent failure risk in {domain_str}: '{task[:60]}' has no validation on "
            f"input data. Corrupted or malformed data could propagate undetected. "
            f"Add input checksums or schema validation at the boundary."
        ),
    }

    return insights_by_template.get(
        template_id,
        f"General risk in {domain_str}: '{task[:60]}' should be stress-tested "
        f"against alternative outcomes."
    )


def dream(n_episodes=10):
    """Run a full dream cycle.

    1. Select episodes
    2. Generate counterfactuals
    3. Reason about each
    4. Store insights

    Returns summary dict.
    """
    print(f"[dream] Starting counterfactual dream cycle ({n_episodes} episodes)...")

    # 1. Select episodes
    episodes = select_episodes(n_episodes)
    if not episodes:
        print("[dream] No episodes available to dream about.")
        return {"error": "no_episodes", "insights": 0}

    print(f"[dream] Selected {len(episodes)} episodes for dreaming")

    log = _load_dream_log()
    session_id = f"dream_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    session_insights = []
    chains_created = []

    # Compute surprise scores for logging
    surprise_scores = {ep["id"]: compute_surprise(ep, episodes) for ep in episodes}

    # 2-3. For each episode, generate counterfactual and reason about it
    for i, episode in enumerate(episodes):
        ep_surprise = surprise_scores.get(episode["id"], 0.0)
        print(f"[dream] [{i+1}/{len(episodes)}] Dreaming about: {episode['task'][:60]}... (surprise={ep_surprise:.3f})")

        # Generate counterfactual
        cf = generate_counterfactual(episode)
        print(f"  Template: {cf['template_label']}")

        # Reason through the counterfactual
        chain_id, insight = reason_about_counterfactual(cf)
        chains_created.append(chain_id)

        # 4. Store dream insight — dedup by episode+template to prevent reruns
        #    from creating duplicate entries.
        dream_text = f"[DREAM INSIGHT] {insight}"
        dream_dedup_id = f"dream_{episode['id']}_{cf['template_id']}"
        dream_memory_id = brain.store(
            dream_text,
            collection="clarvis-learnings",
            importance=0.5,  # Must be >=0.3 to surface in preflight knowledge recall
            tags=["dream", "counterfactual", cf["template_id"], session_id],
            source="dream_engine",
            memory_id=dream_dedup_id,
        )

        dream_entry = {
            "episode_id": episode["id"],
            "episode_task": episode["task"][:100],
            "template": cf["template_id"],
            "counterfactual": cf["scenario"][:150],
            "insight": insight[:200],
            "surprise_score": ep_surprise,
            "chain_id": chain_id,
            "memory_id": dream_memory_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        session_insights.append(dream_entry)
        log["dreams"].append(dream_entry)

        print(f"  Insight: {insight[:80]}...")

    # Update log
    log["total_insights"] += len(session_insights)
    log["sessions"] += 1
    _save_dream_log(log)

    # Store session summary in brain
    summary = (
        f"Dream session {session_id}: {len(session_insights)} counterfactual insights "
        f"generated from {len(episodes)} episodes. Templates used: "
        f"{', '.join(set(d['template'] for d in session_insights))}."
    )
    brain.store(
        summary,
        collection="clarvis-learnings",
        importance=0.4,
        tags=["dream_session", session_id],
        source="dream_engine",
        memory_id=f"dream_session_{session_id}",
    )

    print("\n[dream] Dream cycle complete:")
    print(f"  Episodes dreamed: {len(episodes)}")
    print(f"  Insights generated: {len(session_insights)}")
    print(f"  Reasoning chains: {len(chains_created)}")
    print(f"  Total lifetime dreams: {log['total_insights']}")

    return {
        "session_id": session_id,
        "episodes_dreamed": len(episodes),
        "insights_generated": len(session_insights),
        "chains_created": chains_created,
        "insights": [d["insight"][:100] for d in session_insights],
    }


def rethink_memory(n_episodes=20):
    """Letta-inspired rethink_memory: consolidate raw episodes into learned context.

    Unlike counterfactual dreaming (which stress-tests assumptions), rethink_memory
    extracts positive knowledge — generalizing from successful episodes into
    reusable semantic learnings.

    Inspired by:
    - Letta Sleep-time Compute (arXiv 2504.13171): rethink_memory transforms
      raw context → learned context during offline phases
    - LightMem (arXiv 2510.18866): offline consolidation with topic-aware grouping
    - MemAgent (ICLR 2026): fixed-size overwrite strategy

    Args:
        n_episodes: Number of recent episodes to process

    Returns:
        dict with rethink stats
    """
    print(f"[rethink] Starting rethink_memory cycle ({n_episodes} episodes)...")

    episodes = episodic.episodes
    if not episodes:
        print("[rethink] No episodes available.")
        return {"error": "no_episodes", "learnings": 0}

    # Take most recent episodes (recency-biased window)
    recent = episodes[-n_episodes:]
    successful = [ep for ep in recent if ep.get("outcome") == "success"]

    if len(successful) < 3:
        print(f"[rethink] Only {len(successful)} successful episodes. Need 3+.")
        return {"learnings": 0, "episodes_checked": len(recent)}

    print(f"[rethink] Processing {len(successful)} successful episodes from last {len(recent)}")

    # Group by task type (first word of task)
    groups = {}
    for ep in successful:
        task = ep.get("task", "")
        # Extract category from task prefix patterns
        category = "general"
        for prefix in ["[RESEARCH", "[AUTONOMY", "[SELF-MODEL", "[CRAWL",
                        "[SEMANTIC", "[RECONSOLIDATION", "Build", "Fix",
                        "Implement", "Research", "Add", "Update"]:
            if task.startswith(prefix):
                category = prefix.strip("[").rstrip("]").lower()
                break
        groups.setdefault(category, []).append(ep)

    learnings = []
    log = _load_dream_log()

    for category, eps in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(eps) < 2:
            continue
        if len(learnings) >= 5:
            break

        # Synthesize a generalized learning from the group
        tasks_summary = "; ".join(ep.get("task", "")[:40] for ep in eps[:5])
        durations = [ep.get("duration_s", 0) for ep in eps if ep.get("duration_s")]
        avg_dur = sum(durations) / len(durations) if durations else 0
        confidences = [ep.get("confidence", 0) for ep in eps if ep.get("confidence")]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        learning_text = (
            f"[RETHINK] Learned pattern in '{category}' ({len(eps)} episodes): "
            f"Tasks like [{tasks_summary}] succeed reliably "
            f"(avg {avg_dur:.0f}s, conf {avg_conf:.2f}). "
            f"This capability is stable and can be built upon."
        )

        # Check for duplicate in brain
        existing = brain.recall(learning_text, n=2, collections=["clarvis-learnings"])
        if existing and existing[0].get("distance", 1.0) < 0.5:
            print(f"  [rethink] '{category}' already has similar learning. Skip.")
            continue

        memory_id = brain.store(
            learning_text,
            collection="clarvis-learnings",
            importance=0.55,
            tags=["rethink", f"category:{category}", "dream-rethink"],
            source="dream_engine_rethink"
        )

        learnings.append({
            "category": category,
            "episode_count": len(eps),
            "learning": learning_text[:120],
            "memory_id": memory_id,
        })

        log["dreams"].append({
            "episode_id": f"rethink_{category}",
            "episode_task": f"rethink: {category}",
            "template": "rethink_memory",
            "counterfactual": "",
            "insight": learning_text[:200],
            "chain_id": None,
            "memory_id": memory_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        print(f"  [rethink] '{category}': {len(eps)} eps → learned pattern stored")

    log["total_insights"] += len(learnings)
    _save_dream_log(log)

    print(f"\n[rethink] Complete: {len(learnings)} learned patterns extracted")
    return {
        "episodes_checked": len(recent),
        "successful_episodes": len(successful),
        "learnings": len(learnings),
        "details": learnings,
    }


def get_stats():
    """Get dream engine statistics."""
    log = _load_dream_log()
    dreams = log.get("dreams", [])

    if not dreams:
        return {"sessions": 0, "total_dreams": 0}

    template_counts = {}
    for d in dreams:
        t = d.get("template", "unknown")
        template_counts[t] = template_counts.get(t, 0) + 1

    return {
        "sessions": log.get("sessions", 0),
        "total_dreams": len(dreams),
        "total_insights": log.get("total_insights", 0),
        "template_distribution": template_counts,
        "oldest_dream": dreams[0].get("timestamp", "")[:10] if dreams else None,
        "newest_dream": dreams[-1].get("timestamp", "")[:10] if dreams else None,
    }


def list_insights(n=10):
    """List recent dream insights from brain."""
    results = brain.recall(
        "dream counterfactual insight",
        n=n,
        collections=["clarvis-learnings"]
    )
    insights = []
    for r in results:
        meta = r.get("metadata", {})
        tags_raw = meta.get("tags", "[]")
        try:
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else (tags_raw or [])
        except (json.JSONDecodeError, TypeError):
            tags = []
        if "dream" in tags:
            insights.append({
                "text": r["document"][:120],
                "importance": meta.get("importance", 0),
                "created": meta.get("created_at", "")[:10],
                "id": r.get("id", ""),
            })
    return insights


# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: dream_engine.py <dream|rethink|sleep|stats|insights> [n_episodes]")
        print("Commands:")
        print("  dream [n]    Run counterfactual dream cycle (default: 10 episodes)")
        print("  rethink [n]  Rethink memory: consolidate episodes into learned patterns")
        print("  sleep [n]    Full sleep cycle: dream + rethink (default: 10)")
        print("  stats        Show dream history statistics")
        print("  insights     List stored dream insights")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "dream":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        result = dream(n)
        print(f"\n{json.dumps(result, indent=2)}")

    elif cmd == "rethink":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        result = rethink_memory(n)
        print(f"\n{json.dumps(result, indent=2)}")

    elif cmd == "sleep":
        # Full sleep cycle: counterfactual dreaming + rethink memory
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        print("=== SLEEP CYCLE: Phase 1 — Counterfactual Dreaming ===")
        dream_result = dream(n)
        print("\n=== SLEEP CYCLE: Phase 2 — Rethink Memory ===")
        rethink_result = rethink_memory(n * 2)
        print("\n=== SLEEP CYCLE COMPLETE ===")
        print(f"  Dreams: {dream_result.get('insights_generated', 0)} insights")
        print(f"  Rethink: {rethink_result.get('learnings', 0)} learned patterns")

    elif cmd == "stats":
        stats = get_stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "insights":
        insights = list_insights()
        if not insights:
            print("No dream insights found yet.")
        else:
            for ins in insights:
                print(f"  [{ins['created']}] (imp={ins['importance']:.2f}) {ins['text']}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
