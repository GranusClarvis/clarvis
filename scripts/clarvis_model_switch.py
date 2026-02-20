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

# Session-based model switching
SESSION_FILE = os.path.expanduser("~/.openclaw/agents/main/sessions/sessions.json")
CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
CURRENT_SESSION_KEY = "agent:main:main"

# All models we want to use
ALLOWED_MODELS = {
    "coding": "minimax/minimax-m2.5",
    "reasoning": "z-ai/glm-5", 
    "difficult": "anthropic/claude-opus-4-6"
}

def ensure_model_allowed(model_id: str):
    """Add model to allowlist if not present - CRITICAL for model to work!"""
    import json
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    
    # Get current allowlist
    models = config.get("agents", {}).get("defaults", {}).get("models", {})
    
    # Add model if not present
    full_id = f"openrouter/{model_id}"
    if full_id not in models:
        models[full_id] = {}
        config.setdefault("agents", {}).setdefault("defaults", {}).setdefault("models", models)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Added {full_id} to allowed models")

def get_session_model() -> str:
    """Get current model for THIS session directly from sessions.json"""
    with open(SESSION_FILE, "r") as f:
        sessions = json.load(f)
    return sessions.get(CURRENT_SESSION_KEY, {}).get("model", "unknown")

def set_session_model(model_id: str) -> dict:
    """
    Switch model for current session by editing sessions.json AND config.
    This is how /model command works internally!
    
    Args:
        model_id: e.g., "minimax/minimax-m2.5", "z-ai/glm-5", "anthropic/claude-opus-4-6"
    
    Returns:
        {"old": "...", "new": "..."}
    """
    # CRITICAL: Ensure model is in allowlist first!
    ensure_model_allowed(model_id)
    
    # Get old model from session
    with open(SESSION_FILE, "r") as f:
        sessions = json.load(f)
    old_model = sessions.get(CURRENT_SESSION_KEY, {}).get("model", "unknown")
    
    # 1. Set session model (for current session)
    if CURRENT_SESSION_KEY in sessions:
        sessions[CURRENT_SESSION_KEY]["model"] = model_id
        sessions[CURRENT_SESSION_KEY]["modelProvider"] = "openrouter"
    
    with open(SESSION_FILE, "w") as f:
        json.dump(sessions, f, indent=2)
    
    # 2. ALSO set config primary (prevents reset on new messages!)
    full_model = f"openrouter/{model_id}" if not model_id.startswith("openrouter/") else model_id
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    config.setdefault("agents", {}).setdefault("defaults", {}).setdefault("model", {})["primary"] = full_model
    
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    
    return {"old": old_model, "new": model_id}

def get_current_model():
    """Get current primary model from config"""
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    return config.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "unknown")

def switch_config_model(model_id: str):
    """Switch model in config (for new sessions)"""
    with open(CONFIG_PATH, "r") as f:
        current_config = json.load(f)
    
    if "agents" not in current_config:
        current_config["agents"] = {}
    if "defaults" not in current_config["agents"]:
        current_config["agents"]["defaults"] = {}
    if "model" not in current_config["agents"]["defaults"]:
        current_config["agents"]["defaults"]["model"] = {}
    
    current_config["agents"]["defaults"]["model"]["primary"] = f"openrouter/{model_id}"
    
    with open(CONFIG_PATH, "w") as f:
        json.dump(current_config, f, indent=2)

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
            session_model = get_session_model()
            config_model = get_current_model()
            print(f"Current SESSION model: {session_model}")
            print(f"Current CONFIG model: {config_model}")
        
        elif cmd == "session" and len(sys.argv) > 2:
            # Switch THIS session's model directly (like /model command)
            model_id = sys.argv[2]
            result = set_session_model(model_id)
            print(f"Session model switched: {result['old']} -> {result['new']}")
        
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