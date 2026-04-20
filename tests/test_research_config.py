"""Tests for research auto-fill config controls."""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Create a temporary research config file."""
    cfg = tmp_path / "research_config.json"
    cfg.write_text(json.dumps({
        "research_auto_fill": False,
        "research_inject_from_papers": False,
        "research_discovery_fallback": False,
        "research_bridge_monthly": False,
        "updated_at": "2026-04-09T00:00:00+00:00",
        "updated_by": "test",
        "reason": "test default"
    }))
    monkeypatch.setattr("clarvis.research_config.CONFIG_FILE", str(cfg))
    return cfg


class TestIsEnabled:
    def test_all_off_by_default(self, config_file):
        from clarvis.research_config import is_enabled
        assert is_enabled("research_auto_fill") is False
        assert is_enabled("research_discovery_fallback") is False
        assert is_enabled("research_inject_from_papers") is False
        assert is_enabled("research_bridge_monthly") is False

    def test_master_off_blocks_sub_keys(self, config_file):
        """Sub-keys are blocked even if individually true when master is off."""
        from clarvis.research_config import is_enabled, _load, _save
        config = _load()
        config["research_discovery_fallback"] = True
        config["research_auto_fill"] = False
        _save(config)
        assert is_enabled("research_discovery_fallback") is False

    def test_master_on_enables_sub_keys(self, config_file):
        from clarvis.research_config import is_enabled, enable
        enable("research_auto_fill", reason="test", who="test")
        assert is_enabled("research_auto_fill") is True
        assert is_enabled("research_discovery_fallback") is True
        assert is_enabled("research_inject_from_papers") is True

    def test_missing_config_file_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr("clarvis.research_config.CONFIG_FILE",
                            str(tmp_path / "nonexistent.json"))
        from clarvis.research_config import is_enabled
        assert is_enabled() is False


class TestEnableDisable:
    def test_enable_master_enables_all(self, config_file):
        from clarvis.research_config import enable, _load
        enable("research_auto_fill", reason="operator wants it", who="operator")
        config = _load()
        assert config["research_auto_fill"] is True
        assert config["research_discovery_fallback"] is True
        assert config["research_inject_from_papers"] is True
        assert config["research_bridge_monthly"] is True
        assert config["updated_by"] == "operator"

    def test_disable_master_disables_all(self, config_file):
        from clarvis.research_config import enable, disable, _load
        enable("research_auto_fill")
        disable("research_auto_fill", reason="off again")
        config = _load()
        assert config["research_auto_fill"] is False
        assert config["research_discovery_fallback"] is False

    def test_enable_single_key(self, config_file):
        from clarvis.research_config import enable, _load
        enable("research_discovery_fallback")
        config = _load()
        assert config["research_discovery_fallback"] is True
        assert config["research_auto_fill"] is False  # master unchanged

    def test_invalid_key_raises(self, config_file):
        from clarvis.research_config import enable
        with pytest.raises(ValueError, match="Unknown key"):
            enable("bogus_key")


class TestStatus:
    def test_status_shows_effective_state(self, config_file):
        from clarvis.research_config import status, _load, _save
        config = _load()
        config["research_discovery_fallback"] = True
        config["research_auto_fill"] = False
        _save(config)
        s = status()
        assert s["paths"]["research_discovery_fallback"]["raw"] is True
        assert s["research_auto_fill"] is False


class TestQueueWriterGate:
    def test_research_source_blocked_when_off(self, config_file, monkeypatch):
        """Queue writer blocks research-source tasks when config is OFF."""
        from clarvis.queue.writer import add_tasks

        # Mock file operations to avoid touching real QUEUE.md
        monkeypatch.setattr("clarvis.queue.writer.QUEUE_FILE",
                            str(config_file.parent / "QUEUE.md"))
        monkeypatch.setattr("clarvis.queue.writer.STATE_FILE",
                            str(config_file.parent / "state.json"))

        result = add_tasks(
            ["[RESEARCH_FOO] Study advanced RAG patterns"],
            priority="P1",
            source="research_bridge"
        )
        assert result == []

    def test_non_research_source_not_blocked(self, config_file, monkeypatch):
        """Non-research sources are NOT blocked by research config."""
        from clarvis.queue.writer import add_tasks

        queue_file = config_file.parent / "QUEUE.md"
        queue_file.write_text("## P0\n\n## P1\n")
        monkeypatch.setattr("clarvis.queue.writer.QUEUE_FILE", str(queue_file))
        monkeypatch.setattr("clarvis.queue.writer.STATE_FILE",
                            str(config_file.parent / "state.json"))

        result = add_tasks(
            ["[FIX_BUG] Fix the broken thing"],
            priority="P0",
            source="self_model"
        )
        assert len(result) == 1
