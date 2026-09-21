import streamlit as st
import pandas as pd
import numpy as np
import requests

st.title("MEXC LOB Quantitative Scalping Dashboard")

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

# 2. Multi-Level Imbalance Calculation
def calculate_multi_level_imbalance(bids_df, asks_df, max_levels=5):
    imbalance_data = []
    for level in range(1, max_levels + 1):
        if len(bids_df) >= level and len(asks_df) >= level:
            v_bid = bids_df.loc[level-1, 'Volume']
            v_ask = asks_df.loc[level-1, 'Volume']
            imb = (v_bid - v_ask) / (v_bid + v_ask) if (v_bid + v_ask) > 0 else 0.0
            imbalance_data.append({'Level': level, 'Imbalance': imb})
    return pd.DataFrame(imbalance_data)

# 3. Realized Volatility Calculation (RV_alpha)
def calculate_realized_volatility(bids_df, asks_df):
    prices = pd.concat([bids_df['Price'], asks_df['Price']]).sort_values().values
    if len(prices) < 2:
        return 0.0
    log_returns = np.log(prices[1:] / prices[:-1])
    return np.sqrt(np.sum(log_returns ** 2))

# 4. Hawkes Process Self-Exciting Intensity
def calculate_hawkes_intensity(volume_history, alpha=0.4, beta=0.8):
    if not volume_history or len(volume_history) < 2:
        return float(np.mean(volume_history)) if volume_history else 0.0
    baseline = float(np.mean(volume_history))
    excitement = sum([v * alpha * np.exp(-beta * (len(volume_history) - i)) for i, v in enumerate(volume_history)])
    return baseline + excitement

# 5. Mid-Price Transition Probability via Laplace Transform
def calculate_laplace_probability(avg_imb, intensity, baseline):
    factor = min(max(intensity / (baseline + 1e-8), 0.5), 2.0)
    return 1.0 / (1.0 + np.exp(-3.0 * avg_imb * factor))

# 6. LSTM-style Sequential Trend Prediction
def lstm_predict_signal(imb_history):
    if len(imb_history) < 3:
        return 0.0, "Neutral"
    weights = np.linspace(0.5, 1.0, len(imb_history))
    score = np.dot(imb_history, weights) / weights.sum()
    if score > 0.10:
        return score, "Bullish"
    elif score < -0.10:
        return score, "Bearish"
    return score, "Neutral"

# Session States for Rolling History
if 'vol_history' not in st.session_state:
    st.session_state.vol_history = []
if 'imb_history' not in st.session_state:
    st.session_state.imb_history = []

# Fetching Data
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)

if bids_df is not None and asks_df is not None:
    # Model Calculations
    imb_df = calculate_multi_level_imbalance(bids_df, asks_df, 5)
    avg_imb = imb_df['Imbalance'].mean()
    rv = calculate_realized_volatility(bids_df, asks_df)
    
    total_vol = bids_df['Volume'].sum() + asks_df['Volume'].sum()
    st.session_state.vol_history.append(total_vol)
    if len(st.session_state.vol_history) > 15:
        st.session_state.vol_history.pop(0)
        
    hawkes = calculate_hawkes_intensity(st.session_state.vol_history)
    baseline = np.mean(st.session_state.vol_history) if st.session_state.vol_history else 1.0
    laplace_prob = calculate_laplace_probability(avg_imb, hawkes, baseline)
    
    st.session_state.imb_history.append(avg_imb)
    if len(st.session_state.imb_history) > 10:
        st.session_state.imb_history.pop(0)
    lstm_score, lstm_dir = lstm_predict_signal(st.session_state.imb_history)
    
    # Dashboard Display Layout
    st.subheader("🚀 Live Quantitative Metrics Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("LOB Imbalance", f"{avg_imb:.4f}")
    c2.metric("Realized Vol", f"{rv:.5f}")
    c3.metric("Hawkes Intensity", f"{hawkes:.2f}")
    c4.metric("Laplace Up Prob", f"{laplace_prob*100:.1f}%")
    
    # Aggressive & Sensitive Scalping Signal Execution
    st.subheader("🎯 Master Scalping Signal Execution (Optimized)")
    if avg_imb > 0.15 or hawkes > (baseline * 1.05) or laplace_prob > 0.55:
        st.success("🟢 **STRONG LONG SETUP (Pump Detected):** Buying pressure or intensity spike captured!")
    elif avg_imb < -0.15 or laplace_prob < 0.45:
        st.error("🔴 **STRONG SHORT SETUP (Dump Detected):** Selling pressure or downward spike captured!")
    else:
        st.warning(f"⚪ **NEUTRAL ZONE:** Market consolidating. Current Trend: {lstm_dir}")
        
    # Order Book DataFrames View
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning("Connecting to MEXC Live Order Book...")
