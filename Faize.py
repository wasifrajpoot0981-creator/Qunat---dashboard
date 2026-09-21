import requests
import pandas as pd

def fetch_mexc_live_orderbook(symbol="BTCUSDT", depth=10):
    """
    MEXC public API se live order book fetch karta hai aur DataFrame banata hai.
    """
    url = f"https://www.mexc.com/open/api/v2/market/depth?symbol={symbol}&depth={depth}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get("code") == 200:
            result = data.get("data", {})
            bids = result.get("bids", []) # [price, volume]
            asks = result.get("asks", []) # [price, volume]
            
            # DataFrame mein convert karna
            bids_df = pd.DataFrame(bids, columns=['Price', 'Volume'])
            bids_df['Buy/Sell'] = 1  # 1 for Bid/Buy
            
            asks_df = pd.DataFrame(asks, columns=['Price', 'Volume'])
            asks_df['Buy/Sell'] = -1 # -1 for Ask/Sell
            
            # Combine karna
            combined_df = pd.concat([bids_df, asks_df], ignore_index=True)
            combined_df['TimeStamp'] = pd.Timestamp.now()
            
            # Data types fix karna
            combined_df['Price'] = combined_df['Price'].astype(float)
            combined_df['Volume'] = combined_df['Volume'].astype(float)
            
            return combined_df
        else:
            print("API Error:", data)
            return None
    except Exception as e:
        print("Connection Error:", e)
        return None

# Test karne ke liye:
# df = fetch_mexc_live_orderbook("BTC_USDT", 10)
# print(df.head())
