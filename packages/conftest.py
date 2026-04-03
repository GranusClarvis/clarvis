"""conftest for legacy package tests — ensure installed packages shadow scripts/.

Note: packages are deprecated. clarvis-cost → clarvis.orch.cost_tracker,
clarvis-reasoning → clarvis.cognition.reasoning, clarvis-db → clarvis.brain.
"""
import sys

# Remove scripts/ from sys.path if present, so that installed packages
# are not shadowed by same-named scripts.
_scripts_dir = "/home/agent/.openclaw/workspace/scripts"
while _scripts_dir in sys.path:
    sys.path.remove(_scripts_dir)
