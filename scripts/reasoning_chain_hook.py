#!/usr/bin/env python3
"""
Reasoning Chain Hook — CLI for cron_autonomous.sh integration

Usage:
    # Before task execution: create chain, print chain_id
    python3 reasoning_chain_hook.py open "task text" "section_name" "salience_score"

    # After task execution: close chain with outcome + evidence
    python3 reasoning_chain_hook.py close "chain_id" "success|failure" "task text" "exit_code" ["evidence_summary"]

    # Search for related past reasoning
    python3 reasoning_chain_hook.py related "task text"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from reasoning_chains import create_chain, add_step, complete_step, find_related_chains, list_chains
from brain import brain

try:
    from retrieval_experiment import smart_recall
except ImportError:
    smart_recall = None

try:
    from thought_protocol import thought as thought_proto
except ImportError:
    thought_proto = None


def _recall_context(task_text: str) -> list:
    """Retrieve brain context for a task, with smart_recall fallback."""
    try:
        if smart_recall is not None:
            return smart_recall(task_text, n=3) or []
        return brain.recall(task_text, n=3, caller="reasoning_chain_hook") or []
    except Exception:
        try:
            return brain.recall(task_text, n=3, caller="reasoning_chain_hook") or []
        except Exception:
            return []


def open_chain(task_text: str, section: str = "unknown", salience: str = "0.0") -> str:
    """Create a multi-step reasoning chain before executing a task.

    Step 0: Context analysis — what do we know, what's related
    Step 1: Strategy — why this task, expected approach and outcome

    Returns chain_id to stdout.
    """
    # Look for related past reasoning
    related = []
    try:
        recent_chains = list_chains()[:5]
        for c in recent_chains:
            if any(word in c["title"].lower() for word in task_text.lower().split()[:3]):
                related.append(c["title"])
    except Exception:
        pass

    # Retrieve brain context
    context_memories = _recall_context(task_text)
    context_snippets = []
    for m in context_memories[:3]:
        snippet = m.get("document", m.get("text", ""))[:100].strip()
        if snippet:
            context_snippets.append(snippet)

    # --- Step 0: Context analysis ---
    context_note = ""
    if context_snippets:
        context_note = f" Relevant brain context: {'; '.join(context_snippets[:2])}."
    dependency_note = ""
    if related:
        dependency_note = f" Related past chains: {'; '.join(related[:3])}."

    step0_thought = (
        f"Context analysis for task: {task_text[:200]}. "
        f"Section={section}, salience={salience}. "
        f"Prior knowledge: {len(context_snippets)} relevant memories found."
        f"{context_note}{dependency_note}"
    )

    chain_id = create_chain(f"Task: {task_text[:100]}", step0_thought)

    # Log cognitive state at chain open via thought protocol
    if thought_proto:
        try:
            state = thought_proto.encode_state()
            print(f"THOUGHT_STATE: {state}", file=sys.stderr)
        except Exception:
            pass

    # --- Step 1: Strategy and expected outcome ---
    # Classify task type from keywords
    task_lower = task_text.lower()
    if any(w in task_lower for w in ["fix", "bug", "error", "broken"]):
        task_type = "bug fix"
    elif any(w in task_lower for w in ["build", "create", "implement", "add"]):
        task_type = "new capability"
    elif any(w in task_lower for w in ["wire", "hook", "integrate", "connect"]):
        task_type = "integration"
    elif any(w in task_lower for w in ["improve", "boost", "optimize", "increase"]):
        task_type = "optimization"
    else:
        task_type = "evolution task"

    step1_thought = (
        f"Strategy: This is a {task_type}. "
        f"Selected via attention-based salience scoring (score={salience}) "
        f"as the highest-priority evolution step in {section}. "
        f"Approach: Delegate to Claude Code with full context. "
        f"Expected outcome: Task completes, advancing Clarvis capabilities. "
        f"Risk: {'Low — similar past work succeeded' if related else 'Medium — no closely related past chains'}."
    )

    add_step(chain_id, step1_thought, previous_outcome="Context gathered, strategy formed")

    print(chain_id)  # stdout — captured by bash
    return chain_id


def close_chain(chain_id: str, result: str, task_text: str, exit_code: str = "0",
                evidence: str = "") -> None:
    """Close a reasoning chain after task execution.

    Records actual outcome with evidence from execution output.
    Adds a final step (step 2+) with the concrete outcome.
    """
    # Extract meaningful evidence summary
    evidence_summary = ""
    if evidence:
        # Take last meaningful portion of output as evidence
        evidence_clean = evidence.strip()
        if len(evidence_clean) > 300:
            evidence_clean = evidence_clean[-300:]
        evidence_summary = f" Evidence: {evidence_clean}"

    if result == "success":
        outcome_text = (
            f"Task completed successfully (exit {exit_code}). "
            f"Task: {task_text[:150]}."
            f"{evidence_summary or ' No detailed evidence captured.'}"
        )
        # Close step 1 with outcome, add step 2 as final conclusion
        add_step(chain_id, outcome_text, previous_outcome="Execution succeeded")
    else:
        outcome_text = (
            f"Task FAILED (exit {exit_code}). "
            f"Task: {task_text[:150]}. "
            f"Triggered evolution loop for self-improvement."
            f"{evidence_summary or ' No error details captured.'}"
        )
        add_step(chain_id, outcome_text, previous_outcome="Execution failed")

    # Mark the final step's outcome
    complete_step(chain_id, f"Chain complete: {result}")
    print(f"Chain {chain_id} closed: {result} ({3}+ steps)", file=sys.stderr)


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
        evidence = sys.argv[6] if len(sys.argv) > 6 else ""
        if chain_id:
            close_chain(chain_id, result, task_text, exit_code, evidence)
        else:
            print("ERROR: No chain_id provided", file=sys.stderr)
            sys.exit(1)

    elif cmd == "related":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        show_related(query)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
