#!/usr/bin/env python3
"""
Clarvis Task Graph - Phase 2
Persistent work tracker with dependencies
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

TASK_FILE = "/home/agent/.openclaw/workspace/data/task-graph.json"
os.makedirs(os.path.dirname(TASK_FILE), exist_ok=True)

def load_tasks() -> dict:
    if os.path.exists(TASK_FILE):
        with open(TASK_FILE, "r") as f:
            return json.load(f)
    return {"tasks": [], "version": "1.0"}

def save_tasks(data: dict):
    with open(TASK_FILE, "w") as f:
        json.dump(data, f, indent=2)

def create_task(
    task_id: str,
    goal: str,
    context: str = "",
    status: str = "pending",
    dependencies: list = None,
    parent: Optional[str] = None
) -> dict:
    """Create a new task"""
    data = load_tasks()
    
    task = {
        "id": task_id,
        "goal": goal,
        "context": context,
        "status": status,
        "dependencies": dependencies or [],
        "parent": parent,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": "",
        "outcome": ""
    }
    
    data["tasks"].append(task)
    save_tasks(data)
    
    return task

def update_task(task_id: str, **kwargs) -> Optional[dict]:
    """Update task fields"""
    data = load_tasks()
    
    for task in data["tasks"]:
        if task["id"] == task_id:
            for key, value in kwargs.items():
                if key in task:
                    task[key] = value
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_tasks(data)
            return task
    
    return None

def get_tasks(status: str = None) -> list:
    """Get tasks, optionally filtered by status"""
    data = load_tasks()
    
    if status:
        return [t for t in data["tasks"] if t["status"] == status]
    return data["tasks"]

def get_task(task_id: str) -> Optional[dict]:
    """Get a specific task"""
    data = load_tasks()
    
    for task in data["tasks"]:
        if task["id"] == task_id:
            return task
    return None

def get_ready_tasks() -> list:
    """Get tasks that are ready to work on (dependencies met)"""
    data = load_tasks()
    ready = []
    
    for task in data["tasks"]:
        if task["status"] != "pending":
            continue
        
        # Check dependencies
        deps_met = True
        for dep_id in task.get("dependencies", []):
            dep = get_task(dep_id)
            if not dep or dep["status"] not in ["completed", "done"]:
                deps_met = False
                break
        
        if deps_met:
            ready.append(task)
    
    return ready

# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "create" and len(sys.argv) > 3:
            task_id = sys.argv[2]
            goal = sys.argv[3]
            create_task(task_id, goal)
            print(f"Created: {task_id}")
        
        elif cmd == "list":
            status = sys.argv[2] if len(sys.argv) > 2 else None
            tasks = get_tasks(status)
            print(f"Tasks ({len(tasks)}):")
            for t in tasks:
                deps = f" (deps: {', '.join(t['dependencies'])})" if t['dependencies'] else ""
                print(f"  [{t['status']}] {t['id']}: {t['goal']}{deps}")
        
        elif cmd == "ready":
            tasks = get_ready_tasks()
            print(f"Ready to work on ({len(tasks)}):")
            for t in tasks:
                print(f"  - {t['id']}: {t['goal']}")
        
        elif cmd == "update" and len(sys.argv) > 3:
            task_id = sys.argv[2]
            status = sys.argv[3]
            update_task(task_id, status=status)
            print(f"Updated {task_id} -> {status}")
        
        elif cmd == "note" and len(sys.argv) > 3:
            task_id = sys.argv[2]
            note = " ".join(sys.argv[3:])
            task = get_task(task_id)
            if task:
                notes = task.get("notes", "")
                notes += f"\n[{datetime.now(timezone.utc).isoformat()}] {note}"
                update_task(task_id, notes=notes)
                print(f"Added note to {task_id}")
        
        else:
            print("Usage:")
            print("  task.py create <id> <goal>")
            print("  task.py list [status]")
            print("  task.py ready")
            print("  task.py update <id> <status>")
            print("  task.py note <id> <note>")
    else:
        print("Clarvis Task Graph - Phase 2")
        print(f"Stored in: {TASK_FILE}")