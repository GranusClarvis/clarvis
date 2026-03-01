#!/usr/bin/env python3
"""PR Auto-Fix — Reads GitHub PR review comments, spawns Claude Code to fix them.

Usage:
    python3 pr_autofix.py <pr_number>           # Fix all unresolved comments
    python3 pr_autofix.py <pr_number> --dry-run  # Show what would be fixed
    python3 pr_autofix.py <pr_number> --isolated  # Fix in worktree isolation

Workflow:
    1. Fetch PR review comments via `gh` CLI
    2. Group by file + context
    3. Build a focused fix prompt per comment group
    4. Spawn Claude Code (via agent_lifecycle) to apply fixes
    5. Report results

Requires: gh CLI authenticated with repo access.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

WORKSPACE = Path("/home/agent/.openclaw/workspace")
LOGFILE = WORKSPACE / "memory" / "cron" / "pr_autofix.log"


def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] [pr_autofix] {msg}"
    print(line, file=sys.stderr)
    try:
        with open(LOGFILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _run_gh(args: list[str]) -> str:
    """Run gh CLI command, return stdout."""
    result = subprocess.run(
        ["gh"] + args,
        cwd=str(WORKSPACE),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        _log(f"gh error: {result.stderr.strip()}")
        return ""
    return result.stdout


def fetch_pr_comments(pr_number: int) -> list[dict]:
    """Fetch all review comments on a PR."""
    # Get review comments (line-level)
    raw = _run_gh([
        "api", f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
        "--paginate", "--jq",
        '.[] | {id: .id, path: .path, line: .line, side: .side, '
        'body: .body, diff_hunk: .diff_hunk, user: .user.login, '
        'created_at: .created_at, in_reply_to_id: .in_reply_to_id, '
        'position: .position, original_line: .original_line, '
        'subject_type: .subject_type}'
    ])

    if not raw.strip():
        return []

    comments = []
    for line in raw.strip().split("\n"):
        if line.strip():
            try:
                comments.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return comments


def fetch_pr_issue_comments(pr_number: int) -> list[dict]:
    """Fetch general PR comments (not line-level)."""
    raw = _run_gh([
        "api", f"repos/{{owner}}/{{repo}}/issues/{pr_number}/comments",
        "--paginate", "--jq",
        '.[] | {id: .id, body: .body, user: .user.login, created_at: .created_at}'
    ])

    if not raw.strip():
        return []

    comments = []
    for line in raw.strip().split("\n"):
        if line.strip():
            try:
                comments.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return comments


def group_by_file(comments: list[dict]) -> dict[str, list[dict]]:
    """Group review comments by file path."""
    groups: dict[str, list[dict]] = {}
    for c in comments:
        path = c.get("path", "_general")
        if path not in groups:
            groups[path] = []
        groups[path].append(c)
    return groups


def is_actionable(comment: dict) -> bool:
    """Filter to comments that look like requested changes (not just discussion)."""
    body = (comment.get("body") or "").lower()

    # Skip bot comments, approvals, simple acknowledgements
    skip_patterns = [
        "lgtm", "looks good", "approved", "nice work", "thanks",
        "nit:", "minor:", "optional:",  # nits are low priority but we keep them
    ]

    # These patterns suggest actionable feedback
    action_patterns = [
        "should", "could you", "please", "fix", "change", "rename",
        "remove", "add", "use", "consider", "instead", "missing",
        "wrong", "bug", "error", "typo", "unused", "todo",
        "refactor", "simplify", "move", "extract", "replace",
    ]

    # If reply to another comment, it might be discussion — still include
    # but prioritize root comments
    if any(p in body for p in skip_patterns[:5]):  # approval patterns
        return False

    if any(p in body for p in action_patterns):
        return True

    # Default: include if it has a file path (it's a line comment with context)
    return bool(comment.get("path"))


def build_fix_prompt(pr_number: int, file_groups: dict[str, list[dict]],
                     general_comments: list[dict]) -> str:
    """Build a prompt for Claude Code to fix all review comments."""

    sections = []
    sections.append(
        f"You are fixing PR review comments on PR #{pr_number}.\n"
        f"Read each file mentioned, understand the review comment, and apply the fix.\n"
        f"After fixing, stage the changed files with `git add`.\n"
        f"Do NOT create a new commit — just stage the fixes.\n"
    )

    # File-level comments
    for path, comments in file_groups.items():
        if path == "_general":
            continue
        section = f"\n### File: {path}\n"
        for c in comments:
            line = c.get("line") or c.get("original_line") or "?"
            body = c.get("body", "").strip()
            hunk = c.get("diff_hunk", "")
            section += f"\n**Line {line}** ({c.get('user', 'reviewer')}):\n"
            if hunk:
                # Show last 5 lines of diff hunk for context
                hunk_lines = hunk.strip().split("\n")[-5:]
                section += "```diff\n" + "\n".join(hunk_lines) + "\n```\n"
            section += f"Comment: {body}\n"
        sections.append(section)

    # General comments
    actionable_general = [c for c in general_comments if is_actionable(c)]
    if actionable_general:
        section = "\n### General PR Comments\n"
        for c in actionable_general:
            section += f"\n({c.get('user', 'reviewer')}): {c.get('body', '').strip()}\n"
        sections.append(section)

    sections.append(
        "\n### Instructions\n"
        "1. Read each mentioned file\n"
        "2. Apply the requested fix for each comment\n"
        "3. Stage fixes with `git add <file>`\n"
        "4. Do NOT commit — just stage\n"
        "5. Report what you fixed in a concise summary\n"
    )

    return "\n".join(sections)


def spawn_fix(prompt: str, isolated: bool = False, timeout: int = 900) -> dict:
    """Spawn Claude Code to apply fixes."""
    from agent_lifecycle import cmd_spawn

    task = f"[PR-AUTOFIX] {prompt[:200]}"
    return cmd_spawn(task, timeout=timeout, isolated=isolated)


def run_fix_inline(prompt: str, timeout: int = 900) -> tuple[int, str]:
    """Run Claude Code inline (blocking) to apply fixes. Returns (exit_code, output)."""
    prompt_file = f"/tmp/pr_autofix_{os.getpid()}.txt"
    output_file = f"/tmp/pr_autofix_{os.getpid()}_out.txt"

    Path(prompt_file).write_text(prompt)

    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}

    cmd = [
        "timeout", str(timeout),
        "env", "-u", "CLAUDECODE", "-u", "CLAUDE_CODE_ENTRYPOINT",
        "/home/agent/.local/bin/claude",
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--model", "claude-opus-4-6"
    ]

    with open(output_file, "w") as out_f:
        result = subprocess.run(
            cmd,
            stdout=out_f,
            stderr=subprocess.STDOUT,
            cwd=str(WORKSPACE),
            env=env
        )

    output = ""
    if os.path.exists(output_file):
        output = Path(output_file).read_text()
        os.remove(output_file)
    os.remove(prompt_file) if os.path.exists(prompt_file) else None

    return result.returncode, output


def main():
    parser = argparse.ArgumentParser(description="Auto-fix PR review comments")
    parser.add_argument("pr_number", type=int, help="PR number to fix")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show prompt without executing")
    parser.add_argument("--isolated", action="store_true",
                        help="Run in git worktree isolation")
    parser.add_argument("--timeout", type=int, default=900,
                        help="Timeout in seconds (default 900)")
    parser.add_argument("--background", action="store_true",
                        help="Spawn as background agent")
    args = parser.parse_args()

    _log(f"Fetching comments for PR #{args.pr_number}")

    # Fetch comments
    review_comments = fetch_pr_comments(args.pr_number)
    general_comments = fetch_pr_issue_comments(args.pr_number)

    # Filter to actionable
    actionable_review = [c for c in review_comments if is_actionable(c)]
    actionable_general = [c for c in general_comments if is_actionable(c)]

    total = len(actionable_review) + len(actionable_general)
    _log(f"Found {len(review_comments)} review comments ({len(actionable_review)} actionable)")
    _log(f"Found {len(general_comments)} general comments ({len(actionable_general)} actionable)")

    if total == 0:
        print("No actionable review comments found.")
        return

    # Group and build prompt
    file_groups = group_by_file(actionable_review)
    prompt = build_fix_prompt(args.pr_number, file_groups, general_comments)

    if args.dry_run:
        print("=== DRY RUN — Would send this prompt to Claude Code ===\n")
        print(prompt)
        print(f"\n=== {total} comments to fix across {len(file_groups)} files ===")
        return

    print(f"Fixing {total} comments across {len(file_groups)} files...")

    if args.background:
        result = spawn_fix(prompt, isolated=args.isolated, timeout=args.timeout)
        print(f"Agent spawned: {result['id']} (pid={result['pid']})")
        print(f"Track with: python3 scripts/agent_lifecycle.py status {result['id']}")
    else:
        exit_code, output = run_fix_inline(prompt, timeout=args.timeout)
        if exit_code == 0:
            print("Fixes applied successfully!")
        elif exit_code == 124:
            print("TIMEOUT — some fixes may be incomplete")
        else:
            print(f"Failed with exit code {exit_code}")

        # Show summary (last 1000 chars)
        if output:
            print("\n--- Output ---")
            print(output[-1000:])


if __name__ == "__main__":
    main()
