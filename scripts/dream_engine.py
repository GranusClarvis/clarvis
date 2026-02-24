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
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from brain import brain
from episodic_memory import episodic
from reasoning_chains import create_chain, add_step, complete_step

DREAM_LOG = Path("/home/agent/.openclaw/workspace/data/dream_log.json")
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


def select_episodes(n=10):
    """Select n random episodes for dreaming, biased toward recent and high-valence."""
    episodes = episodic.episodes
    if not episodes:
        return []

    # Weight selection: recent episodes and high-valence episodes are more likely
    weights = []
    for i, ep in enumerate(episodes):
        recency = (i + 1) / len(episodes)  # 0..1, higher for recent
        valence = ep.get("valence", 0.5)
        weight = recency * 0.6 + valence * 0.4
        weights.append(weight)

    # Sample without replacement (or all if fewer than n)
    k = min(n, len(episodes))
    selected = random.choices(episodes, weights=weights, k=k)

    # Deduplicate by episode id
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

    # 2-3. For each episode, generate counterfactual and reason about it
    for i, episode in enumerate(episodes):
        print(f"[dream] [{i+1}/{len(episodes)}] Dreaming about: {episode['task'][:60]}...")

        # Generate counterfactual
        cf = generate_counterfactual(episode)
        print(f"  Template: {cf['template_label']}")

        # Reason through the counterfactual
        chain_id, insight = reason_about_counterfactual(cf)
        chains_created.append(chain_id)

        # 4. Store dream insight (0.5 — discoverable by preflight knowledge recall)
        dream_memory_id = brain.store(
            f"[DREAM INSIGHT] {insight}",
            collection="clarvis-learnings",
            importance=0.5,  # Must be >=0.3 to surface in preflight knowledge recall
            tags=["dream", "counterfactual", cf["template_id"], session_id],
            source="dream_engine"
        )

        dream_entry = {
            "episode_id": episode["id"],
            "episode_task": episode["task"][:100],
            "template": cf["template_id"],
            "counterfactual": cf["scenario"][:150],
            "insight": insight[:200],
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
        source="dream_engine"
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
        print("Usage: dream_engine.py <dream|stats|insights> [n_episodes]")
        print("Commands:")
        print("  dream [n]    Run counterfactual dream cycle (default: 10 episodes)")
        print("  stats        Show dream history statistics")
        print("  insights     List stored dream insights")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "dream":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        result = dream(n)
        print(f"\n{json.dumps(result, indent=2)}")

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
