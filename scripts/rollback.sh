#!/bin/bash
LATEST=$(ls -dt ~/.openclaw/backups/*/ 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
  echo "No backups found"
  exit 1
fi
echo "Rolling back to: $LATEST"
cp -r "$LATEST/workspace/"* ~/.openclaw/workspace/
echo "Rollback complete. Restart gateway to apply."
