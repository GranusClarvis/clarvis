#!/bin/bash
# =============================================================================
# Clarvis Backup Verification
# =============================================================================
# Verifies backup integrity, checks for data drift, and reports health.
#
# Usage:
#   ./backup_verify.sh              # Verify latest backup
#   ./backup_verify.sh --all        # Verify all backups
#   ./backup_verify.sh --backup <n> # Verify specific backup
#   ./backup_verify.sh --compare    # Compare latest backup to live state
# =============================================================================

set -euo pipefail
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

WORKSPACE="$HOME/.openclaw/workspace"
BACKUP_ROOT="$HOME/.openclaw/backups/daily"
ACTION="latest"

for arg in "$@"; do
  case "$arg" in
    --all)     ACTION="all" ;;
    --compare) ACTION="compare" ;;
    --backup)  ACTION="specific"; TARGET="$2"; shift ;;
  esac
done

log() { echo "[$(date '+%H:%M:%S')] $*"; }
PASS=0; FAIL=0; WARN=0

verify_backup() {
  local backup_dir="$1"
  local name
  name=$(basename "$backup_dir")
  local manifest="$backup_dir/manifest.json"
  local meta="$backup_dir/meta.json"

  echo "--- Verifying: $name ---"

  # Check manifest exists
  if [ ! -f "$manifest" ]; then
    echo "  FAIL: No manifest.json"
    ((FAIL++)) || true
    return
  fi

  # Check meta exists
  if [ ! -f "$meta" ]; then
    echo "  WARN: No meta.json"
    ((WARN++)) || true
  fi

  # Verify file checksums within backup
  python3 << 'PYEOF'
import json, hashlib, os, sys

backup_dir = sys.argv[1] if len(sys.argv) > 1 else ""
with open(os.path.join(backup_dir, "manifest.json")) as f:
    manifest = json.load(f)

ok = fail = missing = skipped = 0
backup_type = manifest.get("type", "full")

# Skip cron log files — they change during backup/verify and cause false mismatches
SKIP_PREFIXES = ("memory/cron/",)
SKIP_SUFFIXES = (".log",)

for entry in manifest.get("files", []):
    p = entry["path"]
    if any(p.startswith(pfx) for pfx in SKIP_PREFIXES) and any(p.endswith(sfx) for sfx in SKIP_SUFFIXES):
        skipped += 1
        continue
    backup_file = os.path.join(backup_dir, p)
    if os.path.exists(backup_file):
        with open(backup_file, "rb") as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
        if actual == entry["sha256"]:
            ok += 1
        else:
            print(f"  FAIL: checksum mismatch: {p}")
            fail += 1
    else:
        if backup_type == "incremental":
            pass  # Expected for unchanged files in incremental
        else:
            print(f"  MISSING: {p}")
            missing += 1

print(f"  Files: {ok} verified, {fail} failed, {missing} missing, {skipped} skipped (cron logs)")
sys.exit(1 if fail > 0 else 0)
PYEOF
  local result=$?

  # Verify git bundle if present
  if [ -f "$backup_dir/git-bundle.bundle" ]; then
    if git bundle verify "$backup_dir/git-bundle.bundle" &>/dev/null; then
      echo "  Git bundle: OK"
    else
      echo "  FAIL: Git bundle corrupt"
      ((FAIL++)) || true
    fi
  fi

  if [ "$result" -eq 0 ]; then
    echo "  Status: PASS"
    ((PASS++)) || true
  else
    echo "  Status: FAIL"
    ((FAIL++)) || true
  fi
  echo ""
}

# Inject backup_dir as argument to python
verify_backup_with_arg() {
  local backup_dir="$1"
  local name
  name=$(basename "$backup_dir")
  local manifest="$backup_dir/manifest.json"
  local meta="$backup_dir/meta.json"

  echo "--- Verifying: $name ---"

  if [ ! -f "$manifest" ]; then
    echo "  FAIL: No manifest.json"
    ((FAIL++)) || true
    return
  fi

  if [ ! -f "$meta" ]; then
    echo "  WARN: No meta.json"
    ((WARN++)) || true
  fi

  python3 -c "
import json, hashlib, os, sys

backup_dir = '$backup_dir'
with open(os.path.join(backup_dir, 'manifest.json')) as f:
    manifest = json.load(f)

ok = fail = missing = skipped = 0
backup_type = manifest.get('type', 'full')

# Skip cron log files — they change during backup/verify and cause false mismatches
SKIP_PREFIXES = ('memory/cron/',)
SKIP_SUFFIXES = ('.log',)

for entry in manifest.get('files', []):
    p = entry['path']
    if any(p.startswith(pfx) for pfx in SKIP_PREFIXES) and any(p.endswith(sfx) for sfx in SKIP_SUFFIXES):
        skipped += 1
        continue
    backup_file = os.path.join(backup_dir, p)
    if os.path.exists(backup_file):
        with open(backup_file, 'rb') as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
        if actual == entry['sha256']:
            ok += 1
        else:
            print(f'  FAIL: checksum mismatch: {p}')
            fail += 1
    else:
        if backup_type == 'incremental':
            pass
        else:
            print(f'  MISSING: {p}')
            missing += 1

print(f'  Files: {ok} verified, {fail} failed, {missing} missing, {skipped} skipped (cron logs)')
sys.exit(1 if fail > 0 else 0)
"
  local result=$?

  if [ -f "$backup_dir/git-bundle.bundle" ]; then
    if git bundle verify "$backup_dir/git-bundle.bundle" &>/dev/null; then
      echo "  Git bundle: OK"
    else
      echo "  FAIL: Git bundle corrupt"
      ((FAIL++)) || true
    fi
  fi

  if [ "$result" -eq 0 ]; then
    echo "  Status: PASS"
    ((PASS++)) || true
  else
    echo "  Status: FAIL"
    ((FAIL++)) || true
  fi
  echo ""
}

compare_live() {
  echo "=== Comparing latest backup to live workspace ==="
  local latest
  latest=$(readlink -f "$BACKUP_ROOT/latest" 2>/dev/null)
  if [ -z "$latest" ] || [ ! -d "$latest" ]; then
    echo "No latest backup found"
    exit 1
  fi

  echo "Backup: $(basename "$latest")"
  echo ""

  python3 -c "
import json, hashlib, os

backup_dir = '$latest'
workspace = '$WORKSPACE'

with open(os.path.join(backup_dir, 'manifest.json')) as f:
    manifest = json.load(f)

changed = []
deleted = []
unchanged = 0

for entry in manifest.get('files', []):
    live_file = os.path.join(workspace, entry['path'])
    if os.path.exists(live_file):
        with open(live_file, 'rb') as fh:
            live_hash = hashlib.sha256(fh.read()).hexdigest()
        if live_hash != entry['sha256']:
            changed.append(entry['path'])
        else:
            unchanged += 1
    else:
        deleted.append(entry['path'])

if changed:
    print(f'Changed since backup ({len(changed)}):')
    for p in changed:
        print(f'  M {p}')
if deleted:
    print(f'\\nDeleted since backup ({len(deleted)}):')
    for p in deleted:
        print(f'  D {p}')
if not changed and not deleted:
    print('No drift detected - backup matches live state')

print(f'\\nSummary: {unchanged} unchanged, {len(changed)} changed, {len(deleted)} deleted')
"
}

# --- Main ---
echo "=============================="
echo "Clarvis Backup Verification"
echo "=============================="
echo ""

case "$ACTION" in
  latest)
    latest=$(readlink -f "$BACKUP_ROOT/latest" 2>/dev/null)
    if [ -n "$latest" ] && [ -d "$latest" ]; then
      verify_backup_with_arg "$latest"
    else
      echo "No latest backup found"
      exit 1
    fi
    ;;
  all)
    for dir in $(ls -dt "$BACKUP_ROOT"/2*/ 2>/dev/null); do
      verify_backup_with_arg "$dir"
    done
    ;;
  compare)
    compare_live
    ;;
  specific)
    if [ -d "$BACKUP_ROOT/$TARGET" ]; then
      verify_backup_with_arg "$BACKUP_ROOT/$TARGET"
    else
      echo "Backup not found: $TARGET"
      exit 1
    fi
    ;;
esac

echo "=============================="
echo "Results: $PASS passed, $FAIL failed, $WARN warnings"
echo "=============================="
exit $FAIL
