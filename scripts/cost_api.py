#!/usr/bin/env python3
"""OpenRouter Cost API Client — thin wrapper. Implementation in clarvis/orch/cost_api.py.

Usage:
    from cost_api import get_api_key, fetch_usage, format_usage
"""

import sys
import os

# Ensure clarvis package is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Re-export everything from clarvis.orch.cost_api for backward compatibility
from clarvis.orch.cost_api import (  # noqa: F401
    get_api_key, fetch_usage, fetch_generation,
    format_usage, format_telegram,
    AUTH_FILE, OPENROUTER_BASE,
)


def main():
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "generation":
        if len(sys.argv) < 3:
            print("Usage: cost_api.py generation <generation_id>")
            sys.exit(1)
        gen = fetch_generation(sys.argv[2])
        if "--json" in sys.argv:
            print(json.dumps(gen, indent=2))
        else:
            print(f"=== Generation {gen.get('id', '?')} ===")
            print(f"  Model:    {gen.get('model', '?')}")
            print(f"  Provider: {gen.get('provider', '?')}")
            print(f"  Cost:     ${gen.get('total_cost', 0):.6f}")
            print(f"  Tokens:   {gen.get('tokens_prompt', 0)} in / {gen.get('tokens_completion', 0)} out")
            print(f"  Latency:  {gen.get('latency', '?')}ms")
            print(f"  Time:     {gen.get('generation_time', '?')}ms")
        return

    usage = fetch_usage()

    if "--json" in sys.argv:
        print(json.dumps(usage, indent=2))
    elif "--telegram" in sys.argv:
        print(format_telegram(usage))
    else:
        print(format_usage(usage))


if __name__ == "__main__":
    main()
