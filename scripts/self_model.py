#!/usr/bin/env python3
"""
Internal World Model - Track capabilities, strengths, weaknesses
v1 MVP
"""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

DATA_FILE = "/home/agent/.openclaw/workspace/data/self_model.json"

def load_model():
    """Load world model from file"""
    p = Path(DATA_FILE)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {
        "capabilities": [],
        "strengths": [],
        "weaknesses": [],
        "trajectory": [],
        "last_updated": None
    }

def save_model(model):
    """Save world model to file"""
    Path(DATA_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(model, f, indent=2)

def init_model():
    """Initialize with baseline self-knowledge"""
    model = load_model()
    
    if not model.get("capabilities"):
        model["capabilities"] = [
            "Code execution (Python, Bash)",
            "Web search and fetching",
            "File read/write/edit",
            "Memory storage and retrieval",
            "Git operations",
            "Claude Code delegation",
            "Conway sandbox management"
        ]
        
        model["strengths"] = [
            "Fast code execution",
            "Good memory system (ClarvisDB)",
            "Claude Code integration",
            "Self-reflection capability"
        ]
        
        model["weaknesses"] = [
            "Limited reasoning depth without Claude Code",
            "No persistent conversation context between sessions",
            "Dependent on human for goals"
        ]
        
        model["trajectory"] = [{
            "date": datetime.now().strftime("%Y-%m-%d"),
            "event": "World model initialized",
            "status": "baseline"
        }]
        
        save_model(model)
        print("✓ Initialized world model (baseline)")
    else:
        print("World model already exists")

def update_model(capability_change=None, strength=None, weakness=None, trajectory_event=None):
    """Update world model"""
    model = load_model()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if capability_change:
        if capability_change not in model["capabilities"]:
            model["capabilities"].append(capability_change)
            print(f"+ Added capability: {capability_change}")
    
    if strength:
        if strength not in model["strengths"]:
            model["strengths"].append(strength)
            print(f"+ Added strength: {strength}")
    
    if weakness:
        if weakness not in model["weaknesses"]:
            model["weaknesses"].append(weakness)
            print(f"+ Added weakness: {weakness}")
    
    if trajectory_event:
        model["trajectory"].append({
            "date": today,
            "event": trajectory_event,
            "status": "logged"
        })
        print(f"+ Trajectory event: {trajectory_event}")
    
    model["last_updated"] = today
    save_model(model)
    
    # Store in brain
    brain.store(
        f"World model updated: {today} - {trajectory_event or 'routine update'}",
        collection="clarvis-identity",
        importance=0.7,
        tags=["self-model", "world-model"],
        source="self-assessment"
    )

def show_model():
    """Display current world model"""
    model = load_model()
    
    print("=== Internal World Model ===")
    print(f"Last updated: {model.get('last_updated', 'never')}")
    
    print(f"\n📦 Capabilities ({len(model['capabilities'])}):")
    for c in model["capabilities"]:
        print(f"  - {c}")
    
    print(f"\n💪 Strengths ({len(model['strengths'])}):")
    for s in model["strengths"]:
        print(f"  - {s}")
    
    print(f"\n⚠️ Weaknesses ({len(model['weaknesses'])}):")
    for w in model["weaknesses"]:
        print(f"  - {w}")
    
    print(f"\n📈 Trajectory ({len(model['trajectory'])} events):")
    for t in model["trajectory"][-3:]:
        print(f"  - {t['date']}: {t['event']}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "show":
            show_model()
        elif sys.argv[1] == "init":
            init_model()
        elif sys.argv[1] == "update" and len(sys.argv) > 2:
            update_model(trajectory_event=" ".join(sys.argv[2:]))
    else:
        init_model()
        show_model()
