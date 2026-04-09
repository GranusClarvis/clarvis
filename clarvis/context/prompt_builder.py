"""Shared prompt builder for all Claude Code spawning scripts.

Builds structured prompts with deep contextual intelligence from the brain's
vector DB, semantic graph, synaptic network, episodic memory, and attention
system. Every Claude Code spawn — whether from cron, ACP, or manual — gets
the richest possible context for the task at hand.

Architecture:
    1. brain_introspect.introspect_for_task() — domain detection, targeted
       vector recall across collections, graph traversal, goal alignment,
       identity/preference constraints, infrastructure awareness
    2. EpisodicMemory — recent episodes with causal chains for failures
    3. SynapticMemory.spread() — neural spreading activation from recalled IDs
    4. AttentionSpotlight — live working memory spotlight + task-relevant boost
    5. Somatic markers — failure avoidance signals
    6. context_compressor — compressed queue for pending task awareness

Usage:
    from clarvis.context.prompt_builder import build_prompt, get_context_brief
    prompt = build_prompt(task="Fix retrieval", role="evolution", tier="full")
"""

import json
import os
import time

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
SOMATIC_FILE = os.path.join(WORKSPACE, "data/somatic_markers.json")


# ---------------------------------------------------------------------------
# Section builders — each queries a different cognitive subsystem
# ---------------------------------------------------------------------------

def _introspect_for_task(task, tier):
    """Deep brain introspection: vector search + graph traversal + goal alignment."""
    if not task:
        return ""
    try:
        from brain_introspect import introspect_for_task, format_introspection_for_prompt
        budget = "minimal" if tier == "minimal" else tier
        introspection = introspect_for_task(task, budget=budget)
        formatted = format_introspection_for_prompt(introspection, budget=budget)
        return formatted or ""
    except Exception:
        return ""


def _get_brain_goals(limit=5):
    """Get top goals by progress from brain — uses canonical summary."""
    try:
        from clarvis.brain import brain
        summary = brain.get_goals_summary(top_n=limit)
        if not summary:
            return ""
        lines = []
        for g in summary:
            lines.append(f"  - {g['name']}: {g['progress']}%")
        return "ACTIVE GOALS:\n" + "\n".join(lines)
    except Exception:
        return ""


def _get_brain_context():
    """Get current working context from brain."""
    try:
        from clarvis.brain import brain
        ctx = brain.get_context()
        if ctx and len(ctx.strip()) > 10:
            return f"WORKING CONTEXT: {ctx.strip()[:200]}"
        return ""
    except Exception:
        return ""


def _get_episodic_recall(task=None, limit=3):
    """Get recent episodes via EpisodicMemory class (not flat file)."""
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        if not em.episodes:
            return ""

        lines = []

        # Recent episodes (last N)
        recent = em.episodes[-limit:]
        for ep in reversed(recent):
            task_text = ep.get("task", ep.get("context", "?"))[:60]
            outcome = ep.get("outcome", "?")
            valence = ep.get("valence", 0)
            lines.append(f"  - [{outcome} v={valence:.1f}] {task_text}")

        # For recent failures, include causal chain
        recent_failures = [
            ep for ep in em.episodes[-10:]
            if ep.get("outcome") == "failure"
        ]
        if recent_failures:
            lines.append("  Failure causal chains:")
            for fail in recent_failures[-2:]:  # last 2 failures
                fail_id = fail.get("id", "")
                task_text = fail.get("task", fail.get("context", "?"))[:50]
                lines.append(f"    FAIL: {task_text}")
                # Get causes
                try:
                    causes = em.causes_of(fail_id)
                    for link, cause_ep in causes[:2]:
                        rel = link.get("relationship", "?")
                        cause_text = cause_ep.get("task", cause_ep.get("context", "?"))[:50]
                        lines.append(f"      <- {rel}: {cause_text}")
                except Exception:
                    pass

        return "EPISODIC MEMORY:\n" + "\n".join(lines)
    except Exception:
        return ""


def _get_synaptic_associations(task, recalled_ids=None):
    """Neural spreading activation via synaptic network."""
    if not recalled_ids:
        try:
            from clarvis.brain import brain as _brain_syn
            _results = _brain_syn.recall(task, n=5, caller="synaptic_seeds")
            recalled_ids = [r.get("id", "") for r in _results if r.get("id")]
        except Exception:
            pass
    if not recalled_ids:
        return ""
    try:
        from clarvis.memory.synaptic_memory import SynapticMemory
        syn = SynapticMemory()
        if syn.stats().get("total_synapses", 0) == 0:
            return ""

        spread_results = syn.spread(recalled_ids[:5], n=5, min_weight=0.1)
        if not spread_results:
            return ""

        from clarvis.brain import brain
        lines = []
        for mem_id, activation in spread_results:
            if mem_id in recalled_ids:
                continue
            try:
                for col_name, col in brain.collections.items():
                    try:
                        got = col.get(ids=[mem_id])
                        if got["ids"] and got["documents"] and got["documents"][0]:
                            doc = got["documents"][0][:100]
                            if not doc.startswith("Connection between "):
                                lines.append(f"  - [syn={activation:.2f}] {doc}")
                            break
                    except Exception:
                        continue
            except Exception:
                continue

        if not lines:
            return ""
        return "SYNAPTIC ASSOCIATIONS (neural spread):\n" + "\n".join(lines[:5])
    except Exception:
        return ""


def _get_attention_spotlight(task=None, limit=5):
    """Get live attention spotlight + task-relevant boosting."""
    try:
        from clarvis.cognition.attention import AttentionSpotlight
        attn = AttentionSpotlight()

        if task:
            boosted = attn.spreading_activation(task, n=limit)
            if boosted:
                lines = []
                for item in boosted[:limit]:
                    content = item.get("content", "?")[:80]
                    salience = item.get("salience", item.get("combined_score", 0))
                    lines.append(f"  - [{salience:.2f}] {content}")
                return "ATTENTION (task-boosted):\n" + "\n".join(lines)

        summary = attn.focus_summary()
        if summary and "empty" not in summary:
            return f"ATTENTION:\n  {summary}"
        return ""
    except Exception:
        return ""


def _get_failure_patterns(task=None, limit=3):
    """Get failure avoidance signals from somatic markers + brain search."""
    lines = []

    try:
        if os.path.exists(SOMATIC_FILE):
            with open(SOMATIC_FILE) as f:
                markers = json.load(f)
            avoidance = [
                m for m in markers
                if m.get("signal") == "avoidance" and m.get("strength", 0) > 0.3
            ]
            avoidance.sort(key=lambda m: m.get("strength", 0), reverse=True)
            for m in avoidance[:limit]:
                snippet = m.get("task_snippet", "?")[:60]
                emotion = m.get("emotion", "?")
                lines.append(f"  - AVOID: {snippet} ({emotion})")
    except Exception:
        pass

    if task:
        try:
            from clarvis.brain import brain, LEARNINGS, EPISODES
            failure_memories = brain.recall(
                f"failure lesson: {task}",
                collections=[LEARNINGS, EPISODES],
                n=2,
                min_importance=0.3,
                caller="prompt_builder_failures",
            )
            for mem in failure_memories:
                doc = mem.get("document", "")
                if "fail" in doc.lower() or "error" in doc.lower() or "lesson" in doc.lower():
                    lines.append(f"  - LESSON: {doc[:80]}")
        except Exception:
            pass

    if not lines:
        return ""
    return "FAILURE PATTERNS:\n" + "\n".join(lines[:limit + 2])


def _get_capability_scores():
    """Get current capability scores (weakest-first for self-awareness)."""
    try:
        history_file = os.path.join(WORKSPACE, "data/capability_history.json")
        if not os.path.exists(history_file):
            return ""
        with open(history_file) as f:
            history = json.load(f)
        if not history:
            return ""
        if isinstance(history, dict) and "snapshots" in history:
            history = history["snapshots"]
        latest = history[-1] if isinstance(history, list) else history
        scores = latest.get("scores", latest.get("domains", {}))
        if not scores:
            return ""
        lines = []
        for domain, score in sorted(scores.items(), key=lambda x: x[1]):
            lines.append(f"  - {domain}: {score:.2f}")
        return "CAPABILITY SCORES (weakest first):\n" + "\n".join(lines)
    except Exception:
        return ""


def _get_compressed_queue(tier):
    """Get compressed pending tasks from QUEUE.md."""
    try:
        from clarvis.context.compressor import compress_queue
        queue = compress_queue()
        if not queue or len(queue) <= 20:
            return ""
        max_len = 600 if tier == "standard" else 1200
        if len(queue) > max_len:
            queue = queue[:max_len] + "\n  ... (truncated)"
        return queue
    except Exception:
        return ""


def _extract_recalled_ids(introspection_text):
    """Extract memory IDs from introspection text for synaptic spreading."""
    return []


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def get_context_brief(tier="standard", task=None):
    """Build a context brief for Claude Code prompts using the full brain.

    Uses generate_tiered_brief() as the canonical core (primacy/recency
    optimized, task-class-aware budgets) and enriches with extras that
    the tiered brief doesn't cover: brain introspection, goals, synaptic
    spreading, attention spotlight, capability scores, and compressed queue.

    Tiers:
        minimal  — Goals + working context only (~200 tokens)
        standard — Tiered brief + introspection + goals + queue (~1K tokens)
        full     — Everything: tiered brief + synaptic + attention + caps (~2K tokens)

    Args:
        tier: Context depth level.
        task: The task about to be executed. CRITICAL for task-relevant recall.

    Returns:
        str: Multi-line context block suitable for prompt injection.
    """
    t0 = time.monotonic()
    sections = []

    # === CORE: Tiered brief (primacy/recency optimized) ===
    try:
        from clarvis.context.assembly import generate_tiered_brief
        knowledge_hints = ""
        if task and tier != "minimal":
            introspection = _introspect_for_task(task, tier)
            if introspection:
                knowledge_hints = introspection
        tiered = generate_tiered_brief(
            current_task=task or "", tier=tier,
            knowledge_hints=knowledge_hints)
        if tiered and tiered.strip():
            sections.append(tiered)
    except Exception:
        # Fallback: if tiered brief fails, use individual section builders
        if task and tier != "minimal":
            introspection = _introspect_for_task(task, tier)
            if introspection:
                sections.append(introspection)
        if tier in ("standard", "full"):
            failures = _get_failure_patterns(task=task, limit=3)
            if failures:
                sections.append(failures)

    # === EXTRAS: sections not covered by tiered brief ===

    # Active goals
    goals = _get_brain_goals(limit=5 if tier != "minimal" else 2)
    if goals:
        sections.append(goals)

    # Synaptic spreading (full tier only — expensive)
    if tier == "full" and task:
        synaptic = _get_synaptic_associations(task)
        if synaptic:
            sections.append(synaptic)

    # Attention spotlight (full tier only)
    if tier == "full":
        spotlight = _get_attention_spotlight(task=task, limit=5)
        if spotlight:
            sections.append(spotlight)

    # Capability scores (full tier only)
    if tier == "full":
        caps = _get_capability_scores()
        if caps:
            sections.append(caps)

    # Compressed queue (standard + full)
    if tier in ("standard", "full"):
        queue = _get_compressed_queue(tier)
        if queue:
            sections.append(queue)

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if not sections:
        return "No context available — brain may be initializing."

    footer = f"\n[Context built in {elapsed_ms}ms, tier={tier}]"
    return "\n\n".join(sections) + footer


def build_prompt(task, role="executive", tier="standard", time_budget=None):
    """Build a complete prompt for Claude Code spawning.

    This assembles: ROLE + TIME BUDGET + CONTEXT (from full brain) + TASK + INSTRUCTIONS.

    Args:
        task: The task description to execute.
        role: Role name (executive, evolution, morning, evening, reflection).
        tier: Context tier (minimal, standard, full).
        time_budget: Optional time budget in seconds.

    Returns:
        str: Complete prompt ready for Claude Code.
    """
    context_brief = get_context_brief(tier=tier, task=task)

    parts = []
    parts.append(f"ROLE: You are Clarvis's {role} function (Claude Code Opus).")
    parts.append("")

    if time_budget:
        minutes = max(1, time_budget // 60)
        parts.append(
            f"TIME BUDGET: ~{minutes} minutes. "
            "Prioritize completing something concrete over perfection."
        )
        parts.append("")

    parts.append("CONTEXT:")
    parts.append(context_brief)
    parts.append("")

    parts.append(f"TASK: {task}")
    parts.append("")

    parts.append("INSTRUCTIONS:")
    parts.append(f"- Work in {WORKSPACE}")
    parts.append("- Be concrete. Write code, edit configs, test changes.")
    parts.append("- When done, output a concise summary of what you did.")

    return "\n".join(parts)


def write_prompt_file(task, **kwargs):
    """Write prompt to a temp file and return the path.

    Shell-safe: writes via Python file I/O, no heredoc expansion issues.

    Args:
        task: The task description.
        **kwargs: Passed to build_prompt().

    Returns:
        str: Path to the temp file containing the prompt.
    """
    prompt = build_prompt(task, **kwargs)
    path = f"/tmp/claude_prompt_{os.getpid()}.txt"
    with open(path, "w") as f:
        f.write(prompt)
    return path
