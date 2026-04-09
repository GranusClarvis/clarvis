#!/bin/bash
# =============================================================================
# Clarvis Daily Backup System
# =============================================================================
# Incremental backup with checksums, manifests, and point-in-time recovery.
#
# Usage:
#   ./backup_daily.sh              # Normal daily backup
#   ./backup_daily.sh --full       # Force full backup (no incremental)
#   ./backup_daily.sh --dry-run    # Show what would be backed up
#
# Backup structure:
#   ~/.openclaw/backups/daily/
#     ├── YYYY-MM-DD_HHMMSS/
#     │   ├── manifest.json        # File list with checksums
#     │   ├── meta.json            # Backup metadata
#     │   ├── data/                # Incremental data files
#     │   ├── memory/              # Memory state
#     │   ├── scripts/             # Automation scripts
#     │   ├── config/              # Configuration
#     │   ├── docs/                # Root .md docs (SOUL, SELF, etc.)
#     │   └── git-bundle.bundle    # Git repo bundle
#     ├── latest -> YYYY-MM-DD_HHMMSS  (symlink)
#     └── checksums.log            # Running checksum verification log
# =============================================================================

set -euo pipefail
export CLARVIS_WORKSPACE="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"
source "$CLARVIS_WORKSPACE"/scripts/cron/cron_env.sh

# --- Configuration ---
WORKSPACE="$HOME/.openclaw/workspace"
BACKUP_ROOT="$HOME/.openclaw/backups/daily"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
LATEST_LINK="$BACKUP_ROOT/latest"
CHECKSUM_LOG="$BACKUP_ROOT/checksums.log"
MAX_BACKUPS=30          # Keep 30 daily backups (~1 month)
FORCE_FULL=false
DRY_RUN=false

# --- Parse args ---
for arg in "$@"; do
  case "$arg" in
    --full)    FORCE_FULL=true ;;
    --dry-run) DRY_RUN=true ;;
    *)         echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

# --- Helpers ---
log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

sha256_file() {
  sha256sum "$1" 2>/dev/null | cut -d' ' -f1
}

# --- Determine backup type ---
PREV_MANIFEST=""
if [ -L "$LATEST_LINK" ] && [ -f "$LATEST_LINK/manifest.json" ] && [ "$FORCE_FULL" = false ]; then
  PREV_MANIFEST="$LATEST_LINK/manifest.json"
  BACKUP_TYPE="incremental"
else
  BACKUP_TYPE="full"
fi

log "Starting $BACKUP_TYPE backup: $TIMESTAMP"

# --- Collect all files to back up ---
# These are the critical paths
BACKUP_SOURCES=(
  # ClarvisDB - the crown jewel
  "data/clarvisdb"
  "data/clarvisdb-local"
  # State files
  "data/capability_history.json"
  "data/self_model.json"
  "data/working_memory.json"
  "data/working_memory_state.json"
  "data/self_report_metrics.json"
  "data/meta_cognition.json"
  "data/phi_history.json"
  "data/task-graph.json"
  "data/evolution-log.jsonl"
  # Subdirectories with critical state
  "data/hebbian"
  "data/synaptic"
  "data/attention"
  "data/benchmarks"
  "data/calibration"
  "data/evolution"
  "data/metrics"
  "data/plans"
  "data/reasoning_chains"
  "data/reflections"
  "data/sessions"
  "data/tool_outputs"
  # Memory state
  "memory"
  # Scripts (the brain)
  "scripts"
  # Configuration
  "config"
  # Root docs (identity, soul, self-awareness)
  "AGENTS.md"
  "BOOT.md"
  "HEARTBEAT.md"
  "IDENTITY.md"
  "MEMORY.md"
  "ROADMAP.md"
  "SELF.md"
  "SOUL.md"
  "TOOLS.md"
  ".gitignore"
)

# --- OpenClaw gateway config (outside workspace) ---
OPENCLAW_CONFIG_FILES=(
  "$HOME/.openclaw/openclaw.json"
  "$HOME/.openclaw/agents/main/agent/auth.json"
  "$HOME/.openclaw/workspace/data/budget_config.json"
)

# --- Sensitive files backed up separately (encrypted) ---
ENCRYPTED_FILES=(
  "$HOME/.openclaw/workspace/.env"
)

# --- Build current manifest (path -> sha256) ---
declare -A CURRENT_FILES
declare -A PREV_FILES
FILE_COUNT=0
CHANGED_COUNT=0

build_manifest() {
  local base_path="$1"
  local full_path="$WORKSPACE/$base_path"

  if [ -f "$full_path" ]; then
    local hash
    hash=$(sha256_file "$full_path")
    CURRENT_FILES["$base_path"]="$hash"
    ((FILE_COUNT++)) || true
  elif [ -d "$full_path" ]; then
    while IFS= read -r -d '' file; do
      local rel_path="${file#$WORKSPACE/}"
      local hash
      hash=$(sha256_file "$file")
      CURRENT_FILES["$rel_path"]="$hash"
      ((FILE_COUNT++)) || true
    done < <(find "$full_path" -type f -print0 2>/dev/null)
  fi
}

log "Scanning files..."
for src in "${BACKUP_SOURCES[@]}"; do
  build_manifest "$src"
done
log "Found $FILE_COUNT files to evaluate"

# --- Load previous manifest for incremental ---
if [ -n "$PREV_MANIFEST" ]; then
  while IFS='|' read -r path hash; do
    PREV_FILES["$path"]="$hash"
  done < <(python3 -c "
import json, sys
with open('$PREV_MANIFEST') as f:
    m = json.load(f)
for entry in m.get('files', []):
    print(f\"{entry['path']}|{entry['sha256']}\")
" 2>/dev/null) || true
fi

# --- Determine which files changed ---
declare -A CHANGED_FILES
for path in "${!CURRENT_FILES[@]}"; do
  current_hash="${CURRENT_FILES[$path]}"
  prev_hash="${PREV_FILES[$path]:-}"

  if [ "$BACKUP_TYPE" = "full" ] || [ "$current_hash" != "$prev_hash" ]; then
    CHANGED_FILES["$path"]="$current_hash"
    ((CHANGED_COUNT++)) || true
  fi
done

log "$CHANGED_COUNT files changed since last backup"

# --- Dry run exit ---
if [ "$DRY_RUN" = true ]; then
  log "DRY RUN - would back up:"
  for path in "${!CHANGED_FILES[@]}"; do
    echo "  $path"
  done
  log "Total: $CHANGED_COUNT files"
  exit 0
fi

# --- Skip if nothing changed ---
if [ "$CHANGED_COUNT" -eq 0 ] && [ "$BACKUP_TYPE" = "incremental" ]; then
  log "No changes detected, skipping backup"
  echo "$TIMESTAMP no-change" >> "$CHECKSUM_LOG"
  exit 0
fi

# --- Create backup directory ---
mkdir -p "$BACKUP_DIR"

# --- Copy changed files (with SQLite WAL-safe backup) ---
log "Copying $CHANGED_COUNT files..."
for path in "${!CHANGED_FILES[@]}"; do
  dest="$BACKUP_DIR/$path"
  src="$WORKSPACE/$path"
  mkdir -p "$(dirname "$dest")"
  # Use SQLite backup API for database files to avoid WAL corruption
  if [[ "$src" == *.sqlite3 ]] || [[ "$src" == *.db ]]; then
    if sqlite3 "$src" ".backup '$dest'" 2>/dev/null; then
      touch -r "$src" "$dest" 2>/dev/null  # preserve mtime
    else
      log "WARNING: sqlite3 .backup failed for $path, falling back to cp"
      cp -p "$src" "$dest"
    fi
  else
    cp -p "$src" "$dest"
  fi
done

# --- Copy OpenClaw config files (outside workspace) ---
log "Copying OpenClaw config files..."
CONFIG_DEST="$BACKUP_DIR/openclaw-config"
mkdir -p "$CONFIG_DEST"
for cfg in "${OPENCLAW_CONFIG_FILES[@]}"; do
  if [ -f "$cfg" ]; then
    cp -p "$cfg" "$CONFIG_DEST/"
    log "  Backed up: $(basename "$cfg")"
  fi
done

# --- Encrypted backup of sensitive files ---
log "Backing up sensitive files (encrypted)..."
SENSITIVE_DEST="$BACKUP_DIR/encrypted"
mkdir -p "$SENSITIVE_DEST"
for sf in "${ENCRYPTED_FILES[@]}"; do
  if [ -f "$sf" ]; then
    # Use openssl enc with a key derived from the machine's host ID
    # This ensures only this machine can decrypt, without requiring a separate password
    ENCRYPT_KEY=$(cat /etc/machine-id 2>/dev/null || hostname)
    openssl enc -aes-256-cbc -pbkdf2 -salt \
      -in "$sf" \
      -out "$SENSITIVE_DEST/$(basename "$sf").enc" \
      -pass "pass:$ENCRYPT_KEY" 2>/dev/null && {
        log "  Encrypted: $(basename "$sf")"
      } || {
        log "  WARNING: encryption failed for $(basename "$sf"), skipping"
      }
  fi
done

# --- Create git bundle (full repo state in one file) ---
log "Creating git bundle..."
cd "$WORKSPACE"
git bundle create "$BACKUP_DIR/git-bundle.bundle" --all 2>/dev/null || {
  log "WARNING: git bundle failed, copying .git instead"
  # Fallback: tar the git dir
  tar czf "$BACKUP_DIR/git-repo.tar.gz" -C "$WORKSPACE" .git 2>/dev/null || true
}

# --- Offsite git push (weekly, on Sundays) ---
DOW=$(date +%u)  # 7 = Sunday
if [ "$DOW" -eq 7 ]; then
  log "Weekly offsite git push..."
  cd "$WORKSPACE"
  if git push origin main 2>/dev/null; then
    log "  Git push to origin succeeded"
  else
    log "  WARNING: git push to origin failed (will retry next Sunday)"
  fi
fi

# --- Write manifest ---
log "Writing manifest..."
MANIFEST_ENTRIES=""
for path in "${!CURRENT_FILES[@]}"; do
  hash="${CURRENT_FILES[$path]}"
  size=$(stat -c%s "$WORKSPACE/$path" 2>/dev/null || echo 0)
  if [ -n "$MANIFEST_ENTRIES" ]; then
    MANIFEST_ENTRIES="$MANIFEST_ENTRIES,"
  fi
  MANIFEST_ENTRIES="$MANIFEST_ENTRIES
    {\"path\": \"$path\", \"sha256\": \"$hash\", \"size\": $size}"
done

cat > "$BACKUP_DIR/manifest.json" << MANIFEST_EOF
{
  "timestamp": "$TIMESTAMP",
  "type": "$BACKUP_TYPE",
  "total_files": $FILE_COUNT,
  "changed_files": $CHANGED_COUNT,
  "previous_backup": "$(basename "$(readlink -f "$LATEST_LINK" 2>/dev/null || echo 'none')")",
  "files": [$MANIFEST_ENTRIES
  ]
}
MANIFEST_EOF

# --- Write metadata ---
BACKUP_SIZE=$(du -sb "$BACKUP_DIR" 2>/dev/null | cut -f1)
BACKUP_SIZE_HUMAN=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

# ClarvisDB stats
MEMORY_COUNT=0
EDGE_COUNT=0
if command -v python3 &>/dev/null; then
  MEMORY_COUNT=$(python3 -c "
import sqlite3, sys
try:
    conn = sqlite3.connect('$WORKSPACE/data/clarvisdb/chroma.sqlite3')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM embeddings')
    print(c.fetchone()[0])
    conn.close()
except: print(0)
" 2>/dev/null) || MEMORY_COUNT=0

  if [ -f "$WORKSPACE/data/clarvisdb/relationships.json" ]; then
    EDGE_COUNT=$(python3 -c "
import json
with open('$WORKSPACE/data/clarvisdb/relationships.json') as f:
    data = json.load(f)
print(len(data.get('edges', data if isinstance(data, list) else [])))
" 2>/dev/null) || EDGE_COUNT=0
  fi
fi

cat > "$BACKUP_DIR/meta.json" << META_EOF
{
  "timestamp": "$TIMESTAMP",
  "type": "$BACKUP_TYPE",
  "size_bytes": $BACKUP_SIZE,
  "size_human": "$BACKUP_SIZE_HUMAN",
  "total_files": $FILE_COUNT,
  "changed_files": $CHANGED_COUNT,
  "clarvisdb_memories": $MEMORY_COUNT,
  "clarvisdb_edges": $EDGE_COUNT,
  "git_commit": "$(git -C "$WORKSPACE" rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "git_branch": "$(git -C "$WORKSPACE" branch --show-current 2>/dev/null || echo 'unknown')",
  "hostname": "$(hostname)",
  "created_at": "$(date -Iseconds)"
}
META_EOF

# --- Update latest symlink ---
rm -f "$LATEST_LINK"
ln -s "$BACKUP_DIR" "$LATEST_LINK"

# --- Verify backup integrity ---
log "Verifying backup integrity..."
VERIFY_PASS=0
VERIFY_FAIL=0
for path in "${!CHANGED_FILES[@]}"; do
  # Skip self-referential log files (they change during backup, causing false mismatch)
  case "$path" in
    memory/cron/backup.log|memory/cron/backup_verify.log) ((VERIFY_PASS++)) || true; continue ;;
  esac
  expected="${CHANGED_FILES[$path]}"
  actual=$(sha256_file "$BACKUP_DIR/$path")
  if [ "$expected" = "$actual" ]; then
    ((VERIFY_PASS++)) || true
  else
    ((VERIFY_FAIL++)) || true
    log "CHECKSUM MISMATCH: $path (expected: $expected, got: $actual)"
  fi
done

# --- Log verification ---
echo "$TIMESTAMP $BACKUP_TYPE files=$CHANGED_COUNT verified=$VERIFY_PASS failed=$VERIFY_FAIL size=$BACKUP_SIZE_HUMAN" >> "$CHECKSUM_LOG"

if [ "$VERIFY_FAIL" -gt 0 ]; then
  log "WARNING: $VERIFY_FAIL files failed checksum verification!"
else
  log "All $VERIFY_PASS files verified OK"
fi

# --- Prune old backups ---
log "Pruning old backups (keeping $MAX_BACKUPS)..."
mapfile -t BACKUP_DIRS < <(ls -dt "$BACKUP_ROOT"/2*/ 2>/dev/null)
if [ "${#BACKUP_DIRS[@]}" -gt "$MAX_BACKUPS" ]; then
  for ((i=$MAX_BACKUPS; i<${#BACKUP_DIRS[@]}; i++)); do
    log "  Removing old backup: $(basename "${BACKUP_DIRS[$i]}")"
    rm -rf "${BACKUP_DIRS[$i]}"
  done
fi

# --- Summary ---
log "============================="
log "Backup complete: $BACKUP_TYPE"
log "Location: $BACKUP_DIR"
log "Size: $BACKUP_SIZE_HUMAN"
log "Files: $CHANGED_COUNT changed / $FILE_COUNT total"
log "ClarvisDB: $MEMORY_COUNT memories, $EDGE_COUNT edges"
log "Integrity: $VERIFY_PASS OK, $VERIFY_FAIL failed"
log "============================="
