#!/usr/bin/env python3
"""Brain Effectiveness Scorer — weekly-gated memory in clarvis-learnings.

Aggregates CLR value-add, episode success rate, reasoning chain quality,
and daily brain eval useful_rate into a single retrievable memory.

Designed to answer: "Does the brain actually help Clarvis make better decisions?"

History is appended every run for trend tracking. Brain memory storage is
gated to once per ISO week to avoid daily duplicates in clarvis-learnings.

Usage:
    python3 scripts/metrics/brain_effectiveness.py compute             # Print JSON only
    python3 scripts/metrics/brain_effectiveness.py compute_and_store   # Compute + store (weekly-gated)
    python3 scripts/metrics/brain_effectiveness.py compute_and_store_force  # Compute + store (always)
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA = os.path.join(WORKSPACE, "data")
HISTORY_FILE = os.path.join(DATA, "brain_effectiveness_history.jsonl")
MAX_HISTORY = 90


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _load_clr():
    """Load CLR benchmark — value_add and dimension scores."""
    clr = _load_json(os.path.join(DATA, "clr_benchmark.json"))
    if not clr:
        return {"clr": None, "value_add": None, "task_success": None}
    dims = clr.get("dimensions", {})
    return {
        "clr": clr.get("clr"),
        "value_add": clr.get("value_add"),
        "task_success": dims.get("task_success", {}).get("score"),
        "memory_quality": dims.get("memory_quality", {}).get("score"),
        "retrieval_precision": dims.get("retrieval_precision", {}).get("score"),
        "integration_dynamics": dims.get("integration_dynamics", {}).get("score"),
    }


def _load_episode_stats():
    """Load episode success rate from episodic memory."""
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        stats = em.get_stats()
        outcomes = stats.get("outcomes", {})
        total = stats.get("total", 0)
        success = outcomes.get("success", 0)
        return {
            "total_episodes": total,
            "success_count": success,
            "success_rate": success / total if total > 0 else 0,
            "avg_valence": stats.get("avg_valence", 0),
        }
    except Exception as e:
        print(f"[brain_effectiveness] Episode stats error: {e}", file=sys.stderr)
        return {"total_episodes": 0, "success_count": 0, "success_rate": 0, "avg_valence": 0}


def _load_reasoning_chain_quality():
    """Load reasoning chain meta — calibration and depth."""
    meta = _load_json(os.path.join(DATA, "reasoning_chains", "reasoning_meta.json"))
    if not meta:
        return {"chain_calibration": None, "chain_avg_depth": None, "chain_sessions": 0}
    cal = meta.get("calibration", {})
    return {
        "chain_calibration": cal.get("accuracy"),
        "chain_avg_depth": meta.get("avg_depth"),
        "chain_sessions": meta.get("total_sessions", 0),
    }


def _load_brain_eval():
    """Load daily brain eval — useful_rate and quality_score."""
    eval_data = _load_json(os.path.join(DATA, "daily_brain_eval", "latest.json"))
    if not eval_data:
        return {"eval_useful_rate": None, "eval_quality_score": None}
    retrieval = eval_data.get("retrieval", {})
    assessment = eval_data.get("assessment", {})
    return {
        "eval_useful_rate": retrieval.get("useful_rate"),
        "eval_quality_score": assessment.get("quality_score"),
        "eval_avg_speed_ms": retrieval.get("avg_speed_ms"),
        "eval_weakest_domains": [
            f.get("domain") for f in retrieval.get("failures", [])
        ],
    }


def _load_previous():
    """Load previous effectiveness score for delta computation."""
    if not os.path.exists(HISTORY_FILE):
        return None
    try:
        with open(HISTORY_FILE) as f:
            lines = f.readlines()
        if lines:
            return json.loads(lines[-1])
    except (json.JSONDecodeError, IndexError):
        pass
    return None


def compute():
    """Compute brain effectiveness score and components."""
    clr = _load_clr()
    episodes = _load_episode_stats()
    chains = _load_reasoning_chain_quality()
    brain_eval = _load_brain_eval()

    # Weighted composite — focuses on "does the brain help?"
    # CLR value-add (0.30): direct measure of brain's contribution over baseline
    # Episode success rate (0.25): are tasks succeeding?
    # Brain eval quality (0.25): is retrieval actually useful?
    # Reasoning chain quality (0.10): are chains well-formed?
    # Integration dynamics (0.10): does the brain connect information?
    components = {}
    weights = {}

    # CLR value-add normalized to 0-1 (value_add typically 0-0.8)
    va = clr.get("value_add")
    if va is not None:
        components["clr_value_add"] = min(va / 0.8, 1.0)
        weights["clr_value_add"] = 0.30

    sr = episodes.get("success_rate")
    if sr is not None:
        components["episode_success_rate"] = sr
        weights["episode_success_rate"] = 0.25

    eq = brain_eval.get("eval_quality_score")
    if eq is not None:
        components["brain_eval_quality"] = eq
        weights["brain_eval_quality"] = 0.25

    cc = chains.get("chain_calibration")
    if cc is not None:
        components["reasoning_chain_quality"] = cc
        weights["reasoning_chain_quality"] = 0.10

    ig = clr.get("integration_dynamics")
    if ig is not None:
        components["integration_dynamics"] = ig
        weights["integration_dynamics"] = 0.10

    # Compute weighted score (re-normalize if some components missing)
    total_weight = sum(weights.values())
    if total_weight > 0:
        effectiveness = sum(
            components[k] * weights[k] for k in components
        ) / total_weight
    else:
        effectiveness = 0.0

    # Identify weakest component
    weakest = min(components, key=components.get) if components else "unknown"

    # Delta from previous
    prev = _load_previous()
    delta = None
    if prev and "effectiveness" in prev:
        delta = round(effectiveness - prev["effectiveness"], 4)

    result = {
        "effectiveness": round(effectiveness, 4),
        "components": {k: round(v, 4) for k, v in components.items()},
        "weights": weights,
        "weakest": weakest,
        "delta": delta,
        "raw": {
            "clr": clr.get("clr"),
            "clr_value_add": clr.get("value_add"),
            "episode_success_rate": episodes.get("success_rate"),
            "episode_total": episodes.get("total_episodes"),
            "episode_success_count": episodes.get("success_count"),
            "chain_calibration": chains.get("chain_calibration"),
            "chain_avg_depth": chains.get("chain_avg_depth"),
            "chain_sessions": chains.get("chain_sessions"),
            "eval_useful_rate": brain_eval.get("eval_useful_rate"),
            "eval_quality_score": brain_eval.get("eval_quality_score"),
            "eval_avg_speed_ms": brain_eval.get("eval_avg_speed_ms"),
            "eval_weakest_domains": brain_eval.get("eval_weakest_domains", []),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return result


def _append_history(result):
    """Append result to history JSONL (capped at MAX_HISTORY)."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")
    # Trim if needed
    try:
        with open(HISTORY_FILE) as f:
            lines = f.readlines()
        if len(lines) > MAX_HISTORY:
            with open(HISTORY_FILE, "w") as f:
                f.writelines(lines[-MAX_HISTORY:])
    except Exception:
        pass


def _build_narrative(result):
    """Build human-readable narrative for brain memory storage."""
    r = result["raw"]
    eff = result["effectiveness"]
    delta_str = ""
    if result["delta"] is not None:
        sign = "+" if result["delta"] >= 0 else ""
        delta_str = f" ({sign}{result['delta']:.3f} vs previous)"

    parts = [
        f"Brain effectiveness: {eff:.1%}{delta_str}.",
        f"CLR value-add: {r['clr_value_add']:.3f} (brain adds {r['clr_value_add']:.1%} over baseline)." if r.get("clr_value_add") is not None else None,
        f"Episode success: {r['episode_success_rate']:.1%} ({r['episode_success_count']}/{r['episode_total']})." if r.get("episode_success_rate") is not None else None,
        f"Reasoning chains: calibration={r['chain_calibration']:.1%}, avg depth={r['chain_avg_depth']:.1f}, sessions={r['chain_sessions']}." if r.get("chain_calibration") is not None else None,
        f"Brain eval: useful_rate={r['eval_useful_rate']:.1%}, quality={r['eval_quality_score']:.2f}, speed={r['eval_avg_speed_ms']}ms." if r.get("eval_useful_rate") is not None else None,
        f"Weakest component: {result['weakest']}.",
        f"Weak retrieval domains: {', '.join(r['eval_weakest_domains'])}." if r.get("eval_weakest_domains") else None,
    ]
    return " ".join(p for p in parts if p)


def store_in_brain(result):
    """Store brain effectiveness as a retrievable memory in clarvis-learnings."""
    from clarvis.brain import brain

    narrative = _build_narrative(result)
    ts = result["timestamp"][:10]  # YYYY-MM-DD

    # Deduplicate: search for existing brain_effectiveness memories from today
    # and skip if already stored
    try:
        existing = brain.recall(f"brain effectiveness {ts}")
        for item in existing[:3]:
            doc = item.get("document", "") if isinstance(item, dict) else str(item)
            if "Brain effectiveness:" in doc and ts in doc:
                print(f"[brain_effectiveness] Already stored for {ts}, updating.")
                break
    except Exception:
        pass

    # Store with high importance — this answers "does the brain help?"
    memory_id = f"brain_effectiveness_{ts}"
    brain.store(
        narrative,
        collection="clarvis-learnings",
        importance=0.85,
        tags=["brain_effectiveness", "metrics", "weekly", "clr", "episodes", "reasoning"],
        source="brain_effectiveness_scorer",
        memory_id=memory_id,
    )
    print(f"[brain_effectiveness] Stored: {narrative[:120]}...")
    return narrative


def _should_store_weekly():
    """Check if a brain effectiveness memory was already stored this ISO week.

    Returns True if no entry exists for the current week in the history file.
    This gates brain storage to weekly cadence even when called daily.
    """
    if not os.path.exists(HISTORY_FILE):
        return True
    now = datetime.now(timezone.utc)
    current_week = now.isocalendar()[:2]  # (year, week_number)
    try:
        with open(HISTORY_FILE) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "")
                    if ts:
                        entry_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if entry_dt.isocalendar()[:2] == current_week:
                            return False  # Already stored this week
                except (json.JSONDecodeError, ValueError):
                    continue
    except IOError:
        return True
    return True


def compute_and_store():
    """Compute effectiveness, always append to history, store in brain weekly.

    History is appended every run (for trend tracking), but brain memory
    storage is gated to once per ISO week to avoid polluting clarvis-learnings
    with daily duplicates. Use compute_and_store_force() to bypass the gate.
    """
    result = compute()
    _append_history(result)
    if _should_store_weekly():
        narrative = store_in_brain(result)
        result["stored_in_brain"] = True
    else:
        print("[brain_effectiveness] Skipping brain storage — already stored this week.")
        result["stored_in_brain"] = False
    print(json.dumps(result, indent=2))
    return result


def compute_and_store_force():
    """Compute effectiveness and store in brain unconditionally (bypass weekly gate)."""
    result = compute()
    _append_history(result)
    store_in_brain(result)
    result["stored_in_brain"] = True
    print(json.dumps(result, indent=2))
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: brain_effectiveness.py [compute|compute_and_store]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "compute":
        result = compute()
        print(json.dumps(result, indent=2))
    elif cmd == "compute_and_store":
        compute_and_store()
    elif cmd == "compute_and_store_force":
        compute_and_store_force()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
