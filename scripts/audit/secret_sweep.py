#!/usr/bin/env python3
"""Secret sweep — scan workspace for leaked credentials.

Checks:
  1. Tracked files (git ls-files) for secret patterns
  2. File permissions on sensitive paths
  3. .gitignore coverage for credential files
  4. Environment variable leaks in scripts

Usage:
  python3 scripts/audit/secret_sweep.py          # full sweep
  python3 scripts/audit/secret_sweep.py --json    # machine-readable output
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
OPENCLAW_ROOT = WORKSPACE.parent  # /home/agent/.openclaw

# ── Secret patterns (regex, description) ──
# Known false-positive patterns (test fixtures, example keys)
FALSE_POSITIVE_VALUES = {
    "AKIAIOSFODNN7EXAMPLE",  # AWS documentation example key
}

# Files allowed to contain secret-like patterns (test fixtures)
ALLOWLISTED_FILES = {
    "tests/clarvis/test_secret_redaction.py",
}

SECRET_PATTERNS = [
    (r"sk-or-v1-[A-Za-z0-9]{64,}", "OpenRouter API key"),
    (r"sk-ant-[A-Za-z0-9\-]{40,}", "Anthropic API key"),
    (r"sk-proj-[A-Za-z0-9\-]{40,}", "OpenAI project key"),
    (r"sk-[A-Za-z0-9]{48,}", "OpenAI API key"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
    (r"ghp_[A-Za-z0-9]{36,}", "GitHub personal access token"),
    (r"ghs_[A-Za-z0-9]{36,}", "GitHub server token"),
    (r"xoxb-[0-9]{10,}-[A-Za-z0-9]+", "Slack bot token"),
    (r"xoxp-[0-9]{10,}-[A-Za-z0-9]+", "Slack user token"),
    (r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----", "Private key block"),
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API key"),
]

# ── Sensitive files to permission-check ──
SENSITIVE_FILES = [
    WORKSPACE / ".env",
    WORKSPACE / "data/browser_sessions/default_session.json",
    WORKSPACE / "data/budget_config.json",
    OPENCLAW_ROOT / "openclaw.json",
    OPENCLAW_ROOT / "agents/main/agent/auth.json",
]

# ── Files/dirs that .gitignore MUST cover ──
GITIGNORE_REQUIRED = [
    ".env",
    "*.key",
    "*.pem",
    "data/browser_sessions/",
    "agents/main/agent/auth.json",
]


def _git_tracked_files():
    """Return list of tracked files in workspace."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def scan_secrets():
    """Scan tracked files for secret patterns."""
    findings = []
    tracked = _git_tracked_files()
    for relpath in tracked:
        if relpath in ALLOWLISTED_FILES:
            continue
        fpath = WORKSPACE / relpath
        if not fpath.is_file():
            continue
        # Skip binary files
        if fpath.suffix in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
                            ".ttf", ".eot", ".db", ".sqlite3", ".gz", ".zip", ".tar"}:
            continue
        try:
            content = fpath.read_text(errors="ignore")
        except Exception:
            continue
        for pattern, desc in SECRET_PATTERNS:
            for match in re.finditer(pattern, content):
                value = match.group()
                if value in FALSE_POSITIVE_VALUES:
                    continue
                findings.append({
                    "file": relpath,
                    "type": desc,
                    "match_prefix": value[:20] + "...",
                    "line": content[:match.start()].count("\n") + 1,
                })
    return findings


def check_permissions():
    """Check file permissions on sensitive files."""
    findings = []
    for fpath in SENSITIVE_FILES:
        if not fpath.exists():
            findings.append({"file": str(fpath), "status": "MISSING", "mode": None})
            continue
        mode = oct(fpath.stat().st_mode & 0o777)
        is_ok = (fpath.stat().st_mode & 0o077) == 0  # no group/other access
        findings.append({
            "file": str(fpath),
            "status": "OK" if is_ok else "EXCESSIVE",
            "mode": mode,
            "recommendation": "0600" if not is_ok else None,
        })
    return findings


def check_gitignore():
    """Verify .gitignore covers required patterns."""
    findings = []
    gitignore = WORKSPACE / ".gitignore"
    if not gitignore.exists():
        return [{"pattern": "*", "status": "NO_GITIGNORE"}]
    content = gitignore.read_text()
    for pattern in GITIGNORE_REQUIRED:
        # Simple check: pattern appears somewhere in .gitignore
        if pattern in content or pattern.replace("/", "") in content:
            findings.append({"pattern": pattern, "status": "COVERED"})
        else:
            findings.append({"pattern": pattern, "status": "MISSING"})
    return findings


def check_listening_ports():
    """Check for services listening on 0.0.0.0 (all interfaces)."""
    findings = []
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 4:
                local = parts[3]
                if local.startswith("0.0.0.0:") or local.startswith("*:"):
                    port = local.split(":")[-1]
                    # Extract process name
                    proc = ""
                    if len(parts) >= 6:
                        proc_match = re.search(r'"([^"]+)"', parts[-1])
                        proc = proc_match.group(1) if proc_match else ""
                    findings.append({
                        "port": port,
                        "bind": "0.0.0.0",
                        "process": proc,
                        "status": "EXPOSED",
                    })
    except FileNotFoundError:
        findings.append({"error": "ss not found"})
    return findings


def main():
    json_mode = "--json" in sys.argv
    results = {
        "timestamp": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                     capture_output=True, text=True).stdout.strip(),
        "secrets_in_tracked_files": scan_secrets(),
        "file_permissions": check_permissions(),
        "gitignore_coverage": check_gitignore(),
        "exposed_ports": check_listening_ports(),
    }

    # Summary
    secret_count = len(results["secrets_in_tracked_files"])
    perm_issues = sum(1 for f in results["file_permissions"] if f["status"] == "EXCESSIVE")
    gitignore_gaps = sum(1 for f in results["gitignore_coverage"] if f["status"] == "MISSING")
    exposed_ports = sum(1 for f in results["exposed_ports"] if f.get("status") == "EXPOSED")

    results["summary"] = {
        "secrets_found": secret_count,
        "permission_issues": perm_issues,
        "gitignore_gaps": gitignore_gaps,
        "exposed_ports": exposed_ports,
        "overall": "PASS" if (secret_count == 0 and perm_issues == 0) else "FAIL",
    }

    if json_mode:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 60)
        print("  SECRET SWEEP REPORT")
        print(f"  {results['timestamp']}")
        print("=" * 60)

        print(f"\n🔑 Secrets in tracked files: {secret_count}")
        for f in results["secrets_in_tracked_files"]:
            print(f"  ⚠️  {f['file']}:{f['line']} — {f['type']} ({f['match_prefix']})")

        print(f"\n🔒 File permissions: {perm_issues} issue(s)")
        for f in results["file_permissions"]:
            icon = "✅" if f["status"] == "OK" else ("⚠️" if f["status"] == "EXCESSIVE" else "❌")
            extra = f" → should be {f['recommendation']}" if f.get("recommendation") else ""
            print(f"  {icon} {f['file']} [{f.get('mode', 'N/A')}] {f['status']}{extra}")

        print(f"\n📋 .gitignore coverage: {gitignore_gaps} gap(s)")
        for f in results["gitignore_coverage"]:
            icon = "✅" if f["status"] == "COVERED" else "⚠️"
            print(f"  {icon} {f['pattern']} — {f['status']}")

        print(f"\n🌐 Exposed ports (0.0.0.0): {exposed_ports}")
        for f in results["exposed_ports"]:
            if f.get("status") == "EXPOSED":
                print(f"  ⚠️  :{f['port']} — {f['process']}")

        print(f"\n{'=' * 60}")
        print(f"  OVERALL: {results['summary']['overall']}")
        print(f"{'=' * 60}")

    return 0 if results["summary"]["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
