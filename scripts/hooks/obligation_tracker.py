#!/usr/bin/env python3
# STATUS: CLI WRAPPER — canonical implementation lives in clarvis/cognition/obligations.py
"""Obligation Tracker — CLI entry point.

Library logic lives in clarvis.cognition.obligations. This script provides the CLI
interface used by cron launchers (cron_autonomous.sh, cron_implementation_sprint.sh).

Usage:
    python3 obligation_tracker.py check          # Run all due obligation checks
    python3 obligation_tracker.py list           # List all obligations
    python3 obligation_tracker.py add "desc"     # Add a new obligation
    python3 obligation_tracker.py auto-fix       # Auto-commit+push if safe
    python3 obligation_tracker.py git-hygiene    # Run git hygiene check
    python3 obligation_tracker.py status         # Summary status
    python3 obligation_tracker.py verify         # Self-test / verification
    python3 obligation_tracker.py seed           # Seed default obligations
"""

import sys

from clarvis.cognition.obligations import (  # noqa: F401 — re-export for any remaining callers
    ObligationTracker, seed_defaults, run_verification,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: obligation_tracker.py <check|list|add|auto-fix|git-hygiene|status|verify|seed>")
        sys.exit(1)

    cmd = sys.argv[1]
    tracker = ObligationTracker()

    if cmd == "check":
        results = tracker.check_all()
        for r in results:
            icon = "\u2713" if r["satisfied"] else "\u2717"
            print(f"  [{icon}] {r['obligation_id']}: {r['detail'][:100]}")
        if not results:
            print("  No obligations due for checking.")

    elif cmd == "list":
        for ob in tracker.list_all():
            s = ob["state"]
            status_str = s["status"]
            if s["consecutive_violations"] > 0:
                status_str += f" (VIOLATED {s['consecutive_violations']}x)"
            print(f"  {ob['id']}: {ob['label']} [{status_str}]")

    elif cmd == "add":
        if len(sys.argv) < 3:
            print("Usage: obligation_tracker.py add 'description' [--freq hourly|daily|every_heartbeat]")
            sys.exit(1)
        desc = sys.argv[2]
        freq = "daily"
        if "--freq" in sys.argv:
            idx = sys.argv.index("--freq")
            if idx + 1 < len(sys.argv):
                freq = sys.argv[idx + 1]
        ob = tracker.record_obligation(label=desc, description=desc, frequency=freq, source="cli")
        print(f"Recorded: {ob['id']}")

    elif cmd == "auto-fix":
        dry = "--dry-run" in sys.argv
        result = tracker.auto_commit_push(dry_run=dry)
        print(f"Auto-fix: {result['action']}")
        print(f"  {result['detail']}")
        if result["acted"]:
            print("  Git hygiene enforced successfully.")

    elif cmd == "git-hygiene":
        result = tracker.git_hygiene_check()
        print(f"Git hygiene: {'CLEAN' if result['clean'] else 'DIRTY'}")
        print(f"  {result['summary']}")
        if result["actions"]:
            print(f"  Actions needed: {', '.join(result['actions'])}")

    elif cmd == "status":
        print(tracker.status_summary())

    elif cmd == "verify":
        success = run_verification()
        sys.exit(0 if success else 1)

    elif cmd == "seed":
        seed_defaults(tracker)
        print(f"Seeded. Total obligations: {len(tracker.list_all())}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
