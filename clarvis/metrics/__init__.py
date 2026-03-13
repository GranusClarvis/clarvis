"""Clarvis metrics — phi, performance benchmark, self-model, code validation, quality.

Canonical spine modules:
  - clarvis.metrics.phi             — Phi (IIT) integrated information metric
  - clarvis.metrics.benchmark       — Performance Index (PI) computation
  - clarvis.metrics.self_model      — 7-domain capability assessment
  - clarvis.metrics.code_validation — Deterministic pre-LLM code validation (PyCapsule)
  - clarvis.metrics.quality         — Multi-dimensional quality scoring
"""

from .phi import compute_phi
from .benchmark import compute_pi
from .self_model import assess_all_capabilities as assess
from .code_validation import validate_python_file, validate_output
from .quality import compute_code_quality_score, compute_task_quality_score, get_all_quality_metrics
