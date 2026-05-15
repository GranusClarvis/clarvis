#!/usr/bin/env bash
# Clarvis pre-commit dispatcher (managed by `clarvis hooks install`).
# Runs every script under scripts/hooks/pre_commit_*.{py,sh} in lexical order.
# A non-zero exit from any one rejects the commit.
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
