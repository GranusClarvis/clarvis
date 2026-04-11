#!/usr/bin/env bash
# release_gate_openclaw.sh — Release gate for "works on fresh OpenClaw" claims.
#
# Runs the full validation suite in isolated mode and saves artifacts/logs.
# If any critical check fails, the gate FAILS and no public claim is safe.
#
# Usage:
#   bash scripts/infra/release_gate_openclaw.sh           # Run gate
#   bash scripts/infra/release_gate_openclaw.sh --quick    # Fast subset
#
# Artifacts saved to: docs/validation/openclaw_<timestamp>/
#   - smoke_test.log         Full smoke test output
#   - doctor.json            clarvis doctor --json output
#   - doctor.txt             clarvis doctor human-readable output
#   - gate_verdict.json      Final PASS/FAIL verdict with metadata
#
# Exit: 0 = PASS (safe to claim), 1 = FAIL (do NOT claim support)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ARTIFACT_DIR="$REPO_ROOT/docs/validation/openclaw_${TIMESTAMP}"
QUICK_FLAG=""

while [ $# -gt 0 ]; do
    case "$1" in
        --quick) QUICK_FLAG="--quick"; shift ;;
        --help|-h)
            sed -n '2,14p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) shift ;;
    esac
done

mkdir -p "$ARTIFACT_DIR"

echo "=== OpenClaw Release Gate ==="
echo "Timestamp: ${TIMESTAMP}"
echo "Artifacts: ${ARTIFACT_DIR}"
echo ""

GATE_PASS=true
SMOKE_EXIT=0
DOCTOR_EXIT=0
DOCTOR_FAILS=0
DOCTOR_WARNS=0
DOCTOR_TOTAL=0

# ── Step 1: Run clarvis doctor (non-isolated — checks real install) ──────
echo "[1/3] Running clarvis doctor..."
DOCTOR_JSON_EXIT=0
python3 -m clarvis doctor --json 2>/dev/null > "$ARTIFACT_DIR/doctor.json" || DOCTOR_JSON_EXIT=$?

DOCTOR_EXIT=0
python3 -m clarvis doctor --profile openclaw 2>/dev/null > "$ARTIFACT_DIR/doctor.txt" || DOCTOR_EXIT=$?

if [ "$DOCTOR_JSON_EXIT" -ne 0 ] && [ "$DOCTOR_EXIT" -eq 0 ]; then
    DOCTOR_EXIT=$DOCTOR_JSON_EXIT
fi

# Parse doctor results
if [ -f "$ARTIFACT_DIR/doctor.json" ]; then
    DOCTOR_FAILS=$(python3 -c "import json; d=json.load(open('$ARTIFACT_DIR/doctor.json')); print(d.get('failed',0))" 2>/dev/null || echo "?")
    DOCTOR_WARNS=$(python3 -c "import json; d=json.load(open('$ARTIFACT_DIR/doctor.json')); print(d.get('warnings',0))" 2>/dev/null || echo "?")
    DOCTOR_TOTAL=$(python3 -c "import json; d=json.load(open('$ARTIFACT_DIR/doctor.json')); print(d.get('total',0))" 2>/dev/null || echo "?")
    DOCTOR_PASS=$(python3 -c "import json; d=json.load(open('$ARTIFACT_DIR/doctor.json')); print(d.get('passed',0))" 2>/dev/null || echo "?")
    echo "  Doctor: ${DOCTOR_PASS}/${DOCTOR_TOTAL} passed, ${DOCTOR_FAILS} failed, ${DOCTOR_WARNS} warnings"
else
    echo "  Doctor: FAILED to produce JSON output"
    GATE_PASS=false
fi

if [ "$DOCTOR_EXIT" -ne 0 ]; then
    echo "  FAIL: Doctor execution failed (exit code $DOCTOR_EXIT)"
    GATE_PASS=false
fi

if [ "$DOCTOR_FAILS" != "0" ] && [ "$DOCTOR_FAILS" != "?" ]; then
    echo "  FAIL: Doctor reported $DOCTOR_FAILS failures"
    GATE_PASS=false
fi
echo ""

# ── Step 2: Run fresh install smoke test (isolated) ─────────────────────
echo "[2/3] Running isolated smoke test..."
bash "$SCRIPT_DIR/fresh_install_smoke.sh" --isolated --profile openclaw $QUICK_FLAG \
    > "$ARTIFACT_DIR/smoke_test.log" 2>&1
SMOKE_EXIT=$?

SMOKE_PASS_COUNT=$(grep -cE "^\s+PASS\s" "$ARTIFACT_DIR/smoke_test.log" 2>/dev/null) || SMOKE_PASS_COUNT=0
SMOKE_FAIL_COUNT=$(grep -cE "^\s+FAIL\s" "$ARTIFACT_DIR/smoke_test.log" 2>/dev/null) || SMOKE_FAIL_COUNT=0

echo "  Smoke test: ${SMOKE_PASS_COUNT} passed, exit code ${SMOKE_EXIT}"
if [ "$SMOKE_EXIT" -eq 1 ]; then
    echo "  FAIL: Smoke test reported critical failures"
    GATE_PASS=false
elif [ "$SMOKE_EXIT" -eq 2 ]; then
    echo "  WARN: Smoke test passed with warnings"
fi
echo ""

# ── Step 3: Verify OpenClaw-specific requirements ───────────────────────
echo "[3/3] OpenClaw-specific checks..."
OPENCLAW_CHECKS=0
OPENCLAW_PASS=0

# OpenClaw binary exists
OPENCLAW_CHECKS=$((OPENCLAW_CHECKS+1))
if command -v openclaw &>/dev/null || [ -f "$HOME/.npm-global/lib/node_modules/openclaw/dist/index.js" ]; then
    echo "  PASS  OpenClaw binary"
    OPENCLAW_PASS=$((OPENCLAW_PASS+1))
else
    echo "  FAIL  OpenClaw binary not found"
    GATE_PASS=false
fi

# Gateway config exists
OPENCLAW_CHECKS=$((OPENCLAW_CHECKS+1))
OPENCLAW_ROOT="$(dirname "$REPO_ROOT")"
if [ -f "$OPENCLAW_ROOT/openclaw.json" ]; then
    echo "  PASS  openclaw.json config"
    OPENCLAW_PASS=$((OPENCLAW_PASS+1))
else
    echo "  WARN  openclaw.json not found at $OPENCLAW_ROOT"
fi

# Gateway service exists
OPENCLAW_CHECKS=$((OPENCLAW_CHECKS+1))
if systemctl --user cat openclaw-gateway.service &>/dev/null; then
    echo "  PASS  systemd service unit"
    OPENCLAW_PASS=$((OPENCLAW_PASS+1))
else
    echo "  WARN  systemd service unit not found"
fi

# CLAUDE.md references OpenClaw
OPENCLAW_CHECKS=$((OPENCLAW_CHECKS+1))
if grep -q "OpenClaw" "$OPENCLAW_ROOT/CLAUDE.md" 2>/dev/null || grep -q "OpenClaw" "$REPO_ROOT/CLAUDE.md" 2>/dev/null; then
    echo "  PASS  CLAUDE.md references OpenClaw"
    OPENCLAW_PASS=$((OPENCLAW_PASS+1))
else
    echo "  WARN  CLAUDE.md has no OpenClaw reference"
fi
echo ""

# ── Verdict ──────────────────────────────────────────────────────────────
if $GATE_PASS; then
    VERDICT="PASS"
    echo "=== GATE VERDICT: PASS ==="
    echo "Safe to claim: 'Works on fresh OpenClaw install'"
else
    VERDICT="FAIL"
    echo "=== GATE VERDICT: FAIL ==="
    echo "DO NOT claim OpenClaw support until failures are resolved."
    echo "Review artifacts: $ARTIFACT_DIR"
fi

# Save verdict JSON
GATE_TS="$TIMESTAMP" GATE_VERDICT="$VERDICT" \
    GATE_DOC_EXIT="$DOCTOR_EXIT" GATE_DOC_PASS="${DOCTOR_PASS:-0}" \
    GATE_DOC_FAIL="$DOCTOR_FAILS" GATE_DOC_WARN="$DOCTOR_WARNS" \
    GATE_DOC_TOTAL="$DOCTOR_TOTAL" \
    GATE_SMOKE_EXIT="$SMOKE_EXIT" GATE_SMOKE_PASS="$SMOKE_PASS_COUNT" \
    GATE_SMOKE_FAIL="$SMOKE_FAIL_COUNT" \
    GATE_OC_PASS="$OPENCLAW_PASS" GATE_OC_TOTAL="$OPENCLAW_CHECKS" \
    GATE_ARTIFACTS="$ARTIFACT_DIR" \
python3 -c "
import json, os
v = dict(
    gate='openclaw_release',
    timestamp=os.environ['GATE_TS'],
    verdict=os.environ['GATE_VERDICT'],
    doctor_exit=int(os.environ.get('GATE_DOC_EXIT','0')),
    doctor_passed=os.environ.get('GATE_DOC_PASS','0'),
    doctor_failed=os.environ.get('GATE_DOC_FAIL','0'),
    doctor_warnings=os.environ.get('GATE_DOC_WARN','0'),
    doctor_total=os.environ.get('GATE_DOC_TOTAL','0'),
    smoke_exit=int(os.environ.get('GATE_SMOKE_EXIT','0')),
    smoke_pass=int(os.environ.get('GATE_SMOKE_PASS','0')),
    smoke_fail=int(os.environ.get('GATE_SMOKE_FAIL','0')),
    openclaw_passed=int(os.environ.get('GATE_OC_PASS','0')),
    openclaw_total=int(os.environ.get('GATE_OC_TOTAL','0')),
    artifacts_dir=os.environ['GATE_ARTIFACTS'],
)
out = os.path.join(os.environ['GATE_ARTIFACTS'], 'gate_verdict.json')
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
