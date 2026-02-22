#!/usr/bin/env python3
"""
Clarvis Smart Model Handover System
Analyze task → Plan with GLM-5 → Execute with M2.5
"""

import json
import os
from datetime import datetime, timezone

PLANS_DIR = "/home/agent/.openclaw/workspace/data/plans"
os.makedirs(PLANS_DIR, exist_ok=True)

def analyze_task_complexity(task_description: str) -> dict:
    """
    Analyze if task needs GLM-5 (planning) or M2.5 (execution)
    
    Returns:
        {
            "mode": "reasoning" | "coding" | "difficult",
            "reasoning": str,
            "needs_plan": bool
        }
    """
    task_lower = task_description.lower()
    
    # Indicators for planning mode (GLM-5)
    planning_keywords = [
        "how to", "design", "architecture", "plan", "strategy",
        "should i", "best way", "approach", "consider", "think about",
        "analyze", "review", "improve", "refactor", "create new",
        "what if", "decision", "recommend"
    ]
    
    # Indicators for difficult/AGI thinking
    difficult_keywords = [
        "agi", "consciousness", "self-evolution", "novel", "unprecedented",
        "complex", "difficult", "research", "theory"
    ]
    
    # Indicators for execution mode (M2.5)
    execution_keywords = [
        "write", "code", "implement", "fix", "debug", "create file",
        "run", "execute", "build", "make work", "complete"
    ]
    
    # Check difficulty first
    for kw in difficult_keywords:
        if kw in task_lower:
            return {
                "mode": "difficult",
                "reasoning": f"Task contains '{kw}' - requires deep thinking",
                "needs_plan": True
            }
    
    # Check planning needed
    for kw in planning_keywords:
        if kw in task_lower:
            return {
                "mode": "reasoning",
                "reasoning": f"Task contains '{kw}' - needs analysis and planning",
                "needs_plan": True
            }
    
    # Default to execution
    return {
        "mode": "coding",
        "reasoning": "Task appears to be execution/coding - use M2.5",
        "needs_plan": False
    }

def create_implementation_plan(task: str, analysis: str, steps: list) -> str:
    """Create a detailed plan file that M2.5 can execute"""
    
    plan = {
        "id": f"plan-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "task": task,
        "analysis": analysis,
        "steps": steps,
        "created_with": "glm-5",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending"
    }
    
    filepath = f"{PLANS_DIR}/{plan['id']}.json"
    with open(filepath, "w") as f:
        json.dump(plan, f, indent=2)
    
    return filepath

def get_pending_plans() -> list:
    """Get all pending plans"""
    plans = []
    for f in os.listdir(PLANS_DIR):
        if f.endswith(".json"):
            with open(f"{PLANS_DIR}/{f}") as fp:
                p = json.load(fp)
                if p.get("status") == "pending":
                    plans.append(p)
    return plans

def mark_plan_complete(plan_id: str):
    """Mark a plan as completed"""
    filepath = f"{PLANS_DIR}/{plan_id}.json"
    if os.path.exists(filepath):
        with open(filepath) as f:
            plan = json.load(f)
        plan["status"] = "completed"
        plan["completed_at"] = datetime.now(timezone.utc).isoformat()
        with open(filepath, "w") as f:
            json.dump(plan, f, indent=2)

# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "analyze" and len(sys.argv) > 2:
            task = " ".join(sys.argv[2:])
            result = analyze_task_complexity(task)
            print(f"Mode: {result['mode']}")
            print(f"Reasoning: {result['reasoning']}")
            print(f"Needs plan: {result['needs_plan']}")
        
        elif cmd == "plans":
            plans = get_pending_plans()
            print(f"Pending plans: {len(plans)}")
            for p in plans:
                print(f"  - {p['id']}: {p['task'][:50]}...")
        
        else:
            print("Usage:")
            print("  handover.py analyze <task description>")
            print("  handover.py plans")
    else:
        print("Clarvis Smart Model Handover System")
        print(f"Plans: {PLANS_DIR}/")