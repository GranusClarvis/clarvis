"""One-shot verification retry to rescue falsely-downgraded episodes.

Per ``[ESR_POSTFLIGHT_VERIFICATION_RETRY_PROBE]``: the postflight pipeline
downgrades ``success → partial_success`` whenever the spawned agent claims
``tests_passed=true`` but the parent's quick checks disagree (stderr noise,
lint flake, commit-count drift, stale cache, transient FS error, etc.).

The triage path (``reclassify_agent_reported_success``) handles the case
where the disagreement is a heuristic artifact. This module attacks a
different bucket: when the disagreement reflects a flaky test or a stale
cache miss, simply re-running the cited test command in a clean subshell
often passes. One bounded retry is cheap insurance against a noisy signal.

Design notes
------------
* **One retry per episode** — capped to bound cost. The hook short-circuits
  if no test command can be extracted.
* **Bounded budget** — default 60s. Hard timeout via ``subprocess.run``.
* **Clean subshell** — ``env=os.environ`` but invoked from ``subprocess``;
  no shell injection (uses ``shlex.split``).
* **Default shadow mode** — by default returns telemetry only, does NOT
  mutate ``task_status``. The 7-day shadow run measures rescue rate. Flip
  via ``CLARVIS_VERIFICATION_RETRY_ACTIVE=1`` once rescue rate ≥10%.
* **Conservative command extraction** — only allows pytest-shaped commands
  to keep the attack surface tight. Refuses anything that looks like a
  network call, shell pipe, redirection, or ``rm``/``sudo``/``curl``.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

__all__ = [
    "DEFAULT_BUDGET_S",
    "extract_test_command",
    "run_verification_retry",
    "maybe_retry",
    "should_attempt_retry",
]

DEFAULT_BUDGET_S = 60

_BLOCKED_TOKENS = (
    "rm ", "sudo ", "curl ", "wget ", "ssh ", "scp ", "git push",
    "docker ", "kubectl ", "systemctl ", "kill ", ">", "<", "|", "&",
    "$(", "`",
)

_PYTEST_RE = re.compile(
    r"""(?:^|\s|[`'"])((?:python3?\s+-m\s+)?pytest\s+[^\n`'"<>|&;]+)""",
    re.MULTILINE,
)

_TESTS_PASSED_TRUE_RE = re.compile(
    r'tests_passed["\s\\]*:\s*["\s\\]*true', re.IGNORECASE)


def _looks_safe(cmd: str) -> bool:
    """Reject commands containing shell metachars or known-dangerous tokens.

    Keeps the retry surface narrow: only plain ``pytest <paths> [flags]``
    invocations are eligible. Any redirection, pipe, subshell, or
    privileged command bails out.
    """
    low = cmd.lower()
    for tok in _BLOCKED_TOKENS:
        if tok in low:
            return False
    if not ("pytest" in low):
        return False
    return True


def extract_test_command(text: Optional[str]) -> Optional[str]:
    """Find the first plausibly-safe pytest invocation in ``text``.

    Returns the command string (without surrounding quotes/backticks) or
    ``None`` if none could be extracted safely.
    """
    if not text:
        return None
    for match in _PYTEST_RE.finditer(text):
        candidate = match.group(1).strip().rstrip(".,;:`'\"")
        candidate = candidate.split("\n", 1)[0].strip()
        if not candidate:
            continue
        if _looks_safe(candidate):
            return candidate
    return None


def should_attempt_retry(
    task_status: str,
    output_text: Optional[str],
    failure_type: Optional[str] = None,
    already_retried: bool = False,
) -> Tuple[bool, str]:
    """Gate the retry to the partial_success / agent-claimed-success case.

    Returns ``(eligible, reason)``. ``reason`` is a short telemetry tag.
    """
    if already_retried:
        return False, "already_retried"
    if task_status != "partial_success":
        return False, "status_not_partial_success"
    if not output_text:
        return False, "no_output"
    if not _TESTS_PASSED_TRUE_RE.search(output_text):
        return False, "no_tests_passed_claim"
    # Don't retry the cases the triage classifier already routes — those
    # are postflight artifacts, not flaky tests.
    if failure_type in {"action.test_failure", "action.lint_typecheck_error",
                        "action.compile_error"}:
        return False, "real_failure_type"
    return True, "eligible"


def run_verification_retry(
    command: str,
    budget_s: int = DEFAULT_BUDGET_S,
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    """Run ``command`` once with a hard time budget.

    Returns a dict with keys:
        * ``triggered`` — always True (the caller decides eligibility)
        * ``outcome`` — ``"success" | "still_failing" | "timeout" | "error"``
        * ``exit_code`` — int or None
        * ``duration_s`` — float, wall-clock seconds
        * ``command`` — the actual command executed
    """
    result: Dict[str, Any] = {
        "triggered": True,
        "outcome": "error",
        "exit_code": None,
        "duration_s": 0.0,
        "command": command,
    }
    if not command or not _looks_safe(command):
        result["outcome"] = "error"
        result["error"] = "unsafe_or_empty"
        return result

    try:
        argv = shlex.split(command)
    except ValueError as e:
        result["error"] = f"shlex_failed: {e}"
        return result

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=budget_s,
            check=False,
        )
        result["exit_code"] = proc.returncode
        result["duration_s"] = round(time.monotonic() - t0, 3)
        result["outcome"] = "success" if proc.returncode == 0 else "still_failing"
        tail = (proc.stderr or proc.stdout or "")[-200:]
        if tail:
            result["tail"] = tail
    except subprocess.TimeoutExpired:
        result["duration_s"] = round(time.monotonic() - t0, 3)
        result["outcome"] = "timeout"
    except FileNotFoundError as e:
        result["duration_s"] = round(time.monotonic() - t0, 3)
        result["outcome"] = "error"
        result["error"] = f"not_found: {e}"
    except Exception as e:
        result["duration_s"] = round(time.monotonic() - t0, 3)
        result["outcome"] = "error"
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def maybe_retry(
    task_status: str,
    output_text: Optional[str],
    failure_type: Optional[str] = None,
    cwd: Optional[str] = None,
    budget_s: int = DEFAULT_BUDGET_S,
    shadow_mode: Optional[bool] = None,
) -> Dict[str, Any]:
    """Top-level hook called from postflight.

    Returns the telemetry dict suitable for ``ctx["verification_retry"]``
    and (when active) sidecar storage. Always returns a dict — the caller
    can store it unconditionally.

    The ``override`` key is True iff the caller should flip
    ``task_status`` back to ``"success"``. In shadow mode this is always
    False even if the retry passes.
    """
    if shadow_mode is None:
        shadow_mode = os.environ.get(
            "CLARVIS_VERIFICATION_RETRY_ACTIVE", "0") != "1"

    eligible, reason = should_attempt_retry(task_status, output_text,
                                            failure_type=failure_type)
    if not eligible:
        return {
            "triggered": False,
            "outcome": "skipped",
            "reason": reason,
            "shadow_mode": shadow_mode,
            "override": False,
        }

    command = extract_test_command(output_text)
    if not command:
        return {
            "triggered": False,
            "outcome": "skipped",
            "reason": "no_test_command_extracted",
            "shadow_mode": shadow_mode,
            "override": False,
        }

    retry = run_verification_retry(command, budget_s=budget_s, cwd=cwd)
    retry["shadow_mode"] = shadow_mode
    retry["reason"] = "executed"
    retry["override"] = (retry["outcome"] == "success") and not shadow_mode
    return retry
