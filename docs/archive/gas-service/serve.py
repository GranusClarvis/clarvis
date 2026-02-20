#!/usr/bin/env python3
"""Simple gas API - serves only cache.json"""

import http.server
import socketserver
import json
import os

PORT = 9000
CACHE_FILE = "/home/agent/.openclaw/workspace/services/gas-service/cache.json"

class GasHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/gas", "/gas.json", "/cache.json"]:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE) as f:
                    self.wfile.write(f.read().encode())
            else:
                self.wfile.write(b'{}')
        elif self.path == "/health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, *args):
        pass  # No logging

# Kill old server
os.system("pkill -f 'http.server 9000' 2>/dev/null")

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), GasHandler) as httpd:
    print(f"Clarvis Gas API on port {PORT}")
    httpd.serve_forever()