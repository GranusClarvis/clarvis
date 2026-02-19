#!/usr/bin/env python3
"""
Clarvis Session Bridge
Phase 1: Session Continuity Protocol

Handles:
- Session-Close: Save state at end of each session
- Session-Open: Load state at start of each session
"""

import json
import os
from datetime import datetime, timezone

SESSIONS_DIR = "/home/agent/.openclaw/workspace/data/sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

def session_close(
    summary: str,
    decisions: list[str],
    unfinished: list[str],
    learnings: list[str],
    next_actions: list[str],
    current_mode: str = "coding"
):
    """
    Save session state for future sessions to pick up.
    
    Args:
        summary: What happened this session (3-5 sentences)
        decisions: List of decisions made with reasoning
        unfinished: Work started but not completed
        learnings: New facts, corrections, preferences discovered
        next_actions: Ordered list of things to do next
    """
    session = {
        "id": f"session-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "decisions": decisions,
        "unfinished": unfinished,
        "learnings": learnings,
        "next_actions": next_actions,
        "current_mode": current_mode,
        "status": "closed"
    }
    
    filepath = os.path.join(SESSIONS_DIR, f"{session['id']}.json")
    with open(filepath, "w") as f:
        json.dump(session, f, indent=2)
    
    print(f"Session closed: {filepath}")
    return session

def session_open(n: int = 3) -> list[dict]:
    """
    Load last N sessions for continuity.
    
    Args:
        n: Number of recent sessions to load (default 3)
    
    Returns:
        List of session dictionaries, newest first
    """
    sessions = []
    
    # Get all session files, sorted by name (date)
    files = sorted([f for f in os.listdir(SESSIONS_DIR) if f.endswith(".json")], reverse=True)
    
    for f in files[:n]:
        with open(os.path.join(SESSIONS_DIR, f), "r") as fp:
            sessions.append(json.load(fp))
    
    return sessions

def get_pending_work() -> list[dict]:
    """Get all unfinished work from recent sessions."""
    sessions = session_open(n=10)
    pending = []
    
    for s in sessions:
        if s.get("unfinished"):
            pending.append({
                "session": s["id"],
                "unfinished": s["unfinished"],
                "next_actions": s.get("next_actions", [])
            })
    
    return pending

# CLI for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "close":
            # Demo: close a session
            session_close(
                summary="Built ClarvisBrain with auto-importance detection. Tested storage and recall.",
                decisions=[
                    "Used Chroma as vector DB - works well for embeddings",
                    "Manual message processing for now vs full integration"
                ],
                unfinished=[
                    "Full message integration into OpenClaw flow",
                    "Self-reflection routine"
                ],
                learnings=[
                    "Brain needs to auto-process messages, not manual",
                    "User (Inverse) wants me to take time and test properly",
                    "Session bridge is highest priority for continuity"
                ],
                next_actions=[
                    "Build session-close routine (DONE)",
                    "Build session-open routine",
                    "Test full cycle",
                    "Move to Phase 2: Task Graph"
                ]
            )
        elif sys.argv[1] == "open":
            sessions = session_open(n=3)
            print(f"Loaded {len(sessions)} sessions:")
            for s in sessions:
                print(f"\n=== {s['id']} ===")
                print(f"Summary: {s['summary']}")
                if s.get('unfinished'):
                    print(f"Unfinished: {s['unfinished']}")
                if s.get('next_actions'):
                    print(f"Next: {s['next_actions'][:2]}")
        elif sys.argv[1] == "pending":
            pending = get_pending_work()
            print(f"Pending work from {len(pending)} sessions:")
            for p in pending:
                print(f"  {p['session']}: {p['unfinished']}")
    else:
        print("Usage:")
        print("  python clarvis_session.py close  # Close current session")
        print("  python clarvis_session.py open   # Open last N sessions")
        print("  python clarvis_session.py pending # Get pending work")
def get_current_mode() -> str:
    """Get the current working mode from the most recent session"""
    sessions = session_open(n=1)
    if sessions:
        return sessions[0].get("current_mode", "coding")
    return "coding"

def set_current_mode(mode: str):
    """Set the current mode (updates the most recent session)"""
    import json
    sessions_dir = SESSIONS_DIR
    files = sorted([f for f in os.listdir(sessions_dir) if f.endswith(".json")], reverse=True)
    if files:
        latest = os.path.join(sessions_dir, files[0])
        with open(latest, "r") as f:
            session = json.load(f)
        session["current_mode"] = mode
        with open(latest, "w") as f:
            json.dump(session, f, indent=2)
        return mode
    return None
