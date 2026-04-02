#!/usr/bin/env bash
# verify_install.sh — Post-install verification for Clarvis.
# Checks imports, CLI, brain, test discovery, and profile-specific features.
# Produces a human-readable PASS/WARN/FAIL summary.
#
# Usage: bash scripts/verify_install.sh [--no-brain] [--profile <name>]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export CLARVIS_WORKSPACE="${CLARVIS_WORKSPACE:-$REPO_ROOT}"

NO_BRAIN=0
PROFILE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --no-brain) NO_BRAIN=1; shift ;;
        --profile)  PROFILE="$2"; shift 2 ;;
        --profile=*) PROFILE="${1#*=}"; shift ;;
        --help|-h)
            echo "Usage: bash scripts/verify_install.sh [--no-brain] [--profile <name>]"
            echo "  --no-brain        Treat brain imports as optional (warn, not fail)"
            echo "  --profile <name>  Run profile-specific checks (standalone|openclaw|fullstack|docker)"
            exit 0
            ;;
        *) shift ;;
    esac
done

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
[ -n "$PROFILE" ] && echo "Profile:   $PROFILE"
echo ""

# ── Core imports ──────────────────────────────────────────────────────────
echo "Core imports:"
check "import clarvis" python3 -c "import clarvis"
if [ "$NO_BRAIN" -eq 1 ]; then
    warn_check "import clarvis.brain" python3 -c "from clarvis.brain import brain, search, remember, capture"
else
    check "import clarvis.brain" python3 -c "from clarvis.brain import brain, search, remember, capture"
fi
check "import clarvis.cli" python3 -c "from clarvis.cli import app"
check "import clarvis.heartbeat" python3 -c "import clarvis.heartbeat"
check "import clarvis.cognition" python3 -c "import clarvis.cognition"
if [ "$NO_BRAIN" -eq 1 ]; then
    warn_check "import clarvis.metrics" python3 -c "import clarvis.metrics"
else
    check "import clarvis.metrics" python3 -c "import clarvis.metrics"
fi
check "import clarvis.context" python3 -c "import clarvis.context"
check "import clarvis.runtime" python3 -c "import clarvis.runtime"
echo ""

# ── Sub-packages ──────────────────────────────────────────────────────────
echo "Sub-packages:"
check "import clarvis_db" python3 -c "import clarvis_db"
check "import clarvis_cost" python3 -c "import clarvis_cost"
check "import clarvis_reasoning" python3 -c "import clarvis_reasoning"
echo ""

# ── CLI ───────────────────────────────────────────────────────────────────
echo "CLI:"
check "clarvis --help" python3 -m clarvis --help
if [ "$NO_BRAIN" -eq 1 ]; then
    warn_check "clarvis brain --help" python3 -m clarvis brain --help
else
    check "clarvis brain --help" python3 -m clarvis brain --help
fi
check "clarvis mode --help" python3 -m clarvis mode --help
check "clarvis heartbeat --help" python3 -m clarvis heartbeat --help
echo ""

# ── Brain (optional, needs ChromaDB + data) ───────────────────────────────
echo "Brain (optional — needs ChromaDB + ONNX):"
warn_check "chromadb importable" python3 -c "import chromadb"
warn_check "onnxruntime importable" python3 -c "import onnxruntime"
warn_check "brain health" python3 -m clarvis brain health
echo ""

# ── Dev tools (optional) ─────────────────────────────────────────────────
echo "Dev tools (optional):"
warn_check "ruff available" python3 -m ruff --version
warn_check "pytest available" python3 -m pytest --version
echo ""

# ── Test discovery (canonical root path) ──────────────────────────────────
# This exercises the SAME discovery path as `python3 -m pytest` from root,
# covering tests/ AND packages/*/tests/ via the testpaths config.
echo "Test discovery (canonical pytest path):"
if python3 -m pytest --version >/dev/null 2>&1; then
    # Collect without running — verifies discovery across all test locations
    COLLECT_OUTPUT=$(python3 -m pytest --collect-only -q --no-header 2>&1)
    COLLECT_EXIT=$?

    if [ $COLLECT_EXIT -eq 0 ]; then
        # Count tests from each location
        TOTAL_TESTS=$(echo "$COLLECT_OUTPUT" | grep -c "::" || true)
        ROOT_TESTS=$(echo "$COLLECT_OUTPUT" | grep -c "^tests/" || true)
        PKG_TESTS=$(echo "$COLLECT_OUTPUT" | grep -c "^packages/" || true)

        if [ "$TOTAL_TESTS" -gt 0 ]; then
            echo "  PASS  pytest collection: $TOTAL_TESTS tests ($ROOT_TESTS root, $PKG_TESTS packages)"
            PASS=$((PASS + 1))
        else
            echo "  FAIL  pytest collection: 0 tests found"
            FAIL=$((FAIL + 1))
        fi

        # Verify package tests are discovered (catches silent regressions)
        if [ "$PKG_TESTS" -gt 0 ]; then
            echo "  PASS  package test discovery ($PKG_TESTS tests in packages/)"
            PASS=$((PASS + 1))
        else
            echo "  WARN  no package tests discovered (packages/*/tests/ may be empty)"
            WARN=$((WARN + 1))
        fi
    else
        echo "  FAIL  pytest collection failed"
        FAIL=$((FAIL + 1))
        echo "  WARN  package test discovery skipped (collection failed)"
        WARN=$((WARN + 1))
    fi

    # Run smoke tests (fast subset, not full suite)
    echo ""
    echo "Smoke tests (fast, offline):"
    if python3 -m pytest tests/test_open_source_smoke.py -q --tb=line --no-header 2>&1 | tail -1 | grep -q "passed"; then
        echo "  PASS  open-source smoke tests"
        PASS=$((PASS + 1))
    else
        echo "  FAIL  open-source smoke tests"
        FAIL=$((FAIL + 1))
    fi

    # Run package tests (import reliability, basic functionality)
    PKG_TEST_RESULT=0
    for pkg_test_dir in packages/*/tests; do
        if [ -d "$pkg_test_dir" ]; then
            pkg_name=$(basename "$(dirname "$pkg_test_dir")")
            if python3 -m pytest "$pkg_test_dir" -q --tb=line --no-header -m "not slow" 2>&1 | tail -1 | grep -qE "passed|no tests ran"; then
                echo "  PASS  $pkg_name tests"
                PASS=$((PASS + 1))
            else
                echo "  FAIL  $pkg_name tests"
                FAIL=$((FAIL + 1))
                PKG_TEST_RESULT=1
            fi
        fi
    done
else
    echo "  WARN  pytest not installed — test discovery skipped"
    WARN=$((WARN + 1))
fi
echo ""

# ── Profile-specific checks ──────────────────────────────────────────────
if [ -n "$PROFILE" ]; then
    echo "Profile checks ($PROFILE):"
    case "$PROFILE" in
        standalone)
            check "writable data dir" test -w "$REPO_ROOT/data" -o -w "$REPO_ROOT"
            check ".env exists" test -f "$REPO_ROOT/.env"
            ;;
        openclaw)
            check ".env exists" test -f "$REPO_ROOT/.env"
            if command -v openclaw &>/dev/null || [ -f "$HOME/.npm-global/lib/node_modules/openclaw/dist/index.js" ]; then
                echo "  PASS  OpenClaw installed"
                PASS=$((PASS + 1))
            else
                echo "  WARN  OpenClaw not found (install with: npm install -g openclaw)"
                WARN=$((WARN + 1))
            fi
            ;;
        fullstack)
            check ".env exists" test -f "$REPO_ROOT/.env"
            if command -v openclaw &>/dev/null || [ -f "$HOME/.npm-global/lib/node_modules/openclaw/dist/index.js" ]; then
                echo "  PASS  OpenClaw installed"
                PASS=$((PASS + 1))
            else
                echo "  WARN  OpenClaw not found"
                WARN=$((WARN + 1))
            fi
            if systemctl --user is-enabled openclaw-gateway.service &>/dev/null 2>&1; then
                echo "  PASS  systemd service enabled"
                PASS=$((PASS + 1))
            else
                echo "  WARN  systemd service not enabled"
                WARN=$((WARN + 1))
            fi
            warn_check "crontab configured" bash -c "crontab -l 2>/dev/null | grep -q clarvis"
            ;;
        docker)
            check "Docker available" command -v docker
            check "docker-compose.yml exists" test -f "$REPO_ROOT/docker-compose.yml"
            ;;
    esac
    echo ""
fi

# ── Summary ───────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + WARN))
echo "=== Results: $PASS passed, $FAIL failed, $WARN warnings (of $TOTAL checks) ==="

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Some checks failed. See docs/INSTALL.md for troubleshooting."
    exit 1
else
    echo ""
    echo "Installation verified successfully."
    exit 0
fi
