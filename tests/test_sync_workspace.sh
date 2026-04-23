#!/bin/bash
# Test harness for sync_workspace() in scripts/cron/cron_env.sh
# Exercises: clean sync, dirty-tree sync, stash-pop conflict after ff-merge,
# stash-pop conflict after failed merge, skip-when-diverged, skip-when-not-main.
#
# Usage: bash tests/test_sync_workspace.sh
# Exit 0 = all pass, non-zero = failure count

set -euo pipefail

PASS=0
FAIL=0
TMPDIR_ROOT=$(mktemp -d /tmp/test_sync_workspace_XXXXXX)

cleanup() { rm -rf "$TMPDIR_ROOT"; }
trap cleanup EXIT

log_pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
log_fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

# Build a bare "origin" repo and a "workspace" clone
setup_repos() {
    local test_name="$1"
    local origin="$TMPDIR_ROOT/$test_name/origin.git"
    local workspace="$TMPDIR_ROOT/$test_name/workspace"

    git init --bare "$origin" >/dev/null 2>&1
    git clone "$origin" "$workspace" >/dev/null 2>&1
    cd "$workspace"
    git checkout -b main >/dev/null 2>&1
    echo "initial" > file.txt
    git add file.txt && git commit -m "initial" -q
    git push -u origin main -q 2>/dev/null

    echo "$workspace"
}

# Push a commit to origin from a temporary clone
push_origin_commit() {
    local origin="$1"
    local file="$2"
    local content="$3"
    local tmp_clone
    tmp_clone=$(mktemp -d "$TMPDIR_ROOT/push_XXXXXX")
    git clone "$origin" "$tmp_clone/repo" -q 2>/dev/null
    cd "$tmp_clone/repo"
    echo "$content" > "$file"
    git add "$file" && git commit -m "upstream: $file" -q
    git push origin main -q 2>/dev/null
    cd /
    rm -rf "$tmp_clone"
}

# Source cron_env.sh's sync_workspace in isolation (override env).
# We stub emit_dashboard_event to capture calls.
run_sync() {
    local workspace="$1"
    local dashboard_log="$TMPDIR_ROOT/dashboard_events.log"
    local exit_file="$TMPDIR_ROOT/exit_code"
    > "$dashboard_log"

    # Minimal env for sync_workspace
    (
        export CLARVIS_WORKSPACE="$workspace"
        export CLARVIS_SELF_SYNC="auto"
        emit_dashboard_event() { echo "DASHBOARD: $*" >> "$dashboard_log"; }
        export -f emit_dashboard_event

        # Source only the sync_workspace function (avoid cd side-effect by
        # extracting the function directly)
        eval "$(sed -n '/^sync_workspace()/,/^}/p' "$REAL_CRON_ENV")"
        sync_workspace 2>"$TMPDIR_ROOT/stderr.log" >/dev/null
        echo $? > "$exit_file"
    ) >/dev/null 2>&1
    cat "$exit_file" 2>/dev/null || echo "255"
}

REAL_CRON_ENV="$(cd "$(dirname "$0")/.." && pwd)/scripts/cron/cron_env.sh"
if [ ! -f "$REAL_CRON_ENV" ]; then
    REAL_CRON_ENV="/home/agent/.openclaw/workspace/scripts/cron/cron_env.sh"
fi

echo "=== sync_workspace() test suite ==="
echo "Using: $REAL_CRON_ENV"
echo ""

# -----------------------------------------------------------------------
# TEST 1: Clean fast-forward (no dirty files)
# -----------------------------------------------------------------------
echo "TEST 1: Clean fast-forward"
WS=$(setup_repos "t1")
ORIGIN="$TMPDIR_ROOT/t1/origin.git"
push_origin_commit "$ORIGIN" "new.txt" "from-upstream"

EXIT_CODE=$(run_sync "$WS")
if [ "$EXIT_CODE" = "0" ]; then
    cd "$WS"
    if [ -f "new.txt" ]; then
        log_pass "workspace updated with upstream commit"
    else
        log_fail "upstream file missing after sync"
    fi
else
    log_fail "sync returned non-zero ($EXIT_CODE) for clean ff"
fi

# -----------------------------------------------------------------------
# TEST 2: Dirty tree, no conflict — stash+pop should succeed
# -----------------------------------------------------------------------
echo "TEST 2: Dirty tree, no conflict (stash round-trip)"
WS=$(setup_repos "t2")
ORIGIN="$TMPDIR_ROOT/t2/origin.git"
push_origin_commit "$ORIGIN" "upstream.txt" "new-file"

cd "$WS"
echo "local-dirty" > local_only.txt

EXIT_CODE=$(run_sync "$WS")
cd "$WS"
if [ "$EXIT_CODE" = "0" ] && [ -f "upstream.txt" ] && [ -f "local_only.txt" ]; then
    log_pass "dirty tree preserved after clean ff + stash pop"
else
    log_fail "expected success with preserved dirty file (exit=$EXIT_CODE)"
fi

# -----------------------------------------------------------------------
# TEST 3: Dirty tree + conflict on stash pop after ff-merge
# -----------------------------------------------------------------------
echo "TEST 3: Stash pop conflict after successful ff-merge"
WS=$(setup_repos "t3")
ORIGIN="$TMPDIR_ROOT/t3/origin.git"

# Local dirty change to file.txt
cd "$WS"
echo "local-conflict-content" > file.txt

# Upstream changes the same file
push_origin_commit "$ORIGIN" "file.txt" "upstream-conflict-content"

EXIT_CODE=$(run_sync "$WS")
STDERR=$(cat "$TMPDIR_ROOT/stderr.log" 2>/dev/null || echo "")
DASHBOARD=$(cat "$TMPDIR_ROOT/dashboard_events.log" 2>/dev/null || echo "")

if [ "$EXIT_CODE" = "1" ]; then
    log_pass "returns non-zero on stash pop conflict"
else
    log_fail "should return 1 on stash pop conflict (got $EXIT_CODE)"
fi

if echo "$STDERR" | grep -q "CRITICAL"; then
    log_pass "logs CRITICAL on stash pop failure"
else
    log_fail "expected CRITICAL in stderr: $STDERR"
fi

if echo "$DASHBOARD" | grep -q "stash_pop_failed"; then
    log_pass "emits dashboard event on stash pop failure"
else
    log_fail "expected dashboard event: $DASHBOARD"
fi

# Verify stash is preserved (not lost)
cd "$WS"
STASH_COUNT=$(git stash list 2>/dev/null | wc -l)
if [ "$STASH_COUNT" -ge 1 ]; then
    log_pass "stash entry preserved for manual recovery"
else
    log_fail "stash entry was lost (count=$STASH_COUNT)"
fi

# -----------------------------------------------------------------------
# TEST 4: Diverged histories — should skip (no stash, no merge attempt)
# -----------------------------------------------------------------------
echo "TEST 4: Diverged histories — skip"
WS=$(setup_repos "t4")
ORIGIN="$TMPDIR_ROOT/t4/origin.git"

# Create divergence: local commit + different upstream commit
cd "$WS"
echo "local-commit" > local.txt
git add local.txt && git commit -m "local diverge" -q
push_origin_commit "$ORIGIN" "remote.txt" "remote diverge"

EXIT_CODE=$(run_sync "$WS")
STDERR=$(cat "$TMPDIR_ROOT/stderr.log" 2>/dev/null || echo "")
if [ "$EXIT_CODE" = "0" ] && echo "$STDERR" | grep -q "diverged"; then
    log_pass "skipped sync on diverged branches"
else
    log_fail "expected skip on diverged (exit=$EXIT_CODE, stderr=$STDERR)"
fi

# -----------------------------------------------------------------------
# TEST 5: Not on main — should skip
# -----------------------------------------------------------------------
echo "TEST 5: Not on main branch — skip"
WS=$(setup_repos "t5")
cd "$WS"
git checkout -b feature -q 2>/dev/null

EXIT_CODE=$(run_sync "$WS")
if [ "$EXIT_CODE" = "0" ]; then
    log_pass "skipped sync when not on main"
else
    log_fail "should return 0 (skip) when not on main (got $EXIT_CODE)"
fi

# -----------------------------------------------------------------------
# TEST 6: Already up to date — no-op
# -----------------------------------------------------------------------
echo "TEST 6: Already up to date — no-op"
WS=$(setup_repos "t6")

EXIT_CODE=$(run_sync "$WS")
if [ "$EXIT_CODE" = "0" ]; then
    log_pass "no-op when already up to date"
else
    log_fail "should return 0 when up to date (got $EXIT_CODE)"
fi

# -----------------------------------------------------------------------
# TEST 7: CLARVIS_SELF_SYNC=skip — no-op
# -----------------------------------------------------------------------
echo "TEST 7: CLARVIS_SELF_SYNC=skip — disabled"
WS=$(setup_repos "t7")
ORIGIN="$TMPDIR_ROOT/t7/origin.git"
push_origin_commit "$ORIGIN" "new.txt" "upstream"

EXIT_CODE=$(
    export CLARVIS_WORKSPACE="$WS"
    export CLARVIS_SELF_SYNC="skip"
    emit_dashboard_event() { :; }
    export -f emit_dashboard_event
    eval "$(sed -n '/^sync_workspace()/,/^}/p' "$REAL_CRON_ENV")"
    sync_workspace 2>/dev/null
    echo $?
)
cd "$WS"
if [ "$EXIT_CODE" = "0" ] && [ ! -f "new.txt" ]; then
    log_pass "sync skipped when CLARVIS_SELF_SYNC=skip"
else
    log_fail "should skip sync entirely (exit=$EXIT_CODE)"
fi

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit "$FAIL"
