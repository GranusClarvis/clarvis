"""CLI for ClarvisReasoning."""

import json
import sys


def main():
    if len(sys.argv) < 2:
        print("ClarvisReasoning — Meta-cognitive reasoning quality assessment")
        print()
        print("Usage: clarvis-reasoning <command> [args]")
        print()
        print("Commands:")
        print("  check <thought> [confidence]   Check a reasoning step for quality issues")
        print("  coherence <t1> <t2> [t3...]    Measure coherence across thoughts")
        print("  demo                           Run a demo evaluation")
        sys.exit(1)

    cmd = sys.argv[1]

    from clarvis_reasoning.metacognition import (
        check_step_quality,
        compute_coherence,
        evaluate_session,
    )

    if cmd == "check":
        if len(sys.argv) < 3:
            print("Usage: check <thought> [confidence]")
            sys.exit(1)
        thought = sys.argv[2]
        confidence = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
        flags = check_step_quality(thought, evidence=[], confidence=confidence, previous_thoughts=[])
        if flags:
            print(f"Quality flags: {', '.join(flags)}")
        else:
            print("No quality issues detected.")

    elif cmd == "coherence":
        if len(sys.argv) < 4:
            print("Usage: coherence <thought1> <thought2> [thought3...]")
            sys.exit(1)
        thoughts = sys.argv[2:]
        score = compute_coherence(thoughts)
        print(f"Coherence: {score:.3f}")

    elif cmd == "demo":
        steps = [
            {"thought": "The user wants to optimize database queries for faster response",
             "evidence": ["Profile showed 200ms avg query time"], "confidence": 0.8,
             "sub_problem": "identify bottleneck", "quality_flags": []},
            {"thought": "Adding an index on user_id should reduce scan time significantly",
             "evidence": ["EXPLAIN shows full table scan", "user_id has high cardinality"],
             "confidence": 0.85, "sub_problem": "apply fix", "quality_flags": []},
            {"thought": "After indexing, verify with EXPLAIN that index is being used",
             "evidence": [], "confidence": 0.7,
             "sub_problem": "verify", "quality_flags": []},
        ]
        result = evaluate_session(
            steps,
            sub_problems=["identify bottleneck", "apply fix", "verify"],
            predicted_outcome="success",
            actual_outcome="success",
        )
        print("Demo evaluation:")
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
