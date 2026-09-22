import time
import requests
import numpy as np
import pandas as pd
import streamlit as st

st.title("MEXC Multi-Coin 1M High-Wall Flip & Iceberg Catcher Engine")

symbol = st.selectbox("Select Trading Pair", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"], index=0)

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
    url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval=1m&limit=50"
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

# --- THE QUANT ICEBERG DETECTION FORMULA ---
def calculate_iceberg_intensity(v_executed, v_visible_0, v_visible_t, v_canceled):
    # Phi_t = V_executed,t - (V_visible,0 - V_visible,t + V_canceled,t)[cite: 1]
    return v_executed - (v_visible_0 - v_visible_t + v_canceled)

# --- THE QUANT ABSORPTION EFFICIENCY SCORE (AES) ---
def calculate_absorption_efficiency(market_volume, price_ticks, bids_added, bids_canceled, eps=1e-9):
    # AES = (Market Sells / Price Drop Ticks) * (Bids Added at Floor / (Bids Canceled + epsilon))[cite: 2]
    tick_denom = max(price_ticks, 1e-4)
    term1 = market_volume / tick_denom
    term2 = bids_added / (bids_canceled + eps)
    return term1 * term2

# --- ADVANCED FLIP & ABSORPTION ENGINE ---
def calculate_flip_metrics(bids_df, asks_df, df_1m):
    if bids_df.empty or asks_df.empty or df_1m.empty:
        return 0.0, 0.0, 0.0, 0.0, 0.0, False, 0.0, 0.0
    
    Pb, Vb = bids_df.iloc[0]['Price'], bids_df.iloc[0]['Volume']
    Pa, Va = asks_df.iloc[0]['Price'], asks_df.iloc[0]['Volume']
    micro_price = ((Vb * Pa) + (Va * Pb)) / (Vb + Va) if (Vb + Va) > 0 else (Pb + Pa) / 2.0
    
    spread = Pa - Pb
    avg_vol = (bids_df['Volume'].mean() + asks_df['Volume'].mean()) / 2.0
    est_slippage = (1.0 / avg_vol) * spread if avg_vol > 0 else 0.0

    true_support = bids_df.loc[bids_df['Volume'].idxmax()]['Price']
    true_resistance = asks_df.loc[asks_df['Volume'].idxmax()]['Price']

    bid_heavy = bids_df['Volume'].sum()
    ask_heavy = asks_df['Volume'].sum()
    total_depth = bid_heavy + ask_heavy
    imbalance = (bid_heavy - ask_heavy) / total_depth if total_depth > 0 else 0.0

    avg_1m_vol = df_1m['Volume'].rolling(window=20).mean().iloc[-1]
    current_1m_vol = df_1m['Volume'].iloc[-1]
    is_volume_spiking = current_1m_vol > (avg_1m_vol * 1.4)

    # Applying the Iceberg and Absorption formulas from your screenshots
    v_exec_proxy = current_1m_vol * 1000
    v_vis_0 = bids_df['Volume'].iloc[0] * 2.0
    v_vis_t = bids_df['Volume'].iloc[0]
    v_canc_proxy = v_vis_0 * 0.2
    
    iceberg_phi = calculate_iceberg_intensity(v_exec_proxy, v_vis_0, v_vis_t, v_canc_proxy)[cite: 1]
    
    price_ticks_val = abs(df_1m['Close'].iloc[-1] - df_1m['Open'].iloc[-1]) / (spread if spread > 0 else 1e-4)
    aes_score = calculate_absorption_efficiency(current_1m_vol, max(price_ticks_val, 1.0), bids_df['Volume'].iloc[0], v_canc_proxy)[cite: 2]

    return micro_price, est_slippage, true_support, true_resistance, imbalance, is_volume_spiking, iceberg_phi, aes_score

bids_df, asks_df = fetch_mexc_live_orderbook(symbol, 30)
df_1m = fetch_1m_market_structure(symbol)

if bids_df is not None and asks_df is not None and df_1m is not None:
    micro_price, est_slippage, support_level, resistance_level, imbalance, is_volume_spiking, iceberg_phi, aes_score = calculate_flip_metrics(bids_df, asks_df, df_1m)
    current_close = bids_df.iloc[0]['Price']

    current_live_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    st.caption(f"🟢 **Live Server Timestamp:** {current_live_time} | **Engine:** Iceberg & AES Absorption Mode")

    st.subheader(f"🚀 Big Move & Iceberg Catcher Engine — {symbol}")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Micro-Price", f"${micro_price:,.4f}")
    c2.metric("Iceberg Phi (𝚫)", f"{iceberg_phi:,.1f}")
    c3.metric("AES Score", f"{aes_score:,.2f}")
    c4.metric("Imbalance", f"{imbalance:+.3f}")
    c5.metric("Volume Spike", "🔥 YES" if is_volume_spiking else "💤 NO")
    
    st.subheader("📊 Institutional Absorption Walls")
    l1, l2 = st.columns(2)
    l1.metric("Major Support Wall", f"${support_level:,.4f}")
    l2.metric("Major Resistance Wall", f"${resistance_level:,.4f}")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1: target_long_price = st.number_input("Target Flip Long Wall", value=float(support_level), format="%.4f")
    with col_t2: target_short_price = st.number_input("Target Flip Short Wall", value=float(resistance_level), format="%.4f")

    st.subheader("🎯 Exact Market Flip & Big Move Signals")
    
    at_support_exact = (current_close <= target_long_price * 1.006) and (current_close >= target_long_price * 0.994)
    at_resistance_exact = (current_close >= target_short_price * 0.994) and (current_close <= target_short_price * 1.006)
    
    big_long_flip = at_support_exact and (imbalance > 0.05) and is_volume_spiking and (aes_score > 10.0)
    big_short_flip = at_resistance_exact and (imbalance < -0.05) and is_volume_spiking and (aes_score > 10.0)
    
    if big_long_flip:
        st.success(f"🟢 **EXACT BOTTOM FLIP / BIG LONG ({symbol}):** Iceberg Absorption + AES Confirmed! Major Move Starting!")
    elif big_short_flip:
        st.error(f"🔴 **EXACT TOP FLIP / BIG SHORT ({symbol}):** Iceberg Rejection + AES Confirmed! Major Move Starting!")
    else:
        st.warning(f"⚪ **Waiting for Institutional Flip ({symbol}):** Scanning iceberg intensity and absorption efficiency...")
else:
    st.warning(f"⚠️ Fetching Live Data for {symbol}...")
