#!/bin/bash
# Clarvis Self-Backup
# Run this BEFORE any self-modification

BACKUP_DIR="$HOME/.openclaw/backups/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

cp -r ~/.openclaw/workspace/ "$BACKUP_DIR/workspace/"
cp ~/.openclaw/openclaw.json "$BACKUP_DIR/openclaw.json"
cp -r ~/.openclaw/agents/ "$BACKUP_DIR/agents/" 2>/dev/null

cd ~/.openclaw/workspace
git add -A
git commit -m "backup: pre-modification snapshot $(date +%Y-%m-%d_%H%M%S)" 2>/dev/null || true

echo "Backup created: $BACKUP_DIR"
echo "Git state committed"

ls -dt ~/.openclaw/backups/*/ | tail -n +11 | xargs rm -rf 2>/dev/null
