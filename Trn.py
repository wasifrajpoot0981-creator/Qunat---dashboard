import streamlit as st
import pandas as pd
import numpy as np
import requests

st.title("MEXC 15M Reversal & Momentum Dashboard")

# 1. Live MEXC Order Book Fetching Function
def fetch_mexc_live_orderbook(symbol="BTCUSDT", limit=10):
    url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if "bids" in data and "asks" in data:
            bids_df = pd.DataFrame(data.get("bids", []), columns=['Price', 'Volume']).astype(float)
            asks_df = pd.DataFrame(data.get("asks", []), columns=['Price', 'Volume']).astype(float)
            return bids_df, asks_df
        return None, None
    except Exception as e:
        return None, None

# 2. Safe 15M Candlestick Data (Sirf 6 main columns taake error na aaye)
def fetch_15m_market_structure(symbol="BTCUSDT"):
    url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval=15m&limit=15"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data)[[0, 1, 2, 3, 4, 5]]
            df.columns = ['Open_Time', 'Open', 'High', 'Low', 'Close', 'Volume']
            df[['Open', 'High', 'Low', 'Close', 'Volume']] = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
            return df
        return None
    except Exception as e:
        return None

# 3. Volume Weighted Order Book Imbalance (VW-OBI)
def calculate_vw_obi(bids_df, asks_df, max_levels=5):
    num_levels = min(len(bids_df), len(asks_df), max_levels)
    if num_levels == 0:
        return 0.0
    weighted_bid_sum = sum((1.0 / i) * bids_df.loc[i-1, 'Volume'] for i in range(1, num_levels + 1))
    weighted_ask_sum = sum((1.0 / i) * asks_df.loc[i-1, 'Volume'] for i in range(1, num_levels + 1))
    denominator = weighted_bid_sum + weighted_ask_sum
    if denominator == 0:
        return 0.0
    return (weighted_bid_sum - weighted_ask_sum) / denominator

# 4. Large Order Aggressor Flow (LOAF)
def calculate_loaf(bids_df, asks_df, theta=1.5):
    large_bids = bids_df[bids_df['Volume'] > theta]['Volume'].sum()
    large_asks = asks_df[asks_df['Volume'] > theta]['Volume'].sum()
    return large_bids - large_asks

# 5. Hawkes Process Self-Exciting Intensity
def calculate_hawkes_intensity(volume_history, alpha=0.5, beta=0.8):
    if not volume_history or len(volume_history) < 2:
        return float(np.mean(volume_history)) if volume_history else 0.0
    baseline = float(np.mean(volume_history))
    excitement = sum([v * alpha * np.exp(-beta * (len(volume_history) - i)) for i, v in enumerate(volume_history)])
    return baseline + excitement

# Session States
if 'vol_history' not in st.session_state:
    st.session_state.vol_history = []
if 'prev_obi' not in st.session_state:
    st.session_state.prev_obi = 0.0

# Fetch Data
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)
df_15m = fetch_15m_market_structure("BTCUSDT")

if bids_df is not None and asks_df is not None and df_15m is not None:
    # Core calculations
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.5)
    
    total_vol = bids_df['Volume'].sum() + asks_df['Volume'].sum()
    st.session_state.vol_history.append(total_vol)
    if len(st.session_state.vol_history) > 15:
        st.session_state.vol_history.pop(0)
    
    hawkes = calculate_hawkes_intensity(st.session_state.vol_history)
    obi_delta = vw_obi - st.session_state.prev_obi
    st.session_state.prev_obi = vw_obi
    
    # 15M Reversal & Structure Check
    current_close = df_15m['Close'].iloc[-1]
    prev_close = df_15m['Close'].iloc[-2]
    prev_open = df_15m['Open'].iloc[-2]
    curr_open = df_15m['Open'].iloc[-1]
    
    # Buyer to Seller or Seller to Buyer Reversal Switch on 15M
    seller_to_buyer_15m = (prev_close < prev_open) and (current_close > curr_open)
    buyer_to_seller_15m = (prev_close > prev_open) and (current_close < curr_open)
    
    # Dashboard Metrics Layout
    st.subheader("🚀 MEXC 15M Reversal & Momentum Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VW-OBI", f"{vw_obi:.4f}")
    c2.metric("OBI Delta", f"{obi_delta:.4f}")
    c3.metric("LOAF Value", f"{loaf_val:.2f}")
    c4.metric("15M Close", f"${current_close:,.2f}")
    
    # Strict Filtered Reversal Signals
    st.subheader("🎯 15M Reversal Signal Execution")
    
    long_signal = seller_to_buyer_15m and (vw_obi > 0.10) and (obi_delta > 0.03) and (hawkes > 8.0)
    short_signal = buyer_to_seller_15m and (vw_obi < -0.10) and (obi_delta < -0.03) and (hawkes > 8.0)
    
    if long_signal:
        st.success("🟢 **15M PUMP REVERSAL (Seller -> Buyer):** Momentum shifting to buyers with strong volume & order book support!")
    elif short_signal:
        st.error("🔴 **15M DUMP REVERSAL (Buyer -> Seller):** Momentum shifting to sellers (Dump setup) confirmed!")
    else:
        st.warning("⚪ **WAITING FOR REVERSAL:** Market is running normal. Waiting for exact 15M candle flip & order book shift.")
        
    # Order Book View
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning("⚠️ Connecting to MEXC Live API & 15M Candles...")
