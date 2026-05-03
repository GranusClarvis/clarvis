#!/bin/bash
# End-to-end test for respawn_deferred.sh.
#
# Sets up a sandbox CLARVIS_WORKSPACE with:
#   - a stub `spawn_claude.sh` that records its args and exits 0
#   - a fake deferred ledger entry
#   - a freed global lock
# Then runs the real respawn_deferred.sh and asserts:
#   - the stub was invoked with the original task + flags
#   - the ledger entry was consumed (file removed)
set -uo pipefail

REAL_WS="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"
SANDBOX="$(mktemp -d)"
FAIL=0
_fail() { echo "FAIL: $*"; FAIL=$((FAIL+1)); }
_pass() { echo "PASS: $*"; }

# Mirror the directory structure the script expects.
mkdir -p "$SANDBOX/scripts/agents" "$SANDBOX/scripts/cron" \
         "$SANDBOX/data/deferred_spawns" "$SANDBOX/memory/cron"

# Use the real cron_env + lock_helper + respawn script — the rest is sandboxed.
cp "$REAL_WS/scripts/cron/cron_env.sh"     "$SANDBOX/scripts/cron/cron_env.sh"
cp "$REAL_WS/scripts/cron/lock_helper.sh"  "$SANDBOX/scripts/cron/lock_helper.sh"
cp "$REAL_WS/scripts/agents/respawn_deferred.sh" "$SANDBOX/scripts/agents/respawn_deferred.sh"

# Stub spawn_claude.sh — captures argv, exits 0.
STUB_LOG="$SANDBOX/spawn_invocations.log"
cat > "$SANDBOX/scripts/agents/spawn_claude.sh" <<EOF
#!/bin/bash
echo "INVOKED:" "\$@" >> "$STUB_LOG"
exit 0
EOF
chmod +x "$SANDBOX/scripts/agents/spawn_claude.sh"

# Hand-craft a ledger entry. Must match clarvis.agents.spawn_ledger format.
LEDGER_ID="20260503T140000Z-cafe01"
cat > "$SANDBOX/data/deferred_spawns/${LEDGER_ID}.json" <<EOF
{
  "id": "${LEDGER_ID}",
  "deferred_at": "2026-05-03T14:00:00Z",
  "task": "Sandbox test task with full preservation — quote 'a' and \"b\"",
  "timeout": 1800,
  "category": "research",
  "send_tg": false,
  "isolated": true,
  "tg_topic": "",
  "tg_chat_id": "",
  "retry_max": 0,
  "deferred_reason": "test_e2e",
  "attempts": 0,
  "last_attempt_at": null,
  "source": "test",
  "extra_flags": []
}
EOF

# Ensure the global lock is FREE so respawn proceeds.
rm -f /tmp/clarvis_claude_global.lock
# Dedicate a separate respawn-pass lock path so we don't collide with the real
# /tmp/clarvis_respawn_deferred.lock if production is live on the same machine.
# (The script uses /tmp/clarvis_respawn_deferred.lock — accept that, but ensure
# nobody else holds it.)
rm -f /tmp/clarvis_respawn_deferred.lock

# Point CLARVIS_WORKSPACE at the sandbox so PYTHONPATH and ledger paths route
# there. We reuse the real clarvis package (PYTHONPATH still finds it).
export CLARVIS_WORKSPACE="$SANDBOX"
export PYTHONPATH="$REAL_WS:${PYTHONPATH:-}"
# Don't trip the .env loader on the real workspace — sandbox has no .env.

bash "$SANDBOX/scripts/agents/respawn_deferred.sh"
RC=$?

if [ "$RC" != "0" ]; then
    _fail "respawn_deferred.sh exited $RC (expected 0)"
fi

# Stub should have been invoked exactly once.
if [ ! -f "$STUB_LOG" ]; then
    _fail "stub was never invoked — no $STUB_LOG"
elif [ "$(wc -l < "$STUB_LOG")" != "1" ]; then
    _fail "stub invoked $(wc -l < "$STUB_LOG") times (expected 1)"
else
    _pass "stub invoked exactly once"
fi

# Stub args must contain the original task text and key flags.
if grep -q "Sandbox test task with full preservation" "$STUB_LOG"; then
    _pass "task text preserved through ledger -> respawn"
else
    _fail "task text NOT found in stub args; got: $(cat "$STUB_LOG")"
fi
if grep -q -- '--no-tg' "$STUB_LOG"; then
    _pass "send_tg=false flag forwarded"
else
    _fail "--no-tg flag not forwarded"
fi
if grep -q -- '--isolated' "$STUB_LOG"; then
    _pass "isolated=true flag forwarded"
else
    _fail "--isolated flag not forwarded"
fi
if grep -q -- '--category=research' "$STUB_LOG"; then
    _pass "category flag forwarded"
else
    _fail "--category=research flag not forwarded"
fi
if grep -q -- ' 1800 ' "$STUB_LOG" || grep -q -- ' 1800$' "$STUB_LOG"; then
    _pass "timeout=1800 forwarded"
else
    _fail "timeout=1800 not forwarded; got: $(cat "$STUB_LOG")"
fi

# Ledger entry must have been consumed.
if [ -f "$SANDBOX/data/deferred_spawns/${LEDGER_ID}.json" ]; then
    _fail "ledger file still exists after successful respawn"
else
    _pass "ledger file consumed after successful respawn"
fi

# Cleanup
rm -rf "$SANDBOX"

if [ "$FAIL" = "0" ]; then
    echo "RESPAWN E2E TESTS PASSED"
    exit 0
else
    echo "RESPAWN E2E TESTS FAILED: $FAIL"
    exit 1
fi
