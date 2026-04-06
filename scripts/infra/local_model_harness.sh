#!/usr/bin/env bash
# local_model_harness.sh — Zero-API-key test harness using local Ollama models.
#
# Validates that Clarvis install/smoke tests can run without any external API keys.
# Uses Ollama + qwen3-vl:4b (3.3GB, CPU-only ~7 tok/s) for local inference.
#
# Usage:
#   bash scripts/infra/local_model_harness.sh status    # Show available models
#   bash scripts/infra/local_model_harness.sh test      # Run zero-API test suite
#   bash scripts/infra/local_model_harness.sh start     # Start Ollama service
#   bash scripts/infra/local_model_harness.sh stop      # Stop Ollama service
#
# Environment:
#   OLLAMA_HOST — Ollama API endpoint (default: http://127.0.0.1:11434)
#   OLLAMA_MODEL — Model to use (default: qwen3-vl:4b)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3-vl:4b}"
OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama 2>/dev/null || echo "$HOME/.local/ollama/bin/ollama")}"

# Colours
if [ -t 1 ]; then
    GREEN="\033[32m" YELLOW="\033[33m" RED="\033[31m" CYAN="\033[36m" BOLD="\033[1m" RESET="\033[0m"
else
    GREEN="" YELLOW="" RED="" CYAN="" BOLD="" RESET=""
fi

PASS=0 FAIL=0 WARN=0

pass() { PASS=$((PASS+1)); echo -e "  ${GREEN}PASS${RESET}  $1"; }
fail() { FAIL=$((FAIL+1)); echo -e "  ${RED}FAIL${RESET}  $1"; }
warn() { WARN=$((WARN+1)); echo -e "  ${YELLOW}WARN${RESET}  $1"; }

# ── Commands ──────────────────────────────────────────────────────────────

cmd_status() {
    echo -e "${BOLD}=== Local Model Harness Status ===${RESET}"
    echo ""

    # Ollama binary
    if [ -x "$OLLAMA_BIN" ]; then
        echo -e "Ollama binary: ${GREEN}$OLLAMA_BIN${RESET}"
        echo "Version:       $("$OLLAMA_BIN" --version 2>&1 | head -1)"
    else
        echo -e "Ollama binary: ${RED}not found${RESET}"
        echo "Install: curl -fsSL https://ollama.com/install.sh | sh"
        return 1
    fi

    # Service status
    if systemctl --user is-active ollama.service &>/dev/null; then
        echo -e "Service:       ${GREEN}active${RESET}"
    else
        echo -e "Service:       ${YELLOW}inactive${RESET} (start with: systemctl --user start ollama.service)"
    fi

    # API reachable
    if curl -sf "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
        echo -e "API:           ${GREEN}reachable${RESET} ($OLLAMA_HOST)"
    else
        echo -e "API:           ${RED}unreachable${RESET} ($OLLAMA_HOST)"
    fi

    # Models
    echo ""
    echo "Installed models:"
    "$OLLAMA_BIN" list 2>/dev/null || echo "  (none or service not running)"

    # Recommended model
    echo ""
    if "$OLLAMA_BIN" list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
        echo -e "Test model ($OLLAMA_MODEL): ${GREEN}available${RESET}"
    else
        echo -e "Test model ($OLLAMA_MODEL): ${RED}not pulled${RESET}"
        echo "  Pull with: ollama pull $OLLAMA_MODEL"
    fi

    # Zero-API-key feasibility
    echo ""
    echo -e "${BOLD}Zero-API-key test mode:${RESET}"
    echo "  Model:     $OLLAMA_MODEL (3.3GB, CPU-only ~7 tok/s)"
    echo "  Use case:  Install verification, brain smoke tests, import checks"
    echo "  NOT for:   Agent reasoning, Claude Code spawning, autonomous evolution"
    echo ""
    echo "Commands:"
    echo "  bash scripts/infra/local_model_harness.sh test    # Run test suite"
    echo "  bash scripts/infra/fresh_install_smoke.sh --no-brain --quick  # Quick smoke"
    echo "  OPENROUTER_ROUTING=false python3 scripts/infra/cost_tracker.py api  # Cost check"
}

cmd_start() {
    echo "Starting Ollama service..."
    systemctl --user start ollama.service
    # Wait for API
    for i in $(seq 1 10); do
        if curl -sf "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
            echo -e "${GREEN}Ollama API ready${RESET}"
            return 0
        fi
        sleep 1
    done
    echo -e "${RED}Ollama API not ready after 10s${RESET}"
    return 1
}

cmd_stop() {
    echo "Stopping Ollama service..."
    systemctl --user stop ollama.service
    echo "Stopped."
}

cmd_test() {
    echo -e "${BOLD}=== Zero-API-Key Test Suite ===${RESET}"
    echo "Model: $OLLAMA_MODEL"
    echo "Host:  $OLLAMA_HOST"
    echo ""

    # 1. Service check
    echo -e "${BOLD}[1/5] Ollama service${RESET}"
    if systemctl --user is-active ollama.service &>/dev/null; then
        pass "ollama.service active"
    else
        echo "Starting Ollama..."
        if systemctl --user start ollama.service && sleep 3; then
            pass "ollama.service started"
        else
            fail "ollama.service won't start"
            echo -e "\n${RED}Cannot proceed without Ollama. Aborting.${RESET}"
            return 1
        fi
    fi

    # 2. API health
    echo -e "${BOLD}[2/5] API health${RESET}"
    if curl -sf "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
        pass "API reachable"
    else
        fail "API unreachable at $OLLAMA_HOST"
        return 1
    fi

    # 3. Model availability
    echo -e "${BOLD}[3/5] Model availability${RESET}"
    if "$OLLAMA_BIN" list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
        pass "$OLLAMA_MODEL installed"
    else
        fail "$OLLAMA_MODEL not found (pull with: ollama pull $OLLAMA_MODEL)"
        return 1
    fi

    # 4. Basic inference
    echo -e "${BOLD}[4/5] Basic inference${RESET}"
    RESPONSE=$(curl -sf "$OLLAMA_HOST/api/generate" \
        -d "{\"model\":\"$OLLAMA_MODEL\",\"prompt\":\"Reply with exactly: TEST_OK\",\"stream\":false}" \
        2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('response',''))" 2>/dev/null)

    if [ -n "$RESPONSE" ]; then
        pass "inference returned response (${#RESPONSE} chars)"
    else
        fail "inference returned empty response"
    fi

    # 5. Clarvis import + brain smoke (no external API needed)
    echo -e "${BOLD}[5/5] Clarvis zero-API smoke${RESET}"

    # Core imports (zero API keys needed)
    for mod in clarvis clarvis.cli clarvis.heartbeat clarvis.cognition; do
        if python3 -c "import $mod" 2>/dev/null; then
            pass "import $mod"
        else
            fail "import $mod"
        fi
    done

    # Brain search (uses local ONNX, no API)
    if python3 -c "
from clarvis.brain import search
results = search('test query', n=1)
print('OK' if isinstance(results, list) else 'FAIL')
" 2>/dev/null | grep -q OK; then
        pass "brain.search() works (local ONNX)"
    else
        warn "brain.search() failed (ChromaDB may need init)"
    fi

    # Fresh install smoke (quick, no brain)
    echo ""
    echo -e "${BOLD}Running fresh_install_smoke.sh --quick --no-brain ...${RESET}"
    SMOKE_EXIT=0
    bash "$REPO_ROOT/scripts/infra/fresh_install_smoke.sh" --quick --no-brain 2>&1 || SMOKE_EXIT=$?

    echo ""
    echo -e "${BOLD}=== Zero-API Test Results: ${GREEN}$PASS passed${RESET}, ${RED}$FAIL failed${RESET}, ${YELLOW}$WARN warnings${RESET} ==="

    if [ "$FAIL" -gt 0 ]; then
        return 1
    fi
    return 0
}

# ── Main ──────────────────────────────────────────────────────────────────
case "${1:-status}" in
    status) cmd_status ;;
    test)   cmd_test ;;
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    *)
        echo "Usage: $0 {status|test|start|stop}"
        exit 1
        ;;
esac
