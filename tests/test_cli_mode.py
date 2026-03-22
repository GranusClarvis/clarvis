"""CLI-level tests for `python3 -m clarvis mode` subcommands."""

import importlib
import json

from typer.testing import CliRunner


def _make_cli(monkeypatch, tmp_path):
    """Return a fresh CLI app wired to an isolated tmp workspace."""
    monkeypatch.setenv("CLARVIS_WORKSPACE", str(tmp_path))
    (tmp_path / "data").mkdir(exist_ok=True)
    # Create an empty QUEUE.md so count_active_tasks returns 0
    mem = tmp_path / "memory" / "evolution"
    mem.mkdir(parents=True, exist_ok=True)
    (mem / "QUEUE.md").write_text("# Queue\n- [x] Done task\n")

    import clarvis.runtime.mode as mode_mod
    importlib.reload(mode_mod)
    import clarvis.cli_mode as cli_mod
    importlib.reload(cli_mod)
    return cli_mod.app


runner = CliRunner()


def test_show_default(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0
    assert "Mode: ge" in result.output


def test_show_json(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["show", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["mode"] == "ge"
    assert "policies" in data


def test_set_and_show(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["set", "passive", "--reason", "testing"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "switched"
    assert data["mode"] == "passive"

    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0
    assert "Mode: passive" in result.output


def test_set_with_alias(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["set", "maintenance"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["mode"] == "architecture"


def test_set_invalid_mode(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["set", "bogus"])
    assert result.exit_code == 1
    assert "unknown mode" in result.output.lower() or "unknown mode" in (result.stderr or "").lower()


def test_explain_valid(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["explain", "ge"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["allow_autonomous_execution"] is True


def test_explain_invalid_mode(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["explain", "nonexistent"])
    assert result.exit_code == 1


def test_apply_pending_no_pending(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["apply-pending"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "none"


def test_history_empty(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
    assert "No mode history" in result.output


def test_history_after_switches(monkeypatch, tmp_path):
    app = _make_cli(monkeypatch, tmp_path)
    runner.invoke(app, ["set", "passive"])
    runner.invoke(app, ["set", "ge"])
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
    events = json.loads(result.output)
    assert len(events) == 2
    assert events[0]["event"] == "mode_switched"


def test_set_deferred_with_active_tasks(monkeypatch, tmp_path):
    """When active tasks exist and --immediate is not set, switch is deferred."""
    app = _make_cli(monkeypatch, tmp_path)
    # Write a QUEUE.md with an active (in-progress) task
    qf = tmp_path / "memory" / "evolution" / "QUEUE.md"
    qf.write_text("# Queue\n- [~] In-progress task\n- [~] Another active\n")

    result = runner.invoke(app, ["set", "passive", "--reason", "test defer"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "pending"
    assert data["active_tasks"] == 2

    # Show should still display ge with pending passive
    result = runner.invoke(app, ["show"])
    assert "Mode: ge" in result.output
    assert "Pending: passive" in result.output


def test_set_immediate_overrides_defer(monkeypatch, tmp_path):
    """--immediate forces switch even with active tasks."""
    app = _make_cli(monkeypatch, tmp_path)
    qf = tmp_path / "memory" / "evolution" / "QUEUE.md"
    qf.write_text("# Queue\n- [~] In-progress task\n")

    result = runner.invoke(app, ["set", "passive", "--immediate"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "switched"
    assert data["mode"] == "passive"
