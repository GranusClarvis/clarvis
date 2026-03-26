#!/bin/bash
# =============================================================================
# Cron Error Aggregator — Daily error summary from cron & monitoring logs
# =============================================================================
# Scans memory/cron/*.log and monitoring/*.log for ERROR/FATAL/Traceback lines,
# deduplicates by signature, and writes a daily summary to monitoring/.
#
# Usage:
#   ./cron_error_aggregator.sh           # Scan today's errors, write summary
#   ./cron_error_aggregator.sh --stdout  # Also print summary to stdout
#
# Output: monitoring/cron_errors_daily.md
# Suitable for wiring into cron_report_morning.sh
# =============================================================================

source "$(dirname "$0")/cron_env.sh" 2>/dev/null || true

WORKSPACE="${CLARVIS_WORKSPACE:-/home/agent/.openclaw/workspace}"
CRON_LOG_DIR="$WORKSPACE/memory/cron"
MON_LOG_DIR="$WORKSPACE/monitoring"
OUTPUT="$MON_LOG_DIR/cron_errors_daily.md"
TODAY=$(date '+%Y-%m-%d')
NOW=$(date '+%Y-%m-%d %H:%M:%S')
STDOUT_MODE=false
TMP_RAW=$(mktemp /tmp/clarvis_erragg_raw.XXXXXX)
TMP_SIGS=$(mktemp /tmp/clarvis_erragg_sigs.XXXXXX)

trap 'rm -f "$TMP_RAW" "$TMP_SIGS"' EXIT

for arg in "$@"; do
  case "$arg" in
    --stdout) STDOUT_MODE=true ;;
  esac
done

mkdir -p "$MON_LOG_DIR"

# ---------------------------------------------------------------------------
# 1. Collect raw error lines from all logs (today only, by timestamp or date)
# ---------------------------------------------------------------------------
# Match lines that ARE errors (not lines that merely mention error-related words).
# - Anchored patterns: line starts with or contains bracketed [ERROR]/[FATAL]
# - Traceback header (always a real error)
# - "Error:" at start or after whitespace (Python exception lines)
# - "Failed to authenticate" (API auth failures)
# Filter to today's date where possible (logs use [YYYY-MM-DD...] timestamps)
PATTERN='(\[ERROR\]|\[FATAL\]|\[ALERT\]|^ERROR:|^FATAL:|^Traceback \(most recent|^[A-Za-z]*Error:|^\s+[A-Za-z]*Error:|Failed to authenticate\. API Error|FAILED:)'

for logfile in "$CRON_LOG_DIR"/*.log "$MON_LOG_DIR"/*.log; do
  [ -f "$logfile" ] || continue

  # Only consider lines from today (check for date in brackets or at line start)
  # Also include lines without dates if the file was modified today
  file_date=$(date -r "$logfile" '+%Y-%m-%d' 2>/dev/null)
  basename=$(basename "$logfile" .log)

  # Extract matching lines, prefix with source log name
  while IFS= read -r line; do
    # If line has a date stamp, only include if it's today
    if echo "$line" | grep -qE "\[?$TODAY" 2>/dev/null; then
      echo "$basename|$line" >> "$TMP_RAW"
    elif [ "$file_date" = "$TODAY" ] && ! echo "$line" | grep -qE '\[20[0-9]{2}-[0-9]{2}-[0-9]{2}' 2>/dev/null; then
      # Undated line in a file modified today — include it
      echo "$basename|$line" >> "$TMP_RAW"
    fi
  done < <(grep -E "$PATTERN" "$logfile" 2>/dev/null)
done

TOTAL_RAW=$(wc -l < "$TMP_RAW" 2>/dev/null || echo 0)

# ---------------------------------------------------------------------------
# 2. Deduplicate by signature
# ---------------------------------------------------------------------------
# Signature = source + normalized error text (strip timestamps, hex addrs, IDs)
generate_signature() {
  local source="$1"
  local line="$2"
  # Strip timestamps, request IDs, hex addresses, UUIDs, numbers
  local normalized
  normalized=$(echo "$line" \
    | sed -E 's/\[20[0-9]{2}-[0-9]{2}-[0-9]{2}[T ][0-9:]+\]//g' \
    | sed -E 's/req_[A-Za-z0-9]+/req_XXX/g' \
    | sed -E 's/0x[0-9a-fA-F]+/0xXXX/g' \
    | sed -E 's/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/UUID/g' \
    | sed -E 's/[0-9]+/N/g' \
    | tr -s ' ' \
  )
  echo "${source}::${normalized}"
}

# Build signature -> count + first example mapping
declare -A SIG_COUNT
declare -A SIG_EXAMPLE
declare -A SIG_SOURCE
declare -a SIG_ORDER

while IFS='|' read -r source line; do
  [ -z "$line" ] && continue
  sig=$(generate_signature "$source" "$line")
  if [ -z "${SIG_COUNT[$sig]}" ]; then
    SIG_COUNT[$sig]=1
    SIG_EXAMPLE[$sig]="$line"
    SIG_SOURCE[$sig]="$source"
    SIG_ORDER+=("$sig")
  else
    SIG_COUNT[$sig]=$(( ${SIG_COUNT[$sig]} + 1 ))
  fi
done < "$TMP_RAW"

UNIQUE_SIGS=${#SIG_ORDER[@]}

# ---------------------------------------------------------------------------
# 3. Sort signatures by count (descending)
# ---------------------------------------------------------------------------
for sig in "${SIG_ORDER[@]}"; do
  echo "${SIG_COUNT[$sig]} $sig"
done | sort -rn > "$TMP_SIGS"

# ---------------------------------------------------------------------------
# 4. Write daily summary
# ---------------------------------------------------------------------------
{
  echo "# Cron Error Summary — $TODAY"
  echo ""
  echo "Generated: $NOW"
  echo "Scanned: \`memory/cron/*.log\`, \`monitoring/*.log\`"
  echo ""
  echo "**Total error lines today:** $TOTAL_RAW"
  echo "**Unique error signatures:** $UNIQUE_SIGS"
  echo ""

  if [ "$UNIQUE_SIGS" -eq 0 ]; then
    echo "No errors detected today."
  else
    echo "## Errors by Frequency"
    echo ""
    while read -r count sig; do
      [ -z "$sig" ] && continue
      source_name="${SIG_SOURCE[$sig]}"
      example="${SIG_EXAMPLE[$sig]}"
      # Truncate long examples
      if [ ${#example} -gt 200 ]; then
        example="${example:0:200}..."
      fi
      echo "### \`$source_name\` (${count}x)"
      echo '```'
      echo "$example"
      echo '```'
      echo ""
    done < "$TMP_SIGS"

    # Source breakdown
    echo "## Errors by Source"
    echo ""
    echo "| Log | Count |"
    echo "|-----|-------|"
    declare -A SOURCE_TOTALS
    for sig in "${SIG_ORDER[@]}"; do
      src="${SIG_SOURCE[$sig]}"
      cnt="${SIG_COUNT[$sig]}"
      SOURCE_TOTALS[$src]=$(( ${SOURCE_TOTALS[$src]:-0} + cnt ))
    done
    for src in $(for s in "${!SOURCE_TOTALS[@]}"; do echo "${SOURCE_TOTALS[$s]} $s"; done | sort -rn | awk '{print $2}'); do
      echo "| $src | ${SOURCE_TOTALS[$src]} |"
    done
    echo ""
  fi

  echo "---"
  echo "*Auto-generated by \`cron_error_aggregator.sh\`*"
} > "$OUTPUT"

# ---------------------------------------------------------------------------
# 5. Output
# ---------------------------------------------------------------------------
if [ "$STDOUT_MODE" = true ]; then
  cat "$OUTPUT"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Error aggregator: $TOTAL_RAW raw lines, $UNIQUE_SIGS unique signatures → $OUTPUT"
