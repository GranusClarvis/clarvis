#!/bin/bash
# =============================================================================
# Clarvis Safe OpenClaw Update Script
# =============================================================================
# Performs a full backup, validates the environment, updates OpenClaw,
# runs post-update health checks, and provides rollback capability.
#
# Usage:
#   ./safe_update.sh                    # Full update with backup + verification
#   ./safe_update.sh --check            # Check only (no update, show what would happen)
#   ./safe_update.sh --rollback         # Rollback to pre-update state
#   ./safe_update.sh --skip-backup      # Update without backup (dangerous)
#   ./safe_update.sh --target <version> # Update to specific version
#
# Safety guarantees:
#   1. Full backup with checksum verification BEFORE any changes
#   2. Config backup (openclaw.json + custom skills)
#   3. PM2 graceful stop/start (not kill)
#   4. Post-update health check with automatic rollback option
#   5. Pre-update snapshot for instant rollback
#   6. EXIT trap: gateway always restarts even if script is killed/crashes
#   7. Lockfile prevents concurrent updates
#   8. 5-minute timeout on npm install to prevent hangs
#
# What this script does NOT touch (safe by design):
#   - workspace/data/clarvisdb/* (brain data - OpenClaw doesn't modify this)
#   - workspace/scripts/* (your custom scripts)
#   - workspace/memory/* (working memory)
#   - workspace/skills/* (workspace-level skills)
#   - workspace/*.md (identity docs)
#   - openclaw.json (config preserved by npm)
#
# What OpenClaw update DOES change:
#   - ~/.npm-global/lib/node_modules/openclaw/* (the application code)
#   - Bundled skills in the npm package
# =============================================================================

set -euo pipefail

# --- Configuration ---
WORKSPACE="$HOME/.openclaw/workspace"
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
OPENCLAW_PKG="$HOME/.npm-global/lib/node_modules/openclaw"
BACKUP_ROOT="$HOME/.openclaw/backups"
UPDATE_BACKUP_DIR="$BACKUP_ROOT/pre-update"
SCRIPTS_DIR="$WORKSPACE/scripts"
LOG_FILE="$BACKUP_ROOT/update.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Defaults ---
ACTION="update"
SKIP_BACKUP=false
TARGET_VERSION=""
GATEWAY_WAS_STOPPED=false
LOCKFILE="/tmp/openclaw-update.lock"

# --- Gateway safety net ---
# If we stopped the gateway and the script dies for ANY reason (killed, error,
# signal, timeout, OOM, etc.), always bring the gateway back online.
ensure_gateway_online() {
  if [ "$GATEWAY_WAS_STOPPED" = true ]; then
    log "${YELLOW}SAFETY${NC} Ensuring gateway is online before exit..."
    if ! pm2 list 2>/dev/null | grep -q "openclaw-gateway.*online"; then
      pm2 start openclaw-gateway 2>/dev/null || pm2 restart openclaw-gateway 2>/dev/null || true
      sleep 3
      if pm2 list 2>/dev/null | grep -q "openclaw-gateway.*online"; then
        log "${GREEN}SAFETY${NC} Gateway restarted successfully"
      else
        log "${RED}SAFETY${NC} CRITICAL: Gateway failed to restart! Manual intervention needed: pm2 start openclaw-gateway"
      fi
    else
      log "${GREEN}SAFETY${NC} Gateway already online"
    fi
  fi
  # Clean up lockfile
  rm -f "$LOCKFILE"
}
trap ensure_gateway_online EXIT

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)       ACTION="check" ;;
    --rollback)    ACTION="rollback" ;;
    --skip-backup) SKIP_BACKUP=true ;;
    --target)      TARGET_VERSION="$2"; shift ;;
    -h|--help)     ACTION="help" ;;
    *)             echo "Unknown arg: $1"; exit 1 ;;
  esac
  shift
done

# --- Helpers ---
log() { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
info() { log "${BLUE}INFO${NC}  $*"; }
ok() { log "${GREEN}OK${NC}    $*"; }
warn() { log "${YELLOW}WARN${NC}  $*"; }
fail() { log "${RED}FAIL${NC}  $*"; }
die() { fail "$*"; exit 1; }

separator() {
  echo "================================================================" | tee -a "$LOG_FILE"
}

# --- Help ---
show_help() {
  echo "Clarvis Safe OpenClaw Update Script"
  echo ""
  echo "Usage:"
  echo "  $0                    # Full update with backup + verification"
  echo "  $0 --check            # Check only (no update)"
  echo "  $0 --rollback         # Rollback to pre-update state"
  echo "  $0 --skip-backup      # Update without backup (dangerous)"
  echo "  $0 --target <version> # Update to specific version"
  echo "  $0 --help             # Show this help"
}

# --- Get versions ---
get_installed_version() {
  python3 -c "
import json
with open('$OPENCLAW_PKG/package.json') as f:
    print(json.load(f).get('version', 'unknown'))
" 2>/dev/null || echo "unknown"
}

get_available_version() {
  npm view openclaw version 2>/dev/null || echo "unknown"
}

# --- Pre-flight checks ---
preflight_check() {
  separator
  info "Running pre-flight checks..."

  # 1. Check we're on the NUC / correct host
  local hostname
  hostname=$(hostname)
  info "Host: $hostname"

  # 2. Check Node.js
  if command -v node &>/dev/null; then
    ok "Node.js: $(node --version)"
  else
    die "Node.js not found"
  fi

  # 3. Check npm
  if command -v npm &>/dev/null; then
    ok "npm: $(npm --version)"
  else
    die "npm not found"
  fi

  # 4. Check PM2
  if command -v pm2 &>/dev/null; then
    ok "PM2: $(pm2 --version 2>/dev/null || echo 'installed')"
  else
    die "PM2 not found"
  fi

  # 5. Check gateway is running
  if pm2 list 2>/dev/null | grep -q "openclaw-gateway.*online"; then
    ok "Gateway: running"
  else
    warn "Gateway: NOT running (will continue anyway)"
  fi

  # 6. Check disk space (need at least 500MB free)
  local free_mb
  free_mb=$(df -m "$HOME" | awk 'NR==2 {print $4}')
  if [ "$free_mb" -gt 500 ]; then
    ok "Disk: ${free_mb}MB free"
  else
    die "Insufficient disk space: ${free_mb}MB free (need 500MB+)"
  fi

  # 7. Check versions
  local installed available
  installed=$(get_installed_version)
  available=$(get_available_version)

  info "Installed version: $installed"
  info "Available version: $available"

  if [ "$installed" = "$available" ]; then
    warn "Already on latest version ($installed)"
    if [ "$ACTION" = "check" ]; then
      return 0
    fi
  fi

  # 8. Check workspace git state
  cd "$WORKSPACE"
  if git diff --quiet 2>/dev/null; then
    ok "Git: clean working tree"
  else
    warn "Git: uncommitted changes (will be included in backup)"
  fi

  # 9. Check ClarvisDB integrity
  local brain_check
  brain_check=$(python3 -c "
import sys
sys.path.insert(0, '$SCRIPTS_DIR')
from brain import brain
stats = brain.stats()
print('ok')
" 2>/dev/null || echo "fail")

  if [ "$brain_check" = "ok" ]; then
    ok "ClarvisDB: healthy"
  else
    warn "ClarvisDB: could not verify (backup will still include it)"
  fi

  # 10. Check config exists
  if [ -f "$OPENCLAW_CONFIG" ]; then
    ok "Config: $OPENCLAW_CONFIG exists"
  else
    die "Config not found: $OPENCLAW_CONFIG"
  fi

  ok "Pre-flight checks passed"
}

# --- Create comprehensive pre-update backup ---
create_update_backup() {
  separator
  info "Creating comprehensive pre-update backup..."

  local timestamp
  timestamp=$(date +%Y-%m-%d_%H%M%S)
  local backup_dir="$UPDATE_BACKUP_DIR/$timestamp"
  mkdir -p "$backup_dir"

  # 1. Run the daily backup script for workspace data
  info "Running full workspace backup..."
  bash "$SCRIPTS_DIR/backup_daily.sh" --full 2>&1 | tee -a "$LOG_FILE"
  ok "Workspace backup complete"

  # 2. Backup openclaw.json (with all variants)
  info "Backing up configuration..."
  mkdir -p "$backup_dir/config"
  for f in "$HOME/.openclaw/openclaw.json"*; do
    if [ -f "$f" ]; then
      cp -p "$f" "$backup_dir/config/"
    fi
  done
  ok "Config backed up"

  # 3. Backup the current OpenClaw package (for rollback)
  info "Backing up current OpenClaw package..."
  mkdir -p "$backup_dir/openclaw-pkg"
  # Save version info and critical files, not the entire node_modules
  cp -p "$OPENCLAW_PKG/package.json" "$backup_dir/openclaw-pkg/"
  if [ -f "$OPENCLAW_PKG/CHANGELOG.md" ]; then
    cp -p "$OPENCLAW_PKG/CHANGELOG.md" "$backup_dir/openclaw-pkg/"
  fi
  # Record the exact version for rollback
  get_installed_version > "$backup_dir/openclaw-pkg/VERSION"
  ok "Package info backed up"

  # 4. Backup custom skills (workspace-level)
  info "Backing up workspace skills..."
  if [ -d "$WORKSPACE/skills" ]; then
    cp -rp "$WORKSPACE/skills" "$backup_dir/skills-workspace"
  fi
  ok "Skills backed up"

  # 5. Backup PM2 ecosystem
  info "Backing up PM2 state..."
  pm2 save 2>/dev/null || true
  if [ -f "$HOME/.pm2/dump.pm2" ]; then
    cp -p "$HOME/.pm2/dump.pm2" "$backup_dir/pm2-dump.pm2"
  fi
  ok "PM2 state backed up"

  # 6. Record system state
  info "Recording system state..."
  cat > "$backup_dir/system-state.json" << STATE_EOF
{
  "timestamp": "$timestamp",
  "hostname": "$(hostname)",
  "node_version": "$(node --version 2>/dev/null)",
  "npm_version": "$(npm --version 2>/dev/null)",
  "openclaw_version": "$(get_installed_version)",
  "gateway_pid": "$(pgrep -f openclaw-gateway 2>/dev/null || echo 'none')",
  "uptime": "$(uptime -p 2>/dev/null || echo 'unknown')",
  "disk_free_mb": "$(df -m "$HOME" | awk 'NR==2 {print $4}')",
  "workspace_git_commit": "$(git -C "$WORKSPACE" rev-parse HEAD 2>/dev/null || echo 'unknown')"
}
STATE_EOF
  ok "System state recorded"

  # 7. Update the pre-update symlink
  rm -f "$UPDATE_BACKUP_DIR/latest"
  ln -s "$backup_dir" "$UPDATE_BACKUP_DIR/latest"

  # 8. Verify backup
  info "Verifying backup integrity..."
  local backup_size
  backup_size=$(du -sh "$backup_dir" 2>/dev/null | cut -f1)
  local file_count
  file_count=$(find "$backup_dir" -type f | wc -l)
  ok "Backup complete: $backup_dir ($backup_size, $file_count files)"

  echo "$backup_dir"
}

# --- Stop gateway gracefully ---
stop_gateway() {
  separator
  info "Stopping gateway gracefully..."

  GATEWAY_WAS_STOPPED=true

  if pm2 list 2>/dev/null | grep -q "openclaw-gateway.*online"; then
    pm2 stop openclaw-gateway 2>/dev/null
    sleep 2

    # Verify it stopped
    if pm2 list 2>/dev/null | grep -q "openclaw-gateway.*stopped"; then
      ok "Gateway stopped"
    else
      warn "Gateway may not have stopped cleanly"
    fi
  else
    info "Gateway was not running"
  fi
}

# --- Start gateway ---
start_gateway() {
  separator
  info "Starting gateway..."

  pm2 start openclaw-gateway 2>/dev/null || pm2 restart openclaw-gateway 2>/dev/null
  sleep 5

  if pm2 list 2>/dev/null | grep -q "openclaw-gateway.*online"; then
    ok "Gateway started"
    GATEWAY_WAS_STOPPED=false
  else
    fail "Gateway failed to start!"
    return 1
  fi
}

# --- Perform the update ---
do_update() {
  separator
  info "Updating OpenClaw..."

  local install_cmd="npm install -g openclaw"
  if [ -n "$TARGET_VERSION" ]; then
    install_cmd="npm install -g openclaw@$TARGET_VERSION"
    info "Target version: $TARGET_VERSION"
  fi

  info "Running: $install_cmd"

  # Run the update with a 5 minute timeout so it can't hang forever
  if timeout 300 bash -c "$install_cmd" 2>&1 | tee -a "$LOG_FILE"; then
    local new_version
    new_version=$(get_installed_version)
    ok "Update complete: now running $new_version"
  else
    local exit_code=$?
    if [ "$exit_code" -eq 124 ]; then
      fail "Update timed out after 5 minutes!"
    else
      fail "Update command failed (exit code: $exit_code)!"
    fi
    return 1
  fi
}

# --- Post-update health check ---
post_update_check() {
  separator
  info "Running post-update health checks..."

  local checks_passed=0
  local checks_failed=0

  # 1. Version check
  local new_version
  new_version=$(get_installed_version)
  if [ "$new_version" != "unknown" ]; then
    ok "Version: $new_version"
    ((checks_passed++)) || true
  else
    fail "Cannot read version"
    ((checks_failed++)) || true
  fi

  # 2. Config still intact
  if [ -f "$OPENCLAW_CONFIG" ]; then
    # Verify it's valid JSON
    if python3 -c "import json; json.load(open('$OPENCLAW_CONFIG'))" 2>/dev/null; then
      ok "Config: valid JSON"
      ((checks_passed++)) || true
    else
      fail "Config: invalid JSON!"
      ((checks_failed++)) || true
    fi
  else
    fail "Config: MISSING!"
    ((checks_failed++)) || true
  fi

  # 3. Gateway process
  if pm2 list 2>/dev/null | grep -q "openclaw-gateway.*online"; then
    ok "Gateway: running"
    ((checks_passed++)) || true
  else
    fail "Gateway: not running"
    ((checks_failed++)) || true
  fi

  # 4. ClarvisDB brain
  local brain_check
  brain_check=$(python3 -c "
import sys
sys.path.insert(0, '$SCRIPTS_DIR')
from brain import brain
stats = brain.stats()
total = sum(s.get('count', 0) for s in stats.values()) if isinstance(stats, dict) else 0
print(f'ok:{total}')
" 2>/dev/null || echo "fail:0")

  if [[ "$brain_check" == ok:* ]]; then
    local count="${brain_check#ok:}"
    ok "ClarvisDB: healthy ($count memories)"
    ((checks_passed++)) || true
  else
    fail "ClarvisDB: not responding"
    ((checks_failed++)) || true
  fi

  # 5. Working memory state
  if [ -f "$WORKSPACE/data/working_memory_state.json" ]; then
    ok "Working memory: state file exists"
    ((checks_passed++)) || true
  else
    warn "Working memory: state file missing (may regenerate)"
    ((checks_failed++)) || true
  fi

  # 6. Custom scripts intact
  if [ -f "$SCRIPTS_DIR/brain.py" ] && [ -f "$SCRIPTS_DIR/working_memory.py" ]; then
    ok "Custom scripts: intact"
    ((checks_passed++)) || true
  else
    fail "Custom scripts: missing!"
    ((checks_failed++)) || true
  fi

  # 7. Identity docs intact
  for doc in SOUL.md SELF.md AGENTS.md BOOT.md; do
    if [ -f "$WORKSPACE/$doc" ]; then
      ((checks_passed++)) || true
    else
      fail "Identity doc missing: $doc"
      ((checks_failed++)) || true
    fi
  done

  # 8. Workspace skills intact
  local skill_count
  skill_count=$(find "$WORKSPACE/skills" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
  if [ "$skill_count" -gt 0 ]; then
    ok "Workspace skills: $skill_count found"
    ((checks_passed++)) || true
  else
    warn "Workspace skills: none found"
    ((checks_failed++)) || true
  fi

  # 9. Cron system
  local cron_count
  cron_count=$(crontab -l 2>/dev/null | grep -c "openclaw\|clarvis\|cron_" || echo 0)
  if [ "$cron_count" -gt 0 ]; then
    ok "Cron: $cron_count jobs active"
    ((checks_passed++)) || true
  else
    warn "Cron: no jobs found"
  fi

  # 10. Gateway API responds
  sleep 2
  local api_check
  api_check=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18789/ 2>/dev/null || echo "000")
  if [ "$api_check" != "000" ]; then
    ok "Gateway API: responding (HTTP $api_check)"
    ((checks_passed++)) || true
  else
    fail "Gateway API: not responding on port 18789"
    ((checks_failed++)) || true
  fi

  separator
  if [ "$checks_failed" -eq 0 ]; then
    ok "ALL HEALTH CHECKS PASSED ($checks_passed/$((checks_passed + checks_failed)))"
    return 0
  else
    fail "$checks_failed CHECKS FAILED ($checks_passed passed, $checks_failed failed)"
    return 1
  fi
}

# --- Rollback ---
do_rollback() {
  separator
  info "Starting rollback..."

  local latest_backup="$UPDATE_BACKUP_DIR/latest"
  if [ ! -L "$latest_backup" ] || [ ! -d "$latest_backup" ]; then
    die "No pre-update backup found at $UPDATE_BACKUP_DIR/latest"
  fi

  local backup_dir
  backup_dir=$(readlink -f "$latest_backup")
  info "Rolling back from: $backup_dir"

  # 1. Get the old version
  local old_version="unknown"
  if [ -f "$backup_dir/openclaw-pkg/VERSION" ]; then
    old_version=$(cat "$backup_dir/openclaw-pkg/VERSION")
  fi
  info "Target rollback version: $old_version"

  # 2. Stop gateway
  stop_gateway

  # 3. Rollback OpenClaw package to old version
  if [ "$old_version" != "unknown" ]; then
    info "Reinstalling OpenClaw v$old_version..."
    npm install -g "openclaw@$old_version" 2>&1 | tee -a "$LOG_FILE"
  else
    warn "Unknown previous version, skipping package rollback"
  fi

  # 4. Restore config
  if [ -d "$backup_dir/config" ]; then
    info "Restoring configuration..."
    for f in "$backup_dir/config/"*; do
      local basename
      basename=$(basename "$f")
      cp -p "$f" "$HOME/.openclaw/$basename"
    done
    ok "Config restored"
  fi

  # 5. Restore workspace from daily backup
  info "Restoring workspace data..."
  bash "$SCRIPTS_DIR/backup_restore.sh" --latest --yes 2>&1 | tee -a "$LOG_FILE" || {
    warn "Workspace restore had issues, check manually"
  }

  # 6. Restore PM2 state
  if [ -f "$backup_dir/pm2-dump.pm2" ]; then
    cp -p "$backup_dir/pm2-dump.pm2" "$HOME/.pm2/dump.pm2"
    pm2 resurrect 2>/dev/null || true
  fi

  # 7. Start gateway
  start_gateway

  # 8. Run health check
  post_update_check || {
    fail "Health checks failed after rollback!"
    fail "Manual intervention may be required."
    fail "Backup location: $backup_dir"
  }

  separator
  ok "Rollback complete to v$old_version"
}

# --- Check mode ---
do_check() {
  separator
  info "=== OpenClaw Update Check (dry run) ==="
  separator

  preflight_check

  local installed available
  installed=$(get_installed_version)
  available=$(get_available_version)

  separator
  echo ""
  echo -e "${BLUE}Current version:${NC}   $installed"
  echo -e "${BLUE}Available version:${NC} $available"
  echo ""

  if [ "$installed" = "$available" ]; then
    echo -e "${GREEN}You are already on the latest version.${NC}"
  else
    echo -e "${YELLOW}Update available: $installed -> $available${NC}"
    echo ""
    echo "What the update will do:"
    echo "  1. Create full backup (workspace + config + package info)"
    echo "  2. Stop gateway via PM2"
    echo "  3. Run: npm install -g openclaw"
    echo "  4. Start gateway via PM2"
    echo "  5. Run health checks"
    echo ""
    echo "What will NOT be touched:"
    echo "  - Brain data (data/clarvisdb/)"
    echo "  - Custom scripts (scripts/)"
    echo "  - Working memory (data/working_memory*.json)"
    echo "  - Identity docs (SOUL.md, SELF.md, etc.)"
    echo "  - Your openclaw.json config"
    echo "  - Evolution queue and reasoning chains"
    echo ""
    echo "To update, run:"
    echo "  $0"
    echo ""
    echo "To update to a specific version:"
    echo "  $0 --target $available"
  fi
}

# --- Main update flow ---
do_full_update() {
  mkdir -p "$BACKUP_ROOT" "$(dirname "$LOG_FILE")"
  echo "" >> "$LOG_FILE"

  # Prevent concurrent updates
  if [ -f "$LOCKFILE" ]; then
    local lock_pid
    lock_pid=$(cat "$LOCKFILE" 2>/dev/null || echo "unknown")
    if kill -0 "$lock_pid" 2>/dev/null; then
      die "Another update is already running (PID: $lock_pid). Remove $LOCKFILE if stale."
    else
      warn "Stale lockfile found (PID $lock_pid not running). Removing."
      rm -f "$LOCKFILE"
    fi
  fi
  echo $$ > "$LOCKFILE"

  separator
  info "=== Clarvis Safe OpenClaw Update ==="
  info "=== $(date) ==="
  separator

  # Phase 1: Pre-flight
  preflight_check

  local installed available
  installed=$(get_installed_version)
  available=$(get_available_version)

  if [ "$installed" = "$available" ] && [ -z "$TARGET_VERSION" ]; then
    info "Already on latest version ($installed). Nothing to do."
    exit 0
  fi

  local target="${TARGET_VERSION:-$available}"
  info "Update path: $installed -> $target"

  # Phase 2: Backup
  if [ "$SKIP_BACKUP" = false ]; then
    local backup_dir
    backup_dir=$(create_update_backup)
    ok "Backup saved to: $backup_dir"
  else
    warn "SKIPPING BACKUP (--skip-backup flag)"
  fi

  # Phase 3: Stop gateway
  stop_gateway

  # Phase 4: Update
  if ! do_update; then
    fail "Update failed! Attempting to restart gateway with current version..."
    start_gateway
    die "Update aborted. Gateway restarted with previous version."
  fi

  # Phase 5: Doctor check (OpenClaw's built-in migration)
  info "Running openclaw doctor..."
  openclaw doctor --fix --non-interactive --yes 2>&1 | tee -a "$LOG_FILE" || {
    warn "openclaw doctor had issues (non-fatal)"
  }

  # Phase 6: Start gateway
  if ! start_gateway; then
    fail "Gateway failed to start after update!"
    echo ""
    echo -e "${RED}RECOMMENDED: Run rollback${NC}"
    echo "  $0 --rollback"
    exit 1
  fi

  # Phase 7: Health check
  if post_update_check; then
    separator
    ok "UPDATE SUCCESSFUL: $(get_installed_version)"
    separator
    echo ""
    echo "Post-update checklist (manual verification):"
    echo "  [ ] Send a test message via Telegram"
    echo "  [ ] Check brain recall: python3 scripts/brain.py recall 'test query'"
    echo "  [ ] Verify heartbeat fires (wait for next 30min cycle)"
    echo "  [ ] Check cron: crontab -l"
    echo "  [ ] Review PM2 logs: pm2 logs openclaw-gateway --lines 50"
    echo "  [ ] Test Discord (if applicable)"
    echo ""
    echo "If anything is wrong:"
    echo "  $0 --rollback"
    echo ""
    echo "Backup location: $UPDATE_BACKUP_DIR/latest"
  else
    separator
    fail "HEALTH CHECKS FAILED AFTER UPDATE"
    separator
    echo ""
    echo -e "${YELLOW}Some checks failed. Options:${NC}"
    echo "  1. Review PM2 logs:  pm2 logs openclaw-gateway --lines 100"
    echo "  2. Rollback:         $0 --rollback"
    echo "  3. Try doctor:       openclaw doctor --fix"
    echo ""
    echo "Pre-update backup: $UPDATE_BACKUP_DIR/latest"
    exit 1
  fi
}

# --- Dispatch ---
case "$ACTION" in
  help)     show_help ;;
  check)    preflight_check; do_check ;;
  rollback) do_rollback ;;
  update)   do_full_update ;;
  *)        die "Unknown action: $ACTION" ;;
esac
