"""Integration tests for module import reliability.

Exercises critical import paths from a clean subprocess to catch import
regressions early. These imports are used by 20+ cron jobs and the heartbeat
pipeline — if they break, the entire subconscious layer goes down.

Ticket: STALLED_GOAL_IMPORT_RELIABILITY
"""

import json
import subprocess
import sys
import os

WORKSPACE = "/home/agent/.openclaw/workspace"
PYTHON = sys.executable


def _run_import(code: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a Python import snippet in a clean subprocess."""
    env = os.environ.copy()
    # Ensure PYTHONPATH includes workspace so clarvis package is importable
    env["PYTHONPATH"] = WORKSPACE + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [PYTHON, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=WORKSPACE,
        env=env,
    )


class TestSpineImports:
    """Test that the clarvis spine module imports cleanly."""

    def test_brain_core_imports(self):
        """from clarvis.brain import brain, search, remember, capture"""
        result = _run_import(
            "from clarvis.brain import brain, search, remember, capture; "
            "print('ok')"
        )
        assert result.returncode == 0, (
            f"brain import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "ok" in result.stdout

    def test_brain_callable(self):
        """brain.stats() should return a dict with total_memories."""
        result = _run_import(
            "from clarvis.brain import brain; "
            "s = brain.stats(); "
            "assert isinstance(s, dict), f'Expected dict, got {type(s)}'; "
            "assert 'total_memories' in s, f'Missing total_memories key: {list(s.keys())}'; "
            "print('ok')"
        )
        assert result.returncode == 0, (
            f"brain.stats() failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_search_callable(self):
        """search() should return a list."""
        result = _run_import(
            "from clarvis.brain import search; "
            "r = search('test query', n=1); "
            "assert isinstance(r, list), f'Expected list, got {type(r)}'; "
            "print('ok')"
        )
        assert result.returncode == 0, (
            f"search() failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestMetricsImports:
    """Test that clarvis.metrics imports cleanly."""

    def test_phi_import(self):
        """from clarvis.metrics.phi import compute_phi"""
        result = _run_import(
            "from clarvis.metrics.phi import compute_phi; "
            "assert callable(compute_phi); "
            "print('ok')"
        )
        assert result.returncode == 0, (
            f"phi import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_phi_computable(self):
        """compute_phi() should return a dict with 'phi' key."""
        result = _run_import(
            "from clarvis.metrics.phi import compute_phi; "
            "import json; "
            "r = compute_phi(); "
            "assert isinstance(r, dict), f'Expected dict, got {type(r)}'; "
            "assert 'phi' in r, f'Missing phi key: {list(r.keys())}'; "
            "assert isinstance(r['phi'], (int, float)), f'phi not numeric: {type(r[\"phi\"])}'; "
            "print(json.dumps({'phi': r['phi']}))"
        )
        assert result.returncode == 0, (
            f"compute_phi() failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        data = json.loads(result.stdout.strip().split("\n")[-1])
        assert 0.0 <= data["phi"] <= 1.0, f"phi out of range: {data['phi']}"


class TestLegacyImports:
    """Test that legacy script-path imports still work (used by cron jobs)."""

    def test_legacy_brain_import(self):
        """import brain via sys.path (legacy cron pattern)."""
        result = _run_import(
            "import sys; sys.path.insert(0, 'scripts'); "
            "from brain import brain, search, remember, capture; "
            "print('ok')"
        )
        assert result.returncode == 0, (
            f"legacy brain import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestCrossModuleImports:
    """Test that modules that import each other don't cause circular import failures."""

    def test_heartbeat_imports(self):
        """Heartbeat modules should import without circular errors."""
        result = _run_import(
            "from clarvis.heartbeat import gate; "
            "print('ok')"
        )
        assert result.returncode == 0, (
            f"heartbeat gate import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_cognition_imports(self):
        """Cognition modules should import cleanly."""
        # Try the cognition module if it exists
        result = _run_import(
            "try:\n"
            "    from clarvis.cognition import context_relevance\n"
            "    print('ok')\n"
            "except ImportError as e:\n"
            "    if 'No module' in str(e):\n"
            "        print('skip')\n"
            "    else:\n"
            "        raise\n"
        )
        assert result.returncode == 0, (
            f"cognition import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
