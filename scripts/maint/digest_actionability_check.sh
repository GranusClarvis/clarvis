#!/usr/bin/env bash
# digest_actionability_check.sh — regression guard for digest actionability.
#
# Phase 12 audit (2026-04-30) measured digest actionability at 56.5% (REVISE).
# A common silent failure mode is the digest writer producing a paragraph-only
# blob with zero structured action markers. When that happens, the next morning
# planning slot sees no concrete follow-ups and the autonomous loop drifts.
#
# This guard runs at 22:35 (right after the 22:30 digest writer) and trips when
# the digest contains zero of the canonical actionability markers:
#     ^- \[ \]    (markdown unchecked checkbox)
#     ^Next:      (explicit next-step line)
#     ^Action:    (explicit action line)
#
# Exit codes:
#   0 — at least one marker found (or no digest file → nothing to guard)
#   1 — digest exists but has zero markers (alert)
#   2 — usage error
#
# Output:
#   Appends one line to monitoring/digest_actionability.log on every run,
#   tagged OK / ALERT / SKIP, with the match count.
#
# Usage:
#   digest_actionability_check.sh [DIGEST_PATH]
# If DIGEST_PATH is omitted, defaults to $CLARVIS_WORKSPACE/memory/cron/digest.md
# (with $HOME/.openclaw/workspace as the fallback workspace root).

set -euo pipefail

WS="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"
DIGEST="${1:-$WS/memory/cron/digest.md}"
LOGFILE="$WS/monitoring/digest_actionability.log"

mkdir -p "$(dirname "$LOGFILE")"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ ! -f "$DIGEST" ]; then
    echo "[$(ts)] SKIP digest=$DIGEST reason=missing" >> "$LOGFILE"
    exit 0
fi

# Count matches. grep -c with -E; tolerate zero-match without aborting under -e.
MATCHES=$(grep -cE '^- \[ \]|^Next:|^Action:' "$DIGEST" || true)
MATCHES=${MATCHES:-0}

if [ "$MATCHES" -gt 0 ]; then
    echo "[$(ts)] OK digest=$DIGEST matches=$MATCHES" >> "$LOGFILE"
    exit 0
fi

echo "[$(ts)] ALERT digest=$DIGEST matches=0 patterns='^- [ ]|^Next:|^Action:'" >> "$LOGFILE"
exit 1
