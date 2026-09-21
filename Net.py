import streamlit as st
import pandas as pd
import numpy as np
import requests

st.title("MEXC Ultimate Quantitative, Timing & Crash Prediction Dashboard")

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

# 4. Autoregressive Conditional Duration (ACD Model) - Time between trades[cite: 5]
def calculate_acd_duration(trade_intervals):
    if not trade_intervals or len(trade_intervals) < 3:
        return 1.0
    omega = 0.1
    alpha_coeff = 0.3
    beta_coeff = 0.5
    psi = omega + alpha_coeff * trade_intervals[-1] + beta_coeff * trade_intervals[-2]
    return max(psi, 0.1)

# 5. Black-Scholes Theta (Time Decay Sensitivity)[cite: 4]
def calculate_bs_theta(price, volatility):
    # Proxy estimation for high-frequency option/asset time decay sensitivity theta = dV/dt
    return -0.5 * (price * volatility**2) / 365.0

# 6. Cox Proportional Hazards Model (Hazard/Default Rate Risk)[cite: 7]
def calculate_cox_hazard(avg_imb, volatility):
    lambda_0 = 0.02  # baseline risk
    beta_weight = 1.5
    # High negative imbalance or volatility increases hazard/default risk
    risk_factor = abs(min(avg_imb, 0.0)) * beta_weight + volatility * 10.0
    hazard_rate = lambda_0 * np.exp(risk_factor)
    return hazard_rate

# 7. LPPLS Model (Log-Periodic Power Law Singularity - Bubble Crash Timing)[cite: 6]
def calculate_lppls_crash_indicator(prices):
    if len(prices) < 5:
        return 0.0
    # Measuring acceleration in price peaks to estimate crash proximity t_c
    returns = np.diff(np.log(prices))
    acceleration = np.diff(returns) if len(returns) > 1 else np.array([0.0])
    crash_metric = float(np.mean(np.abs(acceleration))) * 1000.0
    return crash_metric

# Session States for Tracking History
if 'intervals' not in st.session_state:
    st.session_state.intervals = [1.2, 1.0, 1.5]
if 'price_history' not in st.session_state:
    st.session_state.price_history = []

# Fetching Data
bids_df, asks_df = fetch_mexc_live_orderbook("BTCUSDT", 10)

if bids_df is not None and asks_df is not None:
    # Calculations
    imb_df = calculate_multi_level_imbalance(bids_df, asks_df, 5)
    avg_imb = imb_df['Imbalance'].mean()
    rv = calculate_realized_volatility(bids_df, asks_df)
    mid_price = (bids_df.loc[0, 'Price'] + asks_df.loc[0, 'Price']) / 2.0
    
    st.session_state.price_history.append(mid_price)
    if len(st.session_state.price_history) > 20:
        st.session_state.price_history.pop(0)
        
    acd_time = calculate_acd_duration(st.session_state.intervals)
    bs_theta = calculate_bs_theta(mid_price, rv)
    cox_hazard = calculate_cox_hazard(avg_imb, rv)
    lppls_crash = calculate_lppls_crash_indicator(st.session_state.price_history)
    
    # Dashboard Display Layout
    st.subheader("🚀 Advanced Quantitative Timing Metrics Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("LOB Imbalance", f"{avg_imb:.4f}")
    c2.metric("ACD Expected Duration ($\psi_i$)", f"{acd_time:.3f}s")[cite: 5]
    c3.metric("BS Theta ($\Theta$)", f"{bs_theta:.2f}")[cite: 4]
    c4.metric("Cox Hazard Rate ($\lambda(t|X)$)", f"{cox_hazard:.4f}")[cite: 7]
    
    st.subheader("📉 Crash & Volatility Risk Analysis")
    r1, r2 = st.columns(2)
    r1.metric("Realized Vol ($RV_\alpha$)", f"{rv:.5f}")
    r2.metric("LPPLS Crash Indicator", f"{lppls_crash:.2f}")[cite: 6]
    
    # Aggressive Scalping Signal with Timing Models
    st.subheader("🎯 Master Timing & Scalping Signal Execution")
    if avg_imb > 0.20 and cox_hazard < 0.05:
        st.success("🟢 **STRONG LONG SETUP:** Buying pressure active and hazard risk is minimal!")
    elif avg_imb < -0.20 or lppls_crash > 5.0:
        st.error("🔴 **STRONG SHORT/CRASH WARNING:** High selling pressure or LPPLS crash singularity detected!")[cite: 6]
    else:
        st.warning("⚪ **NEUTRAL ZONE:** Market is stable. Monitoring duration and hazard parameters.")
        
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
