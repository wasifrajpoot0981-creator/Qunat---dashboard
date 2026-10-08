import numpy as np
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="YIAWDAMZ-OPS Quant Engine", page_icon="📈", layout="centered"
)

st.title("YIAWDAMZ-OPS: Dynamic Wall & Direction Engine")
st.write(
    "Screenshots upload karein aur market data ke mutabiq live direction aur"
    " walls check karein."
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
  st.metric(
      label="DELTA CALL WALL (Upper Resistance)",
      value=f"${call_wall:.2f}",
      delta="Upper Boundary",
  )

with col2:
  st.metric(
      label="DELTA PUT WALL (Lower Support)",
      value=f"${put_wall:.2f}",
      delta="Lower Boundary",
      delta_value_color="inverse",
  )

st.markdown("---")

# Metrics Overview Box
st.subheader("📊 Live Market Status & Summary")
st.info(
    f"GVZ Volatility: {volatility_gvz}% | Spot Reference: ${spot_ref:.2f} |"
    f" Live Price: ${current_market_price}"
)

# Direction Logic for Market Rise, Fall, or Range
if put_wall <= current_market_price <= call_wall:
  st.success(
      "Market Regime: SIDEWAYS / IN-RANGE\n\n"
      f"Market apni Put Wall (${put_wall}) aur Call Wall (${call_wall}) ke beech"
      " ghoom rahi hai.\n- Agar market upar uthti hai: Target Call Wall"
      f" (${call_wall}) hoga.\n- Agar market neechay girti hai: Target Put Wall"
      f" (${put_wall}) hoga."
  )
elif current_market_price > call_wall:
  st.error(
      "🔥 BULLISH PUMP ACTIVE (Call Wall Breached!)\n\n"
      f"Market ne upar ki taraf move karke Call Wall (${call_wall}) ko cross kar"
      " liya hai. Upar ki taraf volatility expansion aur momentum jari hai!"
  )
else:
  st.warning(
      "⚠️ BEARISH DUMP ACTIVE (Put Wall Breached!)\n\n"
      f"Market girte hue Put Wall (${put_wall}) ko bhi tod kar neechay chali"
      " gayi hai. Neechay ki taraf liquidity grab aur breakdown active hai!"
  )

# SD Levels Table
st.markdown("---")
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
