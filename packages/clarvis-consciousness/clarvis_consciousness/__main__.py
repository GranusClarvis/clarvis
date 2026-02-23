"""CLI for ClarvisConsciousness."""

import json
import sys


def main():
    if len(sys.argv) < 2:
        print("ClarvisConsciousness — IIT Phi, GWT spotlight, self-model")
        print()
        print("Usage: clarvis-consciousness <command> [args]")
        print()
        print("Commands:")
        print("  spotlight-demo     Demo the GWT attention spotlight")
        print("  phi-demo           Demo Phi (integrated information) computation")
        print("  self-model-demo    Demo the self-model")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "spotlight-demo":
        from clarvis_consciousness.gwt import AttentionSpotlight

        spot = AttentionSpotlight(capacity=3)
        spot.submit("User asked about memory architecture", source="conversation", importance=0.9)
        spot.submit("Cron job completed successfully", source="system", importance=0.3)
        spot.submit("Error in deployment pipeline", source="system", importance=0.85)
        spot.submit("Background task finished", source="system", importance=0.2)
        spot.tick()
        focus = spot.focus()
        print("Attention Spotlight (top 3):")
        for item in focus:
            print(f"  [{item.source}] salience={item.salience:.3f} {item.content[:60]}")

    elif cmd == "phi-demo":
        from clarvis_consciousness.phi import compute_phi

        nodes = {
            "mem1": "identity", "mem2": "goals", "mem3": "identity",
            "mem4": "episodic", "mem5": "goals",
        }
        edges = [
            ("mem1", "mem2", "cross"), ("mem1", "mem3", "similar"),
            ("mem2", "mem5", "similar"), ("mem4", "mem1", "temporal"),
        ]
        result = compute_phi(nodes=nodes, edges=edges)
        print(f"Phi: {result['phi']:.4f}")
        print(f"Components: {len(result['components'])}")
        print(json.dumps(result, indent=2, default=str))

    elif cmd == "self-model-demo":
        from clarvis_consciousness.self_model import SelfModel

        model = SelfModel()
        model.add_capability("Code execution")
        model.add_capability("Memory recall")
        model.think_about_thinking("Am I improving at reasoning?")
        model.set_awareness_level("reflective")
        state = model.to_dict()
        print("Self-Model state:")
        print(json.dumps(state, indent=2, default=str))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
