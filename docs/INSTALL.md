# Clarvis Installation Guide

> **Note (2026-04-03):** The `packages/` directory (clarvis-db, clarvis-cost, clarvis-reasoning) has been
> consolidated into the `clarvis/` spine module. References to standalone packages below are historical.
> See `clarvis/brain/`, `clarvis/orch/cost_tracker.py`, `clarvis/cognition/metacognition.py`.


Complete walkthrough for installing and verifying Clarvis on a fresh machine.

## Prerequisites

| Requirement | Minimum | Recommended | Check |
|------------|---------|-------------|-------|
| Python | 3.10 | 3.12 | `python3 --version` |
| pip | 21.0 | latest | `pip --version` |
| git | 2.x | latest | `git --version` |
| SQLite | 3.35+ | 3.40+ | `sqlite3 --version` |
| Disk | 500 MB | 2 GB (with brain data) | |
| RAM | 1 GB | 4 GB (with ONNX embeddings) | |

Optional (depends on profile):
- **Node.js 18+** — only for OpenClaw Gateway profile
- **Docker** — only for Docker profile
- **systemd** — only for Full Stack profile (Linux)

## Quick Start

```bash
git clone https://github.com/GranusClarvis/clarvis.git
cd clarvis
bash scripts/install.sh
```

The guided installer will ask which profile to install. If unsure, choose **Standalone**.

## Installation Profiles

Clarvis supports four deployment profiles. The installer selects one and configures accordingly.

### 1. Standalone (recommended for most users)

Installs the Clarvis Python packages, CLI, and vector brain. No external services.

```
What you get:  clarvis CLI, brain (ChromaDB + ONNX), all Python packages
What you skip: OpenClaw gateway, cron schedule, chat channels
Best for:      Developers, contributors, experimentation
```

### 2. OpenClaw Gateway

Adds the OpenClaw agent gateway on top of Standalone. Provides chat integration
(Telegram, Discord) and the conscious-layer M2.5 session management.

```
What you get:  Everything in Standalone + OpenClaw gateway + channel config
Requires:      Node.js 18+, npm, OpenRouter API key
Best for:      Running Clarvis as a chat agent with Telegram/Discord
```

### 3. Full Stack

Complete dual-layer deployment: OpenClaw gateway (conscious) + system crontab
(subconscious). This is how the reference Clarvis instance runs.

```
What you get:  Everything in OpenClaw + cron schedule + systemd service
Requires:      Linux with systemd, Node.js 18+, Claude Code CLI
Best for:      Production-like deployment on a dedicated host
```

### 4. Docker

Containerized setup for development and testing. Stateless by design.

```
What you get:  Full Python stack in a container, persistent brain volume
Requires:      Docker, Docker Compose
Best for:      Quick evaluation, CI, isolated testing
```

```bash
# Try Clarvis without installing anything locally:
docker compose run clarvis              # runs self-contained demo
docker compose run clarvis clarvis brain health
docker compose run clarvis pytest -m "not slow"
docker compose run clarvis bash         # interactive shell
```

## Profile Comparison Matrix

| Feature | Standalone | OpenClaw | Full Stack | Docker |
|---------|-----------|----------|------------|--------|
| Python packages | Yes | Yes | Yes | Yes |
| CLI (`clarvis`) | Yes | Yes | Yes | Yes |
| Brain (ChromaDB) | Yes | Yes | Yes | Yes |
| Tests (`pytest`) | Yes | Yes | Yes | Yes |
| OpenClaw gateway | - | Yes | Yes | - |
| Chat channels | - | Telegram/Discord | Telegram/Discord | - |
| Cron schedule | - | - | Yes | - |
| systemd service | - | - | Yes | - |
| Claude Code spawning | - | - | Yes | - |
| Container isolation | - | - | - | Yes |

## Guided Installer Flow

The installer (`scripts/install.sh`) runs these steps:

1. **Environment check** — Python version, pip, git, disk space
2. **Profile selection** — Interactive menu or `--profile <name>` flag
3. **Package installation** — Sub-packages in dependency order, then main package
4. **Environment setup** — Creates `.env` from profile template, sets `CLARVIS_WORKSPACE`
5. **Profile-specific setup** — Gateway config, cron install, or Docker build
6. **First-run validation** — Automatic verification with PASS/WARN/FAIL summary

### Non-interactive Mode

```bash
# Install with a specific profile, no prompts
bash scripts/install.sh --profile standalone
bash scripts/install.sh --profile openclaw
bash scripts/install.sh --profile fullstack
bash scripts/install.sh --profile docker

# Additional flags
bash scripts/install.sh --profile standalone --no-brain   # Skip ChromaDB/ONNX
bash scripts/install.sh --profile standalone --dev         # Include ruff + pytest
```

## First-Run Validation

After installation, the installer runs `scripts/verify_install.sh` automatically.
You can also run it manually:

```bash
bash scripts/verify_install.sh
```

The verifier checks:
- **Core imports** — All `clarvis.*` modules load
- **Sub-packages** — `clarvis_db`, `clarvis_cost`, `clarvis_reasoning`
- **CLI** — All subcommands respond to `--help`
- **Brain** — ChromaDB + ONNX importable, brain health passes
- **Tests** — Canonical `pytest` discovery runs successfully
- **Profile-specific** — Gateway reachable, cron installed, Docker builds (per profile)

Output is a clear summary:

```
=== Results: 18 passed, 0 failed, 2 warnings (of 20 checks) ===
Installation verified successfully.
```

## First Run

After verification passes, try the self-contained demo:

```bash
clarvis demo            # store → search → recall → CLI health → heartbeat gate
clarvis demo --verbose  # same, with extra detail
```

This works on a fresh clone with an empty brain. It is also the default Docker command.

## Cron Schedule Setup

For Full Stack deployments, install the cron schedule using presets:

```bash
# List available presets
clarvis cron presets

# Preview what would be installed (dry-run, default)
clarvis cron install recommended

# Apply after reviewing
clarvis cron install recommended --apply

# Switch presets (replaces existing managed block)
clarvis cron install full --apply

# Remove all managed cron entries
clarvis cron remove --apply
```

**Presets:**

| Preset | Jobs | Description |
|--------|------|-------------|
| minimal | 12 | Monitoring + backup + weekly cleanup. No Claude Code spawning. |
| recommended | 27 | Core daily cycle + maintenance + 4x autonomous/day. |
| full | 46 | Complete schedule: 12x autonomous, 2x research, all benchmarks. |
| research | 40 | Extra research + dream engine + benchmarks. |

The installer wraps entries in sentinel comments (`>>> clarvis-managed >>>`) so
`clarvis cron remove` only removes managed entries — your other crontab lines
are preserved. A backup is saved to `memory/cron/crontab.backup` before changes.

A reference crontab is also available at `scripts/crontab.reference` for manual
review or `crontab scripts/crontab.reference` if you prefer direct control.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: clarvis_cost` | Sub-packages must install before main: `bash scripts/install.sh` |
| `ModuleNotFoundError: chromadb` | Install brain extras: `pip install -e ".[brain]"` |
| `clarvis: command not found` | Ensure pip's bin dir is in PATH, or use `python3 -m clarvis` |
| Brain health shows 0 memories | Normal on fresh install — memories accumulate through use |
| Pytest import errors | Run `bash scripts/verify_install.sh` to diagnose |
| OpenClaw gateway won't start | Check Node.js version (`node -v` >= 18), check `openclaw.json` |
| Docker build fails | Ensure Docker daemon running, check disk space |
| `python -m build` fails (PEP 668) | On PEP 668 systems (Ubuntu 24.04+), use `python -m build --no-isolation`. CI uses `actions/setup-python` where isolation works. |

## Upgrading

```bash
git pull
bash scripts/install.sh --profile standalone  # re-run with same profile
```

For OpenClaw gateway updates, use the safe update script:
```bash
bash scripts/safe_update.sh --check   # check available updates
bash scripts/safe_update.sh           # apply with backup + health checks
```

## Uninstalling

```bash
pip uninstall clarvis clarvis-db clarvis-cost clarvis-reasoning
# Remove data (optional):
rm -rf data/clarvisdb data/clarvisdb-local
```
