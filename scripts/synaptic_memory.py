#!/usr/bin/env python3
# STATUS: BRIDGE — canonical implementation lives in clarvis/memory/synaptic_memory.py
# This wrapper preserves CLI + legacy `from synaptic_memory import synaptic` imports.
"""Synaptic Memory — bridge to clarvis.memory.synaptic_memory."""

from clarvis.memory.synaptic_memory import (  # noqa: F401 — re-export
    SynapticMemory,
    get_synaptic,
    synaptic,
)

if __name__ == "__main__":
    import runpy
    runpy.run_module("clarvis.memory.synaptic_memory", run_name="__main__")
