#!/usr/bin/env python3
"""Clarvis Gas API - Running"""
import threading
import time
import requests
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

PORT = 9000
CACHE_FILE = "/home/agent/.openclaw/workspace/services/gas-service/cache.json"
RPC = {
    "base": "https://base-mainnet.public.blastapi.io",
    "optimism": "https://optimism-mainnet.public.blastapi.io",
    "arbitrum": "https://arbitrum-one.public.blastapi.io"
}

def fetch_gas():
    result = {}
    for chain, url in RPC.items():
        try:
            resp = requests.post(url, json={"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1}, timeout=5)
            data = resp.json()
            if "result" in data:
                result[chain] = round(int(data["result"], 16) / 1e9, 3)
        except Exception as e:
            print(f"Error {chain}: {e}")
    result["timestamp"] = datetime.now().isoformat()
    return result

def updater():
    while True:
        data = fetch_gas()
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
        print(f"Updated: {data}")
        time.sleep(30)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            with open(CACHE_FILE) as f:
                self.wfile.write(f.read().encode())
        except:
            self.wfile.write(b"{}")
    def log_message(self, fmt, *args):
        pass

class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    # Start updater
    threading.Thread(target=updater, daemon=True).start()
    
    # Initial fetch
    with open(CACHE_FILE, "w") as f:
        json.dump(fetch_gas(), f)
    
    print(f"Gas API running on port {PORT}")
    Server(("0.0.0.0", PORT), Handler).serve_forever()
