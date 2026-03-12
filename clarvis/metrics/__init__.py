"""Clarvis metrics — phi, performance benchmark, self-model, import health.

Canonical spine modules:
  - clarvis.metrics.phi       — Phi (IIT) integrated information metric
  - clarvis.metrics.benchmark — Performance Index (PI) computation
  - clarvis.metrics.self_model — 7-domain capability assessment
"""

from .phi import compute_phi
from .benchmark import compute_pi
from .self_model import assess_all_capabilities as assess
