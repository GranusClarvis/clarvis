"""
Reasoning Chains — Persistent multi-step thought logging.

Stores chains of reasoning that build on each other across sessions.
Each chain has: title, steps (each with thought, timestamp, outcome).
Socratic self-questioning: each step auto-generates a devil's advocate
question to probe weaknesses; if a weakness is detected, a refinement
is appended to the step.

Migrated from scripts/reasoning_chains.py (2026-04-04 spine consolidation).

Usage:
    from clarvis.cognition.reasoning_chains import create_chain, add_step, complete_step
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from clarvis.brain import brain


# ---------------------------------------------------------------------------
# Socratic self-questioning templates
# ---------------------------------------------------------------------------

_SOCRATIC_TEMPLATES = [
    ("assumption", re.compile(r"\b(assum|presuppos|take for granted|obvious)\w*\b", re.I),
     "But what if that assumption is wrong? What evidence supports it?"),
    ("causation", re.compile(r"\b(because|caus|due to|leads? to|result)\w*\b", re.I),
     "How do we know this is the cause and not merely a correlation?"),
    ("generalization", re.compile(r"\b(always|never|every|all|none|no one)\b", re.I),
     "Is this always true, or are there exceptions we're ignoring?"),
    ("certainty", re.compile(r"\b(certain|definite|clearly|must be|undoubtedly|sure)\b", re.I),
     "What would change our mind? What counter-evidence could exist?"),
    ("should", re.compile(r"\b(should|ought|best|ideal|correct approach)\b", re.I),
     "But what if the opposite approach is better? What trade-offs are we missing?"),
    ("complexity", re.compile(r"\b(simple|straightforward|easy|trivial|just)\b", re.I),
     "Are we oversimplifying? What hidden complexity might we be overlooking?"),
]

_DEFAULT_QUESTION = "What could go wrong with this reasoning? What are we not seeing?"

_WEAKNESS_SIGNALS = re.compile(
    r"\b(maybe|might|unclear|unsure|risk|concern|weakness|gap|unknown|fragile|brittle|hack)\b", re.I
)


def _generate_socratic_question(thought: str) -> str:
    """Generate a devil's advocate question based on the thought content."""
    for _name, pattern, question in _SOCRATIC_TEMPLATES:
        if pattern.search(thought):
            return question
    return _DEFAULT_QUESTION


def _detect_weakness(thought: str, question: str) -> str | None:
    """Check if the thought itself hints at a weakness the question exposes."""
    if _WEAKNESS_SIGNALS.search(thought):
        return (
            f"Weakness detected — the reasoning acknowledges uncertainty. "
            f"Socratic probe: {question} "
            f"Recommendation: gather more evidence or add a fallback path."
        )
    return None

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
REASONING_DIR = Path(_WS) / "data" / "reasoning_chains"
REASONING_DIR.mkdir(parents=True, exist_ok=True)


def create_chain(title: str, initial_thought: str) -> str:
    """Create a new reasoning chain."""
    chain_id = f"chain_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    chain = {
        "id": chain_id,
        "title": title,
        "created": datetime.now().isoformat(),
        "steps": [
            {
                "step": 0,
                "thought": initial_thought,
                "timestamp": datetime.now().isoformat(),
                "outcome": None
            }
        ]
    }

    # Save to file
    chain_file = REASONING_DIR / f"{chain_id}.json"
    chain_file.write_text(json.dumps(chain, indent=2))

    # Also store in brain for searchability — use chain_id as memory_id for upsert
    brain.store(
        f"Reasoning chain: {title}. Initial thought: {initial_thought}",
        collection="clarvis-learnings",
        tags=["reasoning_chain", chain_id],
        memory_id=f"rc_{chain_id}",
    )

    return chain_id


def add_step(chain_id: str, thought: str, previous_outcome: str = None, socratic: bool = True) -> int:
    """Add a step to an existing chain.

    When *socratic* is True (default), a devil's advocate question is
    auto-generated and stored with the step.  If the question exposes a
    weakness, a refinement note is appended.
    """
    chain_file = REASONING_DIR / f"{chain_id}.json"
    if not chain_file.exists():
        raise FileNotFoundError(f"Chain {chain_id} not found")

    chain = json.loads(chain_file.read_text())
    step_num = len(chain["steps"])

    # Update previous step outcome if provided
    if previous_outcome and chain["steps"]:
        chain["steps"][-1]["outcome"] = previous_outcome

    step_entry: dict = {
        "step": step_num,
        "thought": thought,
        "timestamp": datetime.now().isoformat(),
        "outcome": None,
    }

    if socratic:
        question = _generate_socratic_question(thought)
        step_entry["socratic_question"] = question
        refinement = _detect_weakness(thought, question)
        if refinement:
            step_entry["socratic_refinement"] = refinement

    chain["steps"].append(step_entry)
    chain_file.write_text(json.dumps(chain, indent=2))

    brain_text = f"Reasoning chain '{chain['title']}' step {step_num}: {thought}"
    if socratic and step_entry.get("socratic_question"):
        brain_text += f" [Socratic: {step_entry['socratic_question']}]"

    brain.store(
        brain_text,
        collection="clarvis-learnings",
        tags=["reasoning_step", chain_id],
        memory_id=f"rc_{chain_id}_s{step_num}",
    )

    return step_num


def complete_step(chain_id: str, outcome: str):
    """Mark the current step's outcome."""
    chain_file = REASONING_DIR / f"{chain_id}.json"
    if not chain_file.exists():
        raise FileNotFoundError(f"Chain {chain_id} not found")

    chain = json.loads(chain_file.read_text())
    if chain["steps"]:
        chain["steps"][-1]["outcome"] = outcome
        chain_file.write_text(json.dumps(chain, indent=2))

        # Store outcome in brain — upsert by chain_id
        brain.store(
            f"Reasoning chain '{chain['title']}' outcome: {outcome}",
            collection="clarvis-learnings",
            tags=["reasoning_outcome", chain_id],
            memory_id=f"rc_{chain_id}_outcome",
        )


def get_chain(chain_id: str) -> dict:
    """Get full chain details."""
    chain_file = REASONING_DIR / f"{chain_id}.json"
    if not chain_file.exists():
        raise FileNotFoundError(f"Chain {chain_id} not found")
    return json.loads(chain_file.read_text())


def list_chains() -> list:
    """List all reasoning chains."""
    chains = []
    for f in REASONING_DIR.glob("chain_*.json"):
        chain = json.loads(f.read_text())
        chains.append({
            "id": chain["id"],
            "title": chain["title"],
            "steps": len(chain["steps"]),
            "created": chain["created"]
        })
    return sorted(chains, key=lambda x: x["created"], reverse=True)


def find_related_chains(query: str) -> list:
    """Find chains related to a query via brain."""
    results = brain.recall(query, n=5, collections=["clarvis-learnings"])
    chain_ids = set()
    for r in results:
        meta = r.get("metadata", {})
        tags_raw = meta.get("tags", "[]")
        try:
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else (tags_raw or [])
        except (json.JSONDecodeError, TypeError):
            tags = []
        if "reasoning_chain" in tags or "reasoning_step" in tags or "reasoning_outcome" in tags:
            for tag in tags:
                if tag.startswith("chain_"):
                    chain_ids.add(tag)
    return list(chain_ids)
