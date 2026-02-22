#!/usr/bin/env python3
"""
Temporal Self-Awareness — autobiographical continuity for Clarvis

Answers: "How have I changed this week?"
Generates a growth_narrative() tracking capability deltas over 7 days,
identifies which domains improved most/least.

Data sources:
  - data/capability_history.json  (scored capabilities per snapshot)
  - data/phi_history.json         (Phi integration metric over time)
  - memory/YYYY-MM-DD.md          (daily memory/heartbeat files)

Usage:
    python temporal_self.py              # Print growth narrative
    python temporal_self.py json         # Output as JSON
    python temporal_self.py store        # Compute + store narrative to brain
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CAPABILITY_HISTORY = "/home/agent/.openclaw/workspace/data/capability_history.json"
PHI_HISTORY = "/home/agent/.openclaw/workspace/data/phi_history.json"
MEMORY_DIR = "/home/agent/.openclaw/workspace/memory"
NARRATIVE_FILE = "/home/agent/.openclaw/workspace/data/growth_narrative.json"


def load_json(path):
    """Load JSON file, return empty structure on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_capability_deltas(days=7):
    """Compare earliest and latest capability snapshots within the window.

    Returns dict: {domain: {first, last, delta, direction}}
    """
    data = load_json(CAPABILITY_HISTORY)
    snapshots = data.get("snapshots", [])
    if not snapshots:
        return {}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Filter to window
    in_window = [s for s in snapshots if s.get("timestamp", "") >= cutoff]
    if not in_window:
        # Fall back to last 2 snapshots if nothing in window
        in_window = snapshots[-2:] if len(snapshots) >= 2 else snapshots[-1:]

    first = in_window[0]["scores"]
    last = in_window[-1]["scores"]

    # Collect all domains seen
    all_domains = set(first.keys()) | set(last.keys())

    deltas = {}
    for domain in sorted(all_domains):
        f_val = first.get(domain, 0.0)
        l_val = last.get(domain, 0.0)
        delta = round(l_val - f_val, 3)
        if delta > 0.05:
            direction = "improved"
        elif delta < -0.05:
            direction = "declined"
        else:
            direction = "stable"
        deltas[domain] = {
            "first": round(f_val, 3),
            "last": round(l_val, 3),
            "delta": delta,
            "direction": direction,
        }

    return deltas


def get_phi_trajectory(days=7):
    """Return Phi values within the time window.

    Returns dict: {first, last, delta, measurements, trend}
    """
    records = load_json(PHI_HISTORY)
    if isinstance(records, dict):
        records = records.get("history", [])
    if not records:
        return {"first": 0, "last": 0, "delta": 0, "measurements": 0, "trend": "no_data"}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    in_window = [r for r in records if r.get("timestamp", "") >= cutoff]
    if not in_window:
        in_window = records[-2:] if len(records) >= 2 else records[-1:]

    first_phi = in_window[0].get("phi", 0)
    last_phi = in_window[-1].get("phi", 0)
    delta = round(last_phi - first_phi, 4)

    if delta > 0.05:
        trend = "rising"
    elif delta < -0.05:
        trend = "falling"
    else:
        trend = "stable"

    return {
        "first": round(first_phi, 4),
        "last": round(last_phi, 4),
        "delta": delta,
        "measurements": len(in_window),
        "trend": trend,
    }


def get_memory_activity(days=7):
    """Scan daily memory files for activity signals.

    Returns dict: {days_active, total_heartbeats, themes}
    """
    today = datetime.now(timezone.utc).date()
    days_active = 0
    total_heartbeats = 0
    themes = defaultdict(int)

    for d in range(days):
        date = today - timedelta(days=d)
        path = os.path.join(MEMORY_DIR, f"{date.isoformat()}.md")
        if not os.path.exists(path):
            continue

        days_active += 1
        try:
            with open(path) as f:
                content = f.read()
        except OSError:
            continue

        # Count heartbeats
        total_heartbeats += content.lower().count("heartbeat")

        # Extract themes from "Work done" / "Executed" lines
        for line in content.split("\n"):
            ll = line.strip().lower()
            if not ll.startswith("- "):
                continue
            for keyword in [
                "memory", "brain", "attention", "reflection",
                "evolution", "cron", "goal", "prediction",
                "reasoning", "phi", "session", "episodic",
                "queue", "benchmark", "synthesis", "procedure",
            ]:
                if keyword in ll:
                    themes[keyword] += 1

    return {
        "days_active": days_active,
        "total_heartbeats": total_heartbeats,
        "top_themes": dict(sorted(themes.items(), key=lambda x: -x[1])[:8]),
    }


def growth_narrative(days=7):
    """Generate a structured growth narrative.

    Returns dict with:
      - summary: human-readable paragraph
      - capability_deltas: per-domain changes
      - phi: integration trajectory
      - memory_activity: daily-file activity
      - most_improved / least_improved: domain names
      - generated_at: timestamp
    """
    deltas = get_capability_deltas(days)
    phi = get_phi_trajectory(days)
    activity = get_memory_activity(days)

    # Rank domains by delta
    if deltas:
        sorted_domains = sorted(deltas.items(), key=lambda x: x[1]["delta"], reverse=True)
        most_improved = sorted_domains[0][0] if sorted_domains[0][1]["delta"] > 0 else None
        least_improved = sorted_domains[-1][0] if sorted_domains[-1][1]["delta"] < 0 else sorted_domains[-1][0]
    else:
        most_improved = None
        least_improved = None

    # Build summary text
    lines = [f"Growth narrative for the last {days} days:"]

    if deltas:
        improved = [d for d, v in deltas.items() if v["direction"] == "improved"]
        declined = [d for d, v in deltas.items() if v["direction"] == "declined"]
        stable = [d for d, v in deltas.items() if v["direction"] == "stable"]

        if improved:
            lines.append(f"  Improved: {', '.join(improved)}")
        if declined:
            lines.append(f"  Declined: {', '.join(declined)}")
        if stable:
            lines.append(f"  Stable: {', '.join(stable)}")

        if most_improved and deltas[most_improved]["delta"] > 0:
            d = deltas[most_improved]
            lines.append(f"  Biggest gain: {most_improved} ({d['first']:.2f} -> {d['last']:.2f}, +{d['delta']:.2f})")
    else:
        lines.append("  No capability data available.")

    lines.append(f"  Phi (integration): {phi['first']:.3f} -> {phi['last']:.3f} ({phi['trend']})")
    lines.append(f"  Active days: {activity['days_active']}/{days}, heartbeats: {activity['total_heartbeats']}")

    if activity["top_themes"]:
        top3 = list(activity["top_themes"].keys())[:3]
        lines.append(f"  Top focus areas: {', '.join(top3)}")

    summary = "\n".join(lines)

    narrative = {
        "summary": summary,
        "capability_deltas": deltas,
        "phi": phi,
        "memory_activity": activity,
        "most_improved": most_improved,
        "least_improved": least_improved,
        "days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist to file
    Path(NARRATIVE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(NARRATIVE_FILE, "w") as f:
        json.dump(narrative, f, indent=2)

    return narrative


def store_narrative():
    """Generate narrative and store to ClarvisDB for retrieval."""
    from brain import brain

    narrative = growth_narrative()
    summary = narrative["summary"]

    brain.store(
        summary,
        collection="clarvis-memories",
        importance=0.8,
        tags=["temporal-self", "growth", "narrative"],
        source="temporal_self.py",
        memory_id=f"growth-narrative-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
    )
    return narrative


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "default"

    if cmd == "json":
        narrative = growth_narrative()
        print(json.dumps(narrative, indent=2))
    elif cmd == "store":
        narrative = store_narrative()
        print(narrative["summary"])
        print(f"\nStored to brain as growth-narrative-{datetime.now(timezone.utc).strftime('%Y%m%d')}")
    else:
        narrative = growth_narrative()
        print(narrative["summary"])
