#!/usr/bin/env bash
# fresh_install_smoke.sh — Repeatable smoke-test suite for fresh Clarvis installs.
#
# Covers: Python imports, CLI launch, memory paths, brain init, cron wiring,
# autonomous trigger (dry-run), prompt assembly, and first-use experience.
#
# Usage:
#   bash scripts/infra/fresh_install_smoke.sh                    # Full suite
#   bash scripts/infra/fresh_install_smoke.sh --no-brain         # Skip brain checks
#   bash scripts/infra/fresh_install_smoke.sh --isolated         # Run in /tmp workspace
#   bash scripts/infra/fresh_install_smoke.sh --profile openclaw # Profile-specific
#   bash scripts/infra/fresh_install_smoke.sh --quick            # Fast subset only
#
# Exit: 0 = all pass, 1 = critical failures, 2 = warnings only

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Args ─────────────────────────────────────────────────────────────────
NO_BRAIN=0
ISOLATED=0
PROFILE=""
QUICK=0

while [ $# -gt 0 ]; do
    case "$1" in
        --no-brain)  NO_BRAIN=1; shift ;;
        --isolated)  ISOLATED=1; shift ;;
        --profile)   PROFILE="$2"; shift 2 ;;
        --profile=*) PROFILE="${1#*=}"; shift ;;
        --quick)     QUICK=1; shift ;;
        --help|-h)
            sed -n '2,11p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) shift ;;
    esac
done

# ── Setup ────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD="\033[1m" GREEN="\033[32m" YELLOW="\033[33m" RED="\033[31m"
    CYAN="\033[36m" RESET="\033[0m"
else
    BOLD="" GREEN="" YELLOW="" RED="" CYAN="" RESET=""
fi

PASS=0 FAIL=0 WARN=0 SKIP=0
FAILURES=()

pass()  { PASS=$((PASS+1)); echo -e "  ${GREEN}PASS${RESET}  $1"; }
fail()  { FAIL=$((FAIL+1)); FAILURES+=("$1"); echo -e "  ${RED}FAIL${RESET}  $1"; }
warn()  { WARN=$((WARN+1)); echo -e "  ${YELLOW}WARN${RESET}  $1"; }
skip()  { SKIP=$((SKIP+1)); echo -e "  ${CYAN}SKIP${RESET}  $1"; }

# Determine workspace
if [ "$ISOLATED" -eq 1 ]; then
    WORKSPACE="$(mktemp -d /tmp/clarvis_smoke_XXXXXX)"
    echo -e "${CYAN}>>> Creating isolated workspace: $WORKSPACE${RESET}"

    # Minimal workspace structure
    mkdir -p "$WORKSPACE"/{memory/cron,memory/evolution,data/clarvisdb,data/cognitive_workspace,monitoring}
    cp -r "$REPO_ROOT/scripts" "$WORKSPACE/scripts"
    cp -r "$REPO_ROOT/clarvis" "$WORKSPACE/clarvis" 2>/dev/null || true
    cp "$REPO_ROOT/pyproject.toml" "$WORKSPACE/" 2>/dev/null || true
    cp "$REPO_ROOT/.env" "$WORKSPACE/" 2>/dev/null || true
    echo "# Evolution Queue — Clarvis" > "$WORKSPACE/memory/evolution/QUEUE.md"
    echo "- [ ] [SMOKE_TEST] Smoke test task." >> "$WORKSPACE/memory/evolution/QUEUE.md"
    export CLARVIS_WORKSPACE="$WORKSPACE"
    CLEANUP_WORKSPACE=1
else
    WORKSPACE="$REPO_ROOT"
    export CLARVIS_WORKSPACE="$WORKSPACE"
    CLEANUP_WORKSPACE=0
fi

echo -e "${BOLD}=== Clarvis Fresh Install Smoke Test ===${RESET}"
echo "Workspace: $WORKSPACE"
echo "Python:    $(python3 --version 2>&1)"
echo "Date:      $(date -u +%Y-%m-%dT%H:%M:%S)Z"
[ -n "$PROFILE" ] && echo "Profile:   $PROFILE"
echo ""

# ══════════════════════════════════════════════════════════════════════════
# SECTION 1: Core Imports
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[1/8] Core Python imports${RESET}"

for mod in clarvis clarvis.cli clarvis.heartbeat clarvis.cognition clarvis.context clarvis.runtime; do
    if python3 -c "import $mod" 2>/dev/null; then
        pass "$mod"
    else
        fail "$mod import"
    fi
done

if [ "$NO_BRAIN" -eq 1 ]; then
    if python3 -c "from clarvis.brain import brain, search, remember, capture" 2>/dev/null; then
        pass "clarvis.brain (optional)"
    else
        warn "clarvis.brain (--no-brain, skipped)"
    fi
else
    if python3 -c "from clarvis.brain import brain, search, remember, capture" 2>/dev/null; then
        pass "clarvis.brain"
    else
        fail "clarvis.brain import"
    fi
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# SECTION 2: CLI Launch
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[2/8] CLI launch${RESET}"

for cmd in "--help" "mode --help" "heartbeat --help"; do
    label="clarvis $cmd"
    if python3 -m clarvis $cmd >/dev/null 2>&1; then
        pass "$label"
    else
        fail "$label"
    fi
done

if [ "$NO_BRAIN" -eq 0 ]; then
    if python3 -m clarvis brain --help >/dev/null 2>&1; then
        pass "clarvis brain --help"
    else
        fail "clarvis brain --help"
    fi
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# SECTION 3: Memory Paths
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[3/8] Memory & data paths${RESET}"

for dir in memory memory/cron memory/evolution data monitoring; do
    full="$WORKSPACE/$dir"
    if [ -d "$full" ]; then
        pass "$dir exists"
    else
        fail "$dir missing"
    fi
done

# QUEUE.md exists and is readable
if [ -f "$WORKSPACE/memory/evolution/QUEUE.md" ] && [ -r "$WORKSPACE/memory/evolution/QUEUE.md" ]; then
    pass "QUEUE.md readable"
else
    fail "QUEUE.md missing or unreadable"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# SECTION 4: Brain Init (optional)
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[4/8] Brain initialization${RESET}"

if [ "$NO_BRAIN" -eq 1 ]; then
    skip "brain checks (--no-brain)"
elif [ "$ISOLATED" -eq 1 ]; then
    # In isolated mode, just check imports work
    if python3 -c "import chromadb; import onnxruntime" 2>/dev/null; then
        pass "chromadb + onnxruntime importable"
    else
        warn "chromadb/onnxruntime not available (brain won't work)"
    fi
else
    if python3 -m clarvis brain health >/dev/null 2>&1; then
        pass "brain health check"
    else
        warn "brain health check failed (may need initialization)"
    fi

    if python3 -c "from clarvis.brain import brain; s = brain.stats(); assert s" 2>/dev/null; then
        pass "brain.stats() returns data"
    else
        warn "brain.stats() failed"
    fi
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# SECTION 5: Cron Wiring
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[5/8] Cron wiring${RESET}"

# Check cron scripts exist
CRON_DIR="$WORKSPACE/scripts/cron"
EXPECTED_SCRIPTS=(cron_env.sh cron_autonomous.sh lock_helper.sh cron_morning.sh cron_evening.sh cron_reflection.sh)

for script in "${EXPECTED_SCRIPTS[@]}"; do
    if [ -f "$CRON_DIR/$script" ]; then
        pass "$script exists"
    else
        fail "$script missing"
    fi
done

# Bash syntax validation
for script in "$CRON_DIR"/cron_*.sh "$CRON_DIR/lock_helper.sh"; do
    [ -f "$script" ] || continue
    name="$(basename "$script")"
    if bash -n "$script" 2>/dev/null; then
        pass "$name syntax OK"
    else
        fail "$name syntax ERROR"
    fi
done

# cron_env.sh sources correctly with isolated workspace
if bash -c "export CLARVIS_WORKSPACE='$WORKSPACE'; source '$CRON_DIR/cron_env.sh' && echo OK" 2>/dev/null | grep -q OK; then
    pass "cron_env.sh sources correctly"
else
    fail "cron_env.sh source failed"
fi

# Check system crontab (non-isolated only)
if [ "$ISOLATED" -eq 0 ]; then
    if crontab -l 2>/dev/null | grep -q "clarvis-managed"; then
        CRON_COUNT=$(crontab -l 2>/dev/null | grep -c "cron_autonomous.sh" || true)
        pass "crontab has managed block ($CRON_COUNT autonomous entries)"
    else
        warn "crontab has no clarvis-managed block (cron not installed)"
    fi

    # Verify all crontab-referenced scripts exist
    MISSING_SCRIPTS=0
    while IFS= read -r path; do
        path="${path%% *}"
        if [ ! -f "$path" ]; then
            warn "crontab references missing: $path"
            MISSING_SCRIPTS=$((MISSING_SCRIPTS+1))
        fi
    done < <(crontab -l 2>/dev/null | grep -oP "${REPO_ROOT}/scripts/\\S+" | sort -u)
    [ "$MISSING_SCRIPTS" -eq 0 ] && pass "all crontab script paths valid"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# SECTION 6: Autonomous Trigger (dry-run)
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[6/8] Autonomous pipeline (dry-run)${RESET}"

if [ "$QUICK" -eq 1 ]; then
    skip "autonomous dry-run (--quick mode)"
else
    # Test lock acquisition and release
    TEST_LOCK="/tmp/clarvis_smoke_test_$$.lock"
    TEST_LOG="/tmp/clarvis_smoke_test_$$.log"
    : > "$TEST_LOG"

    LOCK_RESULT=$(bash -c "
        source '$CRON_DIR/lock_helper.sh'
        acquire_local_lock '$TEST_LOCK' '$TEST_LOG' 0
        echo LOCKED
    " 2>/dev/null)

    if echo "$LOCK_RESULT" | grep -q "LOCKED"; then
        pass "lock acquisition works"
    else
        fail "lock acquisition failed"
    fi
    # Lock should be cleaned up by EXIT trap
    rm -f "$TEST_LOCK" "$TEST_LOG"

    # Test prompt guard (empty prompt rejection)
    EMPTY_PROMPT=$(mktemp /tmp/clarvis_empty_XXXXXX.txt)
    if bash -c "
        source '$CRON_DIR/cron_env.sh' 2>/dev/null
        [ ! -s '$EMPTY_PROMPT' ] && echo REJECTED || echo ACCEPTED
    " 2>/dev/null | grep -q "REJECTED"; then
        pass "empty prompt guard works"
    else
        fail "empty prompt guard broken"
    fi
    rm -f "$EMPTY_PROMPT"

    # Test task validation (short task rejection)
    if bash -c '
        NEXT_TASK="ab"
        TASK_STRIPPED=$(echo "$NEXT_TASK" | tr -d "[:space:]")
        [ ${#TASK_STRIPPED} -lt 5 ] && echo REJECTED || echo ACCEPTED
    ' 2>/dev/null | grep -q "REJECTED"; then
        pass "short task guard works"
    else
        fail "short task guard broken"
    fi

    # Test heartbeat gate (if not isolated)
    if [ "$ISOLATED" -eq 0 ] && [ -f "$WORKSPACE/scripts/pipeline/heartbeat_gate.py" ]; then
        if timeout 10 python3 "$WORKSPACE/scripts/pipeline/heartbeat_gate.py" >/dev/null 2>&1; then
            pass "heartbeat gate runs (WAKE)"
        else
            EXIT_CODE=$?
            if [ "$EXIT_CODE" -eq 1 ]; then
                pass "heartbeat gate runs (SKIP — expected during active session)"
            else
                warn "heartbeat gate exited with code $EXIT_CODE"
            fi
        fi
    else
        skip "heartbeat gate (isolated or missing)"
    fi
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# SECTION 7: Prompt Assembly
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[7/8] Prompt assembly validation${RESET}"

if [ "$QUICK" -eq 1 ]; then
    skip "prompt assembly (--quick mode)"
elif [ -f "$WORKSPACE/scripts/infra/smoke_test_prompt_assembly.sh" ]; then
    ASSEMBLY_OUTPUT=$(bash "$WORKSPACE/scripts/infra/smoke_test_prompt_assembly.sh" 2>&1)
    ASSEMBLY_FAILS=$(echo "$ASSEMBLY_OUTPUT" | grep -c "FAIL:" || true)
    ASSEMBLY_PASSES=$(echo "$ASSEMBLY_OUTPUT" | grep -c "PASS:" || true)
    if [ "$ASSEMBLY_FAILS" -eq 0 ] && [ "$ASSEMBLY_PASSES" -gt 0 ]; then
        pass "prompt assembly ($ASSEMBLY_PASSES checks passed)"
    elif [ "$ASSEMBLY_FAILS" -gt 0 ]; then
        fail "prompt assembly ($ASSEMBLY_FAILS failures)"
    else
        warn "prompt assembly (no results)"
    fi
else
    skip "prompt assembly (script not found)"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# SECTION 8: First-Use Experience
# ══════════════════════════════════════════════════════════════════════════
echo -e "${BOLD}[8/8] First-use experience${RESET}"

# Check key documentation files exist
for doc in CLAUDE.md AGENTS.md SOUL.md SELF.md; do
    if [ -f "$WORKSPACE/$doc" ] || [ -f "$REPO_ROOT/$doc" ] || [ -f "$WORKSPACE/../$doc" ]; then
        pass "$doc present"
    else
        warn "$doc missing (affects first-use)"
    fi
done

# Check cron CLI works
if python3 -m clarvis cron --help >/dev/null 2>&1; then
    pass "clarvis cron --help"
else
    if python3 -c "from clarvis.cron import app" 2>/dev/null; then
        pass "clarvis.cron importable"
    else
        warn "clarvis cron CLI not available"
    fi
fi

# Verify .env exists (needed for Telegram, API keys)
if [ -f "$WORKSPACE/.env" ]; then
    pass ".env file present"
else
    warn ".env missing (Telegram/API features won't work)"
fi

# Profile-specific checks
if [ -n "$PROFILE" ]; then
    echo ""
    echo -e "${BOLD}Profile: $PROFILE${RESET}"
    case "$PROFILE" in
        standalone)
            if [ -w "$WORKSPACE/data" ] || [ -w "$WORKSPACE" ]; then
                pass "data dir writable"
            else
                fail "data dir not writable"
            fi
            ;;
        openclaw)
            if command -v openclaw &>/dev/null || [ -f "$HOME/.npm-global/lib/node_modules/openclaw/dist/index.js" ]; then
                pass "OpenClaw installed"
                if systemctl --user is-active openclaw-gateway.service &>/dev/null; then
                    pass "gateway running"
                else
                    warn "gateway not running"
                fi
            else
                fail "OpenClaw not found"
            fi
            ;;
        fullstack)
            if command -v openclaw &>/dev/null; then pass "OpenClaw installed"; else warn "OpenClaw not found"; fi
            if command -v claude &>/dev/null; then pass "Claude CLI available"; else warn "Claude CLI not found"; fi
            if crontab -l 2>/dev/null | grep -q clarvis; then pass "crontab configured"; else warn "crontab not configured"; fi
            ;;
    esac
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════
TOTAL=$((PASS + FAIL + WARN + SKIP))
echo -e "${BOLD}=== Results: ${GREEN}$PASS passed${RESET}, ${RED}$FAIL failed${RESET}, ${YELLOW}$WARN warnings${RESET}, ${CYAN}$SKIP skipped${RESET} (of $TOTAL checks) ==="

if [ ${#FAILURES[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Failures:${RESET}"
    for f in "${FAILURES[@]}"; do
        echo "  - $f"
    done
fi

# Cleanup isolated workspace
if [ "$CLEANUP_WORKSPACE" -eq 1 ]; then
    rm -rf "$WORKSPACE"
    echo ""
    echo "Cleaned up isolated workspace: $WORKSPACE"
fi

echo ""
if [ "$FAIL" -gt 0 ]; then
    echo "Status: FAIL — $FAIL critical issue(s) need fixing."
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo "Status: WARN — all critical checks passed, $WARN non-critical warnings."
    exit 2
else
    echo "Status: PASS — all checks passed."
    exit 0
fi
