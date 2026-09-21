import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

# Page Configuration
st.set_page_config(
    page_title="Advanced Monte Carlo & Hawkes Quant Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("🚀 Advanced Monte Carlo Jump Diffusion + Hawkes Dashboard")
st.markdown("Real-time Live Market Data integration with Merton Jump-Diffusion paths & Hawkes Process intensity tracking.")

# Sidebar Controls for Advanced Models
st.sidebar.header("Model Parameters")
asset_choice = st.sidebar.selectbox("Select Asset", ["XAUUSD (Gold)", "BTC/USD"])
ticker_symbol = "GC=F" if "XAUUSD" in asset_choice else "BTC-USD"

# Default price fallback
default_price = 2650.0 if "XAUUSD" in ticker_symbol else 65000.0

st.sidebar.subheader("Jump-Diffusion Parameters")
mu = st.sidebar.slider("Drift (mu)", -0.1, 0.1, 0.02, 0.01)
sigma = st.sidebar.slider("Volatility (sigma)", 0.05, 0.5, 0.15, 0.01)
lam_jump = st.sidebar.slider("Jump Intensity (Lambda)", 0.1, 5.0, 1.0, 0.1)
jump_mean = st.sidebar.slider("Jump Mean Size", -0.05, 0.05, 0.0, 0.01)
jump_std = st.sidebar.slider("Jump Std Dev", 0.01, 0.1, 0.02, 0.01)

st.sidebar.subheader("Hawkes Process Parameters")
alpha = st.sidebar.slider("Jump Impact (alpha)", 0.1, 2.0, 0.5, 0.1)
beta = st.sidebar.slider("Decay Rate (beta)", 0.5, 5.0, 1.5, 0.1)
steps = st.sidebar.slider("Simulation Steps", 50, 300, 100, 10)

# Fetch Live Price from Yahoo Finance
@st.cache_data(ttl=30)
def fetch_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1d", interval="1m")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    return default_price

current_price = fetch_live_price(ticker_symbol)

# Top Metrics Layout
col1, col2, col3 = st.columns(3)
col1.metric(label=f"{asset_choice} Live Base Price", value=f"{current_price:,.2f}")

if st.button("Run Monte Carlo & Hawkes Simulation"):
    with st.spinner("Running advanced stochastic simulations..."):
        np.random.seed(42)
        dt = 1.0 / 252.0
        
        prices = [current_price]
        intensities = [lam_jump]
        time_steps = [0]
        
        curr_intensity = lam_jump
        
        for i in range(1, steps):
            # Update Hawkes intensity decay
            curr_intensity += beta * (lam_jump - curr_intensity) * dt
            
            # Check for jump event via Poisson/Hawkes
            if np.random.rand() < curr_intensity * dt:
                curr_intensity += alpha
                jump_size = np.random.normal(jump_mean, jump_std)
            else:
                jump_size = 0.0
            
            # Merton Jump-Diffusion step
            z = np.random.normal(0, 1)
            dS = prices[-1] * (mu * dt + sigma * np.sqrt(dt) * z + jump_size)
            new_price = max(1.0, prices[-1] + dS)
            
            prices.append(new_price)
            intensities.append(curr_intensity)
            time_steps.append(i)
        
        sim_results = pd.DataFrame({
            "Step": time_steps,
            "Simulated Price": prices,
            "Hawkes Intensity": intensities
        })
        
        col2.metric(label="Final Simulated Price", value=f"{prices[-1]:,.2f}")
        col3.metric(label="Peak Hawkes Intensity ($\lambda$)", value=f"{max(intensities):.2f}")
        
        st.subheader("📈 Merton Jump-Diffusion Price Paths")
        st.line_chart(sim_results.set_index("Step")[["Simulated Price"]])
        
        st.subheader("⚡ Hawkes Process Intensity ($\lambda_t$)")
        st.line_chart(sim_results.set_index("Step")[["Hawkes Intensity"]])
        
        st.success("Advanced Quantitative Simulation Completed Successfully!")
else:
    st.info("Click 'Run Monte Carlo & Hawkes Simulation' button to execute the model using live market data.")
