#!/usr/bin/env bash
# test_digest_actionability.sh — regression test for
# scripts/maint/digest_actionability_check.sh
#
# Acceptance (from [DIGEST_ACTIONABILITY_BASH_GUARD]):
#   - exits 0 on healthy fixture (tests/fixtures/digest_healthy.md)
#   - exits 1 on stripped fixture (tests/fixtures/digest_stripped.md)
#   - SKIP path (missing digest) exits 0

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GUARD="$REPO_ROOT/scripts/maint/digest_actionability_check.sh"
FIX_HEALTHY="$REPO_ROOT/tests/fixtures/digest_healthy.md"
FIX_STRIPPED="$REPO_ROOT/tests/fixtures/digest_stripped.md"

if [[ ! -x "$GUARD" ]]; then
    echo "FAIL: $GUARD missing or not executable"
    exit 1
fi

pass=0
fail=0
TMP_WS="$(mktemp -d -t digest_act.XXXXXX)"
trap 'rm -rf "$TMP_WS"' EXIT

run_case() {
    local name="$1"
    local expected="$2"
    local digest="$3"
    local code
    CLARVIS_WORKSPACE="$TMP_WS" "$GUARD" "$digest" >/dev/null 2>&1 && code=0 || code=$?
    if [[ "$code" == "$expected" ]]; then
        echo "  PASS: $name (exit=$code)"
        pass=$((pass + 1))
    else
        echo "  FAIL: $name (expected=$expected, got=$code)"
        fail=$((fail + 1))
    fi
}

echo "[1] digest_actionability_check.sh — fixture cases"
run_case "healthy-fixture-passes" 0 "$FIX_HEALTHY"
run_case "stripped-fixture-alerts" 1 "$FIX_STRIPPED"
run_case "missing-digest-skips" 0 "$TMP_WS/no_such.md"

echo ""
echo "[2] log file format"
LOG="$TMP_WS/monitoring/digest_actionability.log"
if [[ -f "$LOG" ]] \
    && grep -q "OK digest=.*matches=[1-9]" "$LOG" \
    && grep -q "ALERT digest=.*matches=0" "$LOG" \
    && grep -q "SKIP digest=.*reason=missing" "$LOG"; then
    echo "  PASS: log contains OK + ALERT + SKIP entries"
    pass=$((pass + 1))
else
    echo "  FAIL: log missing expected entries"
    [[ -f "$LOG" ]] && sed 's/^/    /' "$LOG"
    fail=$((fail + 1))
fi

echo ""
echo "Summary: $pass passed, $fail failed"
[[ "$fail" -eq 0 ]]
