#!/usr/bin/env bash
# regression_suite.sh — Durable install regression suite for pre-release validation.
#
# Runs all repeatable install/smoke/gate checks and produces a summary report.
# Designed to be rerun before every release and after major installer changes.
#
# Usage:
#   bash scripts/infra/regression_suite.sh --all       # Full suite (~10 min)
#   bash scripts/infra/regression_suite.sh --quick      # Fast subset (~2 min)
#   bash scripts/infra/regression_suite.sh --core       # Core smoke only (~3 min)
#   bash scripts/infra/regression_suite.sh --gate-oc    # OpenClaw gate only
#   bash scripts/infra/regression_suite.sh --gate-hm    # Hermes gate only
#   bash scripts/infra/regression_suite.sh --dry-run    # Show what would run
#
# Output: docs/validation/regression_<timestamp>/
#   - summary.md          Human-readable summary
#   - summary.json        Machine-readable results
#   - <suite>/*.log       Per-suite logs
#
# Exit: 0 = all critical pass, 1 = any critical failure, 2 = warnings only

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
REPORT_DIR="$REPO_ROOT/docs/validation/regression_${TIMESTAMP}"

# ── Args ─────────────────────────────────────────────────────────────────
RUN_CORE=0
RUN_OVERLAY=0
RUN_CRON=0
RUN_LOCAL_MODEL=0
RUN_GATE_OC=0
RUN_GATE_HM=0
RUN_OS_SMOKE=0
QUICK=0
DRY_RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --all)
            RUN_CORE=1; RUN_OVERLAY=1; RUN_CRON=1; RUN_LOCAL_MODEL=1
            RUN_GATE_OC=1; RUN_GATE_HM=1; RUN_OS_SMOKE=1
            shift ;;
        --quick)
            RUN_CORE=1; RUN_OS_SMOKE=1; QUICK=1
            shift ;;
        --core)
            RUN_CORE=1; RUN_OVERLAY=1; RUN_CRON=1
            shift ;;
        --gate-oc)  RUN_GATE_OC=1; shift ;;
        --gate-hm)  RUN_GATE_HM=1; shift ;;
        --dry-run)  DRY_RUN=1; shift ;;
        --help|-h)
            sed -n '2,16p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) echo "Unknown flag: $1"; exit 1 ;;
    esac
done

# Default: --core if nothing specified
if [ $((RUN_CORE + RUN_OVERLAY + RUN_CRON + RUN_LOCAL_MODEL + RUN_GATE_OC + RUN_GATE_HM + RUN_OS_SMOKE)) -eq 0 ]; then
    RUN_CORE=1; RUN_OVERLAY=1; RUN_CRON=1
fi

# ── Helpers ──────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD="\033[1m" GREEN="\033[32m" YELLOW="\033[33m" RED="\033[31m" RESET="\033[0m"
else
    BOLD="" GREEN="" YELLOW="" RED="" RESET=""
fi

SUITES_RUN=0
SUITES_PASS=0
SUITES_FAIL=0
SUITES_WARN=0
RESULTS=()

run_suite() {
    local name="$1"
    local cmd="$2"
    local critical="${3:-yes}"

    SUITES_RUN=$((SUITES_RUN + 1))

    if [ "$DRY_RUN" -eq 1 ]; then
        echo -e "  [DRY] ${BOLD}${name}${RESET}: $cmd"
        RESULTS+=("{\"suite\":\"$name\",\"status\":\"dry_run\",\"critical\":$( [ "$critical" = "yes" ] && echo true || echo false )}")
        return 0
    fi

    local suite_dir="$REPORT_DIR/$name"
    mkdir -p "$suite_dir"
    local log_file="$suite_dir/output.log"

    echo -e "\n${BOLD}[$SUITES_RUN] $name${RESET}"
    echo "  Command: $cmd"
    echo "  Log: $log_file"

    local start_ts
    start_ts=$(date +%s)

    eval "$cmd" > "$log_file" 2>&1
    local exit_code=$?

    local end_ts
    end_ts=$(date +%s)
    local duration=$((end_ts - start_ts))

    # Extract pass/fail counts from log (works with fresh_install_smoke.sh format)
    local log_pass log_fail log_warn
    log_pass=$(grep -coE "^\s+PASS\s" "$log_file" 2>/dev/null) || log_pass=0
    log_fail=$(grep -coE "^\s+FAIL\s" "$log_file" 2>/dev/null) || log_fail=0
    log_warn=$(grep -coE "^\s+WARN\s" "$log_file" 2>/dev/null) || log_warn=0

    local status="pass"
    if [ "$exit_code" -ne 0 ]; then
        if [ "$exit_code" -eq 2 ] && [ "$log_fail" -eq 0 ]; then
            status="warn"
            SUITES_WARN=$((SUITES_WARN + 1))
            echo -e "  ${YELLOW}WARN${RESET} (exit=$exit_code, ${duration}s, pass=$log_pass warn=$log_warn)"
        else
            status="fail"
            SUITES_FAIL=$((SUITES_FAIL + 1))
            echo -e "  ${RED}FAIL${RESET} (exit=$exit_code, ${duration}s, pass=$log_pass fail=$log_fail)"
        fi
    else
        SUITES_PASS=$((SUITES_PASS + 1))
        echo -e "  ${GREEN}PASS${RESET} (${duration}s, pass=$log_pass)"
    fi

    RESULTS+=("{\"suite\":\"$name\",\"status\":\"$status\",\"exit_code\":$exit_code,\"duration_s\":$duration,\"checks_pass\":$log_pass,\"checks_fail\":$log_fail,\"checks_warn\":$log_warn,\"critical\":$( [ "$critical" = "yes" ] && echo true || echo false )}")
}

# ── Banner ───────────────────────────────────────────────────────────────
echo "=============================================="
echo "  Clarvis Install Regression Suite"
echo "=============================================="
echo "Timestamp: ${TIMESTAMP}"
echo "Commit:    $(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "Report:    ${REPORT_DIR}"
echo ""

QUICK_FLAG=""
[ "$QUICK" -eq 1 ] && QUICK_FLAG="--quick"

if [ "$DRY_RUN" -eq 0 ]; then
    mkdir -p "$REPORT_DIR"
fi

# ── Run Suites ───────────────────────────────────────────────────────────

# Suite 1: Core smoke (isolated)
if [ "$RUN_CORE" -eq 1 ]; then
    run_suite "core-smoke" \
        "bash '$REPO_ROOT/scripts/infra/fresh_install_smoke.sh' --isolated $QUICK_FLAG" \
        "yes"
fi

# Suite 2: Overlay install test
if [ "$RUN_OVERLAY" -eq 1 ]; then
    run_suite "overlay-install" \
        "bash '$REPO_ROOT/tests/test_overlay_install.sh'" \
        "yes"
fi

# Suite 3: Cron e2e (isolated)
if [ "$RUN_CRON" -eq 1 ]; then
    run_suite "cron-e2e" \
        "python3 -m pytest '$REPO_ROOT/tests/test_cron_isolated_e2e.py' -v --tb=short" \
        "yes"
fi

# Suite 4: Local model harness
if [ "$RUN_LOCAL_MODEL" -eq 1 ]; then
    run_suite "local-model" \
        "bash '$REPO_ROOT/scripts/infra/local_model_harness.sh' test" \
        "no"
fi

# Suite 5: OpenClaw release gate
if [ "$RUN_GATE_OC" -eq 1 ]; then
    run_suite "gate-openclaw" \
        "bash '$REPO_ROOT/scripts/infra/release_gate_openclaw.sh' $QUICK_FLAG" \
        "yes"
fi

# Suite 6: Hermes release gate
if [ "$RUN_GATE_HM" -eq 1 ]; then
    run_suite "gate-hermes" \
        "bash '$REPO_ROOT/scripts/infra/release_gate_hermes.sh' $QUICK_FLAG" \
        "no"
fi

# Suite 7: Open-source smoke (pytest)
if [ "$RUN_OS_SMOKE" -eq 1 ]; then
    run_suite "open-source-smoke" \
        "python3 -m pytest '$REPO_ROOT/tests/test_open_source_smoke.py' -v --tb=short" \
        "yes"
fi

# ── Summary ──────────────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  Summary"
echo "=============================================="
echo "Suites run:  $SUITES_RUN"
echo -e "Passed:      ${GREEN}$SUITES_PASS${RESET}"
[ "$SUITES_WARN" -gt 0 ] && echo -e "Warnings:    ${YELLOW}$SUITES_WARN${RESET}"
[ "$SUITES_FAIL" -gt 0 ] && echo -e "Failed:      ${RED}$SUITES_FAIL${RESET}"
echo ""

if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY RUN] No tests were executed."
    exit 0
fi

# ── Write Reports ────────────────────────────────────────────────────────

# JSON summary
{
    echo "{"
    echo "  \"timestamp\": \"${TIMESTAMP}\","
    echo "  \"commit\": \"$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)\","
    echo "  \"suites_run\": $SUITES_RUN,"
    echo "  \"suites_pass\": $SUITES_PASS,"
    echo "  \"suites_fail\": $SUITES_FAIL,"
    echo "  \"suites_warn\": $SUITES_WARN,"
    echo "  \"overall\": \"$( [ "$SUITES_FAIL" -eq 0 ] && echo "PASS" || echo "FAIL")\","
    echo "  \"results\": ["
    _first=1
    for r in "${RESULTS[@]}"; do
        [ "$_first" -eq 0 ] && echo ","
        echo -n "    $r"
        _first=0
    done
    echo ""
    echo "  ]"
    echo "}"
} > "$REPORT_DIR/summary.json"

# Markdown summary
{
    echo "# Regression Suite Report — ${TIMESTAMP}"
    echo ""
    echo "| Property | Value |"
    echo "|----------|-------|"
    echo "| Date | $(date -u +%Y-%m-%d) |"
    echo "| Commit | $(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown) |"
    echo "| Suites run | $SUITES_RUN |"
    echo "| Passed | $SUITES_PASS |"
    echo "| Warnings | $SUITES_WARN |"
    echo "| Failed | $SUITES_FAIL |"
    echo "| Overall | $( [ "$SUITES_FAIL" -eq 0 ] && echo "**PASS**" || echo "**FAIL**") |"
    echo ""
    echo "## Suite Results"
    echo ""
    echo "| Suite | Status | Exit | Duration | Pass | Fail | Warn | Critical |"
    echo "|-------|--------|------|----------|------|------|------|----------|"
    for r in "${RESULTS[@]}"; do
        # Parse JSON-ish fields (simple extraction)
        s_name=$(echo "$r" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['suite'])" 2>/dev/null || echo "?")
        s_status=$(echo "$r" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['status'])" 2>/dev/null || echo "?")
        s_exit=$(echo "$r" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('exit_code','—'))" 2>/dev/null || echo "—")
        s_dur=$(echo "$r" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('duration_s','—'))" 2>/dev/null || echo "—")
        s_pass=$(echo "$r" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('checks_pass','—'))" 2>/dev/null || echo "—")
        s_fail=$(echo "$r" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('checks_fail','—'))" 2>/dev/null || echo "—")
        s_warn=$(echo "$r" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('checks_warn','—'))" 2>/dev/null || echo "—")
        s_crit=$(echo "$r" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print('YES' if d.get('critical') else 'no')" 2>/dev/null || echo "?")
        echo "| $s_name | $s_status | $s_exit | ${s_dur}s | $s_pass | $s_fail | $s_warn | $s_crit |"
    done
    echo ""
    echo "## Logs"
    echo ""
    echo "Per-suite logs are in \`docs/validation/regression_${TIMESTAMP}/<suite>/output.log\`."
    echo ""
    echo "## Next Steps"
    echo ""
    if [ "$SUITES_FAIL" -gt 0 ]; then
        echo "- **FAIL**: Investigate failed suites before making release claims."
        echo "- Update \`docs/SUPPORT_MATRIX.md\` to reflect current reality."
    else
        echo "- All critical suites passed. Safe to make claims matching \`docs/SUPPORT_MATRIX.md\`."
    fi
    echo ""
    echo "---"
    echo "_Generated by \`scripts/infra/regression_suite.sh\`_"
} > "$REPORT_DIR/summary.md"

echo "Reports written to: $REPORT_DIR/"
echo "  summary.md   — Human-readable"
echo "  summary.json — Machine-readable"

# ── Exit ─────────────────────────────────────────────────────────────────
if [ "$SUITES_FAIL" -gt 0 ]; then
    echo -e "\n${RED}REGRESSION SUITE FAILED${RESET} — $SUITES_FAIL suite(s) with critical failures."
    exit 1
elif [ "$SUITES_WARN" -gt 0 ]; then
    echo -e "\n${YELLOW}REGRESSION SUITE PASSED WITH WARNINGS${RESET}"
    exit 2
else
    echo -e "\n${GREEN}REGRESSION SUITE PASSED${RESET}"
    exit 0
fi
