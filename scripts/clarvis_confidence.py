#!/usr/bin/env python3
"""
Clarvis Confidence Gating - Phase 5
Track confidence levels and outcomes for self-calibration
"""

import json
import os
from datetime import datetime, timezone

CALIBRATION_DIR = "/home/agent/.openclaw/workspace/data/calibration"
os.makedirs(CALIBRATION_DIR, exist_ok=True)

def log_prediction(action: str, confidence: str, reasoning: str, outcome: str = None):
    """Log a confidence-gated action for later calibration"""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "confidence": confidence,  # HIGH, MEDIUM, LOW, UNKNOWN
        "reasoning": reasoning,
        "outcome": outcome  # filled later: correct, wrong, partially_correct
    }
    
    filepath = f"{CALIBRATION_DIR}/predictions.jsonl"
    with open(filepath, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    return entry

def get_calibration_stats() -> dict:
    """Get calibration statistics"""
    filepath = f"{CALIBRATION_DIR}/predictions.jsonl"
    if not os.path.exists(filepath):
        return {"total": 0, "by_confidence": {}}
    
    stats = {"total": 0, "by_confidence": {}}
    
    with open(filepath, "r") as f:
        for line in f:
            entry = json.loads(line)
            stats["total"] += 1
            
            conf = entry.get("confidence", "UNKNOWN")
            if conf not in stats["by_confidence"]:
                stats["by_confidence"][conf] = {"total": 0, "correct": 0}
            
            stats["by_confidence"][conf]["total"] += 1
            
            if entry.get("outcome") == "correct":
                stats["by_confidence"][conf]["correct"] += 1
    
    return stats

# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "log" and len(sys.argv) > 3:
            action = sys.argv[2]
            confidence = sys.argv[3]
            reasoning = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else ""
            result = log_prediction(action, confidence, reasoning)
            print(f"Logged: {action} ({confidence})")
        
        elif cmd == "stats":
            stats = get_calibration_stats()
            print(f"Total predictions: {stats['total']}")
            for conf, data in stats.get("by_confidence", {}).items():
                if data["total"] > 0:
                    pct = (data["correct"] / data["total"]) * 100
                    print(f"  {conf}: {data['correct']}/{data['total']} = {pct:.0f}%")
        
        elif cmd == "update" and len(sys.argv) > 4:
            # Update outcome: python clarvis_confidence.py update <action> <outcome>
            action = sys.argv[2]
            outcome = sys.argv[3]
            # Note: This would need to find and update the entry - simplified for now
            print(f"Would update {action} -> {outcome}")
        
        else:
            print("Usage:")
            print("  confidence.py log <action> <HIGH|MEDIUM|LOW|UNKNOWN> <reasoning>")
            print("  confidence.py stats")
    else:
        print("Clarvis Confidence Gating - Phase 5")
        print(f"Data: {CALIBRATION_DIR}/")