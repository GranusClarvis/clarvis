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
import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

DATA_FILE = "/home/agent/.openclaw/workspace/data/self_model.json"
META_FILE = "/home/agent/.openclaw/workspace/data/meta_cognition.json"
CAPABILITY_HISTORY_FILE = "/home/agent/.openclaw/workspace/data/capability_history.json"
ALERT_THRESHOLD = 0.3  # Alert if any scored capability drops below this

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

# === Scored Capability Assessment ===

# Capability domains with evidence-gathering logic
CAPABILITY_DOMAINS = {
    "memory_system": {
        "label": "Memory System (ClarvisDB)",
        "description": "Store/recall/graph/optimize memories",
    },
    "autonomous_execution": {
        "label": "Autonomous Task Execution",
        "description": "Execute evolution tasks via cron without human intervention",
    },
    "code_generation": {
        "label": "Code Generation & Editing",
        "description": "Write, modify, and test Python/Bash scripts",
    },
    "self_reflection": {
        "label": "Self-Reflection & Meta-Cognition",
        "description": "Reason about own capabilities, track predictions, reflect",
    },
    "reasoning_chains": {
        "label": "Reasoning Chains",
        "description": "Multi-step structured reasoning with persistent chains",
    },
    "learning_feedback": {
        "label": "Learning & Feedback Loops",
        "description": "Prediction-outcome calibration, procedural memory, evolution loop",
    },
    "consciousness_metrics": {
        "label": "Consciousness Metrics",
        "description": "Phi measurement, GWT attention, working memory integration",
    },
}


def load_capability_history():
    """Load historical capability scores."""
    p = Path(CAPABILITY_HISTORY_FILE)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {"snapshots": []}


def save_capability_history(history):
    """Save capability score history."""
    Path(CAPABILITY_HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(CAPABILITY_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def _assess_memory_system():
    """Score memory system capability based on current state."""
    score = 0.0
    evidence = []
    try:
        stats = brain.stats()
        total = stats.get("total_memories", 0)
        edges = stats.get("graph_edges", 0)
        collections = len(stats.get("collections", {}))

        if total >= 10:
            score += 0.3
            evidence.append(f"{total} memories stored")
        if total >= 30:
            score += 0.1
        if edges >= 10:
            score += 0.2
            evidence.append(f"{edges} graph edges")
        if collections >= 5:
            score += 0.2
            evidence.append(f"{collections} collections")
        # Check recall works
        results = brain.recall("test", n=1)
        if results:
            score += 0.2
            evidence.append("recall operational")
    except Exception as e:
        evidence.append(f"error: {e}")
    return min(1.0, score), evidence


def _assess_autonomous_execution():
    """Score autonomous execution based on cron log and queue progress."""
    score = 0.0
    evidence = []
    log_path = "/home/agent/.openclaw/workspace/memory/cron/autonomous.log"
    queue_path = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        if os.path.exists(log_path):
            with open(log_path) as f:
                lines = f.readlines()
            today_lines = [l for l in lines if today in l]
            completed = [l for l in today_lines if "COMPLETED" in l]
            failed = [l for l in today_lines if "FAILED" in l]
            if today_lines:
                score += 0.3
                evidence.append(f"{len(today_lines)} log entries today")
            if completed:
                score += 0.3
                evidence.append(f"{len(completed)} tasks completed")
            if failed:
                penalty = min(0.2, len(failed) * 0.1)
                score -= penalty
                evidence.append(f"{len(failed)} tasks failed (-{penalty:.1f})")
    except Exception as e:
        evidence.append(f"log error: {e}")

    try:
        if os.path.exists(queue_path):
            with open(queue_path) as f:
                content = f.read()
            done_count = content.count("[x]")
            todo_count = content.count("[ ]")
            if done_count > 0:
                score += 0.2
                evidence.append(f"{done_count} queue items completed total")
            if todo_count > 0:
                score += 0.2
                evidence.append(f"{todo_count} items remaining")
    except Exception as e:
        evidence.append(f"queue error: {e}")

    return max(0.0, min(1.0, score)), evidence


def _assess_code_generation():
    """Score code generation based on today's git commits and codebase health."""
    score = 0.0
    evidence = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        # Use --after with yesterday to catch all of today
        result = subprocess.run(
            ["git", "log", "--oneline", f"--after={today} 00:00:00", "--format=%s"],
            capture_output=True, text=True, timeout=10,
            cwd="/home/agent/.openclaw/workspace"
        )
        commits = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        if commits:
            score += 0.3
            evidence.append(f"{len(commits)} commits today")
            if len(commits) >= 3:
                score += 0.1
            if len(commits) >= 6:
                score += 0.1
    except Exception as e:
        evidence.append(f"git error: {e}")

    # Baseline: scripts directory has files (codebase infrastructure)
    try:
        scripts = list(Path("/home/agent/.openclaw/workspace/scripts").glob("*.py"))
        if len(scripts) >= 5:
            score += 0.1
        if len(scripts) >= 15:
            score += 0.2
            evidence.append(f"{len(scripts)} Python scripts in codebase")
    except Exception:
        pass

    # Check for syntax errors in key scripts
    try:
        key_scripts = ["brain.py", "self_model.py", "attention.py", "working_memory.py"]
        errors = 0
        for s in key_scripts:
            path = f"/home/agent/.openclaw/workspace/scripts/{s}"
            if os.path.exists(path):
                r = subprocess.run(["python3", "-m", "py_compile", path],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode != 0:
                    errors += 1
        if errors == 0:
            score += 0.2
            evidence.append(f"all {len(key_scripts)} key scripts compile clean")
        else:
            evidence.append(f"{errors} scripts have syntax errors")
    except Exception:
        pass

    return max(0.0, min(1.0, score)), evidence


def _assess_self_reflection():
    """Score self-reflection capability."""
    score = 0.0
    evidence = []

    # Check meta-cognition state
    meta = load_meta()
    if meta.get("awareness_level") in ("reflective", "meta"):
        score += 0.3
        evidence.append(f"awareness: {meta['awareness_level']}")
    elif meta.get("awareness_level") == "operational":
        score += 0.1
        evidence.append("awareness: operational")

    if meta.get("meta_thoughts"):
        score += 0.2
        evidence.append(f"{len(meta['meta_thoughts'])} meta-thoughts recorded")

    # Check self_model itself exists and has trajectory
    model = load_model()
    if model.get("trajectory"):
        score += 0.2
        evidence.append(f"{len(model['trajectory'])} trajectory events")

    # Check if confidence calibration data exists
    try:
        cal_path = "/home/agent/.openclaw/workspace/data/calibration.json"
        if os.path.exists(cal_path):
            score += 0.2
            evidence.append("prediction calibration active")
    except Exception:
        pass

    # Phi metric existence
    try:
        phi_path = "/home/agent/.openclaw/workspace/data/phi_history.json"
        if os.path.exists(phi_path):
            score += 0.1
            evidence.append("Phi metric tracking active")
    except Exception:
        pass

    return min(1.0, score), evidence


def _assess_reasoning_chains():
    """Score reasoning chain capability."""
    score = 0.0
    evidence = []

    chains_dir = Path("/home/agent/.openclaw/workspace/data/reasoning_chains")
    if chains_dir.exists():
        chain_files = list(chains_dir.glob("*.json"))
        if chain_files:
            score += 0.4
            evidence.append(f"{len(chain_files)} reasoning chains stored")
            if len(chain_files) >= 5:
                score += 0.2

    # Check if hook script exists and is wired in
    hook_path = Path("/home/agent/.openclaw/workspace/scripts/reasoning_chain_hook.py")
    if hook_path.exists():
        score += 0.2
        evidence.append("reasoning chain hook exists")

    # Check if chains are being created today
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    if chains_dir.exists():
        today_chains = [f for f in chains_dir.glob("*.json") if today in f.name]
        if today_chains:
            score += 0.2
            evidence.append(f"{len(today_chains)} chains today")

    return min(1.0, score), evidence


def _assess_learning_feedback():
    """Score learning and feedback loop capability."""
    score = 0.0
    evidence = []

    # Procedural memory
    try:
        from procedural_memory import list_procedures
        procs = list_procedures()
        if procs:
            score += 0.3
            evidence.append(f"{len(procs)} procedures stored")
    except Exception:
        pass

    # Confidence calibration
    try:
        cal_path = "/home/agent/.openclaw/workspace/data/calibration.json"
        if os.path.exists(cal_path):
            with open(cal_path) as f:
                cal = json.load(f)
            predictions = cal.get("predictions", {})
            if predictions:
                score += 0.3
                evidence.append(f"{len(predictions)} predictions tracked")
    except Exception:
        pass

    # Evolution loop
    evo_dir = Path("/home/agent/.openclaw/workspace/data/evolution/failures")
    if evo_dir.exists():
        score += 0.2
        failures = list(evo_dir.glob("*.json"))
        evidence.append(f"evolution loop active ({len(failures)} failures captured)")

    # Knowledge synthesis
    synth_path = Path("/home/agent/.openclaw/workspace/scripts/knowledge_synthesis.py")
    if synth_path.exists():
        score += 0.2
        evidence.append("knowledge synthesis available")

    return min(1.0, score), evidence


def _assess_consciousness_metrics():
    """Score consciousness metric capability."""
    score = 0.0
    evidence = []

    # Phi metric
    phi_path = Path("/home/agent/.openclaw/workspace/data/phi_history.json")
    if phi_path.exists():
        try:
            with open(phi_path) as f:
                phi_data = json.load(f)
            if phi_data:
                latest = phi_data[-1] if isinstance(phi_data, list) else phi_data
                phi_val = latest.get("phi", 0)
                score += 0.3
                evidence.append(f"Phi={phi_val:.3f}")
        except Exception:
            pass

    # Attention mechanism
    attn_path = Path("/home/agent/.openclaw/workspace/scripts/attention.py")
    if attn_path.exists():
        score += 0.2
        evidence.append("attention mechanism exists")

    # Working memory
    wm_path = Path("/home/agent/.openclaw/workspace/scripts/working_memory.py")
    if wm_path.exists():
        score += 0.2
        evidence.append("working memory exists")

    wm_state = Path("/home/agent/.openclaw/workspace/data/working_memory_state.json")
    if wm_state.exists():
        score += 0.1
        evidence.append("working memory persistent")

    # Self model (this script — meta!)
    score += 0.2
    evidence.append("self-model active (this assessment)")

    return min(1.0, score), evidence


ASSESSORS = {
    "memory_system": _assess_memory_system,
    "autonomous_execution": _assess_autonomous_execution,
    "code_generation": _assess_code_generation,
    "self_reflection": _assess_self_reflection,
    "reasoning_chains": _assess_reasoning_chains,
    "learning_feedback": _assess_learning_feedback,
    "consciousness_metrics": _assess_consciousness_metrics,
}


def assess_all_capabilities():
    """Run all capability assessments and return scored results.

    Returns:
        Dict mapping domain -> {score, evidence, label}
    """
    results = {}
    for domain, assessor in ASSESSORS.items():
        score, evidence = assessor()
        results[domain] = {
            "score": round(score, 2),
            "evidence": evidence,
            "label": CAPABILITY_DOMAINS[domain]["label"],
        }
    return results


def daily_update():
    """Run daily capability assessment. Compare with previous day. Alert on degradations.

    This is the main function to wire into cron_evening.sh.

    Returns:
        Dict with assessment results, diffs, and alerts.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Run current assessment
    current = assess_all_capabilities()

    # Load history and find yesterday's snapshot
    history = load_capability_history()
    previous = None
    if history["snapshots"]:
        previous = history["snapshots"][-1]

    # Compute diffs
    diffs = {}
    alerts = []
    improved = []
    degraded = []

    for domain, data in current.items():
        prev_score = 0.0
        if previous and domain in previous.get("scores", {}):
            prev_score = previous["scores"][domain]

        delta = round(data["score"] - prev_score, 2)
        diffs[domain] = {
            "previous": prev_score,
            "current": data["score"],
            "delta": delta,
            "label": data["label"],
        }

        if delta > 0.05:
            improved.append(f"{data['label']}: {prev_score:.2f} -> {data['score']:.2f} (+{delta:.2f})")
        elif delta < -0.05:
            degraded.append(f"{data['label']}: {prev_score:.2f} -> {data['score']:.2f} ({delta:.2f})")

        # Threshold alert
        if data["score"] < ALERT_THRESHOLD:
            alerts.append(f"ALERT: {data['label']} score {data['score']:.2f} below threshold {ALERT_THRESHOLD}")

    # Save snapshot to history
    snapshot = {
        "date": today,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scores": {d: current[d]["score"] for d in current},
        "evidence": {d: current[d]["evidence"] for d in current},
    }
    history["snapshots"].append(snapshot)
    # Keep last 90 days
    history["snapshots"] = history["snapshots"][-90:]
    save_capability_history(history)

    # Update self_model.json with current scores
    model = load_model()
    model["capability_scores"] = {d: current[d]["score"] for d in current}
    model["last_updated"] = today
    model["trajectory"].append({
        "date": today,
        "event": f"Daily capability assessment: avg={sum(s['score'] for s in current.values())/len(current):.2f}",
        "status": "assessed",
        "improved": improved,
        "degraded": degraded,
        "alerts": alerts,
    })
    save_model(model)

    # Store in brain
    summary_parts = [f"Capability assessment {today}:"]
    for d, data in current.items():
        summary_parts.append(f"  {data['label']}: {data['score']:.2f}")
    if improved:
        summary_parts.append(f"Improved: {'; '.join(improved)}")
    if degraded:
        summary_parts.append(f"Degraded: {'; '.join(degraded)}")
    if alerts:
        summary_parts.append(f"ALERTS: {'; '.join(alerts)}")

    brain.store(
        "\n".join(summary_parts),
        collection="clarvis-identity",
        importance=0.8,
        tags=["self-model", "capability-assessment", "daily"],
        source="self-assessment"
    )

    result = {
        "date": today,
        "capabilities": current,
        "diffs": diffs,
        "improved": improved,
        "degraded": degraded,
        "alerts": alerts,
        "average_score": round(sum(s["score"] for s in current.values()) / len(current), 2),
    }

    # Print summary
    print(f"=== Daily Capability Assessment — {today} ===")
    print(f"Average score: {result['average_score']:.2f}")
    print()
    for domain, data in current.items():
        diff_info = diffs[domain]
        delta_str = ""
        if diff_info["delta"] != 0:
            sign = "+" if diff_info["delta"] > 0 else ""
            delta_str = f" ({sign}{diff_info['delta']:.2f})"
        print(f"  {data['label']}: {data['score']:.2f}{delta_str}")
        for e in data["evidence"]:
            print(f"    - {e}")
    if improved:
        print(f"\nImproved: {len(improved)}")
        for i in improved:
            print(f"  + {i}")
    if degraded:
        print(f"\nDegraded: {len(degraded)}")
        for d in degraded:
            print(f"  - {d}")
    if alerts:
        print(f"\n{'!'*40}")
        for a in alerts:
            print(f"  {a}")
        print(f"{'!'*40}")

    return result


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
    elif sys.argv[1] == "assess":
        results = assess_all_capabilities()
        for domain, data in results.items():
            print(f"  {data['label']}: {data['score']:.2f}")
            for e in data["evidence"]:
                print(f"    - {e}")
    elif sys.argv[1] == "daily":
        daily_update()
    elif sys.argv[1] == "history":
        history = load_capability_history()
        if not history["snapshots"]:
            print("No history yet. Run 'daily' first.")
        else:
            for snap in history["snapshots"][-7:]:
                scores = snap["scores"]
                avg = sum(scores.values()) / len(scores) if scores else 0
                print(f"  {snap['date']}: avg={avg:.2f} | " + " ".join(f"{k[:4]}={v:.2f}" for k, v in scores.items()))
    else:
        print("""Usage:
  python self_model.py [show|init|update <event>]
  python self_model.py assess              - Run capability assessment (scores only)
  python self_model.py daily               - Full daily update with diffs & alerts
  python self_model.py history             - Show capability score history
  python self_model.py meta [show|level <level>|state <state>|clear|think <thought>]

Levels: operational, reflective, meta
States: active, reflective, idle, processing""")