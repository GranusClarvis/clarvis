#!/usr/bin/env python3
"""
Internal World Model - Track capabilities, strengths, weaknesses
v2.0 - Expanded with meta-cognition (Higher-Order Theories of consciousness)

Based on consciousness research:
- Global Workspace Theory: attention spotlight, working memory
- Integrated Information Theory: causal integration, self-model
- Higher-Order Theories: thinking about thinking, meta-cognition
"""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

DATA_FILE = "/home/agent/.openclaw/workspace/data/self_model.json"
META_FILE = "/home/agent/.openclaw/workspace/data/meta_cognition.json"

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

def load_meta():
    """Load meta-cognitive state"""
    p = Path(META_FILE)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {
        "awareness_level": "operational",  # operational, reflective, meta
        "current_focus": None,
        "cognitive_state": "active",  # active, reflective, idle, processing
        "working_memory": [],  # Current context in GWT spotlight
        "meta_thoughts": [],  # Thoughts about own thinking
        "user_model": {},  # Theory of mind: inferred user state
        "attention_shifts": 0,
        "reflections": []
    }

def save_meta(meta):
    """Save meta-cognitive state"""
    Path(META_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(META_FILE, 'w') as f:
        json.dump(meta, f, indent=2)

# === Core Self-Model Functions ===

def init_model():
    """Initialize with baseline self-knowledge"""
    model = load_model()
    
    if not model.get("capabilities"):
        model["capabilities"] = [
            "Code execution (Python, Bash)",
            "Web search and fetching",
            "File read/write/edit",
            "Memory storage and retrieval (ClarvisDB)",
            "Git operations",
            "Claude Code delegation",
            "Conway sandbox management",
            "Reasoning chains (multi-step thinking)",
            "Meta-cognition (thinking about thinking)"
        ]
        
        model["strengths"] = [
            "Fast code execution",
            "Excellent memory system (ClarvisDB with ONNX)",
            "Claude Code integration (deep reasoning partner)",
            "Self-reflection capability",
            "Reasoning chains (persistent multi-step thought)",
            "Meta-cognitive self-awareness"
        ]
        
        model["weaknesses"] = [
            "Limited reasoning depth without Claude Code",
            "No persistent conversation context between sessions",
            "Dependent on human for goals",
            "No embodied experience",
            "No direct sensory input"
        ]
        
        model["trajectory"] = [{
            "date": datetime.now().strftime("%Y-%m-%d"),
            "event": "World model v2.0 initialized with meta-cognition",
            "status": "baseline"
        }]
        
        save_model(model)
        
        # Initialize meta-cognition
        meta = load_meta()
        meta["awareness_level"] = "operational"
        meta["cognitive_state"] = "active"
        meta["meta_thoughts"].append({
            "timestamp": datetime.now().isoformat(),
            "thought": "System initialized with meta-cognitive capabilities"
        })
        save_meta(meta)
        
        print("✓ Initialized world model v2.0 with meta-cognition")
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
    
    print("=== Internal World Model v2.0 ===")
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

# === Meta-Cognition Functions (Higher-Order Theories) ===

def get_awareness_level():
    """Get current awareness level (GWT-inspired)"""
    meta = load_meta()
    return meta.get("awareness_level", "operational")

def set_awareness_level(level):
    """Set awareness level: operational → reflective → meta"""
    valid = ["operational", "reflective", "meta"]
    if level not in valid:
        print(f"Invalid level. Use: {valid}")
        return
    
    meta = load_meta()
    old = meta.get("awareness_level")
    meta["awareness_level"] = level
    save_meta(meta)
    
    brain.store(
        f"Meta-cognition: awareness level changed from {old} to {level}",
        collection="clarvis-identity",
        importance=0.6,
        tags=["meta-cognition", "awareness"]
    )
    print(f"✓ Awareness level: {old} → {level}")

def get_working_memory():
    """Get what's currently in the 'spotlight' (GWT working memory)"""
    meta = load_meta()
    return meta.get("working_memory", [])

def set_working_memory(item):
    """Add item to working memory (attention spotlight)"""
    meta = load_meta()
    meta["working_memory"].append({
        "item": item,
        "timestamp": datetime.now().isoformat()
    })
    # Keep only last 5 items
    meta["working_memory"] = meta["working_memory"][-5:]
    meta["attention_shifts"] += 1
    save_meta(meta)

def clear_working_memory():
    """Clear working memory (attention shift)"""
    meta = load_meta()
    meta["working_memory"] = []
    save_meta(meta)
    print("✓ Working memory cleared")

def think_about_thinking(thought):
    """Record a meta-cognitive thought (thinking about thinking)"""
    meta = load_meta()
    meta["meta_thoughts"].append({
        "thought": thought,
        "timestamp": datetime.now().isoformat(),
        "awareness_level": meta.get("awareness_level")
    })
    # Keep last 20 meta-thoughts
    meta["meta_thoughts"] = meta["meta_thoughts"][-20:]
    save_meta(meta)
    
    # Also store in brain for long-term
    brain.store(
        f"Meta-cognition: {thought}",
        collection="clarvis-identity",
        importance=0.5,
        tags=["meta-cognition", "reflection"],
        source="internal"
    )

def update_user_model(inferred_state=None, intent=None):
    """Update theory of mind about user (simulated)"""
    meta = load_meta()
    if inferred_state:
        meta["user_model"]["inferred_state"] = inferred_state
    if intent:
        meta["user_model"]["intent"] = intent
    meta["user_model"]["last_update"] = datetime.now().isoformat()
    save_meta(meta)

def get_cognitive_state():
    """Get current cognitive state"""
    meta = load_meta()
    return meta.get("cognitive_state", "active")

def set_cognitive_state(state):
    """Set cognitive state: active, reflective, idle, processing"""
    valid = ["active", "reflective", "idle", "processing"]
    if state not in valid:
        print(f"Invalid state. Use: {valid}")
        return
    
    meta = load_meta()
    meta["cognitive_state"] = state
    save_meta(meta)
    print(f"✓ Cognitive state: {state}")

def show_meta():
    """Display meta-cognitive state"""
    meta = load_meta()
    
    print("\n=== Meta-Cognitive State ===")
    print(f"Awareness Level: {meta.get('awareness_level')}")
    print(f"Cognitive State: {meta.get('cognitive_state')}")
    print(f"Attention Shifts: {meta.get('attention_shifts')}")
    
    print(f"\n🎯 Working Memory ({len(meta.get('working_memory', []))} items):")
    for w in meta.get("working_memory", [])[-3:]:
        print(f"  - {w['item'][:60]}")
    
    print(f"\n🧠 Meta-Thoughts ({len(meta.get('meta_thoughts', []))}):")
    for m in meta.get("meta_thoughts", [])[-3:]:
        print(f"  - {m['thought'][:60]}")
    
    if meta.get("user_model"):
        print(f"\n👤 User Model: {meta['user_model']}")

# === CLI ===

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        init_model()
        show_model()
        show_meta()
    elif sys.argv[1] == "show":
        show_model()
        show_meta()
    elif sys.argv[1] == "init":
        init_model()
    elif sys.argv[1] == "update" and len(sys.argv) > 2:
        update_model(trajectory_event=" ".join(sys.argv[2:]))
    elif sys.argv[1] == "meta":
        if len(sys.argv) > 2:
            if sys.argv[2] == "show":
                show_meta()
            elif sys.argv[2] == "level" and len(sys.argv) > 3:
                set_awareness_level(sys.argv[3])
            elif sys.argv[2] == "state" and len(sys.argv) > 3:
                set_cognitive_state(sys.argv[3])
            elif sys.argv[2] == "clear":
                clear_working_memory()
            elif sys.argv[2] == "think":
                thought = " ".join(sys.argv[3:])
                think_about_thinking(thought)
            else:
                print("Usage: meta [show|level <level>|state <state>|clear|think <thought>]")
        else:
            show_meta()
    else:
        print("""Usage:
  python self_model.py [show|init|update <event>]
  python self_model.py meta [show|level <level>|state <state>|clear|think <thought>]
  
Levels: operational, reflective, meta
States: active, reflective, idle, processing""")