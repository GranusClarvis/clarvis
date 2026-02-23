#!/usr/bin/env python3
"""
OpenRouter Cost API Client — Real usage data from OpenRouter.

Provides:
  - fetch_usage()      → Daily/weekly/monthly spend + remaining credits
  - fetch_generation()  → Detailed stats for a single generation
  - format_usage()     → Human-readable formatted output

Uses urllib.request (zero dependencies). Reads API key from OpenClaw auth.json.

Usage:
    python3 cost_api.py                  # Human-readable usage summary
    python3 cost_api.py --json           # JSON output for programmatic use
    python3 cost_api.py generation <id>  # Lookup a specific generation
"""

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Dict, Optional

AUTH_FILE = "/home/agent/.openclaw/agents/main/agent/auth.json"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

_cached_key: Optional[str] = None


def get_api_key() -> str:
    """Read OpenRouter API key from OpenClaw auth.json. Caches after first read."""
    global _cached_key
    if _cached_key:
        return _cached_key

    if not os.path.exists(AUTH_FILE):
        raise FileNotFoundError(f"Auth file not found: {AUTH_FILE}")

    with open(AUTH_FILE) as f:
        auth = json.load(f)

    key = auth.get("openrouter", {}).get("key")
    if not key:
        raise ValueError("No OpenRouter API key found in auth.json")

    _cached_key = key
    return key


def _api_get(endpoint: str, timeout: int = 10) -> Dict:
    """Make an authenticated GET request to OpenRouter API."""
    url = f"{OPENROUTER_BASE}/{endpoint}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"OpenRouter API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e


def fetch_usage() -> Dict:
    """Fetch real usage data from OpenRouter.

    Returns:
        {
            "daily": float,       # USD spent today (UTC)
            "weekly": float,      # USD spent this week (UTC Monday start)
            "monthly": float,     # USD spent this month (UTC)
            "total": float,       # All-time usage
            "limit": float|None,  # Credit cap (None = unlimited)
            "remaining": float|None,  # Credits remaining
            "is_free_tier": bool,
        }
    """
    resp = _api_get("key")
    data = resp.get("data", {})

    limit = data.get("limit")
    remaining = data.get("limit_remaining")

    return {
        "daily": round(data.get("usage_daily", 0), 4),
        "weekly": round(data.get("usage_weekly", 0), 4),
        "monthly": round(data.get("usage_monthly", 0), 4),
        "total": round(data.get("usage", 0), 4),
        "limit": round(limit, 2) if limit is not None else None,
        "remaining": round(remaining, 4) if remaining is not None else None,
        "is_free_tier": data.get("is_free_tier", False),
    }


def fetch_generation(generation_id: str) -> Dict:
    """Fetch detailed stats for a specific generation.

    Returns dict with: total_cost, model, provider_name, tokens_prompt,
    tokens_completion, generation_time, latency, finish_reason, etc.
    """
    resp = _api_get(f"generation?id={generation_id}")
    data = resp.get("data", resp)
    return {
        "id": data.get("id"),
        "total_cost": data.get("total_cost"),
        "model": data.get("model"),
        "provider": data.get("provider_name"),
        "tokens_prompt": data.get("tokens_prompt"),
        "tokens_completion": data.get("tokens_completion"),
        "generation_time": data.get("generation_time"),
        "latency": data.get("latency"),
        "finish_reason": data.get("finish_reason"),
        "created_at": data.get("created_at"),
    }


def format_usage(usage: Dict) -> str:
    """Format usage dict into a human-readable report."""
    lines = []
    lines.append("=== OpenRouter Usage (Real API Data) ===")
    lines.append(f"  Today:   ${usage['daily']:.4f}")
    lines.append(f"  Week:    ${usage['weekly']:.4f}")
    lines.append(f"  Month:   ${usage['monthly']:.4f}")
    lines.append(f"  Total:   ${usage['total']:.4f}")

    if usage["limit"] is not None:
        pct = (usage["total"] / usage["limit"] * 100) if usage["limit"] > 0 else 0
        lines.append(f"  Limit:   ${usage['limit']:.2f}")
        lines.append(f"  Remain:  ${usage['remaining']:.4f} ({100 - pct:.1f}% left)")

        # Alert levels
        if usage["remaining"] is not None:
            if usage["remaining"] < 10:
                lines.append("  *** CRITICAL: Less than $10 remaining! ***")
            elif usage["remaining"] < 20:
                lines.append("  ** WARNING: Less than $20 remaining **")

    return "\n".join(lines)


def format_telegram(usage: Dict) -> str:
    """Format usage for Telegram message (compact, with model breakdown placeholder)."""
    lines = []
    lines.append("OpenRouter Usage")
    lines.append(f"Today: ${usage['daily']:.2f} | Week: ${usage['weekly']:.2f} | Month: ${usage['monthly']:.2f}")

    if usage["limit"] is not None and usage["remaining"] is not None:
        pct_left = usage["remaining"] / usage["limit"] * 100 if usage["limit"] > 0 else 0
        lines.append(f"Remaining: ${usage['remaining']:.2f} / ${usage['limit']:.0f} ({pct_left:.0f}%)")

        if usage["remaining"] < 10:
            lines.append("CRITICAL: Less than $10 remaining!")
        elif usage["remaining"] < 20:
            lines.append("WARNING: Less than $20 remaining")

    return "\n".join(lines)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "generation":
        if len(sys.argv) < 3:
            print("Usage: cost_api.py generation <generation_id>")
            sys.exit(1)
        gen = fetch_generation(sys.argv[2])
        if "--json" in sys.argv:
            print(json.dumps(gen, indent=2))
        else:
            print(f"=== Generation {gen.get('id', '?')} ===")
            print(f"  Model:    {gen.get('model', '?')}")
            print(f"  Provider: {gen.get('provider', '?')}")
            print(f"  Cost:     ${gen.get('total_cost', 0):.6f}")
            print(f"  Tokens:   {gen.get('tokens_prompt', 0)} in / {gen.get('tokens_completion', 0)} out")
            print(f"  Latency:  {gen.get('latency', '?')}ms")
            print(f"  Time:     {gen.get('generation_time', '?')}ms")
        return

    usage = fetch_usage()

    if "--json" in sys.argv:
        print(json.dumps(usage, indent=2))
    elif "--telegram" in sys.argv:
        print(format_telegram(usage))
    else:
        print(format_usage(usage))


if __name__ == "__main__":
    main()
