#!/usr/bin/env python3
"""
Crypto Alerts CLI - Manage alerts from command line
Usage: python3 manage.py add <coin> <price> <above|below>
       python3 manage.py remove <coin>
       python3 manage.py list
"""

import json
import sys
import os

ALERTS_FILE = "/home/agent/.openclaw/workspace/services/crypto-alerts/alerts.json"

def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return {}
    with open(ALERTS_FILE, "r") as f:
        return json.load(f)

def save_alerts(alerts):
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)

def add_alert(coin, price, direction):
    coin = coin.lower()
    alerts = load_alerts()
    if coin not in alerts:
        alerts[coin] = []
    alerts[coin].append({"price": float(price), "direction": direction})
    save_alerts(alerts)
    print(f"Added alert: {coin} {direction} ${price}")

def remove_alert(coin):
    coin = coin.lower()
    alerts = load_alerts()
    if coin in alerts:
        del alerts[coin]
        save_alerts(alerts)
        print(f"Removed all alerts for {coin}")
    else:
        print(f"No alerts found for {coin}")

def list_alerts():
    alerts = load_alerts()
    if not alerts:
        print("No alerts set")
        return
    for coin, alert_list in alerts.items():
        print(f"\n{coin.upper()}:")
        for a in alert_list:
            print(f"  - {a['direction']} ${a['price']}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    
    if cmd == "add" and len(sys.argv) == 5:
        add_alert(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "remove" and len(sys.argv) == 3:
        remove_alert(sys.argv[2])
    elif cmd == "list":
        list_alerts()
    else:
        print("Usage: python3 manage.py add <coin> <price> <above|below>")
        print("       python3 manage.py remove <coin>")
        print("       python3 manage.py list")
