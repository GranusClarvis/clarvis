#!/usr/bin/env python3
# STATUS: BRIDGE — canonical implementation lives in clarvis/cognition/somatic_markers.py
"""Somatic Markers — bridge to clarvis.cognition.somatic_markers."""

from clarvis.cognition.somatic_markers import (  # noqa: F401 — re-export
    SomaticMarkerSystem,
    get_somatic,
    somatic,
    EMOTIONS,
    MARKERS_FILE,
)

if __name__ == "__main__":
    import runpy
    runpy.run_module("clarvis.cognition.somatic_markers", run_name="__main__")
