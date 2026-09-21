import streamlit as st
import pandas as pd
import requests

st.title("MEXC LOB Scalping & Imbalance Dashboard")

# 1. Live MEXC Data Fetching Function
def fetch_mexc_live_orderbook(symbol="BTCUSDT", limit=10):
    url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if "bids" in data and "asks" in data:
            bids = data.get("bids", []) # [[price, volume], ...]
            asks = data.get("asks", [])
            
            bids_df = pd.DataFrame(bids, columns=['Price', 'Volume'])
            asks_df = pd.DataFrame(asks, columns=['Price', 'Volume'])
            
            # Top levels se Imbalance calculate karne ke liye top rows lenge
            return bids_df, asks_df
        else:
            st.error(f"API Response Error: {data}")
            return None, None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None, None

# 2. Imbalance Calculation (Research Paper Formula)
def calculate_imbalance(bids_df, asks_df, levels=5):
    """
    I_L,t = (V_L^bid - V_L^ask) / (V_L^bid + V_L^ask) formula ke mutabiq.
    """
    try:
        # Top 'levels' tak ka volume sum karna
        v_bid_total = bids_df['Volume'].head(levels).astype(float).sum()
        v_ask_total = asks_df['Volume'].head(levels).astype(float).sum()
        
        if (v_bid_total + v_ask_total) == 0:
            return 0.0
            
        imbalance = (v_bid_total - v_ask_total) / (v_bid_total + v_ask_total)
        return imbalance
    except Exception as e:
        return 0.0

# 3. UI Dashboard Logic
st.write("Analyzing live MEXC Order Book & Imbalance...")
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)

if bids_df is not None and asks_df is not None:
    # Top 5 levels ka LOB Imbalance nikalna
    imb_value = calculate_imbalance(bids_df, asks_df, levels=5)
    
    # Metric card dikhana
    st.metric(label="Order Book Imbalance (I_t)", value=f"{imb_value:.4f}")
    
    # Big Move & Trade Signals Strategy
    st.subheader("🎯 Scalping Signal & Trade Direction:")
    
    if imb_value >= 0.4:
        st.success("🟢 **STRONG LONG (BUY) SIGNAL!** Buyers dominate the order book. Price is likely to pump upwards.")
    elif imb_value <= -0.4:
        st.error("🔴 **STRONG SHORT (SELL) SIGNAL!** Sellers dominate the order book. Price is likely to dump downwards.")
    else:
        st.warning("⚪ **NEUTRAL / NO TRADE ZONE:** Market is balanced. Wait for a big imbalance spike (> 0.4 or < -0.4) to catch big moves.")
        
    # Data tables show karna
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids (Buyers)")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks (Sellers)")
        st.dataframe(asks_df.head(5))
else:
    st.warning("Waiting for live market data...")
