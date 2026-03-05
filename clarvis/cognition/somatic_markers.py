"""Spine proxy — somatic_markers (scripts/somatic_markers.py).

Re-exports the somatic singleton for spine consumers.
Full implementation remains in scripts/ until full migration.
"""

import sys

_SCRIPTS_DIR = "/home/agent/.openclaw/workspace/scripts"


def _ensure_path():
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)


_ensure_path()

# Re-export the somatic singleton
from somatic_markers import somatic  # noqa: E402, F401
