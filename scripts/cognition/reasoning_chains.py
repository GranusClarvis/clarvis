#!/usr/bin/env python3
"""
DEPRECATED: Core logic moved to clarvis.cognition.reasoning_chains (spine migration 2026-04-04).
This wrapper delegates to the spine module for backward compatibility.

New code should use: from clarvis.cognition.reasoning_chains import create_chain, add_step
"""

import json
import sys

# Re-export all public API from spine module
from clarvis.cognition.reasoning_chains import (  # noqa: F401
    create_chain,
    add_step,
    complete_step,
    get_chain,
    list_chains,
    find_related_chains,
    REASONING_DIR,
)


if __name__ == "__main__":
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
