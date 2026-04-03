# BRIDGE: canonical module is clarvis.orch.scoreboard
#!/usr/bin/env python3
"""Orchestration Scoreboard — bridge wrapper.

Core logic lives in clarvis.orch.scoreboard (spine module).
This file re-exports public API and provides CLI entry point.
"""

import sys

from clarvis.orch.scoreboard import (
    record,
    show,
    trend,
    _list_agent_names,
    _load_latest,
    _agent_summary,
    WORKSPACE,
    SCRIPTS,
    BENCHMARKS_DIR,
    SCOREBOARD_DIR,
    SCOREBOARD_FILE,
)

__all__ = ["record", "show", "trend",
           "_list_agent_names", "_load_latest", "_agent_summary"]


def main():
    if len(sys.argv) < 2:
        print("Usage: orchestration_scoreboard.py record | show | trend [n]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "record":
        record()
    elif cmd == "show":
        show()
    elif cmd == "trend":
        n = int(sys.argv[2]) if len(sys.argv) >= 3 else 10
        trend(n)
    else:
        print("Usage: orchestration_scoreboard.py record | show | trend [n]")
        sys.exit(1)


if __name__ == "__main__":
    main()
