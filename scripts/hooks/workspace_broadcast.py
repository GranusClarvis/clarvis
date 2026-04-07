#!/usr/bin/env python3
# STATUS: MIGRATED to clarvis.cognition.workspace_broadcast (spine module)
# This file is a backward-compatibility shim. New code should use:
#   from clarvis.cognition.workspace_broadcast import WorkspaceBroadcast, Codelet, Coalition
"""GWT Workspace Broadcast Bus — backward-compat shim delegating to clarvis.cognition.workspace_broadcast."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

from clarvis.cognition.workspace_broadcast import (  # noqa: F401
    WorkspaceBroadcast, Codelet, Coalition, get_workspace,
    BROADCAST_SLOTS, SALIENCE_THRESHOLD, COALITION_OVERLAP,
)

# --- CLI ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: workspace_broadcast.py <command>")
        print("Commands:")
        print("  cycle     - Run full GWT cycle (collect -> coalesce -> compete -> broadcast)")
        print("  collect   - Only collect codelets (no broadcast)")
        print("  last      - Show last broadcast result")
        print("  history   - Show recent broadcast history")
        print("  stats     - Show broadcast statistics")
        sys.exit(0)

    cmd = sys.argv[1]
    ws = WorkspaceBroadcast()

    if cmd == "cycle":
        result = ws.run_cycle()
        print("\n=== GWT BROADCAST RESULT ===")
        print(f"Codelets collected: {result['total_codelets']}")
        print(f"Coalitions formed:  {result['n_coalitions']}")
        print(f"Winners broadcast:  {result['winners']}")
        print(f"Sources:            {', '.join(result['sources'])}")
        print(f"Cycle time:         {result.get('cycle_time_s', '?')}s")
        print("\nBroadcast content:")
        print(result['broadcast_text'])
        print("\nModule learning:")
        for mod, status in result['learning'].items():
            marker = "OK" if "failed" not in str(status) else "FAIL"
            print(f"  {mod:20s} {marker:4s}  {status}")

    elif cmd == "collect":
        codelets = ws.collect()
        print(f"Collected {len(codelets)} codelets:")
        for c in codelets:
            print(f"  [{c.salience:.2f}] ({c.source}) {c.content[:80]}")

    elif cmd == "last":
        result = WorkspaceBroadcast.last_broadcast()
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("No broadcast history found.")

    elif cmd == "history":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        entries = WorkspaceBroadcast.broadcast_history(n)
        if not entries:
            print("No broadcast history.")
        else:
            for e in entries:
                print(f"  {e.get('ts', '?')[:19]}  "
                      f"codelets={e.get('codelets', 0)}  "
                      f"winners={e.get('winners', 0)}  "
                      f"sources={e.get('sources', [])}")

    elif cmd == "stats":
        entries = WorkspaceBroadcast.broadcast_history(100)
        if not entries:
            print("No broadcast history for stats.")
        else:
            total = len(entries)
            avg_codelets = sum(e.get("codelets", 0) for e in entries) / total
            avg_winners = sum(e.get("winners", 0) for e in entries) / total
            all_sources = set()
            for e in entries:
                all_sources.update(e.get("sources", []))
            print(f"Broadcast stats ({total} cycles):")
            print(f"  Avg codelets/cycle: {avg_codelets:.1f}")
            print(f"  Avg winners/cycle:  {avg_winners:.1f}")
            print(f"  Active sources:     {', '.join(sorted(all_sources))}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
