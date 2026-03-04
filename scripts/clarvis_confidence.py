#!/usr/bin/env python3
"""Clarvis Confidence Tracking — thin wrapper. Implementation in clarvis/cognition/confidence.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.cognition.confidence import *  # noqa: F401,F403
from clarvis.cognition.confidence import (  # noqa: F401
    predict, outcome, calibration, predict_specific, dynamic_confidence,
    review, auto_resolve, save_threshold, load_threshold, main,
    CALIBRATION_DIR, PREDICTIONS_FILE, THRESHOLDS_FILE,
)

if __name__ == "__main__":
    main()
