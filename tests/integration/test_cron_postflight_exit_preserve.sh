#!/bin/bash
# Integration test for combine_exit_codes (CLARVIS_PROC_CRON_POSTFLIGHT_EXIT_PRESERVE_FAILURE).
#
# Validates the helper that lets cron orchestrators preserve the first
# non-zero rc (task/preflight/postflight) instead of letting a successful
# postflight verifier mask an earlier failure.
#
# Required acceptance cases:
#   (1) task_fail (1) + postflight_ok (0) -> non-zero
#   (2) task_ok   (0) + postflight_fail (1) -> non-zero
#   (3) task_ok   (0) + postflight_ok   (0) -> 0
# Plus end-to-end smoke against each orchestrator's final `exit "$FINAL_RC"`
# block by sourcing the script's tail in a stub harness.

set -uo pipefail

WORKSPACE_ROOT="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"
HELPER="$WORKSPACE_ROOT/scripts/cron/lock_helper.sh"

if [ ! -f "$HELPER" ]; then
    echo "FAIL: helper missing at $HELPER" >&2
    exit 2
fi

PASS=0
FAIL=0
_pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
_fail() { echo "  FAIL: $1" >&2; FAIL=$((FAIL + 1)); }

# Source the helper in a clean subshell so the EXIT trap doesn't clobber us.
# We only need combine_exit_codes, not the lock functions.
# shellcheck disable=SC1090
source "$HELPER"

# ---------------------------------------------------------------------------
# Case 1: task_fail (rc=1) + postflight_ok (rc=0) -> non-zero
# ---------------------------------------------------------------------------
echo "[case 1] task_fail + postflight_ok -> non-zero"
got=$(combine_exit_codes 1 0)
if [ "$got" = "1" ]; then
    _pass "task=1 postflight=0 -> $got"
else
    _fail "expected 1, got $got"
fi

# ---------------------------------------------------------------------------
# Case 2: task_ok (rc=0) + postflight_fail (rc=1) -> non-zero
# ---------------------------------------------------------------------------
echo "[case 2] task_ok + postflight_fail -> non-zero"
got=$(combine_exit_codes 0 1)
if [ "$got" = "1" ]; then
    _pass "task=0 postflight=1 -> $got"
else
    _fail "expected 1, got $got"
fi

# ---------------------------------------------------------------------------
# Case 3: success path stays 0
# ---------------------------------------------------------------------------
echo "[case 3] task_ok + postflight_ok -> 0"
got=$(combine_exit_codes 0 0)
if [ "$got" = "0" ]; then
    _pass "task=0 postflight=0 -> $got"
else
    _fail "expected 0, got $got"
fi

# ---------------------------------------------------------------------------
# Case 4: first non-zero wins (root cause preserved)
# ---------------------------------------------------------------------------
echo "[case 4] first non-zero wins"
got=$(combine_exit_codes 0 2 1)
if [ "$got" = "2" ]; then
    _pass "0,2,1 -> $got"
else
    _fail "expected 2, got $got"
fi

# ---------------------------------------------------------------------------
# Case 5: empty/unset args treated as zero (TASK_EXIT may be unset on early
# bail paths). All-empty must return 0.
# ---------------------------------------------------------------------------
echo "[case 5] empty/unset args treated as zero"
got=$(combine_exit_codes "" "" "")
if [ "$got" = "0" ]; then
    _pass "all empty -> $got"
else
    _fail "expected 0, got $got"
fi
got=$(combine_exit_codes "" 0 3 "")
if [ "$got" = "3" ]; then
    _pass "'',0,3,'' -> $got"
else
    _fail "expected 3, got $got"
fi

# ---------------------------------------------------------------------------
# Case 6: end-to-end shape — script that uses the helper's exit pattern.
# Confirms `exit "$FINAL_RC"` propagates correctly from a subshell.
# ---------------------------------------------------------------------------
echo "[case 6] subshell exit propagation"
(
    # shellcheck disable=SC1090
    source "$HELPER"
    TASK_EXIT=1
    POSTFLIGHT_RC=0
    FINAL_RC=$(combine_exit_codes "${TASK_EXIT:-0}" "$POSTFLIGHT_RC")
    exit "$FINAL_RC"
)
got=$?
if [ "$got" = "1" ]; then
    _pass "subshell with task=1 postflight=0 propagates -> $got"
else
    _fail "expected 1, got $got"
fi

(
    # shellcheck disable=SC1090
    source "$HELPER"
    TASK_EXIT=0
    POSTFLIGHT_RC=2
    FINAL_RC=$(combine_exit_codes "${TASK_EXIT:-0}" "$POSTFLIGHT_RC")
    exit "$FINAL_RC"
)
got=$?
if [ "$got" = "2" ]; then
    _pass "subshell with task=0 postflight=2 propagates -> $got"
else
    _fail "expected 2, got $got"
fi

(
    # shellcheck disable=SC1090
    source "$HELPER"
    TASK_EXIT=0
    POSTFLIGHT_RC=0
    FINAL_RC=$(combine_exit_codes "${TASK_EXIT:-0}" "$POSTFLIGHT_RC")
    exit "$FINAL_RC"
)
got=$?
if [ "$got" = "0" ]; then
    _pass "subshell success path -> $got"
else
    _fail "expected 0, got $got"
fi

# ---------------------------------------------------------------------------
# Case 7: structural check — every targeted cron script must call
# combine_exit_codes and exit "$FINAL_RC" instead of bare exit $POSTFLIGHT_RC.
# Guards against regression where the helper exists but a script forgets it.
# ---------------------------------------------------------------------------
echo "[case 7] all 5 orchestrators wired to combine_exit_codes"
SCRIPTS=(
    "$WORKSPACE_ROOT/scripts/cron/cron_autonomous.sh"
    "$WORKSPACE_ROOT/scripts/cron/cron_evolution.sh"
    "$WORKSPACE_ROOT/scripts/cron/cron_implementation_sprint.sh"
    "$WORKSPACE_ROOT/scripts/cron/cron_reflection.sh"
    "$WORKSPACE_ROOT/scripts/cron/cron_research.sh"
)
for s in "${SCRIPTS[@]}"; do
    if ! grep -q "combine_exit_codes" "$s"; then
        _fail "$(basename "$s") does not call combine_exit_codes"
        continue
    fi
    if grep -qE '^exit \$POSTFLIGHT_RC\s*$' "$s"; then
        _fail "$(basename "$s") still has bare \`exit \$POSTFLIGHT_RC\`"
        continue
    fi
    if ! grep -qE 'exit "?\$FINAL_RC"?' "$s"; then
        _fail "$(basename "$s") does not exit with \$FINAL_RC"
        continue
    fi
    _pass "$(basename "$s") wired"
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
