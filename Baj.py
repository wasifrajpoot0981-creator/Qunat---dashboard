import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import requests
import time

# --- 1. MEXC Live Data Fetcher & Formatter ---
def fetch_mexc_live_orderbook(symbol="BTC_USDT", limit=20):
    """MEXC public API se live order book fetch karke model format mein badalta hai"""
    url = f"https://www.mexc.com/open/api/v2/market/depth?symbol={symbol}&depth={limit}"
    
    try:
        response = requests.get(url, timeout=5).json()
        if response.get("code") == 200:
            data = response.get("data", {})
            bids = data.get("bids", []) # [[price, volume], ...]
            asks = data.get("asks", []) # [[price, volume], ...]
            
            # Current timestamp ko float format mein (jaise purane data mein tha)
            current_timestamp = float(time.time())
            rows = []
            
            # Bids ko 'B' (Buy) ke tor par add karna
            for price, volume in bids:
                rows.append({
                    'TimeStamp': current_timestamp,
                    'Buy/Sell': 'B',
                    'Price': float(price),
                    'Volume': float(volume)
                })
                
            # Asks ko 'S' (Sell) ke tor par add karna
            for price, volume in asks:
                rows.append({
                    'TimeStamp': current_timestamp,
                    'Buy/Sell': 'S',
                    'Price': float(price),
                    'Volume': float(volume)
                })
                
            return pd.DataFrame(rows)
    except Exception as e:
        print(f"MEXC API Error: {e}")
        
    return pd.DataFrame()

# --- 2. Live Data Load karna (CSV ki jagah live MEXC data) ---
print("Fetching live order book data from MEXC...")
data = fetch_mexc_live_orderbook("BTC_USDT", 20)

if not data.empty:
    print("Data Shape:", data.shape)
    display(data.head())
    
    # --- 3. Model Processing Logic (Bug-Free Groupby) ---
    print("total bid orders: ", len(data[data['Buy/Sell'] == 'B']))
    print("total ask orders: ", len(data[data['Buy/Sell'] == 'S']))

    # Buy ('B') aur Sell ('S') orders ko alag karna
    def orders_by_type(df, order_type):
        return df[df['Buy/Sell'] == order_type]

    buys = orders_by_type(data, 'B')
    sells = orders_by_type(data, 'S')

    # Bug-free groupby using 'TimeStamp' column directly
    buys_dict = buys.groupby('TimeStamp').apply(lambda x: x.set_index('Price')['Volume'].to_dict()).to_dict()
    sells_dict = sells.groupby('TimeStamp').apply(lambda x: x.set_index('Price')['Volume'].to_dict()).to_dict()

    # Dictionaries ko list format mein convert karne ka function
    def price_vol(orders_dict):
        pri_vol = []
        for k, v in orders_dict.items():
            pri_vol.append(list(v.items()))
        return pri_vol

    buy_orders = price_vol(buys_dict)
    sell_orders = price_vol(sells_dict)
    
    print("Buy orders processed successfully! Length:", len(buy_orders))
else:
    print("Failed to fetch live data from MEXC.")
