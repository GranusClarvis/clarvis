"""
Heartbeat Runner — orchestration for the heartbeat pipeline.

Ties together gate → preflight → (executor) → postflight.
Used by `clarvis heartbeat run` and cron scripts.

The runner does NOT spawn Claude Code itself — that's the cron script's job.
It provides the pre/post logic as importable functions.

Usage:
    from clarvis.heartbeat.runner import run_gate_check, run_preflight, run_postflight
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")


def run_gate_check(verbose: bool = False) -> dict:
    """Run heartbeat gate (zero-LLM pre-check).

    Returns:
        {"decision": "wake"|"skip", "reason": str, "changes": list}
    """
    from .gate import run_gate
    decision, output = run_gate(verbose=verbose)
    return output


def run_preflight(dry_run: bool = False) -> dict:
    """Run heartbeat preflight checks.

    Delegates to scripts/heartbeat_preflight.py (which does the heavy lifting
    with all cognitive subsystem imports). Returns preflight JSON dict.
    """
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)

    # Import and run the preflight module's main logic
    import importlib
    spec = importlib.util.spec_from_file_location(
        "heartbeat_preflight",
        os.path.join(_SCRIPTS_DIR, "heartbeat_preflight.py"),
    )
    mod = importlib.util.module_from_spec(spec)

    # Capture stdout (preflight prints JSON to stdout)
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    try:
        # Set dry_run flag before loading
        if dry_run:
            sys.argv = [sys.argv[0], "--dry-run"]
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue().strip()
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw_output": output}
    return {}


def run_postflight(exit_code: int, output_file: str, preflight_json_file: str) -> dict:
    """Run heartbeat postflight.

    Delegates to scripts/heartbeat_postflight.py.

    Args:
        exit_code: Claude Code exit code (0=success)
        output_file: path to Claude Code output
        preflight_json_file: path to preflight JSON

    Returns:
        postflight result dict
    """
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)

    import importlib
    spec = importlib.util.spec_from_file_location(
        "heartbeat_postflight",
        os.path.join(_SCRIPTS_DIR, "heartbeat_postflight.py"),
    )
    mod = importlib.util.module_from_spec(spec)

    sys.argv = ["heartbeat_postflight.py", str(exit_code), output_file, preflight_json_file]

    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue().strip()
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw_output": output}
    return {}
