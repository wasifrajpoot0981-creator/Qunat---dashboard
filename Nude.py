import asyncio
import websockets
import json
import requests
from datetime import datetime, timezone

# --- Telegram Bot Setup (Screenshot 2 wala logic) ---
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Error: {e}")

# --- 1. Blockchain Flow Tracker (Screenshot 1 wala code) ---
async def btc_flow_tracker():
    url = "wss://ws.blockchain.info/inv"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"op": "unconfirmed_sub"}))
        print("Connected to Blockchain.info WebSocket...")
        
        tx_queue = []
        last_report = asyncio.get_event_loop().time()
        
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                
                if data.get("op") == "utx":
                    tx = data["x"]
                    total_in = sum([inp['prev_out']['value'] for inp in tx['inputs'] if 'prev_out' in inp])
                    total_out = sum([out['value'] for out in tx['out']])
                    tx_queue.append((total_in, total_out, asyncio.get_event_loop().time()))
                
                # Every 5 seconds, calculate net flow
                current_time = asyncio.get_event_loop().time()
                if current_time - last_report >= 5:
                    cutoff = current_time - 5
                    while tx_queue and tx_queue[0][2] < cutoff:
                        tx_queue.pop(0)
                        
                    net_in = sum(tx[0] for tx in tx_queue)
                    net_out = sum(tx[1] for tx in tx_queue)
                    net_flow_btc = (net_out - net_in) / 1e8
                    
                    time_str = datetime.now().strftime('%H:%M:%S')
                    print(f"[{time_str}] Net flow last 5s: {net_flow_btc:.6f} BTC")
                    last_report = current_time
            except Exception as e:
                print(f"Flow Tracker Error: {e}")
                await asyncio.sleep(5)

# --- 2. Main Async Runner ---
async def main():
    # Aap yahan dono functions (Flow tracker aur Liquidation consumer) ko ek sath chala sakte hain
    await asyncio.gather(btc_flow_tracker())

if __name__ == "__main__":
    # Jupyter ya local script ke liye run command
    asyncio.run(main())
