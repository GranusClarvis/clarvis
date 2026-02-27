#!/usr/bin/env python3
"""Shared prompt builder for all Claude Code spawning scripts.

Builds structured prompts with contextual intelligence from brain,
attention, episodic memory, and working memory.

Usage:
    # CLI: get just the context brief
    python3 prompt_builder.py context-brief
    python3 prompt_builder.py context-brief --tier full

    # CLI: build full prompt
    python3 prompt_builder.py build --task "Fix retrieval" --role executive --tier standard

    # Python API
    from prompt_builder import build_prompt, get_context_brief
    prompt = build_prompt(task="Fix retrieval", role="evolution", tier="full")
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WORKSPACE = "/home/agent/.openclaw/workspace"
SOMATIC_FILE = os.path.join(WORKSPACE, "data/somatic_markers.json")
EPISODE_FILE = os.path.join(WORKSPACE, "data/episodes.json")


def _get_brain_goals(limit=5):
    """Get top goals by progress from brain."""
    try:
        from brain import brain
        goals = brain.get_goals()
        if not goals:
            return ""
        # Sort by progress descending, take top N
        goals.sort(
            key=lambda g: g.get("metadata", {}).get("progress", 0),
            reverse=True,
        )
        lines = []
        for g in goals[:limit]:
            meta = g.get("metadata", {})
            name = meta.get("goal", g.get("id", "?"))
            progress = meta.get("progress", 0)
            lines.append(f"  - {name}: {progress}%")
        return "GOALS:\n" + "\n".join(lines)
    except Exception:
        return ""


def _get_recent_episodes(limit=3):
    """Get recent episode outcomes."""
    try:
        if not os.path.exists(EPISODE_FILE):
            return ""
        with open(EPISODE_FILE) as f:
            episodes = json.load(f)
        if not episodes:
            return ""
        recent = episodes[-limit:]
        lines = []
        for ep in reversed(recent):
            task = ep.get("task", "?")[:60]
            outcome = ep.get("outcome", "?")
            lines.append(f"  - [{outcome}] {task}")
        return "RECENT EPISODES:\n" + "\n".join(lines)
    except Exception:
        return ""


def _get_failure_patterns(limit=3):
    """Get failure patterns to avoid from somatic markers."""
    try:
        if not os.path.exists(SOMATIC_FILE):
            return ""
        with open(SOMATIC_FILE) as f:
            markers = json.load(f)
        # Filter for avoidance signals
        avoidance = [
            m for m in markers
            if m.get("signal") == "avoidance" and m.get("strength", 0) > 0.3
        ]
        if not avoidance:
            return ""
        avoidance.sort(key=lambda m: m.get("strength", 0), reverse=True)
        lines = []
        for m in avoidance[:limit]:
            snippet = m.get("task_snippet", "?")[:60]
            emotion = m.get("emotion", "?")
            lines.append(f"  - AVOID: {snippet} ({emotion})")
        return "FAILURE PATTERNS:\n" + "\n".join(lines)
    except Exception:
        return ""


def _get_capability_scores():
    """Get current capability scores from self_model."""
    try:
        history_file = os.path.join(WORKSPACE, "data/capability_history.json")
        if not os.path.exists(history_file):
            return ""
        with open(history_file) as f:
            history = json.load(f)
        if not history:
            return ""
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


def _get_spotlight_items(limit=5):
    """Get current attention spotlight items."""
    try:
        spotlight_file = os.path.join(WORKSPACE, "data/attention_spotlight.json")
        if not os.path.exists(spotlight_file):
            return ""
        with open(spotlight_file) as f:
            data = json.load(f)
        items = data.get("items", [])
        if not items:
            return ""
        # Sort by salience descending
        items.sort(key=lambda i: i.get("salience", 0), reverse=True)
        lines = []
        for item in items[:limit]:
            text = item.get("text", "?")[:60]
            salience = item.get("salience", 0)
            lines.append(f"  - [{salience:.2f}] {text}")
        return "ATTENTION SPOTLIGHT:\n" + "\n".join(lines)
    except Exception:
        return ""


def get_context_brief(tier="standard"):
    """Build a context brief for Claude Code prompts.

    Tiers:
        minimal  - Task-only + 2-line context (for simple/OpenRouter tasks)
        standard - Goals + recent episodes + failure patterns (default)
        full     - Everything: goals + episodes + failures + capabilities + attention

    Returns:
        str: Multi-line context block suitable for prompt injection.
    """
    sections = []

    # All tiers get goals
    goals = _get_brain_goals(limit=5 if tier != "minimal" else 2)
    if goals:
        sections.append(goals)

    if tier in ("standard", "full"):
        episodes = _get_recent_episodes(limit=3)
        if episodes:
            sections.append(episodes)

        failures = _get_failure_patterns(limit=3)
        if failures:
            sections.append(failures)

    if tier == "full":
        caps = _get_capability_scores()
        if caps:
            sections.append(caps)

        spotlight = _get_spotlight_items(limit=5)
        if spotlight:
            sections.append(spotlight)

    # Also try to get compressed queue context from context_compressor
    if tier in ("standard", "full"):
        try:
            from context_compressor import compress_queue
            queue = compress_queue()
            if queue and len(queue) > 20:
                # Truncate for standard tier
                max_len = 800 if tier == "standard" else 1500
                if len(queue) > max_len:
                    queue = queue[:max_len] + "\n  ... (truncated)"
                sections.append(queue)
        except Exception:
            pass

    if not sections:
        return "No context available — brain may be initializing."

    return "\n\n".join(sections)


def build_prompt(task, role="executive", tier="standard", time_budget=None):
    """Build a complete prompt for Claude Code spawning.

    Args:
        task: The task description to execute.
        role: Role name (executive, evolution, morning, evening, reflection).
        tier: Context tier (minimal, standard, full).
        time_budget: Optional time budget in seconds.

    Returns:
        str: Complete prompt ready for Claude Code.
    """
    context_brief = get_context_brief(tier=tier)

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


# === CLI ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  prompt_builder.py context-brief [--tier minimal|standard|full]")
        print("  prompt_builder.py build --task 'description' [--role executive] [--tier standard] [--time-budget 900]")
        sys.exit(0)

    cmd = sys.argv[1]

    # Parse flags
    tier = "standard"
    task = ""
    role = "executive"
    time_budget = None
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--tier" and i + 1 < len(sys.argv):
            tier = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--task" and i + 1 < len(sys.argv):
            task = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--role" and i + 1 < len(sys.argv):
            role = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--time-budget" and i + 1 < len(sys.argv):
            time_budget = int(sys.argv[i + 1])
            i += 2
        else:
            # Positional arg fallback for task
            if not task:
                task = sys.argv[i]
            i += 1

    if cmd == "context-brief":
        print(get_context_brief(tier=tier))

    elif cmd == "build":
        if not task:
            print("Error: --task is required", file=sys.stderr)
            sys.exit(1)
        print(build_prompt(task=task, role=role, tier=tier, time_budget=time_budget))

    elif cmd == "write":
        if not task:
            print("Error: --task is required", file=sys.stderr)
            sys.exit(1)
        path = write_prompt_file(task=task, role=role, tier=tier, time_budget=time_budget)
        print(path)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
