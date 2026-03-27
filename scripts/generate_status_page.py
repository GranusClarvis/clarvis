#!/usr/bin/env python3
"""Generate a static status page for Clarvis.

Pulls live brain stats, PI score, and cron health to produce site/index.html.
Designed to be run on-demand or via cron for periodic refresh.

Usage:
    python3 scripts/generate_status_page.py           # Generate site/index.html
    python3 scripts/generate_status_page.py --json     # Dump stats as JSON (for API)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/home/agent/.openclaw/workspace")
SITE_DIR = WORKSPACE / "site"
METRICS_FILE = WORKSPACE / "data" / "performance_metrics.json"
OUTPUT_FILE = SITE_DIR / "index.html"


def get_brain_stats() -> dict:
    """Get brain stats without importing clarvis (faster, reads ChromaDB directly)."""
    try:
        sys.path.insert(0, str(WORKSPACE / "scripts"))
        from clarvis.brain import brain
        stats = brain.stats()
        return {
            "total_memories": stats.get("total_memories", 0),
            "collections": stats.get("collections", {}),
            "graph_nodes": stats.get("graph_nodes", 0),
            "graph_edges": stats.get("graph_edges", 0),
        }
    except Exception as e:
        return {"total_memories": 0, "error": str(e)}


def get_pi_metrics() -> dict:
    """Load latest PI metrics from performance_metrics.json."""
    try:
        with open(METRICS_FILE) as f:
            data = json.load(f)
        metrics = data.get("metrics", {})
        results = data.get("results", {})
        # Calculate composite PI
        pi_score = None
        for key, info in results.items():
            if key == "pi_composite":
                pi_score = info.get("value")
        # If no composite, compute from individual scores
        if pi_score is None:
            scores = []
            for info in results.values():
                status = info.get("status", "")
                if status == "PASS":
                    scores.append(1.0)
                elif status == "WARN":
                    scores.append(0.5)
                elif status == "FAIL":
                    scores.append(0.0)
            pi_score = sum(scores) / len(scores) if scores else 0.0

        return {
            "pi_score": round(pi_score, 3),
            "timestamp": data.get("timestamp", ""),
            "brain_query_avg_ms": metrics.get("brain_query_avg_ms"),
            "retrieval_hit_rate": metrics.get("retrieval_hit_rate"),
            "episode_success_rate": metrics.get("episode_success_rate"),
            "phi": metrics.get("phi"),
            "load_degradation_pct": metrics.get("load_degradation_pct"),
            "task_quality_score": metrics.get("task_quality_score"),
            "results": {k: v.get("status", "?") for k, v in results.items()},
        }
    except Exception as e:
        return {"pi_score": 0.0, "error": str(e)}


def get_cron_summary() -> dict:
    """Quick cron health: count of active cron entries."""
    import subprocess
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5
        )
        cron_re = re.compile(r"^\s*(@\w+|[0-9*])")
        lines = [
            l for l in result.stdout.splitlines()
            if cron_re.match(l)
        ]
        return {"active_jobs": len(lines)}
    except Exception:
        return {"active_jobs": 0}


def generate_stats_json() -> dict:
    """Combine all stats into a single JSON blob."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brain": get_brain_stats(),
        "performance": get_pi_metrics(),
        "cron": get_cron_summary(),
    }


def render_html(stats: dict) -> str:
    """Render the status page HTML from stats dict."""
    brain = stats["brain"]
    perf = stats["performance"]
    cron = stats["cron"]
    ts = stats["generated_at"][:19].replace("T", " ") + " UTC"

    # Build collection rows
    collections = brain.get("collections", {})
    collection_rows = ""
    for name, count in sorted(collections.items()):
        collection_rows += f'            <tr><td>{name}</td><td>{count:,}</td></tr>\n'

    # Build metric rows
    results = perf.get("results", {})
    metric_rows = ""
    status_class = {"PASS": "pass", "WARN": "warn", "FAIL": "fail"}
    for name, status in sorted(results.items()):
        cls = status_class.get(status, "")
        metric_rows += f'            <tr><td>{name}</td><td class="{cls}">{status}</td></tr>\n'

    # PI gauge color
    pi = perf.get("pi_score", 0)
    if pi >= 0.8:
        pi_color = "#4caf50"
    elif pi >= 0.6:
        pi_color = "#ff9800"
    else:
        pi_color = "#f44336"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clarvis — Cognitive Agent Status</title>
<style>
:root {{
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --yellow: #d29922;
    --red: #f85149;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
    max-width: 960px;
    margin: 0 auto;
}}
h1 {{ color: var(--accent); margin-bottom: 0.5rem; font-size: 2rem; }}
h2 {{ color: var(--text); margin: 2rem 0 1rem; font-size: 1.3rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
.subtitle {{ color: var(--text-dim); margin-bottom: 2rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin: 1.5rem 0; }}
.card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
}}
.card h3 {{ color: var(--accent); font-size: 1rem; margin-bottom: 0.75rem; }}
.stat {{ font-size: 2.5rem; font-weight: 700; }}
.stat-label {{ color: var(--text-dim); font-size: 0.85rem; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; }}
th, td {{ padding: 0.4rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.9rem; }}
th {{ color: var(--text-dim); font-weight: 600; }}
.pass {{ color: var(--green); font-weight: 600; }}
.warn {{ color: var(--yellow); font-weight: 600; }}
.fail {{ color: var(--red); font-weight: 600; }}
.arch-diagram {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    white-space: pre;
    overflow-x: auto;
    line-height: 1.4;
    color: var(--text-dim);
}}
.footer {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 0.8rem;
    text-align: center;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>

<h1>Clarvis</h1>
<p class="subtitle">Dual-layer cognitive agent &mdash; conscious reasoning + autonomous subconscious evolution</p>

<div class="grid">
    <div class="card">
        <h3>Performance Index</h3>
        <div class="stat" style="color: {pi_color}">{pi:.1%}</div>
        <div class="stat-label">Composite health score across 8 dimensions</div>
    </div>
    <div class="card">
        <h3>Brain Memories</h3>
        <div class="stat">{brain.get('total_memories', 0):,}</div>
        <div class="stat-label">Across {len(collections)} collections</div>
    </div>
    <div class="card">
        <h3>Graph Edges</h3>
        <div class="stat">{brain.get('graph_edges', 0):,}</div>
        <div class="stat-label">{brain.get('graph_nodes', 0):,} nodes &bull; Hebbian associative network</div>
    </div>
    <div class="card">
        <h3>Autonomous Jobs</h3>
        <div class="stat">{cron.get('active_jobs', 0)}</div>
        <div class="stat-label">Active cron entries &bull; subconscious layer</div>
    </div>
</div>

<h2>Architecture</h2>
<div class="arch-diagram">
Conscious Layer (MiniMax M2.5 via OpenClaw Gateway)
  \u251c\u2500\u2500 Direct chat with user via Telegram / Discord
  \u251c\u2500\u2500 Reads digest.md to internalize subconscious work
  \u2514\u2500\u2500 Spawns Claude Code for complex tasks

Subconscious Layer (Claude Code Opus via system crontab)
  \u251c\u2500\u2500 12x/day autonomous evolution heartbeats
  \u251c\u2500\u2500 Morning planning \u2192 evolution analysis \u2192 evening assessment
  \u251c\u2500\u2500 Research ingestion, dream engine, strategic audits
  \u2514\u2500\u2500 Results surface via memory/cron/digest.md

ClarvisDB Brain (ChromaDB + ONNX MiniLM, fully local)
  \u251c\u2500\u2500 {len(collections)} semantic collections \u2022 {brain.get('total_memories', 0):,} memories
  \u251c\u2500\u2500 Hebbian associative graph: {brain.get('graph_nodes', 0):,} nodes \u2022 {brain.get('graph_edges', 0):,} edges
  \u251c\u2500\u2500 Episodic memory \u2022 Procedural memory \u2022 Working memory
  \u2514\u2500\u2500 Cognitive workspace (Baddeley model: active/working/dormant buffers)

Cognitive Architecture
  \u251c\u2500\u2500 GWT attention (Global Workspace Theory salience scoring)
  \u251c\u2500\u2500 Meta-cognitive reasoning chains with confidence calibration
  \u251c\u2500\u2500 Self-model (7 capability domains) + Phi metric (IIT proxy)
  \u2514\u2500\u2500 Heartbeat pipeline: gate \u2192 preflight \u2192 execute \u2192 postflight</div>

<h2>Performance Metrics</h2>
<div class="grid">
    <div class="card">
        <h3>Brain Query Speed</h3>
        <div class="stat">{perf.get('brain_query_avg_ms', 0):.0f}<span style="font-size:1rem">ms</span></div>
        <div class="stat-label">Average query latency (target: &lt;800ms)</div>
    </div>
    <div class="card">
        <h3>Retrieval Quality</h3>
        <div class="stat">{(perf.get('retrieval_hit_rate', 0) or 0):.0%}</div>
        <div class="stat-label">Hit rate on known-answer queries</div>
    </div>
    <div class="card">
        <h3>Episode Success</h3>
        <div class="stat">{(perf.get('episode_success_rate', 0) or 0):.1%}</div>
        <div class="stat-label">Autonomous task success rate</div>
    </div>
    <div class="card">
        <h3>Phi (IIT proxy)</h3>
        <div class="stat">{perf.get('phi', 0):.3f}</div>
        <div class="stat-label">Integrated information / cross-module coherence</div>
    </div>
</div>

<table>
    <tr><th>Metric</th><th>Status</th></tr>
{metric_rows}</table>

<h2>Brain Collections</h2>
<table>
    <tr><th>Collection</th><th>Memories</th></tr>
{collection_rows}</table>

<div class="footer">
    <p>Generated {ts} &bull; <a href="https://github.com/GranusClarvis/clarvis">github.com/GranusClarvis/clarvis</a></p>
    <p>Clarvis is a cognitive agent experiment by Patrick / Inverse</p>
</div>

</body>
</html>"""
    return html


def main():
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    stats = generate_stats_json()

    if "--json" in sys.argv:
        print(json.dumps(stats, indent=2))
        return

    html = render_html(stats)
    OUTPUT_FILE.write_text(html)
    print(f"Generated {OUTPUT_FILE} ({len(html):,} bytes)")
    print(f"  Brain: {stats['brain'].get('total_memories', 0):,} memories")
    pi = stats["performance"].get("pi_score", 0)
    print(f"  PI: {pi:.1%}")
    print(f"  Cron: {stats['cron'].get('active_jobs', 0)} active jobs")


if __name__ == "__main__":
    main()
