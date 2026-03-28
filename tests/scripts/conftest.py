"""conftest for tests originally in scripts/tests/."""
import sys
from pathlib import Path

# Add scripts dir so legacy imports (import heartbeat_gate, etc.) work
_scripts_dir = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.append(_scripts_dir)
