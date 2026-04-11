#!/usr/bin/env bash
# collect_test_artifacts.sh — Standardize and collect E2E test artifacts.
#
# Runs all release gate scripts and collects artifacts into a single
# timestamped directory with a unified summary report.
#
# Usage:
#   bash scripts/infra/collect_test_artifacts.sh               # Full collection
#   bash scripts/infra/collect_test_artifacts.sh --quick        # Fast subset
#   bash scripts/infra/collect_test_artifacts.sh --report-only  # Summary of existing artifacts
#
# Artifacts: docs/validation/run_<YYYYMMDD_HHMMSS>/
#   run_summary.json       Machine-readable summary of all gates
#   run_summary.txt        Human-readable report
#   gate_a/                Gate A artifacts (if run)
#   gate_c/                Gate C artifacts
#   hermes/                Hermes gate artifacts
#   commands.txt           Exact commands run with timing
#
# Exit: 0 = all gates pass, 1 = any gate fails

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
RUN_DIR="$REPO_ROOT/docs/validation/run_${TIMESTAMP}"
QUICK=""
REPORT_ONLY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --quick)       QUICK="--quick"; shift ;;
        --report-only) REPORT_ONLY=1; shift ;;
        --help|-h)
            sed -n '2,16p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) shift ;;
    esac
done

# ── Report-only mode: summarize existing artifacts ─────────────────────
if [ "$REPORT_ONLY" -eq 1 ]; then
    echo "=== Existing Validation Artifacts ==="
    echo ""
    VAL_DIR="$REPO_ROOT/docs/validation"

    # Find all verdict JSON files
    VERDICT_FILES=$(find "$VAL_DIR" -name "gate_verdict.json" -type f 2>/dev/null | sort -r)

    if [ -z "$VERDICT_FILES" ]; then
        echo "No gate verdict files found in $VAL_DIR"
        echo ""
        echo "Individual reports:"
        ls -1t "$VAL_DIR"/*.txt "$VAL_DIR"/*.md 2>/dev/null | head -20 | while read -r f; do
            echo "  $(basename "$f")  $(date -r "$f" +%Y-%m-%d 2>/dev/null)"
        done
    else
        echo "Gate verdicts (most recent first):"
        echo ""
        echo "$VERDICT_FILES" | while read -r vf; do
            DIR="$(dirname "$vf")"
            GATE=$(python3 -c "import json; d=json.load(open('$vf')); print(d.get('gate','?'))" 2>/dev/null || echo "?")
            VERDICT=$(python3 -c "import json; d=json.load(open('$vf')); print(d.get('verdict','?'))" 2>/dev/null || echo "?")
            TS=$(python3 -c "import json; d=json.load(open('$vf')); print(d.get('timestamp','?'))" 2>/dev/null || echo "?")
            printf "  %-25s %-6s %s  %s\n" "$GATE" "$VERDICT" "$TS" "$(basename "$DIR")"
        done
    fi

    echo ""
    echo "Text reports:"
    find "$VAL_DIR" -maxdepth 1 -name "*.txt" -o -name "*.md" 2>/dev/null | sort -r | head -10 | while read -r f; do
        echo "  $(basename "$f")"
    done

    exit 0
fi

# ── Full collection mode ───────────────────────────────────────────────
mkdir -p "$RUN_DIR"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  E2E Test Artifact Collection                             ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Run ID:    $TIMESTAMP"
echo "Commit:    $(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "Branch:    $(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || echo unknown)"
echo "Output:    $RUN_DIR"
echo "Mode:      $([ -n "$QUICK" ] && echo 'quick' || echo 'full')"
echo ""

COMMANDS=()
GATE_RESULTS=()
ALL_PASS=true

log_cmd() {
    local name="$1" cmd="$2" start end elapsed exit_code
    start=$(date +%s)
    echo "--- Running: $name ---"
    COMMANDS+=("$(date -u +%H:%M:%SZ) $name: $cmd")
    eval "$cmd"
    exit_code=$?
    end=$(date +%s)
    elapsed=$((end - start))
    COMMANDS+=("  -> exit $exit_code (${elapsed}s)")
    echo ""
    return $exit_code
}

# ── Gate C: Overlay install test ─────────────────────────────────────
mkdir -p "$RUN_DIR/gate_c"
echo "=== Gate C: Clarvis-on-OpenClaw Overlay ==="
OVERLAY_EXIT=0
log_cmd "overlay_test" \
    "bash '$REPO_ROOT/tests/test_overlay_install.sh' $QUICK > '$RUN_DIR/gate_c/overlay_test.log' 2>&1" \
    || OVERLAY_EXIT=$?

GATE_C_PASS=$(grep -cE "^\s+PASS\s" "$RUN_DIR/gate_c/overlay_test.log" 2>/dev/null) || GATE_C_PASS=0
GATE_C_FAIL=$(grep -cE "^\s+FAIL\s" "$RUN_DIR/gate_c/overlay_test.log" 2>/dev/null) || GATE_C_FAIL=0
GATE_C_WARN=$(grep -cE "^\s+WARN\s" "$RUN_DIR/gate_c/overlay_test.log" 2>/dev/null) || GATE_C_WARN=0

echo "  Gate C: ${GATE_C_PASS} pass, ${GATE_C_FAIL} fail, ${GATE_C_WARN} warn (exit $OVERLAY_EXIT)"
GATE_RESULTS+=("gate_c:${GATE_C_PASS}:${GATE_C_FAIL}:${GATE_C_WARN}:${OVERLAY_EXIT}")
[ "$OVERLAY_EXIT" -ne 0 ] && ALL_PASS=false

# Save verify_install output separately
log_cmd "verify_install" \
    "bash '$REPO_ROOT/scripts/infra/verify_install.sh' --no-brain > '$RUN_DIR/gate_c/verify_install.log' 2>&1" \
    || true

# Brain health
log_cmd "brain_health" \
    "python3 -m clarvis brain health > '$RUN_DIR/gate_c/brain_health.log' 2>&1" \
    || true

# CLI check
log_cmd "cli_check" \
    "python3 -m clarvis --help > '$RUN_DIR/gate_c/cli_help.log' 2>&1" \
    || true

# Demo
log_cmd "demo" \
    "python3 -m clarvis demo > '$RUN_DIR/gate_c/demo.log' 2>&1" \
    || true

# ── Hermes Gate ──────────────────────────────────────────────────────
mkdir -p "$RUN_DIR/hermes"
echo "=== Hermes Release Gate ==="
HERMES_EXIT=0
log_cmd "hermes_gate" \
    "bash '$REPO_ROOT/scripts/infra/release_gate_hermes.sh' --quick --skip-hermes > '$RUN_DIR/hermes/gate.log' 2>&1" \
    || HERMES_EXIT=$?

# Copy Hermes artifacts into the run dir
HERMES_LATEST=$(ls -dt "$REPO_ROOT/docs/validation/hermes_"* 2>/dev/null | head -1)
if [ -n "$HERMES_LATEST" ] && [ -d "$HERMES_LATEST" ]; then
    cp "$HERMES_LATEST"/* "$RUN_DIR/hermes/" 2>/dev/null || true
fi

HERMES_VERDICT=$(python3 -c "import json; d=json.load(open('$RUN_DIR/hermes/gate_verdict.json')); print(d['verdict'])" 2>/dev/null || echo "UNKNOWN")
echo "  Hermes gate: $HERMES_VERDICT (exit $HERMES_EXIT)"
GATE_RESULTS+=("hermes:$HERMES_VERDICT:exit_$HERMES_EXIT")
[ "$HERMES_EXIT" -ne 0 ] && ALL_PASS=false

# ── OpenClaw Gate (doctor only — full Gate A needs OpenClaw service) ──
mkdir -p "$RUN_DIR/gate_a"
echo "=== Gate A: OpenClaw (doctor check) ==="
DOCTOR_EXIT=0
log_cmd "doctor" \
    "python3 -m clarvis doctor --json > '$RUN_DIR/gate_a/doctor.json' 2>&1" \
    || DOCTOR_EXIT=$?

python3 -m clarvis doctor > "$RUN_DIR/gate_a/doctor.txt" 2>&1 || true

GW_HEALTH=$(curl -s http://localhost:18789/health 2>/dev/null || echo '{"ok":false}')
echo "$GW_HEALTH" > "$RUN_DIR/gate_a/gateway_health.json"
echo "  Gateway: $GW_HEALTH"
echo ""

# ── Save commands log ────────────────────────────────────────────────
printf "%s\n" "${COMMANDS[@]}" > "$RUN_DIR/commands.txt"

# ── Generate summary ────────────────────────────────────────────────
python3 -c "
import json, os, glob

run_dir = '$RUN_DIR'
timestamp = '$TIMESTAMP'
commit = '$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)'
branch = '$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || echo unknown)'
all_pass = $($ALL_PASS && echo 'True' || echo 'False')

# Collect all verdict JSONs in run dir
verdicts = {}
for vf in glob.glob(os.path.join(run_dir, '*/gate_verdict.json')):
    try:
        with open(vf) as f:
            d = json.load(f)
        verdicts[d.get('gate', os.path.basename(os.path.dirname(vf)))] = d
    except Exception:
        pass

summary = dict(
    run_id=timestamp,
    commit=commit,
    branch=branch,
    all_pass=all_pass,
    gates={},
    overlay_test=dict(
        passed=int('${GATE_C_PASS}'),
        failed=int('${GATE_C_FAIL}'),
        warnings=int('${GATE_C_WARN}'),
        exit_code=int('${OVERLAY_EXIT}'),
    ),
    hermes_verdict='$HERMES_VERDICT',
    gateway_healthy='ok' in '$GW_HEALTH',
    artifacts_dir=run_dir,
)
summary['gates'] = verdicts

with open(os.path.join(run_dir, 'run_summary.json'), 'w') as f:
    json.dump(summary, f, indent=2)

# Human-readable report
with open(os.path.join(run_dir, 'run_summary.txt'), 'w') as f:
    f.write(f'E2E Test Run: {timestamp}\n')
    f.write(f'Commit: {commit} ({branch})\n')
    f.write(f'Overall: {\"PASS\" if all_pass else \"FAIL\"}\n')
    f.write(f'\n')
    f.write(f'Gate C (Overlay): {summary[\"overlay_test\"][\"passed\"]} pass, ')
    f.write(f'{summary[\"overlay_test\"][\"failed\"]} fail, ')
    f.write(f'{summary[\"overlay_test\"][\"warnings\"]} warn\n')
    f.write(f'Hermes Gate: {summary[\"hermes_verdict\"]}\n')
    f.write(f'Gateway: {\"healthy\" if summary[\"gateway_healthy\"] else \"down\"}\n')
    f.write(f'\nArtifacts: {run_dir}\n')

print(json.dumps(summary, indent=2))
"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
if $ALL_PASS; then
    echo "║  ALL GATES PASS                                          ║"
else
    echo "║  SOME GATES FAILED — review artifacts                    ║"
fi
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Artifacts: $RUN_DIR"
echo "Summary:   $RUN_DIR/run_summary.json"
echo "Report:    $RUN_DIR/run_summary.txt"
echo "Commands:  $RUN_DIR/commands.txt"

$ALL_PASS
