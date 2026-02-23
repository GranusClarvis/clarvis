"""CLI for ClarvisCost."""

import json
import sys


def main():
    if len(sys.argv) < 2:
        print("ClarvisCost — Token optimization and cost tracking")
        print()
        print("Usage: clarvis-cost <command> [args]")
        print()
        print("Commands:")
        print("  estimate <model> <input_tokens> <output_tokens>  Estimate cost")
        print("  tokens <text>                                     Estimate token count")
        print("  log <model> <in> <out> [source]                  Log a cost entry")
        print("  rollup [day|week|month] [costs.jsonl]            Show cost rollup")
        print("  budget <daily_budget> [costs.jsonl]              Check budget usage")
        print("  pricing [model]                                   Show pricing table")
        print("  demo                                              Run a demo")
        sys.exit(1)

    cmd = sys.argv[1]

    from clarvis_cost.core import estimate_cost, estimate_tokens, CostTracker, MODEL_PRICING

    if cmd == "estimate":
        if len(sys.argv) < 5:
            print("Usage: estimate <model> <input_tokens> <output_tokens>")
            sys.exit(1)
        cost = estimate_cost(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        print(f"${cost:.6f}")

    elif cmd == "tokens":
        text = " ".join(sys.argv[2:])
        tokens = estimate_tokens(text)
        print(f"~{tokens} tokens")

    elif cmd == "log":
        if len(sys.argv) < 5:
            print("Usage: log <model> <input_tokens> <output_tokens> [source]")
            sys.exit(1)
        path = sys.argv[6] if len(sys.argv) > 6 else "./data/costs.jsonl"
        source = sys.argv[5] if len(sys.argv) > 5 else "cli"
        tracker = CostTracker(path)
        entry = tracker.log(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), source=source)
        print(f"Logged: ${entry.cost_usd:.6f} ({sys.argv[2]})")

    elif cmd == "rollup":
        period = sys.argv[2] if len(sys.argv) > 2 else "day"
        path = sys.argv[3] if len(sys.argv) > 3 else "./data/costs.jsonl"
        tracker = CostTracker(path)
        rollup = tracker.rollup(period)
        print(json.dumps(rollup, indent=2, default=str))

    elif cmd == "budget":
        if len(sys.argv) < 3:
            print("Usage: budget <daily_budget> [costs.jsonl]")
            sys.exit(1)
        budget = float(sys.argv[2])
        path = sys.argv[3] if len(sys.argv) > 3 else "./data/costs.jsonl"
        tracker = CostTracker(path)
        result = tracker.budget_check(daily_budget=budget)
        print(json.dumps(result, indent=2, default=str))

    elif cmd == "pricing":
        model = sys.argv[2] if len(sys.argv) > 2 else None
        if model:
            p = MODEL_PRICING.get(model)
            if p:
                print(f"{model}: input=${p['input']}/1M, output=${p['output']}/1M")
            else:
                print(f"Unknown model: {model}")
        else:
            for m, p in sorted(MODEL_PRICING.items()):
                print(f"  {m:30s}  in=${p['input']:8.2f}/1M  out=${p['output']:8.2f}/1M")

    elif cmd == "demo":
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "costs.jsonl")
            tracker = CostTracker(path)
            tracker.log("claude-opus-4-6", 5000, 1200, source="demo")
            tracker.log("claude-haiku-4-5-20251001", 3000, 800, source="demo")
            tracker.log("claude-sonnet-4-6", 4000, 1000, source="demo")
            rollup = tracker.rollup("day")
            print("Demo cost tracking:")
            print(json.dumps(rollup, indent=2, default=str))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
