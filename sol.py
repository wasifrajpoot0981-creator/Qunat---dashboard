import streamlit as st
import pandas as pd
import requests

st.title("MEXC LOB Scalping Dashboard")

# 1. Updated MEXC v3 API Endpoint
def fetch_mexc_live_orderbook(symbol="BTCUSDT", limit=10):
    url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # Check if bids and asks exist in the response
        if "bids" in data and "asks" in data:
            bids = data.get("bids", []) # [[price, volume], ...]
            asks = data.get("asks", [])
            
            bids_df = pd.DataFrame(bids, columns=['Price', 'Volume'])
            bids_df['Buy/Sell'] = 1  # 1 for Bid/Buy
            
            asks_df = pd.DataFrame(asks, columns=['Price', 'Volume'])
            asks_df['Buy/Sell'] = -1 # -1 for Ask/Sell
            
            combined_df = pd.concat([bids_df, asks_df], ignore_index=True)
            combined_df['TimeStamp'] = pd.Timestamp.now()
            
            combined_df['Price'] = combined_df['Price'].astype(float)
            combined_df['Volume'] = combined_df['Volume'].astype(float)
            
            return combined_df
        else:
            st.error(f"API Response Error: {data}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# 2. UI Display Logic (Symbol format is BTCUSDT without underscore for v3 API)
st.write("Fetching live order book from MEXC v3 API...")
df = fetch_mexc_live_orderbook("BTCUSDT", 10)

if df is not None and not df.empty:
    st.success("Data fetched successfully!")
    st.dataframe(df)
else:
    st.warning("Waiting for data or check symbol format.")
