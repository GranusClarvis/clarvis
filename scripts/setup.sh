#!/usr/bin/env bash
# setup.sh — One-command Clarvis install for fresh clones.
# Usage: bash scripts/setup.sh
#   Options:
#     --dev      Also install dev/test dependencies (ruff, pytest)
#     --no-brain Skip ChromaDB + ONNX (lighter install, no vector memory)
#     --verify   Run verification after install

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DEV=0
BRAIN=1
VERIFY=0

for arg in "$@"; do
    case "$arg" in
        --dev)      DEV=1 ;;
        --no-brain) BRAIN=0 ;;
        --verify)   VERIFY=1 ;;
        --help|-h)
            echo "Usage: bash scripts/setup.sh [--dev] [--no-brain] [--verify]"
            echo ""
            echo "  --dev       Install dev/test extras (ruff, pytest)"
            echo "  --no-brain  Skip ChromaDB + ONNX (lighter install)"
            echo "  --verify    Run verification checks after install"
            exit 0
            ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

echo "=== Clarvis Setup ==="
echo "Python: $(python3 --version 2>&1)"
echo "Repo:   $REPO_ROOT"
echo ""

# Check Python version
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10+ required, found $PY_VERSION"
    exit 1
fi

# Step 1: Install sub-packages (must be before root package)
echo "[1/3] Installing sub-packages..."
pip install -e packages/clarvis-cost -q
pip install -e packages/clarvis-reasoning -q
pip install -e packages/clarvis-db -q
echo "  OK: clarvis-cost, clarvis-reasoning, clarvis-db"

# Step 2: Install main package
echo "[2/3] Installing main package..."
if [ "$BRAIN" -eq 1 ] && [ "$DEV" -eq 1 ]; then
    pip install -e ".[all]" -q
    echo "  OK: clarvis[all] (brain + dev)"
elif [ "$BRAIN" -eq 1 ]; then
    pip install -e ".[brain]" -q
    echo "  OK: clarvis[brain]"
elif [ "$DEV" -eq 1 ]; then
    pip install -e ".[dev]" -q
    echo "  OK: clarvis[dev] (no brain)"
else
    pip install -e . -q
    echo "  OK: clarvis (core only)"
fi

# Step 3: Set CLARVIS_WORKSPACE if not set
echo "[3/3] Environment..."
if [ -z "${CLARVIS_WORKSPACE:-}" ]; then
    echo "  Tip: export CLARVIS_WORKSPACE=\"$REPO_ROOT\""
    echo "  (Add to your shell profile for persistence)"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Quick verify:  python3 -m clarvis brain health"
echo "Run tests:     python3 -m pytest -m 'not slow'"
echo "Full verify:   bash scripts/verify_install.sh"

if [ "$VERIFY" -eq 1 ]; then
    echo ""
    if [ "$BRAIN" -eq 0 ]; then
        bash "$SCRIPT_DIR/verify_install.sh" --no-brain
    else
        bash "$SCRIPT_DIR/verify_install.sh"
    fi
fi
