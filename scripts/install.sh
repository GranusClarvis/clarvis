#!/usr/bin/env bash
# install.sh — Convenience wrapper that delegates to scripts/infra/install.sh.
# Usage: bash scripts/install.sh [OPTIONS]
# See scripts/infra/install.sh --help for full documentation.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/infra/install.sh" "$@"
