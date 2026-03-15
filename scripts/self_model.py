#!/usr/bin/env python3
"""
Internal World Model - Track capabilities, strengths, weaknesses
v2.0 - Expanded with meta-cognition (Higher-Order Theories of consciousness)

CLI wrapper — canonical logic lives in clarvis.metrics.self_model (spine module).
"""
import sys
import os

# Ensure clarvis package is importable
_workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
# Also keep scripts/ on path for legacy imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import everything from the canonical spine module
from clarvis.metrics.self_model import (  # noqa: E402
    # Constants
    DATA_FILE, META_FILE, CAPABILITY_HISTORY_FILE,
    ALERT_THRESHOLD, WEEKLY_REGRESSION_THRESHOLD,
    CAPABILITY_DOMAINS, ASSESSORS, REMEDIATION_THRESHOLD, REMEDIATION_TEMPLATES,
    # I/O
    load_model, save_model, load_meta, save_meta,
    load_capability_history, save_capability_history,
    # Core model
    init_model, update_model,
    # Meta-cognition
    get_awareness_level, set_awareness_level,
    get_working_memory, set_working_memory, clear_working_memory,
    think_about_thinking, update_user_model,
    get_cognitive_state, set_cognitive_state,
    # Assessment
    assess_all_capabilities, generate_remediation_tasks,
    inject_tasks_to_queue, check_weekly_regression, daily_update,
    # Class interface
    SelfModel,
)


# === Display functions (CLI-only, not in spine) ===

def show_model():
    """Display current world model"""
    model = load_model()

    print("=== Internal World Model v2.0 ===")
    print(f"Last updated: {model.get('last_updated', 'never')}")

    print(f"\nCapabilities ({len(model.get('capabilities', []))}):")
    for c in model.get("capabilities", []):
        print(f"  - {c}")

    print(f"\nStrengths ({len(model.get('strengths', []))}):")
    for s in model.get("strengths", []):
        print(f"  - {s}")

    print(f"\nWeaknesses ({len(model.get('weaknesses', []))}):")
    for w in model.get("weaknesses", []):
        print(f"  - {w}")

    print(f"\nTrajectory ({len(model.get('trajectory', []))} events):")
    for t in model.get("trajectory", [])[-3:]:
        print(f"  - {t['date']}: {t['event']}")


def show_meta():
    """Display meta-cognitive state"""
    meta = load_meta()

    print("\n=== Meta-Cognitive State ===")
    print(f"Awareness Level: {meta.get('awareness_level')}")
    print(f"Cognitive State: {meta.get('cognitive_state')}")
    print(f"Attention Shifts: {meta.get('attention_shifts')}")

    print(f"\nWorking Memory ({len(meta.get('working_memory', []))} items):")
    for w in meta.get("working_memory", [])[-3:]:
        print(f"  - {w['item'][:60]}")

    print(f"\nMeta-Thoughts ({len(meta.get('meta_thoughts', []))}):")
    for m in meta.get("meta_thoughts", [])[-3:]:
        print(f"  - {m['thought'][:60]}")

    if meta.get("user_model"):
        print(f"\nUser Model: {meta['user_model']}")


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) == 1:
        init_model()
        show_model()
        show_meta()
    elif sys.argv[1] == "show":
        show_model()
        show_meta()
    elif sys.argv[1] == "init":
        init_model()
    elif sys.argv[1] == "update" and len(sys.argv) > 2:
        update_model(trajectory_event=" ".join(sys.argv[2:]))
    elif sys.argv[1] == "meta":
        if len(sys.argv) > 2:
            if sys.argv[2] == "show":
                show_meta()
            elif sys.argv[2] == "level" and len(sys.argv) > 3:
                set_awareness_level(sys.argv[3])
            elif sys.argv[2] == "state" and len(sys.argv) > 3:
                set_cognitive_state(sys.argv[3])
            elif sys.argv[2] == "clear":
                clear_working_memory()
            elif sys.argv[2] == "think":
                thought = " ".join(sys.argv[3:])
                think_about_thinking(thought)
            else:
                print("Usage: meta [show|level <level>|state <state>|clear|think <thought>]")
        else:
            show_meta()
    elif sys.argv[1] == "assess":
        results = assess_all_capabilities()
        for domain, data in results.items():
            print(f"  {data['label']}: {data['score']:.2f}")
            for e in data["evidence"]:
                print(f"    - {e}")
    elif sys.argv[1] == "daily":
        daily_update()
    elif sys.argv[1] == "history":
        history = load_capability_history()
        if not history["snapshots"]:
            print("No history yet. Run 'daily' first.")
        else:
            for snap in history["snapshots"][-7:]:
                scores = snap["scores"]
                avg = sum(scores.values()) / len(scores) if scores else 0
                print(f"  {snap['date']}: avg={avg:.2f} | " + " ".join(f"{k[:4]}={v:.2f}" for k, v in scores.items()))
    elif sys.argv[1] == "regression":
        history = load_capability_history()
        current = assess_all_capabilities()
        result = check_weekly_regression(current, history)
        if result["alerts"]:
            print("=== Weekly Regression Check ===")
            for a in result["alerts"]:
                print(f"  {a}")
            if result["tasks"]:
                print(f"\n{len(result['tasks'])} remediation tasks would be generated.")
        else:
            print("No weekly regressions detected (all domains within 10% of last week).")
    else:
        print("""Usage:
  python self_model.py [show|init|update <event>]
  python self_model.py assess              - Run capability assessment (scores only)
  python self_model.py daily               - Full daily update with diffs & alerts
  python self_model.py history             - Show capability score history
  python self_model.py regression          - Check for week-over-week regressions (>10%)
  python self_model.py meta [show|level <level>|state <state>|clear|think <thought>]

Levels: operational, reflective, meta
States: active, reflective, idle, processing""")
