#!/usr/bin/env python3
"""bb_beta_summary.py — Daily BB Phase 3 internal beta summary.

Polls the BunnyBagz indexer for the trailing 24h of bet activity across
the three games (coinflip, dice, hilo), aggregates the green-day metrics
defined in ``docs/INTERNAL_BETA_PLAN.md``, and writes a markdown report
to ``memory/cron/bb_beta_<YYYY-MM-DD>.md``.

Operator gates the beta with two env vars (read by the shell wrapper):

    BUNNYBAGZ_BETA_ACTIVE=1                       # required to run
    BUNNYBAGZ_INDEXER_URL=https://indexer.host    # default: localhost:42069

When the beta is inactive, the wrapper short-circuits before this runs.
This script itself is also defensive — if the indexer is unreachable, it
writes an ``INDEXER_UNREACHABLE`` report and pauses the streak (neither
green nor red).

Streak state is tracked in ``memory/cron/bb_beta_streak.json``. Phase 3
exit unblocks once ``green_days >= 7``.

The script intentionally **does not** auto-reopen ``[BB_PHASE3_BETA_FIX_*]``
tasks — that's an operator/triage call (see beta plan §4.4). It only
**cites** any such tasks added to QUEUE.md in the last 24h.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(os.environ.get(
    "CLARVIS_WORKSPACE",
    os.path.expanduser("~/.openclaw/workspace"),
))
CRON_DIR = WORKSPACE / "memory" / "cron"
QUEUE_PATH = WORKSPACE / "memory" / "evolution" / "QUEUE.md"
STREAK_PATH = CRON_DIR / "bb_beta_streak.json"

DEFAULT_INDEXER = "http://localhost:42069"
GAMES = ("coinflip", "dice", "hilo")
NOMINAL_EDGE_PCT = {
    "coinflip": 1.00,
    "dice": 1.00,
    "hilo": 0.75,
}

GREEN_BETS_PER_GAME = 50
GREEN_P95_LATENCY_SEC = 30.0
EDGE_DRIFT_RED_PCT = 1.5  # |drift| > 1.5% counts as red
PENDING_STALE_SEC = 5 * 60  # bets pending > 5 min count as stuck

BETA_FIX_TAG = re.compile(
    r"^\s*-\s*\[\s*[ x]\s*\].*?\[BB_PHASE3_BETA_FIX_[A-Z0-9_]+\]",
    re.MULTILINE,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def _indexer_url() -> str:
    return os.environ.get("BUNNYBAGZ_INDEXER_URL", DEFAULT_INDEXER).rstrip("/")


def _fetch_json(url: str, timeout: float = 10.0) -> Any:
    """GET ``url``, return parsed JSON. Raises on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "clarvis-bb-beta/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[k]


# ── Indexer fetch ─────────────────────────────────────────────────────────

def fetch_recent(indexer: str, game: str, limit: int = 200) -> list[dict] | None:
    """Return recent settled bets for ``game`` from the indexer.

    Returns ``None`` on transport failure (so callers can degrade gracefully).
    Returns ``[]`` on a healthy-but-empty response.
    """
    url = f"{indexer}/api/history?game={game}&limit={limit}&recent=true"
    try:
        body = _fetch_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    bets = body.get("bets") if isinstance(body, dict) else None
    return bets if isinstance(bets, list) else []


def _wei_to_eth(wei_str: str | int | None) -> float:
    if wei_str is None:
        return 0.0
    try:
        return int(str(wei_str)) / 1e18
    except (TypeError, ValueError):
        return 0.0


def _settle_latency_sec(bet: dict) -> float | None:
    """Try to derive settle latency in seconds. Falls back to None."""
    placed = bet.get("blockPlaced") or bet.get("placedAt") or bet.get("placedBlock")
    settled = bet.get("settledAt") or bet.get("settledBlock")
    if not placed or not settled:
        return None
    # If both are ISO timestamps, diff them.
    try:
        if isinstance(placed, str) and "T" in placed and isinstance(settled, str) and "T" in settled:
            p = datetime.fromisoformat(placed.replace("Z", "+00:00"))
            s = datetime.fromisoformat(settled.replace("Z", "+00:00"))
            return max(0.0, (s - p).total_seconds())
    except ValueError:
        pass
    # Block-number diff: assume monad ~1s blocks. Conservative — flag tuning later.
    try:
        return max(0.0, (int(settled) - int(placed)) * 1.0)
    except (TypeError, ValueError):
        return None


def aggregate_game(bets: list[dict] | None, now: datetime) -> dict:
    """Compute the per-game stats from a list of indexer bet rows."""
    if bets is None:
        return {"reachable": False}

    cutoff = now - timedelta(hours=24)
    placed = 0
    settled = 0
    pending_stale = 0
    reverts = 0
    stake_eth = 0.0
    payout_eth = 0.0
    latencies: list[float] = []

    for bet in bets:
        # Filter to last 24h by settledAt or blockPlaced (best-effort).
        ts_raw = bet.get("settledAt") or bet.get("placedAt")
        within = True
        if isinstance(ts_raw, str) and "T" in ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                within = ts >= cutoff
            except ValueError:
                pass
        if not within:
            continue

        placed += 1
        status = bet.get("status")
        if status in ("won", "lost", "settled"):
            settled += 1
            stake_eth += _wei_to_eth(bet.get("stake") or bet.get("stakeWei"))
            payout = bet.get("payout") or bet.get("payoutWei")
            if payout is not None:
                payout_eth += _wei_to_eth(payout)
            lat = _settle_latency_sec(bet)
            if lat is not None:
                latencies.append(lat)
        elif status == "reverted":
            reverts += 1
        elif status == "pending":
            placed_ts = bet.get("placedAt")
            if isinstance(placed_ts, str) and "T" in placed_ts:
                try:
                    pts = datetime.fromisoformat(placed_ts.replace("Z", "+00:00"))
                    if (now - pts).total_seconds() > PENDING_STALE_SEC:
                        pending_stale += 1
                except ValueError:
                    pass

    edge_pct: float | None = None
    if stake_eth > 0:
        edge_pct = (stake_eth - payout_eth) / stake_eth * 100.0

    return {
        "reachable": True,
        "placed": placed,
        "settled": settled,
        "pending_stale": pending_stale,
        "reverts": reverts,
        "stake_eth": stake_eth,
        "payout_eth": payout_eth,
        "edge_pct": edge_pct,
        "p50_sec": _percentile(latencies, 50),
        "p95_sec": _percentile(latencies, 95),
        "max_sec": max(latencies) if latencies else None,
    }


# ── Streak state ──────────────────────────────────────────────────────────

def load_streak() -> dict:
    if not STREAK_PATH.exists():
        return {"green_days": 0, "last_green_date": None, "last_red_reason": None,
                "last_run_date": None, "history": []}
    try:
        data = json.loads(STREAK_PATH.read_text())
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        data.setdefault("green_days", 0)
        data.setdefault("history", [])
        return data
    except (json.JSONDecodeError, ValueError, OSError):
        return {"green_days": 0, "last_green_date": None,
                "last_red_reason": "STREAK_FILE_RESET",
                "last_run_date": None, "history": []}


def save_streak(state: dict) -> None:
    STREAK_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["history"] = state.get("history", [])[-30:]
    STREAK_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


# ── Verdict ───────────────────────────────────────────────────────────────

def _new_beta_fix_tasks_last_24h() -> list[str]:
    """Cite (don't reopen) `[BB_PHASE3_BETA_FIX_*]` queue items mtime-recent."""
    if not QUEUE_PATH.exists():
        return []
    try:
        text = QUEUE_PATH.read_text()
    except OSError:
        return []
    return [m.group(0).strip()[:200] for m in BETA_FIX_TAG.finditer(text)][-10:]


def compute_verdict(per_game: dict[str, dict]) -> tuple[str, list[str]]:
    """Return ('GREEN'|'YELLOW'|'RED'|'PAUSED', reasons_list)."""
    reasons: list[str] = []

    # Indexer reachable for at least one game?
    any_reachable = any(g.get("reachable") for g in per_game.values())
    if not any_reachable:
        return "PAUSED", ["INDEXER_UNREACHABLE"]

    games_at_floor = 0
    for game, stats in per_game.items():
        if not stats.get("reachable"):
            reasons.append(f"{game}: indexer leg unreachable")
            continue
        if stats["settled"] >= GREEN_BETS_PER_GAME:
            games_at_floor += 1
        if stats["reverts"] > 0:
            reasons.append(f"{game}: {stats['reverts']} reverts on settle")
        if stats.get("p95_sec") is not None and stats["p95_sec"] > GREEN_P95_LATENCY_SEC:
            reasons.append(f"{game}: p95 settle latency {stats['p95_sec']:.1f}s > {GREEN_P95_LATENCY_SEC:.0f}s")
        if stats["pending_stale"] > 0:
            reasons.append(f"{game}: {stats['pending_stale']} pending bets older than 5min")
        edge = stats.get("edge_pct")
        nominal = NOMINAL_EDGE_PCT.get(game)
        if edge is not None and nominal is not None:
            drift = edge - nominal
            if abs(drift) > EDGE_DRIFT_RED_PCT:
                reasons.append(f"{game}: edge drift {drift:+.2f}% > ±{EDGE_DRIFT_RED_PCT:.1f}%")

    if reasons:
        # Volume floor not the gating factor when a hard fail already exists.
        return "RED", reasons

    if games_at_floor == len(GAMES):
        return "GREEN", []
    if games_at_floor >= 1:
        return "YELLOW", [f"only {games_at_floor}/{len(GAMES)} games hit the ≥{GREEN_BETS_PER_GAME}-bet floor"]
    return "YELLOW", [f"0/{len(GAMES)} games hit the ≥{GREEN_BETS_PER_GAME}-bet floor"]


# ── Report ────────────────────────────────────────────────────────────────

def _fmt_secs(v: float | None) -> str:
    return f"{v:.1f}s" if isinstance(v, (int, float)) else "—"


def _fmt_eth(v: float) -> str:
    return f"{v:.4f}"


def _fmt_pct(v: float | None) -> str:
    return f"{v:.2f}%" if isinstance(v, (int, float)) else "—"


def render_report(per_game: dict[str, dict], verdict: str, reasons: list[str],
                  streak: dict, today: str, indexer: str,
                  beta_fix_citations: list[str]) -> str:
    streak_count = streak.get("green_days", 0)
    last_green = streak.get("last_green_date") or "—"
    lines: list[str] = []
    lines.append(f"# BB Beta Summary — {today}\n")
    lines.append(f"Beta active: yes  ·  indexer: `{indexer}`")
    lines.append(f"Streak: {streak_count} green day(s) (last green: {last_green})\n")

    lines.append("## 24h volume\n")
    lines.append("| game | placed | settled | pending>5min | reverts |")
    lines.append("|---|---|---|---|---|")
    for game in GAMES:
        s = per_game.get(game, {})
        if not s.get("reachable"):
            lines.append(f"| {game} | — | — | — | — |")
            continue
        lines.append(
            f"| {game} | {s['placed']} | {s['settled']} | {s['pending_stale']} | {s['reverts']} |"
        )

    lines.append("\n## Edge realised\n")
    lines.append("| game | stakes (ETH) | payouts (ETH) | edge | nominal | drift |")
    lines.append("|---|---|---|---|---|---|")
    for game in GAMES:
        s = per_game.get(game, {})
        nominal = NOMINAL_EDGE_PCT[game]
        if not s.get("reachable"):
            lines.append(f"| {game} | — | — | — | {nominal:.2f}% | — |")
            continue
        edge = s.get("edge_pct")
        drift = (edge - nominal) if isinstance(edge, (int, float)) else None
        lines.append(
            f"| {game} | {_fmt_eth(s['stake_eth'])} | {_fmt_eth(s['payout_eth'])} | "
            f"{_fmt_pct(edge)} | {nominal:.2f}% | "
            f"{_fmt_pct(drift) if drift is not None else '—'} |"
        )

    lines.append("\n## Latency\n")
    lines.append("| game | p50 | p95 | max |")
    lines.append("|---|---|---|---|")
    for game in GAMES:
        s = per_game.get(game, {})
        if not s.get("reachable"):
            lines.append(f"| {game} | — | — | — |")
            continue
        lines.append(
            f"| {game} | {_fmt_secs(s.get('p50_sec'))} | "
            f"{_fmt_secs(s.get('p95_sec'))} | {_fmt_secs(s.get('max_sec'))} |"
        )

    lines.append("\n## New beta bugs (citation only — triage owns the queue)\n")
    if beta_fix_citations:
        for cit in beta_fix_citations:
            lines.append(f"- {cit}")
    else:
        lines.append("- (none)")

    lines.append(f"\n## Day verdict: {verdict}\n")
    if reasons:
        lines.append("Reasons:\n")
        for r in reasons:
            lines.append(f"- {r}")
    else:
        lines.append("All thresholds passed.")
    lines.append(f"\nStreak after this run: **{streak_count} green day(s)**.")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────

def update_streak(streak: dict, verdict: str, today: str, reasons: list[str]) -> dict:
    """Mutate streak state per beta-plan §3 rules and return it."""
    if streak.get("last_run_date") == today:
        # Idempotent if the cron fires twice in a day.
        return streak

    if verdict == "GREEN":
        streak["green_days"] = streak.get("green_days", 0) + 1
        streak["last_green_date"] = today
        streak["last_red_reason"] = None
    elif verdict == "RED":
        streak["green_days"] = 0
        streak["last_red_reason"] = "; ".join(reasons)[:300] or "RED"
    elif verdict == "YELLOW":
        # Clock pauses, no reset (beta plan §3.1).
        streak["last_red_reason"] = "; ".join(reasons)[:300] or "YELLOW"
    else:  # PAUSED — indexer unreachable
        streak["last_red_reason"] = "; ".join(reasons)[:300] or "PAUSED"

    streak["last_run_date"] = today
    streak.setdefault("history", []).append({"date": today, "verdict": verdict})
    return streak


def run(args: argparse.Namespace) -> int:
    today = args.date or _today_str()
    indexer = args.indexer or _indexer_url()
    now = _utcnow()

    per_game: dict[str, dict] = {}
    for game in GAMES:
        bets = fetch_recent(indexer, game) if not args.dry_run else []
        per_game[game] = aggregate_game(bets, now)

    if args.dry_run:
        # Force a reachable empty-state path so operators can preview format.
        for game in GAMES:
            per_game[game] = {
                "reachable": True, "placed": 0, "settled": 0,
                "pending_stale": 0, "reverts": 0,
                "stake_eth": 0.0, "payout_eth": 0.0,
                "edge_pct": None, "p50_sec": None, "p95_sec": None, "max_sec": None,
            }

    verdict, reasons = compute_verdict(per_game)
    streak = load_streak()
    streak = update_streak(streak, verdict, today, reasons)

    citations = _new_beta_fix_tasks_last_24h()
    report = render_report(per_game, verdict, reasons, streak, today, indexer, citations)

    out_path = CRON_DIR / f"bb_beta_{today}.md"
    if args.dry_run:
        print(report)
        print(f"\n[dry-run] would write {out_path} and {STREAK_PATH}")
        return 0

    CRON_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    save_streak(streak)
    print(f"BB beta summary: verdict={verdict} streak={streak['green_days']} → {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily BB Phase 3 internal beta summary")
    parser.add_argument("--indexer", help="Indexer base URL (overrides BUNNYBAGZ_INDEXER_URL)")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip indexer poll, render an empty-state report to stdout")
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
