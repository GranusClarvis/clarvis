import requests
import json
import time
from datetime import datetime

CHAINS = {
    "base": "https://base-mainnet.public.blastapi.io",
    "optimism": "https://optimism-mainnet.public.blastapi.io",
    "arbitrum": "https://arbitrum-one.public.blastapi.io"
}

def wei_to_gwei(wei_str):
    return int(wei_str, 16) / 1e9

def fetch_gas(rpc):
    try:
        resp = requests.post(rpc, json={"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1}, timeout=10)
        return wei_to_gwei(resp.json()["result"])
    except:
        return None

while True:
    result = {}
    for chain, rpc in CHAINS.items():
        gas = fetch_gas(rpc)
        if gas:
            result[chain] = round(gas, 4)
    
    if result:
        result["timestamp"] = datetime.now().isoformat()
        with open("cache.json", "w") as f:
            json.dump(result, f)
        print(f"Updated: {result}")
    else:
        print("Failed to fetch gas prices")
    
    time.sleep(30)
