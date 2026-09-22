import time
import requests
import numpy as np
import pandas as pd
import streamlit as st

st.title("MEXC Multi-Coin 1M High-Wall Momentum Engine — Complete Setup")

symbol = st.selectbox("Select Trading Pair", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"], index=0)

# --- MASTER QUANT FORMULA ---
def calculate_master_quant_score(bids_df, asks_df, delta_cvd, cancellation_ratio=0.2, K=5):
    if bids_df.empty or asks_df.empty:
        return 0.0
    num_levels = min(len(bids_df), len(asks_df), K)
    bid_sum = sum((float(i + 1) * bids_df.loc[i, 'Volume']) for i in range(num_levels))
    ask_sum = sum((float(i + 1) * asks_df.loc[i, 'Volume']) for i in range(num_levels))
    denominator = bid_sum + ask_sum
    if denominator == 0:
        return 0.0
    return (delta_cvd / denominator) * (1.0 - cancellation_ratio)

# --- P_REAL AUTHENTICITY FORMULA ---
def calculate_order_authenticity_probability(age_sec, distance_val, fill_ratio, beta_0=-1.5, beta_1=0.1, beta_2=-0.5, beta_3=1.2):
    exponent = -(beta_0 + (beta_1 * age_sec) + (beta_2 * distance_val) + (beta_3 * fill_ratio))
    exponent = np.clip(exponent, -50, 50)
    return 1.0 / (1.0 + np.exp(exponent))

# --- OTR FORMULA ---
def calculate_otr(v_placed, v_canceled, v_executed, eps=1e-9):
    return (v_placed + v_canceled) / (v_executed + eps)

# --- SLIPPAGE FORMULA ---
def calculate_estimated_slippage(bids_df, asks_df, target_volume=1.0):
    if bids_df.empty or asks_df.empty: return 0.0
    spread = asks_df.iloc[0]['Price'] - bids_df.iloc[0]['Price']
    avg_vol = (bids_df['Volume'].mean() + asks_df['Volume'].mean()) / 2.0
    if avg_vol == 0: return 0.0
    return (target_volume / avg_vol) * spread

# --- MULTI-SCALE HAWKES PROCESS FORMULA ---
def calculate_hawkes_process(current_pressure, history_list, mu=0.4, alpha=0.6, beta=0.6):
    excitation = sum(alpha * past_pressure * np.exp(-beta * (i + 1)) for i, past_pressure in enumerate(reversed(history_list)))
    lambda_t = mu + excitation
    history_list.append(current_pressure)
    if len(history_list) > 10:
        history_list.pop(0)
    return lambda_t

# --- LOAF (LARGE ORDER IMBALANCE) FORMULA ---
def calculate_loaf(bids_df, asks_df, theta=1.0):
    if bids_df.empty or asks_df.empty:
        return 0.0
    large_bids = bids_df[bids_df['Volume'] > theta]['Volume'].sum()
    large_asks = asks_df[asks_df['Volume'] > theta]['Volume'].sum()
    return large_bids - large_asks

def fetch_mexc_live_orderbook(symbol="BTCUSDT", limit=30):
    url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if "bids" in data and "asks" in data:
            return pd.DataFrame(data.get("bids", []), columns=['Price', 'Volume']).astype(float), pd.DataFrame(data.get("asks", []), columns=['Price', 'Volume']).astype(float)
        return None, None
    except:
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
    except:
        return None

def calculate_vw_obi(bids_df, asks_df, max_levels=5):
    num_levels = min(len(bids_df), len(asks_df), max_levels)
    if num_levels == 0: return 0.0
    weighted_bid_sum = sum((1.0 / i) * bids_df.loc[i-1, 'Volume'] for i in range(1, num_levels + 1))
    weighted_ask_sum = sum((1.0 / i) * asks_df.loc[i-1, 'Volume'] for i in range(1, num_levels + 1))
    denominator = weighted_bid_sum + weighted_ask_sum
    return (weighted_bid_sum - weighted_ask_sum) / denominator if denominator > 0 else 0.0

def extract_high_walls_support_resistance(bids_df, asks_df):
    if bids_df.empty or asks_df.empty: return 0.0, 0.0, 0.0, 0.0

    v_placed_b = bids_df['Volume'].iloc[0]
    otr_bid = calculate_otr(v_placed_b, v_placed_b * 0.2, max(bids_df['Volume'].mean() * 0.2, 0.001))

    v_placed_a = asks_df['Volume'].iloc[0]
    otr_ask = calculate_otr(v_placed_a, v_placed_a * 0.2, max(asks_df['Volume'].mean() * 0.2, 0.001))

    bids_adj, asks_adj = bids_df.copy(), asks_df.copy()
    if otr_bid > 45: bids_adj.loc[0, 'Volume'] = 0.0
    if otr_ask > 45: asks_adj.loc[0, 'Volume'] = 0.0

    true_support = bids_adj.loc[bids_adj['Volume'].idxmax()]['Price']
    true_resistance = asks_adj.loc[asks_adj['Volume'].idxmax()]['Price']

    return true_support, true_resistance, otr_bid, otr_ask

def calculate_sigmoid_probability(vw_obi, k=4.0):
    p_long = 1.0 / (1.0 + np.exp(-k * vw_obi))
    return p_long, 1.0 - p_long

def calculate_micro_price(bids_df, asks_df):
    if bids_df.empty or asks_df.empty: return 0.0
    Pb, Vb = bids_df.iloc[0]['Price'], bids_df.iloc[0]['Volume']
    Pa, Va = asks_df.iloc[0]['Price'], asks_df.iloc[0]['Volume']
    return ((Vb * Pa) + (Va * Pb)) / (Vb + Va) if (Vb + Va) > 0 else (Pb + Pa) / 2.0

if 'prev_obi' not in st.session_state: st.session_state.prev_obi = 0.0
if 'prev_loaf' not in st.session_state: st.session_state.prev_loaf = 0.0
if 'pressure_history' not in st.session_state: st.session_state.pressure_history = [1.0, 1.2]

bids_df, asks_df = fetch_mexc_live_orderbook(symbol, 30)
df_1m = fetch_1m_market_structure(symbol)

if bids_df is not None and asks_df is not None and df_1m is not None:
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.0)
    p_long, p_short = calculate_sigmoid_probability(vw_obi, k=4.0)
    
    micro_price = calculate_micro_price(bids_df, asks_df)
    estimated_slippage = calculate_estimated_slippage(bids_df, asks_df, target_volume=1.0)
    
    obi_delta = vw_obi - st.session_state.prev_obi
    loaf_delta = loaf_val - st.session_state.prev_loaf
    
    current_pressure = abs(obi_delta * 100) + abs(loaf_delta) + 1.0
    lambda_intensity = calculate_hawkes_process(current_pressure, st.session_state.pressure_history)
    
    st.session_state.prev_obi = vw_obi
    st.session_state.prev_loaf = loaf_val
    
    support_level, resistance_level, otr_bid, otr_ask = extract_high_walls_support_resistance(bids_df, asks_df)
    current_close = bids_df.iloc[0]['Price']
    
    current_cvd_proxy = abs(loaf_val) * 15000 + (df_1m['Volume'].iloc[-1] if not df_1m.empty else 1000)
    master_quant_score = calculate_master_quant_score(bids_df, asks_df, delta_cvd=current_cvd_proxy, cancellation_ratio=0.20, K=5)

    distance_to_support = abs(current_close - support_level) / current_close * 100
    distance_to_resistance = abs(resistance_level - current_close) / current_close * 100
    active_distance = distance_to_support if loaf_val > 0 else distance_to_resistance
    
    p_real_score = calculate_order_authenticity_probability(age_sec=10.0, distance_val=active_distance, fill_ratio=min(max(abs(loaf_val) / 5.0, 0.2), 1.0))

    current_live_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    st.caption(f"🟢 **Live Server Timestamp:** {current_live_time} | **Mode:** Anti-Spoofing & Slippage Active")

    st.subheader(f"🚀 High-Wall Momentum Engine — {symbol}")
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Micro-Price", f"${micro_price:,.4f}")
    c2.metric("Est. Slippage", f"${estimated_slippage:,.4f}")
    c3.metric("LOAF Value", f"{loaf_val:,.2f}")
    c4.metric("OTR Bid/Ask", f"{otr_bid:.1f} / {otr_ask:.1f}")
    c5.metric("P_real Score", f"{p_real_score * 100:.1f}%")
    c6.metric("Quant Score", f"{master_quant_score:,.4f}")
    
    st.subheader("📊 High-Volume Organic Zones (Low Threshold)")
    p1, p2, l1, l2 = st.columns(4)
    p1.metric("P(Long)", f"{p_long*100:.1f}%")
    p2.metric("P(Short)", f"{p_short*100:.1f}%")
    l1.metric("High Support Wall", f"${support_level:,.4f}")
    l2.metric("High Resistance Wall", f"${resistance_level:,.4f}")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1: target_long_price = st.number_input("Target Long High Wall", value=float(support_level), format="%.4f")
    with col_t2: target_short_price = st.number_input("Target Short High Wall", value=float(resistance_level), format="%.4f")

    st.subheader("🎯 1M High-Momentum Execution Signals")
    
    at_support = (current_close <= target_long_price * 1.002) and (current_close >= target_long_price * 0.998)
    at_resistance = (current_close >= target_short_price * 0.998) and (current_close <= target_short_price * 1.002)
    
    long_condition = at_support and (loaf_val > 0.5) and (p_long > p_short) and (p_real_score > 0.70) and (otr_bid < 45)
    short_condition = at_resistance and (loaf_val < -0.5) and (p_short > p_long) and (p_real_score > 0.70) and (otr_ask < 45)
    
    if long_condition:
        st.success(f"🟢 **HIGH WALL LONG SIGNAL ({symbol}):** Momentum Captured! Support Reaction + P_real > 70% Confirmed!")
    elif short_condition:
        st.error(f"🔴 **HIGH WALL SHORT SIGNAL ({symbol}):** Momentum Captured! Resistance Reaction + P_real > 70% Confirmed!")
    else:
        st.warning(f"⚪ **Scanning 1M High Walls ({symbol}):** Active listening for price reaction...")
else:
    st.warning(f"⚠️ Fetching Live High Walls Data for {symbol}...")
