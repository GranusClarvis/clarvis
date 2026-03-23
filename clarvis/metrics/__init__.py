"""Clarvis metrics — phi, performance benchmark, self-model, code validation, quality.

Canonical spine modules:
  - clarvis.metrics.phi             — Phi (IIT) integrated information metric
  - clarvis.metrics.benchmark       — Performance Index (PI) computation
  - clarvis.metrics.self_model      — 7-domain capability assessment
  - clarvis.metrics.code_validation — Deterministic pre-LLM code validation (PyCapsule)
  - clarvis.metrics.quality         — Multi-dimensional quality scoring
  - clarvis.metrics.clr             — CLR-Internal: architecture health composite
  - clarvis.metrics.clr_benchmark   — CLR-Benchmark: external task evaluation
  - clarvis.metrics.longmemeval     — LongMemEval adapter (5 abilities)
  - clarvis.metrics.membench        — MemBench adapter (4 quadrants)
"""

from .phi import compute_phi
from .benchmark import compute_pi
from .clr import compute_clr, record_clr, format_clr, get_clr_trend
from .self_model import assess_all_capabilities as assess, SelfModel
from .code_validation import validate_python_file, validate_output
from .quality import compute_code_quality_score, compute_task_quality_score, get_all_quality_metrics
from .memory_audit import run_full_audit, audit_memory_ratios, audit_archived_vs_active
