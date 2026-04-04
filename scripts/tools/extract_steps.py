#!/usr/bin/env python3
"""
Extract concrete procedural steps from Claude Code task output.

Parses the 1-line summary that Claude produces after completing a task and
extracts the actual actions taken, NOT generic templates.

Returns JSON list of steps, or empty list if extraction fails or steps
look too generic to be useful.

Usage:
    python3 extract_steps.py "Built procedural memory: created scripts/procedural_memory.py..."
    python3 extract_steps.py --file /tmp/task_output.txt
"""

import sys
import json
import re

# Generic phrases that indicate a template, not real steps
# NOTE: These must be specific enough to avoid rejecting concrete steps like
# "tested via python3 foo.py" or "verified brain connectivity". Use end anchors
# and require generic follow-on words to avoid false positives.
GENERIC_PATTERNS = [
    r"^read (context|requirements|the existing)$",
    r"^implement (the )?solution$",
    r"^test end.to.end$",
    r"^verify (and commit|results?|output)$",
    r"^analyze (the )?requirements$",
    r"^write (the )?code$",
    r"^deploy (to production|the changes?)$",
    r"^review (the )?results?$",
]

GENERIC_RE = [re.compile(p, re.IGNORECASE) for p in GENERIC_PATTERNS]

# Minimum quality bar for a step
MIN_STEP_LENGTH = 10  # steps shorter than this are likely too vague
MIN_STEPS = 2
MAX_STEPS = 8


def is_generic(step: str) -> bool:
    """Check if a step looks like a generic template."""
    step_lower = step.strip().lower()
    for pat in GENERIC_RE:
        if pat.search(step_lower):
            return True
    # Also reject very short steps as likely generic
    if len(step.strip()) < MIN_STEP_LENGTH:
        return True
    return False


def extract_steps(output_text: str) -> list[str]:
    """Extract concrete steps from Claude Code task output.

    Strategies (tried in order):
    1. Look for numbered lists (1. ..., 2. ...)
    2. Look for action verbs with specific objects separated by commas/semicolons
    3. Parse "verb + object" chains from summary sentences

    Returns empty list if steps look too generic.
    """
    if not output_text or len(output_text.strip()) < 20:
        return []

    text = output_text.strip()

    # Strategy 1: Look for numbered steps
    numbered = re.findall(r'(?:^|\n)\s*\d+[.)]\s*(.+)', text)
    if len(numbered) >= MIN_STEPS:
        steps = [s.strip().rstrip('.') for s in numbered if len(s.strip()) > 10]
        if steps and not _mostly_generic(steps):
            return steps[:MAX_STEPS]

    # Strategy 2: Split on action-delimiters in summary lines
    # Claude summaries look like: "created X, added Y, wired Z into W, tested end-to-end"
    # or "created X — added Y — wired Z"
    steps = _extract_from_summary(text)
    if len(steps) >= MIN_STEPS and not _mostly_generic(steps):
        return steps[:MAX_STEPS]

    return []


def _extract_from_summary(text: str) -> list[str]:
    """Extract steps from a comma/semicolon/dash-separated summary."""
    # Take the last substantial line (usually the summary)
    lines = [l.strip() for l in text.strip().split('\n') if len(l.strip()) > 30]
    if not lines:
        return []

    summary = lines[-1]

    # Split on common delimiters in Claude summaries
    # Pattern: "verb1 X, verb2 Y, verb3 Z" or "verb1 X; verb2 Y" or "verb1 X — verb2 Y"
    # First try semicolons
    parts = re.split(r'\s*;\s*', summary)
    if len(parts) < MIN_STEPS:
        # Try " — " (em-dash with spaces)
        parts = re.split(r'\s+[—–]\s+', summary)
    if len(parts) < MIN_STEPS:
        # Try commas, but only split on commas before action verbs
        parts = _split_on_action_commas(summary)

    # Filter to actual action items
    action_verbs = re.compile(
        r'^(created|added|built|fixed|wired|modified|updated|implemented|'
        r'replaced|removed|rewrote|integrated|stored|tested|verified|'
        r'diagnosed|raised|ran|found|detected|marked|checked|'
        r'configured|enabled|disabled|moved|renamed|refactored|'
        r'now\s+\w+|first\s+\w+)',
        re.IGNORECASE
    )

    steps = []
    for part in parts:
        part = part.strip().rstrip('.')
        if not part:
            continue
        # Keep if it starts with an action verb or has specific content
        if action_verbs.match(part) and len(part) >= MIN_STEP_LENGTH:
            # Capitalize first letter
            step = part[0].upper() + part[1:]
            steps.append(step)

    return steps


def _split_on_action_commas(text: str) -> list[str]:
    """Split on commas that precede action verbs."""
    verbs = (
        r'created|added|built|fixed|wired|modified|updated|implemented|'
        r'replaced|removed|rewrote|integrated|stored|tested|verified|'
        r'diagnosed|raised|ran|found|detected|marked|checked|now\s'
    )
    # Split on ", <verb>" pattern
    parts = re.split(rf',\s*(?=(?:{verbs}))', text, flags=re.IGNORECASE)
    return parts


def _mostly_generic(steps: list[str]) -> bool:
    """Check if more than half the steps are generic."""
    if not steps:
        return True
    generic_count = sum(1 for s in steps if is_generic(s))
    return generic_count > len(steps) / 2


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extract_steps.py <output_text>")
        print("       extract_steps.py --file <path>")
        sys.exit(1)

    if sys.argv[1] == "--file":
        filepath = sys.argv[2] if len(sys.argv) > 2 else ""
        try:
            with open(filepath) as f:
                text = f.read()
        except (FileNotFoundError, IOError):
            print("[]")
            sys.exit(0)
    else:
        text = " ".join(sys.argv[1:])

    steps = extract_steps(text)
    print(json.dumps(steps))
