#!/usr/bin/env python3
"""
Self-Assessment Script - Track cognitive growth metrics
v1 MVP
"""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

DATA_FILE = "/home/agent/.openclaw/workspace/data/self_report_metrics.json"

def load_metrics():
    """Load metrics from file"""
    p = Path(DATA_FILE)
    if p.exists():
        try:
            with open(p) as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            print(f"Warning: corrupted {DATA_FILE}, starting fresh")
    return {
        "daily": [],
        "goals_history": [],
        "queue_completed": 0,
        "reflections": 0
    }

def save_metrics(metrics):
    """Save metrics to file"""
    Path(DATA_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(metrics, f, indent=2)

def run_assessment():
    """Run self-assessment and store results"""
    print("=== Self-Assessment ===")
    
    # Load current state
    metrics = load_metrics()
    stats = brain.stats()
    goals = brain.get_goals()
    
    # Calculate metrics
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if already ran today
    if metrics.get("last_run") == today:
        print(f"Already ran today: {today}")
        return
    
    # Count today's memories
    today_memories = 0
    for m in brain.recall_recent(days=1, n=100):
        if today in m.get("metadata", {}).get("created_at", ""):
            today_memories += 1
    
    # Goal progress - extract percentages
    goal_progress = {}
    for g in goals:
        doc = g.get("document", "")
        # Extract percentage if present (e.g., "ClarvisDB: 90%")
        if ":" in doc:
            name, rest = doc.split(":", 1)
            if "%" in rest:
                pct = int(rest.split("%")[0].strip())
                goal_progress[name.strip()] = pct
    
    # Store daily snapshot
    snapshot = {
        "date": today,
        "memories": stats["total_memories"],
        "today_memories": today_memories,
        "graph_edges": stats["graph_edges"],
        "collections": len(stats["collections"]),
        "goals": len(goals),
        "goal_progress": goal_progress
    }
    
    # Track goal progress delta
    if metrics.get("goals_history"):
        prev_goals = metrics["goals_history"][-1].get("goal_progress", {})
        for name, pct in goal_progress.items():
            prev_pct = prev_goals.get(name, 0)
            delta = pct - prev_pct
            if delta > 0:
                print(f"  ↑ {name}: +{delta}%")
            elif delta < 0:
                print(f"  ↓ {name}: {delta}%")
    
    metrics["goals_history"].append(snapshot)
    metrics["goals_history"] = metrics["goals_history"][-90:]
    metrics["daily"] = metrics["daily"][-90:]
    metrics["last_run"] = today
    
    # Calculate growth
    if len(metrics["daily"]) >= 2:
        prev = metrics["daily"][-2]
        growth = snapshot["memories"] - prev["memories"]
        print(f"Memory growth: +{growth} today")
    
    # Store in brain
    brain.store(
        f"Self-report: {today} - {stats['total_memories']} total memories, {today_memories} added today, {stats['graph_edges']} graph edges",
        collection="clarvis-memories",
        importance=0.6,
        tags=["self-report", "metrics", today],
        source="self-assessment"
    )
    
    save_metrics(metrics)
    
    print(f"✓ Assessment complete: {today_memories} memories added today")
    print(f"  Total: {stats['total_memories']} memories, {stats['graph_edges']} edges")

if __name__ == "__main__":
    run_assessment()
