#!/usr/bin/env python3
"""
Session Hook — Session lifecycle automation for Clarvis.

Manages attention state and working memory persistence across the daily cycle.
Called by cron scripts:
  - cron_morning.sh  → session_hook.py open   (restore state, set day context)
  - cron_reflection.sh → session_hook.py close (save state, store learnings)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path
from brain import brain
from clarvis.cognition.attention import attention

DATA_DIR = Path("/home/agent/.openclaw/workspace/data")
SESSION_STATE_FILE = DATA_DIR / "session_state.json"


def session_open(session_key=None):
    """
    Called at start of day / new session.
    Restores attention state, loads brain context, sets session metadata.
    """
    session_key = session_key or datetime.now(timezone.utc).strftime("day-%Y-%m-%d")
    print(f"=== Session Open: {session_key} ===")

    # 1. Restore attention spotlight from disk (persisted by last session_close)
    attention._load()
    spotlight_count = len(attention.items)
    print(f"  Attention restored: {spotlight_count} spotlight items")

    # 2. Run a tick to decay stale items and evict expired ones
    tick_result = attention.tick()
    print(f"  Attention tick: evicted={tick_result['evicted']}, remaining={tick_result['total']}")

    # 3. Set brain context with session info
    brain.set_context(
        f"Session opened: {session_key}. "
        f"Spotlight: {tick_result['total']} items. "
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    # 4. Submit session-open event to attention so it's visible in working memory
    attention.submit(
        f"New session started: {session_key}",
        source="session_hook",
        importance=0.6,
        relevance=0.5
    )

    # 5. Theory of Mind: generate proactive suggestions and push to spotlight
    try:
        from theory_of_mind import tom
        suggestions = tom.generate_suggestions()
        pushed = tom.push_to_spotlight(suggestions)
        if suggestions:
            print(f"  Theory of Mind: {len(suggestions)} suggestions, {pushed} pushed to spotlight")
            for s in suggestions[:3]:
                print(f"    [{s['priority']}] {s['suggestion'][:70]}")
    except Exception as e:
        print(f"  Theory of Mind: unavailable ({e})")

    attention._save()

    # 6. Record session state for close to reference
    state = {
        "session_key": session_key,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "spotlight_restored": spotlight_count,
        "spotlight_after_tick": tick_result["total"],
    }
    SESSION_STATE_FILE.write_text(json.dumps(state, indent=2))

    print(f"  Session state saved to {SESSION_STATE_FILE}")
    return state


def session_close(session_key=None, messages=None):
    """
    Called at end of day / session close.
    Saves attention state, stores learnings, records session summary.
    """
    # Try to load session state from open
    prior_state = {}
    if SESSION_STATE_FILE.exists():
        try:
            prior_state = json.loads(SESSION_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    session_key = session_key or prior_state.get("session_key") or datetime.now(timezone.utc).strftime("day-%Y-%m-%d")
    print(f"=== Session Close: {session_key} ===")

    if messages:
        # Extract key info from messages (used when called programmatically)
        decisions = []
        insights = []

        for msg in messages:
            content = msg.get('content', '')
            if any(x in content.lower() for x in ['decided', 'agreed', 'will do', 'priority']):
                decisions.append(content[:150])
            if any(x in content.lower() for x in ['insight', 'realized', 'learned', 'found']):
                insights.append(content[:150])

        if decisions:
            brain.store(
                f"Session decisions: {'; '.join(decisions[:3])}",
                collection="clarvis-learnings",
                importance=0.8,
                tags=["session", "decision"],
                source="session_close"
            )
        if insights:
            brain.store(
                f"Session insights: {'; '.join(insights[:3])}",
                collection="clarvis-learnings",
                importance=0.7,
                tags=["session", "insight"],
                source="session_close"
            )
        print(f"  Stored: {len(decisions)} decisions, {len(insights)} insights")

    # Theory of Mind: record session close event and feed observations
    try:
        from theory_of_mind import tom
        tom.observe("feedback", f"Session closed: {session_key}",
                    context={"source": "session_close"})
        if decisions:
            for d in decisions[:3]:
                tom.observe("preference", d, context={"source": "session_decision"})
        print("  Theory of Mind: session close events recorded")
    except Exception:
        pass

    # Save attention/working memory state for next session
    spotlight_count = len(attention.items)
    attention._save()
    print(f"  Attention saved: {spotlight_count} spotlight items persisted")

    # Update context
    brain.set_context(
        f"Session closed: {session_key}. "
        f"Spotlight: {spotlight_count} items saved. "
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    # Record close in session state
    if prior_state:
        prior_state["closed_at"] = datetime.now(timezone.utc).isoformat()
        prior_state["spotlight_at_close"] = spotlight_count
        SESSION_STATE_FILE.write_text(json.dumps(prior_state, indent=2))
        print(f"  Session duration: {prior_state.get('opened_at', '?')} → {prior_state['closed_at']}")

    return {"session_key": session_key, "spotlight_saved": spotlight_count}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: session_hook.py [open|close]")
        print("  open  — Restore attention state, start new session (called by cron_morning.sh)")
        print("  close — Save attention state, store learnings (called by cron_reflection.sh)")
        sys.exit(0)

    cmd = sys.argv[1]
    session_key = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "open":
        session_open(session_key)
    elif cmd == "close":
        session_close(session_key)
    else:
        print(f"Unknown command: {cmd}. Use 'open' or 'close'.")
        sys.exit(1)
