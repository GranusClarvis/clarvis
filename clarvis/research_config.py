"""Durable research auto-fill / replenishment control.

Single config file controls ALL research injection paths:
  - research_auto_fill:         Master switch (gates all below)
  - research_inject_from_papers: research_to_queue.py inject
  - research_discovery_fallback: cron_research.sh discovery when queue empty
  - research_bridge_monthly:     cron_reflection.sh monthly bridge

Config file: data/research_config.json
CLI: python3 -m clarvis.research_config status|enable|disable [--path KEY]
"""

import json
import os
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
CONFIG_FILE = os.path.join(WORKSPACE, "data", "research_config.json")

_VALID_KEYS = {
    "research_auto_fill",
    "research_inject_from_papers",
    "research_discovery_fallback",
    "research_bridge_monthly",
}

_DEFAULTS = {
    "research_auto_fill": False,
    "research_inject_from_papers": False,
    "research_discovery_fallback": False,
    "research_bridge_monthly": False,
}


def _load() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)


def _save(config: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    config["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(config, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def is_enabled(key: str = "research_auto_fill") -> bool:
    """Check if a research path is enabled. Master switch gates all sub-keys."""
    config = _load()
    # Master switch gates everything
    if not config.get("research_auto_fill", False):
        return False
    if key == "research_auto_fill":
        return True
    return bool(config.get(key, False))


def enable(key: str = "research_auto_fill", reason: str = "", who: str = "system") -> dict:
    """Enable a research path (or all if key is master switch)."""
    config = _load()
    if key == "research_auto_fill":
        for k in _VALID_KEYS:
            config[k] = True
    elif key in _VALID_KEYS:
        config[key] = True
    else:
        raise ValueError(f"Unknown key '{key}'. Valid: {sorted(_VALID_KEYS)}")
    config["updated_by"] = who
    config["reason"] = reason or f"Enabled {key}"
    _save(config)
    return config


def disable(key: str = "research_auto_fill", reason: str = "", who: str = "system") -> dict:
    """Disable a research path (or all if key is master switch)."""
    config = _load()
    if key == "research_auto_fill":
        for k in _VALID_KEYS:
            config[k] = False
    elif key in _VALID_KEYS:
        config[key] = False
    else:
        raise ValueError(f"Unknown key '{key}'. Valid: {sorted(_VALID_KEYS)}")
    config["updated_by"] = who
    config["reason"] = reason or f"Disabled {key}"
    _save(config)
    return config


def status() -> dict:
    """Return current config with effective states."""
    config = _load()
    master = config.get("research_auto_fill", False)
    effective = {}
    for k in sorted(_VALID_KEYS):
        raw = config.get(k, False)
        effective[k] = {"raw": raw, "effective": raw and (master or k == "research_auto_fill")}
    return {
        "config_file": CONFIG_FILE,
        "master_enabled": master,
        "paths": effective,
        "updated_at": config.get("updated_at", "unknown"),
        "updated_by": config.get("updated_by", "unknown"),
        "reason": config.get("reason", ""),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m clarvis.research_config status|enable|disable [--path KEY] [--reason TEXT] [--who NAME]")
        sys.exit(1)

    cmd = sys.argv[1]

    # Parse optional args
    key = "research_auto_fill"
    reason = ""
    who = "cli"
    for i, arg in enumerate(sys.argv):
        if arg == "--path" and i + 1 < len(sys.argv):
            key = sys.argv[i + 1]
        elif arg == "--reason" and i + 1 < len(sys.argv):
            reason = sys.argv[i + 1]
        elif arg == "--who" and i + 1 < len(sys.argv):
            who = sys.argv[i + 1]

    if cmd == "status":
        s = status()
        print(f"Research Auto-Fill: {'ON' if s['master_enabled'] else 'OFF'}")
        print(f"Config: {s['config_file']}")
        print(f"Updated: {s['updated_at']} by {s['updated_by']}")
        if s["reason"]:
            print(f"Reason: {s['reason']}")
        print()
        for k, v in s["paths"].items():
            marker = "ON" if v["effective"] else "OFF"
            print(f"  {k}: {marker}")
    elif cmd == "enable":
        result = enable(key, reason, who)
        print(f"Enabled: {key}")
        print(json.dumps(result, indent=2))
    elif cmd == "disable":
        result = disable(key, reason, who)
        print(f"Disabled: {key}")
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
