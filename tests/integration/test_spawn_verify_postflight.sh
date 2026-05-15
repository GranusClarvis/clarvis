#!/bin/bash
# Integration test for spawn_postflight_verify.py and the spawn_claude.sh
# postflight block (CLARVIS_PROC_SPAWN_VERIFY_POSTFLIGHT acceptance b).
#
# Simulates a spawn that adds a `[x] [UNVERIFIED]` row whose referenced
# artifact does not exist and asserts:
#   (i)   monitoring/spawn_artifact_holds.log gets a JSON line
#   (ii)  the row in QUEUE.md gets a SPAWN_POSTFLIGHT_HELD annotation
#   (iii) the verifier exits non-zero
# Plus the inverse: a closure whose artifact DOES exist must NOT be flagged
# (rc=0, no holds log entry, no annotation).

set -uo pipefail

WORKSPACE_ROOT="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"
VERIFIER="$WORKSPACE_ROOT/scripts/agents/spawn_postflight_verify.py"

if [ ! -f "$VERIFIER" ]; then
    echo "FAIL: verifier missing at $VERIFIER" >&2
    exit 2
fi

TMP="$(mktemp -d -t spawn_postflight_test_XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0
_pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
_fail() { echo "  FAIL: $1" >&2; FAIL=$((FAIL + 1)); }

# ---------------------------------------------------------------------------
# Case A: missing artifact — must emit hold, annotate row, exit non-zero
# ---------------------------------------------------------------------------
echo "[case A] artifact-missing closure should be held"
A_WS="$TMP/case_a"
mkdir -p "$A_WS/memory/evolution" "$A_WS/monitoring" "$A_WS/scripts/infra"

cat > "$A_WS/memory/evolution/QUEUE.md" <<'EOF'
## P0 — Current Sprint
- [ ] **[CASE_A_TASK]** Build it. (PROJECT:CLARVIS)
EOF
cp "$A_WS/memory/evolution/QUEUE.md" "$A_WS/pre_snapshot.md"

# Spawn-style edit: flip to [x] [UNVERIFIED] referencing a path that
# does not exist on disk.
cat > "$A_WS/memory/evolution/QUEUE.md" <<'EOF'
## P0 — Current Sprint
- [x] [UNVERIFIED] **[CASE_A_TASK]** Shipped at `scripts/infra/never_existed.py`. (PROJECT:CLARVIS)
EOF

set +e
python3 "$VERIFIER" \
    --pre-state-file "$A_WS/pre_snapshot.md" \
    --session-id "test-case-a" \
    --workspace "$A_WS" \
    --quiet \
    > "$TMP/case_a.stdout" 2> "$TMP/case_a.stderr"
A_RC=$?
set -e

# (iii) non-zero exit
if [ "$A_RC" -ne 0 ]; then
    _pass "(iii) verifier exits non-zero (rc=$A_RC)"
else
    _fail "(iii) expected non-zero exit, got $A_RC"
fi

# (i) holds log JSON line
if [ -f "$A_WS/monitoring/spawn_artifact_holds.log" ]; then
    HOLD_LINE=$(grep '"missing_path": "scripts/infra/never_existed.py"' \
        "$A_WS/monitoring/spawn_artifact_holds.log" || true)
    if [ -n "$HOLD_LINE" ]; then
        _pass "(i) holds log contains JSON entry for missing artifact"
        # Also assert it's parseable JSON with required fields
        if python3 -c "
import json, sys
line = sys.stdin.read().strip()
d = json.loads(line)
assert d['session_id'] == 'test-case-a', f\"session_id: {d.get('session_id')}\"
assert d['tag'] == 'CASE_A_TASK', f\"tag: {d.get('tag')}\"
assert d['missing_path'] == 'scripts/infra/never_existed.py'
assert d.get('row_line_no'), 'row_line_no missing'
assert d.get('ts'), 'ts missing'
" <<<"$HOLD_LINE" 2>/dev/null; then
            _pass "(i) holds log JSON has session_id, tag, missing_path, row_line_no, ts"
        else
            _fail "(i) holds log JSON missing required fields"
        fi
    else
        _fail "(i) holds log does not mention missing_path"
        cat "$A_WS/monitoring/spawn_artifact_holds.log" >&2 2>/dev/null || true
    fi
else
    _fail "(i) monitoring/spawn_artifact_holds.log was not created"
fi

# (ii) row annotated in QUEUE.md
if grep -q 'SPAWN_POSTFLIGHT_HELD: ARTIFACT_MISSING — scripts/infra/never_existed.py' \
        "$A_WS/memory/evolution/QUEUE.md"; then
    _pass "(ii) QUEUE.md row carries SPAWN_POSTFLIGHT_HELD annotation"
else
    _fail "(ii) QUEUE.md row missing SPAWN_POSTFLIGHT_HELD annotation"
    cat "$A_WS/memory/evolution/QUEUE.md" >&2
fi

# ---------------------------------------------------------------------------
# Case B: artifact present — must NOT be flagged
# ---------------------------------------------------------------------------
echo "[case B] closure with present artifact should pass cleanly"
B_WS="$TMP/case_b"
mkdir -p "$B_WS/memory/evolution" "$B_WS/monitoring" "$B_WS/scripts/infra"
echo "# shipped" > "$B_WS/scripts/infra/exists.py"

cat > "$B_WS/memory/evolution/QUEUE.md" <<'EOF'
## P0 — Current Sprint
- [ ] **[CASE_B_TASK]** Build it. (PROJECT:CLARVIS)
EOF
cp "$B_WS/memory/evolution/QUEUE.md" "$B_WS/pre_snapshot.md"
cat > "$B_WS/memory/evolution/QUEUE.md" <<'EOF'
## P0 — Current Sprint
- [x] [UNVERIFIED] **[CASE_B_TASK]** Shipped at `scripts/infra/exists.py`. (PROJECT:CLARVIS)
EOF

set +e
python3 "$VERIFIER" \
    --pre-state-file "$B_WS/pre_snapshot.md" \
    --session-id "test-case-b" \
    --workspace "$B_WS" \
    --quiet \
    > "$TMP/case_b.stdout" 2> "$TMP/case_b.stderr"
B_RC=$?
set -e

if [ "$B_RC" -eq 0 ]; then
    _pass "case B exits zero (no holds)"
else
    _fail "case B expected rc=0, got $B_RC"
fi
if [ ! -f "$B_WS/monitoring/spawn_artifact_holds.log" ]; then
    _pass "case B did not create holds log"
else
    _fail "case B unexpectedly wrote holds log"
fi
if ! grep -q 'SPAWN_POSTFLIGHT_HELD' "$B_WS/memory/evolution/QUEUE.md"; then
    _pass "case B did not annotate QUEUE.md"
else
    _fail "case B unexpectedly annotated QUEUE.md"
fi

# ---------------------------------------------------------------------------
# Case C: pre-existing [x] [UNVERIFIED] row (unchanged in diff) must be ignored
# ---------------------------------------------------------------------------
echo "[case C] pre-existing closure unchanged in diff should be ignored"
C_WS="$TMP/case_c"
mkdir -p "$C_WS/memory/evolution" "$C_WS/monitoring" "$C_WS/scripts/infra"

# Same row in pre and post. Even though the artifact is missing, this row was
# already closed before the spawn — the spawn should not be blamed for it.
ROW='- [x] [UNVERIFIED] **[CASE_C_OLD]** Old shipment at `scripts/infra/long_gone.py`. (PROJECT:CLARVIS)'
{
    echo "## P0 — Current Sprint"
    echo "$ROW"
} > "$C_WS/memory/evolution/QUEUE.md"
cp "$C_WS/memory/evolution/QUEUE.md" "$C_WS/pre_snapshot.md"

set +e
python3 "$VERIFIER" \
    --pre-state-file "$C_WS/pre_snapshot.md" \
    --session-id "test-case-c" \
    --workspace "$C_WS" \
    --quiet \
    > "$TMP/case_c.stdout" 2> "$TMP/case_c.stderr"
C_RC=$?
set -e

if [ "$C_RC" -eq 0 ]; then
    _pass "case C exits zero (unchanged row ignored)"
else
    _fail "case C expected rc=0, got $C_RC"
fi
if [ ! -f "$C_WS/monitoring/spawn_artifact_holds.log" ]; then
    _pass "case C did not create holds log"
else
    _fail "case C unexpectedly wrote holds log"
    cat "$C_WS/monitoring/spawn_artifact_holds.log" >&2 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Acceptance (a) cross-check: spawn_claude.sh must include the postflight block
# (string-grep — keeps the test honest about wiring even though we don't run a
# real spawn here).
# ---------------------------------------------------------------------------
echo "[case D] spawn_claude.sh wiring check"
SC="$WORKSPACE_ROOT/scripts/agents/spawn_claude.sh"
if grep -q 'CLARVIS_PROC_SPAWN_VERIFY_POSTFLIGHT' "$SC" \
   && grep -q 'spawn_postflight_verify.py' "$SC" \
   && grep -q 'PRE_QUEUE_SNAPSHOT' "$SC"; then
    _pass "spawn_claude.sh contains postflight wiring (snapshot + verifier call)"
else
    _fail "spawn_claude.sh missing postflight wiring"
fi

# ---------------------------------------------------------------------------
# Acceptance (c) cross-check: 5 cron spawners honor the postflight pair
# ---------------------------------------------------------------------------
echo "[case E] cron spawners wiring check"
for f in cron_autonomous cron_evolution cron_reflection cron_research cron_implementation_sprint; do
    p="$WORKSPACE_ROOT/scripts/cron/$f.sh"
    if [ ! -f "$p" ]; then
        _fail "$f.sh missing on disk"
        continue
    fi
    if grep -q 'clarvis_postflight_snapshot' "$p" \
       && grep -q 'clarvis_postflight_verify' "$p"; then
        _pass "$f.sh wires snapshot + verify"
    else
        _fail "$f.sh missing postflight snapshot/verify wiring"
    fi
done

# ---------------------------------------------------------------------------
echo
echo "===================="
echo "PASS: $PASS  FAIL: $FAIL"
echo "===================="
[ "$FAIL" -eq 0 ]
