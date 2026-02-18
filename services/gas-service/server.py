#!/usr/bin/env python3
"""
Clarvis Gas Price API Server
Simple HTTP server serving Base gas data
"""

import http.server
import socketserver
import json
import os
from urllib.parse import urlparse
import gas_monitor

PORT = 8080
CACHE_FILE = "/home/agent/.openclaw/workspace/services/gas-service/cache.json"

class GasHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == "/" or path == "/gas":
            # Serve cached gas data
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(503)
                self.end_headers()
                
        elif path == "/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def refresh_gas():
    """Refresh gas data in background"""
    import subprocess
    subprocess.Popen(["python3", "/home/agent/.openclaw/workspace/services/gas-service/gas_monitor.py"])

if __name__ == "__main__":
    # Refresh gas data on startup
    refresh_gas()
    
    with socketserver.TCPServer(("", PORT), GasHandler) as httpd:
        print(f"Clarvis Gas Service running on port {PORT}")
        httpd.serve_forever()
