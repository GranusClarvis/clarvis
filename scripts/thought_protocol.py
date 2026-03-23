#!/usr/bin/env python3
# BRIDGE: Thin re-export wrapper for legacy sys.path imports.
# Safe to delete ONLY after all callers migrate to: from clarvis.cognition.thought_protocol import ...
# Known callers: reasoning_chain_hook, clarvis_reasoning
"""Thought Protocol — thin wrapper. Implementation in clarvis/cognition/thought_protocol.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.cognition.thought_protocol import (  # noqa: F401
    thought, ThoughtFrame, ThoughtProtocol, Signal, SignalVector,
    Relation, RelationGraph, DecisionRule, get_thought, main,
    THOUGHT_LOG,
)

if __name__ == "__main__":
    main()
