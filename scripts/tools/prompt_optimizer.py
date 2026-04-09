#!/usr/bin/env python3
"""CLI wrapper for clarvis.context.prompt_optimizer.

All library logic lives in clarvis/context/prompt_optimizer.py.
This file provides the CLI interface:
    python3 prompt_optimizer.py select [task_text]
    python3 prompt_optimizer.py record <variant_id> <task_type> <outcome> <duration>
    python3 prompt_optimizer.py report
    python3 prompt_optimizer.py ab-summary
"""

import json
import sys

from clarvis.context.prompt_optimizer import (
    select_variant, record_outcome, get_report, get_ab_summary,
)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: prompt_optimizer.py select|record|report|ab-summary")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "select":
        task = sys.argv[2] if len(sys.argv) > 2 else ""
        result = select_variant(task)
        print(json.dumps(result))

    elif cmd == "record":
        if len(sys.argv) < 6:
            print("Usage: prompt_optimizer.py record <variant_id> <task_type> "
                  "<outcome> <duration> [task_text] [quality_score]")
            sys.exit(1)
        variant_id = sys.argv[2]
        task_type = sys.argv[3]
        outcome = sys.argv[4]
        duration = int(sys.argv[5])
        task_text = sys.argv[6] if len(sys.argv) > 6 else ""
        quality_score = float(sys.argv[7]) if len(sys.argv) > 7 else None
        r = record_outcome(variant_id, task_type, outcome, duration, task_text,
                           quality_score=quality_score)
        print(json.dumps(r))

    elif cmd == "report":
        print(get_report())

    elif cmd == "ab-summary":
        print(get_ab_summary())

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
