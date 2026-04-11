#!/usr/bin/env bash
# isolation_guard.sh — Hard safety guards for E2E install tests.
#
# Source this file at the top of any test script that creates or modifies
# install artifacts. It will abort immediately if ANY condition suggests
# the test could touch production systems.
#
# Usage:
#   export CLARVIS_E2E_ISOLATED=1
#   export CLARVIS_WORKSPACE="/tmp/clarvis-e2e-test/workspace"
#   source scripts/infra/isolation_guard.sh
#
# Self-test:
#   bash scripts/infra/isolation_guard.sh --self-test
#
# Exit: 0 = all guards pass, 1 = guard tripped (test must not proceed)

# Detect --self-test early so guard failures don't exit before we reach the test harness
if [ "${1:-}" = "--self-test" ] 2>/dev/null; then
    _GUARD_SELF_TEST=1
fi

_GUARD_PASS=0
_GUARD_FAIL=0
_GUARD_ERRORS=()

_guard_check() {
    local name="$1" condition="$2" message="$3"
    if eval "$condition"; then
        _GUARD_FAIL=$((_GUARD_FAIL + 1))
        _GUARD_ERRORS+=("BLOCKED [$name]: $message")
        return 1
    fi
    _GUARD_PASS=$((_GUARD_PASS + 1))
    return 0
}

# ── Guard 1: Isolation env var must be set ────────────────────────────
_guard_check "ISOLATION_FLAG" \
    '[ "${CLARVIS_E2E_ISOLATED:-}" != "1" ]' \
    "CLARVIS_E2E_ISOLATED is not set to '1'. Set it to confirm you intend an isolated test run."

# ── Guard 2: CLARVIS_WORKSPACE must NOT be production ────────────────
_PROD_WORKSPACE="/home/agent/.openclaw/workspace"
_guard_check "PROD_WORKSPACE" \
    '[ "${CLARVIS_WORKSPACE:-$_PROD_WORKSPACE}" = "$_PROD_WORKSPACE" ]' \
    "CLARVIS_WORKSPACE points to production ($CLARVIS_WORKSPACE). Set it to a /tmp/ path."

# ── Guard 3: CLARVIS_WORKSPACE must be under /tmp or /opt/clarvis-test ──
_guard_check "SAFE_ROOT" \
    '[ -n "${CLARVIS_WORKSPACE:-}" ] && [[ ! "$CLARVIS_WORKSPACE" =~ ^/tmp/ ]] && [[ ! "$CLARVIS_WORKSPACE" =~ ^/opt/clarvis-test/ ]]' \
    "CLARVIS_WORKSPACE ($CLARVIS_WORKSPACE) is not under /tmp/ or /opt/clarvis-test/."

# ── Guard 4: Gateway port must NOT be production (18789) ─────────────
_E2E_PORT="${CLARVIS_E2E_PORT:-${OPENCLAW_PORT:-18789}}"
_guard_check "PROD_PORT" \
    '[ "$_E2E_PORT" = "18789" ]' \
    "Gateway port is 18789 (production). Use a non-default port like 28789."

# ── Guard 5: Must NOT modify system crontab ──────────────────────────
# Override crontab command to block writes
if [ "${_GUARD_SELF_TEST:-}" != "1" ]; then
    crontab() {
        # Allow reads (crontab -l) but block writes (crontab - or crontab file)
        if [ "${1:-}" = "-l" ]; then
            command crontab "$@"
        else
            echo "ISOLATION GUARD: crontab write blocked. Use --dry-run instead." >&2
            return 1
        fi
    }
    export -f crontab 2>/dev/null || true
fi

# ── Guard 6: Must NOT read/write production auth files ───────────────
_PROD_AUTH_DIR="/home/agent/.openclaw/agents"
_guard_check "PROD_AUTH" \
    '[ -n "${CLARVIS_AUTH_DIR:-}" ] && [[ "$CLARVIS_AUTH_DIR" =~ ^/home/agent/.openclaw/ ]]' \
    "CLARVIS_AUTH_DIR points to production auth directory."

# ── Guard 7: Must NOT be running inside production gateway process ───
_guard_check "GATEWAY_PROCESS" \
    '[ -n "${OPENCLAW_GATEWAY_PID:-}" ] && kill -0 "${OPENCLAW_GATEWAY_PID}" 2>/dev/null' \
    "Running inside a live gateway process tree. Do not run E2E tests from the gateway."

# ── Report ───────────────────────────────────────────────────────────
if [ $_GUARD_FAIL -gt 0 ]; then
    echo "" >&2
    echo "╔═══════════════════════════════════════════════════════════╗" >&2
    echo "║  ISOLATION GUARD FAILED — TEST ABORTED                    ║" >&2
    echo "╚═══════════════════════════════════════════════════════════╝" >&2
    echo "" >&2
    for err in "${_GUARD_ERRORS[@]}"; do
        echo "  $err" >&2
    done
    echo "" >&2
    echo "  Passed: $_GUARD_PASS / $((_GUARD_PASS + _GUARD_FAIL))" >&2
    echo "" >&2
    echo "  To fix: set CLARVIS_E2E_ISOLATED=1, CLARVIS_WORKSPACE=/tmp/..., " >&2
    echo "  and use a non-default port (e.g., CLARVIS_E2E_PORT=28789)." >&2
    echo "" >&2

    if [ "${_GUARD_SELF_TEST:-}" = "1" ]; then
        _GUARD_RESULT="fail"
    else
        # exit 1 terminates the calling script — this is intentional.
        # The guard MUST stop execution to protect production.
        exit 1
    fi
else
    if [ "${_GUARD_SELF_TEST:-}" = "1" ] || [ -t 1 ]; then
        echo "  Isolation guards: $_GUARD_PASS/$_GUARD_PASS passed" >&2
    fi
    _GUARD_RESULT="pass"
fi

# ── Self-test mode ───────────────────────────────────────────────────
if [ "${1:-}" = "--self-test" ] 2>/dev/null; then
    echo ""
    echo "=== Isolation Guard Self-Test ==="
    echo ""

    _SELF_TEST_PASS=0
    _SELF_TEST_FAIL=0

    _st_check() {
        local name="$1" expected="$2" actual="$3"
        if [ "$expected" = "$actual" ]; then
            echo "  PASS  $name"
            _SELF_TEST_PASS=$((_SELF_TEST_PASS + 1))
        else
            echo "  FAIL  $name (expected=$expected, got=$actual)"
            _SELF_TEST_FAIL=$((_SELF_TEST_FAIL + 1))
        fi
    }

    # Test 1: Should FAIL with no env vars set
    result=$(
        unset CLARVIS_E2E_ISOLATED CLARVIS_WORKSPACE CLARVIS_E2E_PORT CLARVIS_AUTH_DIR OPENCLAW_GATEWAY_PID
        export _GUARD_SELF_TEST=1
        _GUARD_PASS=0 _GUARD_FAIL=0 _GUARD_ERRORS=()
        source "${BASH_SOURCE[0]}" 2>/dev/null
        echo "$_GUARD_RESULT"
    )
    _st_check "Rejects bare environment" "fail" "${result:-unknown}"

    # Test 2: Should PASS with correct isolation vars
    result=$(
        export CLARVIS_E2E_ISOLATED=1
        export CLARVIS_WORKSPACE="/tmp/clarvis-e2e-test/workspace"
        export CLARVIS_E2E_PORT=28789
        unset CLARVIS_AUTH_DIR OPENCLAW_GATEWAY_PID
        export _GUARD_SELF_TEST=1
        _GUARD_PASS=0 _GUARD_FAIL=0 _GUARD_ERRORS=()
        source "${BASH_SOURCE[0]}" 2>/dev/null
        echo "$_GUARD_RESULT"
    )
    _st_check "Accepts isolated environment" "pass" "${result:-unknown}"

    # Test 3: Should FAIL with production workspace
    result=$(
        export CLARVIS_E2E_ISOLATED=1
        export CLARVIS_WORKSPACE="/home/agent/.openclaw/workspace"
        export CLARVIS_E2E_PORT=28789
        unset CLARVIS_AUTH_DIR OPENCLAW_GATEWAY_PID
        export _GUARD_SELF_TEST=1
        _GUARD_PASS=0 _GUARD_FAIL=0 _GUARD_ERRORS=()
        source "${BASH_SOURCE[0]}" 2>/dev/null
        echo "$_GUARD_RESULT"
    )
    _st_check "Rejects production workspace" "fail" "${result:-unknown}"

    # Test 4: Should FAIL with production port
    result=$(
        export CLARVIS_E2E_ISOLATED=1
        export CLARVIS_WORKSPACE="/tmp/clarvis-e2e-test/workspace"
        export CLARVIS_E2E_PORT=18789
        unset CLARVIS_AUTH_DIR OPENCLAW_GATEWAY_PID
        export _GUARD_SELF_TEST=1
        _GUARD_PASS=0 _GUARD_FAIL=0 _GUARD_ERRORS=()
        source "${BASH_SOURCE[0]}" 2>/dev/null
        echo "$_GUARD_RESULT"
    )
    _st_check "Rejects production port" "fail" "${result:-unknown}"

    echo ""
    echo "Self-test: $_SELF_TEST_PASS passed, $_SELF_TEST_FAIL failed"
    [ $_SELF_TEST_FAIL -eq 0 ] && exit 0 || exit 1
fi
