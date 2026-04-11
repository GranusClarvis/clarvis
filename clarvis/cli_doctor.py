"""clarvis doctor — post-install health verification.

Usage:
    clarvis doctor             # Run all checks
    clarvis doctor --profile standalone  # Run profile-specific checks too
    clarvis doctor --json      # Output JSON (for scripting)

Produces PASS/WARN/FAIL for:
  - Core imports and CLI
  - Brain initialization (ChromaDB + ONNX)
  - Memory paths and data directories
  - Cron readiness (scripts, crontab)
  - Model wiring (API keys, endpoints)
  - Feature availability (heartbeat, reasoning, queue, calibration, PI)
  - Model connectivity (OpenRouter API, Telegram bot)
  - Harness integration (OpenClaw, Hermes, Ollama)
"""

import importlib
import json as json_mod
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=False, pretty_exceptions_enable=False)

WORKSPACE = Path(os.environ.get(
    "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
))

# ── Result tracking ─────────────────────────────────────────────────────

class _Results:
    def __init__(self):
        self.checks: list[dict] = []

    def _add(self, status: str, label: str, detail: str = ""):
        self.checks.append({"status": status, "label": label, "detail": detail})

    def passed(self, label: str, detail: str = ""):
        self._add("PASS", label, detail)

    def warned(self, label: str, detail: str = ""):
        self._add("WARN", label, detail)

    def failed(self, label: str, detail: str = ""):
        self._add("FAIL", label, detail)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c["status"] == "PASS")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c["status"] == "WARN")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c["status"] == "FAIL")


def _try_import(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


def _cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run_quiet(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    """Run a command, return (success, output)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip()
    except Exception as e:
        return False, str(e)


# ── Check categories ────────────────────────────────────────────────────

def _check_core_imports(r: _Results):
    """Verify core Python imports work."""
    for mod in ["clarvis", "clarvis.cli", "clarvis.heartbeat",
                "clarvis.cognition", "clarvis.context", "clarvis.runtime"]:
        if _try_import(mod):
            r.passed(f"import {mod}")
        else:
            r.failed(f"import {mod}")

    # Spine modules
    for mod, label in [
        ("clarvis.orch.cost_tracker", "cost tracker"),
        ("clarvis.orch.queue_engine", "queue engine"),
        ("clarvis.cognition.reasoning", "reasoning"),
    ]:
        if _try_import(mod):
            r.passed(f"import {label}")
        else:
            r.warned(f"import {label}")


def _check_cli(r: _Results):
    """Verify CLI subcommands respond."""
    ok, _ = _run_quiet([sys.executable, "-m", "clarvis", "--help"])
    if ok:
        r.passed("clarvis --help")
    else:
        r.failed("clarvis --help")

    for sub in ["brain", "cron", "heartbeat", "mode", "queue"]:
        ok, _ = _run_quiet([sys.executable, "-m", "clarvis", sub, "--help"])
        if ok:
            r.passed(f"clarvis {sub} --help")
        else:
            r.warned(f"clarvis {sub} --help")


def _check_brain(r: _Results):
    """Check brain (ChromaDB + ONNX) availability."""
    if _try_import("chromadb"):
        r.passed("chromadb importable")
    else:
        r.warned("chromadb importable", "pip install chromadb")

    if _try_import("onnxruntime"):
        r.passed("onnxruntime importable")
    else:
        r.warned("onnxruntime importable", "pip install onnxruntime")

    # Try actual brain init
    try:
        from clarvis.brain import brain
        stats = brain.stats()
        if isinstance(stats, dict):
            total = stats.get("total_memories", 0)
            r.passed("brain.stats()", f"{total} memories")
        else:
            r.passed("brain.stats()")
    except Exception as e:
        r.warned("brain.stats()", str(e)[:80])

    # Brain health
    ok, out = _run_quiet([sys.executable, "-m", "clarvis", "brain", "health"], timeout=30)
    if ok:
        r.passed("clarvis brain health")
    else:
        r.warned("clarvis brain health", out[:80] if out else "failed")


def _check_memory_paths(r: _Results):
    """Verify expected directory structure exists."""
    dirs = {
        "memory/": WORKSPACE / "memory",
        "memory/cron/": WORKSPACE / "memory" / "cron",
        "memory/evolution/": WORKSPACE / "memory" / "evolution",
        "data/": WORKSPACE / "data",
        "data/clarvisdb/": WORKSPACE / "data" / "clarvisdb",
        "monitoring/": WORKSPACE / "monitoring",
        "scripts/cron/": WORKSPACE / "scripts" / "cron",
    }
    for label, path in dirs.items():
        if path.is_dir():
            r.passed(f"dir {label}")
        else:
            r.failed(f"dir {label}", f"missing: {path}")

    # Key files
    files = {
        ".env": WORKSPACE / ".env",
        "QUEUE.md": WORKSPACE / "memory" / "evolution" / "QUEUE.md",
    }
    for label, path in files.items():
        if path.is_file():
            r.passed(f"file {label}")
        else:
            r.warned(f"file {label}", f"missing: {path}")


def _check_cron_readiness(r: _Results):
    """Check cron scripts exist and crontab state."""
    cron_dir = WORKSPACE / "scripts" / "cron"
    essential = ["cron_env.sh", "lock_helper.sh", "cron_autonomous.sh",
                 "cron_morning.sh", "cron_evening.sh"]
    for script in essential:
        path = cron_dir / script
        if path.is_file():
            r.passed(f"script {script}")
        else:
            r.warned(f"script {script}", f"missing: {path}")

    # Check crontab for managed block
    try:
        raw = subprocess.check_output(
            ["crontab", "-l"], text=True, stderr=subprocess.DEVNULL
        )
        if "clarvis-managed" in raw:
            count = sum(1 for line in raw.splitlines()
                       if line.strip() and not line.strip().startswith("#")
                       and "scripts/" in line)
            r.passed("crontab managed block", f"{count} active entries")
        else:
            r.warned("crontab managed block",
                     "not installed (run: clarvis cron install <preset> --apply)")
    except (subprocess.CalledProcessError, FileNotFoundError):
        r.warned("crontab", "no crontab configured")


def _check_feature_availability(r: _Results):
    """Check which Clarvis features are operational."""
    # Heartbeat pipeline
    for script, label in [
        ("pipeline/heartbeat_gate.py", "heartbeat gate"),
        ("pipeline/heartbeat_preflight.py", "heartbeat preflight"),
        ("pipeline/heartbeat_postflight.py", "heartbeat postflight"),
    ]:
        if (WORKSPACE / "scripts" / script).is_file():
            r.passed(f"feature: {label}")
        else:
            r.warned(f"feature: {label}", f"scripts/{script} missing")

    # Reasoning engine
    try:
        from clarvis.cognition.reasoning import reasoner
        meta = reasoner._load_meta()
        total = meta.get("total_sessions", 0)
        r.passed("feature: reasoning engine", f"{total} sessions")
    except Exception as e:
        r.warned("feature: reasoning engine", str(e)[:60])

    # Queue engine
    try:
        from clarvis.orch.queue_engine import QueueEngine
        r.passed("feature: queue engine")
    except Exception:
        r.warned("feature: queue engine", "import failed")

    # Cognitive workspace
    cw_state = WORKSPACE / "data" / "cognitive_workspace" / "workspace_state.json"
    if cw_state.is_file():
        r.passed("feature: cognitive workspace")
    else:
        r.warned("feature: cognitive workspace", "no state file")

    # Context compressor
    if _try_import("clarvis.context"):
        r.passed("feature: context compressor")
    else:
        r.warned("feature: context compressor")

    # Confidence/calibration
    cal_file = WORKSPACE / "data" / "calibration" / "predictions.jsonl"
    if cal_file.is_file():
        try:
            line_count = sum(1 for _ in open(cal_file))
            r.passed("feature: calibration", f"{line_count} predictions")
        except Exception:
            r.passed("feature: calibration")
    else:
        r.warned("feature: calibration", "no predictions file")

    # Performance benchmark
    pi_file = WORKSPACE / "data" / "performance_metrics.json"
    if pi_file.is_file():
        r.passed("feature: performance index")
    else:
        r.warned("feature: performance index", "no metrics file")


def _check_model_connectivity(r: _Results):
    """Test actual model API connectivity (non-destructive)."""
    env_file = WORKSPACE / ".env"
    if not env_file.is_file():
        r.warned("connectivity: .env", "missing")
        return

    # Load env vars from .env
    env_vars = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env_vars[key.strip()] = val.strip().strip('"').strip("'")

    # Test OpenRouter connectivity (lightweight models endpoint)
    api_key = env_vars.get("OPENROUTER_API_KEY", "")
    if api_key and api_key.startswith("sk-or-"):
        ok, out = _run_quiet([
            "curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}",
            "-H", f"Authorization: Bearer {api_key}",
            "https://openrouter.ai/api/v1/models"
        ], timeout=10)
        if ok and out.strip() == "200":
            r.passed("connectivity: OpenRouter API")
        elif ok:
            r.warned("connectivity: OpenRouter API", f"HTTP {out.strip()}")
        else:
            r.warned("connectivity: OpenRouter API", "unreachable or key invalid")
    else:
        r.warned("connectivity: OpenRouter API", "no key configured")

    # Test Telegram bot (getMe — no side effects)
    tg_token = env_vars.get("TELEGRAM_BOT_TOKEN", "")
    if tg_token:
        ok, out = _run_quiet([
            "curl", "-sf",
            f"https://api.telegram.org/bot{tg_token}/getMe"
        ], timeout=10)
        if ok and "ok" in out.lower():
            r.passed("connectivity: Telegram bot")
        else:
            r.warned("connectivity: Telegram bot", "API call failed")
    else:
        r.warned("connectivity: Telegram bot", "no token configured")


def _check_model_wiring(r: _Results):
    """Check API key and model endpoint availability."""
    # Check .env for key indicators
    env_file = WORKSPACE / ".env"
    has_openrouter = False
    has_telegram = False
    if env_file.is_file():
        content = env_file.read_text()
        has_openrouter = "OPENROUTER_API_KEY" in content and "sk-or-" in content
        has_telegram = "TELEGRAM_BOT_TOKEN" in content

    if has_openrouter:
        r.passed("OpenRouter API key", "configured in .env")
    else:
        r.warned("OpenRouter API key", "not found in .env (needed for Claude Code spawning)")

    if has_telegram:
        r.passed("Telegram bot token", "configured in .env")
    else:
        r.warned("Telegram bot token", "not found in .env (needed for reports)")

    # Check Claude Code binary
    claude_bin = os.path.expanduser("~/.local/bin/claude")
    if os.path.isfile(claude_bin) and os.access(claude_bin, os.X_OK):
        r.passed("Claude Code binary", claude_bin)
    elif _cmd_exists("claude"):
        r.passed("Claude Code binary", "in PATH")
    else:
        r.warned("Claude Code binary", "not found (needed for autonomous tasks)")


def _check_profile(r: _Results, profile: str):
    """Run profile-specific checks."""
    if profile in ("openclaw", "fullstack"):
        if _cmd_exists("openclaw") or Path(
            os.path.expanduser("~/.npm-global/lib/node_modules/openclaw/dist/index.js")
        ).is_file():
            r.passed("OpenClaw installed")
        else:
            r.warned("OpenClaw installed", "npm install -g openclaw")

    if profile == "fullstack":
        ok, _ = _run_quiet(["systemctl", "--user", "is-enabled", "openclaw-gateway.service"])
        if ok:
            r.passed("systemd service enabled")
        else:
            r.warned("systemd service enabled",
                     "systemctl --user enable openclaw-gateway.service")

    if profile == "hermes":
        if _cmd_exists("hermes") or _try_import("hermes_agent"):
            r.passed("hermes-agent available")
        else:
            r.warned("hermes-agent available", "pip install hermes-agent")

    if profile == "local":
        ollama_bin = os.environ.get("OLLAMA_BIN") or shutil.which("ollama") or \
            os.path.expanduser("~/.local/ollama/bin/ollama")
        if os.path.isfile(ollama_bin) and os.access(ollama_bin, os.X_OK):
            r.passed("Ollama binary", ollama_bin)
        else:
            r.warned("Ollama binary", "not found (install from https://ollama.com)")

        ok, out = _run_quiet(["curl", "-sf", "http://127.0.0.1:11434/api/version"])
        if ok:
            r.passed("Ollama API reachable")
        else:
            r.warned("Ollama API reachable", "start with: ollama serve")


# ── Main command ────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def doctor(
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p",
        help="Run profile-specific checks (minimal|standalone|openclaw|fullstack|hermes|local)."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output JSON instead of human-readable."),
):
    """Post-install doctor: PASS/WARN/FAIL verification of Clarvis setup."""
    r = _Results()

    # Detect profile from .env if not specified
    if not profile:
        env_file = WORKSPACE / ".env"
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                if line.startswith("CLARVIS_INSTALL_PROFILE="):
                    profile = line.split("=", 1)[1].strip()
                    break

    if not output_json:
        print("=== Clarvis Doctor ===")
        print(f"Workspace: {WORKSPACE}")
        if profile:
            print(f"Profile:   {profile}")
        print()

    # Run check categories
    sections = [
        ("Core Imports", _check_core_imports),
        ("CLI", _check_cli),
        ("Brain", _check_brain),
        ("Memory Paths", _check_memory_paths),
        ("Cron Readiness", _check_cron_readiness),
        ("Model Wiring", _check_model_wiring),
        ("Feature Availability", _check_feature_availability),
        ("Model Connectivity", _check_model_connectivity),
    ]

    for section_name, check_fn in sections:
        if not output_json:
            print(f"{section_name}:")
        start = len(r.checks)
        check_fn(r)
        if not output_json:
            for c in r.checks[start:]:
                status = c["status"]
                label = c["label"]
                detail = f" ({c['detail']})" if c["detail"] else ""
                print(f"  {status:4s}  {label}{detail}")
            print()

    # Profile-specific
    if profile:
        if not output_json:
            print(f"Profile ({profile}):")
        start = len(r.checks)
        _check_profile(r, profile)
        if not output_json:
            for c in r.checks[start:]:
                status = c["status"]
                label = c["label"]
                detail = f" ({c['detail']})" if c["detail"] else ""
                print(f"  {status:4s}  {label}{detail}")
            print()

    # Summary
    total = len(r.checks)
    if output_json:
        print(json_mod.dumps({
            "workspace": str(WORKSPACE),
            "profile": profile,
            "passed": r.pass_count,
            "warnings": r.warn_count,
            "failed": r.fail_count,
            "total": total,
            "checks": r.checks,
        }, indent=2))
    else:
        print(f"=== Results: {r.pass_count} passed, {r.fail_count} failed, "
              f"{r.warn_count} warnings (of {total} checks) ===")
        if r.fail_count > 0:
            print("\nSome checks failed. Run with --json for details.")
        elif r.warn_count > 0:
            print("\nAll critical checks passed. Warnings are optional features.")
        else:
            print("\nAll checks passed.")

    raise typer.Exit(1 if r.fail_count > 0 else 0)
