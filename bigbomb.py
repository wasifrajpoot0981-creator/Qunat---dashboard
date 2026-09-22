import time
import requests
import numpy as np
import pandas as pd
import streamlit as st

st.title("MEXC Multi-Coin 1M Scalping Dashboard — Ultimate Quant & P_real Engine")

symbol = st.selectbox("Select Trading Pair", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"], index=0)

# --- MASTER MOMENTUM TIMER CLASS ---
class MasterMomentumTimer:
    def __init__(self, time_window=5):
        self.time_window = time_window
        self.cvd_history = []

    def update_cvd(self, current_cvd):
        self.cvd_history.append((time.time(), current_cvd))
        cutoff = time.time() - (self.time_window * 3)
        self.cvd_history = [data for data in self.cvd_history if data[0] > cutoff]

    def calculate_countdown(self, raw_wall_volume, cancellation_ratio=0.3):
        if len(self.cvd_history) < 2:
            return "⏳ System Syncing CVD History...", 0.0
        
        real_wall_volume = raw_wall_volume * (1.0 - cancellation_ratio)
        current_time, current_cvd = self.cvd_history[-1]
        past_cvd = None
        for t, val in reversed(self.cvd_history):
            if current_time - t >= self.time_window:
                past_cvd = val
                break
                
        if past_cvd is None:
            past_cvd = self.cvd_history[0][1]
            
        cvd_velocity = (current_cvd - past_cvd) / self.time_window
        
        if cvd_velocity <= 0:
            return "⚖️ Passive State: Buy flow lagging. Momentum postponed.", 999.0
            
        seconds_to_impact = real_wall_volume / cvd_velocity
        minutes_to_impact = round(seconds_to_impact / 60.0, 1)
        
        if seconds_to_impact <= 3.0:
            return f"🚀 SYSTEM CRITICAL: Impact expected in {round(seconds_to_impact, 1)} seconds!", seconds_to_impact
        elif seconds_to_impact <= 60.0:
            return f"⏰ High Alert: Breakout within {round(seconds_to_impact, 1)} seconds ({minutes_to_impact} minutes)!", seconds_to_impact
        else:
            return f"⏳ Steady Accumulation: Estimated breakout in {minutes_to_impact} minutes.", seconds_to_impact

# --- MASTER QUANT FORMULA ---
def calculate_master_quant_score(bids_df, asks_df, delta_cvd, cancellation_ratio=0.3, K=5):
    if bids_df.empty or asks_df.empty:
        return 0.0
    num_levels = min(len(bids_df), len(asks_df), K)
    bid_sum = sum((float(i + 1) * bids_df.loc[i, 'Volume']) for i in range(num_levels))
    ask_sum = sum((float(i + 1) * asks_df.loc[i, 'Volume']) for i in range(num_levels))
    denominator = bid_sum + ask_sum
    if denominator == 0:
        return 0.0
    return (delta_cvd / denominator) * (1.0 - cancellation_ratio)

# --- NEW: ORDER AUTHENTICITY PROBABILITY FORMULA (P_real from Screenshots) ---
def calculate_order_authenticity_probability(age_sec, distance_val, fill_ratio, beta_0=-1.5, beta_1=0.2, beta_2=-0.5, beta_3=1.2):
    """
    Implements High-Class Quant Formula from screenshots[cite: 13]:
    P_real = 1 / (1 + e^-(beta_0 + beta_1*Age + beta_2*Dist + beta_3*FillRatio))
    """
    exponent = -(beta_0 + (beta_1 * age_sec) + (beta_2 * distance_val) + (beta_3 * fill_ratio))
    # Clip exponent to prevent overflow in exp function
    exponent = np.clip(exponent, -50, 50)
    p_real = 1.0 / (1.0 + np.exp(exponent))
    return p_real

def fetch_mexc_live_orderbook(symbol="BTCUSDT", limit=25):
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

def calculate_loaf(bids_df, asks_df, theta=1.0):
    large_bids = bids_df[bids_df['Volume'] > theta]['Volume'].sum()
    large_asks = asks_df[asks_df['Volume'] > theta]['Volume'].sum()
    return large_bids - large_asks

def extract_true_support_resistance(bids_df, asks_df):
    if bids_df.empty or asks_df.empty:
        return 0.0, 0.0
    b_mean, b_std = bids_df['Volume'].mean(), bids_df['Volume'].std()
    b_threshold = b_mean + 2.5 * (b_std if not pd.isna(b_std) and b_std > 0 else 0.01)
    clean_bids = bids_df[bids_df['Volume'] <= b_threshold]
    if clean_bids.empty:
        clean_bids = bids_df
    true_support = clean_bids.loc[clean_bids['Volume'].idxmax()]['Price']

    a_mean, a_std = asks_df['Volume'].mean(), asks_df['Volume'].std()
    a_threshold = a_mean + 2.5 * (a_std if not pd.isna(a_std) and a_std > 0 else 0.01)
    clean_asks = asks_df[asks_df['Volume'] <= a_threshold]
    if clean_asks.empty:
        clean_asks = asks_df
    true_resistance = clean_asks.loc[clean_asks['Volume'].idxmax()]['Price']

    return true_support, true_resistance

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

def calculate_vpin(bids_df, asks_df):
    if bids_df.empty or asks_df.empty:
        return 0.0
    vb = bids_df['Volume'].values
    vs = asks_df['Volume'].values
    min_len = min(len(vb), len(vs))
    if min_len == 0:
        return 0.0
    return np.sum(np.abs(vb[:min_len] - vs[:min_len])) / np.sum(vb[:min_len] + vs[:min_len])

def calculate_slippage_cost(bids_df, asks_df):
    if bids_df.empty or asks_df.empty:
        return 0.0
    delta_p = abs(asks_df.iloc[0]['Price'] / bids_df.iloc[0]['Price'] - 1)
    market_order_volume = asks_df['Volume'].iloc[0] + bids_df['Volume'].iloc[0]
    if market_order_volume == 0:
        return 0.0
    return delta_p / market_order_volume

# Session states
if 'prev_obi' not in st.session_state:
    st.session_state.prev_obi = 0.0
if 'prev_loaf' not in st.session_state:
    st.session_state.prev_loaf = 0.0
if 'pressure_history' not in st.session_state:
    st.session_state.pressure_history = []
if 'momentum_timer' not in st.session_state:
    st.session_state.momentum_timer = MasterMomentumTimer(time_window=5)

bids_df, asks_df = fetch_mexc_live_orderbook(symbol, 25)
df_1m = fetch_1m_market_structure(symbol)

if bids_df is not None and asks_df is not None and df_1m is not None:
    vw_obi = calculate_vw_obi(bids_df, asks_df, 5)
    loaf_val = calculate_loaf(bids_df, asks_df, theta=1.0)
    garch_vol = calculate_garch_volatility(df_1m['Close'])
    p_long, p_short = calculate_sigmoid_probability(vw_obi, k=3.5)
    
    micro_price = calculate_micro_price(bids_df, asks_df)
    vpin_val = calculate_vpin(bids_df, asks_df)
    slippage_cost = calculate_slippage_cost(bids_df, asks_df)
    
    obi_delta = vw_obi - st.session_state.prev_obi
    loaf_delta = loaf_val - st.session_state.prev_loaf
    
    current_pressure = abs(obi_delta * 100) + abs(loaf_delta)
    jump_intensity = calculate_hawkes_jump_intensity(current_pressure, st.session_state.pressure_history)
    
    st.session_state.prev_obi = vw_obi
    st.session_state.prev_loaf = loaf_val
    
    # Extract True Organic Support & Resistance
    support_level, resistance_level = extract_true_support_resistance(bids_df, asks_df)
    current_close = bids_df.iloc[0]['Price']
    
    # Update Momentum Timer
    current_cvd_proxy = abs(loaf_val) * 10000 + (df_1m['Volume'].iloc[-1] if not df_1m.empty else 1000)
    st.session_state.momentum_timer.update_cvd(current_cvd_proxy)
    
    raw_wall_vol = asks_df['Volume'].max() if loaf_val < 0 else bids_df['Volume'].max()
    countdown_status, seconds_to_impact = st.session_state.momentum_timer.calculate_countdown(raw_wall_volume=raw_wall_vol, cancellation_ratio=0.30)

    # Master Quant Score Calculation
    master_quant_score = calculate_master_quant_score(bids_df, asks_df, delta_cvd=current_cvd_proxy, cancellation_ratio=0.30, K=5)

    # --- CONNECTING P_real FORMULA WITH SUPPORT / RESISTANCE & FILL RATIO ---
    distance_to_support = abs(current_close - support_level) / current_close * 100
    distance_to_resistance = abs(resistance_level - current_close) / current_close * 100
    active_distance = distance_to_support if loaf_val > 0 else distance_to_resistance
    
    estimated_age_sec = 15.0 # Simulated micro-lifetime of whale order in seconds
    estimated_fill_ratio = min(max(abs(loaf_val) / 10.0, 0.1), 1.0) # Execution speed fill ratio matching volume
    
    p_real_score = calculate_order_authenticity_probability(
        age_sec=estimated_age_sec, 
        distance_val=active_distance, 
        fill_ratio=estimated_fill_ratio
    )

    st.subheader(f"🚀 MEXC Multi-Coin 1M Dashboard — {symbol}")
    
    # 6 Metrics Columns including P_real and Impact Time
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Micro-Price", f"${micro_price:,.4f}")
    c2.metric("LOAF Flow", f"{loaf_val:+,.2f}")
    c3.metric("GARCH Vol (1M)", f"{garch_vol:.3f}%")
    c4.metric("P_real Authenticity", f"{p_real_score * 100:.1f}%")
    c5.metric("Quant Score", f"{master_quant_score:,.4f}")
    c6.metric("Impact Time", f"{seconds_to_impact:.1f}s" if seconds_to_impact < 900 else "Syncing")
    
    st.subheader("📊 True Order Book Zones & Probabilities")
    p1, p2, l1, l2 = st.columns(4)
    p1.metric("P(Long)", f"{p_long*100:.1f}%")
    p2.metric("P(Short)", f"{p_short*100:.1f}%")
    l1.metric("True Organic Support", f"${support_level:,.4f}")
    l2.metric("True Organic Resistance", f"${resistance_level:,.4f}")
    
    st.success(f"⏱️ **Master Momentum Timer & Countdown Status:** {countdown_status}")
    
    # Custom Filters
    st.subheader("⚙️ Custom Price & Time Trigger Filters")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        target_long_price = st.number_input("Target Long Price Threshold", value=float(support_level), format="%.4f")
    with col_t2:
        target_short_price = st.number_input("Target Short Price Threshold", value=float(resistance_level), format="%.4f")

    st.subheader("🎯 1M Scalping Execution Signals (Connected with P_real & S/R)")
    
    at_support = (current_close <= target_long_price * 1.0005) and (current_close >= target_long_price * 0.9995)
    at_resistance = (current_close >= target_short_price * 0.9995) and (current_close <= target_short_price * 1.0005)
    
    medium_intensity = (jump_intensity >= 0.5) and (jump_intensity <= 4.0)
    valid_real_book = (slippage_cost > 0.0000001)
    
    # Strict filter: P_real must be > 0.85 for high-confidence real breakout/bounce, rejecting spoof orders (< 0.30)[cite: 12]
    short_condition = (
        at_resistance and 
        (loaf_val < -2.0) and 
        (p_short > p_long) and 
        (vw_obi < 0 or obi_delta < 0) and
        medium_intensity and
        valid_real_book and
        (p_real_score > 0.85)
    )
    
    long_condition = (
        at_support and 
        (loaf_val > 2.0) and 
        (p_long > p_short) and 
        (vw_obi > 0 or obi_delta > 0) and
        medium_intensity and
        valid_real_book and
        (p_real_score > 0.85)
    )
    
    if long_condition:
        st.success(f"🟢 **1M HIGH-CONFIDENCE LONG EXPLORED ({symbol}):** True Support + P_real Authenticity > 85% Confirmed!")
    elif short_condition:
        st.error(f"🔴 **1M HIGH-CONFIDENCE SHORT EXPLORED ({symbol}):** True Resistance + P_real Authenticity > 85% Confirmed!")
    else:
        st.warning(f"⚪ **1M WAITING ZONE ({symbol}):** Verifying P_real score & filtering out fake spoof walls...")
        
    col1, col2 = st.columns(2)
    with col1:
        st.text("Top Bids")
        st.dataframe(bids_df.head(5))
    with col2:
        st.text("Top Asks")
        st.dataframe(asks_df.head(5))
else:
    st.warning(f"⚠️ Connecting to MEXC API & Fetching Live 1M Data for {symbol}...")
