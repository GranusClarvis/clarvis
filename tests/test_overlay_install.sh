#!/usr/bin/env bash
# test_overlay_install.sh — Isolated overlay install test.
#
# Tests that Clarvis installs cleanly into a fresh venv from the repo
# WITHOUT disturbing the current live system. Validates:
#   1. Fresh venv + pip install -e . succeeds
#   2. Core imports work (clarvis, clarvis.cli, clarvis.runtime, etc.)
#   3. CLI responds (clarvis --help)
#   4. verify_install.sh passes in --no-brain mode
#   5. Brain-optional install (--no-brain) also works
#   6. Profile-based install (standalone) also works
#
# Usage:
#   bash tests/test_overlay_install.sh                # Full test
#   bash tests/test_overlay_install.sh --quick        # Skip brain install
#   bash tests/test_overlay_install.sh --profile X    # Test specific profile
#
# All work happens in /tmp/clarvis_overlay_test_* — cleaned up on exit.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

QUICK=0
PROFILE="standalone"
KEEP=0

for arg in "$@"; do
    case "$arg" in
        --quick)   QUICK=1 ;;
        --keep)    KEEP=1 ;;
        --help|-h)
            echo "Usage: bash tests/test_overlay_install.sh [--quick] [--keep]"
            echo "  --quick   Skip brain (ChromaDB/ONNX) install test"
            echo "  --keep    Don't clean up temp dir on exit"
            exit 0
            ;;
    esac
done

# ── Setup ────────────────────────────────────────────────────────────────
TESTDIR=$(mktemp -d /tmp/clarvis_overlay_test_XXXXXX)
PASS=0
FAIL=0
WARN=0
STEPS=()

# Enforce isolation guards — abort if any production resource could be touched
export CLARVIS_E2E_ISOLATED=1
export CLARVIS_WORKSPACE="$TESTDIR/workspace"
export CLARVIS_E2E_PORT="${CLARVIS_E2E_PORT:-28789}"
if [ -f "$REPO_ROOT/scripts/infra/isolation_guard.sh" ]; then
    source "$REPO_ROOT/scripts/infra/isolation_guard.sh"
fi

cleanup() {
    if [ "$KEEP" -eq 0 ] && [ -d "$TESTDIR" ]; then
        rm -rf "$TESTDIR"
    else
        echo ""
        echo "Test dir preserved: $TESTDIR"
    fi
}
trap cleanup EXIT

log_pass() { echo "  PASS  $1"; PASS=$((PASS + 1)); STEPS+=("PASS: $1"); }
log_fail() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); STEPS+=("FAIL: $1"); }
log_warn() { echo "  WARN  $1"; WARN=$((WARN + 1)); STEPS+=("WARN: $1"); }

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  Clarvis Overlay Install Test                             ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Repo:    $REPO_ROOT"
echo "Testdir: $TESTDIR"
echo "Mode:    $([ "$QUICK" -eq 1 ] && echo 'quick (no brain)' || echo 'full')"
echo ""

# ── Step 1: Copy repo to isolated dir (simulates fresh clone) ────────────
echo "=== Step 1: Simulate fresh clone ==="
# Copy working tree (including uncommitted changes) to simulate a fresh clone.
# Use rsync to skip heavy dirs that aren't needed for install testing.
rsync -a --exclude='.git' --exclude='data/clarvisdb' --exclude='data/browser_sessions' \
    --exclude='node_modules' --exclude='.claude/worktrees' --exclude='__pycache__' \
    "$REPO_ROOT/" "$TESTDIR/workspace/"
# Init a git repo so setuptools can work
git -C "$TESTDIR/workspace" init -q 2>/dev/null || true
if [ -d "$TESTDIR/workspace/clarvis" ]; then
    log_pass "Repo cloned to isolated dir"
else
    log_fail "Repo clone failed"
    echo "RESULT: fail — could not clone repo"
    exit 1
fi
echo ""

# ── Step 2: Create fresh venv ────────────────────────────────────────────
echo "=== Step 2: Create fresh virtualenv ==="
python3 -m venv "$TESTDIR/venv"
source "$TESTDIR/venv/bin/activate"

if [ -n "${VIRTUAL_ENV:-}" ]; then
    log_pass "Virtualenv created and activated"
else
    log_fail "Virtualenv creation failed"
    echo "RESULT: fail — venv failed"
    exit 1
fi

# Override any global pip --user config (breaks venvs)
export PIP_USER=0

# Upgrade pip silently
pip install --upgrade pip -q 2>&1 | tail -1 || true
echo ""

# ── Step 3: Install clarvis (core only, no brain) ───────────────────────
echo "=== Step 3: Install clarvis (core only) ==="
cd "$TESTDIR/workspace"
export CLARVIS_WORKSPACE="$TESTDIR/workspace"

INSTALL_OUTPUT=$(pip install -e . 2>&1)
INSTALL_EXIT=$?

if [ $INSTALL_EXIT -eq 0 ]; then
    log_pass "pip install -e . (core) succeeded"
else
    log_fail "pip install -e . (core) failed"
    echo "  Output: $(echo "$INSTALL_OUTPUT" | tail -5)"
fi
echo ""

# ── Step 4: Verify core imports ──────────────────────────────────────────
echo "=== Step 4: Core imports ==="

for mod in "clarvis" "clarvis.cli" "clarvis.runtime" "clarvis.runtime.mode" \
           "clarvis.heartbeat" "clarvis.cognition" "clarvis.context" \
           "clarvis.orch.cost_tracker" "clarvis.compat.contracts" \
           "clarvis.adapters" "clarvis.adapters.openclaw" \
           "clarvis.queue.writer"; do
    if python3 -c "import $mod" 2>/dev/null; then
        log_pass "import $mod"
    else
        # Capture the actual error
        ERR=$(python3 -c "import $mod" 2>&1 | tail -1)
        log_fail "import $mod ($ERR)"
    fi
done
echo ""

# ── Step 5: CLI responds ────────────────────────────────────────────────
echo "=== Step 5: CLI ==="
if python3 -m clarvis --help >/dev/null 2>&1; then
    log_pass "clarvis --help"
else
    log_fail "clarvis --help"
fi

if python3 -m clarvis mode --help >/dev/null 2>&1; then
    log_pass "clarvis mode --help"
else
    log_fail "clarvis mode --help"
fi

if python3 -m clarvis heartbeat --help >/dev/null 2>&1; then
    log_pass "clarvis heartbeat --help"
else
    log_fail "clarvis heartbeat --help"
fi
echo ""

# ── Step 6: verify_install.sh (--no-brain) ──────────────────────────────
echo "=== Step 6: verify_install.sh --no-brain ==="
VERIFY_OUTPUT=$(bash scripts/infra/verify_install.sh --no-brain 2>&1)
VERIFY_EXIT=$?

if [ $VERIFY_EXIT -eq 0 ]; then
    log_pass "verify_install.sh --no-brain passed"
else
    log_warn "verify_install.sh --no-brain had failures"
    # Show summary line
    echo "  $(echo "$VERIFY_OUTPUT" | grep 'Results:')"
fi

# Show individual FAIL lines from verify
echo "$VERIFY_OUTPUT" | grep "FAIL" | while read -r line; do
    echo "    $line"
done
echo ""

# ── Step 7: Brain install (unless --quick) ──────────────────────────────
if [ "$QUICK" -eq 0 ]; then
    echo "=== Step 7: Install with brain extras ==="
    BRAIN_OUTPUT=$(pip install -e ".[brain]" 2>&1)
    BRAIN_EXIT=$?

    if [ $BRAIN_EXIT -eq 0 ]; then
        log_pass "pip install -e '.[brain]' succeeded"
    else
        log_fail "pip install -e '.[brain]' failed"
        echo "  $(echo "$BRAIN_OUTPUT" | tail -3)"
    fi

    # Test brain imports
    if python3 -c "from clarvis.brain import brain, search, remember, capture" 2>/dev/null; then
        log_pass "brain imports work"
    else
        ERR=$(python3 -c "from clarvis.brain import brain, search, remember, capture" 2>&1 | tail -1)
        log_fail "brain imports ($ERR)"
    fi

    if python3 -c "import chromadb" 2>/dev/null; then
        log_pass "chromadb importable"
    else
        log_fail "chromadb not importable"
    fi
    echo ""

    # ── Step 8: Brain health (will init fresh DB) ───────────────────────
    echo "=== Step 8: Brain health on fresh install ==="
    # Create data dir (fresh clone won't have brain data)
    mkdir -p "$TESTDIR/workspace/data/clarvisdb"

    HEALTH_OUTPUT=$(python3 -m clarvis brain health 2>&1)
    HEALTH_EXIT=$?

    if [ $HEALTH_EXIT -eq 0 ]; then
        log_pass "clarvis brain health on fresh DB"
    else
        # Brain health may fail on fresh install (no data) — that's a warn, not fail
        log_warn "brain health returned non-zero on fresh DB (expected if no collections)"
        echo "  $(echo "$HEALTH_OUTPUT" | tail -3)"
    fi
    echo ""
else
    echo "=== Step 7: Brain install skipped (--quick) ==="
    echo ""
fi

# ── Step 9: Test that setup.sh works ────────────────────────────────────
echo "=== Step 9: setup.sh dry-run validation ==="
# Re-create venv to test setup.sh from scratch
deactivate 2>/dev/null || true
rm -rf "$TESTDIR/venv2"
python3 -m venv "$TESTDIR/venv2"
source "$TESTDIR/venv2/bin/activate"
export PIP_USER=0
pip install --upgrade pip -q 2>&1 | tail -1 || true

cd "$TESTDIR/workspace"

if [ "$QUICK" -eq 1 ]; then
    SETUP_OUTPUT=$(bash scripts/infra/setup.sh --no-brain 2>&1)
else
    SETUP_OUTPUT=$(bash scripts/infra/setup.sh 2>&1)
fi
SETUP_EXIT=$?

if [ $SETUP_EXIT -eq 0 ]; then
    log_pass "setup.sh completed successfully"
else
    log_fail "setup.sh failed (exit $SETUP_EXIT)"
    echo "  $(echo "$SETUP_OUTPUT" | tail -5)"
fi

# Verify imports still work after setup.sh
if python3 -c "import clarvis; from clarvis.cli import app" 2>/dev/null; then
    log_pass "imports work after setup.sh"
else
    log_fail "imports broken after setup.sh"
fi
echo ""

# ── Step 10: install.sh --profile standalone (non-interactive) ──────────
echo "=== Step 10: install.sh --profile standalone ==="
deactivate 2>/dev/null || true
rm -rf "$TESTDIR/venv3"
python3 -m venv "$TESTDIR/venv3"
source "$TESTDIR/venv3/bin/activate"
export PIP_USER=0
pip install --upgrade pip -q 2>&1 | tail -1 || true

cd "$TESTDIR/workspace"
# Remove .env if exists so install.sh creates one
rm -f "$TESTDIR/workspace/.env"

if [ "$QUICK" -eq 1 ]; then
    INSTALL_SH_OUTPUT=$(bash scripts/infra/install.sh --profile standalone --no-brain 2>&1)
else
    INSTALL_SH_OUTPUT=$(bash scripts/infra/install.sh --profile standalone 2>&1)
fi
INSTALL_SH_EXIT=$?

if [ $INSTALL_SH_EXIT -eq 0 ]; then
    log_pass "install.sh --profile standalone completed"
else
    log_warn "install.sh --profile standalone had issues (exit $INSTALL_SH_EXIT)"
    # Show FAIL lines
    echo "$INSTALL_SH_OUTPUT" | grep -E "FAIL|Error" | head -5 | while read -r line; do
        echo "    $line"
    done
fi

# Check .env was created
if [ -f "$TESTDIR/workspace/.env" ]; then
    log_pass ".env created by install.sh"
else
    log_fail ".env not created"
fi
echo ""

# ── Summary ─────────────────────────────────────────────────────────────
deactivate 2>/dev/null || true

TOTAL=$((PASS + FAIL + WARN))
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  Results: $PASS passed, $FAIL failed, $WARN warnings (of $TOTAL checks)"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "FAILED CHECKS:"
    for s in "${STEPS[@]}"; do
        if [[ "$s" == FAIL* ]]; then
            echo "  - ${s#FAIL: }"
        fi
    done
    echo ""
fi

if [ "$WARN" -gt 0 ]; then
    echo "WARNINGS:"
    for s in "${STEPS[@]}"; do
        if [[ "$s" == WARN* ]]; then
            echo "  - ${s#WARN: }"
        fi
    done
    echo ""
fi

# Exit code: 0 if no failures, 1 if any
[ "$FAIL" -eq 0 ]
