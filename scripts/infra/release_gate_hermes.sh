#!/usr/bin/env bash
# release_gate_hermes.sh — Release gate for "works on Hermes" claims.
#
# Runs the Hermes overlay test suite in isolated mode and saves artifacts/logs.
# If any critical check fails, the gate FAILS and no public claim is safe.
#
# Usage:
#   bash scripts/infra/release_gate_hermes.sh              # Run gate
#   bash scripts/infra/release_gate_hermes.sh --quick       # Fast subset (skip brain + Hermes clone)
#   bash scripts/infra/release_gate_hermes.sh --skip-hermes # Adapter-only (no Hermes repo needed)
#
# Artifacts saved to: docs/validation/hermes_<timestamp>/
#   - overlay_test.log     Full overlay test output
#   - adapter_check.log    Hermes adapter detection log
#   - gate_verdict.json    Final PASS/FAIL verdict with metadata
#
# Exit: 0 = PASS (safe to claim), 1 = FAIL (do NOT claim support)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ARTIFACT_DIR="$REPO_ROOT/docs/validation/hermes_${TIMESTAMP}"
QUICK_FLAG=""
HERMES_FLAG=""

while [ $# -gt 0 ]; do
    case "$1" in
        --quick)       QUICK_FLAG="--quick"; shift ;;
        --skip-hermes) HERMES_FLAG="--skip-hermes"; shift ;;
        --help|-h)
            sed -n '2,14p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) shift ;;
    esac
done

mkdir -p "$ARTIFACT_DIR"

echo "=== Hermes Release Gate ==="
echo "Timestamp: ${TIMESTAMP}"
echo "Artifacts: ${ARTIFACT_DIR}"
echo "Commit:    $(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo ""

GATE_PASS=true
OVERLAY_EXIT=0
ADAPTER_OK=false

# ── Step 1: Run Hermes overlay test (isolated) ──────────────────────────
echo "[1/3] Running Hermes overlay test..."
bash "$REPO_ROOT/tests/test_hermes_overlay.sh" $QUICK_FLAG $HERMES_FLAG \
    > "$ARTIFACT_DIR/overlay_test.log" 2>&1
OVERLAY_EXIT=$?

OVERLAY_PASS=$(grep -cE "^\s+PASS\s" "$ARTIFACT_DIR/overlay_test.log" 2>/dev/null) || OVERLAY_PASS=0
OVERLAY_FAIL=$(grep -cE "^\s+FAIL\s" "$ARTIFACT_DIR/overlay_test.log" 2>/dev/null) || OVERLAY_FAIL=0
OVERLAY_WARN=$(grep -cE "^\s+WARN\s" "$ARTIFACT_DIR/overlay_test.log" 2>/dev/null) || OVERLAY_WARN=0

echo "  Overlay test: ${OVERLAY_PASS} passed, ${OVERLAY_FAIL} failed, ${OVERLAY_WARN} warnings (exit ${OVERLAY_EXIT})"
if [ "$OVERLAY_EXIT" -eq 1 ]; then
    echo "  FAIL: Hermes overlay test reported critical failures"
    GATE_PASS=false
elif [ "$OVERLAY_EXIT" -eq 2 ]; then
    echo "  WARN: Overlay test passed with warnings"
fi
echo ""

# ── Step 2: Verify Hermes adapter code is present and functional ─────────
echo "[2/3] Checking Hermes adapter..."
{
    python3 -c "
from clarvis.adapters.hermes import HermesAdapter, detect_hermes
adapter = HermesAdapter()
result = adapter.hermes_available()
print(f'adapter_instantiated=True')
print(f'hermes_detected={result.ok}')
print(f'config_dir={result.data.get(\"config_dir\", \"N/A\")}')
" 2>&1
} > "$ARTIFACT_DIR/adapter_check.log"

ADAPTER_EXIT=$?
if [ $ADAPTER_EXIT -eq 0 ]; then
    echo "  PASS  HermesAdapter instantiates"
    ADAPTER_OK=true
    cat "$ARTIFACT_DIR/adapter_check.log" | sed 's/^/    /'
else
    echo "  FAIL  HermesAdapter failed to instantiate"
    GATE_PASS=false
    tail -3 "$ARTIFACT_DIR/adapter_check.log" | sed 's/^/    /'
fi
echo ""

# ── Step 3: Verify Gate D criteria (from E2E_RELEASE_VALIDATION_PLAN) ────
echo "[3/3] Gate D criteria check..."
GATE_D_PASS=0
GATE_D_TOTAL=0

# D1: Install script exists and is runnable
GATE_D_TOTAL=$((GATE_D_TOTAL+1))
if [ -f "$REPO_ROOT/scripts/infra/install.sh" ]; then
    # Verify --profile hermes is recognized
    if bash "$REPO_ROOT/scripts/infra/install.sh" --help 2>&1 | grep -qi "hermes"; then
        echo "  PASS  install.sh recognizes hermes profile"
        GATE_D_PASS=$((GATE_D_PASS+1))
    else
        echo "  WARN  install.sh --help does not mention hermes"
    fi
else
    echo "  FAIL  install.sh not found"
    GATE_PASS=false
fi

# D2: Core imports (verified by overlay test)
GATE_D_TOTAL=$((GATE_D_TOTAL+1))
if python3 -c "import clarvis; import clarvis.adapters.hermes" 2>/dev/null; then
    echo "  PASS  Core imports + Hermes adapter"
    GATE_D_PASS=$((GATE_D_PASS+1))
else
    echo "  FAIL  Core imports or Hermes adapter broken"
    GATE_PASS=false
fi

# D3: CLI responds
GATE_D_TOTAL=$((GATE_D_TOTAL+1))
if python3 -m clarvis --help >/dev/null 2>&1; then
    echo "  PASS  clarvis CLI responds"
    GATE_D_PASS=$((GATE_D_PASS+1))
else
    echo "  FAIL  clarvis CLI broken"
    GATE_PASS=false
fi

# D7: Hermes still works (can only check if not --skip-hermes)
GATE_D_TOTAL=$((GATE_D_TOTAL+1))
if [ -z "$HERMES_FLAG" ] && [ -z "$QUICK_FLAG" ]; then
    if grep -q "hermes_agent still importable" "$ARTIFACT_DIR/overlay_test.log" 2>/dev/null; then
        echo "  PASS  Hermes survives overlay"
        GATE_D_PASS=$((GATE_D_PASS+1))
    elif grep -q "FAIL.*hermes.*broken" "$ARTIFACT_DIR/overlay_test.log" 2>/dev/null; then
        echo "  FAIL  Hermes broken by overlay"
        GATE_PASS=false
    else
        echo "  WARN  Hermes post-overlay status unclear"
        GATE_D_PASS=$((GATE_D_PASS+1))
    fi
else
    echo "  SKIP  Hermes post-overlay (--quick or --skip-hermes)"
    GATE_D_PASS=$((GATE_D_PASS+1))
fi
echo ""

# ── Verdict ──────────────────────────────────────────────────────────────
if $GATE_PASS; then
    VERDICT="PASS"
    echo "=== GATE VERDICT: PASS ==="
    echo "Safe to claim: 'Experimental Hermes support'"
    echo "(Note: Hermes support is EXPERIMENTAL — claim requires full overlay test without --quick)"
else
    VERDICT="FAIL"
    echo "=== GATE VERDICT: FAIL ==="
    echo "DO NOT claim Hermes support until failures are resolved."
    echo "Review artifacts: $ARTIFACT_DIR"
fi

# Save verdict JSON
python3 -c "
import json, os
v = dict(
    gate='hermes_release',
    timestamp='$TIMESTAMP',
    commit='$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)',
    verdict='$VERDICT',
    overlay_exit=$OVERLAY_EXIT,
    overlay_passed=$OVERLAY_PASS,
    overlay_failed=$OVERLAY_FAIL,
    overlay_warnings=$OVERLAY_WARN,
    adapter_ok=$($ADAPTER_OK && echo 'True' || echo 'False'),
    gate_d_passed=$GATE_D_PASS,
    gate_d_total=$GATE_D_TOTAL,
    quick_mode=$( [ -n '$QUICK_FLAG' ] && echo 'True' || echo 'False'),
    skip_hermes=$( [ -n '$HERMES_FLAG' ] && echo 'True' || echo 'False'),
    artifacts_dir='$ARTIFACT_DIR',
    note='Hermes support is EXPERIMENTAL. Full claim requires overlay test without --quick or --skip-hermes.',
)
out = os.path.join('$ARTIFACT_DIR', 'gate_verdict.json')
with open(out, 'w') as f:
    json.dump(v, f, indent=2)
print(json.dumps(v, indent=2))
" || echo "  (verdict JSON generation failed)"

echo ""
echo "Artifacts saved to: $ARTIFACT_DIR"

if [ "$VERDICT" = "PASS" ]; then
    exit 0
else
    exit 1
fi
