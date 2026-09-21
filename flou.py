import streamlit as st
import pandas as pd
import requests

st.title("MEXC LOB Scalping Dashboard")

# 1. Live MEXC Data Fetching Function
def fetch_mexc_live_orderbook(symbol="BTC_USDT", depth=10):
    url = f"https://www.mexc.com/open/api/v2/market/depth?symbol={symbol}&depth={depth}"
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get("code") == 200:
            result = data.get("data", {})
            bids = result.get("bids", [])
            asks = result.get("asks", [])
            
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
            st.error(f"API Error: {data}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# 2. UI Display Logic
st.write("Fetching live order book from MEXC...")
df = fetch_mexc_live_orderbook("BTC_USDT", 10)

if df is not None and not df.empty:
    st.success("Data fetched successfully!")
    st.dataframe(df)
else:
    st.warning("Waiting for data or check symbol format.")
