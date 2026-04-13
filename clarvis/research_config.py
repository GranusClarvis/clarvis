"""Durable auto-fill / replenishment control for queue and research injection.

Two independent master switches:
  - queue_auto_fill:            Controls all non-research, non-user auto-injection
  - research_auto_fill:         Controls all research injection paths (gates sub-keys below)
    - research_inject_from_papers: research_to_queue.py inject
    - research_discovery_fallback: cron_research.sh discovery when queue empty
    - research_bridge_monthly:     cron_reflection.sh monthly bridge

Config file: data/research_config.json
CLI: python3 -m clarvis.research_config status|enable|disable [--path KEY]
Skills: /autoqueue on|off, /autoresearch on|off
"""

import json
import os
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
CONFIG_FILE = os.path.join(WORKSPACE, "data", "research_config.json")

# Keys grouped by scope — enable/disable of a master only touches its own group
_RESEARCH_KEYS = {
    "research_auto_fill",
    "research_inject_from_papers",
    "research_discovery_fallback",
    "research_bridge_monthly",
}
_QUEUE_KEYS = {
    "queue_auto_fill",
}
_VALID_KEYS = _RESEARCH_KEYS | _QUEUE_KEYS

_DEFAULTS = {
    "queue_auto_fill": True,
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
    """Check if an auto-fill path is enabled.

    - queue_auto_fill: standalone master, True/False directly
    - research_auto_fill: master switch that gates all research sub-keys
    - research sub-keys: only effective if research_auto_fill is also True
    """
    config = _load()
    if key == "queue_auto_fill":
        return bool(config.get("queue_auto_fill", _DEFAULTS["queue_auto_fill"]))
    # Research keys: master gates everything
    if not config.get("research_auto_fill", False):
        return False
    if key == "research_auto_fill":
        return True
    return bool(config.get(key, False))


def enable(key: str = "research_auto_fill", reason: str = "", who: str = "system") -> dict:
    """Enable an auto-fill path. Each master only enables its own scope."""
    config = _load()
    if key not in _VALID_KEYS:
        raise ValueError(f"Unknown key '{key}'. Valid: {sorted(_VALID_KEYS)}")

    if key == "research_auto_fill":
        # Enable research master + all research sub-keys
        for k in _RESEARCH_KEYS:
            config[k] = True
    elif key == "queue_auto_fill":
        # Enable only queue master (no sub-keys to cascade)
        config["queue_auto_fill"] = True
    elif key in _RESEARCH_KEYS:
        # Enable a specific research sub-key
        config[key] = True
    config["updated_by"] = who
    config["reason"] = reason or f"Enabled {key}"
    _save(config)
    return config


def disable(key: str = "research_auto_fill", reason: str = "", who: str = "system") -> dict:
    """Disable an auto-fill path. Each master only disables its own scope."""
    config = _load()
    if key not in _VALID_KEYS:
        raise ValueError(f"Unknown key '{key}'. Valid: {sorted(_VALID_KEYS)}")

    if key == "research_auto_fill":
        # Disable research master + all research sub-keys
        for k in _RESEARCH_KEYS:
            config[k] = False
    elif key == "queue_auto_fill":
        # Disable only queue master
        config["queue_auto_fill"] = False
    elif key in _RESEARCH_KEYS:
        # Disable a specific research sub-key
        config[key] = False
    config["updated_by"] = who
    config["reason"] = reason or f"Disabled {key}"
    _save(config)
    return config


def status() -> dict:
    """Return current config with effective states."""
    config = _load()
    queue_master = config.get("queue_auto_fill", _DEFAULTS["queue_auto_fill"])
    research_master = config.get("research_auto_fill", False)
    effective = {}
    for k in sorted(_VALID_KEYS):
        raw = config.get(k, _DEFAULTS.get(k, False))
        if k == "queue_auto_fill":
            eff = raw
        elif k == "research_auto_fill":
            eff = raw
        else:
            # Research sub-keys: effective only if research master is on
            eff = raw and research_master
        effective[k] = {"raw": raw, "effective": eff}
    return {
        "config_file": CONFIG_FILE,
        "queue_auto_fill": queue_master,
        "research_auto_fill": research_master,
        "paths": effective,
        "updated_at": config.get("updated_at", "unknown"),
        "updated_by": config.get("updated_by", "unknown"),
        "reason": config.get("reason", ""),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m clarvis.research_config status|enable|disable [--path KEY]")
        print(f"  Valid keys: {', '.join(sorted(_VALID_KEYS))}")
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
        print(f"Queue Auto-Fill:    {'ON' if s['queue_auto_fill'] else 'OFF'}")
        print(f"Research Auto-Fill: {'ON' if s['research_auto_fill'] else 'OFF'}")
        print(f"Config: {s['config_file']}")
        print(f"Updated: {s['updated_at']} by {s['updated_by']}")
        if s["reason"]:
            print(f"Reason: {s['reason']}")
        print()
        for k, v in s["paths"].items():
            marker = "ON" if v["effective"] else "OFF"
            raw_marker = f" (raw={v['raw']})" if v["raw"] != v["effective"] else ""
            print(f"  {k}: {marker}{raw_marker}")
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
