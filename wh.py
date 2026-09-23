import streamlit as st
import asyncio
import json
import threading
import time
from datetime import datetime, timezone

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Whale Iceberg & Price Level Tracker",
    page_icon="🐋",
    layout="wide"
)

# --- GLOBAL SHARED STATE ---
class AppState:
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()
        self.status = "Disconnected ❌"

state = AppState()

# --- ICEBERG TRACKER CLASS ---
class IcebergTracker:
    def __init__(self):
        self.tranches = []
        self.resting_volume = 0.0
        
    def process_trade(self, trade_volume, visible_volume):
        self.tranches.append(trade_volume)
        self.resting_volume = visible_volume
        
        if len(self.tranches) >= 2:
            v_peak = max(self.tranches)
            estimated_total = sum(self.tranches) + self.resting_volume
            return v_peak, estimated_total
        return 0.0, 0.0

tracker = IcebergTracker()

# --- BACKGROUND WEBSOCKET THREAD ---
def run_websocket_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def consume():
        import websockets
        uri = "wss://fstream.binance.com/ws/!forceOrder@arr"
        while True:
            try:
                state.status = "Connecting to Binance... 🔄"
                async with websockets.connect(uri) as websocket:
                    state.status = "Connected & Tracking Whales 🟢"
                    async for message in websocket:
                        data = json.loads(message)
                        order_data = data.get('o', {})
                        
                        side = order_data.get('S') # SELL = Long Liquidated (Support level), BUY = Short Liquidated (Resistance level)
                        price = float(order_data.get('p', 0))
                        amount = float(order_data.get('q', 0))
                        symbol = order_data.get('s', 'UNKNOWN')
                        
                        # Filter for high value whales (0.5+ BTC)
                        if amount >= 0.5:
                            v_peak, est_total = tracker.process_trade(amount, amount * 0.2)
                            
                            with state.lock:
                                state.events.insert(0, {
                                    'time': datetime.now(timezone.utc).strftime('%H:%M:%S'),
                                    'symbol': symbol,
                                    'side': side,
                                    'price': price,
                                    'amount': amount,
                                    'v_peak': v_peak,
                                    'est_total': est_total
                                })
                                if len(state.events) > 50:
                                    state.events.pop()
            except Exception as e:
                state.status = f"Reconnecting... (Error: {e})"
                await asyncio.sleep(5)

    loop.run_until_complete(consume())

@st.cache_resource
def start_bg_thread():
    t = threading.Thread(target=run_websocket_thread, daemon=True)
    t.start()

start_bg_thread()

# --- STREAMLIT DASHBOARD UI ---
st.title("🐋 Whale Iceberg & Turning Level Detector")
st.markdown("Real-time Order Flow tracking to identify exact Price Levels where Whales trigger Reversals.")

st.sidebar.header("System Status")
st.sidebar.info(state.status)

# Metrics Row
col1, col2, col3 = st.columns(3)

with state.lock:
    current_events = list(state.events)

sell_vol = sum(ev['amount'] for ev in current_events if ev['side'] == 'SELL')
buy_vol = sum(ev['amount'] for ev in current_events if ev['side'] == 'BUY')

with col1:
    st.metric(label="Total Whale Events", value=len(current_events))
with col2:
    st.metric(label="Long Washout Vol (Support)", value=f"{sell_vol:.2f} BTC")
with col3:
    st.metric(label="Short Washout Vol (Resistance)", value=f"{buy_vol:.2f} BTC")

# --- EXACT TURNING PRICE LEVELS SECTION ---
st.subheader("🎯 Key Whale Turning Levels (Support & Resistance Zones)")

if current_events:
    col_level1, col_level2 = st.columns(2)
    
    # Extract recent major levels
    support_levels = [ev['price'] for ev in current_events if ev['side'] == 'SELL']
    resistance_levels = [ev['price'] for ev in current_events if ev['side'] == 'BUY']
    
    with col_level1:
        st.markdown("### 🟢 Support Zones (Long Entry Levels)")
        if support_levels:
            # Show top unique recent support price levels
            unique_supports = sorted(list(set(support_levels)), reverse=True)[:5]
            for p in unique_supports:
                st.success(f"**Price Level: ${p:,.2f}** — *(Whale Long Washout / Bounce Expected)*")
        else:
            st.info("Waiting for major long liquidations...")
            
    with col_level2:
        st.markdown("### 🔴 Resistance Zones (Short Entry Levels)")
        if resistance_levels:
            unique_resistances = sorted(list(set(resistance_levels)), reverse=True)[:5]
            for p in unique_resistances:
                st.error(f"**Price Level: ${p:,.2f}** — *(Whale Short Squeeze / Rejection Expected)*")
        else:
            st.info("Waiting for major short liquidations...")
else:
    st.warning("Listening for market activity to calculate turning levels...")

# Live Events Table
st.subheader("📊 Live Whale Order Stream & Iceberg Estimates")
if current_events:
    st.dataframe(current_events, use_container_width=True)
else:
    st.info("Waiting for incoming whale orders...")

# Auto refresh dashboard every 3 seconds
time.sleep(3)
st.rerun()
