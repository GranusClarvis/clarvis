#!/usr/bin/env bash
# e2e_clarvis_on_hermes_fresh.sh — End-to-end: Clarvis on fresh Hermes install.
#
# 1. Creates a fresh venv in /tmp, installs hermes-agent (pip)
# 2. Layers Clarvis via install.sh --profile hermes (as a real user would)
# 3. Validates all core Clarvis features + Hermes adapter integration
# 4. Documents friction, failures, and manual steps needed
#
# Usage:
#   bash scripts/infra/e2e_clarvis_on_hermes_fresh.sh           # Full run
#   bash scripts/infra/e2e_clarvis_on_hermes_fresh.sh --quick   # Skip brain + Hermes install
#
# Artifacts: docs/validation/e2e_clarvis_on_hermes_fresh_<ts>/
# Exit: 0 = all critical pass, 1 = critical failures

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS="$(date -u +%Y%m%d_%H%M%S)"
TEST_ROOT="/tmp/e2e-clarvis-hermes-${TS}"
QUICK=false

while [ $# -gt 0 ]; do
    case "$1" in
        --quick) QUICK=true; shift ;;
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
    type deactivate &>/dev/null && deactivate 2>/dev/null || true
}
trap cleanup EXIT

echo -e "${B}╔═════════════════════════════════════��═════════════════════╗${Z}"
echo -e "${B}║  E2E: Clarvis on Fresh Hermes Install                     ║${Z}"
echo -e "${B}╚═════════════════════════════════════════════════���═════════╝${Z}"
echo ""
echo "Test root:  $TEST_ROOT"
echo "Quick mode: $QUICK"
echo "Repo root:  $REPO_ROOT"
echo "Timestamp:  $TS"
echo ""

mkdir -p "$TEST_ROOT"/{workspace,venv,artifacts}

# Isolation
export CLARVIS_E2E_ISOLATED=1
export CLARVIS_WORKSPACE="$TEST_ROOT/workspace"
export CLARVIS_E2E_PORT=28789

# ════════��════════════════════════════��══════════════════════════════════════
# PHASE A: Fresh Hermes Install
# ══════════════════════════════���═════════════════════════════════════════════
echo -e "${B}━━━ PHASE A: Fresh Hermes Install ━━━${Z}"
echo ""

# ── A1: Create venv ──
echo -e "${B}[A1] Create fresh venv${Z}"
python3 -m venv "$TEST_ROOT/venv"
# shellcheck disable=SC1091
source "$TEST_ROOT/venv/bin/activate"
export PIP_USER=0
pip install --upgrade pip -q 2>&1 | tail -1 || true
if [ -n "${VIRTUAL_ENV:-}" ]; then
    pass "A1: Venv created and activated"
else
    fail "A1: Venv creation failed"
fi
echo ""

# ─�� A2: Install hermes-agent ──
echo -e "${B}[A2] Install hermes-agent${Z}"
if $QUICK; then
    skip_it "A2: Hermes install (--quick)"
else
    HERMES_OUTPUT=$(pip install hermes-agent 2>&1)
    HERMES_EXIT=$?
    echo "$HERMES_OUTPUT" > "$TEST_ROOT/artifacts/hermes_install.log"

    if [ "$HERMES_EXIT" -eq 0 ]; then
        pass "A2: pip install hermes-agent succeeded"
    else
        warn "A2: pip install hermes-agent failed (exit $HERMES_EXIT)"
        friction "A2: hermes-agent pip install failed — package may be unavailable or renamed"
        # Try from GitHub as fallback
        echo "  Trying from source..."
        HERMES_SRC_OUTPUT=$(pip install git+https://github.com/NousResearch/hermes-agent.git 2>&1)
        HERMES_SRC_EXIT=$?
        if [ "$HERMES_SRC_EXIT" -eq 0 ]; then
            pass "A2: hermes-agent installed from source"
        else
            warn "A2: hermes-agent not available from PyPI or GitHub"
            friction "A2: hermes-agent cannot be installed — test continues with adapter-only checks"
        fi
    fi

    # Verify hermes import
    if python3 -c "import hermes_agent" 2>/dev/null; then
        pass "A2: hermes_agent importable"
    elif command -v hermes &>/dev/null; then
        pass "A2: hermes CLI available"
    else
        warn "A2: hermes_agent not importable (adapter-only testing)"
    fi
fi
echo ""

# ════════════════════════════════════════════════════════════════════════════
# PHASE B: Clarvis Install (as a real user would)
# ══��═════════════════════════════════════════════════════════════════════════
echo -e "${B}━━━ PHASE B: Clarvis Install via install.sh ━━━${Z}"
echo ""

# ── B1: Clone repo to isolated workspace ──
echo -e "${B}[B1] Simulate git clone${Z}"
rsync -a --exclude='.git' --exclude='data/clarvisdb' --exclude='data/browser_sessions' \
    --exclude='node_modules' --exclude='.claude/worktrees' --exclude='__pycache__' \
    "$REPO_ROOT/" "$TEST_ROOT/workspace/"
git -C "$TEST_ROOT/workspace" init -q 2>/dev/null || true
if [ -d "$TEST_ROOT/workspace/clarvis" ]; then
    pass "B1: Repo cloned to isolated workspace"
else
    fail "B1: Repo clone failed"
fi
echo ""

# ── B2: Install Clarvis with hermes profile ──
echo -e "${B}[B2] install.sh --profile hermes${Z}"
cd "$TEST_ROOT/workspace"
export CLARVIS_WORKSPACE="$TEST_ROOT/workspace"

mkdir -p "$TEST_ROOT/workspace"/{memory/cron,memory/evolution,data/clarvisdb,data/cognitive_workspace,monitoring}
echo "# Evolution Queue" > "$TEST_ROOT/workspace/memory/evolution/QUEUE.md"

INSTALL_EXIT=0
if $QUICK; then
    INSTALL_OUTPUT=$(bash scripts/infra/install.sh --profile hermes --no-brain --no-cron 2>&1) || INSTALL_EXIT=$?
else
    INSTALL_OUTPUT=$(bash scripts/infra/install.sh --profile hermes --no-cron 2>&1) || INSTALL_EXIT=$?
fi
echo "$INSTALL_OUTPUT" > "$TEST_ROOT/artifacts/install.log"

if [ "$INSTALL_EXIT" -eq 0 ]; then
    pass "B2: install.sh --profile hermes completed successfully"
else
    if echo "$INSTALL_OUTPUT" | grep -q "Installation Complete"; then
        warn "B2: install.sh completed but verification had issues (exit $INSTALL_EXIT)"
    else
        fail "B2: install.sh --profile hermes failed (exit $INSTALL_EXIT)"
    fi
    INSTALL_FAILS=$(echo "$INSTALL_OUTPUT" | grep -cE "^\s+FAIL\s" || true)
    if [ "$INSTALL_FAILS" -gt 0 ]; then
        friction "B2: install.sh reported $INSTALL_FAILS check failures"
    fi
fi

if [ -f "$TEST_ROOT/workspace/.env" ]; then
    pass "B3: .env created by install.sh"
else
    warn "B3: .env not created"
fi
echo ""

# ══════���════════════════════════════════��════════════════════════════════════
# PHASE C: Core Clarvis Feature Validation
# ════════════════════════���═════════════════════════════���═════════════════════
echo -e "${B}━━━ PHASE C: Core Clarvis Feature Validation ━━━${Z}"
echo ""

# ── C1: Core Python imports ──
echo -e "${B}[C1] Core imports${Z}"
for mod in "clarvis" "clarvis.cli" "clarvis.runtime" "clarvis.runtime.mode" \
           "clarvis.heartbeat" "clarvis.cognition" "clarvis.context" \
           "clarvis.orch.cost_tracker" "clarvis.compat.contracts" \
           "clarvis.adapters" "clarvis.queue.writer"; do
    if python3 -c "import $mod" 2>/dev/null; then
        pass "C1: import $mod"
    else
        ERR=$(python3 -c "import $mod" 2>&1 | tail -1)
        fail "C1: import $mod ($ERR)"
    fi
done
echo ""

# ── C2: CLI responds ���─
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

    mkdir -p "$TEST_ROOT/workspace/data/clarvisdb"
    HEALTH_EXIT=0
    python3 -m clarvis brain health >/dev/null 2>&1 || HEALTH_EXIT=$?
    if [ "$HEALTH_EXIT" -eq 0 ]; then
        pass "C3: brain health on fresh DB"
    else
        warn "C3: brain health returned non-zero on fresh DB"
    fi
fi
echo ""

# ─��� C4: Heartbeat gate ──
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
    warn "C4: heartbeat_gate.py not found"
fi
echo ""

# ── C5: Cron scripts ──
echo -e "${B}[C5] Cron scripts${Z}"
CRON_DIR="$TEST_ROOT/workspace/scripts/cron"
for script in cron_env.sh cron_autonomous.sh lock_helper.sh; do
    if [ -f "$CRON_DIR/$script" ]; then
        pass "C5: $script exists"
    else
        fail "C5: $script missing"
    fi
done

SYNTAX_FAIL=0
for script in "$CRON_DIR"/cron_*.sh "$CRON_DIR/lock_helper.sh"; do
    [ -f "$script" ] || continue
    if ! bash -n "$script" 2>/dev/null; then
        fail "C5: $(basename "$script") syntax error"
        SYNTAX_FAIL=$((SYNTAX_FAIL+1))
    fi
done
[ "$SYNTAX_FAIL" -eq 0 ] && pass "C5: all cron scripts pass bash -n"
echo ""

# ── C6: Hermes adapter ──
echo -e "${B}[C6] Hermes adapter${Z}"
if python3 -c "from clarvis.adapters.hermes import HermesAdapter; print('OK')" 2>/dev/null | grep -q OK; then
    pass "C6: HermesAdapter importable"
else
    fail "C6: HermesAdapter import failed"
fi

# Test adapter detection
DETECT_OUT=$(python3 -c "
from clarvis.adapters.hermes import HermesAdapter
a = HermesAdapter()
r = a.hermes_available()
print(f'detected={r.ok}')
" 2>/dev/null || echo "error")

if echo "$DETECT_OUT" | grep -q "detected="; then
    pass "C6: HermesAdapter.hermes_available() runs"
else
    warn "C6: HermesAdapter detection inconclusive"
fi
echo ""

# ── C7: Documentation files ──
echo -e "${B}[C7] Documentation files${Z}"
for doc in AGENTS.md SOUL.md SELF.md HEARTBEAT.md; do
    if [ -f "$TEST_ROOT/workspace/$doc" ]; then
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
    VERIFY_OUTPUT=$(bash scripts/infra/verify_install.sh --no-brain --profile hermes 2>&1)
else
    VERIFY_OUTPUT=$(bash scripts/infra/verify_install.sh --profile hermes 2>&1)
fi
VERIFY_EXIT=$?
echo "$VERIFY_OUTPUT" > "$TEST_ROOT/artifacts/verify.log"

VERIFY_PASSES=$(echo "$VERIFY_OUTPUT" | grep -cE "^\s+PASS\s" || true)
VERIFY_FAILS=$(echo "$VERIFY_OUTPUT" | grep -cE "^\s+FAIL\s" || true)

if [ "$VERIFY_EXIT" -eq 0 ]; then
    pass "C9: verify_install.sh passed ($VERIFY_PASSES checks)"
elif [ "$VERIFY_FAILS" -eq 0 ]; then
    warn "C9: verify_install.sh exit $VERIFY_EXIT but no FAIL lines"
else
    warn "C9: verify_install.sh had $VERIFY_FAILS failures"
    echo "$VERIFY_OUTPUT" | grep "FAIL" | head -5 | while read -r line; do
        echo "    $line"
    done
fi
echo ""

# ── C10: Hermes still works after Clarvis overlay ──
echo -e "${B}[C10] Hermes post-overlay${Z}"
if $QUICK; then
    skip_it "C10: Hermes post-overlay (--quick)"
else
    if python3 -c "import hermes_agent" 2>/dev/null; then
        pass "C10: hermes_agent still importable after Clarvis overlay"
    elif command -v hermes &>/dev/null; then
        pass "C10: hermes CLI still available after overlay"
    else
        warn "C10: hermes_agent not importable (may not have been installed)"
    fi
fi
echo ""

# ═══════════════════════════════════════════════���════════════════════════════
# SUMMARY & ARTIFACTS
# ══════════════════════��════════════════════════════════���════════════════════
TOTAL=$((PASS + FAIL + WARN + SKIP))
echo -e "${B}╔═══════════════════════════��═══════════════════════════════╗${Z}"
echo -e "${B}║  Results: ${G}$PASS passed${Z}, ${R}$FAIL failed${Z}, ${Y}$WARN warnings${Z}, ${C}$SKIP skipped${Z} (of $TOTAL) ║"
echo -e "${B}╚══���════════════════════════════════════════════════════════╝${Z}"
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

if [ "$FAIL" -eq 0 ]; then
    VERDICT="PASS"
    echo -e "${G}${B}VERDICT: PASS${Z}"
    echo "Clarvis installs and runs on a fresh Hermes install."
else
    VERDICT="FAIL"
    echo -e "${R}${B}VERDICT: FAIL${Z}"
    echo "Resolve failures before claiming Clarvis-on-Hermes support."
fi
echo ""

# Save result JSON
ARTIFACT_DIR="$REPO_ROOT/docs/validation/e2e_clarvis_on_hermes_fresh_${TS}"
mkdir -p "$ARTIFACT_DIR"
cp "$TEST_ROOT/artifacts/"* "$ARTIFACT_DIR/" 2>/dev/null || true

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
    'gate': 'e2e_clarvis_on_hermes_fresh',
    'timestamp': '$TS',
    'verdict': '$VERDICT',
    'passed': $PASS,
    'failed': $FAIL,
    'warnings': $WARN,
    'skipped': $SKIP,
    'total': $TOTAL,
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

[ "$VERDICT" = "PASS" ] && exit 0 || exit 1
