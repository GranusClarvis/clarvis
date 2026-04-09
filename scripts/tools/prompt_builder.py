#!/usr/bin/env python3
"""CLI wrapper for clarvis.context.prompt_builder.

All library logic lives in clarvis/context/prompt_builder.py.
This file provides the CLI interface called by shell scripts:
    python3 prompt_builder.py context-brief --task "description" [--tier standard]
    python3 prompt_builder.py build --task "description" [--role executive]
    python3 prompt_builder.py write --task "description" [--role executive]
"""

import sys

from clarvis.context.prompt_builder import get_context_brief, build_prompt, write_prompt_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  prompt_builder.py context-brief --task 'description' [--tier minimal|standard|full]")
        print("  prompt_builder.py build --task 'description' [--role executive] [--tier standard] [--time-budget 900]")
        print("  prompt_builder.py write --task 'description' [--role executive] [--tier standard]")
        sys.exit(0)

    cmd = sys.argv[1]

    # Parse flags
    tier = "standard"
    task = ""
    role = "executive"
    time_budget = None
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--tier" and i + 1 < len(sys.argv):
            tier = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--task" and i + 1 < len(sys.argv):
            task = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--role" and i + 1 < len(sys.argv):
            role = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--time-budget" and i + 1 < len(sys.argv):
            time_budget = int(sys.argv[i + 1])
            i += 2
        else:
            if not task:
                task = sys.argv[i]
            i += 1

    if cmd == "context-brief":
        print(get_context_brief(tier=tier, task=task))

    elif cmd == "build":
        if not task:
            print("Error: --task is required", file=sys.stderr)
            sys.exit(1)
        print(build_prompt(task=task, role=role, tier=tier, time_budget=time_budget))

    elif cmd == "write":
        if not task:
            print("Error: --task is required", file=sys.stderr)
            sys.exit(1)
        path = write_prompt_file(task=task, role=role, tier=tier, time_budget=time_budget)
        print(path)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
