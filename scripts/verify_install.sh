#!/usr/bin/env bash
# verify_install.sh — Post-install verification for Clarvis.
# Checks imports, CLI, brain, and tests without requiring any runtime data.
# Usage: bash scripts/verify_install.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export CLARVIS_WORKSPACE="${CLARVIS_WORKSPACE:-$REPO_ROOT}"

PASS=0
FAIL=0
WARN=0

check() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "  PASS  $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL  $label"
        FAIL=$((FAIL + 1))
    fi
}

warn_check() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "  PASS  $label"
        PASS=$((PASS + 1))
    else
        echo "  WARN  $label (optional)"
        WARN=$((WARN + 1))
    fi
}

echo "=== Clarvis Install Verification ==="
echo "Python:    $(python3 --version 2>&1)"
echo "Workspace: $CLARVIS_WORKSPACE"
echo ""

# --- Core imports ---
echo "Core imports:"
check "import clarvis" python3 -c "import clarvis"
check "import clarvis.brain" python3 -c "from clarvis.brain import brain, search, remember, capture"
check "import clarvis.cli" python3 -c "from clarvis.cli import app"
check "import clarvis.heartbeat" python3 -c "import clarvis.heartbeat"
check "import clarvis.cognition" python3 -c "import clarvis.cognition"
check "import clarvis.metrics" python3 -c "import clarvis.metrics"
check "import clarvis.context" python3 -c "import clarvis.context"
check "import clarvis.runtime" python3 -c "import clarvis.runtime"
echo ""

# --- Sub-packages ---
echo "Sub-packages:"
check "import clarvis_db" python3 -c "import clarvis_db"
check "import clarvis_cost" python3 -c "import clarvis_cost"
check "import clarvis_reasoning" python3 -c "import clarvis_reasoning"
echo ""

# --- CLI ---
echo "CLI:"
check "clarvis --help" python3 -m clarvis --help
check "clarvis brain --help" python3 -m clarvis brain --help
check "clarvis mode --help" python3 -m clarvis mode --help
check "clarvis heartbeat --help" python3 -m clarvis heartbeat --help
echo ""

# --- Brain (optional, needs ChromaDB + data) ---
echo "Brain (optional — needs ChromaDB + ONNX):"
warn_check "chromadb importable" python3 -c "import chromadb"
warn_check "onnxruntime importable" python3 -c "import onnxruntime"
warn_check "brain health" python3 -m clarvis brain health
echo ""

# --- Dev tools (optional) ---
echo "Dev tools (optional):"
warn_check "ruff available" python3 -m ruff --version
warn_check "pytest available" python3 -m pytest --version
if python3 -m pytest --version >/dev/null 2>&1; then
    echo "  Running smoke tests..."
    if python3 -m pytest tests/test_open_source_smoke.py -q --tb=line 2>&1 | tail -1 | grep -q "passed"; then
        echo "  PASS  smoke tests"
        PASS=$((PASS + 1))
    else
        echo "  FAIL  smoke tests"
        FAIL=$((FAIL + 1))
    fi
fi
echo ""

# --- Summary ---
TOTAL=$((PASS + FAIL + WARN))
echo "=== Results: $PASS passed, $FAIL failed, $WARN warnings (of $TOTAL checks) ==="

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Some checks failed. See troubleshooting in README.md."
    exit 1
else
    echo ""
    echo "Installation verified successfully."
    exit 0
fi
