"""
Clarvis Adapter — Wire ClarvisCode into the main Clarvis brain.

Provides drop-in replacements for scripts/task_router.py and
scripts/context_compressor.py using the standalone package,
plus integration with brain.py for metric-enriched context.

Usage from Clarvis scripts:
    from clarvis_code.clarvis_adapter import (
        route_task,
        compress_context,
        build_task_prompt,
    )
"""

import json
import os
import sys
from typing import Any, Dict, Optional

# Add scripts path for brain.py access
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

from clarvis_code.router import TaskRouter
from clarvis_code.compressor import ContextCompressor
from clarvis_code.prompt_builder import PromptBuilder, PromptConfig
from clarvis_code.session import SessionManager

# === Singleton instances with Clarvis-specific config ===

DATA_DIR = "/home/agent/.openclaw/workspace/data"
QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"

_router = TaskRouter(
    log_path=os.path.join(DATA_DIR, "router_decisions.jsonl"),
)

_compressor = ContextCompressor(max_recent_completed=5)

_builder = PromptBuilder(PromptConfig(
    preamble="You are Clarvis's executive function. Execute this evolution task:",
    suffix="Do the work. Be concrete. Write code if needed. Test it.\nWhen done, output a 1-line summary of what you accomplished.",
))

_lightweight_builder = PromptBuilder(PromptConfig(
    preamble="You are Clarvis's executive function. Execute this evolution task:",
    suffix="Do the work. Be concrete. When done, output a 1-line summary.",
    include_escalation_instruction=True,
    escalation_marker="NEEDS_CLAUDE_CODE: true",
))


def route_task(task_text: str, context: str = "") -> Dict[str, Any]:
    """Route a task — drop-in replacement for task_router.py classify_task().

    Returns dict compatible with existing cron_autonomous.sh parsing.
    Maps 'agent' -> 'claude' and 'lightweight' -> 'gemini' for backward compat.
    """
    result = _router.classify(task_text, context)
    # Map executor names for backward compatibility
    executor_map = {"agent": "claude", "lightweight": "gemini"}
    return {
        "tier": result.tier,
        "score": round(result.score, 4),
        "executor": executor_map.get(result.executor, result.executor),
        "dimensions": {k: round(v, 3) for k, v in result.dimensions.items()},
        "reason": result.reason,
    }


def compress_context(queue_file: str = QUEUE_FILE) -> str:
    """Compress context — drop-in replacement for context_compressor.py generate_context_brief().

    Enriches with brain.py metrics when available.
    """
    parts = [_compressor.compress_queue(queue_file)]

    # Add metrics from data files
    metrics = _get_latest_metrics()
    if metrics:
        parts.append("\n=== LATEST METRICS ===")
        for k, v in metrics.items():
            if isinstance(v, float):
                parts.append(f"{k}={v:.3f}")
            elif isinstance(v, dict):
                items = ", ".join(f"{sk}={sv}" for sk, sv in sorted(v.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0))
                parts.append(f"{k}: {items}")
            else:
                parts.append(f"{k}={v}")

    # Brain stats
    try:
        from brain import brain
        stats = brain.stats()
        parts.append(f"Brain: {stats['total_memories']} memories, {stats['graph_edges']} edges")
    except Exception:
        pass

    return "\n".join(parts)


def build_task_prompt(
    task: str,
    context: str = "",
    proc_hint: str = "",
    episode_hint: str = "",
    lightweight: bool = False,
) -> str:
    """Build a task prompt — unified prompt construction.

    Args:
        task: Task description.
        context: Compressed context (from compress_context()).
        proc_hint: Procedural memory hint string.
        episode_hint: Episodic memory hint string.
        lightweight: If True, build for lightweight executor with escalation.

    Returns:
        Formatted prompt string.
    """
    if lightweight:
        return _lightweight_builder.build_lightweight(task, context)

    # Parse procedure hint into dict if it's a string
    procedure = None
    if proc_hint:
        steps = []
        for line in proc_hint.split("\n"):
            line = line.strip()
            import re
            match = re.match(r'\d+\.\s+(.+)', line)
            if match:
                steps.append(match.group(1))
        if steps:
            procedure = {"steps": steps, "success_rate": "from procedural memory"}

    # Parse episode hint into list if it's a string
    episodes = None
    if episode_hint:
        episodes = []
        for line in episode_hint.split("\n"):
            line = line.strip()
            import re
            match = re.match(r'\[(\w+)\]\s*(.+)', line)
            if match:
                episodes.append({"outcome": match.group(1), "task": match.group(2)})

    return _builder.build(
        task=task,
        context=context,
        episodes=episodes,
        procedure=procedure,
    )


def _get_latest_metrics() -> Dict[str, Any]:
    """Read latest metrics from data files."""
    metrics = {}

    cap_file = os.path.join(DATA_DIR, "capability_history.json")
    if os.path.exists(cap_file):
        try:
            with open(cap_file) as f:
                history = json.load(f)
            if history:
                latest = history[-1]
                scores = {k: round(v, 2) for k, v in latest.get("scores", {}).items()
                          if isinstance(v, (int, float))}
                if scores:
                    metrics["capabilities"] = scores
                    metrics["capability_avg"] = round(sum(scores.values()) / len(scores), 2)
        except Exception:
            pass

    phi_file = os.path.join(DATA_DIR, "phi_history.json")
    if os.path.exists(phi_file):
        try:
            with open(phi_file) as f:
                phi_hist = json.load(f)
            if phi_hist:
                metrics["Phi"] = round(phi_hist[-1].get("phi", 0), 3)
        except Exception:
            pass

    return metrics
