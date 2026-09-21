import requests
import pandas as pd
import time

def get_mexc_orderbook_dataframe(symbol="BTC_USDT", limit=20):
    url = f"https://www.mexc.com/open/api/v2/market/depth?symbol={symbol}&depth={limit}"
    
    try:
        response = requests.get(url, timeout=5).json()
        if response.get("code") == 200:
            data = response.get("data", {})
            bids = data.get("bids", [])  # Format: [[price, volume], ...]
            asks = data.get("asks", [])  # Format: [[price, volume], ...]
            
            current_timestamp = time.time()
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
                
            # Pandas DataFrame banana jo bilkul aapki CSV file jaisa dikhega
            df = pd.DataFrame(rows)
            return df
            
    except Exception as e:
        print(f"Error fetching MEXC data: {e}")
        
    return pd.DataFrame()

# Code ko test karne ke liye DataFrame print karein:
data = get_mexc_orderbook_dataframe("BTC_USDT", 10)
print(data.head())
