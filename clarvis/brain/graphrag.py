"""Spine proxy — graphrag_communities (scripts/graphrag_communities.py).

Re-exports key functions for spine consumers: global_search, enhanced_local_search.
Full implementation remains in scripts/ until full migration.
"""

import sys

_SCRIPTS_DIR = "/home/agent/.openclaw/workspace/scripts"


def _ensure_path():
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)


_ensure_path()

# Re-export needed symbols
from graphrag_communities import (  # noqa: E402, F401
    global_search,
    enhanced_local_search,
    COMMUNITIES_FILE,
    SUMMARIES_FILE,
)
