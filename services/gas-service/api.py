#!/usr/bin/env python3
"""
Clarvis Gas API - Pure stdlib version
"""

import http.server
import socketserver
import json
import os
import threading
import time
import requests
from datetime import datetime
from urllib.parse import urlparse

PORT = 9000
CACHE_FILE = "/home/agent/.openclaw/workspace/services/gas-service/cache.json"
LOG_FILE = "/home/agent/.openclaw/workspace/services/gas-service/requests.log"

RPC_ENDPOINTS = {
    "base": "https://base-mainnet.public.blastapi.io",
    "optimism": "https://optimism-mainnet.public.blastapi.io", 
    "arbitrum": "https://arbitrum-one.public.blastapi.io"
}

def wei_to_gwei(wei_str):
    return int(wei_str, 16) / 1e9

def fetch_gas(chain="base"):
    rpc = RPC_ENDPOINTS.get(chain)
    try:
        resp = requests.post(rpc, 
            json={"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1},
            timeout=10)
        data = resp.json()
        if "result" in data:
            return wei_to_gwei(data["result"])
    except Exception as e:
        print(f"Error fetching {chain}: {e}")
    return None

def update_cache():
    while True:
        result = {}
        for chain in RPC_ENDPOINTS:
            gas = fetch_gas(chain)
            if gas:
                result[chain] = round(gas, 3)
        
        if result:
            result["timestamp"] = datetime.now().isoformat()
            with open(CACHE_FILE, "w") as f:
                json.dump(result, f)
            print(f"Updated: {result}")
        
        time.sleep(30)

class GasHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        
        # Log request
        with open(LOG_FILE, "a") as l:
            l.write(f"{datetime.now().isoformat()} - {path}\n")
        
        if path in ["/", "/gas", "/gas/"]:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    self.wfile.write(f.read().encode())
            else:
                self.wfile.write(b'{"error":"No data"}')
        
        elif path.startswith("/gas/"):
            chain = path.split("/")[-1]
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    if chain in data:
                        self.wfile.write(json.dumps({"chain": chain, "gas_gwei": data[chain], "timestamp": data.get("timestamp")}).encode())
                    else:
                        self.wfile.write(b'{"error":"Chain not found"}')
        
        elif path == "/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging

if __name__ == "__main__":
    # Start background updater
    updater = threading.Thread(target=update_cache, daemon=True)
    updater.start()
    
    # Initial fetch
    update_cache()
    
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), GasHandler) as httpd:
        print(f"Clarvis Gas API running on port {PORT}")
        httpd.serve_forever()