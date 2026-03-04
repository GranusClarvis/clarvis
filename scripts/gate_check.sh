#!/usr/bin/env bash
# gate_check.sh — Pre-merge scalability gate
# Runs: compileall + import_health + spine smoke test + pytest
# Exit 0 = all clear, non-zero = gate failed
# Usage: scripts/gate_check.sh [--quick]

set -euo pipefail

WORKSPACE="/home/agent/.openclaw/workspace"
SCRIPTS="$WORKSPACE/scripts"
PASSED=0
FAILED=0
TOTAL=0
FAILURES=""

# Colors (if terminal)
if [ -t 1 ]; then
    GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
else
    GREEN=''; RED=''; YELLOW=''; NC=''
fi

report() {
    local name="$1" exit_code="$2"
    TOTAL=$((TOTAL + 1))
    if [ "$exit_code" -eq 0 ]; then
        PASSED=$((PASSED + 1))
        printf "${GREEN}PASS${NC} %s\n" "$name"
    else
        FAILED=$((FAILED + 1))
        FAILURES="$FAILURES  - $name\n"
        printf "${RED}FAIL${NC} %s\n" "$name"
    fi
}

echo "=== Gate Check ==="
echo ""

# --- 1. compileall: catch syntax errors across scripts/ and clarvis/ ---
echo "--- compileall ---"
compileall_rc=0
python3 -m py_compile --help >/dev/null 2>&1 || true
# Use compileall in quiet mode; -q suppresses listing, exit 1 on error
python3 -m compileall -q "$SCRIPTS" "$WORKSPACE/clarvis" 2>&1 | tail -5 || compileall_rc=$?
report "compileall (scripts/ + clarvis/)" $compileall_rc

# --- 2. import_health --quick ---
echo ""
echo "--- import_health ---"
health_rc=0
python3 "$SCRIPTS/import_health.py" --quick 2>&1 || health_rc=$?
report "import_health --quick" $health_rc

# --- 3. Spine smoke test: verify clarvis CLI loads ---
echo ""
echo "--- spine smoke test ---"
spine_rc=0
(
    cd "$WORKSPACE"
    # --help must exit 0 and show subcommands
    python3 -m clarvis --help >/dev/null 2>&1
    # brain stats must produce JSON output
    python3 -m clarvis brain stats >/dev/null 2>&1
) || spine_rc=$?
report "spine (clarvis --help + brain stats)" $spine_rc

# --- 4. pytest: run package tests ---
echo ""
echo "--- pytest (clarvis-db) ---"
pytest_rc=0
python3 -m pytest "$WORKSPACE/packages/clarvis-db/tests/" -q --tb=short 2>&1 | tail -10 || pytest_rc=$?
report "pytest (clarvis-db)" $pytest_rc

# --- 5. pytest: CLI tests ---
echo ""
echo "--- pytest (CLI) ---"
cli_test_rc=0
python3 -m pytest "$WORKSPACE/tests/test_cli.py" -q --tb=short 2>&1 | tail -10 || cli_test_rc=$?
report "pytest (test_cli.py)" $cli_test_rc

# --- 5b. pytest: pipeline integration tests ---
echo ""
echo "--- pytest (pipeline integration) ---"
pipeline_test_rc=0
python3 -m pytest "$WORKSPACE/tests/test_pipeline_integration.py" -q --tb=short 2>&1 | tail -10 || pipeline_test_rc=$?
report "pytest (test_pipeline_integration.py)" $pipeline_test_rc

# --- 6. clarvis queue status (smoke) ---
echo ""
echo "--- clarvis queue status ---"
queue_rc=0
(cd "$WORKSPACE" && python3 -m clarvis queue status >/dev/null 2>&1) || queue_rc=$?
report "clarvis queue status" $queue_rc

# --- 7. clarvis cron list (smoke) ---
echo ""
echo "--- clarvis cron list ---"
cron_rc=0
(cd "$WORKSPACE" && python3 -m clarvis cron list >/dev/null 2>&1) || cron_rc=$?
report "clarvis cron list" $cron_rc

# --- Summary ---
echo ""
echo "=== Gate Result: $PASSED/$TOTAL passed ==="
if [ "$FAILED" -gt 0 ]; then
    printf "${RED}BLOCKED${NC} — failures:\n"
    printf "$FAILURES"
    exit 1
else
    printf "${GREEN}ALL CLEAR${NC}\n"
    exit 0
fi
