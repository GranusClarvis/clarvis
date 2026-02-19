#!/usr/bin/env python3
"""
Clarvis Reflection Protocol - Phase 3
Daily/Weekly/Monthly reflection routines
"""

import json
import os
from datetime import datetime, timezone

REFLECTIONS_DIR = "/home/agent/.openclaw/workspace/data/reflections"
DAILY_DIR = f"{REFLECTIONS_DIR}/daily"
os.makedirs(DAILY_DIR, exist_ok=True)

def daily_reflection():
    """Daily reflection - review today's sessions and consolidate learnings"""
    
    # Load today's sessions
    from clarvis_session import session_open
    
    sessions = session_open(n=10)
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_sessions = [s for s in sessions if today_date in s["id"]]
    
    # Consolidate learnings
    all_learnings = []
    all_unfinished = []
    patterns = []
    
    for s in today_sessions:
        all_learnings.extend(s.get("learnings", []))
        all_unfinished.extend(s.get("unfinished", []))
    
    # Generate reflection
    reflection = {
        "type": "daily",
        "date": datetime.now(timezone.utc).isoformat(),
        "sessions_reviewed": len(today_sessions),
        "learnings": list(set(all_learnings)),  # Dedupe
        "unfinished_work": list(set(all_unfinished)),
        "patterns": patterns,
        "actions_needed": list(set(all_unfinished))
    }
    
    # Save
    filename = f"daily-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    with open(f"{DAILY_DIR}/{filename}", "w") as f:
        json.dump(reflection, f, indent=2)
    
    return reflection

def get_latest_reflection(reflection_type="daily"):
    """Get the latest reflection of a type"""
    dir_map = {
        "daily": DAILY_DIR,
    }
    
    target_dir = dir_map.get(reflection_type, DAILY_DIR)
    
    if not os.path.exists(target_dir):
        return None
    
    files = sorted([f for f in os.listdir(target_dir) if f.startswith(reflection_type)], reverse=True)
    
    if not files:
        return None
    
    with open(f"{target_dir}/{files[0]}", "r") as f:
        return json.load(f)

# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "daily":
            result = daily_reflection()
            print(f"Daily reflection saved: {len(result['learnings'])} learnings, {len(result['unfinished_work'])} unfinished")
            print(f"File: {DAILY_DIR}/daily-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json")
        
        elif cmd == "latest" and len(sys.argv) > 2:
            result = get_latest_reflection(sys.argv[2])
            if result:
                print(json.dumps(result, indent=2))
            else:
                print(f"No {sys.argv[2]} reflections found")
        
        else:
            print("Usage:")
            print("  reflection.py daily     # Run daily reflection")
            print("  reflection.py latest daily  # Get latest daily reflection")
    else:
        print("Clarvis Reflection Protocol - Phase 3")
        print(f"Daily: {DAILY_DIR}/")