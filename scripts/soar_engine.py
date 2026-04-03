#!/usr/bin/env python3
# STATUS: BRIDGE — canonical implementation lives in clarvis/memory/soar.py
"""SOAR Engine — bridge to clarvis.memory.soar."""

from clarvis.memory.soar import (  # noqa: F401 — re-export
    Goal,
    Operator,
    SOAREngine,
    get_soar,
    soar,
)

if __name__ == "__main__":
    import runpy
    runpy.run_module("clarvis.memory.soar", run_name="__main__")
