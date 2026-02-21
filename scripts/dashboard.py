#!/usr/bin/env python3
"""
Clarvis Self-Monitoring Dashboard
Shows brain stats, goal progress, and evolution velocity in real-time.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))
from brain import brain

DASHBOARD_DIR = Path("/home/agent/.openclaw/workspace/data/dashboard")
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

def get_brain_stats():
    """Get current brain statistics."""
    stats = brain.stats()
    return {
        "total_memories": stats.get("total_memories", 0),
        "collections": stats.get("collections", {}),
        "timestamp": datetime.now().isoformat()
    }

def get_goal_progress():
    """Get all goal progress using get_goals() (normalized output)."""
    goals = brain.get_goals()
    result = []
    for g in goals:
        name = g["metadata"].get("goal", "unknown")
        progress = g["metadata"].get("progress", 0)
        result.append(f"{name}: {progress}%")
    return result

def get_evolution_velocity():
    """Calculate evolution velocity from recent memory activity."""
    # Get memories from last 24 hours
    try:
        recent = brain.recall_recent(days=1)
        return {
            "memories_24h": len(recent),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"memories_24h": 0, "error": str(e)}

def get_reasoning_chains():
    """Count active reasoning chains."""
    chains_dir = Path("/home/agent/.openclaw/workspace/data/reasoning_chains")
    if chains_dir.exists():
        chains = list(chains_dir.glob("chain_*.json"))
        return len(chains)
    return 0

def generate_dashboard():
    """Generate the monitoring dashboard HTML."""
    brain_stats = get_brain_stats()
    goals = get_goal_progress()
    velocity = get_evolution_velocity()
    chains = get_reasoning_chains()
    
    # Calculate some derived metrics
    memory_growth = "↑" if brain_stats["total_memories"] > 100 else "→"
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Clarvis Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            padding: 20px;
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
        h2 {{ color: #8b949e; margin-top: 30px; }}
        .metric {{ 
            display: inline-block; 
            background: #161b22; 
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 15px 25px;
            margin: 10px 10px 10px 0;
        }}
        .metric-value {{ 
            font-size: 32px; 
            font-weight: bold;
            color: #58a6ff;
        }}
        .metric-label {{ 
            font-size: 12px; 
            color: #8b949e;
            text-transform: uppercase;
        }}
        .collection {{
            background: #21262d;
            padding: 8px 12px;
            margin: 4px;
            border-radius: 4px;
            font-size: 13px;
        }}
        .timestamp {{ color: #484f58; font-size: 12px; margin-top: 30px; }}
        .status-ok {{ color: #3fb950; }}
    </style>
</head>
<body>
    <h1>🦞 Clarvis Monitoring Dashboard</h1>
    
    <h2>Brain Stats</h2>
    <div class="metric">
        <div class="metric-value">{brain_stats['total_memories']} {memory_growth}</div>
        <div class="metric-label">Total Memories</div>
    </div>
    <div class="metric">
        <div class="metric-value">{chains}</div>
        <div class="metric-label">Reasoning Chains</div>
    </div>
    <div class="metric">
        <div class="metric-value">{velocity.get('memories_24h', 0)}</div>
        <div class="metric-label">Memories (24h)</div>
    </div>
    
    <h2>Collections</h2>
    <div>
"""
    
    for coll, count in brain_stats["collections"].items():
        html += f'        <span class="collection">{coll}: {count}</span>\n'
    
    html += """    </div>
    
    <h2>Goals</h2>
    <div>
"""
    
    for goal in goals[:10]:
        html += f'        <div class="collection">{goal[:100]}</div>\n'
    
    html += f"""    </div>
    
    <div class="timestamp">
        Last updated: {brain_stats['timestamp']} | Status: <span class="status-ok">● Active</span>
    </div>
</body>
</html>"""
    
    # Write HTML file
    dashboard_file = DASHBOARD_DIR / "index.html"
    dashboard_file.write_text(html)
    
    # Also write JSON for API access
    api_data = {
        "brain": brain_stats,
        "velocity": velocity,
        "chains": chains,
        "goals": goals[:10]
    }
    api_file = DASHBOARD_DIR / "status.json"
    api_file.write_text(json.dumps(api_data, indent=2))
    
    return html

if __name__ == "__main__":
    html = generate_dashboard()
    print(f"Dashboard generated: {DASHBOARD_DIR}/index.html")
    print(f"API status: {DASHBOARD_DIR}/status.json")