#!/usr/bin/env bash
# e2e_clarvis_on_openclaw_fresh.sh — End-to-end: Clarvis on fresh OpenClaw install.
#
# 1. Creates a fresh OpenClaw install in /tmp (isolated, non-default port)
# 2. Layers Clarvis via install.sh --profile openclaw (as a real user would)
# 3. Validates all core Clarvis features on the fresh install
# 4. Documents friction, failures, and manual steps needed
#
# Usage:
#   bash scripts/infra/e2e_clarvis_on_openclaw_fresh.sh           # Full run
#   bash scripts/infra/e2e_clarvis_on_openclaw_fresh.sh --quick   # Skip brain + chat
#
# Artifacts: docs/validation/e2e_clarvis_on_openclaw_fresh_<ts>/
# Exit: 0 = all critical pass, 1 = critical failures

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS="$(date -u +%Y%m%d_%H%M%S)"
TEST_ROOT="/tmp/e2e-clarvis-openclaw-${TS}"
TEST_PORT=28789
QUICK=false

OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3-vl:4b}"

while [ $# -gt 0 ]; do
    case "$1" in
        --quick) QUICK=true; shift ;;
        --port) TEST_PORT="$2"; shift 2 ;;
        --help|-h)
            sed -n '2,11p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) shift ;;
    esac
done

# Colours
if [ -t 1 ]; then
    G="\033[32m" Y="\033[33m" R="\033[31m" B="\033[1m" C="\033[36m" Z="\033[0m"
else
    G="" Y="" R="" B="" C="" Z=""
fi

PASS=0 FAIL=0 WARN=0 SKIP=0 RESULTS=() FRICTION=()

pass()     { PASS=$((PASS+1)); RESULTS+=("PASS|$1"); echo -e "  ${G}PASS${Z}  $1"; }
fail()     { FAIL=$((FAIL+1)); RESULTS+=("FAIL|$1"); echo -e "  ${R}FAIL${Z}  $1"; }
warn()     { WARN=$((WARN+1)); RESULTS+=("WARN|$1"); echo -e "  ${Y}WARN${Z}  $1"; }
skip_it()  { SKIP=$((SKIP+1)); RESULTS+=("SKIP|$1"); echo -e "  ${C}SKIP${Z}  $1"; }
friction() { FRICTION+=("$1"); echo -e "  ${Y}FRICTION${Z}  $1"; }

cleanup() {
    # Kill gateway if we started one
    if [ -n "${GW_PID:-}" ] && kill -0 "$GW_PID" 2>/dev/null; then
        kill "$GW_PID" 2>/dev/null
        wait "$GW_PID" 2>/dev/null || true
    fi
    # Deactivate venv if active
    type deactivate &>/dev/null && deactivate 2>/dev/null || true
}
trap cleanup EXIT

echo -e "${B}╔═══════════════════════════════════════════════════════════╗${Z}"
echo -e "${B}║  E2E: Clarvis on Fresh OpenClaw Install                   ║${Z}"
echo -e "${B}╚═══════════════════════════════════════════════════════════╝${Z}"
echo ""
echo "Test root:  $TEST_ROOT"
echo "Port:       $TEST_PORT"
echo "Ollama:     $OLLAMA_HOST ($OLLAMA_MODEL)"
echo "Quick mode: $QUICK"
echo "Repo root:  $REPO_ROOT"
echo "Timestamp:  $TS"
echo ""

# ════════════════════════════════════════════════════════════════════════════
# PHASE A: Fresh OpenClaw Install
# ════════════════════════════════════════════════════════════════════════════
echo -e "${B}━━━ PHASE A: Fresh OpenClaw Install ━━━${Z}"
echo ""

mkdir -p "$TEST_ROOT"/{npm-global,openclaw-home,workspace,venv,artifacts}

# Isolation vars
export NPM_CONFIG_PREFIX="$TEST_ROOT/npm-global"
export PATH="$TEST_ROOT/npm-global/bin:$PATH"
export OPENCLAW_STATE_DIR="$TEST_ROOT/openclaw-home"
export OPENCLAW_CONFIG_PATH="$TEST_ROOT/openclaw-home/openclaw.json"
export CLARVIS_E2E_ISOLATED=1
export CLARVIS_E2E_PORT="$TEST_PORT"

# ── A1: Ollama pre-flight ──
echo -e "${B}[A1] Ollama pre-flight${Z}"
if ! curl -sf "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
    systemctl --user start ollama.service 2>/dev/null || true
    sleep 3
fi
if curl -sf "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
    pass "A1: Ollama API reachable"
else
    warn "A1: Ollama unreachable — chat tests will be skipped"
fi
echo ""

# ── A2: Install OpenClaw into isolated prefix ──
echo -e "${B}[A2] OpenClaw CLI install${Z}"
OPENCLAW_VERSION="$(openclaw --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo 'latest')"
echo "  Installing openclaw@${OPENCLAW_VERSION} to $NPM_CONFIG_PREFIX ..."
npm install -g "openclaw@${OPENCLAW_VERSION}" --prefix "$NPM_CONFIG_PREFIX" 2>&1 | tail -3

OC="$TEST_ROOT/npm-global/bin/openclaw"
if "$OC" --help >/dev/null 2>&1; then
    pass "A2: openclaw --help responds"
else
    fail "A2: openclaw CLI install failed"
fi
echo ""

# ── A3: Onboard + config ──
echo -e "${B}[A3] OpenClaw onboard${Z}"
ONBOARD_EXIT=0
"$OC" onboard \
    --non-interactive \
    --accept-risk \
    --flow quickstart \
    --auth-choice ollama \
    --gateway-port "$TEST_PORT" \
    --gateway-auth token \
    --gateway-token "e2e-test-token-${TS}" \
    --gateway-bind loopback \
    --no-install-daemon \
    --workspace "$TEST_ROOT/workspace" \
    > "$TEST_ROOT/artifacts/onboard.log" 2>&1 || ONBOARD_EXIT=$?

# Ensure config exists (create manually if onboard didn't)
CONFIG_FILE=""
for candidate in "$OPENCLAW_CONFIG_PATH" "$OPENCLAW_STATE_DIR/openclaw.json"; do
    [ -f "$candidate" ] && CONFIG_FILE="$candidate" && break
done

if [ -z "$CONFIG_FILE" ] || ! python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
    CONFIG_FILE="$OPENCLAW_STATE_DIR/openclaw.json"
    mkdir -p "$OPENCLAW_STATE_DIR"
    cat > "$CONFIG_FILE" << ENDJSON
{
  "gateway": {
    "port": $TEST_PORT,
    "mode": "local",
    "bind": "loopback",
    "auth": {"mode": "token", "token": "e2e-test-token"}
  },
  "agents": {
    "defaults": {
      "model": {"primary": "ollama/$OLLAMA_MODEL"},
      "workspace": "$TEST_ROOT/workspace"
    }
  },
  "update": {"checkOnStart": false, "auto": {"enabled": false}},
  "channels": {}
}
ENDJSON
    friction "A3: onboard did not produce valid config — created manually"
fi

# Patch config for local-model path
python3 -c "
import json
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
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
cfg['channels'] = {}
with open('$CONFIG_FILE', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null

if [ "$ONBOARD_EXIT" -eq 0 ]; then
    pass "A3: OpenClaw onboard succeeded"
elif python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
    warn "A3: onboard exit $ONBOARD_EXIT but config is valid"
else
    fail "A3: OpenClaw onboard failed and no valid config"
fi
echo ""

# ════════════════════════════════════════════════════════════════════════════
# PHASE B: Clarvis Install (as a real user would)
# ════════════════════════════════════════════════════════════════════════════
echo -e "${B}━━━ PHASE B: Clarvis Install via install.sh ━━━${Z}"
echo ""

# ── B1: Clone repo to isolated workspace ──
echo -e "${B}[B1] Simulate git clone${Z}"
rsync -a --exclude='.git' --exclude='data/clarvisdb' --exclude='data/browser_sessions' \
    --exclude='node_modules' --exclude='.claude/worktrees' --exclude='__pycache__' \
    "$REPO_ROOT/" "$TEST_ROOT/workspace/"
# Init git for setuptools-scm
git -C "$TEST_ROOT/workspace" init -q 2>/dev/null || true
if [ -d "$TEST_ROOT/workspace/clarvis" ]; then
    pass "B1: Repo cloned to isolated workspace"
else
    fail "B1: Repo clone failed"
fi
echo ""

# ── B2: Create venv and install Clarvis ──
echo -e "${B}[B2] Create venv + install Clarvis${Z}"
python3 -m venv "$TEST_ROOT/venv"
# shellcheck disable=SC1091
source "$TEST_ROOT/venv/bin/activate"
export PIP_USER=0
pip install --upgrade pip -q 2>&1 | tail -1 || true

cd "$TEST_ROOT/workspace"
export CLARVIS_WORKSPACE="$TEST_ROOT/workspace"

# Create essential dirs that a fresh clone wouldn't have
mkdir -p "$TEST_ROOT/workspace"/{memory/cron,memory/evolution,data/clarvisdb,data/cognitive_workspace,monitoring}
echo "# Evolution Queue" > "$TEST_ROOT/workspace/memory/evolution/QUEUE.md"

INSTALL_EXIT=0
if $QUICK; then
    INSTALL_OUTPUT=$(bash scripts/infra/install.sh --profile openclaw --no-brain --no-cron 2>&1) || INSTALL_EXIT=$?
else
    INSTALL_OUTPUT=$(bash scripts/infra/install.sh --profile openclaw --no-cron 2>&1) || INSTALL_EXIT=$?
fi
echo "$INSTALL_OUTPUT" > "$TEST_ROOT/artifacts/install.log"

if [ "$INSTALL_EXIT" -eq 0 ]; then
    pass "B2: install.sh --profile openclaw completed successfully"
else
    # Check if install itself passed but verify_install.sh had warnings
    if echo "$INSTALL_OUTPUT" | grep -q "Installation Complete"; then
        warn "B2: install.sh completed but verification had issues (exit $INSTALL_EXIT)"
    else
        fail "B2: install.sh --profile openclaw failed (exit $INSTALL_EXIT)"
    fi
    # Log friction from install output
    INSTALL_FAILS=$(echo "$INSTALL_OUTPUT" | grep -cE "^\s+FAIL\s" || true)
    if [ "$INSTALL_FAILS" -gt 0 ]; then
        friction "B2: install.sh reported $INSTALL_FAILS check failures"
        echo "$INSTALL_OUTPUT" | grep -E "FAIL" | head -5 | while read -r line; do
            echo "    $line"
        done
    fi
fi

# ── B3: Check .env was created ──
if [ -f "$TEST_ROOT/workspace/.env" ]; then
    pass "B3: .env created by install.sh"
else
    warn "B3: .env not created"
fi
echo ""

# ════════════════════════════════════════════════════════════════════════════
# PHASE C: Core Clarvis Feature Validation
# ════════════════════════════════════════════════════════════════════════════
echo -e "${B}━━━ PHASE C: Core Clarvis Feature Validation ━━━${Z}"
echo ""

# ── C1: Core Python imports ──
echo -e "${B}[C1] Core imports${Z}"
for mod in "clarvis" "clarvis.cli" "clarvis.runtime" "clarvis.runtime.mode" \
           "clarvis.heartbeat" "clarvis.cognition" "clarvis.context" \
           "clarvis.orch.cost_tracker" "clarvis.compat.contracts" \
           "clarvis.adapters" "clarvis.adapters.openclaw" \
           "clarvis.queue.writer"; do
    if python3 -c "import $mod" 2>/dev/null; then
        pass "C1: import $mod"
    else
        ERR=$(python3 -c "import $mod" 2>&1 | tail -1)
        fail "C1: import $mod ($ERR)"
    fi
done
echo ""

# ── C2: CLI responds ──
echo -e "${B}[C2] CLI subcommands${Z}"
for cmd in "--help" "mode --help" "heartbeat --help" "cron --help"; do
    label="clarvis $cmd"
    if python3 -m clarvis $cmd >/dev/null 2>&1; then
        pass "C2: $label"
    else
        fail "C2: $label"
    fi
done
echo ""

# ── C3: Brain (unless --quick) ──
echo -e "${B}[C3] Brain${Z}"
if $QUICK; then
    skip_it "C3: Brain checks (--quick)"
else
    if python3 -c "from clarvis.brain import brain, search, remember, capture" 2>/dev/null; then
        pass "C3: brain imports"
    else
        ERR=$(python3 -c "from clarvis.brain import brain" 2>&1 | tail -1)
        fail "C3: brain imports ($ERR)"
    fi

    if python3 -c "import chromadb" 2>/dev/null; then
        pass "C3: chromadb importable"
    else
        fail "C3: chromadb not available"
    fi

    # Brain health on fresh empty DB
    mkdir -p "$TEST_ROOT/workspace/data/clarvisdb"
    HEALTH_OUTPUT=$(python3 -m clarvis brain health 2>&1)
    HEALTH_EXIT=$?
    if [ "$HEALTH_EXIT" -eq 0 ]; then
        pass "C3: brain health on fresh DB"
    else
        warn "C3: brain health returned non-zero on fresh DB"
        echo "  $(echo "$HEALTH_OUTPUT" | tail -3)"
    fi

    # Test store + recall round-trip
    STORE_OK=$(python3 -c "
from clarvis.brain import brain
brain.store('E2E test memory: Clarvis installed on fresh OpenClaw', importance=0.5, collection='clarvis-learnings')
results = brain.search('E2E test memory OpenClaw', n=1)
print('OK' if results else 'EMPTY')
" 2>/dev/null || echo "ERROR")
    if [ "$STORE_OK" = "OK" ]; then
        pass "C3: brain store/recall round-trip"
    else
        warn "C3: brain store/recall returned: $STORE_OK"
    fi
fi
echo ""

# ── C4: Heartbeat gate ──
echo -e "${B}[C4] Heartbeat gate (dry-run)${Z}"
if [ -f "$TEST_ROOT/workspace/scripts/pipeline/heartbeat_gate.py" ]; then
    GATE_EXIT=0
    timeout 10 python3 "$TEST_ROOT/workspace/scripts/pipeline/heartbeat_gate.py" >/dev/null 2>&1 || GATE_EXIT=$?
    if [ "$GATE_EXIT" -eq 0 ]; then
        pass "C4: heartbeat gate exits 0 (WAKE)"
    elif [ "$GATE_EXIT" -eq 1 ]; then
        pass "C4: heartbeat gate exits 1 (SKIP — expected)"
    else
        warn "C4: heartbeat gate exit $GATE_EXIT"
    fi
else
    warn "C4: heartbeat_gate.py not found in workspace"
fi
echo ""

# ── C5: Cron wiring ──
echo -e "${B}[C5] Cron scripts${Z}"
CRON_DIR="$TEST_ROOT/workspace/scripts/cron"
for script in cron_env.sh cron_autonomous.sh lock_helper.sh cron_morning.sh cron_evening.sh cron_reflection.sh; do
    if [ -f "$CRON_DIR/$script" ]; then
        pass "C5: $script exists"
    else
        fail "C5: $script missing"
    fi
done

# Syntax check all cron scripts
SYNTAX_FAIL=0
for script in "$CRON_DIR"/cron_*.sh "$CRON_DIR/lock_helper.sh"; do
    [ -f "$script" ] || continue
    if ! bash -n "$script" 2>/dev/null; then
        fail "C5: $(basename "$script") syntax error"
        SYNTAX_FAIL=$((SYNTAX_FAIL+1))
    fi
done
[ "$SYNTAX_FAIL" -eq 0 ] && pass "C5: all cron scripts pass bash -n"

# cron_env.sh sources correctly
if bash -c "export CLARVIS_WORKSPACE='$TEST_ROOT/workspace'; source '$CRON_DIR/cron_env.sh' && echo OK" 2>/dev/null | grep -q OK; then
    pass "C5: cron_env.sh sources correctly"
else
    fail "C5: cron_env.sh source failed"
fi
echo ""

# ── C6: OpenClaw adapter ──
echo -e "${B}[C6] OpenClaw adapter${Z}"
if python3 -c "from clarvis.adapters.openclaw import OpenClawAdapter; print('OK')" 2>/dev/null | grep -q OK; then
    pass "C6: OpenClawAdapter importable"
else
    fail "C6: OpenClawAdapter import failed"
fi
echo ""

# ── C7: Key documentation files ──
echo -e "${B}[C7] Documentation files${Z}"
for doc in CLAUDE.md AGENTS.md SOUL.md SELF.md HEARTBEAT.md; do
    if [ -f "$TEST_ROOT/workspace/$doc" ] || [ -f "$TEST_ROOT/workspace/../$doc" ]; then
        pass "C7: $doc present"
    else
        warn "C7: $doc missing"
    fi
done
echo ""

# ── C8: Queue access ──
echo -e "${B}[C8] Queue system${Z}"
if python3 -c "from clarvis.queue.writer import add_task; print('OK')" 2>/dev/null | grep -q OK; then
    pass "C8: queue.writer.add_task importable"
else
    warn "C8: queue.writer.add_task import failed"
fi
echo ""

# ── C9: verify_install.sh ──
echo -e "${B}[C9] verify_install.sh${Z}"
if $QUICK; then
    VERIFY_OUTPUT=$(bash scripts/infra/verify_install.sh --no-brain --profile openclaw 2>&1)
else
    VERIFY_OUTPUT=$(bash scripts/infra/verify_install.sh --profile openclaw 2>&1)
fi
VERIFY_EXIT=$?
echo "$VERIFY_OUTPUT" > "$TEST_ROOT/artifacts/verify.log"

VERIFY_PASSES=$(echo "$VERIFY_OUTPUT" | grep -cE "^\s+PASS\s" || true)
VERIFY_FAILS=$(echo "$VERIFY_OUTPUT" | grep -cE "^\s+FAIL\s" || true)

if [ "$VERIFY_EXIT" -eq 0 ]; then
    pass "C9: verify_install.sh passed ($VERIFY_PASSES checks)"
elif [ "$VERIFY_FAILS" -eq 0 ]; then
    warn "C9: verify_install.sh exit $VERIFY_EXIT but no FAIL lines ($VERIFY_PASSES passes)"
else
    warn "C9: verify_install.sh had $VERIFY_FAILS failures"
    echo "$VERIFY_OUTPUT" | grep "FAIL" | head -5 | while read -r line; do
        echo "    $line"
    done
fi
echo ""

# ════════════════════════════════════════════════════════════════════════════
# PHASE D: Gateway Integration (if OpenClaw working)
# ════════════════════════════════════════════════════════════════════════════
echo -e "${B}━━━ PHASE D: Gateway Integration ━━━${Z}"
echo ""

echo -e "${B}[D1] Gateway boot${Z}"
fuser -k "$TEST_PORT/tcp" 2>/dev/null || true
sleep 1

GW_PID=""
OPENCLAW_STATE_DIR="$OPENCLAW_STATE_DIR" \
OPENCLAW_CONFIG_PATH="$CONFIG_FILE" \
    "$OC" gateway run --port "$TEST_PORT" --allow-unconfigured \
    > "$TEST_ROOT/artifacts/gateway.log" 2>&1 &
GW_PID=$!

GW_READY=false
for i in $(seq 1 15); do
    if curl -sf "http://127.0.0.1:${TEST_PORT}/health" >/dev/null 2>&1 || \
       curl -sf "http://127.0.0.1:${TEST_PORT}/" >/dev/null 2>&1; then
        GW_READY=true
        break
    fi
    kill -0 "$GW_PID" 2>/dev/null || break
    sleep 1
done

if $GW_READY; then
    pass "D1: Gateway responding on port $TEST_PORT"
elif kill -0 "$GW_PID" 2>/dev/null && (ss -tln 2>/dev/null | grep -q ":${TEST_PORT}"); then
    pass "D1: Gateway bound to port $TEST_PORT (WS-only)"
else
    fail "D1: Gateway not responding"
fi
echo ""

# ── D2: Gateway shutdown ──
echo -e "${B}[D2] Clean shutdown${Z}"
if [ -n "${GW_PID:-}" ] && kill -0 "$GW_PID" 2>/dev/null; then
    kill "$GW_PID" 2>/dev/null
    CLEAN=true
    for i in $(seq 1 5); do
        kill -0 "$GW_PID" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$GW_PID" 2>/dev/null; then
        kill -9 "$GW_PID" 2>/dev/null
        CLEAN=false
    fi
    GW_PID=""
    if $CLEAN; then
        pass "D2: Gateway shut down cleanly"
    else
        warn "D2: Gateway required SIGKILL"
    fi
else
    warn "D2: Gateway was not running"
fi
echo ""

# ════════════════════════════════════════════════════════════════════════════
# SUMMARY & ARTIFACTS
# ════════════════════════════════════════════════════════════════════════════
TOTAL=$((PASS + FAIL + WARN + SKIP))
echo -e "${B}╔═══════════════════════════════════════════════════════════╗${Z}"
echo -e "${B}║  Results: ${G}$PASS passed${Z}, ${R}$FAIL failed${Z}, ${Y}$WARN warnings${Z}, ${C}$SKIP skipped${Z} (of $TOTAL) ║"
echo -e "${B}╚═══════════════════════════════════════════════════════════╝${Z}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${R}Failures:${Z}"
    for r in "${RESULTS[@]}"; do
        [[ "$r" == FAIL* ]] && echo "  - ${r#FAIL|}"
    done
    echo ""
fi

if [ ${#FRICTION[@]} -gt 0 ]; then
    echo -e "${Y}Friction points:${Z}"
    for f in "${FRICTION[@]}"; do
        echo "  - $f"
    done
    echo ""
fi

# Verdict
if [ "$FAIL" -eq 0 ]; then
    VERDICT="PASS"
    echo -e "${G}${B}VERDICT: PASS${Z}"
    echo "Clarvis installs and runs on a fresh OpenClaw install."
else
    VERDICT="FAIL"
    echo -e "${R}${B}VERDICT: FAIL${Z}"
    echo "Resolve failures before claiming Clarvis-on-OpenClaw support."
fi
echo ""

# Save result JSON
ARTIFACT_DIR="$REPO_ROOT/docs/validation/e2e_clarvis_on_openclaw_fresh_${TS}"
mkdir -p "$ARTIFACT_DIR"
cp "$TEST_ROOT/artifacts/"* "$ARTIFACT_DIR/" 2>/dev/null || true

# Write friction to temp file for Python to read
FRICTION_FILE="$TEST_ROOT/artifacts/friction.txt"
: > "$FRICTION_FILE"
for f in "${FRICTION[@]+"${FRICTION[@]}"}"; do
    echo "$f" >> "$FRICTION_FILE"
done

python3 -c "
import json
results = []
for r in '''$(printf '%s\n' "${RESULTS[@]}")'''.strip().split('\n'):
    if '|' in r:
        status, desc = r.split('|', 1)
        results.append({'status': status, 'criterion': desc})
friction = [l.strip() for l in open('$FRICTION_FILE').readlines() if l.strip()]
verdict = {
    'gate': 'e2e_clarvis_on_openclaw_fresh',
    'timestamp': '$TS',
    'verdict': '$VERDICT',
    'passed': $PASS,
    'failed': $FAIL,
    'warnings': $WARN,
    'skipped': $SKIP,
    'total': $TOTAL,
    'port': $TEST_PORT,
    'quick_mode': $([ "$QUICK" = "true" ] && echo "True" || echo "False"),
    'test_root': '$TEST_ROOT',
    'results': results,
    'friction': friction,
}
out = '$ARTIFACT_DIR/result.json'
with open(out, 'w') as f:
    json.dump(verdict, f, indent=2)
print(json.dumps(verdict, indent=2))
" 2>&1

echo ""
echo "Artifacts: $ARTIFACT_DIR/"
echo "  result.json    — Structured verdict"
echo "  install.log    — install.sh output"
echo "  verify.log     — verify_install.sh output"
echo "  onboard.log    — OpenClaw onboard output"
echo "  gateway.log    — Gateway output"

[ "$VERDICT" = "PASS" ] && exit 0 || exit 1
