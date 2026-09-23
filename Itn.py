import streamlit as st
import requests
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="MEXC Iceberg Levels & Signals Dashboard",
    page_icon="🐋",
    layout="wide"
)

TOP_COINS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'BNB_USDT']

# --- ICEBERG ESTIMATION LOGIC ---
class IcebergTracker:
    def estimate_iceberg(self, visible_qty):
        # Research paper math: estimating hidden iceberg volume from visible order book depth
        estimated_total = visible_qty * 2.5 
        return estimated_total

tracker = IcebergTracker()

def fetch_mexc_iceberg_data():
    all_data = []
    
    for symbol in TOP_COINS:
        try:
            url = f"https://www.mexc.com/open/api/v2/market/depth?symbol={symbol}&depth=10"
            response = requests.get(url, timeout=3)
            res_data = response.json()
            
            if 'data' in res_data and res_data['data']:
                data = res_data['data']
                bids = data.get('bids', [])
                asks = data.get('asks', [])
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    current_price = (best_bid + best_ask) / 2
                    
                    # Check Bids (Support / Buy Icebergs)
                    for p_str, q_str in bids:
                        price = float(p_str)
                        qty = float(q_str)
                        if qty >= 0.5:
                            est_total = tracker.estimate_iceberg(qty)
                            distance_pct = abs(current_price - price) / current_price * 100
                            
                            signal = "WAIT (Approaching)"
                            if distance_pct <= 0.8:
                                signal = "🟢 LONG SIGNAL (Support Iceberg Hit)"
                            
                            all_data.append({
                                'Symbol': symbol.replace('_', ''),
                                'Zone': 'Support (Buy Iceberg)',
                                'Wall Price': price,
                                'Current Price': current_price,
                                'Visible Qty': qty,
                                'Est. Hidden Total': est_total,
                                'Distance %': round(distance_pct, 2),
                                'Signal': signal
                            })
                            
                    # Check Asks (Resistance / Sell Icebergs)
                    for p_str, q_str in asks:
                        price = float(p_str)
                        qty = float(q_str)
                        if qty >= 0.5:
                            est_total = tracker.estimate_iceberg(qty)
                            distance_pct = abs(current_price - price) / current_price * 100
                            
                            signal = "WAIT (Approaching)"
                            if distance_pct <= 0.8:
                                signal = "🔴 SHORT SIGNAL (Resistance Iceberg Hit)"
                                
                            all_data.append({
                                'Symbol': symbol.replace('_', ''),
                                'Zone': 'Resistance (Sell Iceberg)',
                                'Wall Price': price,
                                'Current Price': current_price,
                                'Visible Qty': qty,
                                'Est. Hidden Total': est_total,
                                'Distance %': round(distance_pct, 2),
                                'Signal': signal
                            })
        except Exception as e:
            continue
            
    return all_data

# --- STREAMLIT UI DESIGN ---
st.title("🐋 MEXC Iceberg Whale Levels & Live Reversal Dashboard")
st.markdown("Real-time Order Book analysis detecting **Synthetic Iceberg Walls**, **Exact Price Levels**, and **Automated Long/Short Signals**.")

if st.button("🔄 Refresh Live Levels & Signals"):
    st.rerun()

data = fetch_mexc_iceberg_data()

if data:
    df = pd.DataFrame(data)
    active_signals = df[df['Signal'].str.contains('SIGNAL')]
    
    # Metrics Row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Total Whale Icebergs Tracked", value=len(df))
    with col2:
        st.metric(label="Active Reversal Signals", value=len(active_signals))
    with col3:
        st.metric(label="Coins Monitored", value=len(TOP_COINS))
        
    # --- SECTION 1: ACTIVE SIGNALS ---
    st.subheader("🚨 Active Trade Signals (Market at Level)")
    if not active_signals.empty:
        for _, row in active_signals.iterrows():
            if "LONG" in row['Signal']:
                st.success(f"**{row['Symbol']}** | Current: **${row['Current Price']:,.2f}** | Iceberg Wall: **${row['Wall Price']:,.2f}** | Est. Vol: {row['Est. Hidden Total']:.2f} | **{row['Signal']}**")
            else:
                st.error(f"**{row['Symbol']}** | Current: **${row['Current Price']:,.2f}** | Iceberg Wall: **${row['Wall Price']:,.2f}** | Est. Vol: {row['Est. Hidden Total']:.2f} | **{row['Signal']}**")
    else:
        st.info("Market abhi target levels se thori door hai. Neeche diye gaye **Support & Resistance Levels** par nazar rakhein.")
        
    st.markdown("---")
    
    # --- SECTION 2: DEDICATED PRICE LEVELS BOARD ---
    st.subheader("🎯 Key Whale Price Levels Board (Support & Resistance Zones)")
    
    col_sup, col_res = st.columns(2)
    
    with col_sup:
        st.markdown("### 🟢 Support Levels (Buy Walls / Bounce Expected)")
        supports = df[df['Zone'].str.contains('Support')]
        if not supports.empty:
            for _, row in supports.iterrows():
                st.success(f"**{row['Symbol']}** ➔ Level: **${row['Wall Price']:,.2f}**\n\n*Visible Qty:* {row['Visible Qty']} | *Est. Total:* {row['Est. Hidden Total']:.2f} | *Distance:* {row['Distance %']}%")
        else:
            st.info("No active support buy walls found.")
            
    with col_res:
        st.markdown("### 🔴 Resistance Levels (Sell Walls / Rejection Expected)")
        resistances = df[df['Zone'].str.contains('Resistance')]
        if not resistances.empty:
            for _, row in resistances.iterrows():
                st.error(f"**{row['Symbol']}** ➔ Level: **${row['Wall Price']:,.2f}**\n\n*Visible Qty:* {row['Visible Qty']} | *Est. Total:* {row['Est. Hidden Total']:.2f} | *Distance:* {row['Distance %']}%")
        else:
            st.info("No active resistance sell walls found.")
            
    st.markdown("---")
    st.markdown("### 📊 Complete Raw Data Stream")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("Data fetch ho raha hai. 'Refresh Live Levels & Signals' button par click karein.")
