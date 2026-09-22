import streamlit as st
import pandas as pd
import numpy as np
import requests

st.title("MEXC 15M Filtered & Optimized Dashboard")

# 1. Live MEXC Data Fetching Function
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
        st.error(f"Connection Error: {e}")
        return None, None

# 2. Volume Weighted Order Book Imbalance (VW-OBI) Calculation
def calculate_vw_obi(bids_df, asks_df, max_levels=5):
    num_levels = min(len(bids_df), len(asks_df), max_levels)
    if num_levels == 0:
        return 0.0
    
    weighted_bid_sum = 0.0
    weighted_ask_sum = 0.0
    
    for i in range(1, num_levels + 1):
        w_i = 1.0 / i  
        v_b = bids_df.loc[i-1, 'Volume']
        v_a = asks_df.loc[i-1, 'Volume']
        weighted_bid_sum += w_i * v_b
        weighted_ask_sum += w_i * v_a
        
    denominator = weighted_bid_sum + weighted_ask_sum
    if denominator == 0:
        return 0.0
    return (weighted_bid_sum - weighted_ask_sum) / denominator

# 3. Large Order Aggressor Flow (LOAF)
def calculate_loaf(bids_df, asks_df, theta=1.5):
    large_bids = bids_df[bids_df['Volume'] > theta]['Volume'].sum()
    large_asks = asks_df[asks_df['Volume'] > theta]['Volume'].sum()
    return large_bids - large_asks

# 4. Hawkes Process Self-Exciting Intensity
def calculate_hawkes_intensity(volume_history, alpha=0.5, beta=0.8):
    if not volume_history or len(volume_history) < 2:
        return float(np.mean(volume_history)) if volume_history else 0.0
    baseline = float(np.mean(volume_history))
    excitement = sum([v * alpha * np.exp(-beta * (len(volume_history) - i)) for i, v in enumerate(volume_history)])
    return baseline + excitement

# 5. LSTM-style Sequential Trend Prediction (Moderate Intensity Weights)
def lstm_predict_signal(obi_history):
    if len(obi_history) < 3:
        return 0.0, "Neutral"
    weights = np.linspace(0.7, 1.0, len(obi_history))
    score = np.dot(obi_history, weights) / weights.sum()
    if score > 0.90:
        return score, "Trend Buy"
    elif score < -0.90:
        return score, "Trend Sell"
    return score, "Neutral"

# 6. Logistic Sigmoid Probability Mapping
def calculate_sigmoid_probability(vw_obi, k=3.5):
    p_long = 1.0 / (1.0 + np.exp(-k * vw_obi))
    p_short = 1.0 - p_long
    return p_long, p_short

# 7. Reaction Levels Identifier
def analyze_reaction_levels(bids_df, asks_df, max_levels=5):
    max_bid_idx = bids_df.head(max_levels)['Volume'].idxmax()
    max_ask_idx = asks_df.head(max_levels)['Volume'].idxmax()
    return bids_df.loc[max_bid_idx, 'Price'], asks_df.loc[max_ask_idx, 'Price']

# 8. ABE (Adaptive Box Envelope / Volatility Bands) Calculation
def calculate_abe(bids_df, asks_df, multiplier=1.5):
    mid_price = (bids_df.loc[0, 'Price'] + asks_df.loc[0, 'Price']) / 2.0
    spread = asks_df.loc[0, 'Price'] - bids_df.loc[0, 'Price']
    upper_band = mid_price + (spread * multiplier)
    lower_band = mid_price - (spread * multiplier)
    return lower_band, mid_price, upper_band

# Session States for Rolling History
if 'vol_history' not in st.session_state:
    st.session_state.vol_history = []
if 'obi_history' not in st.session_state:
    st.session_state.obi_history = []

# Fetching Data
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)

if bids_df is not None and asks_df is not None:
    # Model Calculations
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.5)
    
    total_vol = bids_df['Volume'].sum() + asks_df['Volume'].sum()
    st.session_state.vol_history.append(total_vol)
    if len(st.session_state.vol_history) > 15:
        st.session_state.vol_history.pop(0)
    
    hawkes = calculate_hawkes_intensity(st.session_state.vol_history)
    
    st.session_state.obi_history.append(vw_obi)
    if len(st.session_state.obi_history) > 10:
        st.session_state.obi_history.pop(0)
    lstm_score, lstm_dir = lstm_predict_signal(st.session_state.obi_history)
    
    p_long, p_short = calculate_sigmoid_probability(vw_obi, k=3.5)
    strong_bid_lvl, strong_ask_lvl = analyze_reaction_levels(bids_df, asks_df, 5)
    
    # ABE Calculation & Mid Price
    lower_abe, mid_price, upper_abe = calculate_abe(bids_df, asks_df, multiplier=1.5)
    
    # Price proximity check for Support and Resistance
    # Checking if mid price is near Support level (within 0.3% range) or Resistance level
    is_at_support = abs(mid_price - strong_bid_lvl) / strong_bid_lvl <= 0.003
    is_at_resistance = abs(mid_price - strong_ask_lvl) / strong_ask_lvl <= 0.003
    
    # Dashboard Display Layout
    st.subheader("🚀 Optimized Quantitative Metrics Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VW-OBI", f"{vw_obi:.4f}")
    c2.metric("LOAF Value", f"{loaf_val:.2f}")
    c3.metric("Hawkes Intensity", f"{hawkes:.2f}")
    c4.metric("LSTM Trend", f"{lstm_score:.4f} ({lstm_dir})")
    
    st.subheader("📊 Probability & Key Reaction Levels")
    p1, p2, r1, r2 = st.columns(4)
    p1.metric("P(Long)", f"{p_long*100:.1f}%")
    p2.metric("P(Short)", f"{p_short*100:.1f}%")
    r1.metric("Support Level", f"${strong_bid_lvl:,.2f}")
    r2.metric("Resistance Level", f"${strong_ask_lvl:,.2f}")
    
    st.subheader("📦 Adaptive Box Envelope (ABE) Bands")
    a1, a2, a3 = st.columns(3)
    a1.metric("ABE Lower Band", f"${lower_abe:,.2f}")
    a2.metric("Mid Price", f"${mid_price:,.2f}")
    a3.metric("ABE Upper Band", f"${upper_abe:,.2f}")
    
    # Filter Signal Execution based on User Conditions:
    # Probability > 70% (0.70), Hawkes > 10, LOAF > 5 (for long) or < -5 (for short), Price at Support/Resistance
    st.subheader("🎯 Filtered Signal Execution")
    
    long_condition = (p_long > 0.70) and (hawkes > 10.0) and (loaf_val > 5.0) and is_at_support
    short_condition = (p_short > 0.70) and (hawkes > 10.0) and (loaf_val < -5.0) and is_at_resistance
    
    if long_condition:
        st.success("🟢 **HIGH-CONFIDENCE LONG SETUP:** P(Long) > 70%, Hawkes > 10, LOAF > 5, and Price is at Support Level!")
    elif short_condition:
        st.error("🔴 **HIGH-CONFIDENCE SHORT SETUP:** P(Short) > 70%, Hawkes > 10, LOAF < -5, and Price is at Resistance Level!")
    else:
        st.warning(f"⚪ **FILTERED ZONE:** Waiting for exact conditions (P > 70%, Hawkes > 10, LOAF > 5 or < -5, Price at Support/Resistance).")
        
    # Order Book DataFrames View
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids (Support)")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks (Resistance)")
        st.dataframe(asks_df.head(5))
else:
    st.warning("Connecting to MEXC Live Order Book...")
