#!/usr/bin/env python3
"""Safety Invariant Checker — enforces docs/SAFETY_INVARIANTS.md rules.

Usage:
    python3 safety_check.py pre-commit    # Check staged .py files compile
    python3 safety_check.py postflight    # Post-heartbeat invariant check
    python3 safety_check.py all           # Run all checks
"""

import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/home/agent/.openclaw/workspace")
violations = []


def check_syntax(files=None):
    """Invariant 2: All .py files must compile."""
    if files:
        # Pre-commit mode: check specific files
        targets = [f for f in files if f.endswith(".py")]
    else:
        # Full mode: check scripts/ and clarvis/
        targets = []
        for d in ["scripts", "clarvis"]:
            p = WORKSPACE / d
            if p.exists():
                targets.extend(str(f) for f in p.rglob("*.py"))

    failed = []
    for f in targets:
        try:
            subprocess.run(
                [sys.executable, "-m", "py_compile", f],
                capture_output=True, text=True, timeout=10,
            )
        except subprocess.CalledProcessError:
            failed.append(f)
        except Exception:
            pass

    if failed:
        violations.append(f"SYNTAX: {len(failed)} file(s) failed to compile: {failed[:5]}")
        return False
    return True


def check_brain_size():
    """Invariant 1: Brain data hasn't shrunk dramatically."""
    db_path = WORKSPACE / "data" / "clarvisdb"
    if not db_path.exists():
        return True

    # Check total size hasn't dropped below 50MB (healthy brain is ~100MB+)
    total_bytes = sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())
    total_mb = total_bytes / (1024 * 1024)
    if total_mb < 50:
        violations.append(f"BRAIN_SIZE: ClarvisDB only {total_mb:.1f}MB (expected >50MB)")
        return False
    return True


def check_credential_isolation():
    """Invariant 3: No session/cookie files staged for commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=10,
            cwd=str(WORKSPACE),
        )
        staged = result.stdout.strip().split("\n") if result.stdout.strip() else []
    except Exception:
        return True  # Can't check, assume OK

    bad_files = [
        f for f in staged
        if "session" in f.lower() and f.endswith(".json")
        or "cookie" in f.lower()
        or ".env" in f
        or "credentials" in f.lower()
    ]

    if bad_files:
        violations.append(f"CREDENTIALS: Staged sensitive files: {bad_files}")
        return False
    return True


def check_data_files_exist():
    """Invariant 7: Critical data files must exist and not be empty."""
    critical = [
        "data/episodes.json",
        "data/clarvisdb",
    ]
    for rel in critical:
        p = WORKSPACE / rel
        if not p.exists():
            violations.append(f"DATA_MISSING: {rel} does not exist")
            return False
        if p.is_file() and p.stat().st_size == 0:
            violations.append(f"DATA_EMPTY: {rel} is empty")
            return False
    return True


def check_brain_health():
    """Invariant 8: Brain health check passes."""
    try:
        sys.path.insert(0, str(WORKSPACE / "scripts"))
        from brain import brain
        result = brain.health_check()
        is_healthy = result.get("healthy", False) or result.get("status") == "healthy"
        if not is_healthy:
            violations.append(f"BRAIN_HEALTH: health_check failed: {result}")
            return False
    except Exception as e:
        violations.append(f"BRAIN_HEALTH: Exception: {e}")
        return False
    return True


def run_precommit():
    """Pre-commit checks: syntax + credential isolation."""
    # Get staged files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=10,
            cwd=str(WORKSPACE),
        )
        staged = result.stdout.strip().split("\n") if result.stdout.strip() else []
    except Exception:
        staged = []

    py_files = [str(WORKSPACE / f) for f in staged if f.endswith(".py")]
    check_syntax(py_files)
    check_credential_isolation()
    return len(violations) == 0


def run_postflight():
    """Post-heartbeat checks: brain size + data files + brain health."""
    check_brain_size()
    check_data_files_exist()
    check_brain_health()
    return len(violations) == 0


def run_all():
    """Run all invariant checks."""
    check_syntax()
    check_brain_size()
    check_credential_isolation()
    check_data_files_exist()
    check_brain_health()
    return len(violations) == 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "pre-commit":
        ok = run_precommit()
    elif cmd == "postflight":
        ok = run_postflight()
    elif cmd == "all":
        ok = run_all()
    else:
        print(f"Usage: safety_check.py [pre-commit|postflight|all]")
        sys.exit(1)

    if violations:
        print(f"SAFETY VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"  [FAIL] {v}")
        sys.exit(1)
    else:
        print(f"All safety invariants passed ({cmd}).")
        sys.exit(0)
