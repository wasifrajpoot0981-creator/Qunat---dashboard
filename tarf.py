import requests
import numpy as np
import pandas as pd
import streamlit as st

st.title("MEXC Order Book Level-Triggered Mega-Quant Dashboard")

# 1. Live MEXC Order Book Fetching
def fetch_mexc_live_orderbook(symbol="BTCUSDT", limit=20):
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

# 2. 15M Candlestick Data (For GARCH and Volume Trend)
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

# 5. Logistic Sigmoid Probability Mapping Model
def calculate_sigmoid_probability(vw_obi, k=3.5):
    p_long = 1.0 / (1.0 + np.exp(-k * vw_obi))
    p_short = 1.0 - p_long
    return p_long, p_short

# 6. GARCH(1,1) Conditional Variance Model
def calculate_garch_volatility(prices, omega=1e-5, alpha=0.15, beta=0.80):
    returns = prices.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    variance = np.zeros(len(returns))
    variance[0] = returns.var()
    for t in range(1, len(returns)):
        variance[t] = omega + alpha * (returns.iloc[t-1]**2) + beta * variance[t-1]
    return np.sqrt(variance[-1]) * 100

# 7. Self-Exciting Hawkes Jump Model
def calculate_hawkes_jump_intensity(current_pressure, history_list, alpha=0.8, beta=0.5):
    mu = 0.5 
    excitation = 0.0
    for i, past_pressure in enumerate(reversed(history_list)):
        time_decay = np.exp(-beta * (i + 1))
        excitation += alpha * past_pressure * time_decay
    history_list.append(current_pressure)
    if len(history_list) > 10:
        history_list.pop(0)
    return mu + excitation

# 8. Micro-Price Equation[cite: 1]
def calculate_micro_price(bids_df, asks_df):
    if bids_df.empty or asks_df.empty:
        return 0.0
    Pb = bids_df.iloc[0]['Price']
    Vb = bids_df.iloc[0]['Volume']
    Pa = asks_df.iloc[0]['Price']
    Va = asks_df.iloc[0]['Volume']
    denominator = Vb + Va
    if denominator == 0:
        return (Pb + Pa) / 2.0
    return ((Vb * Pa) + (Va * Pb)) / denominator

# 9. Bid Floor Exhaustion (Void Level)[cite: 2]
def check_bid_floor_exhaustion(bids_df, k=1.5):
    if len(bids_df) < 2:
        return False
    mu_v = bids_df['Volume'].mean()
    sigma_v = bids_df['Volume'].std()
    if pd.isna(sigma_v) or sigma_v == 0:
        sigma_v = 0.01
    return (bids_df['Volume'] > (mu_v + k * sigma_v)).any()

# 10. Anomalous Ask Volume Cumulative Filter (Liquidity Wall)[cite: 3]
def check_anomalous_ask_volume(asks_df, k=1.5):
    if len(asks_df) < 2:
        return False
    mu_v = asks_df['Volume'].mean()
    sigma_v = asks_df['Volume'].std()
    if pd.isna(sigma_v) or sigma_v == 0:
        sigma_v = 0.01
    return (asks_df['Volume'] > (mu_v + k * sigma_v)).any()

# 11. Order Book Based Support & Resistance Level Identifier
def calculate_orderbook_levels(bids_df, asks_df):
    if bids_df.empty or asks_df.empty:
        return 0.0, 0.0
    # Support = Bid price with maximum volume cluster in order book
    max_bid_idx = bids_df['Volume'].idxmax()
    support_level = bids_df.loc[max_bid_idx, 'Price']
    
    # Resistance = Ask price with maximum volume cluster in order book
    max_ask_idx = asks_df['Volume'].idxmax()
    resistance_level = asks_df.loc[max_ask_idx, 'Price']
    
    return support_level, resistance_level

# Session States
if 'prev_obi' not in st.session_state:
    st.session_state.prev_obi = 0.0
if 'prev_loaf' not in st.session_state:
    st.session_state.prev_loaf = 0.0
if 'pressure_history' not in st.session_state:
    st.session_state.pressure_history = []

# Fetch Data with deeper order book limit for accurate level mapping
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 20)
df_15m = fetch_15m_market_structure("BTCUSDT")

if bids_df is not None and asks_df is not None and df_15m is not None:
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.5)
    garch_vol = calculate_garch_volatility(df_15m['Close'])
    p_long, p_short = calculate_sigmoid_probability(vw_obi, k=3.5)
    
    micro_price = calculate_micro_price(bids_df, asks_df)
    bid_exhaustion = check_bid_floor_exhaustion(bids_df)
    ask_wall = check_anomalous_ask_volume(asks_df)
    
    obi_delta = vw_obi - st.session_state.prev_obi
    loaf_delta = loaf_val - st.session_state.prev_loaf
    
    current_pressure = abs(obi_delta * 100) + abs(loaf_delta)
    jump_intensity = calculate_hawkes_jump_intensity(current_pressure, st.session_state.pressure_history)
    
    st.session_state.prev_obi = vw_obi
    st.session_state.prev_loaf = loaf_val
    
    # Extract levels directly from order book walls
    support_level, resistance_level = calculate_orderbook_levels(bids_df, asks_df)
    current_close = bids_df.iloc[0]['Price']  # Using top of order book price for immediate trigger
    
    avg_volume = df_15m['Volume'].rolling(window=5).mean().iloc[-1]
    current_volume = df_15m['Volume'].iloc[-1]
    is_valid_volume = current_volume >= (avg_volume * 0.8)
    
    st.subheader("🚀 MEXC Order Book Level-Driven Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Micro-Price", f"${micro_price:,.2f}")
    c2.metric("GARCH Volatility", f"{garch_vol:.3f}%")
    c3.metric("Hawkes Intensity", f"{jump_intensity:.2f}")
    c4.metric("VW-OBI Delta", f"{obi_delta:+.4f}")
    
    st.subheader("📊 Order Book Walls & Probabilities")
    p1, p2, l1, l2 = st.columns(4)
    p1.metric("P(Long)", f"{p_long*100:.1f}%")
    p2.metric("P(Short)", f"{p_short*100:.1f}%")
    l1.metric("Order Book Support", f"${support_level:,.2f}")
    l2.metric("Order Book Resistance", f"${resistance_level:,.2f}")
    
    st.info(f"💡 **Order Book Status:** Bid Void: `{bid_exhaustion}` | Anomalous Ask Wall: `{ask_wall}`")
    
    st.subheader("🎯 Execution Signals")
    
    at_support = (current_close >= support_level) and (current_close <= support_level * 1.002)
    at_resistance = (current_close <= resistance_level) and (current_close >= resistance_level * 0.998)
    
    long_condition = (
        (p_long > 0.70) and 
        (obi_delta > 0.02) and 
        (loaf_val > 2.0) and 
        (garch_vol > 0.02) and 
        (jump_intensity > 1.5) and 
        (micro_price > current_close) and
        at_support and 
        is_valid_volume
    )
    
    short_condition = (
        (p_short > 0.70) and 
        (obi_delta < -0.02) and 
        (loaf_val < -2.0) and 
        (garch_vol > 0.02) and 
        (jump_intensity > 1.5) and 
        (micro_price < current_close) and
        at_resistance and 
        is_valid_volume
    )
    
    if long_condition:
        st.success("🟢 **HIGH-CONFIDENCE LONG EXECUTION:** Order Book Support Wall + Full Consensus Confirmed!")
    elif short_condition:
        st.error("🔴 **HIGH-CONFIDENCE SHORT EXECUTION:** Order Book Resistance Wall + Full Consensus Confirmed!")
    else:
        st.warning("⚪ **WAITING ZONE:** Monitoring order book depth walls and quantitative indicators.")
        
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning("⚠️ Connecting to MEXC API & Fetching Order Book Depth...")
