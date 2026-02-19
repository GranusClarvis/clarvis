#!/usr/bin/env python3
"""
Clarvis Model Config Switcher
Safely modify my own model config
"""

import json
import os
import subprocess

CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
BACKUP_PATH = os.path.expanduser("~/.openclaw/openclaw.json.model-switch.bak")

# Model mappings
MODEL_MAP = {
    "coding": "openrouter/minimax/minimax-m2.5",
    "reasoning": "openrouter/z-ai/glm-5", 
    "difficult": "openrouter/anthropic/claude-opus-4-6"
}

def get_current_model():
    """Get current primary model from config"""
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    return config.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "unknown")

def switch_model(mode: str) -> dict:
    """
    Switch to the model for the given mode.
    Modes: coding, reasoning, difficult
    """
    if mode not in MODEL_MAP:
        return {"error": f"Unknown mode: {mode}"}
    
    new_model = MODEL_MAP[mode]
    
    # Backup current config
    with open(CONFIG_PATH, "r") as f:
        current_config = json.load(f)
    
    with open(BACKUP_PATH, "w") as f:
        json.dump(current_config, f, indent=2)
    
    # Modify config
    if "agents" not in current_config:
        current_config["agents"] = {}
    if "defaults" not in current_config["agents"]:
        current_config["agents"]["defaults"] = {}
    if "model" not in current_config["agents"]["defaults"]:
        current_config["agents"]["defaults"]["model"] = {}
    
    old_model = current_config["agents"]["defaults"]["model"].get("primary", "unknown")
    current_config["agents"]["defaults"]["model"]["primary"] = new_model
    
    # Write config
    with open(CONFIG_PATH, "w") as f:
        json.dump(current_config, f, indent=2)
    
    return {
        "old_model": old_model,
        "new_model": new_model,
        "mode": mode,
        "backup": BACKUP_PATH
    }

def restore_backup():
    """Restore from backup if something went wrong"""
    if os.path.exists(BACKUP_PATH):
        with open(BACKUP_PATH, "r") as f:
            config = json.load(f)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        return True
    return False

# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "get":
            print(f"Current model: {get_current_model()}")
        
        elif cmd == "switch" and len(sys.argv) > 2:
            mode = sys.argv[2]
            result = switch_model(mode)
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Switched from {result['old_model']} to {result['new_model']} (mode: {result['mode']})")
                print(f"Backup: {result['backup']}")
        
        elif cmd == "restore":
            if restore_backup():
                print("Restored from backup")
            else:
                print("No backup found")
        
        else:
            print("Usage:")
            print("  model_switch.py get           # Show current model")
            print("  model_switch.py switch <mode>  # Switch mode (coding/reasoning/difficult)")
            print("  model_switch.py restore        # Restore from backup")
    else:
        print(f"Current model: {get_current_model()}")
        print(f"Config: {CONFIG_PATH}")