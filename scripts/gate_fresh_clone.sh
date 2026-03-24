#!/usr/bin/env bash
# gate_fresh_clone.sh — Validate fresh-clone setup path (E3 release gate)
# Usage: ./scripts/gate_fresh_clone.sh [--keep-venv]
# Creates a temporary venv, installs everything per README, runs tests + lint.
# Exit 0 = setup path is reproducible. Exit 1 = something broke.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="/tmp/clarvis-fresh-clone-venv-$$"
KEEP_VENV=false

[[ "${1:-}" == "--keep-venv" ]] && KEEP_VENV=true

cleanup() {
    if ! $KEEP_VENV && [[ -d "$VENV_DIR" ]]; then
        rm -rf "$VENV_DIR"
    fi
}
trap cleanup EXIT

echo "=== E3 Fresh Clone Setup Gate ==="
echo "Repo: $REPO_ROOT"
echo "Venv: $VENV_DIR"
echo ""

# Step 1: Create venv
echo "[1/6] Creating fresh venv..."
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
# Ensure pip works inside venv (override any PIP_USER=1)
export PIP_USER=0
pip install --upgrade pip -q

# Step 2: Install sub-packages
echo "[2/6] Installing sub-packages..."
pip install -e "$REPO_ROOT/packages/clarvis-cost" -q
pip install -e "$REPO_ROOT/packages/clarvis-reasoning" -q
pip install -e "$REPO_ROOT/packages/clarvis-db" -q

# Step 3: Install main package
echo "[3/6] Installing main package with brain extras..."
pip install -e "$REPO_ROOT[brain]" -q

# Step 4: Verify brain import
echo "[4/6] Verifying brain import..."
CLARVIS_WORKSPACE="$REPO_ROOT" python3 -c "from clarvis.brain import brain; print('brain import OK')"

# Step 5: Run tests
echo "[5/6] Running tests..."
pip install pytest -q
CLARVIS_WORKSPACE="$REPO_ROOT" python3 -m pytest \
    "$REPO_ROOT/tests/test_open_source_smoke.py" \
    "$REPO_ROOT/tests/test_contextual_enrich.py" \
    "$REPO_ROOT/tests/test_clr_stability_gate.py" \
    "$REPO_ROOT/tests/test_research_lesson_store.py" \
    "$REPO_ROOT/tests/test_performance_gate_trajectory.py" \
    -v --tb=short

# Step 6: Lint
echo "[6/6] Running lint..."
pip install ruff -q
ruff check "$REPO_ROOT/clarvis/" "$REPO_ROOT/packages/" "$REPO_ROOT/tests/"

echo ""
echo "=== E3 GATE: PASS ==="
echo "Fresh clone setup path is reproducible."
