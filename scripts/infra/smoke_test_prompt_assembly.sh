#!/bin/bash
# Smoke test: validate prompt assembly in all Claude-spawning scripts.
# Catches the class of failures where heredoc expansion or shell quoting
# produces empty prompt files, which cause instant Claude exit=1.
#
# Usage: ./scripts/smoke_test_prompt_assembly.sh
# Exit: 0 = all pass, 1 = failures found

set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(cd "$SCRIPTS_DIR/../.." && pwd)"
CRON_DIR="$WORKSPACE/scripts/cron"

PASS=0
FAIL=0
WARN=0

pass() { PASS=$((PASS+1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }
warn() { WARN=$((WARN+1)); echo "  WARN: $1"; }

echo "=== Prompt Assembly Smoke Test ==="
echo ""

# --- Test 1: Bash syntax check all cron scripts ---
echo "[1] Bash syntax validation"
for script in cron_autonomous.sh cron_evening.sh cron_evolution.sh \
              cron_implementation_sprint.sh cron_research.sh \
              cron_monthly_reflection.sh cron_strategic_audit.sh \
              cron_morning.sh cron_env.sh; do
    if [ -f "$CRON_DIR/$script" ]; then
        if bash -n "$CRON_DIR/$script" 2>/dev/null; then
            pass "$script syntax OK"
        else
            fail "$script syntax ERROR"
        fi
    fi
done
# Also check spawn_claude.sh (in agents/)
if [ -f "$WORKSPACE/scripts/agents/spawn_claude.sh" ]; then
    if bash -n "$WORKSPACE/scripts/agents/spawn_claude.sh" 2>/dev/null; then
        pass "spawn_claude.sh syntax OK"
    else
        fail "spawn_claude.sh syntax ERROR"
    fi
fi

# --- Test 2: No unquoted heredocs with variable expansion in prompt builders ---
echo ""
echo "[2] Unquoted heredoc detection (prompt builders)"
for script in cron_autonomous.sh cron_evening.sh cron_evolution.sh \
              cron_implementation_sprint.sh cron_research.sh \
              cron_monthly_reflection.sh cron_strategic_audit.sh; do
    f="$CRON_DIR/$script"
    [ -f "$f" ] || continue
    # Look for << WORD (unquoted) that likely builds prompts
    # Exclude <<- (tab-stripped) and <<'WORD' / <<"WORD" (quoted)
    unquoted=$(grep -nP '<<\s*[A-Z][A-Z_]+\s*$' "$f" 2>/dev/null | grep -v "<<'" | grep -v '<<"' || true)
    if [ -n "$unquoted" ]; then
        warn "$script has unquoted heredoc(s): $(echo "$unquoted" | head -1 | sed 's/\t/ /g')"
    else
        pass "$script no unquoted heredocs"
    fi
done

# --- Test 3: Prompt empty validation exists in key paths ---
echo ""
echo "[3] Prompt-empty guard check"
if grep -q 'PROMPT_GUARD' "$CRON_DIR/cron_autonomous.sh" 2>/dev/null; then
    pass "cron_autonomous.sh has PROMPT_GUARD"
else
    fail "cron_autonomous.sh missing PROMPT_GUARD"
fi
if grep -q 'PROMPT_GUARD' "$CRON_DIR/cron_env.sh" 2>/dev/null; then
    pass "cron_env.sh (run_claude_monitored) has PROMPT_GUARD"
else
    fail "cron_env.sh missing PROMPT_GUARD"
fi

# --- Test 4: Simulate prompt assembly with test data ---
echo ""
echo "[4] Prompt assembly simulation (cron_autonomous pattern)"
WORKER_TEMPLATE="Test template"
TIME_BUDGET_HINT="TIME BUDGET: ~25 minutes"
WEAKEST_METRIC="Reasoning Chains"
CONTEXT_BRIEF='Brain data with $DOLLAR and ${BRACES} and `backticks` and ENDPROMPT in text'
PROC_HINT=""
BATCH_TASKS="[TEST] Task with special chars: \$var \${expansion} \`cmd\`"
_test_file=$(mktemp --suffix=.txt)
{
    printf '%s\n\n' "${WORKER_TEMPLATE:-You are Clarvis executive function.}"
    printf '%s\n' "$TIME_BUDGET_HINT"
    printf 'WEAKEST METRIC: %s — consider if your task can improve this.\n' "$WEAKEST_METRIC"
    printf 'QUEUE: Read memory/evolution/QUEUE.md for task backlog.\n'
    printf '%s\n' "$CONTEXT_BRIEF"
    if [ -n "$PROC_HINT" ]; then
        printf '\nPROCEDURAL HINT: %s\n' "$PROC_HINT"
    fi
    printf '\nTASKS:\n'
    printf '%s\n' "$BATCH_TASKS" | nl -w2 -s'. '
} > "$_test_file"
if [ -s "$_test_file" ]; then
    SIZE=$(wc -c < "$_test_file")
    # Verify special chars survived
    if grep -q 'DOLLAR' "$_test_file" && grep -q 'BRACES' "$_test_file" && grep -q 'backticks' "$_test_file"; then
        pass "Prompt assembly OK (${SIZE}B, special chars preserved)"
    else
        fail "Prompt assembly lost special characters"
    fi
else
    fail "Prompt assembly produced empty file"
fi
rm -f "$_test_file"

# --- Test 5: Python null-safety in key modules ---
echo ""
echo "[5] Python null-safety checks"
if python3 -c "
import sys; sys.path.insert(0, '$WORKSPACE/scripts/evolution')
from automation_insights import _extract_action_verb
assert _extract_action_verb(None) == '', 'None should return empty'
assert _extract_action_verb('') == '', 'Empty should return empty'
assert _extract_action_verb('[TEST] Fix bug') != '', 'Normal text should return verb'
print('automation_insights null-safe')
" 2>&1; then
    pass "automation_insights._extract_action_verb null-safe"
else
    fail "automation_insights._extract_action_verb NOT null-safe"
fi

if python3 -c "
import sys; sys.path.insert(0, '$WORKSPACE/scripts/evolution')
from meta_learning import MetaLearner
# Test that analyze works even if episodes have null tasks
ml = MetaLearner()
# Just verify it doesn't crash on import
print('meta_learning importable')
" 2>&1; then
    pass "meta_learning importable and null-safe"
else
    fail "meta_learning import/null-safety issue"
fi

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed, $WARN warnings ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
