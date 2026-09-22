import asyncio
import json
import time
from datetime import datetime, timezone
import websockets
import requests

TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
MIN_AMOUNT = 1.0  # Example volume threshold

collected_events = []

def send_telegram_message(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"[Telegram Error]: {e}")

async def consume_market_data():
    url = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    while True:
        try:
            async with websockets.connect(url) as ws:
                print("[WebSocket] Connected to market stream...")
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    price = float(data.get('p', 0))
                    qty = float(data.get('q', 0))
                    
                    if qty >= MIN_AMOUNT:
                        print(f"[Stream] Event captured: Price={price}, Qty={qty}")
                        collected_events.append(data)
        except Exception as e:
            print(f"[WebSocket Error]: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

async def send_summary():
    while True:
        await asyncio.sleep(60)
        if len(collected_events) > 0:
            now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            lines = [f"*Institutional Summary Report - {now}*"]
            for ev in collected_events:
                price = float(ev.get('p', 0))
                qty = float(ev.get('q', 0))
                side = "SELL" if ev.get('m', False) else "BUY"
                lines.append(f"Side: {side} | Price: ${price:.2f} | Qty: {qty}")
            
            message = "\n".join(lines)
            print("[Summary] Sending Telegram message...")
            send_telegram_message(message)
            collected_events.clear()
        else:
            print("[Summary] No events collected in this period.")

async def main():
    await asyncio.gather(consume_market_data(), send_summary())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[Script Stopped by User]")
