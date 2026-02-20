#!/usr/bin/env python3
"""Minimal Gas API Server"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import threading
import requests
from datetime import datetime
from socketserver import ThreadingMixIn

PORT = 9000
CACHE_FILE = "/home/agent/.openclaw/workspace/services/gas-service/cache.json"

RPC_ENDPOINTS = {
    "base": "https://base-mainnet.public.blastapi.io",
    "optimism": "https://optimism-mainnet.public.blastapi.io", 
    "arbitrum": "https://arbitrum-one.public.blastapi.io"
}

def fetch_all_gas():
    result = {}
    for chain, rpc in RPC_ENDPOINTS.items():
        try:
            resp = requests.post(rpc, 
                json={"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1},
                timeout=5)
            data = resp.json()
            if "result" in data:
                result[chain] = round(int(data["result"], 16) / 1e9, 3)
        except Exception as e:
            print(f"{chain}: {e}")
    result["timestamp"] = datetime.now().isoformat()
    return result

def updater():
    while True:
        data = fetch_all_gas()
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
        print(f"Updated: {data}")
        time.sleep(30)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/", "/gas", "/gas/"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                with open(CACHE_FILE) as f:
                    self.wfile.write(f.read().encode())
            except:
                self.wfile.write(b'{"error":"No data"}')
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, fmt, *args):
        pass  # Silent

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    # Start updater thread
    t = threading.Thread(target=updater, daemon=True)
    t.start()
    
    # Initial fetch
    data = fetch_all_gas()
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)
    print(f"Initial: {data}")
    
    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Gas API running on port {PORT}")
    server.serve_forever()
