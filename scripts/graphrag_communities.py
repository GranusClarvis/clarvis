#!/usr/bin/env python3
# STATUS: BRIDGE — canonical implementation lives in clarvis/brain/graphrag.py
"""GraphRAG Communities — bridge to clarvis.brain.graphrag."""

from clarvis.brain.graphrag import (  # noqa: F401 — re-export
    global_search,
    enhanced_local_search,
    COMMUNITIES_FILE,
    SUMMARIES_FILE,
)

if __name__ == "__main__":
    import runpy
    runpy.run_module("clarvis.brain.graphrag", run_name="__main__")
