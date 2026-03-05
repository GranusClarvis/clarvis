"""Spine proxy — meta_learning (scripts/meta_learning.py).

Re-exports the MetaLearner class for spine consumers.
Full implementation remains in scripts/ until full migration.
"""

import sys

_SCRIPTS_DIR = "/home/agent/.openclaw/workspace/scripts"


def _ensure_path():
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)


_ensure_path()

# Re-export the MetaLearner class
from meta_learning import MetaLearner  # noqa: E402, F401
