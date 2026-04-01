"""Spine proxy — soar_engine (scripts/soar_engine.py).

Re-exports the soar singleton for spine consumers.
Full implementation remains in scripts/ until full migration.
"""

import os
import sys

_SCRIPTS_DIR = os.path.join(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"), "scripts")


def _ensure_path():
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)


_ensure_path()

# Re-export the soar singleton
from soar_engine import soar  # noqa: E402, F401
