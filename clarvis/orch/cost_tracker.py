"""
ClarvisCost core — token counting, pricing, and cost tracking.

Migrated from packages/clarvis-cost/clarvis_cost/core.py into the spine.
The canonical import is now: from clarvis.orch.cost_tracker import CostTracker

Provides:
  - Model pricing table (Claude, Gemini, OpenRouter models)
  - Token estimation (pre-send)
  - API call logging to JSONL
  - Budget rollups (daily/weekly/monthly)
  - Optimization analysis
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

# === PRICING TABLE ===
# Prices in USD per 1M tokens (input/output)
# Updated 2026-02-23 — adjust as pricing changes

MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Claude models (Anthropic / OpenRouter)
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.0},
    # Aliases used via OpenRouter
    "anthropic/claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "anthropic/claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "anthropic/claude-haiku-4-5": {"input": 0.80, "output": 4.0},
    # Gemini models
    "gemini-2.0-flash": {"input": 0.0, "output": 0.0},  # Free tier
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-3-flash": {"input": 0.80, "output": 0.80},   # Web search model
    # OpenClaw / OpenRouter models (per-1M-token pricing)
    "minimax-m2.5": {"input": 0.42, "output": 0.42},     # Simple/coding tasks
    "glm-5": {"input": 1.32, "output": 1.32},             # Complex reasoning
    "kimi-k2.5": {"input": 0.90, "output": 0.90},         # Vision tasks
    # OpenRouter-prefixed aliases (as used in openclaw.json and router)
    "openrouter/minimax/minimax-m2.5": {"input": 0.42, "output": 0.42},
    "openrouter/z-ai/glm-5": {"input": 1.32, "output": 1.32},
    "minimax/minimax-m2.5": {"input": 0.42, "output": 0.42},
    "z-ai/glm-5": {"input": 1.32, "output": 1.32},
    "moonshotai/kimi-k2.5": {"input": 0.90, "output": 0.90},
    "google/gemini-3-flash-preview": {"input": 0.80, "output": 0.80},
    # Claude Code CLI — priced as opus (tool-use sessions)
    "claude-code": {"input": 15.0, "output": 75.0},
}

# Fallback for unknown models
DEFAULT_PRICING = {"input": 3.0, "output": 15.0}


def get_pricing(model: str) -> Dict[str, float]:
    """Get per-1M-token pricing for a model. Falls back to DEFAULT_PRICING."""
    return MODEL_PRICING.get(model, DEFAULT_PRICING)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given call."""
    pricing = get_pricing(model)
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return round(cost, 6)


# === TOKEN ESTIMATION ===

# Average chars per token by model family (empirically measured)
CHARS_PER_TOKEN = {
    "claude": 3.5,
    "gemini": 4.0,
    "default": 3.8,
}


def estimate_tokens(text: str, model: str = "default") -> int:
    """Estimate token count from text. More accurate than naive len/4.

    Uses model-family-specific chars-per-token ratios.
    For structured content (JSON, code), applies a density multiplier.
    """
    if not text:
        return 0

    # Detect model family
    family = "default"
    model_lower = model.lower()
    if "claude" in model_lower:
        family = "claude"
    elif "gemini" in model_lower:
        family = "gemini"

    chars_per_tok = CHARS_PER_TOKEN[family]
    base_estimate = len(text) / chars_per_tok

    # Structured content has more tokens per char (brackets, keys, etc.)
    json_density = 1.0
    if text.lstrip().startswith("{") or text.lstrip().startswith("["):
        json_density = 1.15  # JSON is ~15% more token-dense
    elif text.count("\n") > 0:
        code_indicators = sum(1 for kw in ["def ", "class ", "import ", "if ", "for "]
                              if kw in text)
        if code_indicators >= 2:
            json_density = 1.10  # Code is ~10% more token-dense

    return int(base_estimate * json_density)


# === COST LOG ===

@dataclass
class CostEntry:
    """A single API call cost record."""
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    source: str = ""          # Where the call came from (cron_autonomous, cron_evolution, etc.)
    task: str = ""            # Task description (first 150 chars)
    duration_s: float = 0.0   # API call duration
    generation_id: str = ""   # OpenRouter generation ID for detailed lookups
    estimated: bool = True    # False when cost comes from real API data
    audit_trace_id: str = ""  # Phase 0 audit substrate — links spend to a spawn trace

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> CostEntry:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _resolve_audit_trace_id(explicit: str = "") -> str:
    """Return the passed id, or fall back to the ambient audit trace id."""
    if explicit:
        return explicit
    try:
        from clarvis.audit import current_trace_id
        return current_trace_id() or ""
    except Exception:
        return ""


class CostTracker:
    """Append-only JSONL cost logger with rollup queries."""

    def __init__(self, log_path: str):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        source: str = "",
        task: str = "",
        duration_s: float = 0.0,
        audit_trace_id: str = "",
    ) -> CostEntry:
        """Log an API call and return the cost entry.

        ``audit_trace_id`` is optional; when omitted, the Phase 0 audit
        substrate's ambient id (env / process) is used so spend maps to a
        spawn trace automatically.
        """
        cost = estimate_cost(model, input_tokens, output_tokens)
        entry = CostEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            source=source,
            task=task[:150],
            duration_s=round(duration_s, 2),
            audit_trace_id=_resolve_audit_trace_id(audit_trace_id),
        )
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def log_real(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        source: str = "",
        task: str = "",
        duration_s: float = 0.0,
        generation_id: str = "",
        audit_trace_id: str = "",
    ) -> CostEntry:
        """Log an API call with REAL cost from API response (not estimated).

        Use this when you have the actual cost from OpenRouter's usage.cost field.
        """
        entry = CostEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 6),
            source=source,
            task=task[:150],
            duration_s=round(duration_s, 2),
            generation_id=generation_id,
            estimated=False,
            audit_trace_id=_resolve_audit_trace_id(audit_trace_id),
        )
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def _read_entries(self, since: Optional[datetime] = None) -> List[CostEntry]:
        """Read log entries, optionally filtered by time."""
        if not os.path.exists(self.log_path):
            return []

        entries = []
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    entry = CostEntry.from_dict(d)
                    if since:
                        ts = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                        if ts < since:
                            continue
                    entries.append(entry)
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue
        return entries

    def rollup(self, period: str = "day") -> Dict:
        """Aggregate costs for a time period.

        Args:
            period: "day", "week", "month", or "all"

        Returns:
            {
                "period": str,
                "total_cost": float,
                "total_input_tokens": int,
                "total_output_tokens": int,
                "call_count": int,
                "by_model": {model: {cost, input, output, count}},
                "by_source": {source: {cost, count}},
            }
        """
        now = datetime.now(timezone.utc)
        if period == "day":
            since = now - timedelta(days=1)
        elif period == "week":
            since = now - timedelta(weeks=1)
        elif period == "month":
            since = now - timedelta(days=30)
        else:
            since = None

        entries = self._read_entries(since)

        total_cost = 0.0
        total_in = 0
        total_out = 0
        by_model: Dict[str, Dict] = {}
        by_source: Dict[str, Dict] = {}

        for e in entries:
            total_cost += e.cost_usd
            total_in += e.input_tokens
            total_out += e.output_tokens

            # By model
            if e.model not in by_model:
                by_model[e.model] = {"cost": 0.0, "input": 0, "output": 0, "count": 0}
            by_model[e.model]["cost"] += e.cost_usd
            by_model[e.model]["input"] += e.input_tokens
            by_model[e.model]["output"] += e.output_tokens
            by_model[e.model]["count"] += 1

            # By source
            src = e.source or "unknown"
            if src not in by_source:
                by_source[src] = {"cost": 0.0, "count": 0}
            by_source[src]["cost"] += e.cost_usd
            by_source[src]["count"] += 1

        return {
            "period": period,
            "since": since.isoformat() if since else "all",
            "total_cost": round(total_cost, 4),
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "call_count": len(entries),
            "by_model": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_model.items()},
            "by_source": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_source.items()},
        }

    def daily_trend(self, days: int = 7) -> List[Dict]:
        """Get cost-per-day for the last N days."""
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)
        entries = self._read_entries(since)

        buckets: Dict[str, Dict] = {}
        for e in entries:
            day = e.timestamp[:10]  # YYYY-MM-DD
            if day not in buckets:
                buckets[day] = {"cost": 0.0, "tokens": 0, "calls": 0}
            buckets[day]["cost"] += e.cost_usd
            buckets[day]["tokens"] += e.input_tokens + e.output_tokens
            buckets[day]["calls"] += 1

        result = []
        for d in range(days):
            day_str = (now - timedelta(days=days - 1 - d)).strftime("%Y-%m-%d")
            b = buckets.get(day_str, {"cost": 0.0, "tokens": 0, "calls": 0})
            result.append({"date": day_str, **{k: round(v, 4) if isinstance(v, float) else v for k, v in b.items()}})
        return result

    def task_costs(self, days: int = 7, top_n: int = 20) -> Dict:
        """Per-task cost breakdown for the last N days."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        entries = self._read_entries(since)

        by_task: Dict[str, Dict] = {}
        total = 0.0
        for e in entries:
            key = e.task[:80] if e.task else "(no task)"
            total += e.cost_usd
            if key not in by_task:
                by_task[key] = {"cost": 0.0, "calls": 0, "models": set(), "duration": 0.0}
            by_task[key]["cost"] += e.cost_usd
            by_task[key]["calls"] += 1
            by_task[key]["models"].add(e.model)
            by_task[key]["duration"] += e.duration_s

        tasks = []
        for task_name, data in sorted(by_task.items(), key=lambda x: -x[1]["cost"]):
            tasks.append({
                "task": task_name,
                "total_cost": round(data["cost"], 4),
                "calls": data["calls"],
                "avg_cost": round(data["cost"] / data["calls"], 4) if data["calls"] else 0,
                "models": sorted(data["models"]),
                "total_duration_s": round(data["duration"], 1),
            })

        return {
            "period_days": days,
            "tasks": tasks[:top_n],
            "total_cost": round(total, 4),
            "unique_tasks": len(by_task),
        }

    def routing_effectiveness(self, days: int = 7, router_log: str = "") -> Dict:
        """Analyze routing effectiveness from cost log + optional router decisions."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        entries = self._read_entries(since)

        CHEAP_MODELS = {
            "minimax-m2.5", "minimax/minimax-m2.5", "openrouter/minimax/minimax-m2.5",
            "gemini-2.0-flash", "gemini-3-flash", "google/gemini-3-flash-preview",
            "glm-5", "z-ai/glm-5", "openrouter/z-ai/glm-5",
            "moonshotai/kimi-k2.5", "kimi-k2.5",
        }

        cheap = {"count": 0, "cost": 0.0}
        expensive = {"count": 0, "cost": 0.0}
        routed_savings = 0.0

        for e in entries:
            if e.model in CHEAP_MODELS:
                cheap["count"] += 1
                cheap["cost"] += e.cost_usd
                claude_cost = estimate_cost("claude-code", e.input_tokens, e.output_tokens)
                routed_savings += claude_cost - e.cost_usd
            else:
                expensive["count"] += 1
                expensive["cost"] += e.cost_usd

        total = cheap["count"] + expensive["count"]
        return {
            "period_days": days,
            "total_calls": total,
            "by_tier": {
                "cheap": {
                    "count": cheap["count"],
                    "cost": round(cheap["cost"], 4),
                    "pct": round(cheap["count"] / total * 100, 1) if total else 0,
                },
                "expensive": {
                    "count": expensive["count"],
                    "cost": round(expensive["cost"], 4),
                    "pct": round(expensive["count"] / total * 100, 1) if total else 0,
                },
            },
            "estimated_savings": round(routed_savings, 4),
            "routing_rate": round(cheap["count"] / total * 100, 1) if total else 0,
        }

    def budget_check(self, daily_budget: float = 5.0) -> Dict:
        """Check if spending is within budget."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        entries = self._read_entries(today_start)
        today_cost = sum(e.cost_usd for e in entries)

        remaining = daily_budget - today_cost
        pct = (today_cost / daily_budget * 100) if daily_budget > 0 else 0

        if pct >= 100:
            alert = "exceeded"
        elif pct >= 75:
            alert = "warning"
        else:
            alert = "ok"

        return {
            "today_cost": round(today_cost, 4),
            "daily_budget": daily_budget,
            "remaining": round(remaining, 4),
            "pct_used": round(pct, 1),
            "alert": alert,
        }


# === OPTIMIZATION ANALYSIS ===

def analyze_savings(tracker: CostTracker, router_log_path: str = "") -> Dict:
    """Analyze cost optimization opportunities."""
    week = tracker.rollup("week")
    suggestions = []
    stats = {
        "weekly_cost": week["total_cost"],
        "weekly_calls": week["call_count"],
        "weekly_tokens": week["total_input_tokens"] + week["total_output_tokens"],
    }

    for model, data in week.get("by_model", {}).items():
        pricing = get_pricing(model)
        if pricing["input"] >= 10.0 and data["count"] > 5:
            suggestions.append(
                f"High-cost model '{model}' used {data['count']}x this week "
                f"(${data['cost']:.2f}). Consider routing simpler tasks to cheaper models."
            )

    for source, data in week.get("by_source", {}).items():
        if data["cost"] > week["total_cost"] * 0.5 and data["count"] > 3:
            suggestions.append(
                f"Source '{source}' accounts for {data['cost']/max(week['total_cost'],0.01)*100:.0f}% "
                f"of costs. Optimize prompts or add caching."
            )

    if router_log_path and os.path.exists(router_log_path):
        total = fallbacks = 0
        with open(router_log_path) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    total += 1
                    if entry.get("executor") == "claude" and entry.get("tier") in ("simple", "medium"):
                        fallbacks += 1
                except (json.JSONDecodeError, KeyError):
                    continue
        if total > 0:
            fallback_rate = fallbacks / total * 100
            stats["router_fallback_rate"] = round(fallback_rate, 1)
            if fallback_rate > 20:
                suggestions.append(
                    f"Router fallback rate is {fallback_rate:.0f}% — "
                    f"{fallbacks}/{total} simple/medium tasks went to Claude. "
                    f"Check Gemini API key and reliability."
                )

    if week["total_input_tokens"] > 0:
        ratio = week["total_output_tokens"] / week["total_input_tokens"]
        stats["output_input_ratio"] = round(ratio, 2)
        if ratio > 3.0:
            suggestions.append(
                f"Output/input ratio is {ratio:.1f}x — generating much more than receiving. "
                f"Consider constraining max_tokens or using structured outputs."
            )

    stats["suggestions"] = suggestions
    return stats


def import_router_decisions(router_log_path: str, tracker: CostTracker) -> int:
    """Import historical router decisions into the cost tracker."""
    if not os.path.exists(router_log_path):
        return 0

    existing_ts = set()
    if os.path.exists(tracker.log_path):
        with open(tracker.log_path) as f:
            for line in f:
                try:
                    d = json.loads(line.strip())
                    existing_ts.add(d.get("timestamp", ""))
                except (json.JSONDecodeError, KeyError):
                    continue

    imported = 0
    with open(router_log_path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                ts = entry.get("timestamp", "")
                if ts in existing_ts:
                    continue

                model = entry.get("executor", "unknown")
                if model == "gemini":
                    model = "gemini-2.0-flash"
                elif model == "claude":
                    model = "claude-code"

                task = entry.get("task", "")
                est_input = estimate_tokens(task, model) + 500
                est_output = 300

                cost = estimate_cost(model, est_input, est_output)
                cost_entry = CostEntry(
                    timestamp=ts,
                    model=model,
                    input_tokens=est_input,
                    output_tokens=est_output,
                    cost_usd=cost,
                    source="task_router",
                    task=task[:150],
                )
                with open(tracker.log_path, "a") as out:
                    out.write(json.dumps(cost_entry.to_dict()) + "\n")
                imported += 1
            except (json.JSONDecodeError, KeyError):
                continue

    return imported
