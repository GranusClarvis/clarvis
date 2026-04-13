#!/usr/bin/env python3
"""Skill script for /autoresearch — toggle research auto-fill ON/OFF."""

import sys
import os

sys.path.insert(0, os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))

from clarvis.research_config import enable, disable, status


def main():
    args = " ".join(sys.argv[1:]).strip().lower()

    if args in ("on", "enable"):
        enable("research_auto_fill", reason="Operator enabled via /autoresearch", who="operator")
        print("Research auto-fill: ON")
        print("Research papers, discovery, and monthly bridge will inject tasks.")
        print("Takes effect on next research cron cycle.")

    elif args in ("off", "disable"):
        disable("research_auto_fill", reason="Operator disabled via /autoresearch", who="operator")
        print("Research auto-fill: OFF")
        print("All research injection stopped. Normal queue auto-fill unaffected.")

    else:
        s = status()
        queue_on = s["queue_auto_fill"]
        research_on = s["research_auto_fill"]
        print(f"Queue auto-fill:    {'ON' if queue_on else 'OFF'}")
        print(f"Research auto-fill: {'ON' if research_on else 'OFF'}")
        if research_on:
            print("  Research sub-paths:")
            for k, v in s["paths"].items():
                if k.startswith("research_") and k != "research_auto_fill":
                    print(f"    {k}: {'ON' if v['effective'] else 'OFF'}")
        print(f"Last changed: {s['updated_at'][:16]} by {s['updated_by']}")
        if s["reason"]:
            print(f"Reason: {s['reason']}")
        print()
        print("Usage: /autoresearch on | /autoresearch off")


if __name__ == "__main__":
    main()
