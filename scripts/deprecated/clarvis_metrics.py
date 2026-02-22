#!/usr/bin/env python3
"""
Clarvis Metrics - Phase 6
Track performance metrics for self-improvement
"""

import json
import os
from datetime import datetime, timezone

METRICS_DIR = "/home/agent/.openclaw/workspace/data/metrics"
os.makedirs(METRICS_DIR, exist_ok=True)

def log_event(event_type: str, details: dict):
    """Log a metric event"""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "details": details
    }
    
    filepath = f"{METRICS_DIR}/{event_type}.jsonl"
    with open(filepath, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    return entry

def get_metric(event_type: str) -> list:
    """Get all events of a type"""
    filepath = f"{METRICS_DIR}/{event_type}.jsonl"
    if not os.path.exists(filepath):
        return []
    
    events = []
    with open(filepath, "r") as f:
        for line in f:
            events.append(json.loads(line))
    return events

def get_summary() -> dict:
    """Get summary of all metrics"""
    summary = {}
    
    for filename in os.listdir(METRICS_DIR):
        if filename.endswith(".jsonl"):
            event_type = filename[:-6]
            events = get_metric(event_type)
            summary[event_type] = len(events)
    
    return summary

# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "log" and len(sys.argv) > 3:
            event_type = sys.argv[2]
            details = json.loads(" ".join(sys.argv[3:]))
            log_event(event_type, details)
            print(f"Logged: {event_type}")
        
        elif cmd == "summary":
            summary = get_summary()
            print("Metrics Summary:")
            for event_type, count in summary.items():
                print(f"  {event_type}: {count}")
        
        elif cmd == "list" and len(sys.argv) > 2:
            events = get_metric(sys.argv[2])
            print(f"{sys.argv[2]} ({len(events)}):")
            for e in events[-5:]:
                print(f"  - {e['timestamp'][:19]}: {e['details']}")
        
        else:
            print("Usage:")
            print("  metrics.py log <type> <json_details>")
            print("  metrics.py summary")
            print("  metrics.py list <type>")
    else:
        print("Clarvis Metrics - Phase 6")
        print(f"Data: {METRICS_DIR}/")