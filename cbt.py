import numpy as np
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="YIAWDAMZ-OPS Quant Engine", page_icon="📈", layout="centered"
)

st.title("YIAWDAMZ-OPS: Dynamic Wall & Direction Engine")
st.write(
    "Screenshots upload karein. Engine khud detect karega ke market pump kar"
    " rahi hai ya dump, aur walls ke mutabiq direction batayega."
)

# --- 1. SIDEBAR INPUTS & SCREENSHOT HOOKS ---
st.sidebar.header("📸 Live Screenshot Inputs")
uploaded_tv_label = st.sidebar.file_uploader(
    "0. TradingView Open Label Image", type=["png", "jpg", "jpeg"]
)
uploaded_cme = st.sidebar.file_uploader(
    "1. CME / QuikStrike Image (OI & Walls)", type=["png", "jpg", "jpeg"]
)
uploaded_tv_chart = st.sidebar.file_uploader(
    "2. TradingView Options Chart", type=["png", "jpg", "jpeg"]
)

# --- 2. QUANT PARAMETERS & VALUES ---
st.sidebar.header("⚙️ Market Data Setup")
futures_price = st.sidebar.number_input(
    "Futures Price (GC1!)", value=4174.89, format="%.2f"
)
basis_diff = st.sidebar.number_input("Basis Diff", value=25.30, format="%.2f")
volatility_gvz = st.sidebar.number_input(
    "Volatility (GVZ %)", value=23.32, format="%.2f"
)

st.sidebar.subheader("Walls Setup")
call_wall = st.sidebar.number_input(
    "Delta Call Wall (Upper)", value=4174.70, format="%.2f"
)
put_wall = st.sidebar.number_input(
    "Delta Put Wall (Lower)", value=4124.70, format="%.2f"
)
current_market_price = st.sidebar.number_input(
    "Current Spot / Market Price (Live)", value=4150.00, format="%.2f"
)
daily_range_val = st.sidebar.number_input(
    "Daily Range (±SD Value)", value=60.98, format="%.2f"
)

# --- 3. CALCULATIONS ---
spot_ref = futures_price - basis_diff
sd1_upper = spot_ref + (daily_range_val * 0.5)
sd1_lower = spot_ref - (daily_range_val * 0.5)
sd2_upper = spot_ref + daily_range_val
sd2_lower = spot_ref - daily_range_val

# --- 4. DASHBOARD UI & DIRECTION TRACKER ---
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
  st.markdown(
      f"""
    <div style="background-color: #1e1e1e; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;">
        <h4 style="color: #ff4b4b; margin: 0;">DELTA CALL WALL</h4>
        <h2 style="color: white; margin: 5px 0;">${call_wall}</h2>
        <p style="color: #888; margin: 0;">Upper Resistance Boundary</p>
    </div>
    """,
      unsafe_allow_html=True,
  )

with col2:
  st.markdown(
      f"""
    <div style="background-color: #1e1e1e; padding: 15px; border-radius: 10px; border-left: 5px solid #00cc66;">
        <h4 style="color: #00cc66; margin: 0;">DELTA PUT WALL</h4>
        <h2 style="color: white; margin: 5px 0;">${put_wall}</h2>
        <p style="color: #888; margin: 0;">Lower Support Boundary</p>
    </div>
    """,
      unsafe_allow_html=True,
  )

st.markdown("<br>", unsafe_allow_html=True)

# Dynamic Market Direction & Wall Proximity Box
st.markdown(
    f"""
<div style="background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d;">
    <h3 style="color: #f0883e; margin-top: 0;">🚨 LIVE MARKET DIRECTION & WALL STATUS</h3>
    <p><b>GVZ Volatility:</b> {volatility_gvz}% | <b>Spot Reference:</b> ${spot_ref:.2f} \vert{} <b>Live Price:</b>${current_market_price}</p>
""",
    unsafe_allow_html=True,
)

# Direction Logic for Market Rise, Fall, or Range
distance_to_call = call_wall - current_market_price
distance_to_put = current_market_price - put_wall

if put_wall <= current_market_price <= call_wall:
  st.markdown(
      f"""
    <p style="color: #58a6ff;"><b>Market Regime: SIDEWAYS / IN-RANGE</b><br>
    Market apni Put Wall (<b>${put_wall}</b>) aur Call Wall (<b>${call_wall}</b>) ke beech ghoom rahi hai.<br>
    👉 <i>Agar market upar uthti hai:</i> Target <b>Call Wall (${call_wall})</b> hoga.<br>
    👉 <i>Agar market neechay girti hai:</i> Target <b>Put Wall (${put_wall})</b> hoga.</p>
    """,
      unsafe_allow_html=True,
  )
elif current_market_price > call_wall:
  st.markdown(
      f"""
    <p style="color: #ff4b4b;"><b>🔥 BULLISH PUMP ACTIVE (Call Wall Breached!)</b><br>
    Market ne upar ki taraf move karke <b>Call Wall (${call_wall})</b> ko cross kar liya hai. 
    Upar ki taraf volatility expansion aur momentum jari hai!</p>
    """,
      unsafe_allow_html=True,
  )
else:
  st.markdown(
      f"""
    <p style="color: #00cc66;"><b>⚠️ BEARISH DUMP ACTIVE (Put Wall Breached!)</b><br>
    Market girte hue <b>Put Wall (${put_wall})</b> ko bhi tod kar neechay chali gayi hai. 
    Neechay ki taraf liquidity grab aur breakdown active hai!</p>
    """,
      unsafe_allow_html=True,
  )

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# SD Levels Table
st.subheader("📉 Standard Deviation (SD) Support & Resistance Matrix")

st.markdown(
    f"""
| SD Level | Upper Target (+SD) | Lower Target (-SD) |
| :--- | :--- | :--- |
| **±1 SD (68%)** | `${sd1_upper:.2f}` | `${sd1_lower:.2f}` |
| **±2 SD (95%)** | `${sd2_upper:.2f}` | `${sd2_lower:.2f}` |
""",
    unsafe_allow_html=True,
)
