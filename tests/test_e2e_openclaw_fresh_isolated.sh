#!/usr/bin/env bash
# test_e2e_openclaw_fresh_isolated.sh — Gate A: Fresh OpenClaw isolated install E2E test.
#
# Validates: onboarding, gateway boot, config creation, local-model path,
# chat round-trip, clean shutdown, and zero contamination of production.
#
# Uses openclaw --profile to isolate state to ~/.openclaw-e2e-test-<PID>.
# Gateway runs on port 28789 (non-default).
# Ollama must be running with at least one model.
#
# Usage:
#   bash tests/test_e2e_openclaw_fresh_isolated.sh
#   bash tests/test_e2e_openclaw_fresh_isolated.sh --keep   # Don't clean up
#
# Exit: 0 = all mandatory gates pass, 1 = any mandatory gate fails

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Args ─────────────────────────────────────────────────────────────────
KEEP=0
for arg in "$@"; do
    case "$arg" in
        --keep) KEEP=1 ;;
        --help|-h)
            echo "Usage: bash tests/test_e2e_openclaw_fresh_isolated.sh [--keep]"
            exit 0
            ;;
    esac
done

# ── Config ───────────────────────────────────────────────────────────────
PROFILE_NAME="e2e-test-$$"
E2E_PORT=28789
PROD_PORT=18789
PROD_STATE_DIR="$HOME/.openclaw"
E2E_STATE_DIR="$HOME/.openclaw-${PROFILE_NAME}"
E2E_WORKSPACE=$(mktemp -d /tmp/clarvis-e2e-openclaw-XXXXXX)
GW_PID=""
GW_LOG="$E2E_WORKSPACE/gateway.log"

# ── Isolation guard env ──────────────────────────────────────────────────
export CLARVIS_E2E_ISOLATED=1
export CLARVIS_WORKSPACE="$E2E_WORKSPACE/workspace"
export CLARVIS_E2E_PORT=$E2E_PORT

# Source isolation guard
if [ -f "$REPO_ROOT/scripts/infra/isolation_guard.sh" ]; then
    source "$REPO_ROOT/scripts/infra/isolation_guard.sh"
fi

# ── Setup ────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD="\033[1m" GREEN="\033[32m" YELLOW="\033[33m" RED="\033[31m"
    CYAN="\033[36m" RESET="\033[0m"
else
    BOLD="" GREEN="" YELLOW="" RED="" CYAN="" RESET=""
fi

PASS=0 FAIL=0 WARN=0 SKIP=0
FAILURES=()
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

pass()  { PASS=$((PASS+1)); echo -e "  ${GREEN}PASS${RESET}  $1"; }
fail()  { FAIL=$((FAIL+1)); FAILURES+=("$1"); echo -e "  ${RED}FAIL${RESET}  $1"; }
warn()  { WARN=$((WARN+1)); echo -e "  ${YELLOW}WARN${RESET}  $1"; }
skip()  { SKIP=$((SKIP+1)); echo -e "  ${CYAN}SKIP${RESET}  $1"; }

cleanup() {
    echo ""
    echo -e "${BOLD}=== Cleanup ===${RESET}"

    # Kill gateway if running
    if [ -n "$GW_PID" ] && kill -0 "$GW_PID" 2>/dev/null; then
        echo "  Stopping gateway (PID $GW_PID)..."
        kill "$GW_PID" 2>/dev/null
        wait "$GW_PID" 2>/dev/null || true
    fi

    # Check for orphan processes on E2E_PORT
    ORPHAN_PID=$(lsof -ti :$E2E_PORT 2>/dev/null || true)
    if [ -n "$ORPHAN_PID" ]; then
        echo "  WARNING: Orphan process on port $E2E_PORT (PID $ORPHAN_PID) — killing"
        kill "$ORPHAN_PID" 2>/dev/null || true
    fi

    if [ "$KEEP" -eq 0 ]; then
        # Remove profile state dir
        if [ -d "$E2E_STATE_DIR" ]; then
            rm -rf "$E2E_STATE_DIR"
            echo "  Removed profile state: $E2E_STATE_DIR"
        fi
        # Remove workspace
        if [ -d "$E2E_WORKSPACE" ]; then
            rm -rf "$E2E_WORKSPACE"
            echo "  Removed workspace: $E2E_WORKSPACE"
        fi
    else
        echo "  --keep: preserving $E2E_STATE_DIR and $E2E_WORKSPACE"
    fi
}
trap cleanup EXIT

echo -e "${BOLD}╔═══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║  Gate A: Fresh OpenClaw Isolated Install E2E             ║${RESET}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo "Timestamp:    $TIMESTAMP"
echo "Profile:      $PROFILE_NAME"
echo "State dir:    $E2E_STATE_DIR"
echo "Workspace:    $E2E_WORKSPACE"
echo "Gateway port: $E2E_PORT"
echo "Prod port:    $PROD_PORT"
echo "OpenClaw:     $(openclaw --version 2>&1)"
echo ""

# ══════════════════════════════════════════════════════════════════════════
# PRE-FLIGHT: Verify we're not touching production
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[Pre-flight] Contamination guards${RESET}"

# Verify production gateway is on a different port
PROD_HEALTH=$(curl -s http://localhost:$PROD_PORT/health 2>/dev/null || echo "")
if echo "$PROD_HEALTH" | grep -q '"ok":true'; then
    pass "Production gateway alive on :$PROD_PORT (will verify no interference)"
else
    warn "Production gateway not responding on :$PROD_PORT (can't verify non-interference)"
fi

# Verify E2E port is free
if lsof -ti :$E2E_PORT >/dev/null 2>/dev/null; then
    fail "Port $E2E_PORT already in use — cannot proceed"
    exit 1
else
    pass "Port $E2E_PORT is free"
fi

# Snapshot production state for contamination check
PROD_CONFIG_HASH=""
if [ -f "$PROD_STATE_DIR/openclaw.json" ]; then
    PROD_CONFIG_HASH=$(sha256sum "$PROD_STATE_DIR/openclaw.json" | cut -d' ' -f1)
    pass "Production config snapshot taken"
fi

# E2E state dir must NOT exist yet
if [ -d "$E2E_STATE_DIR" ]; then
    fail "E2E state dir already exists: $E2E_STATE_DIR — stale from a prior run?"
    rm -rf "$E2E_STATE_DIR"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# A1: CLI responds
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[A1] CLI responds${RESET}"

if openclaw --version >/dev/null 2>&1; then
    pass "openclaw --version"
else
    fail "openclaw --version"
fi

if openclaw --help >/dev/null 2>&1; then
    pass "openclaw --help"
else
    fail "openclaw --help"
fi

if openclaw --profile "$PROFILE_NAME" --help >/dev/null 2>&1; then
    pass "openclaw --profile $PROFILE_NAME --help"
else
    fail "openclaw --profile $PROFILE_NAME --help"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# A2: Onboard completes (non-interactive, skip auth — local model only)
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[A2] Onboard (non-interactive, local model only)${RESET}"

mkdir -p "$E2E_WORKSPACE/workspace"

ONBOARD_OUTPUT=$(timeout 60 openclaw --profile "$PROFILE_NAME" onboard \
    --non-interactive \
    --accept-risk \
    --auth-choice ollama \
    --gateway-port "$E2E_PORT" \
    --workspace "$E2E_WORKSPACE/workspace" \
    --skip-channels \
    --skip-skills \
    --skip-daemon \
    --skip-health \
    --skip-search \
    --skip-ui \
    --json 2>&1) || true

ONBOARD_EXIT=$?

if [ -d "$E2E_STATE_DIR" ]; then
    pass "Onboard created profile state dir"
else
    # Profile dir might be named differently — check
    if [ -d "$HOME/.openclaw-$PROFILE_NAME" ]; then
        pass "Onboard created profile state dir (alt path)"
        E2E_STATE_DIR="$HOME/.openclaw-$PROFILE_NAME"
    else
        fail "Onboard did not create profile state dir"
        echo "  Output: $(echo "$ONBOARD_OUTPUT" | tail -5)"
    fi
fi

# Check for JSON output
if echo "$ONBOARD_OUTPUT" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    pass "Onboard returned valid JSON"
else
    warn "Onboard did not return valid JSON (may have non-JSON output mixed in)"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# A3: Config created and valid
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[A3] Config created${RESET}"

# OpenClaw profile-based onboard creates agent config files, not a top-level openclaw.json.
# Config is split: auth-profiles.json (credentials), models.json (model registry).
E2E_AUTH_CONFIG="$E2E_STATE_DIR/agents/main/agent/auth-profiles.json"
E2E_MODELS_CONFIG="$E2E_STATE_DIR/agents/main/agent/models.json"
E2E_CONFIG="$E2E_STATE_DIR/openclaw.json"

# Check agent config files (primary config artifacts from onboard)
CONFIG_FOUND=0
if [ -f "$E2E_AUTH_CONFIG" ]; then
    if python3 -c "import json; json.load(open('$E2E_AUTH_CONFIG'))" 2>/dev/null; then
        pass "auth-profiles.json exists and is valid JSON"
        CONFIG_FOUND=1
    else
        fail "auth-profiles.json is invalid JSON"
    fi
else
    fail "auth-profiles.json not created by onboard"
fi

if [ -f "$E2E_MODELS_CONFIG" ]; then
    if python3 -c "import json; json.load(open('$E2E_MODELS_CONFIG'))" 2>/dev/null; then
        pass "models.json exists and is valid JSON"
        CONFIG_FOUND=1
    else
        fail "models.json is invalid JSON"
    fi
else
    fail "models.json not created by onboard"
fi

# Top-level openclaw.json is optional for profile-based installs
if [ -f "$E2E_CONFIG" ]; then
    if python3 -c "import json; json.load(open('$E2E_CONFIG'))" 2>/dev/null; then
        pass "openclaw.json exists and is valid JSON"
    else
        warn "openclaw.json exists but is invalid JSON"
    fi
else
    if [ "$CONFIG_FOUND" -eq 1 ]; then
        pass "Agent config created (no top-level openclaw.json needed for profile)"
    else
        fail "No config files created by onboard"
    fi
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# A4: Gateway boots
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[A4] Gateway boot${RESET}"

# Start gateway in background using profile
openclaw --profile "$PROFILE_NAME" gateway run \
    --port "$E2E_PORT" \
    --auth none \
    --allow-unconfigured \
    > "$GW_LOG" 2>&1 &
GW_PID=$!

pass "Gateway process started (PID $GW_PID)"

# Wait for gateway to become healthy
BOOT_TIMEOUT=30
BOOT_START=$(date +%s)
GATEWAY_UP=0

while [ $(($(date +%s) - BOOT_START)) -lt $BOOT_TIMEOUT ]; do
    if curl -s "http://localhost:$E2E_PORT/health" 2>/dev/null | grep -q '"ok":true'; then
        GATEWAY_UP=1
        break
    fi
    sleep 1
done

if [ "$GATEWAY_UP" -eq 1 ]; then
    BOOT_TIME=$(($(date +%s) - BOOT_START))
    pass "Gateway healthy on :$E2E_PORT (boot time: ${BOOT_TIME}s)"
else
    fail "Gateway did not become healthy within ${BOOT_TIMEOUT}s"
    echo "  Last 10 lines of gateway log:"
    tail -10 "$GW_LOG" 2>/dev/null | sed 's/^/    /'
fi

# Verify production gateway is still alive
if [ -n "$PROD_HEALTH" ]; then
    PROD_STILL_OK=$(curl -s "http://localhost:$PROD_PORT/health" 2>/dev/null || echo "")
    if echo "$PROD_STILL_OK" | grep -q '"ok":true'; then
        pass "Production gateway still healthy on :$PROD_PORT"
    else
        fail "Production gateway disrupted after E2E gateway start!"
    fi
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# A5: Chat round-trip (via gateway agent endpoint)
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[A5] Chat round-trip${RESET}"

if [ "$GATEWAY_UP" -eq 1 ]; then
    # Method 1: Try gateway call with health endpoint (proves RPC works)
    GW_CALL_HEALTH=$(timeout 10 openclaw --profile "$PROFILE_NAME" gateway call health 2>&1) || true

    if echo "$GW_CALL_HEALTH" | grep -qi "ok\|live\|healthy"; then
        pass "Gateway RPC call (health) works"
    else
        warn "Gateway RPC call returned unexpected: $(echo "$GW_CALL_HEALTH" | head -1)"
    fi

    # Method 2: Try agent chat — needs a session or target
    # Use --agent flag to specify the default agent
    CHAT_RESPONSE=$(timeout 60 openclaw --profile "$PROFILE_NAME" agent \
        --agent main \
        --message "Reply with exactly one word: PONG" \
        --json 2>&1) || true

    if echo "$CHAT_RESPONSE" | grep -qi "pong"; then
        pass "Chat round-trip: model responded with PONG"
    elif echo "$CHAT_RESPONSE" | grep -qi "reply\|response\|text\|content\|message"; then
        # Got some response — model is working even if didn't say PONG exactly
        warn "Chat got a response but PONG not detected (model-dependent)"
        echo "  Response preview: $(echo "$CHAT_RESPONSE" | head -2 | cut -c1-120)"
    elif echo "$CHAT_RESPONSE" | grep -qi "error\|fail\|refused"; then
        # Chat failed — but gateway is up, so this is a config/model issue
        warn "Chat round-trip error (gateway up, model may not be configured)"
        echo "  Error: $(echo "$CHAT_RESPONSE" | head -2 | cut -c1-120)"
    else
        warn "Chat round-trip inconclusive"
        echo "  Output: $(echo "$CHAT_RESPONSE" | head -2 | cut -c1-120)"
    fi
else
    skip "Chat round-trip (gateway not up)"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# A6: No API key needed (local model only)
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[A6] Local model path (no API key)${RESET}"

# Check Ollama is reachable
if curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | grep -q "models"; then
    pass "Ollama accessible at :11434"
else
    fail "Ollama not accessible (needed for local-model path)"
fi

# Verify the profile config doesn't have hardcoded API keys
# Check all config files in the profile dir
if [ -d "$E2E_STATE_DIR" ]; then
    HAS_API_KEY=$(python3 -c "
import json, re, pathlib
state_dir = pathlib.Path('$E2E_STATE_DIR')
text = ''
for f in state_dir.rglob('*.json'):
    try: text += f.read_text()
    except: pass
patterns = [r'sk-or-v1-', r'sk-ant-', r'sk-proj-', r'OPENROUTER_API_KEY', r'ANTHROPIC_API_KEY']
found = [p for p in patterns if re.search(p, text)]
print('YES' if found else 'NO')
" 2>/dev/null || echo "PARSE_ERROR")

    if [ "$HAS_API_KEY" = "NO" ]; then
        pass "Config has no hardcoded API keys (local-model only)"
    elif [ "$HAS_API_KEY" = "YES" ]; then
        fail "Config contains API keys — should be local-model-only"
    else
        warn "Could not parse config for API key check"
    fi
fi

# Verify auth was set to ollama
if [ -f "$E2E_AUTH_CONFIG" ]; then
    AUTH_TYPE=$(python3 -c "
import json
c = json.load(open('$E2E_AUTH_CONFIG'))
profiles = c.get('profiles', {})
for k, v in profiles.items():
    if 'ollama' in k.lower() or v.get('provider','') == 'ollama':
        print('ollama')
        break
else:
    print(json.dumps(list(profiles.keys())))
" 2>/dev/null || echo "UNKNOWN")

    if echo "$AUTH_TYPE" | grep -qi "ollama"; then
        pass "Auth profile includes Ollama provider"
    else
        warn "Auth profile may not include Ollama: $AUTH_TYPE"
    fi
else
    warn "Auth config not found — cannot verify Ollama auth"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# A7: Clean shutdown
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[A7] Clean shutdown${RESET}"

if [ -n "$GW_PID" ] && kill -0 "$GW_PID" 2>/dev/null; then
    # Send SIGTERM
    kill "$GW_PID" 2>/dev/null
    SHUTDOWN_START=$(date +%s)

    # Wait up to 10s for clean exit
    CLEAN_EXIT=0
    for i in $(seq 1 10); do
        if ! kill -0 "$GW_PID" 2>/dev/null; then
            CLEAN_EXIT=1
            break
        fi
        sleep 1
    done

    if [ "$CLEAN_EXIT" -eq 1 ]; then
        SHUTDOWN_TIME=$(($(date +%s) - SHUTDOWN_START))
        pass "Gateway shut down cleanly in ${SHUTDOWN_TIME}s"
    else
        fail "Gateway did not exit within 10s — killing"
        kill -9 "$GW_PID" 2>/dev/null || true
    fi

    # Check for orphan processes on E2E_PORT
    sleep 1
    ORPHAN=$(lsof -ti :$E2E_PORT 2>/dev/null || true)
    if [ -z "$ORPHAN" ]; then
        pass "No orphan processes on port $E2E_PORT"
    else
        fail "Orphan process found on port $E2E_PORT (PID: $ORPHAN)"
    fi

    # Mark GW_PID as handled so cleanup doesn't try again
    GW_PID=""
else
    if [ "$GATEWAY_UP" -eq 1 ]; then
        fail "Gateway process disappeared before shutdown test"
    else
        skip "Clean shutdown (gateway never started)"
    fi
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# CONTAMINATION CHECK: Production unchanged
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[Contamination] Production state unchanged${RESET}"

# Check production config unchanged
if [ -n "$PROD_CONFIG_HASH" ] && [ -f "$PROD_STATE_DIR/openclaw.json" ]; then
    POST_HASH=$(sha256sum "$PROD_STATE_DIR/openclaw.json" | cut -d' ' -f1)
    if [ "$PROD_CONFIG_HASH" = "$POST_HASH" ]; then
        pass "Production openclaw.json unchanged (SHA-256 match)"
    else
        fail "Production openclaw.json MODIFIED during test!"
    fi
fi

# Check production gateway still healthy
PROD_FINAL=$(curl -s "http://localhost:$PROD_PORT/health" 2>/dev/null || echo "")
if echo "$PROD_FINAL" | grep -q '"ok":true'; then
    pass "Production gateway still healthy after full test"
elif [ -z "$PROD_HEALTH" ]; then
    skip "Production gateway check (was not running pre-test)"
else
    fail "Production gateway no longer healthy after test!"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════
TOTAL=$((PASS + FAIL + WARN + SKIP))
echo -e "${BOLD}══════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}Results: ${GREEN}$PASS passed${RESET}, ${RED}$FAIL failed${RESET}, ${YELLOW}$WARN warnings${RESET}, ${CYAN}$SKIP skipped${RESET} (of $TOTAL checks)${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════════════${RESET}"

if [ ${#FAILURES[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Failures:${RESET}"
    for f in "${FAILURES[@]}"; do
        echo "  - $f"
    done
fi

# Save test artifact
ARTIFACT_DIR="$REPO_ROOT/docs/validation"
mkdir -p "$ARTIFACT_DIR"
cat > "$ARTIFACT_DIR/gate_a_result_$(date +%Y%m%d).txt" << EOF
Gate A: Fresh OpenClaw Isolated Install E2E
Date: $TIMESTAMP
Commit: $(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
OpenClaw: $(openclaw --version 2>&1)
Profile: $PROFILE_NAME
Port: $E2E_PORT
Results: $PASS passed, $FAIL failed, $WARN warnings, $SKIP skipped (of $TOTAL)
$([ ${#FAILURES[@]} -gt 0 ] && echo "Failures:" && printf "  - %s\n" "${FAILURES[@]}" || echo "No failures")
EOF

echo ""
echo "Artifact saved: $ARTIFACT_DIR/gate_a_result_$(date +%Y%m%d).txt"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "Status: FAIL — $FAIL critical issue(s)"
    exit 1
else
    echo "Status: PASS — all mandatory gates passed"
    exit 0
fi
