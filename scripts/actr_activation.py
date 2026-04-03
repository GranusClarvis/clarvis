#!/usr/bin/env python3
# STATUS: BRIDGE — canonical implementation lives in clarvis/brain/actr_activation.py
# This wrapper preserves CLI + legacy `from actr_activation import ...` imports.
"""ACT-R Activation Scoring — bridge to clarvis.brain.actr_activation."""

from clarvis.brain.actr_activation import (  # noqa: F401 — re-export
    DECAY_D, DECAY_D_MIN, DECAY_D_MAX,
    SPACING_C, SPACING_GAMMA,
    SPREADING_W, MAX_SPREADING_SOURCES,
    NOISE_S,
    SEMANTIC_WEIGHT, ACTIVATION_WEIGHT,
    RETRIEVAL_TAU, LOW_ACCESS_THRESHOLD, LOW_ACCESS_GRACE,
    compute_base_level,
    base_level_optimized,
    consolidation_strength,
    retrieval_probability,
    compute_spreading_activation,
    logistic_noise,
    sigmoid,
    actr_activation,
    actr_score,
    actr_rank,
)

if __name__ == "__main__":
    # Delegate CLI to spine module
    import runpy
    runpy.run_module("clarvis.brain.actr_activation", run_name="__main__")
