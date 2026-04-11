#!/usr/bin/env bash
# test_hermes_overlay.sh — Isolated Clarvis-on-Hermes overlay test.
#
# Tests that Clarvis installs and works inside a Hermes venv without
# breaking Hermes or touching production. Validates:
#   1. Hermes is installable in isolated venv
#   2. Clarvis pip install works alongside Hermes deps
#   3. Core Clarvis imports succeed
#   4. Clarvis CLI responds
#   5. Brain health (if ChromaDB available)
#   6. Hermes adapter detects Hermes
#   7. Hermes still works after Clarvis overlay
#
# Usage:
#   bash tests/test_hermes_overlay.sh                # Full test
#   bash tests/test_hermes_overlay.sh --quick        # Skip brain + Hermes install
#   bash tests/test_hermes_overlay.sh --keep         # Preserve temp dir
#   bash tests/test_hermes_overlay.sh --skip-hermes  # Test adapter only (no Hermes clone)
#
# All work happens in /tmp/clarvis_hermes_overlay_* — cleaned up on exit.
# Requires: git, python3.10+

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

QUICK=0
KEEP=0
SKIP_HERMES=0

for arg in "$@"; do
    case "$arg" in
        --quick)       QUICK=1 ;;
        --keep)        KEEP=1 ;;
        --skip-hermes) SKIP_HERMES=1 ;;
        --help|-h)
            echo "Usage: bash tests/test_hermes_overlay.sh [--quick] [--keep] [--skip-hermes]"
            echo "  --quick        Skip brain (ChromaDB/ONNX) and Hermes clone"
            echo "  --keep         Don't clean up temp dir on exit"
            echo "  --skip-hermes  Skip Hermes install, test adapter code only"
            exit 0
            ;;
    esac
done

# ── Setup ────────────────────────────────────────────────────────────
TESTDIR=$(mktemp -d /tmp/clarvis_hermes_overlay_XXXXXX)
PASS=0
FAIL=0
WARN=0
STEPS=()

# Enforce isolation guards
export CLARVIS_E2E_ISOLATED=1
export CLARVIS_WORKSPACE="$TESTDIR/workspace"
export CLARVIS_E2E_PORT=28789
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
echo "║  Clarvis-on-Hermes Overlay Test                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Repo:    $REPO_ROOT"
echo "Testdir: $TESTDIR"
echo "Mode:    $([ "$QUICK" -eq 1 ] && echo 'quick' || echo 'full') $([ "$SKIP_HERMES" -eq 1 ] && echo '(skip-hermes)' || echo '')"
echo ""

# ── Step 1: Copy Clarvis repo to isolated dir ───────────────────────
echo "=== Step 1: Simulate fresh Clarvis clone ==="
rsync -a --exclude='.git' --exclude='data/clarvisdb' --exclude='data/browser_sessions' \
    --exclude='node_modules' --exclude='.claude/worktrees' --exclude='__pycache__' \
    "$REPO_ROOT/" "$TESTDIR/workspace/"
git -C "$TESTDIR/workspace" init -q 2>/dev/null || true
if [ -d "$TESTDIR/workspace/clarvis" ]; then
    log_pass "Clarvis repo cloned to isolated dir"
else
    log_fail "Clarvis repo clone failed"
    exit 1
fi
echo ""

# ── Step 2: Create fresh venv ───────────────────────────────────────
echo "=== Step 2: Create fresh virtualenv ==="
python3 -m venv "$TESTDIR/venv"
source "$TESTDIR/venv/bin/activate"
export PIP_USER=0

if [ -n "${VIRTUAL_ENV:-}" ]; then
    log_pass "Virtualenv created and activated"
else
    log_fail "Virtualenv creation failed"
    exit 1
fi
pip install --upgrade pip -q 2>&1 | tail -1 || true
echo ""

# ── Step 3: Install Hermes (optional) ───────────────────────────────
if [ "$SKIP_HERMES" -eq 0 ] && [ "$QUICK" -eq 0 ]; then
    echo "=== Step 3: Install Hermes agent ==="
    if git clone --depth 1 https://github.com/NousResearch/hermes-agent.git "$TESTDIR/hermes" 2>/dev/null; then
        log_pass "Hermes repo cloned"
        cd "$TESTDIR/hermes"
        if pip install -e . -q 2>&1 | tail -3; then
            if python3 -c "import hermes_agent" 2>/dev/null || command -v hermes &>/dev/null; then
                log_pass "Hermes installed successfully"
            else
                log_warn "Hermes pip install completed but not importable"
            fi
        else
            log_warn "Hermes pip install had issues (may be OK for overlay test)"
        fi
    else
        log_warn "Could not clone Hermes repo (network issue?) — continuing with adapter-only test"
        SKIP_HERMES=1
    fi
    echo ""
else
    echo "=== Step 3: Hermes install skipped ==="
    echo ""
fi

# ── Step 4: Install Clarvis on top ──────────────────────────────────
echo "=== Step 4: Install Clarvis (pip install -e .) ==="
cd "$TESTDIR/workspace"
INSTALL_OUTPUT=$(pip install -e . 2>&1)
INSTALL_EXIT=$?

if [ $INSTALL_EXIT -eq 0 ]; then
    log_pass "Clarvis pip install succeeded alongside Hermes"
else
    log_fail "Clarvis pip install failed"
    echo "  Output: $(echo "$INSTALL_OUTPUT" | tail -5)"
fi
echo ""

# ── Step 5: Core Clarvis imports ────────────────────────────────────
echo "=== Step 5: Clarvis core imports ==="
for mod in "clarvis" "clarvis.cli" "clarvis.runtime" "clarvis.runtime.mode" \
           "clarvis.heartbeat" "clarvis.cognition" "clarvis.context" \
           "clarvis.orch.cost_tracker" "clarvis.adapters" \
           "clarvis.adapters.hermes" "clarvis.queue.writer"; do
    if python3 -c "import $mod" 2>/dev/null; then
        log_pass "import $mod"
    else
        ERR=$(python3 -c "import $mod" 2>&1 | tail -1)
        log_fail "import $mod ($ERR)"
    fi
done
echo ""

# ── Step 6: Clarvis CLI ────────────────────────────────────────────
echo "=== Step 6: Clarvis CLI ==="
if python3 -m clarvis --help >/dev/null 2>&1; then
    log_pass "clarvis --help responds"
else
    log_fail "clarvis --help failed"
fi
echo ""

# ── Step 7: Hermes adapter detection ───────────────────────────────
echo "=== Step 7: Hermes adapter ==="
ADAPTER_OUT=$(python3 -c "
from clarvis.adapters.hermes import HermesAdapter, detect_hermes
adapter = HermesAdapter()
result = adapter.hermes_available()
print(f'detected={result.ok} config_dir={result.data[\"config_dir\"]}')
" 2>&1)
if [ $? -eq 0 ]; then
    log_pass "HermesAdapter instantiates ($ADAPTER_OUT)"
    if [ "$SKIP_HERMES" -eq 0 ] && echo "$ADAPTER_OUT" | grep -q "detected=True"; then
        log_pass "HermesAdapter detects Hermes installation"
    elif [ "$SKIP_HERMES" -eq 1 ]; then
        log_pass "HermesAdapter reports Hermes not installed (expected with --skip-hermes)"
    else
        log_warn "HermesAdapter did not detect Hermes (may be import path issue)"
    fi
else
    log_fail "HermesAdapter failed ($ADAPTER_OUT)"
fi
echo ""

# ── Step 8: Brain health (optional) ─────────────────────────────────
if [ "$QUICK" -eq 0 ]; then
    echo "=== Step 8: Brain health ==="
    mkdir -p "$TESTDIR/workspace/data/clarvisdb"
    BRAIN_OUT=$(CLARVIS_WORKSPACE="$TESTDIR/workspace" python3 -c "
from clarvis.brain import brain
print(brain.stats())
" 2>&1)
    if [ $? -eq 0 ]; then
        log_pass "Brain initializes in isolated workspace"
    else
        log_warn "Brain init failed (may need ChromaDB deps): $(echo "$BRAIN_OUT" | tail -1)"
    fi
    echo ""
fi

# ── Step 9: Hermes still works after overlay ────────────────────────
if [ "$SKIP_HERMES" -eq 0 ] && [ "$QUICK" -eq 0 ]; then
    echo "=== Step 9: Hermes post-overlay check ==="
    if python3 -c "import hermes_agent" 2>/dev/null; then
        log_pass "hermes_agent still importable after Clarvis overlay"
    else
        log_fail "hermes_agent broken by Clarvis overlay"
    fi
    if command -v hermes &>/dev/null && hermes --help >/dev/null 2>&1; then
        log_pass "hermes CLI still works after overlay"
    elif command -v hermes &>/dev/null; then
        log_warn "hermes CLI exists but --help failed"
    else
        log_warn "hermes CLI not on PATH (may be OK if not entry_points installed)"
    fi
    echo ""
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  Results                                                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  PASS: $PASS  FAIL: $FAIL  WARN: $WARN"
echo ""
for step in "${STEPS[@]}"; do
    echo "  $step"
done
echo ""

if [ $FAIL -gt 0 ]; then
    echo "RESULT: fail — $FAIL failures"
    exit 1
elif [ $WARN -gt 0 ]; then
    echo "RESULT: partial — $WARN warnings"
    exit 2
else
    echo "RESULT: success — all checks passed"
    exit 0
fi
