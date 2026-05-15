"""clarvis hooks — install/manage git hooks for fresh checkouts.

Usage:
    clarvis hooks install            # Symlink .git/hooks/pre-commit to dispatcher
    clarvis hooks install --force    # Overwrite an existing hook
    clarvis hooks install --copy     # Copy instead of symlink (Windows-friendly)
    clarvis hooks list               # Show installed hooks
    clarvis hooks status             # Show health of installed hooks

The pre-commit dispatcher runs every script under `scripts/hooks/pre_commit_*.py`
in lexical order. A non-zero exit from any one rejects the commit. Currently:
  - pre_commit_queue_artifact_check.py — rejects `[x] [UNVERIFIED]` rows whose
    referenced artifacts do not exist on disk.
  - pre_commit_queue_orphan_tags.py — rejects QUEUE.md commits that introduce
    finding-style tags outside `- [ ]` / `- [x]` task rows.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


WORKSPACE = Path(
    os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
)


def _repo_root() -> Path:
    """Resolve the git repo root, falling back to CLARVIS_WORKSPACE."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            cwd=str(WORKSPACE),
        ).decode().strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return WORKSPACE


def _hooks_dir(root: Path) -> Path:
    """Return `.git/hooks/` honoring `core.hooksPath` if set."""
    try:
        out = subprocess.check_output(
            ["git", "config", "--get", "core.hooksPath"],
            stderr=subprocess.DEVNULL,
            cwd=str(root),
        ).decode().strip()
        if out:
            return (root / out).resolve() if not Path(out).is_absolute() else Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return root / ".git" / "hooks"


DISPATCHER_BODY = """#!/usr/bin/env bash
# Clarvis pre-commit dispatcher (managed by `clarvis hooks install`).
# Runs every executable script under scripts/hooks/pre_commit_*.{py,sh} in
# lexical order. A non-zero exit from any one rejects the commit.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
HOOK_DIR="$ROOT/scripts/hooks"

if [ ! -d "$HOOK_DIR" ]; then
    exit 0
fi

shopt -s nullglob
status=0
for hook in "$HOOK_DIR"/pre_commit_*.py "$HOOK_DIR"/pre_commit_*.sh; do
    [ -f "$hook" ] || continue
    case "$hook" in
        *.py) python3 "$hook" || status=$? ;;
        *.sh) bash "$hook"    || status=$? ;;
    esac
    if [ "$status" -ne 0 ]; then
        echo "clarvis pre-commit: $hook rejected the commit (exit $status)" >&2
        exit "$status"
    fi
done

exit 0
"""


@app.command("install")
def install(
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite an existing pre-commit hook."
    ),
    copy: bool = typer.Option(
        False, "--copy", help="Copy the dispatcher instead of symlinking."
    ),
    symlink_single: Optional[str] = typer.Option(
        None,
        "--symlink",
        help=(
            "Skip the dispatcher and symlink .git/hooks/pre-commit directly to a "
            "single hook script (relative to scripts/hooks/). Used when only one "
            "hook should run on commit."
        ),
    ),
) -> None:
    """Install the Clarvis pre-commit dispatcher into `.git/hooks/`.

    By default writes a bash dispatcher that runs every script under
    `scripts/hooks/pre_commit_*.{py,sh}`. Use `--symlink NAME` to bypass the
    dispatcher and link straight to one script (matches the original ask for
    `[CLARVIS_PROC_QUEUE_ARTIFACT_HOOK]`).
    """
    root = _repo_root()
    hooks_dir = _hooks_dir(root)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    target = hooks_dir / "pre-commit"

    if target.exists() or target.is_symlink():
        if not force:
            typer.echo(
                f"clarvis hooks: {target} already exists. Re-run with --force "
                "to overwrite.",
                err=True,
            )
            raise typer.Exit(code=1)
        target.unlink()

    if symlink_single is not None:
        script = root / "scripts" / "hooks" / symlink_single
        if not script.exists():
            typer.echo(f"clarvis hooks: {script} does not exist", err=True)
            raise typer.Exit(code=2)
        target.symlink_to(script.resolve())
        typer.echo(f"clarvis hooks: symlinked {target} -> {script}")
        return

    dispatcher = root / "scripts" / "hooks" / "_pre_commit_dispatcher.sh"
    if not dispatcher.exists():
        # Bootstrap fallback for old checkouts that predate the committed dispatcher.
        dispatcher.write_text(DISPATCHER_BODY, encoding="utf-8")
    dispatcher.chmod(
        dispatcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    )

    if copy:
        shutil.copy(dispatcher, target)
        target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    else:
        target.symlink_to(dispatcher.resolve())

    typer.echo(f"clarvis hooks: installed pre-commit dispatcher at {target}")


@app.command("list")
def list_cmd() -> None:
    """List hooks discovered under `scripts/hooks/`."""
    root = _repo_root()
    hook_dir = root / "scripts" / "hooks"
    if not hook_dir.exists():
        typer.echo(f"clarvis hooks: {hook_dir} does not exist", err=True)
        raise typer.Exit(code=1)
    found = sorted(
        list(hook_dir.glob("pre_commit_*.py")) + list(hook_dir.glob("pre_commit_*.sh"))
    )
    if not found:
        typer.echo("clarvis hooks: no pre_commit_* scripts found")
        return
    for h in found:
        typer.echo(f"  {h.relative_to(root)}")


@app.command("status")
def status() -> None:
    """Report whether `.git/hooks/pre-commit` is wired to Clarvis."""
    root = _repo_root()
    hooks_dir = _hooks_dir(root)
    target = hooks_dir / "pre-commit"
    if not (target.exists() or target.is_symlink()):
        typer.echo("clarvis hooks: NOT INSTALLED — run `clarvis hooks install`", err=True)
        raise typer.Exit(code=1)
    resolved = target.resolve() if target.is_symlink() else target
    typer.echo(f"clarvis hooks: pre-commit -> {resolved}")


if __name__ == "__main__":
    app()
