#!/usr/bin/env python3
"""
Clarvis Gas Price Service
Monitors and serves Base network gas prices
"""

import json
import time
import requests
from datetime import datetime
import os

# Base RPC endpoints (public)
RPC_ENDPOINTS = [
    "https://base-mainnet.public.blastapi.io",
    "https://base.llamarpc.com",
]

CACHE_FILE = "/home/agent/.openclaw/workspace/services/gas-service/cache.json"
LOG_FILE = "/home/agent/.openclaw/workspace/services/gas-service/requests.log"

def wei_to_gwei(wei):
    """Convert wei to gwei"""
    return int(wei, 16) / 1e9

def get_gas_prices():
    """Fetch current gas prices from Base"""
    for rpc in RPC_ENDPOINTS:
        try:
            # Get current gas price
            response = requests.post(rpc, 
                json={"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1},
                timeout=10)
            data = response.json()
            
            if "result" in data:
                gas_wei = int(data["result"], 16)
                gas_gwei = gas_wei / 1e9
                
                # Estimate L1 fees (rough approximation)
                l1_fee = 0.001  # Base L1 fee estimate
                
                return {
                    "slow": round(gas_gwei * 0.8, 4),
                    "normal": round(gas_gwei, 4),
                    "fast": round(gas_gwei * 1.2, 4),
                    "current_gwei": round(gas_gwei, 4),
                    "l1_estimate": l1_fee,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            print(f"RPC {rpc} failed: {e}")
            continue
    
    return None

def log_request(gas_data):
    """Log incoming requests"""
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {json.dumps(gas_data)}\n")

def serve():
    """Main service loop"""
    gas_data = get_gas_prices()
    
    if gas_data:
        # Cache the data
        with open(CACHE_FILE, "w") as f:
            json.dump(gas_data, f)
        
        log_request(gas_data)
        print(json.dumps(gas_data))
    else:
        # Serve cached if available
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cached = json.load(f)
            print(json.dumps(cached))
        else:
            print(json.dumps({"error": "No data available"}))

if __name__ == "__main__":
    serve()
