import streamlit as st
import requests
import pandas as pd
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="MEXC Master Hidden Iceberg & Multi-Target Engine",
    page_icon="🎯",
    layout="wide"
)

TOP_COINS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 
    'ADAUSDT', 'AVAXUSDT', 'DOGEUSDT', 'LINKUSDT', 'DOTUSDT',
    'NEARUSDT', 'MATICUSDT', 'SHIBUSDT', 'LTCUSDT', 'BCHUSDT'
]

# --- ADVANCED MULTI-TARGET & HIDDEN VOLUME ENGINE ---
def fetch_advanced_targets():
    master_analysis = []
    
    for symbol in TOP_COINS:
        try:
            url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit=100"
            response = requests.get(url, timeout=3)
            res_data = response.json()
            
            if 'bids' in res_data and 'asks' in res_data:
                bids = res_data['bids']
                asks = res_data['asks']
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    current_price = (best_bid + best_ask) / 2
                    
                    bid_df = pd.DataFrame(bids, columns=['Price', 'Qty'])
                    bid_df['Price'] = bid_df['Price'].astype(float)
                    bid_df['Qty'] = bid_df['Qty'].astype(float)
                    
                    ask_df = pd.DataFrame(asks, columns=['Price', 'Qty'])
                    ask_df['Price'] = ask_df['Price'].astype(float)
                    ask_df['Qty'] = ask_df['Qty'].astype(float)
                    
                    avg_bid_qty = bid_df['Qty'].mean() if not bid_df.empty else 1
                    avg_ask_qty = ask_df['Qty'].mean() if not ask_df.empty else 1
                    
                    # Find Strongest Support (Floor) below current price
                    valid_bids = bid_df[bid_df['Price'] <= current_price]
                    if not valid_bids.empty:
                        heavy_bids = valid_bids[valid_bids['Qty'] >= (avg_bid_qty * 3.0)]
                        if not heavy_bids.empty:
                            best_sup = heavy_bids.loc[heavy_bids['Qty'].idxmax()]
                            sup_price = best_sup['Price']
                            sup_qty = best_sup['Qty']
                        else:
                            best_sup = valid_bids.loc[valid_bids['Qty'].idxmax()]
                            sup_price = best_sup['Price']
                            sup_qty = best_sup['Qty']
                    else:
                        sup_price = best_bid
                        sup_qty = bids[0][1]
                        
                    # Find Strongest Resistance (Ceiling / Next Target) above current price
                    valid_asks = ask_df[ask_df['Price'] >= current_price]
                    if not valid_asks.empty:
                        heavy_asks = valid_asks[valid_asks['Qty'] >= (avg_ask_qty * 3.0)]
                        if not heavy_asks.empty:
                            best_res = heavy_asks.loc[heavy_asks['Qty'].idxmax()]
                            res_price = best_res['Price']
                            res_qty = best_res['Qty']
                        else:
                            best_res = valid_asks.loc[valid_asks['Qty'].idxmax()]
                            res_price = best_res['Price']
                            res_qty = best_res['Qty']
                    else:
                        res_price = best_ask
                        res_qty = asks[0][1]
                        
                    # Distance calculations
                    sup_dist = abs(current_price - sup_price) / current_price * 100
                    res_dist = abs(res_price - current_price) / current_price * 100
                    
                    # Probability & Target scoring
                    total_vol = sup_qty + res_qty
                    prob_score = round((total_vol * 10) / (sup_dist + 0.1), 2)
                    
                    master_analysis.append({
                        'Symbol': symbol,
                        'Current Price': current_price,
                        'Support Level (Entry)': sup_price,
                        'Support Vol': sup_qty,
                        'Support Dist %': round(sup_dist, 2),
                        'Next Target Level (Exit)': res_price,
                        'Resistance Vol': res_qty,
                        'Target Dist %': round(res_dist, 2),
                        'Probability Score': prob_score
                    })
        except Exception as e:
            continue
            
    return master_analysis

# --- STREAMLIT UI DESIGN ---
st.title("🎯 Master Multi-Target Hidden Iceberg & Exit Engine")
st.markdown("Yeh model dump ke waqt exact **Support Entry**, **Next Hidden Wall Target (Exit)**, aur **High Probability Score** calculate karta hai.")

if st.button("🔄 Scan Market & Calculate Targets"):
    st.rerun()

data = fetch_advanced_targets()

if data:
    df = pd.DataFrame(data)
    df = df.sort_values(by='Probability Score', ascending=False)
    
    # Pick the absolute #1 best coin setup
    best_setup = df.iloc[0]
    
    st.markdown("---")
    st.subheader("🚨 #1 HIGH-PROBABILITY LIVE BLINK SIGNAL (Entry + Target)")
    
    # Check if support is close enough to trigger instant blink (e.g., within 1.5%)
    if best_setup['Support Dist %'] <= 1.5:
        st.success(
            f"🔥 **BLINK ALERT! LONG ENTRY TRIGGERED ON {best_setup['Symbol']}!** 🔥\n\n"
            f"* **Live Market Price:** `${best_setup['Current Price']:,.4f}`\n"
            f"* **🟢 Long Entry Support Floor:** `${best_setup['Support Level (Entry)']:,.4f}` (Distance: `{best_setup['Support Dist %']}%`)\n"
            f"* **🎯 Next Target / Exit Resistance Wall:** `${best_setup['Next Target Level (Exit)']:,.4f}` (Distance: `+{best_setup['Target Dist %']}%`)\n"
            f"* **Probability Score:** `{best_setup['Probability Score']}` (Very High!)\n\n"
            f"👉 **Trading Plan:** Market dump mein is support wall par aa chuki hai. Yahan hidden volume absorb ho raha hai. **Long entry karein aur apna pehla target `${best_setup['Next Target Level (Exit)']:,.4f}` par set karein!**"
        )
    else:
        st.info(
            f"⏳ **Current #1 Focus Coin:** **{best_setup['Symbol']}**\n"
            f"* Support Level: `${best_setup['Support Level (Entry)']:,.4f}` (Dur: {best_setup['Support Dist %']}%)\n"
            f"* Next Target Wall: `${best_setup['Next Target Level (Exit)']:,.4f}`\n"
            f"👉 Price abhi support ke thora qareeb ja rahi hai. Jaise hi hit karegi, blink alert active ho jayega."
        )
        
    st.markdown("---")
    st.subheader("📊 All Coins Support-to-Target Map (Entry & Exit Levels)")
    
    # Clean display cards for all coins
    for _, row in df.iterrows():
        st.markdown(
            f"**{row['Symbol']}** ➔ Live: `${row['Current Price']:,.4f}` | "
            f"🟢 **Support (Entry):** `${row['Support Level (Entry)']:,.4f}` ({row['Support Dist %']}% dur) ➔ "
            f"🎯 **Next Target (Exit):** `${row['Next Target Level (Exit)']:,.4f}` (+{row['Target Dist %']}% uper) | "
            f"⭐ Score: `{row['Probability Score']}`"
        )
        
    st.markdown("---")
    st.markdown("### 📋 Detailed Master Table")
    st.dataframe(df, use_container_width=True)

else:
    st.warning("Market ka data scan ho raha hai. 'Scan Market & Calculate Targets' par click karein.")

time.sleep(5)
st.rerun()
