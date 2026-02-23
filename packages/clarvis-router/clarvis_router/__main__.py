"""CLI for ClarvisRouter."""

import json
import sys


def main():
    if len(sys.argv) < 2:
        print("ClarvisRouter — Smart model routing with 14-dimension prompt scoring")
        print()
        print("Usage: clarvis-router <command> [args]")
        print()
        print("Commands:")
        print("  score <prompt>       Show 14-dimension feature vector")
        print("  models               List available models")
        print("  filter [--tag TAG]   Filter models by criteria")
        sys.exit(1)

    cmd = sys.argv[1]

    from clarvis_router.scorer import PromptScorer
    from clarvis_router.models import ModelRegistry

    if cmd == "score":
        prompt = " ".join(sys.argv[2:])
        if not prompt:
            print("Usage: score <prompt>")
            sys.exit(1)
        scorer = PromptScorer()
        result = scorer.score(prompt)
        print(json.dumps(result.__dict__ if hasattr(result, '__dict__') else result, indent=2, default=str))

    elif cmd == "models":
        registry = ModelRegistry()
        registry.load_defaults()
        for m in registry.all():
            print(f"  {m.display_name:30s}  ${m.cost_per_1m_input:6.2f}/1M in  ctx={m.context_window:,}")

    elif cmd == "filter":
        registry = ModelRegistry()
        registry.load_defaults()
        tags = []
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--tag" and i + 1 < len(sys.argv):
                tags.append(sys.argv[i + 1])
                i += 2
            else:
                i += 1
        models = registry.filter(tags=tags if tags else None)
        for m in models:
            print(f"  {m.display_name:30s}  ${m.cost_per_1m_input:6.2f}/1M  tags={m.tags}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
