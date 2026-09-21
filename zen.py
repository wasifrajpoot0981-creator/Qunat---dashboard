import streamlit as st
import numpy as np
import pandas as pd
import time
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Quant Trading & Time-Signal Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Quant Trading & Precise Timing Engine")
st.markdown("Real-time Stochastic Simulation with Automated **Long / Short** Entry & Exit Timestamps.")

# Sidebar Controls
st.sidebar.header("Model & Timing Parameters")
asset_choice = st.sidebar.selectbox("Select Asset", ["XAUUSD (Gold)", "BTC/USD"])
base_price = 2650.0 if "XAUUSD" in asset_choice else 65000.0

mu = st.sidebar.slider("Drift (mu)", -0.05, 0.05, 0.01, 0.005)
sigma = st.sidebar.slider("Volatility (sigma)", 0.01, 0.2, 0.05, 0.01)
hawkes_threshold = st.sidebar.slider("Signal Intensity Threshold", 1.0, 5.0, 2.5, 0.1)

# Dashboard Layout
col1, col2, col3, col4 = st.columns(4)
price_placeholder = col1.empty()
intensity_placeholder = col2.empty()
signal_placeholder = col3.empty()
time_placeholder = col4.empty()

st.subheader("📈 Live Stream & Signal Generation")
chart_placeholder = st.empty()
history_log = []

chart_data = pd.DataFrame(columns=["Timestamp", "Price", "Intensity"])

if st.button("Start Live Trading & Timing Engine"):
    current_price = base_price
    curr_intensity = 1.0
    
    for i in range(20):
        # Current Exact Time Stamp
        now_str = datetime.now().strftime("%H:%M:%S")
        
        # Stochastic Jump & Price Movement
        np.random.seed(None)
        shock = np.random.choice([0, 1, -1], p=[0.7, 0.15, 0.15])
        jump = shock * np.random.uniform(0.5, 2.0) * (base_price * 0.001)
        
        current_price += np.random.normal(mu, sigma) * current_price * 0.01 + jump
        curr_intensity = max(0.5, curr_intensity + abs(jump) * 0.5 - 0.1) # Hawkes decay effect
        
        # Determine Trade Signal & Timing Logic
        if curr_intensity >= hawkes_threshold and jump > 0:
            signal = "🟢 LONG (BUY)"
            signal_color = "success"
        elif curr_intensity >= hawkes_threshold and jump < 0:
            signal = "🔴 SHORT (SELL)"
            signal_color = "error"
        else:
            signal = "⏳ WAIT / HOLD"
            signal_color = "info"
            
        # Update UI Metrics
        price_placeholder.metric(label=f"{asset_choice} Price", value=f"${current_price:,.2f}")
        intensity_placeholder.metric(label="Hawkes Intensity ($\lambda$)", value=f"{curr_intensity:.2f}")
        
        if signal_color == "success":
            signal_placeholder.success(f"Signal: {signal}")
        elif signal_color == "error":
            signal_placeholder.error(f"Signal: {signal}")
        else:
            signal_placeholder.info(f"Signal: {signal}")
            
        time_placeholder.metric(label="Exact Action Time", value=now_str)
        
        # Append data for live chart tracking
        new_row = pd.DataFrame({"Timestamp": [now_str], "Price": [current_price], "Intensity": [curr_intensity]})
        chart_data = pd.concat([chart_data, new_row], ignore_index=True)
        
        chart_placeholder.line_chart(chart_data.set_index("Timestamp")[["Price"]])
        time.sleep(1.5)
        
    st.success("Live Quant Session Completed Successfully!")
else:
    st.info("Click the button above to run the live quantitative trading and timing engine.")
