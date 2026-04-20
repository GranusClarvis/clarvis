#!/usr/bin/env python3
"""Unified cost dashboard — merges Anthropic (CLI token capture) and OpenRouter spend.

Usage:
    python3 cost_dashboard.py summary          # One-screen unified overview
    python3 cost_dashboard.py providers        # Side-by-side provider breakdown
    python3 cost_dashboard.py trend [days]     # Daily trend by provider (default 7)
    python3 cost_dashboard.py quality          # Data quality report (estimated vs real)
    python3 cost_dashboard.py telegram         # Compact Telegram-ready output
    python3 cost_dashboard.py json             # Full dashboard as JSON
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from clarvis.orch.cost_tracker import CostTracker, CostEntry, get_pricing
from clarvis.orch.cost_api import fetch_usage

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE",
    os.path.join(os.path.dirname(__file__), "..", ".."),
)
COST_LOG = os.path.join(WORKSPACE, "data", "costs.jsonl")

ANTHROPIC_MODELS = {
    "claude-code", "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5",
    "anthropic/claude-opus-4-6", "anthropic/claude-sonnet-4-6",
    "anthropic/claude-haiku-4-5",
}


def _is_anthropic(model: str) -> bool:
    return model in ANTHROPIC_MODELS or model.startswith("claude")


def _load_entries(days: int = 0) -> list[CostEntry]:
    tracker = CostTracker(COST_LOG)
    since = None
    if days > 0:
        since = datetime.now(timezone.utc) - timedelta(days=days)
    return tracker._read_entries(since)


def _classify(entries: list[CostEntry]) -> dict:
    anthropic = []
    openrouter = []
    for e in entries:
        if _is_anthropic(e.model):
            anthropic.append(e)
        else:
            openrouter.append(e)
    return {"anthropic": anthropic, "openrouter": openrouter}


def _provider_stats(entries: list[CostEntry]) -> dict:
    total_cost = sum(e.cost_usd for e in entries)
    real = [e for e in entries if not e.estimated]
    estimated = [e for e in entries if e.estimated]
    by_model: dict[str, dict] = {}
    for e in entries:
        if e.model not in by_model:
            by_model[e.model] = {"cost": 0.0, "calls": 0, "in_tok": 0, "out_tok": 0}
        by_model[e.model]["cost"] += e.cost_usd
        by_model[e.model]["calls"] += 1
        by_model[e.model]["in_tok"] += e.input_tokens
        by_model[e.model]["out_tok"] += e.output_tokens
    return {
        "total_cost": round(total_cost, 4),
        "calls": len(entries),
        "real_count": len(real),
        "estimated_count": len(estimated),
        "real_pct": round(len(real) / max(len(entries), 1) * 100, 1),
        "real_cost": round(sum(e.cost_usd for e in real), 4),
        "estimated_cost": round(sum(e.cost_usd for e in estimated), 4),
        "by_model": {
            k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()}
            for k, v in sorted(by_model.items(), key=lambda x: -x[1]["cost"])
        },
    }


def _try_openrouter_live() -> dict | None:
    try:
        return fetch_usage()
    except Exception:
        return None


def _daily_trend_by_provider(entries: list[CostEntry], days: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    buckets: dict[str, dict] = {}
    for e in entries:
        day = e.timestamp[:10]
        if day not in buckets:
            buckets[day] = {"anthropic": 0.0, "openrouter": 0.0, "total": 0.0}
        provider = "anthropic" if _is_anthropic(e.model) else "openrouter"
        buckets[day][provider] += e.cost_usd
        buckets[day]["total"] += e.cost_usd

    result = []
    for d in range(days):
        day_str = (now - timedelta(days=days - 1 - d)).strftime("%Y-%m-%d")
        b = buckets.get(day_str, {"anthropic": 0.0, "openrouter": 0.0, "total": 0.0})
        result.append({
            "date": day_str,
            "anthropic": round(b["anthropic"], 4),
            "openrouter": round(b["openrouter"], 4),
            "total": round(b["total"], 4),
        })
    return result


def build_dashboard(days: int = 30) -> dict:
    entries = _load_entries(days)
    classified = _classify(entries)
    live_or = _try_openrouter_live()

    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "period_days": days,
        "unified": {
            "total_cost": round(sum(e.cost_usd for e in entries), 4),
            "total_calls": len(entries),
            "real_entries": sum(1 for e in entries if not e.estimated),
            "estimated_entries": sum(1 for e in entries if e.estimated),
        },
        "anthropic": _provider_stats(classified["anthropic"]),
        "openrouter": _provider_stats(classified["openrouter"]),
        "openrouter_live": live_or,
        "trend_7d": _daily_trend_by_provider(entries, min(days, 7)),
    }


def cmd_summary():
    dash = build_dashboard(30)
    u = dash["unified"]
    a = dash["anthropic"]
    o = dash["openrouter"]
    live = dash["openrouter_live"]

    print("=" * 56)
    print("  UNIFIED COST DASHBOARD — Clarvis (30-day window)")
    print("=" * 56)
    print()
    print(f"  Total spend (logged):  ${u['total_cost']:.2f}")
    print(f"  Total API calls:       {u['total_calls']}")
    print(f"  Real entries:          {u['real_entries']} / {u['total_calls']}"
          f" ({u['real_entries']/max(u['total_calls'],1)*100:.0f}%)")
    print()

    print("  --- Anthropic (Claude Code CLI) ---")
    print(f"  Spend:   ${a['total_cost']:.2f}  ({a['calls']} calls)")
    print(f"  Real:    ${a['real_cost']:.2f}  ({a['real_count']} entries, "
          f"{a['real_pct']:.0f}% verified)")
    if a["by_model"]:
        top = list(a["by_model"].items())[:3]
        for m, s in top:
            print(f"    {m}: ${s['cost']:.2f} ({s['calls']} calls)")
    print()

    print("  --- OpenRouter (M2.5 / GLM-5 / Kimi) ---")
    print(f"  Spend:   ${o['total_cost']:.2f}  ({o['calls']} calls)")
    print(f"  Real:    ${o['real_cost']:.2f}  ({o['real_count']} entries, "
          f"{o['real_pct']:.0f}% verified)")
    if o["by_model"]:
        top = list(o["by_model"].items())[:3]
        for m, s in top:
            print(f"    {m}: ${s['cost']:.2f} ({s['calls']} calls)")

    if live:
        print()
        print("  --- OpenRouter Live API ---")
        print(f"  Today:  ${live['daily']:.4f}  |  Week: ${live['weekly']:.4f}"
              f"  |  Month: ${live['monthly']:.4f}")
        if live.get("remaining") is not None:
            print(f"  Remaining: ${live['remaining']:.2f} / ${live['limit']:.0f}")
    else:
        print()
        print("  --- OpenRouter Live API ---")
        print("  [UNAVAILABLE] API key returns 401 — see [PHASE14_OPENROUTER_API_KEY_FIX]")

    print()
    trend = dash["trend_7d"]
    print("  --- 7-Day Trend ---")
    max_cost = max((t["total"] for t in trend), default=1) or 1
    for t in trend:
        bar_len = int(t["total"] / max_cost * 30) if max_cost > 0 else 0
        bar = "█" * bar_len
        print(f"  {t['date']}  ${t['total']:6.2f}  {bar}")
    print()


def cmd_providers():
    dash = build_dashboard(30)
    a = dash["anthropic"]
    o = dash["openrouter"]

    print("Provider Breakdown (30-day)")
    print()
    for label, stats in [("Anthropic", a), ("OpenRouter", o)]:
        print(f"  {label}:")
        print(f"    Cost: ${stats['total_cost']:.2f} | Calls: {stats['calls']}"
              f" | Real: {stats['real_pct']:.0f}%")
        for m, s in stats["by_model"].items():
            print(f"      {m}: ${s['cost']:.2f} ({s['calls']}x, "
                  f"{s['in_tok']}in/{s['out_tok']}out)")
        print()


def cmd_trend(days: int = 7):
    entries = _load_entries(days)
    trend = _daily_trend_by_provider(entries, days)

    print(f"Daily Cost Trend ({days}-day)")
    print(f"{'Date':<12} {'Anthropic':>10} {'OpenRouter':>10} {'Total':>10}")
    print("-" * 44)
    for t in trend:
        print(f"{t['date']:<12} ${t['anthropic']:>8.2f} ${t['openrouter']:>8.2f}"
              f" ${t['total']:>8.2f}")

    totals = {
        "anthropic": sum(t["anthropic"] for t in trend),
        "openrouter": sum(t["openrouter"] for t in trend),
    }
    total = totals["anthropic"] + totals["openrouter"]
    print("-" * 44)
    print(f"{'Total':<12} ${totals['anthropic']:>8.2f} ${totals['openrouter']:>8.2f}"
          f" ${total:>8.2f}")


def cmd_quality():
    entries = _load_entries(0)
    classified = _classify(entries)

    print("Data Quality Report (all time)")
    print()
    for label, group in [("Anthropic", classified["anthropic"]),
                         ("OpenRouter", classified["openrouter"])]:
        real = [e for e in group if not e.estimated]
        est = [e for e in group if e.estimated]
        total = len(group)
        print(f"  {label}:")
        print(f"    Total entries:   {total}")
        print(f"    Real (verified): {len(real)} ({len(real)/max(total,1)*100:.0f}%)")
        print(f"    Estimated:       {len(est)} ({len(est)/max(total,1)*100:.0f}%)")
        if real:
            real_cost = sum(e.cost_usd for e in real)
            est_cost = sum(e.cost_usd for e in est)
            print(f"    Real spend:      ${real_cost:.2f}")
            print(f"    Estimated spend: ${est_cost:.2f}")
        print()

    live = _try_openrouter_live()
    if live:
        print("  OpenRouter API: CONNECTED")
        print(f"    Monthly actual: ${live['monthly']:.4f}")
    else:
        print("  OpenRouter API: DISCONNECTED (401)")
        print("    Fix: [PHASE14_OPENROUTER_API_KEY_FIX]")


def cmd_telegram():
    dash = build_dashboard(30)
    u = dash["unified"]
    a = dash["anthropic"]
    o = dash["openrouter"]
    live = dash["openrouter_live"]

    lines = [
        "Cost Dashboard (30d)",
        f"Total: ${u['total_cost']:.2f} ({u['total_calls']} calls, "
        f"{u['real_entries']} real)",
        f"Anthropic: ${a['total_cost']:.2f} | OpenRouter: ${o['total_cost']:.2f}",
    ]
    if live:
        lines.append(
            f"OR Live — Today: ${live['daily']:.2f} | Month: ${live['monthly']:.2f}"
        )
        if live.get("remaining") is not None:
            lines.append(f"Remaining: ${live['remaining']:.2f} / ${live['limit']:.0f}")
    else:
        lines.append("OR API: unavailable (401)")
    print("\n".join(lines))


def cmd_json():
    dash = build_dashboard(30)
    print(json.dumps(dash, indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "summary":
        cmd_summary()
    elif cmd == "providers":
        cmd_providers()
    elif cmd == "trend":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        cmd_trend(days)
    elif cmd == "quality":
        cmd_quality()
    elif cmd == "telegram":
        cmd_telegram()
    elif cmd == "json":
        cmd_json()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
