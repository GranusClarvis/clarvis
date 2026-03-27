#!/usr/bin/env python3
"""
Reasoning Chain Hook — CLI for cron_autonomous.sh integration

Now dual-writes: legacy chain format + ClarvisReasoning session for richer meta-cognition.

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
import logging

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))

from reasoning_chains import create_chain, add_step, complete_step, find_related_chains, list_chains
from brain import brain

try:
    from clarvis_reasoning import reasoner as cr_reasoner
except ImportError:
    cr_reasoner = None

try:
    from retrieval_experiment import smart_recall
except ImportError:
    smart_recall = None

try:
    from thought_protocol import thought as thought_proto
except ImportError:
    thought_proto = None

# Map chain_id -> session_id for the ClarvisReasoning dual-write
_SESSION_MAP_FILE = os.path.join(os.path.dirname(__file__),
                                  "..", "data", "reasoning_chains", "session_map.json")


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
    except Exception as e:
        logger.debug("Failed to list recent chains for related-task search: %s", e)

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
        except Exception as e:
            logger.debug("thought_proto.encode_state() failed at chain open: %s", e)

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

    # === ClarvisReasoning dual-write: richer session with decomposition ===
    if cr_reasoner:
        try:
            session = cr_reasoner.begin(task_text[:200])
            # Decompose based on task type
            if task_type == "bug fix":
                session.decompose(["Diagnose root cause", "Design fix", "Implement and verify"])
            elif task_type == "new capability":
                session.decompose(["Understand requirements", "Design approach", "Build implementation", "Test"])
            elif task_type == "integration":
                session.decompose(["Identify integration points", "Wire connections", "Verify end-to-end"])
            else:
                session.decompose(["Analyze context", "Plan approach", "Execute"])

            # Step 1: Context analysis with evidence
            session.step(
                step0_thought,
                sub_problem=session.sub_problems[0] if session.sub_problems else "",
                evidence=[s[:80] for s in context_snippets[:3]] or ["no prior context found"],
                confidence=min(0.9, 0.5 + float(salience) * 0.4),
            )

            # Step 2: Strategy with evidence
            risk_level = "low" if related else "medium"
            session.step(
                step1_thought,
                sub_problem=session.sub_problems[1] if len(session.sub_problems) > 1 else "",
                evidence=[f"task_type={task_type}", f"salience={salience}", f"risk={risk_level}"],
                confidence=min(0.9, 0.5 + float(salience) * 0.3),
            )

            # Predict outcome
            pred_conf = min(0.85, 0.6 + float(salience) * 0.2)
            session.predict("success", pred_conf)

            # Save session_id mapping so close_chain can find it
            _save_session_map(chain_id, session.session_id)
            print(f"REASONING_SESSION: {session.session_id}", file=sys.stderr)
        except Exception as e:
            print(f"ClarvisReasoning session error: {e}", file=sys.stderr)

    print(chain_id, file=sys.stderr)  # stderr — don't contaminate stdout JSON
    return chain_id


def _save_session_map(chain_id: str, session_id: str):
    """Map chain_id to session_id for close_chain lookup."""
    import json
    try:
        data = {}
        if os.path.exists(_SESSION_MAP_FILE):
            with open(_SESSION_MAP_FILE) as f:
                data = json.load(f)
        data[chain_id] = session_id
        # Keep only last 100 mappings
        if len(data) > 100:
            keys = sorted(data.keys())
            data = {k: data[k] for k in keys[-100:]}
        os.makedirs(os.path.dirname(_SESSION_MAP_FILE), exist_ok=True)
        with open(_SESSION_MAP_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug("Failed to save chain→session mapping to %s: %s", _SESSION_MAP_FILE, e)


def _get_session_id(chain_id: str) -> str:
    """Get ClarvisReasoning session_id for a legacy chain_id."""
    import json
    try:
        if os.path.exists(_SESSION_MAP_FILE):
            with open(_SESSION_MAP_FILE) as f:
                data = json.load(f)
            return data.get(chain_id, "")
    except Exception as e:
        logger.debug("Failed to load chain→session mapping for chain_id=%s: %s", chain_id, e)
    return ""


def close_chain(chain_id: str, result: str, task_text: str, exit_code: str = "0",
                evidence: str = "") -> None:
    """Close a reasoning chain after task execution.

    Records actual outcome with evidence from execution output.
    Adds a final step (step 2+) with the concrete outcome.
    """
    # Extract meaningful evidence summary
    evidence_summary = ""
    evidence_clean = evidence.strip() if evidence else ""
    if evidence_clean:
        # Take last meaningful portion of output as evidence
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
    try:
        step_count = len(list_chains().get(chain_id, {}).get("steps", []))
    except Exception as e:
        logger.debug("Failed to count steps for chain_id=%s: %s", chain_id, e)
        step_count = "?"
    print(f"Chain {chain_id} closed: {result} ({step_count} steps)", file=sys.stderr)

    # === ClarvisReasoning dual-write: complete the session ===
    if cr_reasoner:
        try:
            session_id = _get_session_id(chain_id)
            if session_id:
                session = cr_reasoner.load_session(session_id)
                # Add execution outcome step with evidence
                session.step(
                    outcome_text,
                    sub_problem=session.sub_problems[-1] if session.sub_problems else "",
                    evidence=[f"exit_code={exit_code}"] + ([evidence_clean[:100]] if evidence else []),
                    confidence=0.9 if result == "success" else 0.3,
                )
                session.complete(result, outcome_text[:200])
                ev = session.evaluate()
                print(f"REASONING_SESSION: {session_id} closed, grade={ev.get('quality_grade')}", file=sys.stderr)
        except Exception as e:
            print(f"ClarvisReasoning close error: {e}", file=sys.stderr)


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
