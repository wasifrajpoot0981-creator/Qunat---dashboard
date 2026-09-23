import streamlit as st
import requests
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="MEXC Live Whale & Instant Signal Dashboard",
    page_icon="🐋",
    layout="wide"
)

TOP_COINS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 
    'ADAUSDT', 'AVAXUSDT', 'DOGEUSDT', 'LINKUSDT', 'DOTUSDT'
]

def fetch_mexc_live_signals():
    all_data = []
    
    for symbol in TOP_COINS:
        try:
            url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit=5"
            response = requests.get(url, timeout=2)
            res_data = response.json()
            
            if 'bids' in res_data and 'asks' in res_data:
                bids = res_data['bids']
                asks = res_data['asks']
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    current_price = (best_bid + best_ask) / 2
                    
                    # Support Buy Walls
                    for p_str, q_str in bids:
                        price = float(p_str)
                        qty = float(q_str)
                        if qty >= 0.05: 
                            distance_pct = abs(current_price - price) / current_price * 100
                            
                            signal = "WAIT"
                            # Agar live price level ke bilkul paas hai (within 1%)
                            if distance_pct <= 1.0:
                                signal = "LONG"
                            
                            all_data.append({
                                'Symbol': symbol,
                                'Type': 'Support',
                                'Level': price,
                                'Current Price': current_price,
                                'Volume': qty,
                                'Distance %': round(distance_pct, 2),
                                'Signal': signal
                            })
                            
                    # Resistance Sell Walls
                    for p_str, q_str in asks:
                        price = float(p_str)
                        qty = float(q_str)
                        if qty >= 0.05:
                            distance_pct = abs(current_price - price) / current_price * 100
                            
                            signal = "WAIT"
                            if distance_pct <= 1.0:
                                signal = "SHORT"
                                
                            all_data.append({
                                'Symbol': symbol,
                                'Type': 'Resistance',
                                'Level': price,
                                'Current Price': current_price,
                                'Volume': qty,
                                'Distance %': round(distance_pct, 2),
                                'Signal': signal
                            })
        except Exception as e:
            continue
            
    return all_data

# --- STREAMLIT UI ---
st.title("🐋 Live Price Tracker & Instant Reversal Signals")
st.markdown("Model live MEXC price ko track karta hai aur level hit hone par foran **Long** ya **Short** ka signal deta hai.")

if st.button("🔄 Refresh Live Signals & Levels"):
    st.rerun()

data = fetch_mexc_live_signals()

if data:
    df = pd.DataFrame(data)
    
    # Instant Triggered Signals
    triggered_signals = df[df['Signal'] != 'WAIT']
    
    # --- 1. INSTANT SIGNAL BANNER (TOP) ---
    st.subheader("🚨 Instant Trade Signals (Level Hit)")
    if not triggered_signals.empty:
        for _, row in triggered_signals.iterrows():
            if row['Signal'] == 'LONG':
                st.success(f"🟢 **LONG SIGNAL HIT!** | Coin: **{row['Symbol']}** | Current Price: **${row['Current Price']:,.4f}** | Support Level: **${row['Level']:,.4f}**")
            else:
                st.error(f"🔴 **SHORT SIGNAL HIT!** | Coin: **{row['Symbol']}** | Current Price: **${row['Current Price']:,.4f}** | Resistance Level: **${row['Level']:,.4f}**")
    else:
        st.info("Market abhi levels ke qareeb chal rahi hai. Jaise hi live price exact level ko hit karegi, yahan foran signal aa jayega.")
        
    st.markdown("---")
    
    # --- 2. CLEAN GREEN & RED LEVELS BOARD ---
    st.subheader("🎯 Live Support & Resistance Levels Board")
    col_g, col_r = st.columns(2)
    
    with col_g:
        st.markdown("### 🟢 Green Support Levels (Buy Zones)")
        supports = df[df['Type'] == 'Support']
        if not supports.empty:
            for _, row in supports.iterrows():
                st.success(f"**{row['Symbol']}** ➔ **${row['Level']:,.4f}**\n\n*(Current: ${row['Current Price']:,.4f} | Dist: {row['Distance %']}%)*")
        else:
            st.info("No support levels found.")
            
    with col_r:
        st.markdown("### 🔴 Red Resistance Levels (Sell Zones)")
        resistances = df[df['Type'] == 'Resistance']
        if not resistances.empty:
            for _, row in resistances.iterrows():
                st.error(f"**{row['Symbol']}** ➔ **${row['Level']:,.4f}**\n\n*(Current: ${row['Current Price']:,.4f} | Dist: {row['Distance %']}%)*")
        else:
            st.info("No resistance levels found.")
            
else:
    st.warning("Live data load ho raha hai. Button par click karein.")
