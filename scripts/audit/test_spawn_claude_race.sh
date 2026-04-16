#!/bin/bash
# Primitive-level tests for spawn_claude.sh global-lock race fix.
# Does NOT invoke the real spawn_claude.sh (would collide with the real
# /tmp/clarvis_claude_global.lock in production). Instead, exercises the
# race-critical primitives this fix depends on:
#   1. _is_clarvis_process rejects dead PIDs (stale-reclaim safety)
#   2. Bash noclobber (`set -C`) gives O_EXCL atomicity against two racers
#   3. Worker ownership check (_worker_owns_lock logic) rejects foreign PIDs
#
# A true end-to-end race test requires either:
#   (a) a stub `claude` binary + isolated CLARVIS_WORKSPACE, or
#   (b) running in a VM / clean environment where clobbering the real lock
#       is safe. Both are out of scope here — this file guards the primitives.
set -u

WORKSPACE="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"
FAIL=0
_fail() { echo "FAIL: $*"; FAIL=$((FAIL+1)); }
_pass() { echo "PASS: $*"; }

# ---------- Test 1: _is_clarvis_process rejects dead PIDs ----------
echo "== Test 1: _is_clarvis_process stale-PID rejection =="
source "$WORKSPACE/scripts/cron/lock_helper.sh"

DEAD_PID=$(( $(cat /proc/sys/kernel/pid_max 2>/dev/null || echo 65535) - 1 ))
while kill -0 "$DEAD_PID" 2>/dev/null; do DEAD_PID=$((DEAD_PID - 1)); done
if _is_clarvis_process "$DEAD_PID"; then
    _fail "_is_clarvis_process returned true for dead PID $DEAD_PID"
else
    _pass "_is_clarvis_process rejects dead PID $DEAD_PID"
fi

# Non-clarvis live process (init/systemd)
if _is_clarvis_process 1; then
    _fail "_is_clarvis_process returned true for init (PID 1) — would honor non-clarvis locks"
else
    _pass "_is_clarvis_process rejects init (PID 1) as non-clarvis"
fi

# ---------- Test 2: noclobber gives atomicity under contention ----------
echo
echo "== Test 2: set -C / noclobber O_EXCL race =="
TEST_LOCK="/tmp/spawn_claude_race_test_$$.lock"
rm -f "$TEST_LOCK"

# 20 concurrent racers; exactly one should win.
RACERS=20
TEMPDIR="$(mktemp -d)"
for i in $(seq 1 "$RACERS"); do
    (
        set -C
        if { echo "$$ winner_$i" > "$TEST_LOCK"; } 2>/dev/null; then
            echo "WON" > "$TEMPDIR/r$i"
        else
            echo "LOST" > "$TEMPDIR/r$i"
        fi
    ) &
done
wait

WINNERS=$(grep -l "^WON$" "$TEMPDIR"/r* 2>/dev/null | wc -l)
if [ "$WINNERS" = "1" ]; then
    _pass "exactly 1 winner out of $RACERS racers"
else
    _fail "expected 1 winner, got $WINNERS. noclobber atomicity is broken on this system."
fi
rm -rf "$TEMPDIR"
rm -f "$TEST_LOCK"

# ---------- Test 3: worker ownership check ----------
echo
echo "== Test 3: _worker_owns_lock ownership validation =="
TEST_LOCK="/tmp/spawn_claude_ownership_test_$$.lock"
GLOBAL_LOCK="$TEST_LOCK"

_worker_owns_lock() {
    [ -f "$GLOBAL_LOCK" ] || return 1
    local owner
    owner=$(awk 'NR==1{print $1}' "$GLOBAL_LOCK" 2>/dev/null)
    [ "$owner" = "$$" ]
}

# Missing lock -> false
rm -f "$TEST_LOCK"
if _worker_owns_lock; then
    _fail "returned true with no lock file"
else
    _pass "correctly false when lock is absent"
fi

# Lock with foreign PID -> false
echo "999999 2026-04-16T00:00:00" > "$TEST_LOCK"
if _worker_owns_lock; then
    _fail "falsely accepted foreign PID 999999 (our PID=$$)"
else
    _pass "rejects foreign PID 999999"
fi

# Lock with our PID -> true
echo "$$ 2026-04-16T00:00:00" > "$TEST_LOCK"
if _worker_owns_lock; then
    _pass "accepts matching PID $$"
else
    _fail "rejected matching PID $$"
fi

# Lock with our PID + extra whitespace -> still true
echo "$$  2026-04-16T00:00:00  extra" > "$TEST_LOCK"
if _worker_owns_lock; then
    _pass "handles extra whitespace / fields"
else
    _fail "rejected valid lock with extra whitespace"
fi

rm -f "$TEST_LOCK"

# ---------- Test 4: bash -n syntax check on the spawn script ----------
echo
echo "== Test 4: spawn_claude.sh syntactic validity =="
if bash -n "$WORKSPACE/scripts/agents/spawn_claude.sh"; then
    _pass "spawn_claude.sh parses cleanly"
else
    _fail "spawn_claude.sh has syntax errors"
fi

echo
if [ "$FAIL" = "0" ]; then
    echo "ALL PRIMITIVE TESTS PASSED"
    exit 0
else
    echo "TESTS FAILED: $FAIL"
    exit 1
fi
