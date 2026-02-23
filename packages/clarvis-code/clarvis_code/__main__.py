"""
ClarvisCode CLI — Task routing, context compression, and prompt building.

Usage:
    clarvis-code route "Build a new API endpoint"
    clarvis-code compress /path/to/queue.md
    clarvis-code prompt "Fix the auth bug" --context "JWT module..."
    clarvis-code session open
    clarvis-code session close
    clarvis-code stats
"""

import json
import sys

from clarvis_code.router import TaskRouter
from clarvis_code.compressor import ContextCompressor
from clarvis_code.prompt_builder import PromptBuilder, PromptConfig
from clarvis_code.session import SessionManager


def main():
    if len(sys.argv) < 2:
        print("ClarvisCode — Smart task routing for Claude Code / OpenCode")
        print()
        print("Commands:")
        print("  route <task>              Classify task complexity and recommend executor")
        print("  compress <queue_path>     Compress a task queue file")
        print("  prompt <task> [--context] Build an execution prompt")
        print("  session open|close        Manage session lifecycle")
        print("  stats                     Show routing statistics")
        print()
        print("Examples:")
        print('  clarvis-code route "Build a new REST API endpoint"')
        print('  clarvis-code compress memory/evolution/QUEUE.md')
        print('  clarvis-code prompt "Fix auth bug" --context "JWT with 1h expiry"')
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "route":
        task = " ".join(sys.argv[2:])
        if not task:
            print("Error: provide a task to route")
            sys.exit(1)
        router = TaskRouter()
        result = router.classify(task)
        print(json.dumps(result.to_dict(), indent=2))

    elif cmd == "compress":
        if len(sys.argv) < 3:
            print("Error: provide path to queue file")
            sys.exit(1)
        path = sys.argv[2]
        compressor = ContextCompressor()
        print(compressor.compress_queue(path))

    elif cmd == "prompt":
        task = ""
        context = ""
        # Parse args
        args = sys.argv[2:]
        task_parts = []
        i = 0
        while i < len(args):
            if args[i] == "--context" and i + 1 < len(args):
                context = args[i + 1]
                i += 2
            else:
                task_parts.append(args[i])
                i += 1
        task = " ".join(task_parts)

        if not task:
            print("Error: provide a task")
            sys.exit(1)

        builder = PromptBuilder()
        print(builder.build(task, context=context))

    elif cmd == "session":
        if len(sys.argv) < 3:
            print("Error: use 'session open' or 'session close'")
            sys.exit(1)
        subcmd = sys.argv[2]
        data_dir = sys.argv[3] if len(sys.argv) > 3 else "./data"
        session = SessionManager(data_dir)

        if subcmd == "open":
            state = session.open()
            print(json.dumps(state, indent=2))
        elif subcmd == "close":
            state = session.close()
            print(json.dumps(state, indent=2))
        elif subcmd == "status":
            print(json.dumps(session.state, indent=2))
        else:
            print(f"Unknown session command: {subcmd}")
            sys.exit(1)

    elif cmd == "stats":
        router = TaskRouter()
        print(json.dumps(router.stats(), indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
