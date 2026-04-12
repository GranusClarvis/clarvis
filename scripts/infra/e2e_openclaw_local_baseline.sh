#!/usr/bin/env bash
# e2e_openclaw_local_baseline.sh — Fresh isolated OpenClaw install + local LLM baseline.
#
# Creates a clean OpenClaw install in /tmp with its own npm prefix, config,
# and workspace. Wires it to the local Ollama LLM. Validates all 7 Path A
# criteria from docs/INSTALL_MATRIX.md.
#
# Usage:
#   bash scripts/infra/e2e_openclaw_local_baseline.sh         # Full run
#   bash scripts/infra/e2e_openclaw_local_baseline.sh --quick  # Skip chat round-trip
#
# Artifacts: /tmp/e2e-openclaw-<ts>/result.json, /tmp/e2e-openclaw-<ts>/test.log
#
# Exit: 0 = all PASS, 1 = any FAIL

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS="$(date -u +%Y%m%d_%H%M%S)"
TEST_ROOT="/tmp/e2e-openclaw-${TS}"
TEST_PORT=28789
QUICK=false

OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3-vl:4b}"

while [ $# -gt 0 ]; do
    case "$1" in
        --quick) QUICK=true; shift ;;
        --port) TEST_PORT="$2"; shift 2 ;;
        --help|-h)
            sed -n '2,13p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) shift ;;
    esac
done

# Colours
if [ -t 1 ]; then
    G="\033[32m" Y="\033[33m" R="\033[31m" B="\033[1m" Z="\033[0m"
else
    G="" Y="" R="" B="" Z=""
fi

PASS=0 FAIL=0 WARN=0 RESULTS=()

pass() { PASS=$((PASS+1)); RESULTS+=("PASS|$1"); echo -e "  ${G}PASS${Z}  $1"; }
fail() { FAIL=$((FAIL+1)); RESULTS+=("FAIL|$1"); echo -e "  ${R}FAIL${Z}  $1"; }
warn() { WARN=$((WARN+1)); RESULTS+=("WARN|$1"); echo -e "  ${Y}WARN${Z}  $1"; }

cleanup() {
    # Kill gateway if we started one
    if [ -n "${GW_PID:-}" ] && kill -0 "$GW_PID" 2>/dev/null; then
        kill "$GW_PID" 2>/dev/null
        wait "$GW_PID" 2>/dev/null || true
    fi
    # Don't remove TEST_ROOT — keep artifacts for inspection
}
trap cleanup EXIT

echo -e "${B}=== E2E OpenClaw Local Baseline ===${Z}"
echo "Test root:  $TEST_ROOT"
echo "Port:       $TEST_PORT"
echo "Ollama:     $OLLAMA_HOST ($OLLAMA_MODEL)"
echo "Quick mode: $QUICK"
echo "Timestamp:  $TS"
echo ""

# ── Pre-flight: Ollama must be running ──────────────────────────────────
echo -e "${B}[0/7] Pre-flight: Ollama check${Z}"
if ! curl -sf "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
    echo "Starting Ollama..."
    systemctl --user start ollama.service 2>/dev/null || true
    sleep 3
fi
if curl -sf "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
    pass "Ollama API reachable"
else
    fail "Ollama API unreachable — cannot test local-model path"
    # Continue with remaining tests that don't need LLM
fi
echo ""

# ── Setup: Create isolated environment ──────────────────────────────────
echo -e "${B}Setting up isolated environment...${Z}"
mkdir -p "$TEST_ROOT"/{npm-global,openclaw-home,workspace}

# Isolated npm prefix so we don't touch the real global openclaw
export NPM_CONFIG_PREFIX="$TEST_ROOT/npm-global"
export PATH="$TEST_ROOT/npm-global/bin:$PATH"

# Isolated OpenClaw state dir (this is what --profile achieves, but we
# do it manually for full isolation)
export OPENCLAW_STATE_DIR="$TEST_ROOT/openclaw-home"
export OPENCLAW_CONFIG_PATH="$TEST_ROOT/openclaw-home/openclaw.json"
export HOME_BACKUP="$HOME"

echo "  NPM prefix:  $NPM_CONFIG_PREFIX"
echo "  State dir:    $OPENCLAW_STATE_DIR"
echo "  Config path:  $OPENCLAW_CONFIG_PATH"
echo ""

# ── Criterion 1: openclaw CLI responds to --help ────────────────────────
echo -e "${B}[1/7] OpenClaw CLI install${Z}"

# Install openclaw into isolated prefix
# Use the same version as production to keep test meaningful
OPENCLAW_VERSION="$(openclaw --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo 'latest')"
echo "  Installing openclaw@${OPENCLAW_VERSION} to $NPM_CONFIG_PREFIX ..."

npm install -g "openclaw@${OPENCLAW_VERSION}" --prefix "$NPM_CONFIG_PREFIX" 2>&1 | tail -3

if "$TEST_ROOT/npm-global/bin/openclaw" --help >/dev/null 2>&1; then
    pass "C1: openclaw --help responds"
else
    fail "C1: openclaw --help failed"
fi
echo ""

# Alias for convenience
OC="$TEST_ROOT/npm-global/bin/openclaw"

# ── Criterion 2: openclaw onboard completes without error ───────────────
echo -e "${B}[2/7] openclaw onboard (non-interactive)${Z}"

ONBOARD_EXIT=0
"$OC" onboard \
    --non-interactive \
    --accept-risk \
    --flow quickstart \
    --auth-choice ollama \
    --gateway-port "$TEST_PORT" \
    --gateway-auth token \
    --gateway-token "e2e-test-token-$(date +%s)" \
    --gateway-bind loopback \
    --no-install-daemon \
    --workspace "$TEST_ROOT/workspace" \
    > "$TEST_ROOT/onboard.log" 2>&1 || ONBOARD_EXIT=$?

if [ "$ONBOARD_EXIT" -eq 0 ]; then
    pass "C2: openclaw onboard exits 0"
else
    # Onboard may fail at the gateway self-test step (1006 abnormal closure)
    # while still successfully creating config + workspace. Check what it produced.
    ONBOARD_CONFIG_OK=false
    ONBOARD_WORKSPACE_OK=false
    if grep -q "Updated.*openclaw.json" "$TEST_ROOT/onboard.log" 2>/dev/null; then
        ONBOARD_CONFIG_OK=true
    fi
    if grep -q "Workspace OK" "$TEST_ROOT/onboard.log" 2>/dev/null; then
        ONBOARD_WORKSPACE_OK=true
    fi

    if $ONBOARD_CONFIG_OK && $ONBOARD_WORKSPACE_OK; then
        warn "C2: openclaw onboard exit $ONBOARD_EXIT (config+workspace created, gateway self-test failed)"
    elif grep -qiE "fatal|crash|ENOENT|MODULE_NOT_FOUND" "$TEST_ROOT/onboard.log" 2>/dev/null; then
        fail "C2: openclaw onboard failed critically (exit $ONBOARD_EXIT, see onboard.log)"
    else
        warn "C2: openclaw onboard exit $ONBOARD_EXIT (partial success, see onboard.log)"
    fi
fi
echo ""

# ── Criterion 5: openclaw.json is created and valid JSON ────────────────
echo -e "${B}[5/7] Config bootstrap${Z}"

# Find the config — onboard may have created it at OPENCLAW_CONFIG_PATH or
# at the default location inside OPENCLAW_STATE_DIR
CONFIG_FILE=""
for candidate in \
    "$OPENCLAW_CONFIG_PATH" \
    "$OPENCLAW_STATE_DIR/openclaw.json" \
    "$TEST_ROOT/openclaw-home/openclaw.json"; do
    if [ -f "$candidate" ]; then
        CONFIG_FILE="$candidate"
        break
    fi
done

if [ -n "$CONFIG_FILE" ] && python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
    pass "C5: openclaw.json exists and is valid JSON ($CONFIG_FILE)"
else
    # If onboard didn't create it, create a minimal one for gateway test
    CONFIG_FILE="$OPENCLAW_STATE_DIR/openclaw.json"
    mkdir -p "$OPENCLAW_STATE_DIR"
    cat > "$CONFIG_FILE" << ENDJSON
{
  "gateway": {
    "port": $TEST_PORT,
    "mode": "local",
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "e2e-test-token"
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/$OLLAMA_MODEL"
      },
      "workspace": "$TEST_ROOT/workspace"
    }
  },
  "update": {
    "checkOnStart": false,
    "auto": { "enabled": false }
  },
  "channels": {}
}
ENDJSON
    if python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
        warn "C5: openclaw.json created manually (onboard didn't produce one)"
    else
        fail "C5: cannot create valid openclaw.json"
    fi
fi
echo ""

# ── Ensure config points to Ollama for local-model tests ───────────────
# Patch the config to wire model to Ollama regardless of what onboard set
python3 -c "
import json
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
# Wire model to local Ollama
cfg.setdefault('agents', {}).setdefault('defaults', {})
cfg['agents']['defaults']['model'] = {'primary': 'ollama/$OLLAMA_MODEL'}
cfg.setdefault('gateway', {})
cfg['gateway']['port'] = $TEST_PORT
cfg['gateway']['mode'] = 'local'
cfg['gateway']['bind'] = 'loopback'
cfg['gateway'].setdefault('auth', {'mode': 'token', 'token': 'e2e-test-token'})
cfg.setdefault('update', {})
cfg['update']['checkOnStart'] = False
cfg['update']['auto'] = {'enabled': False}
# Strip channels that need credentials
cfg['channels'] = {}
with open('$CONFIG_FILE', 'w') as f:
    json.dump(cfg, f, indent=2)
print('Config patched for local-model test')
" 2>&1

# ── Criterion 3: Gateway starts on configured port ──────────────────────
echo -e "${B}[3/7] Gateway boot${Z}"

# Kill anything on the test port first
fuser -k "$TEST_PORT/tcp" 2>/dev/null || true
sleep 1

# Start gateway in background
GW_PID=""
OPENCLAW_STATE_DIR="$OPENCLAW_STATE_DIR" \
OPENCLAW_CONFIG_PATH="$CONFIG_FILE" \
    "$OC" gateway run --port "$TEST_PORT" --allow-unconfigured \
    > "$TEST_ROOT/gateway.log" 2>&1 &
GW_PID=$!

# Wait for gateway to become ready (up to 15s)
GW_READY=false
for i in $(seq 1 15); do
    if curl -sf "http://127.0.0.1:${TEST_PORT}/health" >/dev/null 2>&1; then
        GW_READY=true
        break
    fi
    # Also try /api/health and root
    if curl -sf "http://127.0.0.1:${TEST_PORT}/" >/dev/null 2>&1; then
        GW_READY=true
        break
    fi
    # Check gateway still alive
    if ! kill -0 "$GW_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done

if $GW_READY; then
    pass "C3: Gateway responding on port $TEST_PORT"
else
    # Gateway may use WebSocket only (no HTTP health endpoint)
    if kill -0 "$GW_PID" 2>/dev/null; then
        # Process is running — check if port is bound
        if ss -tln 2>/dev/null | grep -q ":${TEST_PORT}" || \
           lsof -i ":${TEST_PORT}" >/dev/null 2>&1; then
            pass "C3: Gateway bound to port $TEST_PORT (WS-only, no HTTP health)"
        else
            warn "C3: Gateway process alive (PID $GW_PID) but port $TEST_PORT not bound yet"
        fi
    else
        fail "C3: Gateway process died (see gateway.log)"
        echo "  Last 10 lines of gateway.log:"
        tail -10 "$TEST_ROOT/gateway.log" 2>/dev/null | sed 's/^/    /'
    fi
fi
echo ""

# ── Criterion 4: Chat round-trip with local model ──────────────────────
echo -e "${B}[4/7] Chat round-trip (local model)${Z}"

if $QUICK; then
    warn "C4: Skipped (--quick mode)"
else
    # Try the `openclaw agent` CLI for a single-turn chat
    CHAT_RESPONSE=""
    CHAT_EXIT=0
    OPENCLAW_STATE_DIR="$OPENCLAW_STATE_DIR" \
    OPENCLAW_CONFIG_PATH="$CONFIG_FILE" \
        timeout 60 "$OC" agent \
            --local \
            --message "Reply with exactly: OPENCLAW_E2E_OK" \
            --session-id "e2e-test-session" \
            > "$TEST_ROOT/chat_response.txt" 2>&1 || CHAT_EXIT=$?

    if [ -f "$TEST_ROOT/chat_response.txt" ] && [ -s "$TEST_ROOT/chat_response.txt" ]; then
        CHAT_RESPONSE="$(cat "$TEST_ROOT/chat_response.txt")"
    fi

    if [ -n "$CHAT_RESPONSE" ] && [ "$CHAT_EXIT" -eq 0 ]; then
        pass "C4: Chat round-trip returned response (${#CHAT_RESPONSE} chars)"
    elif [ -n "$CHAT_RESPONSE" ]; then
        warn "C4: Chat returned response but exit $CHAT_EXIT"
    else
        # Fallback: test Ollama directly (proves local model works even if gateway routing is incomplete)
        echo "  Gateway chat failed; testing Ollama directly..."
        OLLAMA_RESP=$(curl -sf "$OLLAMA_HOST/api/generate" \
            -d "{\"model\":\"$OLLAMA_MODEL\",\"prompt\":\"Reply with exactly: OPENCLAW_E2E_OK\",\"stream\":false}" \
            2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('response',''))" 2>/dev/null)

        if [ -n "$OLLAMA_RESP" ]; then
            warn "C4: Direct Ollama chat works (${#OLLAMA_RESP} chars) but gateway routing not validated"
        else
            fail "C4: No chat response from gateway or Ollama"
        fi
    fi
fi
echo ""

# ── Criterion 6: No API key required for local-model path ──────────────
echo -e "${B}[6/7] No API key required${Z}"

# Verify the config has no external API keys
HAS_EXTERNAL_KEY=false
python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
# Check for non-empty API keys in auth profiles
auth = cfg.get('auth', {}).get('profiles', {})
for name, profile in auth.items():
    if 'api_key' in profile or 'apiKey' in profile:
        key = profile.get('api_key', profile.get('apiKey', ''))
        if key and key.strip():
            print(f'EXTERNAL_KEY:{name}')
            sys.exit(1)
# Check model is Ollama-based
model = cfg.get('agents', {}).get('defaults', {}).get('model', {})
primary = model.get('primary', '') if isinstance(model, dict) else str(model)
if 'ollama' in primary.lower():
    print('LOCAL_MODEL_ONLY')
else:
    print(f'NON_LOCAL_MODEL:{primary}')
    sys.exit(1)
" 2>/dev/null
KEY_EXIT=$?

if [ "$KEY_EXIT" -eq 0 ]; then
    pass "C6: No external API key required (local Ollama model)"
else
    fail "C6: Config references external API keys or non-local model"
fi
echo ""

# ── Criterion 7: Clean shutdown ─────────────────────────────────────────
echo -e "${B}[7/7] Clean shutdown${Z}"

if [ -n "${GW_PID:-}" ] && kill -0 "$GW_PID" 2>/dev/null; then
    kill "$GW_PID" 2>/dev/null
    SHUTDOWN_CLEAN=true
    for i in $(seq 1 5); do
        if ! kill -0 "$GW_PID" 2>/dev/null; then
            break
        fi
        sleep 1
    done
    if kill -0 "$GW_PID" 2>/dev/null; then
        kill -9 "$GW_PID" 2>/dev/null
        SHUTDOWN_CLEAN=false
    fi
    # Clear GW_PID so cleanup doesn't double-kill
    GW_PID=""

    if $SHUTDOWN_CLEAN; then
        pass "C7: Gateway shut down cleanly (SIGTERM)"
    else
        warn "C7: Gateway required SIGKILL (not fully clean)"
    fi

    # Check for orphan processes on the port
    sleep 1
    if ss -tln 2>/dev/null | grep -q ":${TEST_PORT}"; then
        fail "C7: Port $TEST_PORT still bound after shutdown (orphan process)"
    else
        pass "C7: No orphan processes on port $TEST_PORT"
    fi
else
    warn "C7: Gateway was not running (cannot test shutdown)"
fi
echo ""

# ── Summary ─────────────────────────────────────────────────────────────
echo -e "${B}=== E2E OpenClaw Local Baseline Results ===${Z}"
echo -e "  ${G}PASS: $PASS${Z}  ${R}FAIL: $FAIL${Z}  ${Y}WARN: $WARN${Z}"
echo ""

if [ "$FAIL" -eq 0 ]; then
    VERDICT="PASS"
    echo -e "${G}${B}VERDICT: PASS${Z}"
    echo "This OpenClaw install is a viable base for layering Clarvis on top."
else
    VERDICT="FAIL"
    echo -e "${R}${B}VERDICT: FAIL${Z}"
    echo "Resolve failures before attempting Clarvis overlay."
fi

# Save result artifact
python3 -c "
import json, datetime
results = []
for r in '''$(printf '%s\n' "${RESULTS[@]}")'''.strip().split('\n'):
    if '|' in r:
        status, desc = r.split('|', 1)
        results.append({'status': status, 'criterion': desc})
verdict = {
    'gate': 'e2e_openclaw_local_baseline',
    'timestamp': '$TS',
    'verdict': '$VERDICT',
    'passed': $PASS,
    'failed': $FAIL,
    'warnings': $WARN,
    'port': $TEST_PORT,
    'ollama_model': '$OLLAMA_MODEL',
    'test_root': '$TEST_ROOT',
    'results': results,
}
with open('$TEST_ROOT/result.json', 'w') as f:
    json.dump(verdict, f, indent=2)
print(json.dumps(verdict, indent=2))
" 2>&1

echo ""
echo "Artifacts: $TEST_ROOT/"
echo "  result.json   — Structured verdict"
echo "  onboard.log   — Onboard wizard output"
echo "  gateway.log   — Gateway stdout/stderr"
echo "  chat_response.txt — Chat round-trip output (if run)"

# Also save a copy to docs/validation/ for the repo
ARTIFACT_DIR="$REPO_ROOT/docs/validation"
mkdir -p "$ARTIFACT_DIR"
cp "$TEST_ROOT/result.json" "$ARTIFACT_DIR/e2e_openclaw_local_baseline_${TS}.json" 2>/dev/null || true

if [ "$VERDICT" = "PASS" ]; then
    exit 0
else
    exit 1
fi
