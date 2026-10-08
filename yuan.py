import numpy as np
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="YIAWDAMZ-OPS Quant Engine", page_icon="📊", layout="centered"
)

st.title("YIAWDAMZ-OPS: Delta-GEX & IV Quant Engine")
st.write(
    "Aap apna OPS aur CME data yahan input karein, engine khud ba khud"
    " calculations aur market regime batayega."
)

# --- 1. OPS & CME RAW INPUT SECTION ---
st.sidebar.header("📥 OPS & CME Data Inputs")
ops_text_input = st.sidebar.text_area(
    "Paste OPS / CME Data Notes (Optional)",
    placeholder=(
        "Yahan apna custom OPS data ya text paste kar sakte hain..."
    ),
)

futures_price = st.sidebar.number_input(
    "Futures Price (GC1!)", value=4174.89, format="%.2f"
)
basis_diff = st.sidebar.number_input(
    "Basis Diff", value=25.3, format="%.2f"
)  # Spot reference ke liye
volatility_gvz = st.sidebar.number_input(
    "Volatility (GVZ %)", value=23.32, format="%.2f"
)

st.sidebar.subheader("Walls & Open Interest (OI)")
call_wall = st.sidebar.number_input(
    "Delta Call Wall Strike", value=4174.70, format="%.2f"
)
call_oi = st.sidebar.number_input("Call OI", value=920, step=10)
futures_ref_call = st.sidebar.number_input(
    "Call Futures Ref", value=4200.00, format="%.2f"
)

put_wall = st.sidebar.number_input(
    "Delta Put Wall Strike", value=4124.70, format="%.2f"
)
put_oi = st.sidebar.number_input("Put OI", value=680, step=10)
futures_ref_put = st.sidebar.number_input(
    "Put Futures Ref", value=4150.00, format="%.2f"
)

current_market_price = st.sidebar.number_input(
    "Current Spot / Market Price", value=4150.00, format="%.2f"
)
daily_range_input = st.sidebar.number_input(
    "Daily Range (±SD Value)", value=60.98, format="%.2f"
)

# --- 2. AUTOMATED QUANT CALCULATIONS ---
spot_ref = futures_price - basis_diff

# SD Level Calculations (Jaise pic mein hain)
sd1_upper = spot_ref + (daily_range_input * 0.5)
sd1_lower = spot_ref - (daily_range_input * 0.5)
sd2_upper = spot_ref + daily_range_input
sd2_lower = spot_ref - daily_range_input

# --- 3. DASHBOARD UI (JESA PIC MEIN HAI) ---
st.markdown("---")

# Top Cards for Walls
col1, col2 = st.columns(2)

with col1:
  st.markdown(
      f"""
    <div style="background-color: #1e1e1e; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;">
        <h4 style="color: #ff4b4b; margin: 0;">DELTA CALL WALL</h4>
        <h2 style="color: white; margin: 5px 0;">${call_wall}</h2>
        <p style="color: #888; margin: 0;">OI: {call_oi} | Futures Ref: ${futures_ref_call}</p>
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
        <p style="color: #888; margin: 0;">OI: {put_oi} | Futures Ref: ${futures_ref_put}</p>
    </div>
    """,
      unsafe_allow_html=True,
  )

st.markdown("<br>", unsafe_allow_html=True)

# Quant Market Outlook Box
st.markdown(
    """
<div style="background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d;">
    <h3 style="color: #f0883e; margin-top: 0;">📊 QUANT MARKET OUTLOOK & REGIME</h3>
""",
    unsafe_allow_html=True,
)

if put_wall <= current_market_price <= call_wall:
  st.markdown(
      f"""
    <p><b>Market Regime:</b> NEUTRAL GEX / SIDEWAYS<br>
    สถานะ Delta สองฝั่งใกล้เคียงกัน ตลาดเคลื่อนไหวในรูปแบบ Range-bound ระหว่าง <b>${put_wall} ถึง ${call_wall}</b>.<br>
    💡 <b>กลยุทธ์แนะนำ:</b> เล่นในกรอบความผันผวน Daily Range ±${daily_range_input} โดยเน้นเข้าเทรดเมื่อราคาเข้าใกล้กรอบ +1SD / -1SD</p>
    """,
      unsafe_allow_html=True,
  )
elif current_market_price > call_wall:
  st.markdown(
      """
    <p style="color: #ff4b4b;"><b>BULLISH BREAKOUT / PUMP SCENARIO ACTIVE:</b> Price Call Wall ko cross kar chuki hai. Momentum expansion expected.</p>
    """,
      unsafe_allow_html=True,
  )
else:
  st.markdown(
      """
    <p style="color: #00cc66;"><b>BEARISH BREAKDOWN / DUMP SCENARIO ACTIVE:</b> Price Put Wall se neechay ja chuki hai. Liquidity grab tracking.</p>
    """,
      unsafe_allow_html=True,
  )

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# SD Levels Table (Jesa pic mein hai)
st.subheader("📉 Standard Deviation (SD) Levels Table")

st.markdown(
    f"""
| SD Level | Spot Upper (+SD) | Spot Lower (-SD) |
| :--- | :--- | :--- |
| **±1 SD (68%)** | `${sd1_upper:.2f}` | `${sd1_lower:.2f}` |
| **±2 SD (95%)** | `${sd2_upper:.2f}` | `${sd2_lower:.2f}` |
""",
    unsafe_allow_html=True,
)

if ops_text_input:
  st.markdown("---")
  st.subheader("📝 Parsed OPS Data Notes")
  st.write(ops_text_input)
