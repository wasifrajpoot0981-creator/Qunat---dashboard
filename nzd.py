import time
import requests
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="MEXC 15M Institutional Event Engine", layout="wide")

st.title("MEXC 15M Institutional Wall & Event Batching Engine")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ Bot Settings & Batching")
symbol = st.sidebar.selectbox("Select Trading Pair", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"], index=0)
refresh_rate = st.sidebar.slider("Scan Interval (Seconds)", min_value=5, max_value=60, value=10)

st.sidebar.subheader("📱 Telegram Summary Setup")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

def send_telegram_message(token, chat_id, message):
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=5)
        except:
            pass

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

def fetch_market_structure(symbol="BTCUSDT", interval="15m"):
    url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=50"
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

# Initialize Session State for Event Queue and Timing
if 'tracked_symbol' not in st.session_state or st.session_state.tracked_symbol != symbol:
    st.session_state.tracked_symbol = symbol
    st.session_state.init_vis_bid = None
    st.session_state.event_queue = []
    st.session_state.last_summary_time = time.time()

bids_df, asks_df = fetch_mexc_live_orderbook(symbol, 30)
df_htf = fetch_market_structure(symbol, "15m")

if bids_df is not None and not bids_df.empty and asks_df is not None and not asks_df.empty and df_htf is not None and not df_htf.empty:
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

    # 15M Trend Filtering using EMA 20 & EMA 50
    df_htf['EMA_20'] = df_htf['Close'].ewm(span=20, adjust=False).mean()
    df_htf['EMA_50'] = df_htf['Close'].ewm(span=50, adjust=False).mean()
    
    current_htf_close = df_htf['Close'].iloc[-1]
    ema_20 = df_htf['EMA_20'].iloc[-1]
    ema_50 = df_htf['EMA_50'].iloc[-1]
    
    is_strong_bullish = (current_htf_close > ema_20) and (ema_20 > ema_50)
    is_strong_bearish = (current_htf_close < ema_20) and (ema_20 < ema_50)

    avg_htf_vol = df_htf['Volume'].rolling(window=20).mean().iloc[-1] if len(df_htf) >= 20 else df_htf['Volume'].mean()
    current_htf_vol = df_htf['Volume'].iloc[-1]
    is_volume_spiking = current_htf_vol > (avg_htf_vol * 1.2)

    v_exec_proxy = current_htf_vol * 500
    v_canc_proxy = abs(st.session_state.init_vis_bid - Vb) * 0.5
    
    iceberg_phi = calculate_iceberg_intensity(v_exec_proxy, st.session_state.init_vis_bid, Vb, v_canc_proxy)
    
    price_ticks_val = abs(df_htf['Close'].iloc[-1] - df_htf['Open'].iloc[-1]) / (spread if spread > 0 else 1e-4)
    aes_score = calculate_absorption_efficiency(current_htf_vol, max(price_ticks_val, 1.0), Vb, v_canc_proxy)

    current_close = Pb

    current_live_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    st.caption(f"🟢 **Live Server Timestamp:** {current_live_time} | **Engine:** 15M Event Batching Mode")

    st.subheader(f"🚀 15M Institutional Event Engine — {symbol}")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Micro-Price", f"${micro_price:,.4f}")
    c2.metric("Iceberg Phi (𝚫)", f"{iceberg_phi:,.1f}")
    c3.metric("AES Score", f"{aes_score:,.2f}")
    c4.metric("15M Trend", "📈 Bullish" if is_strong_bullish else ("📉 Bearish" if is_strong_bearish else "⚖️ Neutral"))
    c5.metric("Volume Spike", "🔥 YES" if is_volume_spiking else "💤 NO")
    
    st.subheader("📊 Institutional Absorption Walls (15M)")
    l1, l2 = st.columns(2)
    l1.metric("Major Support Wall", f"${true_support:,.4f}")
    l2.metric("Major Resistance Wall", f"${true_resistance:,.4f}")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1: target_long_price = st.number_input("Target 15M Long Wall", value=float(true_support), format="%.4f")
    with col_t2: target_short_price = st.number_input("Target 15M Short Wall", value=float(true_resistance), format="%.4f")

    st.subheader("🎯 15M Event Queue & Batching Monitor")
    
    at_support_active = (current_close <= target_long_price * 1.010) and (current_close >= target_long_price * 0.990)
    at_resistance_active = (current_close >= target_short_price * 0.990) and (current_close <= target_short_price * 1.010)
    
    long_prediction = at_support_active and (imbalance > 0.04) and (aes_score > 3.0) and is_strong_bullish and is_volume_spiking
    short_prediction = at_resistance_active and (imbalance < -0.04) and (aes_score > 3.0) and is_strong_bearish and is_volume_spiking
    
    # Event Queue Collection Logic (similar to your screenshot's summary loop)
    if long_prediction:
        event_str = f"🟢 [LONG FLIP] {symbol} @ ${current_close} | Iceberg: {iceberg_phi:.1f} | AES: {aes_score:.2f}"
        if event_str not in st.session_state.event_queue:
            st.session_state.event_queue.append(event_str)
        st.success(event_str)
    elif short_prediction:
        event_str = f"🔴 [SHORT FLIP] {symbol} @ ${current_close} | Iceberg: {iceberg_phi:.1f} | AES: {aes_score:.2f}"
        if event_str not in st.session_state.event_queue:
            st.session_state.event_queue.append(event_str)
        st.error(event_str)
    else:
        st.warning(f"⚪ **Scanning {symbol}:** Collecting institutional wall events into queue...")

    # Periodic summary sender (Every 60 seconds batch report to Telegram, exactly like your script)
    summary_interval = 60
    if time.time() - st.session_state.last_summary_time >= summary_interval:
        if len(st.session_state.event_queue) > 0:
            report_msg = f"📊 *MEXC 15M Institutional Summary Report* ({current_live_time})\n\n" + "\n".join(st.session_state.event_queue)
            send_telegram_message(telegram_token, telegram_chat_id, report_msg)
            st.session_state.event_queue.clear()
        st.session_state.last_summary_time = time.time()
else:
    st.warning(f"⚠️ 15M market data load ho raha hai, kripya thori der wait karein...")
