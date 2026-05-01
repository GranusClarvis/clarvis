#!/bin/bash
# cron_schedule_audit.sh — Diff three sources of cron truth and report drift.
#
# Sources:
#   1. live `crontab -l` — what the system actually runs
#   2. `clarvis cron list` — what the clarvis cron manager believes is installed
#   3. CLAUDE.md schedule table — documented schedule (the human contract)
#
# Drift categories (any non-empty category causes non-zero exit):
#   A. Time mismatch — script in both crontab and clarvis list with different schedules
#   B. Missing managed — script in clarvis list but not in crontab
#   C. Unmanaged in crontab — script in crontab not in clarvis list AND not in CLAUDE.md
#
# Soft (informational only, no exit code impact):
#   D. Documented but absent — script in CLAUDE.md but not in crontab
#
# Output: monitoring/cron_drift.log
# Exit:   0 = no drift; 1 = drift detected; 2 = audit error
#
# Test override: set CRON_AUDIT_CRONTAB_FILE to a file path to substitute for `crontab -l`.
# Test hook:    set CLARVIS_CRONTAB_CMD to a binary that emulates `crontab` (used by tests
#               to simulate permission-denied / unreadable crontabs without touching the
#               system crontab). Defaults to plain `crontab` from PATH.

set -uo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOGFILE="$CLARVIS_WORKSPACE/monitoring/cron_drift.log"
CLAUDE_MD="${CLARVIS_CLAUDE_MD:-/home/agent/.openclaw/CLAUDE.md}"
CRONTAB_SOURCE="${CRON_AUDIT_CRONTAB_FILE:-}"

mkdir -p "$(dirname "$LOGFILE")"

TMPDIR_AUDIT="$(mktemp -d -t cron_audit.XXXXXX)"
trap 'rm -rf "$TMPDIR_AUDIT"' EXIT

CRONTAB_PARSED="$TMPDIR_AUDIT/crontab.parsed"
CLARVIS_PARSED="$TMPDIR_AUDIT/clarvis.parsed"
CLAUDE_PARSED="$TMPDIR_AUDIT/claude.parsed"

ts() { date -u +%Y-%m-%dT%H:%M:%S; }

log() { echo "[$(ts)] $*" | tee -a "$LOGFILE"; }

# --- Parse crontab -l --------------------------------------------------------
# Output format per line: <sched>|<script_basename>|<original_line>
# <sched> = first 5 cron fields, space-separated
# <script_basename> = main script (excludes cron_env.sh utility)
parse_crontab() {
    local cmd_output
    if [ -n "$CRONTAB_SOURCE" ] && [ -f "$CRONTAB_SOURCE" ]; then
        cmd_output="$(cat "$CRONTAB_SOURCE")"
    else
        # Capture stdout and stderr separately so we can distinguish a benign
        # "no crontab for <user>" (just an empty schedule) from a real read or
        # permission failure. The previous `crontab -l 2>/dev/null || true`
        # silently masked permission errors as zero-drift.
        local stderr_file="$TMPDIR_AUDIT/crontab.stderr"
        local crontab_cmd="${CLARVIS_CRONTAB_CMD:-crontab}"
        local rc=0
        cmd_output="$("$crontab_cmd" -l 2>"$stderr_file")" || rc=$?
        local stderr_msg
        stderr_msg="$(cat "$stderr_file" 2>/dev/null || true)"
        if [ "$rc" -ne 0 ]; then
            if echo "$stderr_msg" | grep -qiE 'no crontab for'; then
                cmd_output=""
            else
                log "ERROR: crontab -l failed (exit=$rc): ${stderr_msg:-<no stderr>}"
                log "Refusing to report drift from an unreadable live crontab. Use CRON_AUDIT_CRONTAB_FILE=<path> to supply a fixture."
                return 2
            fi
        fi
    fi
    echo "$cmd_output" | awk '
    /^[[:space:]]*$/ { next }
    /^[[:space:]]*#/ { next }
    {
        # Capture full original line for reporting
        original = $0
        # First 5 fields are the schedule (handle ranges/commas/asterisks)
        sched = $1 " " $2 " " $3 " " $4 " " $5
        # Remainder is the command
        cmd = ""
        for (i = 6; i <= NF; i++) cmd = cmd " " $i
        # Strip log redirect
        sub(/[[:space:]]*>>?.*$/, "", cmd)
        # Find all .sh/.py file references
        n = 0
        # Iterate by manual tokenize on whitespace and shell metacharacters
        m = cmd
        gsub(/[;&|<>()]/, " ", m)
        split(m, parts, /[[:space:]]+/)
        chosen = ""
        for (j in parts) {
            t = parts[j]
            if (t ~ /\.(sh|py)$/) {
                # strip path
                bn = t
                sub(/.*\//, "", bn)
                if (bn != "cron_env.sh") {
                    chosen = bn
                }
            }
        }
        if (chosen == "") next
        printf "%s|%s|%s\n", sched, chosen, original
    }
    ' > "$CRONTAB_PARSED"
}

# --- Parse `clarvis cron list` ----------------------------------------------
# Output format: <sched>|<script_basename>
parse_clarvis() {
    if ! command -v clarvis >/dev/null 2>&1; then
        log "WARN: clarvis CLI not found on PATH — clarvis source will be empty"
        : > "$CLARVIS_PARSED"
        return
    fi
    clarvis cron list 2>/dev/null | awk '
    /^Schedule[[:space:]]/  { next }
    /^[[:space:]]*$/         { next }
    /^[─-]+/                  { next }
    {
        # Require last field to look like a script basename (.sh or .py).
        script = $NF
        if (script !~ /\.(sh|py)$/) next
        # First 5 whitespace-separated fields are the schedule
        sched = $1 " " $2 " " $3 " " $4 " " $5
        printf "%s|%s\n", sched, script
    }
    ' > "$CLARVIS_PARSED"
}

# --- Parse CLAUDE.md schedule table -----------------------------------------
# Output format: <script_basename>
# (We do not attempt to parse the human-readable times — too fuzzy.)
parse_claude_md() {
    if [ ! -f "$CLAUDE_MD" ]; then
        log "WARN: CLAUDE.md not found at $CLAUDE_MD — claude_md source will be empty"
        : > "$CLAUDE_PARSED"
        return
    fi
    # Capture lines inside any markdown table containing a script basename
    grep -E '^\|.*\.(sh|py)' "$CLAUDE_MD" | grep -oE '[a-zA-Z_0-9]+\.(sh|py)' | sort -u > "$CLAUDE_PARSED"
}

# --- Compare and report ------------------------------------------------------
compare() {
    local drift=0

    log "=== Cron schedule drift audit started ==="
    log "Sources: crontab=$(wc -l <"$CRONTAB_PARSED") clarvis=$(wc -l <"$CLARVIS_PARSED") claude_md=$(wc -l <"$CLAUDE_PARSED")"

    # Build script-only sets (sorted, unique) for set ops
    local crontab_scripts="$TMPDIR_AUDIT/crontab.scripts"
    local clarvis_scripts="$TMPDIR_AUDIT/clarvis.scripts"
    cut -d'|' -f2 "$CRONTAB_PARSED" | sort -u > "$crontab_scripts"
    cut -d'|' -f2 "$CLARVIS_PARSED" | sort -u > "$clarvis_scripts"

    # --- (A) Time mismatches: same script, different schedule -----------
    # Note: a script may legitimately appear multiple times (e.g. cron_autonomous.sh).
    # We consider it a mismatch only if the script appears in BOTH sources but
    # the SET of schedules differs.
    local mismatches="$TMPDIR_AUDIT/mismatches.txt"
    : > "$mismatches"
    while IFS= read -r script; do
        [ -z "$script" ] && continue
        # crontab schedules for this script
        local cs
        cs="$(awk -F'|' -v s="$script" '$2==s {print $1}' "$CRONTAB_PARSED" | sort -u)"
        # clarvis schedules for this script
        local ls
        ls="$(awk -F'|' -v s="$script" '$2==s {print $1}' "$CLARVIS_PARSED" | sort -u)"
        if [ -n "$cs" ] && [ -n "$ls" ] && [ "$cs" != "$ls" ]; then
            {
                echo "  $script"
                echo "    crontab : $(echo "$cs" | tr '\n' ';' | sed 's/;$//')"
                echo "    clarvis : $(echo "$ls" | tr '\n' ';' | sed 's/;$//')"
            } >> "$mismatches"
        fi
    done < <(cat "$crontab_scripts" "$clarvis_scripts" | sort -u)

    if [ -s "$mismatches" ]; then
        drift=1
        log "DRIFT [A] Time mismatches between crontab and clarvis cron list:"
        cat "$mismatches" | tee -a "$LOGFILE"
    else
        log "OK   [A] No time mismatches"
    fi

    # --- (B) Missing managed: in clarvis list but not in crontab --------
    local missing="$TMPDIR_AUDIT/missing.txt"
    comm -23 "$clarvis_scripts" "$crontab_scripts" > "$missing"
    if [ -s "$missing" ]; then
        drift=1
        log "DRIFT [B] Missing managed entries (in clarvis cron list but not in crontab):"
        sed 's/^/  /' "$missing" | tee -a "$LOGFILE"
    else
        log "OK   [B] No missing managed entries"
    fi

    # --- (C) Unmanaged in crontab: in crontab, not in clarvis, not in CLAUDE.md
    local unmanaged="$TMPDIR_AUDIT/unmanaged.txt"
    : > "$unmanaged"
    while IFS= read -r script; do
        [ -z "$script" ] && continue
        if grep -Fxq "$script" "$clarvis_scripts"; then continue; fi
        if grep -Fxq "$script" "$CLAUDE_PARSED"; then continue; fi
        # Find the offending line(s)
        awk -F'|' -v s="$script" '$2==s {print $3}' "$CRONTAB_PARSED" | while IFS= read -r off_line; do
            echo "  $script" >> "$unmanaged"
            echo "    line: $off_line" >> "$unmanaged"
        done
    done < "$crontab_scripts"
    if [ -s "$unmanaged" ]; then
        drift=1
        log "DRIFT [C] Unmanaged crontab entries (not in clarvis cron list AND not documented in CLAUDE.md):"
        cat "$unmanaged" | tee -a "$LOGFILE"
    else
        log "OK   [C] No unmanaged crontab entries"
    fi

    # --- (D) Documented but absent (informational only) -----------------
    local absent="$TMPDIR_AUDIT/absent.txt"
    comm -23 "$CLAUDE_PARSED" "$crontab_scripts" > "$absent"
    if [ -s "$absent" ]; then
        log "INFO [D] Documented in CLAUDE.md but absent from crontab (informational, not drift):"
        sed 's/^/  /' "$absent" | tee -a "$LOGFILE"
    else
        log "OK   [D] All documented scripts present in crontab"
    fi

    if [ "$drift" -eq 0 ]; then
        log "=== Audit clean: zero drift ==="
        return 0
    else
        log "=== Audit DETECTED DRIFT — review above ==="
        return 1
    fi
}

# --- Main --------------------------------------------------------------------
main() {
    parse_crontab
    local crontab_rc=$?
    if [ "$crontab_rc" -ne 0 ]; then
        log "=== Audit ABORTED — crontab source unreadable (exit $crontab_rc) ==="
        return "$crontab_rc"
    fi
    parse_clarvis
    parse_claude_md
    compare
}

main "$@"
