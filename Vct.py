import streamlit as st
import pandas as pd
import numpy as np
import requests

st.title("MEXC 15M Balanced Multi-Model Dashboard")

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

# 2. Fetch 15M Candlestick Data for Market Structure Shift (CHoCH / BOS)
def fetch_15m_market_structure(symbol="BTCUSDT"):
    url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval=15m&limit=25"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data, columns=[
                'Open_Time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close_Time', 'Quote_Asset_Volume', 'Trades', 'Taker_Buy_Base', 'Taker_Buy_Quote', 'Ignore'
            ])
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

# 6. Logistic Sigmoid Probability Mapping
def calculate_sigmoid_probability(vw_obi, k=3.5):
    p_long = 1.0 / (1.0 + np.exp(-k * vw_obi))
    p_short = 1.0 - p_long
    return p_long, p_short

# Session States
if 'vol_history' not in st.session_state:
    st.session_state.vol_history = []

# Fetch Data
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)
df_15m = fetch_15m_market_structure("BTCUSDT")

if bids_df is not None and asks_df is not None and df_15m is not None:
    # Core calculations across models
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.5)
    
    total_vol = bids_df['Volume'].sum() + asks_df['Volume'].sum()
    st.session_state.vol_history.append(total_vol)
    if len(st.session_state.vol_history) > 15:
        st.session_state.vol_history.pop(0)
    
    hawkes = calculate_hawkes_intensity(st.session_state.vol_history)
    p_long, p_short = calculate_sigmoid_probability(vw_obi, k=3.5)
    
    # 15M Market Structure & Transition Analysis
    recent_highs = df_15m['High'].iloc[-15:-1].max()
    recent_lows = df_15m['Low'].iloc[-15:-1].min()
    current_close = df_15m['Close'].iloc[-1]
    prev_close = df_15m['Close'].iloc[-2]
    
    structure_bullish_break = current_close > recent_highs
    structure_bearish_break = current_close < recent_lows
    
    # Explicit Shifts:
    # Buyer to Seller Shift (Bearish / Dump setup)
    buyer_to_seller_shift = (prev_close > df_15m['Open'].iloc[-2]) and (current_close < df_15m['Open'].iloc[-1])
    # Seller to Buyer Shift (Bullish / Pump setup)
    seller_to_buyer_shift = (prev_close < df_15m['Open'].iloc[-2]) and (current_close > df_15m['Open'].iloc[-1])

    # Dashboard Metrics Layout
    st.subheader("🚀 MEXC Balanced Multi-Model Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VW-OBI", f"{vw_obi:.4f}")
    c2.metric("LOAF Value", f"{loaf_val:.2f}")
    c3.metric("Hawkes Intensity", f"{hawkes:.2f}")
    c4.metric("15M Close Price", f"${current_close:,.2f}")
    
    st.subheader("📊 Probabilities & 15M Key Levels")
    p1, p2, r1, r2 = st.columns(4)
    p1.metric("P(Long)", f"{p_long*100:.1f}%")
    p2.metric("P(Short)", f"{p_short*100:.1f}%")
    r1.metric("15M Swing Resistance", f"${recent_highs:,.2f}")
    r2.metric("15M Swing Support", f"${recent_lows:,.2f}")
    
    # Synchronized Signal Execution with Correct Directional Shifts
    st.subheader("🎯 Synchronized Signal Execution")
    
    long_signal = (p_long > 0.70) and (hawkes > 10.0) and (loaf_val > 5.0) and (structure_bullish_break or seller_to_buyer_shift)
    short_signal = (p_short > 0.70) and (hawkes > 10.0) and (loaf_val < -5.0) and (structure_bearish_break or buyer_to_seller_shift)
    
    if long_signal:
        st.success("🟢 **BALANCED LONG SETUP:** Seller-to-Buyer Shift Confirmed with Prob > 70%, Hawkes > 10, & LOAF > 5!")
    elif short_signal:
        st.error("🔴 **BALANCED SHORT SETUP:** Buyer-to-Seller Shift (Dump) Confirmed with Prob > 70%, Hawkes > 10, & LOAF < -5!")
    else:
        st.warning("⚪ **MEDIATING ZONE:** Waiting for clear directional shift (Seller-to-Buyer for Long / Buyer-to-Seller for Short).")
        
    # Order Book View
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning("Connecting to MEXC Live API & 15M Candlestick Data...")
