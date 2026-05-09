#!/usr/bin/env python3
"""Telegram notifier for cron_bb_visual_regression.sh.

Reads the JSON report produced by `apps/web/scripts/visual-baseline.mjs
--diff --json`, formats a compact summary of regressions, and POSTs it
to Telegram. Mirrors the env conventions of `scripts/infra/budget_alert.py`
so the operator's existing bot creds work unchanged.

Environment:
  TELEGRAM_BOT_TOKEN      bot token (required)
  CLARVIS_TG_GROUP_ID     group chat id (preferred when set)
  CLARVIS_TG_TOPIC_ID     optional topic thread id
  CLARVIS_TG_CHAT_ID      fallback DM chat id

Exit codes:
  0 — message sent (or env missing — caller logs and moves on)
  1 — Telegram API error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import Any


def _send(token: str, chat_id: str, text: str, topic_id: str = "") -> bool:
    if not token or not chat_id:
        print("[notify] missing TELEGRAM_BOT_TOKEN or chat id — noop", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text[:3900],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if topic_id and topic_id != "1" and topic_id.isdigit():
        payload["message_thread_id"] = int(topic_id)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return bool(result.get("ok"))
    except Exception as exc:  # noqa: BLE001 — surface any failure
        print(f"[notify] telegram error: {exc}", file=sys.stderr)
        return False


def _format(report: dict) -> str:
    regressions = [d for d in report.get("diffs", []) if d.get("regression")]
    total_captured = report.get("captured", 0)
    capture_errors = report.get("captureErrors", []) or []
    thresholds = report.get("thresholds", {"pixel": 0.05, "hash": 10})
    lines = [
        "<b>BunnyBagz visual regression</b>",
        f"captured={total_captured} regressions={len(regressions)} "
        f"thresholds=pixel&gt;{thresholds.get('pixel', 0.05) * 100:.0f}% / hash&gt;{thresholds.get('hash', 10)}",
    ]
    if capture_errors:
        lines.append(f"capture_errors={len(capture_errors)}")
    # Sort by pixel ratio descending so the worst regressions surface first.
    def _key(d: dict) -> float:
        v = d.get("pixelRatio")
        return float(v) if isinstance(v, (int, float)) else 1.0

    for d in sorted(regressions, key=_key, reverse=True)[:12]:
        ratio = d.get("pixelRatio")
        dist = d.get("hashDistance")
        ratio_s = f"{ratio * 100:.1f}%" if isinstance(ratio, (int, float)) else "?"
        dist_s = f"{dist}" if isinstance(dist, int) else "?"
        err = d.get("error")
        suffix = f" err={err}" if err else ""
        lines.append(
            f"• <code>{d.get('route')}</code> {d.get('viewport')} "
            f"{d.get('theme')} — pixel={ratio_s} hash={dist_s}{suffix}"
        )
    if len(regressions) > 12:
        lines.append(f"… and {len(regressions) - 12} more")
    lines.append(
        "Update baseline (after intentional change):\n"
        "<code>cd apps/web && node scripts/visual-baseline.mjs --update-baseline</code>"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="path to JSON report")
    args = parser.parse_args()

    try:
        with open(args.report, encoding="utf-8") as fh:
            report = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"[notify] cannot read report: {exc}", file=sys.stderr)
        return 1

    text = _format(report)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    group_id = os.environ.get("CLARVIS_TG_GROUP_ID", "")
    topic_id = os.environ.get("CLARVIS_TG_TOPIC_ID", "")
    chat_id = os.environ.get("CLARVIS_TG_CHAT_ID", "")

    target = group_id or chat_id
    if not target:
        # Fall back to the same budget_config.json chat if available.
        cfg_path = os.path.join(
            os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")),
            "data",
            "budget_config.json",
        )
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
            target = cfg.get("telegram_chat_id", "") or target
            if not token:
                token = cfg.get("telegram_bot_token", "") or token
        except Exception:
            pass

    if not (token and target):
        print("[notify] no telegram creds — printing report to stdout instead", file=sys.stderr)
        print(text)
        return 0

    ok = _send(token, target, text, topic_id)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
