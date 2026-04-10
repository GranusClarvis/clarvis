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
import subprocess
import time
from datetime import datetime, timezone

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
_PIPELINE_DIR = os.path.join(_SCRIPTS_DIR, "pipeline")
_PYTHON = os.environ.get("CLARVIS_PYTHON", "python3")


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

    Delegates to scripts/pipeline/heartbeat_preflight.py via subprocess.
    Returns preflight JSON dict.
    """
    script = os.path.join(_PIPELINE_DIR, "heartbeat_preflight.py")
    cmd = [_PYTHON, script]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    output = result.stdout.strip()
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw_output": output}
    return {}


def run_postflight(exit_code: int, output_file: str, preflight_json_file: str) -> dict:
    """Run heartbeat postflight.

    Delegates to scripts/pipeline/heartbeat_postflight.py via subprocess.

    Args:
        exit_code: Claude Code exit code (0=success)
        output_file: path to Claude Code output
        preflight_json_file: path to preflight JSON

    Returns:
        postflight result dict
    """
    script = os.path.join(_PIPELINE_DIR, "heartbeat_postflight.py")
    cmd = [_PYTHON, script, str(exit_code), output_file, preflight_json_file]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    output = result.stdout.strip()
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw_output": output}
    return {}
