#!/usr/bin/env python3
"""Skill script for /autoqueue — toggle queue auto-fill ON/OFF."""

import sys
import os

sys.path.insert(0, os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))

from clarvis.research_config import enable, disable, status


def main():
    args = " ".join(sys.argv[1:]).strip().lower()

    if args in ("on", "enable"):
        enable("queue_auto_fill", reason="Operator enabled via /autoqueue", who="operator")
        print("Queue auto-fill: ON")
        print("Auto-injection from self-model, PI, meta-learning, etc. is now enabled.")
        print("Takes effect on next heartbeat/cron cycle.")

    elif args in ("off", "disable"):
        disable("queue_auto_fill", reason="Operator disabled via /autoqueue", who="operator")
        print("Queue auto-fill: OFF")
        print("Automatic task injection stopped. Existing queue tasks still execute.")
        print("User-directed tasks (/spawn, CLI) still work.")

    else:
        s = status()
        queue_on = s["queue_auto_fill"]
        research_on = s["research_auto_fill"]
        print(f"Queue auto-fill:    {'ON' if queue_on else 'OFF'}")
        print(f"Research auto-fill: {'ON' if research_on else 'OFF'}")
        print(f"Last changed: {s['updated_at'][:16]} by {s['updated_by']}")
        if s["reason"]:
            print(f"Reason: {s['reason']}")
        print()
        print("Usage: /autoqueue on | /autoqueue off")


if __name__ == "__main__":
    main()
