#!/usr/bin/env python3
"""
Budget Alert System — Monitors OpenRouter spending and alerts via Telegram.

Checks remaining credits against configurable thresholds and sends
Telegram alerts with anti-spam cooldowns (1 alert per threshold per 6 hours).

Usage:
    python3 budget_alert.py              # Check and alert if needed
    python3 budget_alert.py --test       # Send a test alert to verify Telegram
    python3 budget_alert.py --status     # Print current budget status (no alert)
    python3 budget_alert.py --json       # JSON output for programmatic use

Configuration: workspace/data/budget_config.json
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from cost_api import fetch_usage

# === CONFIGURATION ===

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
CONFIG_FILE = os.path.join(DATA_DIR, 'budget_config.json')
STATE_FILE = os.path.join(DATA_DIR, 'budget_alert_state.json')

DEFAULT_CONFIG = {
    "thresholds": [
        {"name": "critical", "remaining_below": 10, "message": "CRITICAL: Less than $10 remaining on OpenRouter!"},
        {"name": "warning", "remaining_below": 20, "message": "WARNING: Less than $20 remaining on OpenRouter."},
        {"name": "daily_high", "daily_above": 10, "message": "Daily spend exceeds $10 on OpenRouter."},
    ],
    "cooldown_hours": 6,
    "telegram_bot_token": "REDACTED_TELEGRAM_BOT_TOKEN",
    "telegram_chat_id": "REDACTED_CHAT_ID",
}


def load_config() -> dict:
    """Load config, creating with defaults if missing."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    # Create default config
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    return DEFAULT_CONFIG


def load_state() -> dict:
    """Load alert state (last alert timestamps per threshold)."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    return {"last_alerts": {}}


def save_state(state: dict):
    """Save alert state atomically."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }).encode()

    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return result.get("ok", False)
    except Exception as e:
        print(f"Telegram send failed: {e}", file=sys.stderr)
        return False


def check_and_alert(test_mode=False) -> dict:
    """Check budget thresholds and send alerts if needed.

    Returns:
        {"alerts_sent": int, "usage": dict, "triggered": [str]}
    """
    config = load_config()
    state = load_state()
    usage = fetch_usage()

    now = time.time()
    cooldown_s = config.get("cooldown_hours", 6) * 3600
    triggered = []
    alerts_sent = 0

    for threshold in config.get("thresholds", []):
        name = threshold["name"]

        # Check if threshold is triggered
        fired = False
        if "remaining_below" in threshold and usage.get("remaining") is not None:
            fired = usage["remaining"] < threshold["remaining_below"]
        elif "daily_above" in threshold:
            fired = usage["daily"] > threshold["daily_above"]

        if not fired:
            continue

        triggered.append(name)

        # Check cooldown
        last_alert = state.get("last_alerts", {}).get(name, 0)
        if not test_mode and (now - last_alert) < cooldown_s:
            continue

        # Build alert message
        msg = f"<b>Budget Alert: {threshold['message']}</b>\n\n"
        msg += f"Today: ${usage['daily']:.2f}\n"
        msg += f"Week: ${usage['weekly']:.2f}\n"
        msg += f"Month: ${usage['monthly']:.2f}\n"
        if usage["remaining"] is not None:
            msg += f"Remaining: ${usage['remaining']:.2f} / ${usage.get('limit', '?')}\n"

        if test_mode:
            msg = f"<b>[TEST] {msg.lstrip('<b>')}"

        # Send alert
        bot_token = config.get("telegram_bot_token", "")
        chat_id = config.get("telegram_chat_id", "")
        if bot_token and chat_id:
            if send_telegram(bot_token, chat_id, msg):
                alerts_sent += 1
                state.setdefault("last_alerts", {})[name] = now
                print(f"Alert sent: {name}", file=sys.stderr)
            else:
                print(f"Alert FAILED: {name}", file=sys.stderr)

    save_state(state)

    return {
        "alerts_sent": alerts_sent,
        "usage": usage,
        "triggered": triggered,
    }


def main():
    if "--test" in sys.argv:
        print("Sending test alert...")
        config = load_config()
        usage = fetch_usage()
        msg = "<b>[TEST] Budget Alert System Working</b>\n\n"
        msg += f"Today: ${usage['daily']:.2f}\n"
        msg += f"Week: ${usage['weekly']:.2f}\n"
        msg += f"Month: ${usage['monthly']:.2f}\n"
        if usage["remaining"] is not None:
            msg += f"Remaining: ${usage['remaining']:.2f} / ${usage.get('limit', '?')}\n"
        msg += f"\nTimestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

        ok = send_telegram(
            config.get("telegram_bot_token", ""),
            config.get("telegram_chat_id", ""),
            msg
        )
        print(f"Test alert: {'sent successfully' if ok else 'FAILED'}")
        return

    if "--status" in sys.argv:
        usage = fetch_usage()
        config = load_config()
        state = load_state()
        print("=== Budget Status ===")
        print(f"Daily:     ${usage['daily']:.4f}")
        print(f"Weekly:    ${usage['weekly']:.4f}")
        print(f"Monthly:   ${usage['monthly']:.4f}")
        if usage["remaining"] is not None:
            print(f"Remaining: ${usage['remaining']:.4f} / ${usage.get('limit', '?')}")
        print("\nThresholds:")
        now = time.time()
        cooldown_s = config.get("cooldown_hours", 6) * 3600
        for t in config.get("thresholds", []):
            last = state.get("last_alerts", {}).get(t["name"], 0)
            cooldown_left = max(0, cooldown_s - (now - last)) / 3600
            triggered = False
            if "remaining_below" in t and usage.get("remaining") is not None:
                triggered = usage["remaining"] < t["remaining_below"]
            elif "daily_above" in t:
                triggered = usage["daily"] > t["daily_above"]
            status = "TRIGGERED" if triggered else "ok"
            cooldown_str = f" (cooldown: {cooldown_left:.1f}h)" if last > 0 else ""
            print(f"  {t['name']}: {status}{cooldown_str}")
        return

    if "--json" in sys.argv:
        result = check_and_alert()
        print(json.dumps(result, indent=2))
        return

    result = check_and_alert()
    if result["triggered"]:
        print(f"Triggered: {', '.join(result['triggered'])} | Alerts sent: {result['alerts_sent']}")
    else:
        print(f"Budget OK — remaining: ${result['usage'].get('remaining', '?')}")


if __name__ == "__main__":
    main()
