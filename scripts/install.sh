#!/usr/bin/env bash
# install.sh — Guided Clarvis installer with profile selection.
#
# Usage:
#   bash scripts/install.sh                          # Interactive (prompts for profile)
#   bash scripts/install.sh --profile standalone     # Non-interactive
#   bash scripts/install.sh --profile openclaw --dev # With dev extras
#
# Profiles: standalone, openclaw, fullstack, docker
# Flags:    --dev, --no-brain, --profile <name>, --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ── Defaults ──────────────────────────────────────────────────────────────
PROFILE=""
DEV=0
BRAIN=1
INTERACTIVE=1

# ── Colours (if terminal) ────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD="\033[1m"
    GREEN="\033[32m"
    YELLOW="\033[33m"
    RED="\033[31m"
    CYAN="\033[36m"
    RESET="\033[0m"
else
    BOLD="" GREEN="" YELLOW="" RED="" CYAN="" RESET=""
fi

info()  { echo -e "${CYAN}>>>${RESET} $*"; }
ok()    { echo -e "  ${GREEN}OK${RESET}  $*"; }
warn()  { echo -e "  ${YELLOW}WARN${RESET}  $*"; }
fail()  { echo -e "  ${RED}FAIL${RESET}  $*"; }

# ── Argument parsing ─────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        --profile)
            PROFILE="$2"; INTERACTIVE=0; shift 2 ;;
        --profile=*)
            PROFILE="${1#*=}"; INTERACTIVE=0; shift ;;
        --dev)      DEV=1; shift ;;
        --no-brain) BRAIN=0; shift ;;
        --help|-h)
            cat <<'USAGE'
Clarvis Installer

Usage: bash scripts/install.sh [OPTIONS]

Options:
  --profile <name>   Install profile: standalone, openclaw, fullstack, docker
  --dev              Include dev/test extras (ruff, pytest)
  --no-brain         Skip ChromaDB + ONNX (lighter install, no vector memory)
  --help             Show this help

Profiles:
  standalone   Python packages + CLI + brain (default, recommended)
  openclaw     Standalone + OpenClaw gateway + chat channels
  fullstack    OpenClaw + system crontab + systemd service
  docker       Containerized dev/test setup

Examples:
  bash scripts/install.sh                           # Interactive
  bash scripts/install.sh --profile standalone      # Non-interactive
  bash scripts/install.sh --profile standalone --dev --no-brain
USAGE
            exit 0 ;;
        *) echo "Unknown option: $1 (try --help)"; exit 1 ;;
    esac
done

# ── Banner ───────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔═══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       Clarvis Installer v1.0          ║${RESET}"
echo -e "${BOLD}╚═══════════════════════════════════════╝${RESET}"
echo ""

# ── Step 1: Environment checks ──────────────────────────────────────────
info "Checking environment..."

# Python
if ! command -v python3 &>/dev/null; then
    fail "python3 not found — install Python 3.10+"
    exit 1
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    fail "Python 3.10+ required, found $PY_VERSION"
    exit 1
fi
ok "Python $PY_VERSION"

# pip
if ! python3 -m pip --version &>/dev/null; then
    fail "pip not found — install python3-pip"
    exit 1
fi
ok "pip available"

# git
if ! command -v git &>/dev/null; then
    warn "git not found — some features may not work"
else
    ok "git $(git --version | cut -d' ' -f3)"
fi

# SQLite
if command -v sqlite3 &>/dev/null; then
    ok "sqlite3 $(sqlite3 --version | cut -d' ' -f1)"
else
    warn "sqlite3 not found — graph backend may fall back to JSON"
fi

echo ""

# ── Step 2: Profile selection ────────────────────────────────────────────
if [ "$INTERACTIVE" -eq 1 ] && [ -z "$PROFILE" ]; then
    info "Select an installation profile:"
    echo ""
    echo -e "  ${BOLD}1)${RESET} ${GREEN}Standalone${RESET} (recommended)"
    echo "     Python packages + CLI + brain. No external services."
    echo ""
    echo -e "  ${BOLD}2)${RESET} ${CYAN}OpenClaw Gateway${RESET}"
    echo "     Standalone + chat agent (Telegram/Discord). Needs Node.js 18+."
    echo ""
    echo -e "  ${BOLD}3)${RESET} ${YELLOW}Full Stack${RESET}"
    echo "     OpenClaw + cron + systemd. The reference deployment. Needs Linux."
    echo ""
    echo -e "  ${BOLD}4)${RESET} Docker"
    echo "     Containerized dev/test. Needs Docker + Compose."
    echo ""
    while true; do
        read -rp "Profile [1-4, default=1]: " choice
        case "${choice:-1}" in
            1|standalone)  PROFILE="standalone"; break ;;
            2|openclaw)    PROFILE="openclaw"; break ;;
            3|fullstack)   PROFILE="fullstack"; break ;;
            4|docker)      PROFILE="docker"; break ;;
            *) echo "  Please enter 1-4." ;;
        esac
    done
    echo ""
fi

# Validate profile
PROFILE="${PROFILE:-standalone}"
case "$PROFILE" in
    standalone|openclaw|fullstack|docker) ;;
    *) fail "Unknown profile: $PROFILE (valid: standalone, openclaw, fullstack, docker)"; exit 1 ;;
esac

info "Profile: ${BOLD}$PROFILE${RESET}"
echo ""

# ── Step 3: Profile-specific prereq checks ───────────────────────────────
if [ "$PROFILE" = "openclaw" ] || [ "$PROFILE" = "fullstack" ]; then
    if ! command -v node &>/dev/null; then
        fail "Node.js not found — required for OpenClaw gateway"
        echo "  Install Node.js 18+: https://nodejs.org/"
        exit 1
    fi
    NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -lt 18 ]; then
        fail "Node.js 18+ required, found $(node -v)"
        exit 1
    fi
    ok "Node.js $(node -v)"
fi

if [ "$PROFILE" = "fullstack" ]; then
    if ! command -v systemctl &>/dev/null; then
        fail "systemd not found — required for Full Stack profile"
        echo "  Full Stack requires Linux with systemd."
        exit 1
    fi
    ok "systemd available"
fi

if [ "$PROFILE" = "docker" ]; then
    if ! command -v docker &>/dev/null; then
        fail "Docker not found — required for Docker profile"
        echo "  Install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    ok "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

    info "Building Docker image..."
    docker compose build
    ok "Docker image built"

    info "Running verification inside container..."
    docker compose run --rm clarvis bash scripts/verify_install.sh
    echo ""
    info "Docker profile ready."
    echo "  Run:  docker compose run clarvis"
    echo "  Test: docker compose run clarvis pytest -m 'not slow'"
    exit 0
fi

# ── Step 4: Install Python packages ─────────────────────────────────────
info "Installing Python packages..."

# Detect PEP 668 externally-managed environment
PIP_EXTRA=""
if python3 -c "import sysconfig; exit(0 if (sysconfig.get_path('stdlib') / 'EXTERNALLY-MANAGED').exists() if hasattr(sysconfig.get_path('stdlib'), '__class__') else False)" 2>/dev/null; then
    true  # Can't detect this way
fi
if [ -f "$(python3 -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')/EXTERNALLY-MANAGED" ]; then
    PIP_EXTRA="--break-system-packages"
    warn "PEP 668 detected — using --break-system-packages"
fi

echo "  [1/3] Sub-packages (dependency order)..."
pip install $PIP_EXTRA -e packages/clarvis-cost -q 2>&1 | grep -v "already satisfied" || true
pip install $PIP_EXTRA -e packages/clarvis-reasoning -q 2>&1 | grep -v "already satisfied" || true
pip install $PIP_EXTRA -e packages/clarvis-db -q 2>&1 | grep -v "already satisfied" || true
ok "clarvis-cost, clarvis-reasoning, clarvis-db"

echo "  [2/3] Main package..."
if [ "$BRAIN" -eq 1 ] && [ "$DEV" -eq 1 ]; then
    pip install $PIP_EXTRA -e ".[all]" -q 2>&1 | grep -v "already satisfied" || true
    ok "clarvis[all] (brain + dev)"
elif [ "$BRAIN" -eq 1 ]; then
    pip install $PIP_EXTRA -e ".[brain]" -q 2>&1 | grep -v "already satisfied" || true
    ok "clarvis[brain]"
elif [ "$DEV" -eq 1 ]; then
    pip install $PIP_EXTRA -e ".[dev]" -q 2>&1 | grep -v "already satisfied" || true
    ok "clarvis[dev] (no brain)"
else
    pip install $PIP_EXTRA -e . -q 2>&1 | grep -v "already satisfied" || true
    ok "clarvis (core only)"
fi

# ── Step 5: Environment setup ────────────────────────────────────────────
echo "  [3/3] Environment..."

# Create .env if it doesn't exist
if [ ! -f "$REPO_ROOT/.env" ]; then
    TEMPLATE="$REPO_ROOT/config/profiles/${PROFILE}.env.template"
    if [ -f "$TEMPLATE" ]; then
        # Use profile-specific template
        sed "s|__WORKSPACE__|$REPO_ROOT|g" "$TEMPLATE" > "$REPO_ROOT/.env"
        ok "Created .env from $PROFILE profile template"
    else
        # Fallback: create minimal .env
        cat > "$REPO_ROOT/.env" <<ENVEOF
# Clarvis environment — generated by install.sh (profile: $PROFILE)
CLARVIS_WORKSPACE=$REPO_ROOT
CLARVIS_GRAPH_BACKEND=sqlite
ENVEOF
        ok "Created minimal .env"
    fi
else
    ok ".env already exists (kept as-is)"
fi

# Ensure CLARVIS_WORKSPACE is set for this session
export CLARVIS_WORKSPACE="$REPO_ROOT"
echo ""

# ── Step 6: Profile-specific setup ──────────────────────────────────────
if [ "$PROFILE" = "openclaw" ] || [ "$PROFILE" = "fullstack" ]; then
    info "OpenClaw gateway setup..."
    if command -v openclaw &>/dev/null; then
        ok "OpenClaw CLI already installed"
    elif [ -f "$HOME/.npm-global/lib/node_modules/openclaw/dist/index.js" ]; then
        ok "OpenClaw found at ~/.npm-global"
    else
        warn "OpenClaw not installed — install with: npm install -g openclaw"
        echo "  See https://openclaw.dev for setup instructions"
    fi
fi

if [ "$PROFILE" = "fullstack" ]; then
    info "Cron schedule setup..."
    echo "  The full cron schedule can be installed from the reference crontab."
    echo "  Review: less scripts/crontab.reference"
    echo "  Install: crontab scripts/crontab.reference"
    warn "Cron schedule not auto-installed (review first)"

    info "systemd service setup..."
    if systemctl --user is-enabled openclaw-gateway.service &>/dev/null 2>&1; then
        ok "openclaw-gateway.service enabled"
    else
        warn "openclaw-gateway.service not enabled"
        echo "  Enable: systemctl --user enable openclaw-gateway.service"
        echo "  Start:  systemctl --user start openclaw-gateway.service"
    fi
fi

# ── Step 7: First-run validation ─────────────────────────────────────────
echo ""
info "Running first-run validation..."
echo ""

VERIFY_ARGS=""
if [ "$BRAIN" -eq 0 ]; then
    VERIFY_ARGS="--no-brain"
fi

bash "$SCRIPT_DIR/verify_install.sh" $VERIFY_ARGS

echo ""
echo -e "${BOLD}╔═══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       Installation Complete            ║${RESET}"
echo -e "${BOLD}╚═══════════════════════════════════════╝${RESET}"
echo ""
echo "  Profile:   $PROFILE"
echo "  Workspace: $REPO_ROOT"
echo ""
echo "  Next steps:"
echo "    clarvis brain health          # Check brain status"
echo "    python3 -m pytest -m 'not slow'  # Run tests"
if [ "$PROFILE" = "openclaw" ] || [ "$PROFILE" = "fullstack" ]; then
    echo "    systemctl --user start openclaw-gateway.service  # Start gateway"
fi
echo "    cat docs/INSTALL.md           # Full documentation"
echo ""
