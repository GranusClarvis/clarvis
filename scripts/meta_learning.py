#!/usr/bin/env python3
# STATUS: BRIDGE — canonical implementation lives in clarvis/learning/meta_learning.py
"""Meta-Learning — bridge to clarvis.learning.meta_learning."""

from clarvis.learning.meta_learning import MetaLearner  # noqa: F401 — re-export

if __name__ == "__main__":
    import runpy
    runpy.run_module("clarvis.learning.meta_learning", run_name="__main__")
