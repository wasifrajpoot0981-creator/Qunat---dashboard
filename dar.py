import requests
import numpy as np
import pandas as pd
import streamlit as st

st.title("MEXC Multi-Model Dashboard (Adaptive Dynamic Levels Engine)")

# 1. Live MEXC Order Book Fetching
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

# 2. 15M Candlestick Data
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

# 5. Hawkes Process Intensity
def calculate_15m_hawkes_intensity(volume_series, alpha=0.5, beta=0.8):
    if len(volume_series) < 2:
        return float(volume_series.mean()) if not volume_series.empty else 0.0
    baseline = float(volume_series.mean())
    vol_list = volume_series.tolist()
    excitement = sum([v * alpha * np.exp(-beta * (len(vol_list) - i)) for i, v in enumerate(vol_list)])
    return baseline + excitement

# 6. Logistic Sigmoid Probability Mapping
def calculate_sigmoid_probability(vw_obi, k=3.5):
    p_long = 1.0 / (1.0 + np.exp(-k * vw_obi))
    p_short = 1.0 - p_long
    return p_long, p_short

# 7. GARCH(1,1) Conditional Variance Model
def calculate_garch_volatility(prices, omega=1e-5, alpha=0.15, beta=0.80):
    returns = prices.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    variance = np.zeros(len(returns))
    variance[0] = returns.var()
    for t in range(1, len(returns)):
        variance[t] = omega + alpha * (returns.iloc[t-1]**2) + beta * variance[t-1]
    return np.sqrt(variance[-1]) * 100

# 8. Adaptive Next-Level Shift Identifier
def calculate_adaptive_next_levels(df_15m, window=8, atr_mult=1.5):
    df = df_15m.copy()
    
    # ATR Calculation
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    base_res = df['High'].rolling(window=window).max().iloc[-2]
    base_sup = df['Low'].rolling(window=window).min().iloc[-2]
    
    current_close = df['Close'].iloc[-1]
    current_atr = df['atr'].iloc[-1] if not np.isnan(df['atr'].iloc[-1]) else 20.0
    
    # Level Breakout & Shift Logic
    if current_close > base_res:
        # Resistance broken! Shift to NEXT upper target level
        support_level = base_res
        resistance_level = current_close + (current_atr * atr_mult)
        breakout_status = "BULLISH BREAKOUT (Next Target Active)"
    elif current_close < base_sup:
        # Support broken! Shift to NEXT lower target level
        support_level = current_close - (current_atr * atr_mult)
        resistance_level = base_sup
        breakout_status = "BEARISH BREAKDOWN (Next Target Active)"
    else:
        support_level = base_sup
        resistance_level = base_res
        breakout_status = "RANGE BOUND"
        
    return support_level, resistance_level, breakout_status

# Session State for OBI Delta
if 'prev_obi' not in st.session_state:
    st.session_state.prev_obi = 0.0

# Fetch Data
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)
df_15m = fetch_15m_market_structure("BTCUSDT")

if bids_df is not None and asks_df is not None and df_15m is not None:
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.5)
    hawkes_15m = calculate_15m_hawkes_intensity(df_15m['Volume'])
    garch_vol = calculate_garch_volatility(df_15m['Close'])
    
    p_long, p_short = calculate_sigmoid_probability(vw_obi, k=3.5)
    obi_delta = vw_obi - st.session_state.prev_obi
    st.session_state.prev_obi = vw_obi
    
    support_level, resistance_level, breakout_status = calculate_adaptive_next_levels(df_15m)
    current_close = df_15m['Close'].iloc[-1]
    
    st.subheader("🚀 MEXC Dashboard (Next-Level Adaptive Engine)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VW-OBI", f"{vw_obi:.4f}")
    c2.metric("GARCH Volatility", f"{garch_vol:.3f}%")
    c3.metric("15M Hawkes", f"{hawkes_15m:,.1f}")
    c4.metric("LOAF Value", f"{loaf_val:.2f}")
    
    st.subheader("📊 Dynamic Levels & Structure")
    p1, p2, l1, l2 = st.columns(4)
    p1.metric("P(Long)", f"{p_long*100:.1f}%")
    p2.metric("P(Short)", f"{p_short*100:.1f}%")
    l1.metric("Adaptive Support", f"${support_level:,.2f}")
    l2.metric("Next Resistance Target", f"${resistance_level:,.2f}")
    
    st.info(f"📍 **Level Status:** {breakout_status}")
    
    # Synchronized Execution Signals
    st.subheader("🎯 Execution Signals")
    
    long_condition = (p_long > 0.70) and (obi_delta > 0.03) and (loaf_val > 3.0) and (garch_vol > 0.05)
    short_condition = (p_short > 0.70) and (obi_delta < -0.03) and (loaf_val < -3.0) and (garch_vol > 0.05)
    
    if long_condition:
        st.success("🟢 **HIGH-CONFIDENCE LONG SETUP:** Next-Level Target Shift + Momentum Confirmed!")
    elif short_condition:
        st.error("🔴 **HIGH-CONFIDENCE SHORT SETUP:** Downward Level Shift + Seller Pressure Confirmed!")
    else:
        st.warning("⚪ **WAITING ZONE:** Monitoring order book delta and next level targets.")
        
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning("⚠️ Connecting to MEXC API & Updating Dynamic Levels...")
