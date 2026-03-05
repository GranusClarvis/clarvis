#!/usr/bin/env python3
"""dead_code_audit.py — Static scan for unused scripts.

Identifies scripts that are never imported, never referenced by cron,
not used by skills, and not documented as entrypoints.

A script is "exercised" if ANY of:
  1. Referenced by system crontab (`crontab -l`)
  2. Imported by another non-deprecated script
  3. Referenced in an OpenClaw skill (skills/*/SKILL.md)
  4. Referenced in CLAUDE.md, AGENTS.md, HEARTBEAT.md, SELF.md, BOOT.md, RUNBOOK.md
  5. Has `if __name__ == "__main__"` AND is invoked by a cron .sh wrapper
  6. Referenced in openclaw.json or cron/jobs.json
  7. Referenced by clarvis/ spine package (imported or delegated to)

Otherwise: candidate for deprecated/ (recommend 7-day soak).

Usage:
    python3 scripts/dead_code_audit.py              # Full audit
    python3 scripts/dead_code_audit.py --json        # JSON output
    python3 scripts/dead_code_audit.py --exercised   # Show only exercised scripts
"""

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/home/agent/.openclaw/workspace")
SCRIPTS_DIR = WORKSPACE / "scripts"
OPENCLAW_ROOT = Path("/home/agent/.openclaw")

# Documentation files to scan for references
DOC_FILES = [
    WORKSPACE / "CLAUDE.md",
    WORKSPACE / "AGENTS.md",
    WORKSPACE / "HEARTBEAT.md",
    WORKSPACE / "SELF.md",
    WORKSPACE / "BOOT.md",
    WORKSPACE / "SOUL.md",
    WORKSPACE / "ROADMAP.md",
]

# Config files
CONFIG_FILES = [
    OPENCLAW_ROOT / "openclaw.json",
    OPENCLAW_ROOT / "cron" / "jobs.json",
]


def get_all_scripts() -> list[Path]:
    """Get all .py files in scripts/ (not subdirs)."""
    return sorted(SCRIPTS_DIR.glob("*.py"))


def get_crontab_refs() -> set[str]:
    """Extract script references from system crontab."""
    refs = set()
    try:
        output = subprocess.check_output(["crontab", "-l"], text=True, stderr=subprocess.DEVNULL)
        for line in output.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            # Match .py and .sh filenames
            for m in re.finditer(r'[\w/.-]*scripts/([\w.-]+\.(?:py|sh))', line):
                refs.add(m.group(1))
            # Also check for script names without full path
            for m in re.finditer(r'\b(\w+\.(?:py|sh))\b', line):
                refs.add(m.group(1))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return refs


def get_import_refs(script: Path, all_script_names: set[str]) -> set[str]:
    """Find which other scripts this script imports."""
    refs = set()
    try:
        content = script.read_text()
    except Exception:
        return refs

    # Match: from X import ..., import X
    for m in re.finditer(r'(?:from|import)\s+([\w.]+)', content):
        module = m.group(1).split('.')[0]
        if f"{module}.py" in all_script_names:
            refs.add(f"{module}.py")

    return refs


def get_cron_sh_refs() -> set[str]:
    """Find .py scripts referenced inside cron .sh wrappers."""
    refs = set()
    for sh in SCRIPTS_DIR.glob("cron_*.sh"):
        try:
            content = sh.read_text()
            for m in re.finditer(r'([\w]+\.py)', content):
                refs.add(m.group(1))
        except Exception:
            pass
    # Also check standalone shell scripts
    for sh in SCRIPTS_DIR.glob("*.sh"):
        try:
            content = sh.read_text()
            for m in re.finditer(r'([\w]+\.py)', content):
                refs.add(m.group(1))
        except Exception:
            pass
    return refs


def get_doc_refs() -> set[str]:
    """Find script references in documentation files."""
    refs = set()
    for doc in DOC_FILES:
        if not doc.exists():
            continue
        try:
            content = doc.read_text()
            # Match script_name.py references
            for m in re.finditer(r'\b([\w]+\.py)\b', content):
                refs.add(m.group(1))
        except Exception:
            pass
    return refs


def get_skill_refs() -> set[str]:
    """Find script references in OpenClaw skills."""
    refs = set()
    skills_dir = WORKSPACE / "skills"
    if not skills_dir.exists():
        return refs
    for skill_md in skills_dir.rglob("SKILL.md"):
        try:
            content = skill_md.read_text()
            for m in re.finditer(r'\b([\w]+\.py)\b', content):
                refs.add(m.group(1))
        except Exception:
            pass
    return refs


def get_config_refs() -> set[str]:
    """Find script references in config files."""
    refs = set()
    for cfg in CONFIG_FILES:
        if not cfg.exists():
            continue
        try:
            content = cfg.read_text()
            for m in re.finditer(r'\b([\w]+\.py)\b', content):
                refs.add(m.group(1))
        except Exception:
            pass
    return refs


def get_spine_refs() -> set[str]:
    """Find scripts referenced/imported by clarvis/ spine package."""
    refs = set()
    clarvis_dir = WORKSPACE / "clarvis"
    if not clarvis_dir.exists():
        return refs
    for py in clarvis_dir.rglob("*.py"):
        try:
            content = py.read_text()
            # Direct imports from scripts
            for m in re.finditer(r'(?:from|import)\s+([\w.]+)', content):
                module = m.group(1).split('.')[0]
                refs.add(f"{module}.py")
            # String references to script names
            for m in re.finditer(r'["\'](\w+\.py)["\']', content):
                refs.add(m.group(1))
        except Exception:
            pass
    return refs


def get_cross_imports(all_scripts: list[Path]) -> dict[str, set[str]]:
    """Build import graph: which scripts import which other scripts."""
    all_names = {s.name for s in all_scripts}
    graph = {}
    for script in all_scripts:
        imported_by = get_import_refs(script, all_names)
        graph[script.name] = imported_by
    return graph


def get_last_git_touch(script: Path) -> str:
    """Get the last git commit date for a script."""
    try:
        output = subprocess.check_output(
            ["git", "log", "-1", "--format=%ci", "--", str(script)],
            cwd=WORKSPACE, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return output[:10] if output else "unknown"
    except Exception:
        return "unknown"


def run_audit(show_json: bool = False, show_exercised: bool = False):
    """Run the full dead code audit."""
    all_scripts = get_all_scripts()
    all_names = {s.name for s in all_scripts}

    # Gather all reference sources
    crontab_refs = get_crontab_refs()
    cron_sh_refs = get_cron_sh_refs()
    doc_refs = get_doc_refs()
    skill_refs = get_skill_refs()
    config_refs = get_config_refs()
    spine_refs = get_spine_refs()
    import_graph = get_cross_imports(all_scripts)

    # Build reverse import map: which scripts are imported by others
    imported_by_others = set()
    for script_name, imports in import_graph.items():
        imported_by_others.update(imports)

    results = []

    for script in all_scripts:
        name = script.name
        reasons = []

        if name in crontab_refs:
            reasons.append("crontab")
        if name in cron_sh_refs:
            reasons.append("cron_sh_wrapper")
        if name in imported_by_others:
            reasons.append("imported_by_script")
        if name in doc_refs:
            reasons.append("documented")
        if name in skill_refs:
            reasons.append("skill_ref")
        if name in config_refs:
            reasons.append("config_ref")
        if name in spine_refs:
            reasons.append("spine_ref")

        exercised = len(reasons) > 0
        last_touch = get_last_git_touch(script)

        results.append({
            "script": name,
            "exercised": exercised,
            "reasons": reasons,
            "last_git_touch": last_touch,
        })

    # Sort: unexercised first, then by last_touch ascending (oldest first)
    exercised = [r for r in results if r["exercised"]]
    candidates = [r for r in results if not r["exercised"]]
    candidates.sort(key=lambda r: r["last_git_touch"])
    exercised.sort(key=lambda r: r["script"])

    if show_json:
        print(json.dumps(results, indent=2))
        return

    if show_exercised:
        print(f"=== Exercised Scripts ({len(exercised)}/{len(results)}) ===\n")
        for r in exercised:
            print(f"  {r['script']:40s} [{', '.join(r['reasons'])}]")
        return

    # Default output: show candidates for deprecation
    print(f"=== Dead Code Audit ({datetime.now().strftime('%Y-%m-%d')}) ===")
    print(f"Total scripts: {len(results)}")
    print(f"Exercised: {len(exercised)}")
    print(f"Candidates for deprecation: {len(candidates)}\n")

    if candidates:
        print("--- Deprecation Candidates (recommend 7-day soak) ---\n")
        for r in candidates:
            print(f"  {r['script']:40s} last touched: {r['last_git_touch']}")
        print(f"\n  Total: {len(candidates)} scripts")
        print("  Action: Move to scripts/deprecated/ after 7-day soak.")
        print("  Re-run audit after soak to confirm still unused.")
    else:
        print("No candidates — all scripts are exercised.")

    print(f"\n--- Exercised ({len(exercised)}) ---\n")
    for r in exercised:
        print(f"  {r['script']:40s} [{', '.join(r['reasons'])}]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dead code audit for scripts/")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--exercised", action="store_true", help="Show only exercised scripts")
    args = parser.parse_args()
    run_audit(show_json=args.json, show_exercised=args.exercised)
