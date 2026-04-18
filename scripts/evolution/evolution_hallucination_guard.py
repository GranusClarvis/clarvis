#!/usr/bin/env python3
"""
evolution_hallucination_guard.py — Validate file-path references in QUEUE.md items.

Scans QUEUE.md for unchecked task items (- [ ]) and verifies that any file/directory
paths referenced in the description actually exist on disk. Items with non-existent
paths are flagged with [UNVERIFIED] and logged.

Usage:
    python3 evolution_hallucination_guard.py [--queue FILE] [--workspace DIR]

Exit codes:
    0 — all paths verified (or no paths found)
    1 — one or more hallucinated paths detected and flagged
"""

import os
import re
import sys
import argparse
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
QUEUE_FILE = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE.md")
LOG_FILE = os.path.join(WORKSPACE, "monitoring", "evolution_hallucinations.log")

# Match paths like scripts/foo.py, clarvis/bar/baz.py, data/something.json
# Also matches absolute paths starting with /home/agent
PATH_PATTERN = re.compile(
    r'(?:^|[\s`\'"(])('
    r'(?:scripts|clarvis|data|memory|monitoring|docs|skills|packages)/[\w./\-]+'
    r'|/home/agent/[\w./\-]+'
    r')',
    re.MULTILINE,
)

# Patterns indicating the task intends to CREATE the referenced file
# (so it not existing yet is expected, not a hallucination)
CREATION_CONTEXT = re.compile(
    r'(?<!\w)(?:Create|Add|Write|Generate|Emit|Build|Produce|Ship|Wire .* into)\s+[`\'"]?(?:scripts|clarvis|data|memory|monitoring|docs)'
    r'|(?:Persist|log)\s+(?:\w+\s+){0,4}to\s+[`\'"]?(?:scripts|clarvis|data|memory|monitoring|docs)',
    re.IGNORECASE,
)

# Patterns indicating the path is cited as a known-bad reference (e.g. "stale paths")
STALE_CONTEXT = re.compile(
    r'(?:stale|pre-reorg|broken|old|dead|removed|missing)\s+(?:script\s+)?path',
    re.IGNORECASE,
)

# Match unchecked task lines
TASK_PATTERN = re.compile(r'^(\s*- \[ \] .+)$', re.MULTILINE)


def extract_paths(text: str) -> list[str]:
    """Extract file/directory path references from text."""
    matches = PATH_PATTERN.findall(text)
    # Clean trailing punctuation
    cleaned = []
    for m in matches:
        m = m.rstrip(".,;:)'\"")
        if m and len(m) > 5:  # skip very short matches
            cleaned.append(m)
    return cleaned


def validate_paths(paths: list[str], workspace: str) -> list[dict]:
    """Check each path against the filesystem. Returns list of {path, exists}."""
    results = []
    for p in paths:
        if p.startswith("/"):
            full = p
        else:
            full = os.path.join(workspace, p)
        exists = os.path.exists(full)
        results.append({"path": p, "full": full, "exists": exists})
    return results


def run(queue_file: str = QUEUE_FILE, workspace: str = WORKSPACE) -> dict:
    """
    Validate all file references in unchecked QUEUE.md items.

    Returns dict with:
        items_checked: number of task items scanned
        paths_checked: total path references found
        hallucinated: list of {task_line, bad_paths}
        flagged: number of items flagged with [UNVERIFIED]
    """
    with open(queue_file) as f:
        content = f.read()

    tasks = TASK_PATTERN.findall(content)
    hallucinated = []
    all_paths_checked = 0

    for task_line in tasks:
        # Skip items already flagged
        if "[UNVERIFIED]" in task_line:
            continue

        # Skip items that describe creating files (missing path is expected)
        if CREATION_CONTEXT.search(task_line):
            continue

        # Skip items that cite paths as known-stale references
        if STALE_CONTEXT.search(task_line):
            continue

        paths = extract_paths(task_line)
        if not paths:
            continue

        all_paths_checked += len(paths)
        results = validate_paths(paths, workspace)
        bad = [r for r in results if not r["exists"]]

        if bad:
            hallucinated.append({
                "task_line": task_line.strip(),
                "bad_paths": [r["path"] for r in bad],
            })

    # Flag hallucinated items in QUEUE.md
    flagged = 0
    if hallucinated:
        for h in hallucinated:
            old_line = h["task_line"]
            # Insert [UNVERIFIED] after the checkbox
            new_line = old_line.replace("- [ ] ", "- [ ] [UNVERIFIED] ", 1)
            content = content.replace(old_line, new_line, 1)
            flagged += 1

        with open(queue_file, "w") as f:
            f.write(content)

        # Log hallucinations
        _log_hallucinations(hallucinated)

    return {
        "items_checked": len(tasks),
        "paths_checked": all_paths_checked,
        "hallucinated": hallucinated,
        "flagged": flagged,
    }


def _log_hallucinations(hallucinated: list[dict]):
    """Append hallucination records to the monitoring log."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG_FILE, "a") as f:
        for h in hallucinated:
            f.write(f"[{ts}] BAD_PATHS={h['bad_paths']} TASK={h['task_line'][:200]}\n")


def main():
    parser = argparse.ArgumentParser(description="Validate file paths in QUEUE.md items")
    parser.add_argument("--queue", default=QUEUE_FILE, help="Path to QUEUE.md")
    parser.add_argument("--workspace", default=WORKSPACE, help="Workspace root")
    args = parser.parse_args()

    result = run(queue_file=args.queue, workspace=args.workspace)

    print(f"Items checked: {result['items_checked']}")
    print(f"Paths checked: {result['paths_checked']}")
    print(f"Hallucinated items: {len(result['hallucinated'])}")
    print(f"Flagged [UNVERIFIED]: {result['flagged']}")

    if result["hallucinated"]:
        for h in result["hallucinated"]:
            print(f"  BAD: {h['bad_paths']} in: {h['task_line'][:120]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
