#!/usr/bin/env bash
# test_notask_attribution.sh — regression test for
# scripts/maint/notask_attribution.sh
#
# Acceptance (from [HEARTBEAT_NOTASK_ATTRIBUTION_BASH]):
#   - exits 0 on healthy fixture (≤25% no-task)
#   - exits 1 on regressed fixture (>25% no-task)
#   - missing input log exits 0 (SKIP path)
#   - emits a CSV row with the canonical reason=count fields per run

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GUARD="$REPO_ROOT/scripts/maint/notask_attribution.sh"
FIX_HEALTHY_TPL="$REPO_ROOT/tests/fixtures/heartbeat_healthy.log"
FIX_REGRESSED_TPL="$REPO_ROOT/tests/fixtures/heartbeat_regressed.log"

if [[ ! -x "$GUARD" ]]; then
    echo "FAIL: $GUARD missing or not executable"
    exit 1
fi

pass=0
fail=0
TMP="$(mktemp -d -t notask_attr.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# Render fixture: replace __TN__ placeholders with timestamps inside the
# 24h window so the awk filter accepts every line. Spread N hours back from
# 1 hour ago so we never tip over the cutoff in either direction.
render_fixture() {
    local src="$1"
    local dst="$2"
    awk '
        BEGIN {
            cmd = "date -u -d \"@$(($(date -u +%s) - 3600))\" +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S"
        }
        {
            line = $0
            while (match(line, /__T[0-9]+__/)) {
                tag = substr(line, RSTART, RLENGTH)
                n = substr(tag, 4, RLENGTH - 6) + 0
                # Build a per-N timestamp by shelling out once per N seen.
                stamp = stamps[n]
                if (stamp == "") {
                    h = n + 2
                    cmd2 = "date -u -d \"" h " hours ago\" +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-" h "H +%Y-%m-%dT%H:%M:%S"
                    cmd2 | getline stamp
                    close(cmd2)
                    stamps[n] = stamp
                }
                line = substr(line, 1, RSTART - 1) stamp substr(line, RSTART + RLENGTH)
            }
            print line
        }
    ' "$src" > "$dst"
}

FIX_HEALTHY="$TMP/heartbeat_healthy.log"
FIX_REGRESSED="$TMP/heartbeat_regressed.log"
render_fixture "$FIX_HEALTHY_TPL" "$FIX_HEALTHY"
render_fixture "$FIX_REGRESSED_TPL" "$FIX_REGRESSED"

# Exit-code check; counters live in the parent shell so we don't run inside $(...).
run_case() {
    local name="$1"
    local expected="$2"
    local input="$3"
    local out_log="$4"
    local code
    OUT_LOG="$out_log" CLARVIS_WORKSPACE="$TMP" LOCK="$TMP/${name//[^a-zA-Z0-9]/_}.lock" \
        "$GUARD" "$input" >/dev/null 2>&1 && code=0 || code=$?
    if [[ "$code" == "$expected" ]]; then
        echo "  PASS: $name (exit=$code)"
        pass=$((pass + 1))
    else
        echo "  FAIL: $name (expected=$expected, got=$code)"
        [[ -f "$out_log" ]] && sed 's/^/    csv: /' "$out_log"
        fail=$((fail + 1))
    fi
}

echo "[1] notask_attribution.sh — fixture exit codes"
HEALTHY_OUT="$TMP/out_healthy.csv"
REGRESSED_OUT="$TMP/out_regressed.csv"
SKIP_OUT="$TMP/out_skip.csv"
run_case "healthy-fixture-passes" 0 "$FIX_HEALTHY" "$HEALTHY_OUT"
run_case "regressed-fixture-alerts" 1 "$FIX_REGRESSED" "$REGRESSED_OUT"
run_case "missing-log-skips" 0 "$TMP/no_such.log" "$SKIP_OUT"

echo ""
echo "[2] CSV row shape"
check_csv_shape() {
    local label="$1"
    local file="$2"
    if [[ -f "$file" ]] && grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2},[0-9]+,all_filtered_by_v2=[0-9]+,queue_empty=[0-9]+,gate_skip=[0-9]+,lock_held=[0-9]+,unknown=[0-9]+,notask=[0-9]+,ratio=[0-9.]+$' "$file"; then
        echo "  PASS: $label CSV row matches canonical shape"
        pass=$((pass + 1))
    else
        echo "  FAIL: $label CSV row missing or malformed"
        [[ -f "$file" ]] && sed 's/^/    /' "$file"
        fail=$((fail + 1))
    fi
}

check_csv_shape "healthy" "$HEALTHY_OUT"
check_csv_shape "regressed" "$REGRESSED_OUT"

echo ""
echo "[3] regressed fixture attributes the breach to all_filtered_by_v2"
if grep -q "all_filtered_by_v2=[3-9]" "$REGRESSED_OUT" && grep -q "ratio=[3-9][0-9]" "$REGRESSED_OUT"; then
    echo "  PASS: regressed CSV reports majority all_filtered_by_v2 + ratio>30%"
    pass=$((pass + 1))
else
    echo "  FAIL: regressed CSV did not show expected attribution"
    sed 's/^/    /' "$REGRESSED_OUT"
    fail=$((fail + 1))
fi

echo ""
echo "Summary: $pass passed, $fail failed"
[[ "$fail" -eq 0 ]]
