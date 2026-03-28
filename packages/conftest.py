"""conftest for package tests — ensure installed packages shadow scripts/."""
import sys

# Remove scripts/ from sys.path if present, so that installed packages
# (e.g. clarvis_reasoning) are not shadowed by scripts/clarvis_reasoning.py.
_scripts_dir = "/home/agent/.openclaw/workspace/scripts"
while _scripts_dir in sys.path:
    sys.path.remove(_scripts_dir)

# Clear any cached script-level modules that shadow packages
_shadow_modules = ["clarvis_reasoning"]
for _mod in _shadow_modules:
    if _mod in sys.modules:
        _cached = sys.modules[_mod]
        # Only remove if it's the script, not the package
        if hasattr(_cached, "__file__") and _cached.__file__ and "scripts/" in _cached.__file__:
            del sys.modules[_mod]
