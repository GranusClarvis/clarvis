"""Load scripts/ modules via importlib — no import-path manipulation.

Provides a single ``load(name, subdir)`` function that loads a script from
``scripts/<subdir>/<name>.py`` using ``importlib.util.spec_from_file_location``.
Modules are cached after first load.

Used by spine modules (clarvis/) that need to call operational scripts
without modifying the Python import path.
"""

import importlib.util
import os
import sys

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
_SCRIPTS = os.path.join(WORKSPACE, "scripts")


def load(name: str, subdir: str = ""):
    """Load a script module by name from ``scripts/<subdir>/<name>.py``.

    The module's own top-level code (including any internal path setup)
    runs during loading. Returns the cached module on subsequent calls.
    """
    if name in sys.modules:
        return sys.modules[name]
    base = os.path.join(_SCRIPTS, subdir) if subdir else _SCRIPTS
    path = os.path.join(base, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Script not found: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
