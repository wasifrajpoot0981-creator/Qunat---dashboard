import time
import requests
import numpy as np
import pandas as pd
import streamlit as st

st.title("MEXC Multi-Coin 1M High-Wall Flip & Iceberg Catcher Engine (Safe Mode)")

symbol = st.selectbox("Select Trading Pair", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"], index=0)

def fetch_mexc_live_orderbook(symbol="BTCUSDT", limit=30):
    url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if "bids" in data and "asks" in data:
            bids = pd.DataFrame(data.get("bids", []), columns=['Price', 'Volume']).astype(float)
            asks = pd.DataFrame(data.get("asks", []), columns=['Price', 'Volume']).astype(float)
            return bids, asks
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

def calculate_iceberg_intensity(v_executed, v_visible_0, v_visible_t, v_canceled):
    return v_executed - (v_visible_0 - v_visible_t + v_canceled)

def calculate_absorption_efficiency(market_volume, price_ticks, bids_added, bids_canceled, eps=1e-9):
    tick_denom = max(price_ticks, 1e-4)
    term1 = market_volume / tick_denom
    term2 = bids_added / (bids_canceled + eps)
    return term1 * term2

if 'tracked_symbol' not in st.session_state or st.session_state.tracked_symbol != symbol:
    st.session_state.tracked_symbol = symbol
    st.session_state.init_vis_bid = None

bids_df, asks_df = fetch_mexc_live_orderbook(symbol, 30)
df_1m = fetch_1m_market_structure(symbol)

if bids_df is not None and not bids_df.empty and asks_df is not None and not asks_df.empty and df_1m is not None and not df_1m.empty:
    Pb, Vb = bids_df.iloc[0]['Price'], bids_df.iloc[0]['Volume']
    Pa, Va = asks_df.iloc[0]['Price'], asks_df.iloc[0]['Volume']
    
    if st.session_state.init_vis_bid is None:
        st.session_state.init_vis_bid = Vb

    micro_price = ((Vb * Pa) + (Va * Pb)) / (Vb + Va) if (Vb + Va) > 0 else (Pb + Pa) / 2.0
    spread = Pa - Pb
    avg_vol = (bids_df['Volume'].mean() + asks_df['Volume'].mean()) / 2.0
    est_slippage = (1.0 / avg_vol) * spread if avg_vol > 0 else 0.0

    true_support = bids_df.loc[bids_df['Volume'].idxmax()]['Price'] if not bids_df.empty else Pb
    true_resistance = asks_df.loc[asks_df['Volume'].idxmax()]['Price'] if not asks_df.empty else Pa

    bid_heavy = bids_df['Volume'].sum()
    ask_heavy = asks_df['Volume'].sum()
    total_depth = bid_heavy + ask_heavy
    imbalance = (bid_heavy - ask_heavy) / total_depth if total_depth > 0 else 0.0

    avg_1m_vol = df_1m['Volume'].rolling(window=20).mean().iloc[-1] if len(df_1m) >= 20 else df_1m['Volume'].mean()
    current_1m_vol = df_1m['Volume'].iloc[-1]
    is_volume_spiking = current_1m_vol > (avg_1m_vol * 1.1)

    v_exec_proxy = current_1m_vol * 500
    v_canc_proxy = abs(st.session_state.init_vis_bid - Vb) * 0.5
    
    iceberg_phi = calculate_iceberg_intensity(v_exec_proxy, st.session_state.init_vis_bid, Vb, v_canc_proxy)
    
    price_ticks_val = abs(df_1m['Close'].iloc[-1] - df_1m['Open'].iloc[-1]) / (spread if spread > 0 else 1e-4)
    aes_score = calculate_absorption_efficiency(current_1m_vol, max(price_ticks_val, 1.0), Vb, v_canc_proxy)

    current_close = Pb

    current_live_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    st.caption(f"🟢 **Live Server Timestamp:** {current_live_time} | **Engine:** Safe Dynamic Mode")

    st.subheader(f"🚀 Big Move & Iceberg Catcher Engine — {symbol}")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Micro-Price", f"${micro_price:,.4f}")
    c2.metric("Iceberg Phi (𝚫)", f"{iceberg_phi:,.1f}")
    c3.metric("AES Score", f"{aes_score:,.2f}")
    c4.metric("Imbalance", f"{imbalance:+.3f}")
    c5.metric("Volume Spike", "🔥 YES" if is_volume_spiking else "💤 NO")
    
    st.subheader("📊 Institutional Absorption Walls")
    l1, l2 = st.columns(2)
    l1.metric("Major Support Wall", f"${true_support:,.4f}")
    l2.metric("Major Resistance Wall", f"${true_resistance:,.4f}")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1: target_long_price = st.number_input("Target Flip Long Wall", value=float(true_support), format="%.4f")
    with col_t2: target_short_price = st.number_input("Target Flip Short Wall", value=float(true_resistance), format="%.4f")

    st.subheader("🎯 Active Market Flip & Prediction Signals")
    
    at_support_active = (current_close <= target_long_price * 1.012) and (current_close >= target_long_price * 0.988)
    at_resistance_active = (current_close >= target_short_price * 0.988) and (current_close <= target_short_price * 1.012)
    
    long_prediction = at_support_active and (imbalance > 0.02) and (aes_score > 2.0)
    short_prediction = at_resistance_active and (imbalance < -0.02) and (aes_score > 2.0)
    
    if long_prediction:
        st.success(f"🟢 **PREDICTION LONG SIGNAL ({symbol}):** Support Absorption Active! Potential Upward Flip Detected!")
    elif short_prediction:
        st.error(f"🔴 **PREDICTION SHORT SIGNAL ({symbol}):** Resistance Rejection Active! Potential Downward Flip Detected!")
    else:
        st.warning(f"⚪ **Scanning Market ({symbol}):** Listening for active wall reactions...")
else:
    st.warning(f"⚠️ Live data fetch karne mein thori der lag rahi hai ya data empty hai. Kripya thori der wait karein...")
