#!/usr/bin/env python3
# STATUS: BRIDGE — canonical implementation lives in clarvis/cognition/reasoning.py
"""Clarvis Reasoning — bridge to clarvis.cognition.reasoning."""

from clarvis.cognition.reasoning import (  # noqa: F401 — re-export
    ReasoningStep,
    ReasoningSession,
    ClarvisReasoner,
    get_reasoner,
    reasoner,
)

if __name__ == "__main__":
    import runpy
    runpy.run_module("clarvis.cognition.reasoning", run_name="__main__")
