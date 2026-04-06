"""clarvis welcome — first-run onboarding briefing and help surface.

Usage:
    clarvis welcome                # Full onboarding briefing
    clarvis welcome --short        # Quick command reference only
    clarvis welcome --json         # Machine-readable output
"""

from __future__ import annotations

import json as json_mod
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=False, pretty_exceptions_enable=False)

WORKSPACE = Path(os.environ.get(
    "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
))

# ── Onboarding content ─────────────────────────────────────────────────

GREETING = """\
╔══════════════════════════════════════════════════════════════╗
║                Welcome to Clarvis                           ║
║        Dual-layer cognitive agent system                    ║
╚══════════════════════════════════════════════════════════════╝"""

WHAT_IS_CLARVIS = """\
Clarvis is a cognitive agent with two execution layers:

  Conscious layer   Direct chat via OpenClaw gateway (MiniMax M2.5).
                    Handles conversation, reads digests, spawns tasks.

  Subconscious layer  Autonomous background work via Claude Code Opus.
                      Runs on a cron schedule: evolution, reflection,
                      research, maintenance — results surface to you
                      through daily digests.

The brain (ClarvisDB) is a local ChromaDB vector store with 10
collections, graph memory, and Hebbian learning — no data leaves
your machine unless you configure external APIs."""

QUICK_START = """\
── Quick Start ──────────────────────────────────────────────────

  Verify installation:
    clarvis doctor                 Run health checks on your setup
    clarvis demo                   Self-contained end-to-end demo

  Explore the brain:
    clarvis brain health           Full brain health report
    clarvis brain stats            Quick memory statistics
    clarvis brain search "topic"   Search stored memories

  Heartbeat (autonomous task cycle):
    clarvis heartbeat gate         Check if a heartbeat should run
    clarvis heartbeat run          Execute one heartbeat cycle

  Evolution queue:
    clarvis queue next             See next queued task
    clarvis queue list             List all pending tasks

  Cron schedule (background autonomy):
    clarvis cron presets           Available schedule presets
    clarvis cron list              Show installed cron entries
    clarvis cron status            Last-run timestamps

  Modes & metrics:
    clarvis mode show              Current operating mode
    clarvis metrics pi             Performance Index score
    clarvis metrics phi            Integrated information metric

  Cost tracking:
    clarvis cost report            API usage and cost summary

  Maintenance:
    clarvis maintenance status     Hygiene job status"""

KEY_FILES = """\
── Key Files ────────────────────────────────────────────────────

  SOUL.md        Agent identity and operating principles
  AGENTS.md      Session boot sequence and spawning rules
  SELF.md        Architecture diagram and self-modification protocol
  ROADMAP.md     6-phase evolution roadmap
  QUEUE.md       Task backlog (memory/evolution/QUEUE.md)
  CLAUDE.md      Full developer reference"""

NEXT_STEPS_TPL = """\
── What To Do Next ──────────────────────────────────────────────

  1. Run  clarvis doctor       to verify everything works
  2. Run  clarvis demo         to see the brain in action
  3. Read SOUL.md              to understand Clarvis's identity
  {cron_step}{gateway_step}
  Run  clarvis welcome --short  any time for a command cheat sheet.
"""


def _detect_profile() -> Optional[str]:
    """Read install profile from .env."""
    env_file = WORKSPACE / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            if line.startswith("CLARVIS_INSTALL_PROFILE="):
                return line.split("=", 1)[1].strip()
    return None


def _has_cron() -> bool:
    """Check if cron schedule is installed."""
    try:
        raw = subprocess.check_output(
            ["crontab", "-l"], text=True, stderr=subprocess.DEVNULL
        )
        return "clarvis-managed" in raw
    except Exception:
        return False


def _brain_summary() -> Optional[str]:
    """Get a one-line brain summary if available."""
    try:
        from clarvis.brain import brain
        stats = brain.stats()
        if isinstance(stats, dict):
            total = sum(v for v in stats.values() if isinstance(v, (int, float)))
            return f"{total} memories across {len(stats)} collections"
    except Exception:
        pass
    return None


def _build_next_steps(profile: Optional[str], has_cron: bool) -> str:
    """Build profile-aware next-steps section."""
    cron_step = ""
    gateway_step = ""

    if not has_cron and profile not in ("minimal", "docker", None):
        cron_step = "  4. Run  clarvis cron presets  to see background schedule options\n"

    if profile in ("openclaw", "fullstack"):
        n = 5 if cron_step else 4
        gateway_step = (
            f"  {n}. Start the gateway:       "
            "systemctl --user start openclaw-gateway.service\n"
        )

    return NEXT_STEPS_TPL.format(cron_step=cron_step, gateway_step=gateway_step)


# ── Commands ───────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def welcome(
    short: bool = typer.Option(False, "--short", "-s", help="Quick command reference only."),
    output_json: bool = typer.Option(False, "--json", help="Output JSON."),
):
    """First-run onboarding briefing — what Clarvis is and how to use it."""

    profile = _detect_profile()
    has_cron_schedule = _has_cron()
    brain_info = _brain_summary()

    if output_json:
        print(json_mod.dumps({
            "workspace": str(WORKSPACE),
            "profile": profile,
            "has_cron": has_cron_schedule,
            "brain": brain_info,
        }, indent=2))
        return

    if short:
        print(QUICK_START)
        return

    # Full onboarding briefing
    print(GREETING)
    print()

    # Status line
    status_parts = []
    if profile:
        status_parts.append(f"Profile: {profile}")
    status_parts.append(f"Workspace: {WORKSPACE}")
    if brain_info:
        status_parts.append(f"Brain: {brain_info}")
    if has_cron_schedule:
        status_parts.append("Cron: active")
    else:
        status_parts.append("Cron: not installed")
    print("  " + "  |  ".join(status_parts))
    print()

    print(WHAT_IS_CLARVIS)
    print()
    print(QUICK_START)
    print()
    print(KEY_FILES)
    print()
    print(_build_next_steps(profile, has_cron_schedule))
