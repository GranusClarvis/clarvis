#!/usr/bin/env python3
"""
Reasoning Chain Hook — CLI for cron_autonomous.sh integration

Usage:
    # Before task execution: create chain, print chain_id
    python3 reasoning_chain_hook.py open "task text" "section_name" "salience_score"

    # After task execution: close chain with outcome
    python3 reasoning_chain_hook.py close "chain_id" "success|failure" "task text" "exit_code"

    # Search for related past reasoning
    python3 reasoning_chain_hook.py related "task text"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from reasoning_chains import create_chain, add_step, complete_step, find_related_chains, list_chains
from brain import brain


def open_chain(task_text: str, section: str = "unknown", salience: str = "0.0") -> str:
    """Create a reasoning chain before executing a task.

    Builds the initial thought: why this task matters, expected outcome, dependencies.
    Returns chain_id to stdout.
    """
    # Look for related past reasoning to inform this chain
    related = []
    try:
        recent_chains = list_chains()[:5]
        for c in recent_chains:
            if any(word in c["title"].lower() for word in task_text.lower().split()[:3]):
                related.append(c["title"])
    except Exception:
        pass

    # Build the initial reasoning thought
    dependency_note = ""
    if related:
        dependency_note = f" Related past work: {'; '.join(related[:3])}."

    initial_thought = (
        f"Executing evolution task (section={section}, salience={salience}). "
        f"Why this matters: This task was selected by attention-based salience scoring as the "
        f"highest-priority evolution step. "
        f"Expected outcome: Task completes successfully, advancing Clarvis's capabilities. "
        f"Task: {task_text[:200]}.{dependency_note}"
    )

    # Enrich with brain context — what do we know about this domain?
    try:
        context_memories = brain.recall(task_text, limit=3)
        if context_memories:
            snippets = [m.get("text", "")[:80] for m in context_memories[:2]]
            initial_thought += f" Brain context: {'; '.join(snippets)}"
    except Exception:
        pass

    chain_id = create_chain(f"Task: {task_text[:100]}", initial_thought)
    print(chain_id)  # stdout — captured by bash
    return chain_id


def close_chain(chain_id: str, result: str, task_text: str, exit_code: str = "0") -> None:
    """Close a reasoning chain after task execution.

    Records actual outcome, whether it matched expectations.
    """
    if result == "success":
        outcome = (
            f"Task completed successfully (exit {exit_code}). "
            f"The evolution step was executed as expected. "
            f"Task: {task_text[:200]}"
        )
    else:
        outcome = (
            f"Task FAILED (exit {exit_code}). "
            f"Expected success but execution failed. "
            f"This triggered the evolution loop for self-improvement. "
            f"Task: {task_text[:200]}"
        )

    complete_step(chain_id, outcome)
    print(f"Chain {chain_id} closed: {result}", file=sys.stderr)


def show_related(task_text: str) -> None:
    """Print related reasoning chains for a task."""
    chain_ids = find_related_chains(task_text)
    for cid in chain_ids:
        print(cid)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: reasoning_chain_hook.py <open|close|related> [args]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "open":
        task_text = sys.argv[2] if len(sys.argv) > 2 else ""
        section = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        salience = sys.argv[4] if len(sys.argv) > 4 else "0.0"
        open_chain(task_text, section, salience)

    elif cmd == "close":
        chain_id = sys.argv[2] if len(sys.argv) > 2 else ""
        result = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        task_text = sys.argv[4] if len(sys.argv) > 4 else ""
        exit_code = sys.argv[5] if len(sys.argv) > 5 else "0"
        if chain_id:
            close_chain(chain_id, result, task_text, exit_code)
        else:
            print("ERROR: No chain_id provided", file=sys.stderr)
            sys.exit(1)

    elif cmd == "related":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        show_related(query)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
