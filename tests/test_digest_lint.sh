#!/usr/bin/env bash
# test_digest_lint.sh — synthetic test for scripts/cron/digest_lint.sh
#
# Exercises both code paths required by [DIGEST_LINT_PRECOMMIT]:
#   - garbled 2026-04-25 sample → exit ≠ 0 with one-line reason
#   - clean digest sample        → exit 0
# Plus regression coverage for the other two checks (braces, EOF truncation)
# and the wired digest_writer.py rollback + fenced fallback.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LINT="$REPO_ROOT/scripts/cron/digest_lint.sh"
WRITER="$REPO_ROOT/scripts/tools/digest_writer.py"

if [[ ! -f "$LINT" ]]; then
    echo "FAIL: $LINT missing"
    exit 1
fi
chmod +x "$LINT" 2>/dev/null || true

pass=0
fail=0

run_lint_case() {
    local name="$1"
    local expected="$2"   # "0" or "nonzero"
    local content="$3"
    local tmp out code
    tmp="$(mktemp)"
    printf '%s' "$content" > "$tmp"
    out="$(bash "$LINT" "$tmp" 2>&1)" && code=$? || code=$?
    rm -f "$tmp"
    if [[ "$expected" == "0" && "$code" == "0" ]]; then
        echo "  PASS: $name (exit=0)"
        pass=$((pass + 1))
    elif [[ "$expected" == "nonzero" && "$code" != "0" ]]; then
        echo "  PASS: $name (exit=$code, reason: $out)"
        pass=$((pass + 1))
    else
        echo "  FAIL: $name (expected=$expected, got=$code, output: $out)"
        fail=$((fail + 1))
    fi
}

echo "[1] digest_lint.sh — direct cases"

# (a) Garbled 2026-04-25 sample — the explicit acceptance criterion
run_lint_case "garbled-2026-04-25-sample" "nonzero" \
"### autonomous — 12:34 UTC

me plays.n  ,n  tests_passed: true,n  duration: 12s

---
"

# Clean digest sample — explicit acceptance criterion
run_lint_case "clean-digest-sample" "0" \
"# Clarvis Daily Digest — 2026-04-30

_What I did today, written by my subconscious processes._

### autonomous — 12:34 UTC

I executed task X. Result: success. Duration: 42s.

---

"

# (b) Unbalanced JSON-like braces
run_lint_case "unbalanced-braces" "nonzero" \
"### x — 1:1

Result: { \"a\": 1, \"b\": 2

---
"

# (c) Mid-word truncation at EOF
run_lint_case "midword-truncation" "nonzero" \
"### x — 1:1

I did somethi"

# Fenced code block — braces and ,n inside fence are ignored
run_lint_case "fenced-code-ignored" "0" \
"### x — 1:1

I did stuff.

\`\`\`json
{ \"a\": 1, \"b\": 2,n  field: x

\`\`\`

---
"

# Empty file — accept
run_lint_case "empty-file" "0" ""

echo ""
echo "[2] digest_writer.py — wired rollback + fenced fallback"

if [[ ! -f "$WRITER" ]]; then
    echo "  FAIL: $WRITER missing"
    fail=$((fail + 1))
else
    tmp_ws="$(mktemp -d)"
    py_out="$(CLARVIS_WORKSPACE="$tmp_ws" python3 - <<PYEOF 2>&1
import os, sys
sys.path.insert(0, "$REPO_ROOT/scripts/tools")
import digest_writer
digest_writer.DIGEST_LINT_SCRIPT = "$LINT"

# garbled payload should be rolled back + re-rendered as fenced
r = digest_writer.write_digest("autonomous", "me plays.n  ,n  tests_passed: true,n  duration: 12s")
print("LF=" + str(r["lint_failed"]))

# clean payload after a fenced fallback must not re-trigger
r2 = digest_writer.write_digest("autonomous", "I executed task X. Result: success.")
print("CL=" + str(r2["lint_failed"]))

# the digest file must contain the fenced wrapper but no raw garble outside it
content = open(digest_writer.DIGEST_FILE).read()
print("FENCE=" + str("\`\`\`" in content))
PYEOF
)"
    rm -rf "$tmp_ws"
    if grep -q "LF=True" <<<"$py_out" \
       && grep -q "CL=False" <<<"$py_out" \
       && grep -q "FENCE=True" <<<"$py_out"; then
        echo "  PASS: writer rolls back garbled payload and renders fenced fallback"
        pass=$((pass + 1))
    else
        echo "  FAIL: writer integration"
        echo "$py_out" | sed 's/^/    /'
        fail=$((fail + 1))
    fi
fi

echo ""
echo "Summary: $pass passed, $fail failed"
[[ "$fail" -eq 0 ]]
