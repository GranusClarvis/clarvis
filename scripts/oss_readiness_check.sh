#!/bin/bash
# =============================================================================
# Open-Source Readiness Check
# =============================================================================
# Automated pre-launch audit for the Clarvis repository.
# Scans for leaked secrets, missing files, large binaries, and internal refs.
# Exit 0 = all pass, Exit 1 = one or more failures.
#
# Usage: ./scripts/oss_readiness_check.sh [--verbose]
# =============================================================================
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

WORKSPACE="/home/agent/.openclaw/workspace"
VERBOSE="${1:---quiet}"
PASS=0
FAIL=0
WARN=0

# --- Formatting helpers (matches health_monitor.sh style) ---
DATE=$(date '+%Y-%m-%d %H:%M:%S')

pass()  { PASS=$((PASS + 1)); echo "  [PASS] $1"; }
fail()  { FAIL=$((FAIL + 1)); echo "  [FAIL] $1"; }
warn()  { WARN=$((WARN + 1)); echo "  [WARN] $1"; }
info()  { echo "  [INFO] $1"; }
section() { echo ""; echo "=== $1 ==="; }

echo "============================================"
echo " Clarvis OSS Readiness Check"
echo " $DATE"
echo "============================================"

# ==========================================================================
# 1. Scan for hardcoded IPs/tokens/emails in Python source files
# ==========================================================================
section "Secret / Credential Scan (Python sources)"

# Patterns to detect (one per line for readability)
# We search tracked Python files only (excludes data/, .git/, etc.)
cd "$WORKSPACE" || exit 1

# Get list of tracked .py files
TRACKED_PY=$(git ls-files '*.py' 2>/dev/null)

if [ -z "$TRACKED_PY" ]; then
    warn "No tracked Python files found"
else
    # --- Hardcoded IP addresses (skip 127.0.0.1 and 0.0.0.0 as they are benign) ---
    IP_HITS=$(echo "$TRACKED_PY" | xargs grep -nP '\b(?!127\.0\.0\.1|0\.0\.0\.0)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b' 2>/dev/null \
        | grep -vP '(#.*\d+\.\d+\.\d+\.\d+|version|__version__|"""|\bv?\d+\.\d+\.\d+[.-])' \
        | grep -vP '(localhost|0\.0\.0\.0|127\.0\.0\.1|255\.255|\.0\.0\b)' || true)
    if [ -n "$IP_HITS" ]; then
        fail "Hardcoded IP addresses found in Python files:"
        echo "$IP_HITS" | head -10 | sed 's/^/         /'
        [ "$(echo "$IP_HITS" | wc -l)" -gt 10 ] && info "... and more (truncated)"
    else
        pass "No hardcoded IP addresses in Python sources"
    fi

    # --- API tokens / keys (sk-or-, sk-, ghp_, ghu_, AKIA, etc.) ---
    TOKEN_HITS=$(echo "$TRACKED_PY" | xargs grep -nP '(sk-or-v1-[a-zA-Z0-9]{20,}|sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|ghu_[a-zA-Z0-9]{36}|AKIA[0-9A-Z]{16}|xox[bpoa]-[a-zA-Z0-9-]+)' 2>/dev/null \
        | grep -v '# example\|# placeholder\|# fake\|# test' || true)
    if [ -n "$TOKEN_HITS" ]; then
        fail "Possible API tokens/keys found in Python files:"
        echo "$TOKEN_HITS" | head -10 | sed 's/^/         /'
    else
        pass "No API tokens/keys detected in Python sources"
    fi

    # --- Email addresses (skip generic/example ones) ---
    EMAIL_HITS=$(echo "$TRACKED_PY" | xargs grep -nPoH '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' 2>/dev/null \
        | grep -viP '(example\.com|test\.com|placeholder|noreply|users\.noreply\.github\.com)' || true)
    if [ -n "$EMAIL_HITS" ]; then
        fail "Personal email addresses found in Python files:"
        echo "$EMAIL_HITS" | head -10 | sed 's/^/         /'
    else
        pass "No personal email addresses in Python sources"
    fi

    # --- Telegram chat IDs / bot tokens ---
    TG_HITS=$(echo "$TRACKED_PY" | xargs grep -nP '(chat_id\s*=\s*["\x27]?\d{7,}|bot\d{8,}:AA)' 2>/dev/null || true)
    if [ -n "$TG_HITS" ]; then
        fail "Hardcoded Telegram chat IDs or bot tokens found:"
        echo "$TG_HITS" | head -10 | sed 's/^/         /'
    else
        pass "No hardcoded Telegram credentials in Python sources"
    fi
fi

# ==========================================================================
# 2. Validate LICENSE file exists
# ==========================================================================
section "License"

if [ -f "$WORKSPACE/LICENSE" ] || [ -f "$WORKSPACE/LICENSE.md" ] || [ -f "$WORKSPACE/LICENSE.txt" ]; then
    LICENSE_FILE=$(ls "$WORKSPACE"/LICENSE* 2>/dev/null | head -1)
    LICENSE_SIZE=$(wc -c < "$LICENSE_FILE")
    if [ "$LICENSE_SIZE" -gt 100 ]; then
        pass "LICENSE file exists ($LICENSE_FILE, ${LICENSE_SIZE} bytes)"
    else
        warn "LICENSE file exists but seems too small (${LICENSE_SIZE} bytes)"
    fi
else
    fail "No LICENSE file found in repository root"
fi

# ==========================================================================
# 3. Check .gitignore covers secrets dirs
# ==========================================================================
section ".gitignore Coverage"

GITIGNORE="$WORKSPACE/.gitignore"
if [ ! -f "$GITIGNORE" ]; then
    fail ".gitignore file not found"
else
    MISSING_PATTERNS=()

    # Required patterns
    for pattern in "data/" "*.env" "*.key" "*.secret" "*credentials*"; do
        if grep -qF "$pattern" "$GITIGNORE" 2>/dev/null; then
            pass ".gitignore covers: $pattern"
        else
            fail ".gitignore missing pattern: $pattern"
            MISSING_PATTERNS+=("$pattern")
        fi
    done

    # Bonus patterns (warn only)
    for pattern in "*.pem" "*.token" "monitoring/"; do
        if grep -qF "$pattern" "$GITIGNORE" 2>/dev/null; then
            pass ".gitignore covers: $pattern"
        else
            warn ".gitignore does not cover: $pattern (recommended)"
        fi
    done
fi

# ==========================================================================
# 4. Check for large binaries in git history (>5MB)
# ==========================================================================
section "Large Files in Git History"

# Use git rev-list + cat-file to find blobs > 5MB
LARGE_FILES=$(git -C "$WORKSPACE" rev-list --objects --all 2>/dev/null \
    | git -C "$WORKSPACE" cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' 2>/dev/null \
    | awk '/^blob/ && $2 > 5242880 {print $2, $3}' \
    | sort -rn | head -20)

if [ -n "$LARGE_FILES" ]; then
    warn "Large files (>5MB) found in git history:"
    echo "$LARGE_FILES" | while read -r size path; do
        SIZE_MB=$(echo "scale=1; $size / 1048576" | bc 2>/dev/null || echo "?")
        echo "         ${SIZE_MB}MB  $path"
    done
else
    pass "No files >5MB in git history"
fi

# ==========================================================================
# 5. Audit CLAUDE.md for internal-only references
# ==========================================================================
section "CLAUDE.md Internal Reference Audit"

# CLAUDE.md may live in workspace or one level up (OpenClaw root)
if [ -f "$WORKSPACE/CLAUDE.md" ]; then
    CLAUDEMD="$WORKSPACE/CLAUDE.md"
elif [ -f "$WORKSPACE/../CLAUDE.md" ]; then
    CLAUDEMD="$WORKSPACE/../CLAUDE.md"
else
    CLAUDEMD=""
fi

if [ -z "$CLAUDEMD" ]; then
    fail "CLAUDE.md not found"
else
    # Check for internal IPs (non-localhost)
    CLAUDE_IPS=$(grep -nP '\b(?!127\.0\.0\.1|0\.0\.0\.0)(\d{1,3}\.){3}\d{1,3}\b' "$CLAUDEMD" \
        | grep -vP '(localhost|version|v?\d+\.\d+\.\d+[.-]|0\.0\.0\.0|255\.)' || true)
    if [ -n "$CLAUDE_IPS" ]; then
        fail "CLAUDE.md contains internal IP addresses:"
        echo "$CLAUDE_IPS" | sed 's/^/         /'
    else
        pass "CLAUDE.md has no internal IP addresses"
    fi

    # Check for passwords / tokens
    # Match real tokens (long alphanumeric), not documentation placeholders like sk-or-v1-...
    CLAUDE_SECRETS=$(grep -niP '(password\s*[:=]\s*\S{8,}|sk-or-v1-[a-zA-Z0-9]{20,}|sk-[a-z0-9]{20,}|bot\d+:AA[a-zA-Z0-9_-]{30,})' "$CLAUDEMD" || true)
    if [ -n "$CLAUDE_SECRETS" ]; then
        fail "CLAUDE.md contains password/token references:"
        echo "$CLAUDE_SECRETS" | sed 's/^/         /'
    else
        pass "CLAUDE.md has no embedded passwords/tokens"
    fi

    # Check for private API endpoints
    CLAUDE_ENDPOINTS=$(grep -niP '(api\.mcporter\.io|internal\.|\.local:|private\.)' "$CLAUDEMD" || true)
    if [ -n "$CLAUDE_ENDPOINTS" ]; then
        warn "CLAUDE.md references possibly internal endpoints:"
        echo "$CLAUDE_ENDPOINTS" | sed 's/^/         /'
    else
        pass "CLAUDE.md has no internal API endpoints"
    fi

    # Check for personal identifiers (Telegram chat IDs, personal names with context)
    CLAUDE_PII=$(grep -nP 'chat_id\s+[`"'"'"']?\d{7,}' "$CLAUDEMD" || true)
    if [ -n "$CLAUDE_PII" ]; then
        warn "CLAUDE.md contains personal identifiers (chat IDs):"
        echo "$CLAUDE_PII" | sed 's/^/         /'
    else
        pass "CLAUDE.md has no hardcoded personal identifiers"
    fi
fi

# ==========================================================================
# 6. Summary
# ==========================================================================
echo ""
echo "============================================"
echo " RESULTS: $PASS passed, $FAIL failed, $WARN warnings"
echo " $DATE"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo " STATUS: NOT READY — fix $FAIL failure(s) before open-sourcing."
    exit 1
else
    echo ""
    if [ "$WARN" -gt 0 ]; then
        echo " STATUS: READY (with $WARN advisory warning(s))"
    else
        echo " STATUS: READY"
    fi
    exit 0
fi
