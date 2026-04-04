"""Auto-discover and register all script subdirectories on sys.path.

Usage (in any script that moved to a subdirectory):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import _paths  # noqa: F401
"""
import sys
import os

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)
for _entry in sorted(os.listdir(_root)):
    _p = os.path.join(_root, _entry)
    if os.path.isdir(_p) and not _entry.startswith(("_", ".", "__")):
        if _p not in sys.path:
            sys.path.insert(0, _p)
