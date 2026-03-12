"""PR Factory Rules — DEPRECATED wrapper.

Canonical module: clarvis.orch.pr_rules
This file delegates to the spine module for backward compatibility.
"""
import warnings as _w
_w.warn("pr_factory_rules is deprecated; use clarvis.orch.pr_rules", DeprecationWarning, stacklevel=2)

from clarvis.orch.pr_rules import build_pr_rules_section, PR_CLASSES  # noqa: F401

__all__ = ["build_pr_rules_section", "PR_CLASSES"]
