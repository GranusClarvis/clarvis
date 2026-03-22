#!/usr/bin/env python3
"""Generate static HTML health dashboard from performance + watchdog data.

Usage:
    python3 scripts/generate_dashboard.py
    # Outputs: monitoring/dashboard.html

Data sources:
    - data/performance_history.jsonl  (PI, context_relevance, phi, etc.)
    - data/clr_history.jsonl          (CLR composite + dimensions)
    - monitoring/watchdog.log*        (cron success/fail per job)
"""

import json
import re
import glob
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
PERF_HISTORY = WORKSPACE / "data" / "performance_history.jsonl"
CLR_HISTORY = WORKSPACE / "data" / "clr_history.jsonl"
WATCHDOG_LOGS = sorted(glob.glob(str(WORKSPACE / "monitoring" / "watchdog.log*")))
OUTPUT = WORKSPACE / "monitoring" / "dashboard.html"

DAYS_WINDOW = 7


def load_jsonl(path: Path, days: int = 30) -> list[dict]:
    """Load JSONL, keep entries from last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []
    if not path.exists():
        return entries
    for line in path.read_text().strip().splitlines():
        try:
            rec = json.loads(line)
            ts = datetime.fromisoformat(rec["timestamp"])
            if ts >= cutoff:
                entries.append(rec)
        except (json.JSONDecodeError, KeyError):
            continue
    return entries


def parse_watchdog_logs(log_paths: list[str], days: int = DAYS_WINDOW) -> dict:
    """Parse watchdog logs into per-job, per-day status counts.

    Returns: {job_name: {date_str: {"ok": N, "fail": N}}}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results: dict[str, dict[str, dict[str, int]]] = {}
    date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})")
    job_ok = re.compile(r"^OK\s+(\S+)")
    job_fail = re.compile(r"^\s*\[FAILED?\s*\]\s*(\S+)", re.IGNORECASE)

    current_date = None

    for log_path in log_paths:
        try:
            text = open(log_path).read()
        except OSError:
            continue
        for line in text.splitlines():
            dm = date_pattern.search(line)
            if dm:
                try:
                    dt = datetime.strptime(dm.group(1), "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                    if dt >= cutoff:
                        current_date = dm.group(1)
                    else:
                        current_date = None
                except ValueError:
                    pass
                continue

            if current_date is None:
                continue

            m_ok = job_ok.match(line)
            if m_ok:
                job = m_ok.group(1)
                results.setdefault(job, {}).setdefault(current_date, {"ok": 0, "fail": 0})
                results[job][current_date]["ok"] += 1
                continue

            m_fail = job_fail.match(line)
            if m_fail:
                job = m_fail.group(1)
                results.setdefault(job, {}).setdefault(current_date, {"ok": 0, "fail": 0})
                results[job][current_date]["fail"] += 1

    return results


def generate_html(perf: list[dict], clr: list[dict], watchdog: dict) -> str:
    """Build self-contained HTML dashboard."""

    # Extract time series for charts
    pi_series = [
        {"t": r["timestamp"][:10], "v": round(r["pi"]["pi"], 4)}
        for r in perf
        if r.get("pi")
    ]
    cr_series = [
        {"t": r["timestamp"][:10], "v": round(r["metrics"].get("context_relevance", 0), 4)}
        for r in perf
        if r.get("metrics")
    ]
    phi_series = [
        {"t": r["timestamp"][:10], "v": round(r["metrics"].get("phi", 0), 4)}
        for r in perf
        if r.get("metrics")
    ]
    clr_series = [
        {"t": r["timestamp"][:10], "v": round(r.get("clr", 0), 4)}
        for r in clr
    ]

    # Latest values
    latest = perf[-1] if perf else {}
    latest_m = latest.get("metrics", {})
    latest_pi = latest.get("pi", {}).get("pi", 0)
    latest_cr = latest_m.get("context_relevance", 0)
    latest_phi = latest_m.get("phi", 0)
    latest_clr = clr[-1].get("clr", 0) if clr else 0
    latest_memories = latest_m.get("brain_total_memories", 0)
    latest_query_ms = latest_m.get("brain_query_avg_ms", 0)

    # Heatmap data: dates x jobs
    today = datetime.now(timezone.utc).date()
    date_range = [(today - timedelta(days=i)).isoformat() for i in range(DAYS_WINDOW - 1, -1, -1)]
    jobs = sorted(watchdog.keys())
    heatmap_data = []
    for j_idx, job in enumerate(jobs):
        for d_idx, d in enumerate(date_range):
            counts = watchdog.get(job, {}).get(d, {"ok": 0, "fail": 0})
            status = 2 if counts["fail"] > 0 else (1 if counts["ok"] > 0 else 0)
            heatmap_data.append({"x": d_idx, "y": j_idx, "s": status, "ok": counts["ok"], "fail": counts["fail"]})

    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clarvis Health Dashboard</title>
<style>
  :root {{ --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #e6edf3;
           --muted: #8b949e; --green: #3fb950; --yellow: #d29922; --red: #f85149;
           --blue: #58a6ff; --purple: #bc8cff; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; padding: 20px; }}
  h1 {{ font-size: 1.4em; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 0.85em; margin-bottom: 20px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }}
  .card .label {{ color: var(--muted); font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ font-size: 1.8em; font-weight: 700; margin-top: 4px; }}
  .good {{ color: var(--green); }}
  .warn {{ color: var(--yellow); }}
  .bad {{ color: var(--red); }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
  @media (max-width: 800px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  .chart-box {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
  .chart-box h3 {{ font-size: 0.9em; color: var(--muted); margin-bottom: 12px; }}
  canvas {{ width: 100% !important; height: 200px !important; }}
  .heatmap-section {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
  .heatmap-section h3 {{ font-size: 0.9em; color: var(--muted); margin-bottom: 12px; }}
  .heatmap {{ display: grid; gap: 2px; }}
  .heatmap-row {{ display: flex; align-items: center; gap: 2px; }}
  .heatmap-label {{ width: 120px; font-size: 0.7em; color: var(--muted); text-align: right; padding-right: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .heatmap-cell {{ width: 28px; height: 20px; border-radius: 3px; cursor: default; }}
  .heatmap-cell.ok {{ background: var(--green); opacity: 0.8; }}
  .heatmap-cell.fail {{ background: var(--red); opacity: 0.9; }}
  .heatmap-cell.none {{ background: var(--border); opacity: 0.4; }}
  .heatmap-dates {{ display: flex; gap: 2px; margin-left: 120px; margin-top: 4px; }}
  .heatmap-dates span {{ width: 28px; font-size: 0.6em; color: var(--muted); text-align: center; }}
  .legend {{ display: flex; gap: 16px; margin-top: 8px; font-size: 0.7em; color: var(--muted); }}
  .legend span {{ display: flex; align-items: center; gap: 4px; }}
  .legend .dot {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
</style>
</head>
<body>
<h1>Clarvis Health Dashboard</h1>
<p class="subtitle">Generated: {gen_time} &mdash; Last {DAYS_WINDOW} days</p>

<div class="cards">
  <div class="card">
    <div class="label">PI</div>
    <div class="value {'good' if latest_pi >= 0.9 else 'warn' if latest_pi >= 0.7 else 'bad'}">{latest_pi:.3f}</div>
  </div>
  <div class="card">
    <div class="label">Context Relevance</div>
    <div class="value {'good' if latest_cr >= 0.75 else 'warn' if latest_cr >= 0.5 else 'bad'}">{latest_cr:.3f}</div>
  </div>
  <div class="card">
    <div class="label">CLR</div>
    <div class="value {'good' if latest_clr >= 0.8 else 'warn' if latest_clr >= 0.6 else 'bad'}">{latest_clr:.3f}</div>
  </div>
  <div class="card">
    <div class="label">Phi</div>
    <div class="value {'good' if latest_phi >= 0.7 else 'warn' if latest_phi >= 0.5 else 'bad'}">{latest_phi:.3f}</div>
  </div>
  <div class="card">
    <div class="label">Memories</div>
    <div class="value" style="color:var(--blue)">{latest_memories:,}</div>
  </div>
  <div class="card">
    <div class="label">Query Avg</div>
    <div class="value {'good' if latest_query_ms < 500 else 'warn' if latest_query_ms < 1000 else 'bad'}">{latest_query_ms:.0f}ms</div>
  </div>
</div>

<div class="charts">
  <div class="chart-box">
    <h3>Performance Index (PI)</h3>
    <canvas id="piChart"></canvas>
  </div>
  <div class="chart-box">
    <h3>Context Relevance</h3>
    <canvas id="crChart"></canvas>
  </div>
  <div class="chart-box">
    <h3>CLR Composite</h3>
    <canvas id="clrChart"></canvas>
  </div>
  <div class="chart-box">
    <h3>Phi (Consciousness Proxy)</h3>
    <canvas id="phiChart"></canvas>
  </div>
</div>

<div class="heatmap-section">
  <h3>Cron Job Status &mdash; Last {DAYS_WINDOW} Days</h3>
  <div class="heatmap" id="heatmap"></div>
  <div class="heatmap-dates" id="heatmap-dates"></div>
  <div class="legend">
    <span><span class="dot" style="background:var(--green)"></span> All OK</span>
    <span><span class="dot" style="background:var(--red)"></span> Has Failures</span>
    <span><span class="dot" style="background:var(--border)"></span> No Data</span>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script>
const piData = {json.dumps(pi_series)};
const crData = {json.dumps(cr_series)};
const clrData = {json.dumps(clr_series)};
const phiData = {json.dumps(phi_series)};
const heatmapData = {json.dumps(heatmap_data)};
const jobs = {json.dumps(jobs)};
const dates = {json.dumps(date_range)};

function makeChart(id, data, color, target) {{
  const ctx = document.getElementById(id).getContext('2d');
  const datasets = [{{
    data: data.map(d => ({{x: d.t, y: d.v}})),
    borderColor: color,
    backgroundColor: color + '22',
    fill: true,
    tension: 0.3,
    pointRadius: 3,
    borderWidth: 2
  }}];
  if (target !== undefined) {{
    datasets.push({{
      data: data.map(d => ({{x: d.t, y: target}})),
      borderColor: '#d29922',
      borderDash: [5, 5],
      borderWidth: 1,
      pointRadius: 0,
      fill: false,
      label: 'target'
    }});
  }}
  new Chart(ctx, {{
    type: 'line',
    data: {{ datasets }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#8b949e', maxTicksLimit: 7 }}, grid: {{ color: '#30363d' }} }},
        y: {{ min: 0, max: 1.05, ticks: {{ color: '#8b949e' }}, grid: {{ color: '#30363d' }} }}
      }}
    }}
  }});
}}

makeChart('piChart', piData, '#3fb950', 0.9);
makeChart('crChart', crData, '#58a6ff', 0.75);
makeChart('clrChart', clrData, '#bc8cff', 0.8);
makeChart('phiChart', phiData, '#d29922');

// Heatmap
const heatmapEl = document.getElementById('heatmap');
jobs.forEach((job, jIdx) => {{
  const row = document.createElement('div');
  row.className = 'heatmap-row';
  const label = document.createElement('div');
  label.className = 'heatmap-label';
  label.textContent = job;
  row.appendChild(label);
  dates.forEach((d, dIdx) => {{
    const cell = document.createElement('div');
    cell.className = 'heatmap-cell';
    const entry = heatmapData.find(h => h.x === dIdx && h.y === jIdx);
    if (entry && entry.s === 2) {{
      cell.classList.add('fail');
      cell.title = `${{job}} ${{d}}: ${{entry.ok}} ok, ${{entry.fail}} fail`;
    }} else if (entry && entry.s === 1) {{
      cell.classList.add('ok');
      cell.title = `${{job}} ${{d}}: ${{entry.ok}} ok`;
    }} else {{
      cell.classList.add('none');
      cell.title = `${{job}} ${{d}}: no data`;
    }}
    row.appendChild(cell);
  }});
  heatmapEl.appendChild(row);
}});

const datesEl = document.getElementById('heatmap-dates');
dates.forEach(d => {{
  const s = document.createElement('span');
  s.textContent = d.slice(5);
  datesEl.appendChild(s);
}});
</script>
</body>
</html>"""


def main():
    perf = load_jsonl(PERF_HISTORY, days=30)
    clr = load_jsonl(CLR_HISTORY, days=30)
    watchdog = parse_watchdog_logs(WATCHDOG_LOGS, days=DAYS_WINDOW)

    html = generate_html(perf, clr, watchdog)
    OUTPUT.write_text(html)
    print(f"Dashboard written to {OUTPUT} ({len(html)} bytes)")
    print(f"  PI entries: {len(perf)}, CLR entries: {len(clr)}, Cron jobs: {len(watchdog)}")


if __name__ == "__main__":
    main()
