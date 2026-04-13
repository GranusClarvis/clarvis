#!/usr/bin/env bash
# install.sh — Guided Clarvis installer with profile selection.
#
# Usage:
#   bash scripts/install.sh                              # Interactive (prompts for profile)
#   bash scripts/install.sh --profile standalone         # Non-interactive
#   bash scripts/install.sh --profile openclaw --dev     # With dev extras
#   bash scripts/install.sh --profile local --no-cron    # Local-only, no cron
#
# Profiles:
#   minimal      Core CLI only — no brain, no services, no API keys
#   standalone   CLI + brain (ChromaDB + ONNX). Recommended for most users
#   openclaw     Standalone + OpenClaw gateway + chat channels (Telegram/Discord)
#   fullstack    OpenClaw + cron schedule + systemd. Reference deployment
#   hermes       Standalone + Hermes agent harness (NousResearch/hermes-agent)
#   local        Standalone + Ollama local models. Zero API keys needed
#   docker       Containerized dev/test setup
#
# Modifiers:
#   --dev          Include dev/test extras (ruff, pytest)
#   --no-brain     Skip ChromaDB + ONNX (auto-set for minimal profile)
#   --cron <preset>  Install cron schedule (minimal|recommended|full|research)
#   --no-cron      Explicitly skip cron setup (default for non-fullstack profiles)
#   --help         Show this help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# ── Defaults ──────────────────────────────────────────────────────────────
PROFILE=""
DEV=0
BRAIN=1      # 1=install brain, 0=skip, -1=auto (profile decides)
BRAIN_SET=0  # was --no-brain explicitly passed?
CRON=""      # empty=auto (profile decides), "none"=skip, preset name=install
CRON_SET=0   # was --cron/--no-cron explicitly passed?
INTERACTIVE=1

VALID_PROFILES="minimal standalone openclaw fullstack hermes local docker"
VALID_CRON_PRESETS="minimal recommended full research"

# ── Colours (if terminal) ────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD="\033[1m"
    GREEN="\033[32m"
    YELLOW="\033[33m"
    RED="\033[31m"
    CYAN="\033[36m"
    DIM="\033[2m"
    RESET="\033[0m"
else
    BOLD="" GREEN="" YELLOW="" RED="" CYAN="" DIM="" RESET=""
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
        --no-brain) BRAIN=0; BRAIN_SET=1; shift ;;
        --cron)
            CRON="$2"; CRON_SET=1; shift 2 ;;
        --cron=*)
            CRON="${1#*=}"; CRON_SET=1; shift ;;
        --no-cron)  CRON="none"; CRON_SET=1; shift ;;
        --openrouter-key)
            export OPENROUTER_API_KEY="$2"; shift 2 ;;
        --openrouter-key=*)
            export OPENROUTER_API_KEY="${1#*=}"; shift ;;
        --help|-h)
            cat <<'USAGE'
Clarvis Installer

Usage: bash scripts/install.sh [OPTIONS]

Options:
  --profile <name>     Install profile (see below)
  --dev                Include dev/test extras (ruff, pytest)
  --no-brain           Skip ChromaDB + ONNX (lighter install, no vector memory)
  --cron <preset>      Install cron schedule: minimal, recommended, full, research
  --no-cron            Explicitly skip cron setup
  --openrouter-key KEY Set OpenRouter API key (or set OPENROUTER_API_KEY env var)
  --help               Show this help

Profiles:
  minimal      Core CLI only — no brain, no services, no API keys needed
  standalone   CLI + brain (ChromaDB + ONNX). Recommended for most users
  openclaw     Standalone + OpenClaw gateway + chat channels
  fullstack    OpenClaw + system crontab + systemd (reference deployment)
  hermes       Standalone + Hermes agent harness (NousResearch/hermes-agent)
  local        Standalone + Ollama local models (zero API keys)
  docker       Containerized dev/test setup

Profile comparison:
  Feature         minimal  standalone  openclaw  fullstack  hermes  local  docker
  ─────────────────────────────────────────────────────────────────────────────────
  Python CLI        Yes      Yes         Yes       Yes       Yes     Yes    Yes
  Brain (ChromaDB)  -        Yes         Yes       Yes       Yes     Yes    Yes
  OpenClaw GW       -        -           Yes       Yes       -       -      -
  Chat channels     -        -           Yes       Yes       -       -      -
  Cron schedule     -        -           -         Yes*      -       -      -
  systemd service   -        -           -         Yes       -       -      -
  Hermes agent      -        -           -         -         Yes     -      -
  Local models      -        -           -         -         -       Yes    -
  Container         -        -           -         -         -       -      Yes
  API key needed    No       No**        Yes       Yes       No***   No     No

  *  Cron can be added to any profile with --cron <preset>
  ** Brain works locally; API key only needed for Claude Code spawning
  *** Hermes can use local models or API keys

Examples:
  bash scripts/install.sh                             # Interactive
  bash scripts/install.sh --profile standalone        # Quick standalone
  bash scripts/install.sh --profile minimal           # Lightest possible
  bash scripts/install.sh --profile local             # Zero API keys
  bash scripts/install.sh --profile fullstack --cron recommended
  bash scripts/install.sh --profile standalone --cron minimal --dev
USAGE
            exit 0 ;;
        *) echo "Unknown option: $1 (try --help)"; exit 1 ;;
    esac
done

# ── Banner ───────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔═══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       Clarvis Installer v2.0          ║${RESET}"
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
    echo -e "  ${BOLD}1)${RESET} ${GREEN}Minimal${RESET}"
    echo -e "     Core CLI only. No brain, no services, no API keys.${DIM} (~30 MB)${RESET}"
    echo ""
    echo -e "  ${BOLD}2)${RESET} ${GREEN}Standalone${RESET} ${CYAN}(recommended)${RESET}"
    echo -e "     CLI + vector brain (ChromaDB + ONNX). Full local intelligence.${DIM} (~500 MB)${RESET}"
    echo ""
    echo -e "  ${BOLD}3)${RESET} ${CYAN}OpenClaw Gateway${RESET}"
    echo "     Standalone + chat agent (Telegram/Discord). Needs Node.js 18+."
    echo ""
    echo -e "  ${BOLD}4)${RESET} ${YELLOW}Full Stack${RESET}"
    echo "     OpenClaw + cron + systemd. The reference deployment. Needs Linux."
    echo ""
    echo -e "  ${BOLD}5)${RESET} Hermes Agent"
    echo "     Standalone + Hermes harness (NousResearch). Alternative to OpenClaw."
    echo ""
    echo -e "  ${BOLD}6)${RESET} Local Models Only"
    echo "     Standalone + Ollama setup. Zero API keys — fully offline."
    echo ""
    echo -e "  ${BOLD}7)${RESET} Docker"
    echo "     Containerized dev/test. Needs Docker + Compose."
    echo ""
    while true; do
        read -rp "Profile [1-7, default=2]: " choice
        case "${choice:-2}" in
            1|minimal)     PROFILE="minimal"; break ;;
            2|standalone)  PROFILE="standalone"; break ;;
            3|openclaw)    PROFILE="openclaw"; break ;;
            4|fullstack)   PROFILE="fullstack"; break ;;
            5|hermes)      PROFILE="hermes"; break ;;
            6|local)       PROFILE="local"; break ;;
            7|docker)      PROFILE="docker"; break ;;
            *) echo "  Please enter 1-7." ;;
        esac
    done
    echo ""

    # ── Interactive: cron preference ────────────────────────────────────
    if [ "$CRON_SET" -eq 0 ]; then
        # fullstack defaults to cron; others ask if user wants it
        if [ "$PROFILE" = "fullstack" ]; then
            echo -e "  ${DIM}Cron schedule will be configured (default for fullstack).${RESET}"
            echo ""
            info "Select cron preset:"
            echo ""
            echo -e "  ${BOLD}1)${RESET} ${GREEN}Minimal${RESET} — 12 jobs: monitoring + backup. No Claude Code spawning."
            echo -e "  ${BOLD}2)${RESET} ${CYAN}Recommended${RESET} — 27 jobs: daily cycle + 4x autonomous/day."
            echo -e "  ${BOLD}3)${RESET} ${YELLOW}Full${RESET} — 46 jobs: 12x autonomous, research, all benchmarks."
            echo -e "  ${BOLD}4)${RESET} Research — 40 jobs: extra research + dream engine."
            echo ""
            while true; do
                read -rp "Cron preset [1-4, default=2]: " cron_choice
                case "${cron_choice:-2}" in
                    1|minimal)      CRON="minimal"; break ;;
                    2|recommended)  CRON="recommended"; break ;;
                    3|full)         CRON="full"; break ;;
                    4|research)     CRON="research"; break ;;
                    *) echo "  Please enter 1-4." ;;
                esac
            done
        elif [ "$PROFILE" != "minimal" ] && [ "$PROFILE" != "docker" ]; then
            echo ""
            read -rp "Enable cron schedule (autonomous background tasks)? [y/N]: " enable_cron
            case "$enable_cron" in
                [yY]|[yY][eE][sS])
                    echo ""
                    info "Select cron preset:"
                    echo ""
                    echo -e "  ${BOLD}1)${RESET} ${GREEN}Minimal${RESET} — 12 jobs: monitoring + backup only."
                    echo -e "  ${BOLD}2)${RESET} ${CYAN}Recommended${RESET} — 27 jobs: daily cycle + 4x autonomous/day."
                    echo ""
                    while true; do
                        read -rp "Cron preset [1-2, default=1]: " cron_choice
                        case "${cron_choice:-1}" in
                            1|minimal)      CRON="minimal"; break ;;
                            2|recommended)  CRON="recommended"; break ;;
                            *) echo "  Please enter 1-2." ;;
                        esac
                    done
                    ;;
                *)
                    CRON="none"
                    ;;
            esac
        else
            CRON="none"
        fi
    fi
    echo ""
fi

# ── Validate profile ────────────────────────────────────────────────────
PROFILE="${PROFILE:-standalone}"
PROFILE_VALID=0
for p in $VALID_PROFILES; do
    [ "$p" = "$PROFILE" ] && PROFILE_VALID=1
done
if [ "$PROFILE_VALID" -eq 0 ]; then
    fail "Unknown profile: $PROFILE"
    echo "  Valid profiles: $VALID_PROFILES"
    exit 1
fi

# ── Apply profile defaults ──────────────────────────────────────────────
# Brain: minimal=off, all others=on (unless user overrode with --no-brain)
if [ "$BRAIN_SET" -eq 0 ]; then
    case "$PROFILE" in
        minimal) BRAIN=0 ;;
        *)       BRAIN=1 ;;
    esac
fi

# Cron: fullstack defaults to recommended, others default to none
if [ "$CRON_SET" -eq 0 ] && [ -z "$CRON" ]; then
    case "$PROFILE" in
        fullstack) CRON="recommended" ;;
        *)         CRON="none" ;;
    esac
fi

# Validate cron preset
if [ "$CRON" != "none" ] && [ -n "$CRON" ]; then
    CRON_VALID=0
    for p in $VALID_CRON_PRESETS; do
        [ "$p" = "$CRON" ] && CRON_VALID=1
    done
    if [ "$CRON_VALID" -eq 0 ]; then
        fail "Unknown cron preset: $CRON"
        echo "  Valid presets: $VALID_CRON_PRESETS"
        exit 1
    fi
fi

# ── Display configuration ───────────────────────────────────────────────
info "Configuration:"
echo "  Profile:   $PROFILE"
echo "  Brain:     $([ "$BRAIN" -eq 1 ] && echo "yes (ChromaDB + ONNX)" || echo "no")"
echo "  Dev tools: $([ "$DEV" -eq 1 ] && echo "yes (ruff + pytest)" || echo "no")"
echo "  Cron:      $([ "$CRON" = "none" ] && echo "disabled" || echo "$CRON")"
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

if [ "$PROFILE" = "hermes" ]; then
    # Check if hermes-agent is installed or pip-installable
    if command -v hermes &>/dev/null; then
        ok "hermes CLI found: $(command -v hermes)"
    elif python3 -c "import hermes_agent" 2>/dev/null; then
        ok "hermes-agent Python package available"
    else
        warn "hermes-agent not found — will attempt install (PyPI → GitHub source)"
    fi
fi

if [ "$PROFILE" = "local" ]; then
    OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama 2>/dev/null || echo "$HOME/.local/ollama/bin/ollama")}"
    if [ -x "$OLLAMA_BIN" ]; then
        ok "Ollama found: $OLLAMA_BIN"
    else
        warn "Ollama not found — install from https://ollama.com"
        echo "  After install, run: ollama pull qwen3-vl:4b"
    fi
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
    docker compose run --rm clarvis bash scripts/infra/verify_install.sh
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
if [ -f "$(python3 -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')/EXTERNALLY-MANAGED" ]; then
    PIP_EXTRA="--break-system-packages"
    warn "PEP 668 detected — using --break-system-packages"
fi

EXTRAS=""
if [ "$BRAIN" -eq 1 ] && [ "$DEV" -eq 1 ]; then
    EXTRAS="all"
elif [ "$BRAIN" -eq 1 ]; then
    EXTRAS="brain"
elif [ "$DEV" -eq 1 ]; then
    EXTRAS="dev"
fi

if [ -n "$EXTRAS" ]; then
    pip install $PIP_EXTRA -e ".[$EXTRAS]" -q 2>&1 | grep -v "already satisfied" || true
    ok "clarvis[$EXTRAS]"
else
    pip install $PIP_EXTRA -e . -q 2>&1 | grep -v "already satisfied" || true
    ok "clarvis (core only)"
fi

# ── Step 5: Environment setup ────────────────────────────────────────────
info "Environment setup..."

# Create .env if it doesn't exist
if [ ! -f "$REPO_ROOT/.env" ]; then
    TEMPLATE="$REPO_ROOT/config/profiles/${PROFILE}.env.template"
    if [ -f "$TEMPLATE" ]; then
        sed "s|__WORKSPACE__|$REPO_ROOT|g" "$TEMPLATE" > "$REPO_ROOT/.env"
        ok "Created .env from $PROFILE profile template"
    else
        cat > "$REPO_ROOT/.env" <<ENVEOF
# Clarvis environment — generated by install.sh (profile: $PROFILE)
CLARVIS_WORKSPACE=$REPO_ROOT
CLARVIS_GRAPH_BACKEND=sqlite
CLARVIS_INSTALL_PROFILE=$PROFILE
ENVEOF
        ok "Created minimal .env"
    fi
else
    ok ".env already exists (kept as-is)"
fi

export CLARVIS_WORKSPACE="$REPO_ROOT"
echo ""

# ── Step 5b: LLM connectivity note ──────────────────────────────────────
# Clarvis doesn't manage the LLM connection — that's the harness's job
# (OpenClaw's openclaw.json, Hermes's config.yaml, or Ollama).
# Just check if an API key is already present from the environment or .env.
if [ "$PROFILE" != "minimal" ] && [ "$PROFILE" != "docker" ]; then
    _HAS_KEY=false
    if [ -n "${OPENROUTER_API_KEY:-}" ] && [ "${OPENROUTER_API_KEY:-}" != "sk-or-v1-your-key-here" ]; then
        _HAS_KEY=true
    elif grep -qE "^(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY)=" "$REPO_ROOT/.env" 2>/dev/null; then
        _KEY_VAL=$(grep -E "^(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY)=" "$REPO_ROOT/.env" | head -1 | cut -d= -f2-)
        [ -n "$_KEY_VAL" ] && [ "$_KEY_VAL" != "sk-or-v1-your-key-here" ] && _HAS_KEY=true
    fi

    if $_HAS_KEY; then
        ok "LLM API key detected in environment"
    else
        echo ""
        echo -e "  ${DIM}Note: Clarvis brain and CLI work without any API key.${RESET}"
        echo -e "  ${DIM}LLM features (chat, routing, autonomy) are configured through${RESET}"
        echo -e "  ${DIM}your harness (OpenClaw/Hermes) or .env file. See docs/INSTALL.md.${RESET}"
    fi
fi
echo ""

# ── Step 6: Profile-specific setup ──────────────────────────────────────
case "$PROFILE" in
    openclaw|fullstack)
        info "OpenClaw gateway setup..."
        if command -v openclaw &>/dev/null; then
            ok "OpenClaw CLI already installed"
        elif [ -f "$HOME/.npm-global/lib/node_modules/openclaw/dist/index.js" ]; then
            ok "OpenClaw found at ~/.npm-global"
        else
            warn "OpenClaw not installed — install with: npm install -g openclaw"
            echo "  See https://openclaw.dev for setup instructions"
        fi

        # Port conflict check (default gateway port 18789)
        GW_PORT=18789
        if ss -tln 2>/dev/null | grep -q ":${GW_PORT} " || \
           lsof -i ":${GW_PORT}" >/dev/null 2>&1; then
            warn "Port $GW_PORT is already in use — gateway may not start"
            echo "  Check: ss -tlnp | grep $GW_PORT"
            echo "  Or configure a different port in openclaw.json"
        else
            ok "Port $GW_PORT available for gateway"
        fi
        ;;

    hermes)
        info "Hermes agent harness setup..."
        if ! command -v hermes &>/dev/null && ! python3 -c "import hermes_agent" 2>/dev/null; then
            echo "  Installing hermes-agent from PyPI..."
            if pip install $PIP_EXTRA hermes-agent -q 2>&1 | grep -v "already satisfied"; then
                : # success
            else
                warn "PyPI install failed — trying GitHub source..."
                pip install $PIP_EXTRA "git+https://github.com/NousResearch/hermes-agent.git" -q 2>&1 | grep -v "already satisfied" || true
            fi
            if command -v hermes &>/dev/null || python3 -c "import hermes_agent" 2>/dev/null; then
                ok "hermes-agent installed"
            else
                fail "hermes-agent install failed"
                echo "  Install manually: pip install git+https://github.com/NousResearch/hermes-agent.git"
            fi
        else
            ok "hermes-agent already available"
        fi

        # Headless Hermes config bootstrap — create ~/.hermes/ and config.yaml
        # so users don't need an interactive TTY for first-time setup.
        # Only creates a default config if none exists; respects existing setup.
        HERMES_DIR="${HERMES_HOME:-$HOME/.hermes}"
        mkdir -p "$HERMES_DIR"
        if [ ! -f "$HERMES_DIR/config.yaml" ]; then
            cat > "$HERMES_DIR/config.yaml" <<'HERMESCFG'
# Hermes config — generated by Clarvis install.sh
# Edit model/provider to match your setup.
# Examples:
#   provider: "openrouter"   → set OPENROUTER_API_KEY in env or .env
#   provider: "ollama"       → local model via Ollama
#   provider: "anthropic"    → set ANTHROPIC_API_KEY
# Use `hermes chat --provider openrouter -m model/name` to override per-session.
model: "qwen3-vl:4b"
provider: "ollama"
base_url: "http://127.0.0.1:11434"
HERMESCFG
            ok "Created $HERMES_DIR/config.yaml (edit to match your LLM setup)"
        else
            ok "$HERMES_DIR/config.yaml already exists"
        fi
        if [ ! -f "$HERMES_DIR/.env" ]; then
            cat > "$HERMES_DIR/.env" <<HERMESENV
# Hermes environment — generated by Clarvis install.sh
# Uncomment and fill in any API keys you need:
# OPENROUTER_API_KEY=sk-or-v1-...
# ANTHROPIC_API_KEY=sk-ant-...
HERMESENV
            ok "Created $HERMES_DIR/.env (edit to add API keys)"
        else
            ok "$HERMES_DIR/.env already exists"
        fi

        echo ""
        echo "  Hermes config:  $HERMES_DIR/config.yaml"
        echo "  Hermes env:     $HERMES_DIR/.env"
        echo "  Sessions:       $HERMES_DIR/sessions/"
        echo ""
        echo "  IMPORTANT: Use the 'hermes' CLI (not 'hermes-agent') — it correctly"
        echo "  reads config.yaml. The 'hermes-agent' entry point has flag-handling bugs."
        echo "  Docs: https://github.com/NousResearch/hermes-agent"
        ;;

    local)
        info "Local model setup..."
        OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama 2>/dev/null || echo "$HOME/.local/ollama/bin/ollama")}"
        if [ -x "$OLLAMA_BIN" ]; then
            ok "Ollama binary: $OLLAMA_BIN"

            # Check if service is running
            if systemctl --user is-active ollama.service &>/dev/null 2>&1; then
                ok "Ollama service running"
            elif curl -sf http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
                ok "Ollama API reachable"
            else
                warn "Ollama service not running"
                echo "  Start: systemctl --user start ollama.service"
                echo "  Or:    ollama serve &"
            fi

            # Check for recommended model
            if "$OLLAMA_BIN" list 2>/dev/null | grep -q "qwen3-vl"; then
                ok "Local model available (qwen3-vl)"
            else
                warn "No local model found"
                echo "  Pull recommended model: ollama pull qwen3-vl:4b  (3.3 GB)"
            fi
        else
            warn "Ollama not installed"
            echo "  Install: curl -fsSL https://ollama.com/install.sh | sh"
            echo "  Then: ollama pull qwen3-vl:4b"
        fi

        echo ""
        echo "  Local model harness: bash scripts/infra/local_model_harness.sh status"
        echo "  Zero-API test suite: bash scripts/infra/local_model_harness.sh test"
        ;;
esac

# ── Step 7: Cron schedule ───────────────────────────────────────────────
if [ "$CRON" != "none" ] && [ -n "$CRON" ]; then
    echo ""
    info "Cron schedule setup (preset: $CRON)..."

    # Check if clarvis CLI supports cron commands
    if python3 -m clarvis cron presets >/dev/null 2>&1; then
        echo ""
        echo "  Preview of cron entries:"
        python3 -m clarvis cron install "$CRON" 2>&1 | head -20
        echo "  ..."
        echo ""

        if [ "$INTERACTIVE" -eq 1 ]; then
            read -rp "  Apply this cron schedule? [y/N]: " apply_cron
            case "$apply_cron" in
                [yY]|[yY][eE][sS])
                    python3 -m clarvis cron install "$CRON" --apply
                    ok "Cron schedule installed ($CRON)"
                    ;;
                *)
                    warn "Cron schedule not applied (dry-run only)"
                    echo "  Apply later: clarvis cron install $CRON --apply"
                    ;;
            esac
        else
            # Non-interactive: apply directly
            python3 -m clarvis cron install "$CRON" --apply
            ok "Cron schedule installed ($CRON)"
        fi
    else
        warn "clarvis cron CLI not available — install cron manually"
        echo "  See: clarvis cron presets"
    fi
fi

# ── Step 8: systemd service (fullstack only) ────────────────────────────
if [ "$PROFILE" = "fullstack" ]; then
    echo ""
    info "systemd service setup..."
    if systemctl --user is-enabled openclaw-gateway.service &>/dev/null 2>&1; then
        ok "openclaw-gateway.service enabled"
    else
        warn "openclaw-gateway.service not enabled"
        echo "  Enable: systemctl --user enable openclaw-gateway.service"
        echo "  Start:  systemctl --user start openclaw-gateway.service"
    fi
fi

# ── Step 9: Brain seed (fresh installs get useful initial memories) ─────
if [ "$BRAIN" -eq 1 ]; then
    echo ""
    info "Seeding brain with initial memories..."
    if python3 -m clarvis brain seed 2>/dev/null; then
        ok "Brain seeded"
    else
        warn "Brain seed skipped (non-critical)"
    fi
fi

# ── Step 10: First-run validation ────────────────────────────────────────
echo ""
info "Running first-run validation..."
echo ""

VERIFY_ARGS=""
[ "$BRAIN" -eq 0 ] && VERIFY_ARGS="$VERIFY_ARGS --no-brain"
[ -n "$PROFILE" ] && VERIFY_ARGS="$VERIFY_ARGS --profile $PROFILE"

# shellcheck disable=SC2086
bash "$SCRIPT_DIR/verify_install.sh" $VERIFY_ARGS || true

# ── Summary ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔═══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       Installation Complete            ║${RESET}"
echo -e "${BOLD}╚═══════════════════════════════════════╝${RESET}"
echo ""
echo "  Profile:   $PROFILE"
echo "  Brain:     $([ "$BRAIN" -eq 1 ] && echo "enabled" || echo "disabled")"
echo "  Cron:      $([ "$CRON" = "none" ] && echo "disabled" || echo "$CRON")"
echo "  Workspace: $REPO_ROOT"
echo ""
echo "  Next steps:"

case "$PROFILE" in
    minimal)
        echo "    clarvis --help                     # Explore CLI"
        echo "    clarvis mode show                  # Check operating mode"
        echo "    # Upgrade to standalone: bash scripts/install.sh --profile standalone"
        ;;
    standalone)
        echo "    clarvis brain health               # Check brain status"
        echo "    clarvis demo                       # Run self-contained demo"
        echo "    python3 -m pytest -m 'not slow'    # Run tests"
        ;;
    openclaw|fullstack)
        echo "    clarvis brain health               # Check brain status"
        echo "    systemctl --user start openclaw-gateway.service  # Start gateway"
        if [ "$CRON" = "none" ]; then
            echo "    clarvis cron presets              # See available cron presets"
        else
            echo "    clarvis cron status               # Check cron job status"
        fi
        ;;
    hermes)
        echo "    clarvis brain health               # Check brain status"
        echo "    hermes --help                      # Explore Hermes CLI (not hermes-agent)"
        echo "    hermes doctor                      # Check Hermes setup"
        echo "    cat docs/USER_GUIDE_HERMES.md      # Runtime guide (EXPERIMENTAL)"
        ;;
    local)
        echo "    clarvis brain health               # Check brain status"
        echo "    bash scripts/infra/local_model_harness.sh status  # Model status"
        echo "    bash scripts/infra/local_model_harness.sh test    # Zero-API test"
        ;;
esac

echo ""
echo "  For a full briefing on Clarvis and all available commands:"
echo "    clarvis welcome                    # Onboarding guide"
echo "    clarvis welcome --short            # Quick command cheat sheet"
echo ""
echo "    cat docs/INSTALL.md                # Full documentation"
echo "    cat docs/WHAT_IS_CLARVIS.md        # What makes Clarvis different"
echo ""

# Show quick command reference automatically
if python3 -m clarvis welcome --short 2>/dev/null; then
    : # shown above
fi
