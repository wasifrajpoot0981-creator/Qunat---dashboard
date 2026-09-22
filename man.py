import requests
import numpy as np
import pandas as pd
import streamlit as st

st.title("MEXC Multi-Coin 1M Dashboard (1M Scalping)")

symbol = st.selectbox("Select Trading Pair", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"], index=0)

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

def fetch_1m_market_structure(symbol="BTCUSDT"):
    url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval=1m&limit=30"
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

def calculate_loaf(bids_df, asks_df, theta=1.5):
    large_bids = bids_df[bids_df['Volume'] > theta]['Volume'].sum()
    large_asks = asks_df[asks_df['Volume'] > theta]['Volume'].sum()
    return large_bids - large_asks

def calculate_sigmoid_probability(vw_obi, k=3.5):
    p_long = 1.0 / (1.0 + np.exp(-k * vw_obi))
    p_short = 1.0 - p_long
    return p_long, p_short

def calculate_garch_volatility(prices, omega=1e-5, alpha=0.15, beta=0.80):
    returns = prices.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    variance = np.zeros(len(returns))
    variance[0] = returns.var()
    for t in range(1, len(returns)):
        variance[t] = omega + alpha * (returns.iloc[t-1]**2) + beta * variance[t-1]
    return np.sqrt(variance[-1]) * 100

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

def check_bid_floor_exhaustion(bids_df, k=1.5):
    if len(bids_df) < 2:
        return False
    mu_v = bids_df['Volume'].mean()
    sigma_v = bids_df['Volume'].std()
    if pd.isna(sigma_v) or sigma_v == 0:
        sigma_v = 0.01
    return (bids_df['Volume'] > (mu_v + k * sigma_v)).any()

def check_anomalous_ask_volume(asks_df, k=1.5):
    if len(asks_df) < 2:
        return False
    mu_v = asks_df['Volume'].mean()
    sigma_v = asks_df['Volume'].std()
    if pd.isna(sigma_v) or sigma_v == 0:
        sigma_v = 0.01
    return (asks_df['Volume'] > (mu_v + k * sigma_v)).any()

def calculate_orderbook_levels(bids_df, asks_df):
    if bids_df.empty or asks_df.empty:
        return 0.0, 0.0
    max_bid_idx = bids_df['Volume'].idxmax()
    support_level = bids_df.loc[max_bid_idx, 'Price']
    
    max_ask_idx = asks_df['Volume'].idxmax()
    resistance_level = asks_df.loc[max_ask_idx, 'Price']
    
    return support_level, resistance_level

def calculate_vpin(bids_df, asks_df):
    if bids_df.empty or asks_df.empty:
        return 0.0
    vb = bids_df['Volume'].values
    vs = asks_df['Volume'].values
    min_len = min(len(vb), len(vs))
    if min_len == 0:
        return 0.0
    num_sum = np.sum(np.abs(vb[:min_len] - vs[:min_len]))
    total_vol = np.sum(vb[:min_len] + vs[:min_len])
    if total_vol == 0:
        return 0.0
    return num_sum / total_vol

def calculate_slippage_cost(bids_df, asks_df):
    if bids_df.empty or asks_df.empty:
        return 0.0
    delta_p = abs(asks_df.iloc[0]['Price'] - bids_df.iloc[0]['Price'])
    market_order_volume = asks_df['Volume'].iloc[0] + bids_df['Volume'].iloc[0]
    if market_order_volume == 0:
        return 0.0
    return delta_p / market_order_volume

if 'prev_obi' not in st.session_state:
    st.session_state.prev_obi = 0.0
if 'prev_loaf' not in st.session_state:
    st.session_state.prev_loaf = 0.0
if 'pressure_history' not in st.session_state:
    st.session_state.pressure_history = []

bids_df, asks_df = fetch_mexc_live_orderbook(symbol, 20)
df_1m = fetch_1m_market_structure(symbol)

if bids_df is not None and asks_df is not None and df_1m is not None:
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.5)
    garch_vol = calculate_garch_volatility(df_1m['Close'])
    p_long, p_short = calculate_sigmoid_probability(vw_obi, k=3.5)
    
    micro_price = calculate_micro_price(bids_df, asks_df)
    bid_exhaustion = check_bid_floor_exhaustion(bids_df)
    ask_wall = check_anomalous_ask_volume(asks_df)
    
    vpin_val = calculate_vpin(bids_df, asks_df)
    slippage_cost = calculate_slippage_cost(bids_df, asks_df)
    
    obi_delta = vw_obi - st.session_state.prev_obi
    loaf_delta = loaf_val - st.session_state.prev_loaf
    
    current_pressure = abs(obi_delta * 100) + abs(loaf_delta)
    jump_intensity = calculate_hawkes_jump_intensity(current_pressure, st.session_state.pressure_history)
    
    st.session_state.prev_obi = vw_obi
    st.session_state.prev_loaf = loaf_val
    
    support_level, resistance_level = calculate_orderbook_levels(bids_df, asks_df)
    current_close = bids_df.iloc[0]['Price']
    
    st.subheader(f"🚀 MEXC Multi-Coin 1M Dashboard — {symbol}")
    
    # Updated metrics layout to display LOAF clearly right at the top
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Micro-Price", f"${micro_price:,.4f}")
    c2.metric("LOAF Flow", f"{loaf_val:+,.2f}")
    c3.metric("GARCH Vol (1M)", f"{garch_vol:.3f}%")
    c4.metric("VPIN Toxicity", f"{vpin_val:.3f}")
    c5.metric("Slippage Cost", f"{slippage_cost:.6f}")
    
    st.subheader("📊 Order Book Walls & Probabilities")
    p1, p2, l1, l2 = st.columns(4)
    p1.metric("P(Long)", f"{p_long*100:.1f}%")
    p2.metric("P(Short)", f"{p_short*100:.1f}%")
    l1.metric("Order Book Support", f"${support_level:,.4f}")
    l2.metric("Order Book Resistance", f"${resistance_level:,.4f}")
    
    st.info(f"💡 **Order Book Status:** Bid Void: `{bid_exhaustion}` | Anomalous Ask Wall: `{ask_wall}` | Current LOAF: `{loaf_val:,.2f}`")
    
    st.subheader("🎯 1M Scalping Execution Signals (Filtered)")
    
    at_support = (current_close >= support_level) and (current_close <= support_level * 1.001)
    at_resistance = (current_close <= resistance_level) and (current_close >= resistance_level * 0.999)
    
    medium_intensity = (jump_intensity >= 1.0) and (jump_intensity <= 3.0) and (garch_vol >= 0.01)
    valid_real_book = (slippage_cost > 0.000001)
    
    short_condition = (
        at_resistance and 
        (loaf_val < -3.0) and 
        (p_short > p_long) and 
        (vw_obi < 0 or obi_delta < 0) and
        (vpin_val > 0.1) and
        medium_intensity and
        valid_real_book
    )
    
    long_condition = (
        at_support and 
        (loaf_val > 3.0) and 
        (p_long > p_short) and 
        (vw_obi > 0 or obi_delta > 0) and
        (vpin_val > 0.1) and
        medium_intensity and
        valid_real_book
    )
    
    if long_condition:
        st.success(f"🟢 **1M HIGH-CONFIDENCE LONG EXECUTION ({symbol}):** Support Reached + LOAF > 3.0 + 1M Volatility Confirmed!")
    elif short_condition:
        st.error(f"🔴 **1M HIGH-CONFIDENCE SHORT EXECUTION ({symbol}):** Resistance Reached + LOAF < -3.0 + 1M Volatility Confirmed!")
    else:
        st.warning(f"⚪ **1M WAITING ZONE ({symbol}):** Monitoring live 1-minute order flow, LOAF, and volatility...")
        
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning(f"⚠️ Connecting to MEXC API & Fetching Live 1M Data for {symbol}...")
