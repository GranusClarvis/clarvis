#!/usr/bin/env python3
"""
Reasoning Chains — Persistent multi-step thought logging

Stores chains of reasoning that build on each other across sessions.
Each chain has: title, steps (each with thought, timestamp, outcome)
"""

import json
from datetime import datetime
from pathlib import Path

from brain import brain

REASONING_DIR = Path("/home/agent/.openclaw/workspace/data/reasoning_chains")
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
    
    # Also store in brain for searchability
    brain.store(
        f"Reasoning chain: {title}. Initial thought: {initial_thought}",
        collection="clarvis-learnings",
        tags=["reasoning_chain", chain_id]
    )
    
    return chain_id

def add_step(chain_id: str, thought: str, previous_outcome: str = None) -> int:
    """Add a step to an existing chain."""
    chain_file = REASONING_DIR / f"{chain_id}.json"
    if not chain_file.exists():
        raise FileNotFoundError(f"Chain {chain_id} not found")
    
    chain = json.loads(chain_file.read_text())
    step_num = len(chain["steps"])
    
    # Update previous step outcome if provided
    if previous_outcome and chain["steps"]:
        chain["steps"][-1]["outcome"] = previous_outcome
    
    chain["steps"].append({
        "step": step_num,
        "thought": thought,
        "timestamp": datetime.now().isoformat(),
        "outcome": None
    })
    
    chain_file.write_text(json.dumps(chain, indent=2))
    
    # Store in brain
    brain.store(
        f"Reasoning chain '{chain['title']}' step {step_num}: {thought}",
        collection="clarvis-learnings",
        tags=["reasoning_step", chain_id]
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
        
        # Store outcome in brain
        brain.store(
            f"Reasoning chain '{chain['title']}' outcome: {outcome}",
            collection="clarvis-learnings",
            tags=["reasoning_outcome", chain_id]
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
            # Extract chain_id from tags (it's the non-keyword tag)
            for tag in tags:
                if tag.startswith("chain_"):
                    chain_ids.add(tag)
    return list(chain_ids)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: reasoning_chains.py <create|add|complete|list|get|search> [args]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        title = sys.argv[2] if len(sys.argv) > 2 else input("Title: ")
        thought = sys.argv[3] if len(sys.argv) > 3 else input("Initial thought: ")
        chain_id = create_chain(title, thought)
        print(f"Created chain: {chain_id}")
    
    elif cmd == "add":
        chain_id = sys.argv[2]
        thought = sys.argv[3] if len(sys.argv) > 3 else input("Thought: ")
        outcome = sys.argv[4] if len(sys.argv) > 4 else None
        step = add_step(chain_id, thought, outcome)
        print(f"Added step {step} to {chain_id}")
    
    elif cmd == "complete":
        chain_id = sys.argv[2]
        outcome = sys.argv[3] if len(sys.argv) > 3 else input("Outcome: ")
        complete_step(chain_id, outcome)
        print(f"Completed latest step in {chain_id}")
    
    elif cmd == "list":
        for c in list_chains():
            print(f"{c['id']}: {c['title']} ({c['steps']} steps)")
    
    elif cmd == "get":
        chain_id = sys.argv[2]
        chain = get_chain(chain_id)
        print(json.dumps(chain, indent=2))
    
    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else input("Query: ")
        for cid in find_related_chains(query):
            print(cid)
    
    else:
        print(f"Unknown command: {cmd}")
