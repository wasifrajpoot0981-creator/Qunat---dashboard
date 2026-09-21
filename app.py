import streamlit as st
import numpy as np
import pandas as pd
import time

# Page Configuration
st.set_page_config(
    page_title="Institutional Quant Trading Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("🚀 XAUUSD & BTC Quantitative Time-Velocity & Microstructure Dashboard")
st.markdown("---")

# Sidebar - User Controls
st.sidebar.header("⚙️ Model Parameters")
asset = st.sidebar.selectbox("Select Asset", ["XAUUSD (Gold)", "BTCUSD (Crypto)"])
daily_atr = st.sidebar.number_input("Enter Daily ATR / Range ($)", value=99.0, step=1.0)
trading_hours_sqrt = st.sidebar.number_input("Trading Hours Square Root ($\sqrt{H}$)", value=4.79, step=0.01)

current_price = st.sidebar.number_input("Current Price ($)", value=4351.0, step=0.5)
target_price = st.sidebar.number_input("Target Price ($)", value=4323.0, step=0.5)

# Order Book & Hawkes Inputs
st.sidebar.markdown("### 📊 Microstructure & Hawkes Parameters")
bid_volume = st.sidebar.number_input("Total Bid Volume", value=500.0, step=10.0)
ask_volume = st.sidebar.number_input("Total Ask Volume", value=200.0, step=10.0)
cancellation_rate = st.sidebar.slider("Cancellation-to-Execution Ratio (CER %)", 0.0, 100.0, 15.0)

# Hawkes Process Simulation Inputs
mu_baseline = st.sidebar.slider("Hawkes Baseline Rate ($\mu$)", 0.1, 5.0, 1.2)
alpha_impact = st.sidebar.slider("Self-Excitation Impact ($\alpha$)", 0.1, 2.0, 0.8)
beta_decay = st.sidebar.slider("Decay Rate ($\beta$)", 0.5, 5.0, 2.0)

# --- CALCULATIONS ---
# 1. Hourly Velocity
hourly_velocity = daily_atr / trading_hours_sqrt

# 2. Distance and Time to Target
price_distance = abs(current_price - target_price)
time_to_target_hours = price_distance / hourly_velocity if hourly_velocity > 0 else 0

# 3. Order Book Imbalance (OBI)
total_vol = bid_volume + ask_volume
obi = (bid_volume - ask_volume) / total_vol if total_vol > 0 else 0

# 4. Hawkes Process Intensity Calculation (Simulated Event History)
# Masalan, pichle kuch seconds mein 4 major trade/order events aaye hain
event_intervals = [0.1, 0.3, 0.35, 0.8] 
current_time = 1.0
excitation = sum(alpha_impact * np.exp(-beta_decay * (current_time - t)) for t in event_intervals)
hawkes_intensity = mu_baseline + excitation

# --- MAIN DASHBOARD DISPLAY ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="⚡ Hourly Velocity", value=f"${hourly_velocity:.2f} / hr")

with col2:
    st.metric(label="🎯 Distance to Target", value=f"${price_distance:.2f}")

with col3:
    st.metric(label="⏳ Time-to-Target", value=f"{time_to_target_hours:.2f} Hrs")

with col4:
    st.metric(label="🔥 Hawkes Intensity ($\lambda$)", value=f"{hawkes_intensity:.2f}")

st.markdown("---")

# Detailed Insights & Filters Section
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📌 Time & Volatility Analysis")
    st.write(f"• **Asset Selected:** {asset}")
    st.write(f"• **Daily Range Base:** ${daily_atr}")
    if time_to_target_hours < 2:
        st.success("🔥 High Momentum Zone: Target expected to hit rapidly!")
    else:
        st.info("⚖️ Normal Macro Drift: Standard time projection active.")

with col_right:
    st.subheader("🛡️ Order Book & Hawkes Microstructure Filter")
    st.write(f"• **Order Book Imbalance (OBI):** `{obi:.2f}`")
    st.write(f"• **Hawkes Process Rate ($\lambda$):** `{hawkes_intensity:.2f}` (Threshold > 3.0 indicates cascade)")
    
    # Combined Logic for Spoofing vs Real Liquidity
    if cancellation_rate > 80.0:
        st.error(f"🚨 WARNING: High Cancellation Rate ({cancellation_rate}%) -> **FAKE WALL (SPOOFING)**")
    elif hawkes_intensity > 3.0 and obi > 0.5:
        st.success(f"🚀 High Intensity Cluster Detected! **Real Institutional Liquidity Sweep Confirmed.**")
    else:
        st.success(f"✅ Market Stable: Normal Order Flow Active.")

# Footer
st.markdown("---")
st.markdown("💡 *Institutional Quant Model: Time-Velocity + Order Book Imbalance + Hawkes Self-Exciting Point Process.*")
