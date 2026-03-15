#!/bin/bash
# =============================================================================
# Clarvis Backup Restore / Point-in-Time Recovery
# =============================================================================
# Restores from a specific backup or the latest backup.
#
# Usage:
#   ./backup_restore.sh                       # List available backups
#   ./backup_restore.sh --latest              # Restore from latest
#   ./backup_restore.sh --date 2026-02-21     # Restore closest to date
#   ./backup_restore.sh --backup <name>       # Restore specific backup
#   ./backup_restore.sh --file <path>         # Restore single file from latest
#   ./backup_restore.sh --dry-run --latest    # Show what would be restored
#
# Safety:
#   - Creates a pre-restore snapshot before overwriting anything
#   - Verifies checksums after restore
#   - Never touches git history (bundle restore is separate)
# =============================================================================

set -euo pipefail

WORKSPACE="$HOME/.openclaw/workspace"
BACKUP_ROOT="$HOME/.openclaw/backups/daily"
PRE_RESTORE_DIR="$HOME/.openclaw/backups/pre-restore"

# --- Defaults ---
ACTION="list"
TARGET_BACKUP=""
TARGET_DATE=""
TARGET_FILE=""
DRY_RUN=false
SKIP_CONFIRM=false

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --latest)     ACTION="restore"; TARGET_BACKUP="latest" ;;
    --date)       ACTION="restore"; TARGET_DATE="$2"; shift ;;
    --backup)     ACTION="restore"; TARGET_BACKUP="$2"; shift ;;
    --file)       ACTION="restore-file"; TARGET_FILE="$2"; shift ;;
    --dry-run)    DRY_RUN=true ;;
    --yes|-y)     SKIP_CONFIRM=true ;;
    --git)        ACTION="restore-git" ;;
    *)            echo "Unknown arg: $1"; exit 1 ;;
  esac
  shift
done

log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

# --- List available backups ---
list_backups() {
  echo "Available backups:"
  echo "===================="
  local i=0
  # shellcheck disable=SC2012,SC2045  # backup dirs are date-named, no whitespace risk; need mtime sort
  for dir in $(ls -dt "$BACKUP_ROOT"/2*/ 2>/dev/null); do
    local name
    name=$(basename "$dir")
    local meta="$dir/meta.json"
    if [ -f "$meta" ]; then
      local size type memories
      size=$(python3 -c "import json; print(json.load(open('$meta'))['size_human'])" 2>/dev/null || echo "?")
      type=$(python3 -c "import json; print(json.load(open('$meta'))['type'])" 2>/dev/null || echo "?")
      memories=$(python3 -c "import json; print(json.load(open('$meta'))['clarvisdb_memories'])" 2>/dev/null || echo "?")
      printf "  [%2d] %-24s  %s  %-12s  %s memories\n" "$i" "$name" "$size" "$type" "$memories"
    else
      printf "  [%2d] %-24s  (no metadata)\n" "$i" "$name"
    fi
    ((i++)) || true
  done
  echo ""
  echo "Latest: $(basename "$(readlink -f "$BACKUP_ROOT/latest" 2>/dev/null || echo 'none')")"
  echo ""
  echo "Usage:"
  echo "  $0 --latest              # Restore most recent"
  echo "  $0 --date 2026-02-21     # Restore closest to date"
  echo "  $0 --backup <name>       # Restore specific backup"
  echo "  $0 --file <rel-path>     # Restore single file"
}

# --- Resolve backup directory ---
resolve_backup() {
  if [ "$TARGET_BACKUP" = "latest" ]; then
    if [ -L "$BACKUP_ROOT/latest" ]; then
      RESOLVED=$(readlink -f "$BACKUP_ROOT/latest")
    else
      RESOLVED=$(ls -dt "$BACKUP_ROOT"/2*/ 2>/dev/null | head -1)
    fi
  elif [ -n "$TARGET_DATE" ]; then
    # Find closest backup to the given date
    # shellcheck disable=SC2012,SC2010  # backup dirs are date-named, grep on dir names is safe
    RESOLVED=$(ls -dt "$BACKUP_ROOT"/2*/ 2>/dev/null | grep "$TARGET_DATE" | head -1)
    if [ -z "$RESOLVED" ]; then
      # Fall back to closest before the date
      RESOLVED=$(ls -dt "$BACKUP_ROOT"/2*/ 2>/dev/null | while read -r d; do
        bname=$(basename "$d")
        if [[ "$bname" < "$TARGET_DATE" ]] || [[ "$bname" == "$TARGET_DATE"* ]]; then
          echo "$d"
          break
        fi
      done)
    fi
  elif [ -n "$TARGET_BACKUP" ]; then
    RESOLVED="$BACKUP_ROOT/$TARGET_BACKUP"
  fi

  if [ -z "${RESOLVED:-}" ] || [ ! -d "${RESOLVED:-}" ]; then
    die "Could not resolve backup: ${TARGET_BACKUP:-$TARGET_DATE}"
  fi

  echo "$RESOLVED"
}

# --- Pre-restore safety snapshot ---
create_pre_restore_snapshot() {
  local snap_dir
  snap_dir="$PRE_RESTORE_DIR/$(date +%Y-%m-%d_%H%M%S)"
  mkdir -p "$snap_dir"
  log "Creating pre-restore snapshot: $snap_dir"

  # Snapshot current critical state
  for path in data/clarvisdb data/clarvisdb-local data/working_memory.json \
              data/working_memory_state.json data/self_model.json \
              data/capability_history.json data/evolution-log.jsonl \
              memory/evolution/QUEUE.md; do
    local full="$WORKSPACE/$path"
    if [ -e "$full" ]; then
      mkdir -p "$snap_dir/$(dirname "$path")"
      cp -rp "$full" "$snap_dir/$path"
    fi
  done

  # Git state
  cd "$WORKSPACE"
  git stash --include-untracked -m "pre-restore-$(date +%s)" 2>/dev/null || true

  echo "$snap_dir"
}

# --- Restore from backup ---
do_restore() {
  local backup_dir
  backup_dir=$(resolve_backup)
  local backup_name
  backup_name=$(basename "$backup_dir")

  log "Restore target: $backup_name"

  # Show what's in this backup
  if [ -f "$backup_dir/meta.json" ]; then
    log "Backup metadata:"
    python3 -c "
import json
with open('$backup_dir/meta.json') as f:
    m = json.load(f)
print(f\"  Type:     {m['type']}\")
print(f\"  Size:     {m['size_human']}\")
print(f\"  Files:    {m['changed_files']} changed / {m['total_files']} total\")
print(f\"  Memories: {m['clarvisdb_memories']}\")
print(f\"  Edges:    {m['clarvisdb_edges']}\")
print(f\"  Commit:   {m['git_commit'][:8]}\")
print(f\"  Created:  {m['created_at']}\")
" 2>/dev/null || true
  fi

  # Count files to restore
  local file_count
  file_count=$(find "$backup_dir" -type f ! -name 'manifest.json' ! -name 'meta.json' ! -name '*.bundle' ! -name '*.tar.gz' | wc -l)
  log "Files to restore: $file_count"

  if [ "$DRY_RUN" = true ]; then
    log "DRY RUN - would restore from: $backup_dir"
    find "$backup_dir" -type f ! -name 'manifest.json' ! -name 'meta.json' ! -name '*.bundle' ! -name '*.tar.gz' | while read -r f; do
      echo "  ${f#$backup_dir/}"
    done
    return
  fi

  # Confirmation
  if [ "$SKIP_CONFIRM" = false ]; then
    echo ""
    echo "This will overwrite current workspace files with backup: $backup_name"
    read -p "Continue? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || { log "Aborted."; exit 0; }
  fi

  # Pre-restore snapshot
  local snap
  snap=$(create_pre_restore_snapshot)
  log "Pre-restore snapshot saved to: $snap"

  # Restore files
  log "Restoring files..."
  local restored=0
  local errors=0

  find "$backup_dir" -type f ! -name 'manifest.json' ! -name 'meta.json' ! -name '*.bundle' ! -name '*.tar.gz' -print0 | while IFS= read -r -d '' file; do
    local rel_path="${file#$backup_dir/}"
    local dest="$WORKSPACE/$rel_path"
    mkdir -p "$(dirname "$dest")"
    if cp -p "$file" "$dest" 2>/dev/null; then
      ((restored++)) || true
    else
      log "ERROR restoring: $rel_path"
      ((errors++)) || true
    fi
  done

  # Verify restored files against manifest
  if [ -f "$backup_dir/manifest.json" ]; then
    log "Verifying restored files..."
    python3 -c "
import json, hashlib, sys

with open('$backup_dir/manifest.json') as f:
    manifest = json.load(f)

ok = fail = 0
for entry in manifest.get('files', []):
    path = '$WORKSPACE/' + entry['path']
    expected = entry['sha256']
    try:
        with open(path, 'rb') as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
        if actual == expected:
            ok += 1
        else:
            print(f'MISMATCH: {entry[\"path\"]}')
            fail += 1
    except FileNotFoundError:
        # File might be from an incremental that didn't include it
        pass

print(f'Verified: {ok} OK, {fail} failed')
sys.exit(1 if fail > 0 else 0)
" 2>/dev/null && log "Verification passed" || log "WARNING: Some files failed verification"
  fi

  log "Restore complete from: $backup_name"
  log "Pre-restore snapshot at: $snap"
  log ""
  log "If something went wrong, run:"
  log "  cp -r $snap/* $WORKSPACE/"
}

# --- Restore single file ---
do_restore_file() {
  if [ -z "$TARGET_FILE" ]; then
    die "No file specified. Use --file <relative-path>"
  fi

  # Search for the file across backups (newest first)
  log "Searching for: $TARGET_FILE"
  # shellcheck disable=SC2012,SC2045  # backup dirs are date-named, no whitespace risk; need mtime sort
  for dir in $(ls -dt "$BACKUP_ROOT"/2*/ 2>/dev/null); do
    local candidate="$dir/$TARGET_FILE"
    if [ -f "$candidate" ]; then
      local backup_name
      backup_name=$(basename "$dir")
      local hash
      hash=$(sha256sum "$candidate" | cut -d' ' -f1)
      log "Found in backup: $backup_name (sha256: ${hash:0:16}...)"

      if [ "$DRY_RUN" = true ]; then
        log "DRY RUN - would restore: $TARGET_FILE from $backup_name"
        return
      fi

      # Backup current version
      local dest="$WORKSPACE/$TARGET_FILE"
      if [ -f "$dest" ]; then
        cp -p "$dest" "${dest}.pre-restore" 2>/dev/null || true
        log "Current version saved as: ${TARGET_FILE}.pre-restore"
      fi

      mkdir -p "$(dirname "$dest")"
      cp -p "$candidate" "$dest"
      log "Restored: $TARGET_FILE from $backup_name"
      return
    fi
  done

  die "File not found in any backup: $TARGET_FILE"
}

# --- Restore git from bundle ---
do_restore_git() {
  local backup_dir
  backup_dir=$(resolve_backup)
  local bundle="$backup_dir/git-bundle.bundle"

  if [ ! -f "$bundle" ]; then
    die "No git bundle found in: $(basename "$backup_dir")"
  fi

  log "Verifying git bundle..."
  git bundle verify "$bundle" || die "Bundle verification failed"

  if [ "$DRY_RUN" = true ]; then
    log "DRY RUN - would restore git from bundle in: $(basename "$backup_dir")"
    git bundle list-heads "$bundle"
    return
  fi

  log "Restoring git repository from bundle..."
  cd "$WORKSPACE"
  git fetch "$bundle" --all 2>/dev/null || die "Failed to fetch from bundle"
  log "Git history restored. Use 'git log' to verify."
}

# --- Main ---
case "$ACTION" in
  list)         list_backups ;;
  restore)      do_restore ;;
  restore-file) do_restore_file ;;
  restore-git)  do_restore_git ;;
  *)            die "Unknown action: $ACTION" ;;
esac
