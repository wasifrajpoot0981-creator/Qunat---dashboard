import streamlit as st
import pandas as pd
import numpy as np
import requests

st.title("MEXC Ultimate Multi-Model Dashboard with Kalman Filter")

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

# 2. Safe 15M Candlestick Data
def fetch_15m_market_structure(symbol="BTCUSDT"):
    url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval=15m&limit=30"
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

# 5. Hawkes Process Intensity based on 15M Candle Volumes
def calculate_15m_hawkes_intensity(volume_series, alpha=0.5, beta=0.8):
    if len(volume_series) < 2:
        return float(volume_series.mean()) if not volume_series.empty else 0.0
    baseline = float(volume_series.mean())
    vol_list = volume_series.tolist()
    excitement = sum([v * alpha * np.exp(-beta * (len(vol_list) - i)) for i, v in enumerate(vol_list)])
    return baseline + excitement

# 6. Logistic Sigmoid Probability Mapping Model
def calculate_sigmoid_probability(vw_obi, k=3.5):
    p_long = 1.0 / (1.0 + np.exp(-k * vw_obi))
    p_short = 1.0 - p_long
    return p_long, p_short

# 7. Kalman Filter Implementation (From your snippet)[cite: 4]
def apply_kalman_filter(prices, Q=0.01, R=1.0):
    x = prices.iloc[0]
    P = 1.0
    filtered_prices = []
    for price in prices:
        x_pred = x
        P_pred = P + Q
        K = P_pred / (P_pred + R)
        x = x_pred + K * (price - x_pred)
        P = (1 - K) * P_pred
        filtered_prices.append(x)
    return pd.Series(filtered_prices, index=prices.index)

# 8. Level Identifier & False Breakout Detector
def detect_false_breakouts(df_15m, vw_obi, obi_delta):
    df = df_15m.copy()
    df['resistance'] = df['High'].shift(1).rolling(window=5).max()
    df['support'] = df['Low'].shift(1).rolling(window=5).min()
    df['obi'] = vw_obi
    df['delta'] = obi_delta
    
    price_cond_short = df['High'].iloc[-1] > df['resistance'].iloc[-1]
    book_cond_short = df['obi'].iloc[-1] <= -0.10
    delta_cond_short = df['delta'].iloc[-1] < 0
    
    price_cond_long = df['Low'].iloc[-1] < df['support'].iloc[-1]
    book_cond_long = df['obi'].iloc[-1] >= 0.10
    delta_cond_long = df['delta'].iloc[-1] > 0
    
    false_breakout_short = price_cond_short and book_cond_short and delta_cond_short
    false_breakout_long = price_cond_long and book_cond_long and delta_cond_long
    
    return false_breakout_short, false_breakout_long, df['support'].iloc[-1], df['resistance'].iloc[-1]

# Session State for OBI Delta
if 'prev_obi' not in st.session_state:
    st.session_state.prev_obi = 0.0

# Fetch Data
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)
df_15m = fetch_15m_market_structure("BTCUSDT")

if bids_df is not None and asks_df is not None and df_15m is not None:
    # Apply Kalman Filter to Close Prices[cite: 4]
    df_15m['kalman_price'] = apply_kalman_filter(df_15m['Close'], Q=0.01, R=1.0)
    
    # Core Model Calculations
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.5)
    hawkes_15m = calculate_15m_hawkes_intensity(df_15m['Volume'])
    
    p_long, p_short = calculate_sigmoid_probability(vw_obi, k=3.5)
    obi_delta = vw_obi - st.session_state.prev_obi
    st.session_state.prev_obi = vw_obi
    
    fb_short, fb_long, support_level, resistance_level = detect_false_breakouts(df_15m, vw_obi, obi_delta)
    current_close = df_15m['Close'].iloc[-1]
    kalman_val = df_15m['kalman_price'].iloc[-1]
    
    # Dashboard Metrics Layout
    st.subheader("🚀 Ultimate Multi-Model Dashboard with Kalman Filter")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VW-OBI", f"{vw_obi:.4f}")
    c2.metric("Kalman Price", f"${kalman_val:,.2f}")
    c3.metric("15M Hawkes", f"{hawkes_15m:,.1f}")
    c4.metric("LOAF Value", f"{loaf_val:.2f}")
    
    st.subheader("📊 Probabilities & Bro Levels")
    p1, p2, l1, l2 = st.columns(4)
    p1.metric("P(Long)", f"{p_long*100:.1f}%")
    p2.metric("P(Short)", f"{p_short*100:.1f}%")
    l1.metric("Support Level", f"${support_level:,.2f}")
    l2.metric("Resistance Level", f"${resistance_level:,.2f}")
    
    # Synchronized Signal Execution
    st.subheader("🎯 Synchronized Execution Signals")
    
    long_condition = (p_long > 0.70) and (obi_delta > 0.03) and (loaf_val > 3.0) and (fb_long or current_close <= support_level * 1.003)
    short_condition = (p_short > 0.70) and (obi_delta < -0.03) and (loaf_val < -3.0) and (fb_short or current_close >= resistance_level * 0.997)
    
    if long_condition:
        st.success("🟢 **HIGH-CONFIDENCE LONG SETUP:** Kalman Trend + False Breakout Reversal Confirmed!")
    elif short_condition:
        st.error("🔴 **HIGH-CONFIDENCE SHORT SETUP:** Kalman Trend + Resistance Trap Confirmed!")
    else:
        st.warning("⚪ **WAITING ZONE:** Filtering noise with Kalman & monitoring order book flow.")
        
    # Order Book View
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning("⚠️ Connecting to MEXC API & Initializing Kalman Filter...")
