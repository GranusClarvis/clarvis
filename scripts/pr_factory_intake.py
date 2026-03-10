"""PR Factory Phase 2 — Deterministic Intake Artifacts — DEPRECATED wrapper.

Canonical module: clarvis.orch.pr_intake
This file delegates to the spine module for backward compatibility.

Usage (new):
    from clarvis.orch.pr_intake import refresh_artifacts
Usage (legacy, still works):
    from pr_factory_intake import refresh_artifacts
"""
import warnings as _w
_w.warn("pr_factory_intake is deprecated; use clarvis.orch.pr_intake", DeprecationWarning, stacklevel=2)

from clarvis.orch.pr_intake import (  # noqa: F401
    generate_project_brief,
    generate_stack_detect,
    generate_commands,
    generate_architecture_map,
    generate_trust_boundaries,
    generate_sector_playbook,
    seed_sector_to_brain,
    refresh_artifacts,
    load_all_artifacts,
    format_artifacts_for_prompt,
    is_stale,
    CONFIG_FILES,
    FRAMEWORK_MARKERS,
    SKIP_DIRS,
    # Private but used by tests/soak eval
    _load_artifact,
    _save_artifact,
    _artifacts_dir,
)

__all__ = [
    "generate_project_brief",
    "generate_stack_detect",
    "generate_commands",
    "generate_architecture_map",
    "generate_trust_boundaries",
    "generate_sector_playbook",
    "seed_sector_to_brain",
    "refresh_artifacts",
    "load_all_artifacts",
    "format_artifacts_for_prompt",
    "is_stale",
    "CONFIG_FILES",
    "FRAMEWORK_MARKERS",
    "SKIP_DIRS",
]

if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    if len(sys.argv) < 3:
        print("Usage: pr_factory_intake.py <agent_dir> <workspace>")
        sys.exit(1)
    agent_dir = Path(sys.argv[1])
    workspace = Path(sys.argv[2])
    report = refresh_artifacts(agent_dir, workspace)
    print(json.dumps(report, indent=2))
