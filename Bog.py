import streamlit as st
import pandas as pd
import numpy as np
import requests

st.title("MEXC LOB Ultimate Stochastic & Hawkes Dashboard")

# 1. Live MEXC Data Fetching Function
def fetch_mexc_live_orderbook(symbol="BTCUSDT", limit=10):
    url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if "bids" in data and "asks" in data:
            bids = data.get("bids", []) 
            asks = data.get("asks", [])
            
            bids_df = pd.DataFrame(bids, columns=['Price', 'Volume']).astype(float)
            asks_df = pd.DataFrame(asks, columns=['Price', 'Volume']).astype(float)
            
            return bids_df, asks_df
        else:
            st.error(f"API Response Error: {data}")
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
            
            if (v_bid + v_ask) > 0:
                imb = (v_bid - v_ask) / (v_bid + v_ask)
            else:
                imb = 0.0
            imbalance_data.append({'Level': level, 'Imbalance': imb})
            
    return pd.DataFrame(imbalance_data)

# 3. Hawkes Process Self-Exciting Intensity Formula Implementation
def calculate_hawkes_intensity(volume_history, alpha=0.4, beta=0.8):
    """
    Lambda_t(t) = lambda_0 + sum( alpha * exp(-beta * dt) )
    """
    if not volume_history or len(volume_history) < 2:
        return float(np.mean(volume_history)) if volume_history else 0.0
        
    baseline_lambda = float(np.mean(volume_history))
    excitement = 0.0
    
    # Simulating decay over recent events
    n = len(volume_history)
    for i, v in enumerate(volume_history):
        dt = n - i  # time difference proxy
        excitement += v * alpha * np.exp(-beta * dt)
        
    total_intensity = baseline_lambda + excitement
    return total_intensity

# 4. Realized Volatility Calculation
def calculate_realized_volatility(bids_df, asks_df):
    prices = pd.concat([bids_df['Price'], asks_df['Price']]).sort_values().values
    if len(prices) < 2:
        return 0.0
    log_returns = np.log(prices[1:] / prices[:-1])
    rv = np.sqrt(np.sum(log_returns ** 2))
    return rv

# Session States for tracking history
if 'vol_history' not in st.session_state:
    st.session_state.vol_history = []

# 5. UI Dashboard Logic
st.write("Running Ultimate Order Book Dynamics & Hawkes Intensity Model...")
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)

if bids_df is not None and asks_df is not None:
    imb_df = calculate_multi_level_imbalance(bids_df, asks_df, max_levels=5)
    avg_imb = imb_df['Imbalance'].mean()
    rv_value = calculate_realized_volatility(bids_df, asks_df)
    
    # Update volume history for Hawkes Intensity
    current_total_vol = bids_df['Volume'].sum() + asks_df['Volume'].sum()
    st.session_state.vol_history.append(current_total_vol)
    if len(st.session_state.vol_history) > 15:
        st.session_state.vol_history.pop(0)
        
    hawkes_intensity = calculate_hawkes_intensity(st.session_state.vol_history)
    
    st.subheader("📊 Advanced Quantitative Metrics")
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric(label="LOB Imbalance (Top 5)", value=f"{avg_imb:.4f}")
    with col_m2:
        st.metric(label="Realized Volatility ($RV_\\alpha$)", value=f"{rv_value:.6f}")
    with col_m3:
        st.metric(label="Hawkes Intensity ($\\lambda_t$)", value=f"{hawkes_intensity:.2f}")
    
    # Scalping Signal Execution based on Hawkes Intensity + Imbalance
    st.subheader("🎯 Ultimate Trade Signal Execution:")
    if avg_imb >= 0.35 and hawkes_intensity > np.mean(st.session_state.vol_history):
        st.success("🟢 **STRONG LONG (BUY) SETUP:** High buy imbalance coupled with self-exciting order flow surge.")
    elif avg_imb <= -0.35 and hawkes_intensity > np.mean(st.session_state.vol_history):
        st.error("🔴 **STRONG SHORT (SELL) SETUP:** High sell imbalance coupled with self-exciting order flow surge.")
    else:
        st.warning("⚪ **NEUTRAL ZONE:** Monitoring order flow intensity for breakout.")
        
    # Order Book Tables side-by-side
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning("Waiting for live market data...")
