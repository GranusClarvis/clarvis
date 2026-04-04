#!/usr/bin/env python3
# BRIDGE: Thin re-export wrapper for legacy sys.path imports.
# Safe to delete ONLY after all callers migrate to: from clarvis.cognition.confidence import ...
# Known callers: self_model, evolution_preflight (heartbeat_preflight/postflight migrated 2026-03-24)
"""Clarvis Confidence Tracking — thin wrapper. Implementation in clarvis/cognition/confidence.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import _paths  # noqa: F401 — registers all script subdirs on sys.path
from clarvis.cognition.confidence import (  # noqa: F401
    predict, outcome, calibration, predict_specific, dynamic_confidence,
    review, auto_resolve, sweep_stale, archive_old,
    save_threshold, load_threshold, main,
    CALIBRATION_DIR, PREDICTIONS_FILE, THRESHOLDS_FILE,
)

if __name__ == "__main__":
    main()
