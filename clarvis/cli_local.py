"""clarvis local — zero-API-key local model quickstart.

Usage:
    clarvis local status       # Show Ollama status and available models
    clarvis local setup        # Guided zero-API setup (install check + model pull)
    clarvis local test         # Run zero-API test suite
    clarvis local start        # Start Ollama service
    clarvis local stop         # Stop Ollama service

Wraps the local_model_harness.sh with a Python CLI for discoverability.
All operations use local Ollama models — no API keys required.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = Path(os.environ.get(
    "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
))
HARNESS = WORKSPACE / "scripts" / "infra" / "local_model_harness.sh"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-vl:4b")


def _find_ollama() -> str | None:
    """Find the Ollama binary."""
    if os.environ.get("OLLAMA_BIN"):
        return os.environ["OLLAMA_BIN"]
    w = shutil.which("ollama")
    if w:
        return w
    default = os.path.expanduser("~/.local/ollama/bin/ollama")
    if os.path.isfile(default) and os.access(default, os.X_OK):
        return default
    return None


def _run_harness(cmd: str) -> int:
    """Run local_model_harness.sh with the given subcommand."""
    if not HARNESS.is_file():
        print(f"Error: harness script not found at {HARNESS}")
        return 1
    r = subprocess.run(
        ["bash", str(HARNESS), cmd],
        cwd=str(WORKSPACE),
    )
    return r.returncode


@app.command()
def status():
    """Show Ollama status and available local models."""
    raise typer.Exit(_run_harness("status"))


@app.command()
def start():
    """Start the Ollama service."""
    raise typer.Exit(_run_harness("start"))


@app.command()
def stop():
    """Stop the Ollama service."""
    raise typer.Exit(_run_harness("stop"))


@app.command()
def test():
    """Run the zero-API-key test suite."""
    raise typer.Exit(_run_harness("test"))


@app.command()
def setup():
    """Guided zero-API-key quickstart.

    Walks through: Ollama check, model pull, brain verification,
    and runs a quick smoke test — all without any API keys.
    """
    print("=== Clarvis Local Model Quickstart ===")
    print()
    print("This sets up Clarvis with local models only — no API keys needed.")
    print(f"Model:    {OLLAMA_MODEL} (3.3 GB, CPU-only ~7 tok/s)")
    print(f"Endpoint: {OLLAMA_HOST}")
    print()

    # Step 1: Check Ollama
    ollama = _find_ollama()
    if not ollama:
        print("STEP 1: Ollama binary — NOT FOUND")
        print()
        print("  Install Ollama:")
        print("    curl -fsSL https://ollama.com/install.sh | sh")
        print()
        print("  Or download from: https://ollama.com")
        print()
        print("After installing, re-run: clarvis local setup")
        raise typer.Exit(1)

    print(f"STEP 1: Ollama binary — OK ({ollama})")

    # Step 2: Start service
    print()
    api_ok = False
    try:
        r = subprocess.run(
            ["curl", "-sf", f"{OLLAMA_HOST}/api/version"],
            capture_output=True, timeout=5,
        )
        api_ok = r.returncode == 0
    except Exception:
        pass

    if api_ok:
        print("STEP 2: Ollama API — already running")
    else:
        print("STEP 2: Ollama API — starting...")
        try:
            subprocess.run(
                ["systemctl", "--user", "start", "ollama.service"],
                capture_output=True, timeout=10,
            )
            import time
            for _ in range(10):
                try:
                    r = subprocess.run(
                        ["curl", "-sf", f"{OLLAMA_HOST}/api/version"],
                        capture_output=True, timeout=3,
                    )
                    if r.returncode == 0:
                        api_ok = True
                        break
                except Exception:
                    pass
                time.sleep(1)
        except Exception:
            pass

        if api_ok:
            print("         Ollama API — OK")
        else:
            print("         Ollama API — FAILED to start")
            print()
            print("  Try manually: ollama serve &")
            print("  Or:           systemctl --user start ollama.service")
            raise typer.Exit(1)

    # Step 3: Model availability
    print()
    try:
        r = subprocess.run(
            [ollama, "list"], capture_output=True, text=True, timeout=10,
        )
        has_model = OLLAMA_MODEL.split(":")[0] in r.stdout
    except Exception:
        has_model = False

    if has_model:
        print(f"STEP 3: Model {OLLAMA_MODEL} — already available")
    else:
        print(f"STEP 3: Model {OLLAMA_MODEL} — pulling (this may take a few minutes)...")
        pull_r = subprocess.run(
            [ollama, "pull", OLLAMA_MODEL],
            timeout=600,
        )
        if pull_r.returncode == 0:
            print(f"         Model {OLLAMA_MODEL} — OK")
        else:
            print(f"         Model {OLLAMA_MODEL} — FAILED to pull")
            raise typer.Exit(1)

    # Step 4: Clarvis import check
    print()
    try:
        import clarvis  # noqa: F401
        print("STEP 4: Clarvis imports — OK")
    except Exception as e:
        print(f"STEP 4: Clarvis imports — FAILED ({e})")
        print("  Run: pip install -e . (from workspace root)")
        raise typer.Exit(1)

    # Step 5: Brain check (local ONNX, no API)
    print()
    try:
        from clarvis.brain import search
        results = search("test query", n=1)
        if isinstance(results, list):
            print("STEP 5: Brain search (local ONNX) — OK")
        else:
            print("STEP 5: Brain search — unexpected result type")
    except Exception as e:
        print(f"STEP 5: Brain search — WARN ({str(e)[:60]})")
        print("  Brain needs ChromaDB: pip install -e '.[brain]'")

    # Summary
    print()
    print("=== Setup Complete ===")
    print()
    print("What works without API keys:")
    print("  - clarvis brain search/stats/health   (local ONNX embeddings)")
    print("  - clarvis doctor                      (health verification)")
    print("  - clarvis demo                        (self-contained demo)")
    print(f"  - Local inference via Ollama           ({OLLAMA_MODEL})")
    print("  - All import checks and unit tests")
    print()
    print("What needs API keys:")
    print("  - Claude Code spawning (autonomous evolution)")
    print("  - OpenRouter model routing")
    print("  - Telegram bot reports")
    print()
    print("Next steps:")
    print("  clarvis local test     # Run full zero-API test suite")
    print("  clarvis doctor         # Comprehensive health check")
    print("  clarvis brain health   # Brain status")
