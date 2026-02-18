#!/usr/bin/env python3
"""
Crypto Price Alert Checker
Checks prices via CoinGecko API and triggers alerts
"""

import json
import os
import time
from urllib.request import urlopen
from urllib.parse import quote

ALERTS_FILE = "/home/agent/.openclaw/workspace/services/crypto-alerts/alerts.json"
LOG_FILE = "/home/agent/.openclaw/workspace/services/crypto-alerts/check.log"
COINGECKO_API = "https://api.coingecko.com/api/v3"

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return {}
    with open(ALERTS_FILE, "r") as f:
        return json.load(f)

def get_price(coin_id):
    """Fetch price from CoinGecko"""
    try:
        url = f"{COINGECKO_API}/simple/price?ids={coin_id}&vs_currencies=usd"
        with urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get(coin_id, {}).get("usd")
    except Exception as e:
        log(f"Error fetching {coin_id}: {e}")
        return None

def check_alerts():
    """Check all alerts and return triggered ones"""
    alerts = load_alerts()
    triggered = []
    
    for coin_id, alert_list in alerts.items():
        current_price = get_price(coin_id)
        if current_price is None:
            continue
            
        for alert in alert_list:
            target = alert["price"]
            direction = alert["direction"]  # "above" or "below"
            
            if direction == "above" and current_price >= target:
                triggered.append(f"{coin_id} above ${target} (now ${current_price})")
            elif direction == "below" and current_price <= target:
                triggered.append(f"{coin_id} below ${target} (now ${current_price})")
    
    return triggered

if __name__ == "__main__":
    triggered = check_alerts()
    if triggered:
        for t in triggered:
            log(f"TRIGGERED: {t}")
            print(f"ALERT: {t}")
    else:
        log("No alerts triggered")
        print("No alerts triggered")
