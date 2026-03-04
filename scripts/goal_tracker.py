#!/usr/bin/env python3
"""
Goal Progress Tracker — closes the loop between "what we want" and "what we do".

Reads clarvis-goals collection, compares each goal's target metrics against
current capability scores from self_model.py, identifies stalled goals
(no progress in 24h), and auto-generates targeted QUEUE.md tasks.

Usage:
    python3 goal_tracker.py              # Full analysis + task generation
    python3 goal_tracker.py check        # Report only (no QUEUE.md writes)
    python3 goal_tracker.py update-goals # Update goal progress from capability scores
"""
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain
from self_model import assess_all_capabilities

QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
TRACKER_STATE_FILE = "/home/agent/.openclaw/workspace/data/goal_tracker_state.json"
STALL_HOURS = 24

# Map goals to capability domains they depend on.
# A goal can map to multiple domains; progress is derived from the avg score.
GOAL_DOMAIN_MAP = {
    "ClarvisDB": ["memory_system"],
    "AGI/consciousness": ["consciousness_metrics", "self_reflection", "reasoning_chains"],
    "Session Continuity": ["memory_system", "autonomous_execution"],
    "Heartbeat Efficiency": ["autonomous_execution"],
    "Self-Reflection": ["self_reflection"],
    "North Star": ["memory_system", "autonomous_execution", "code_generation",
                    "self_reflection", "reasoning_chains", "learning_feedback",
                    "consciousness_metrics"],
    "Feedback Loop": ["learning_feedback"],
    "Neural Memory": ["memory_system", "consciousness_metrics"],
    "Confidence": ["learning_feedback", "self_reflection"],
    "Consciousness": ["consciousness_metrics", "self_reflection"],
    "Self Model": ["self_reflection"],
    "Reasoning Chains": ["reasoning_chains"],
}

# For each goal, define what a concrete next step looks like given low scores
# in the mapped domains. Format: domain -> task template
GOAL_TASK_TEMPLATES = {
    "ClarvisDB": {
        "memory_system": "Improve ClarvisDB retrieval quality — avg distance too high or hit rate low. Run retrieval_benchmark.py, tune smart_recall() thresholds, consider re-embedding sparse collections.",
    },
    "AGI/consciousness": {
        "consciousness_metrics": "Advance consciousness metrics toward AGI goal — improve Phi by increasing cross-collection connectivity. Run bulk_cross_link, enrich sparse collections.",
        "self_reflection": "Deepen self-reflection for AGI goal — improve meta-thought frequency and prediction calibration.",
        "reasoning_chains": "Strengthen reasoning chains for AGI goal — ensure chains record outcomes, increase chain depth and quality.",
    },
    "Session Continuity": {
        "memory_system": "Improve session continuity — strengthen memory persistence. Verify working_memory load_from_disk() runs on boot, check session_hook.py save triggers.",
        "autonomous_execution": "Improve session continuity — ensure heartbeat preserves context across restarts. Verify working memory survives cron cycles.",
    },
    "Heartbeat Efficiency": {
        "autonomous_execution": "Optimize heartbeat efficiency — improve task success rate and velocity. Analyze autonomous.log for common failure patterns, fix top error class.",
    },
    "Self-Reflection": {
        "self_reflection": "Advance self-reflection — record more meta-thoughts, improve calibration Brier score, run phi_metric more frequently.",
    },
    "North Star": {
        "_any": "Progress toward North Star — identify and fix lowest capability score. Run full daily_update() and address the weakest domain.",
    },
    "Feedback Loop": {
        "learning_feedback": "Close feedback loops — resolve pending predictions, increase procedural memory usage, verify evolution_loop captures and acts on failures.",
    },
    "Neural Memory": {
        "memory_system": "Enhance neural memory — improve graph density (edges/memory ratio). Run bulk_cross_link, ensure auto_link fires on every store().",
        "consciousness_metrics": "Enhance neural memory integration — increase Phi by building more cross-collection semantic bridges.",
    },
    "Confidence": {
        "learning_feedback": "Improve confidence calibration — resolve unresolved predictions, lower Brier score, verify dynamic_confidence() adjusts thresholds.",
        "self_reflection": "Improve confidence self-awareness — review calibration curve, identify overconfident/underconfident domains.",
    },
    "Consciousness": {
        "consciousness_metrics": "Advance consciousness implementation — improve Phi, increase attention spotlight utilization, ensure working memory has active items.",
        "self_reflection": "Advance consciousness self-model — record meta-thoughts about consciousness progress, update awareness level based on evidence.",
    },
    "Self Model": {
        "self_reflection": "Improve self-model — run daily_update() to refresh capability scores, add trajectory events for significant changes, fix any ceiling effects in assessors.",
    },
    "Reasoning Chains": {
        "reasoning_chains": "Improve reasoning chains — ensure reasoning_chain_hook.py close() records real outcomes, increase chain quality (steps + outcomes). Target: >50% chains with outcomes.",
    },
}


def load_tracker_state():
    """Load previous tracker state for dedup."""
    p = Path(TRACKER_STATE_FILE)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {"last_run": None, "tasks_generated": []}


def save_tracker_state(state):
    """Save tracker state."""
    Path(TRACKER_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_goals_with_status():
    """Get all goals with stall detection and capability mapping.

    Returns list of dicts:
        goal_name, progress, updated, stalled, hours_since_update,
        mapped_domains, domain_scores, avg_domain_score, gap
    """
    goals = brain.get_goals()
    capabilities = assess_all_capabilities()
    now = datetime.now(timezone.utc)
    results = []

    for g in goals:
        meta = g.get("metadata", {})
        goal_name = meta.get("goal", g["id"])
        progress = int(meta.get("progress", 0))
        updated_str = meta.get("updated", "")

        # Parse last update time
        hours_since = None
        stalled = False
        if updated_str:
            try:
                updated_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                if updated_dt.tzinfo is None:
                    updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                hours_since = (now - updated_dt).total_seconds() / 3600
                stalled = hours_since >= STALL_HOURS
            except (ValueError, TypeError):
                stalled = True  # Can't parse = assume stalled
                hours_since = None

        # Map to capability domains
        mapped_domains = GOAL_DOMAIN_MAP.get(goal_name, [])
        domain_scores = {}
        for domain in mapped_domains:
            if domain in capabilities:
                domain_scores[domain] = capabilities[domain]["score"]

        # Calculate average domain score (0-1) as proxy for actual progress
        avg_score = 0.0
        if domain_scores:
            avg_score = sum(domain_scores.values()) / len(domain_scores)

        # Gap: how far the goal is from where capability scores suggest it should be
        # Convert avg_score (0-1) to progress scale (0-100)
        implied_progress = int(avg_score * 100)
        gap = implied_progress - progress  # Positive = goal should be updated up

        results.append({
            "goal_name": goal_name,
            "progress": progress,
            "updated": updated_str,
            "stalled": stalled,
            "hours_since_update": round(hours_since, 1) if hours_since else None,
            "mapped_domains": mapped_domains,
            "domain_scores": domain_scores,
            "avg_domain_score": round(avg_score, 2),
            "implied_progress": implied_progress,
            "gap": gap,
        })

    return results


def find_weakest_domains(goal_status):
    """Across all stalled goals, find which domains are blocking progress most."""
    domain_block_count = {}
    for g in goal_status:
        if not g["stalled"]:
            continue
        for domain, score in g["domain_scores"].items():
            if score < 0.6:  # Below 60% = blocking
                domain_block_count[domain] = domain_block_count.get(domain, 0) + 1
    return sorted(domain_block_count.items(), key=lambda x: -x[1])


def generate_tasks(goal_status, dry_run=False):
    """Generate concrete QUEUE.md tasks for stalled goals with low domain scores.

    Returns list of task strings generated.
    """
    state = load_tracker_state()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tasks = []

    for g in goal_status:
        goal_name = g["goal_name"]

        # Skip goals at 90%+ progress (basically done)
        if g["progress"] >= 90:
            continue

        # Only generate tasks for stalled goals OR goals with very low domain scores
        if not g["stalled"] and g["avg_domain_score"] >= 0.5:
            continue

        # Find the weakest domain for this goal
        templates = GOAL_TASK_TEMPLATES.get(goal_name, {})
        weakest_domain = None
        weakest_score = 1.0

        for domain, score in g["domain_scores"].items():
            if score < weakest_score:
                weakest_score = score
                weakest_domain = domain

        # Generate a task based on the weakest domain
        task_text = None
        if weakest_domain and weakest_domain in templates:
            task_text = templates[weakest_domain]
        elif "_any" in templates:
            task_text = templates["_any"]
        elif weakest_domain:
            # Generic fallback
            task_text = (
                f"Improve {goal_name} — weakest domain '{weakest_domain}' "
                f"at {weakest_score:.2f}. Run targeted assessment and fix the "
                f"lowest-scoring evidence item."
            )

        if task_text:
            # Add context
            full_task = (
                f"[GOAL-TRACKER {today}] {task_text} "
                f"(Goal: {goal_name}, progress={g['progress']}%, "
                f"stalled={g['hours_since_update']:.0f}h, "
                f"domain={weakest_domain}={weakest_score:.2f})"
            )

            # Dedup: don't regenerate the same task
            task_key = f"{goal_name}:{weakest_domain}"
            if task_key in state.get("tasks_generated", []):
                continue

            tasks.append(full_task)
            state.setdefault("tasks_generated", []).append(task_key)

    if not dry_run and tasks:
        inject_tasks(tasks)
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        # Reset generated tasks list daily so tasks can regenerate the next day
        if state.get("last_reset_date") != today:
            state["tasks_generated"] = [
                f"{g['goal_name']}:{d}"
                for g in goal_status
                for d in g["domain_scores"]
                if g["domain_scores"][d] < 0.4  # Only keep truly stuck ones
            ]
            state["last_reset_date"] = today
        save_tracker_state(state)

    return tasks


def inject_tasks(tasks):
    """Inject tasks into QUEUE.md under P0 section via shared queue_writer."""
    if not tasks:
        return
    try:
        from queue_writer import add_tasks
        added = add_tasks(tasks, priority="P0", source="goal-tracker")
        if added:
            print(f"  Injected {len(added)} goal-tracker tasks into QUEUE.md")
    except ImportError:
        # Fallback: direct write
        queue_path = Path(QUEUE_FILE)
        if not queue_path.exists():
            return
        content = queue_path.read_text()
        lines = content.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if "## P0" in line:
                insert_idx = i + 1
                break
        if insert_idx is None:
            return
        while insert_idx < len(lines) and (lines[insert_idx].startswith("###") or lines[insert_idx].strip() == ""):
            insert_idx += 1
        for task in reversed(tasks):
            lines.insert(insert_idx, f"- [ ] {task}")
        queue_path.write_text("\n".join(lines))
        print(f"  Injected {len(tasks)} goal-tracker tasks into QUEUE.md (legacy)")


def update_goal_progress(goal_status):
    """Update goal progress in brain based on capability scores.

    Only updates goals where implied progress is significantly different
    from recorded progress (gap >= 10 or gap <= -10).
    """
    updated = 0
    for g in goal_status:
        gap = g["gap"]
        if abs(gap) < 10:
            continue  # Not significant enough

        goal_name = g["goal_name"]
        new_progress = max(0, min(100, g["implied_progress"]))

        # Don't decrease progress below what was manually set (ratchet up only)
        if new_progress < g["progress"]:
            continue

        brain.set_goal(goal_name, new_progress)
        updated += 1
        print(f"  Updated {goal_name}: {g['progress']}% -> {new_progress}% (domain avg={g['avg_domain_score']:.2f})")

    return updated


def run_tracker(dry_run=False):
    """Main entry point: analyze goals, detect stalls, generate tasks."""
    print("=== Goal Progress Tracker ===")
    print()

    goal_status = get_goals_with_status()

    # Report
    stalled_count = 0
    for g in goal_status:
        status_icon = "STALLED" if g["stalled"] else "active"
        if g["stalled"]:
            stalled_count += 1
        hours_str = f"{g['hours_since_update']:.0f}h ago" if g['hours_since_update'] else "unknown"

        print(f"  [{status_icon:7s}] {g['goal_name']}: {g['progress']}% "
              f"(domains avg={g['avg_domain_score']:.2f}, implied={g['implied_progress']}%, "
              f"updated {hours_str})")

        if g["domain_scores"]:
            low_domains = [(d, s) for d, s in g["domain_scores"].items() if s < 0.5]
            if low_domains:
                for d, s in low_domains:
                    print(f"           ^ weak: {d}={s:.2f}")

    print(f"\n  Total goals: {len(goal_status)}, Stalled: {stalled_count}")

    # Find cross-goal blockers
    blockers = find_weakest_domains(goal_status)
    if blockers:
        print("\n  Cross-goal blockers (domains blocking most stalled goals):")
        for domain, count in blockers[:3]:
            print(f"    {domain}: blocking {count} goal(s)")

    # Generate tasks
    tasks = generate_tasks(goal_status, dry_run=dry_run)
    if tasks:
        print(f"\n  Generated {len(tasks)} new tasks:")
        for t in tasks:
            print(f"    -> {t[:120]}...")
    else:
        print("\n  No new tasks needed (all goals progressing or already tracked)")

    return {
        "goals": goal_status,
        "stalled_count": stalled_count,
        "blockers": blockers,
        "tasks_generated": tasks,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "check":
            run_tracker(dry_run=True)
        elif cmd == "update-goals":
            goal_status = get_goals_with_status()
            updated = update_goal_progress(goal_status)
            print(f"Updated {updated} goal(s)")
        else:
            print("Usage: goal_tracker.py [check|update-goals]")
            print("  (no args) = full analysis + inject tasks into QUEUE.md")
            print("  check     = report only, no writes")
            print("  update-goals = update goal progress from capability scores")
    else:
        run_tracker(dry_run=False)
