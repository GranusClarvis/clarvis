#!/usr/bin/env python3
# STATUS: BRIDGE — canonical implementation lives in clarvis/brain/retrieval_quality.py
# This wrapper preserves CLI + legacy `from retrieval_quality import tracker` imports.
"""Retrieval Quality Tracker — bridge to clarvis.brain.retrieval_quality."""

from clarvis.brain.retrieval_quality import (  # noqa: F401 — re-export
    RetrievalQualityTracker,
    get_tracker,
    tracker,
    DATA_DIR,
    EVENTS_FILE,
    REPORT_FILE,
    MAX_EVENTS,
)

if __name__ == "__main__":
    import runpy
    runpy.run_module("clarvis.brain.retrieval_quality", run_name="__main__")
