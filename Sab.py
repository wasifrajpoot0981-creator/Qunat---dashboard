import asyncio
import websockets
import json
from datetime import datetime

async def btc_flow_tracker():
    url = "wss://ws.blockchain.info/inv"
    print("🔄 Connecting to Blockchain.info WebSocket...")
    
    try:
        async with websockets.connect(url) as ws:
            print("✅ Connected Successfully! Subscribing to unconfirmed transactions...")
            await ws.send(json.dumps({"op": "unconfirmed_sub"}))
            
            tx_queue = []
            last_report = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # Message receive karne ka wait kar rahe hain
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if data.get("op") == "utx":
                        print("⚡ New Transaction Detected!") # Yeh batayega ke data aa raha hai
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
                        print(f"[{time_str}] Net flow last 5s: {net_flow_btc:.6f} BTC (Queue size: {len(tx_queue)})")
                        last_report = current_time
                        
                except Exception as inner_e:
                    print(f"⚠️ Error inside loop: {inner_e}")
                    await asyncio.sleep(2)
                    
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

async def main():
    await btc_flow_tracker()

if __name__ == "__main__":
    asyncio.run(main())
