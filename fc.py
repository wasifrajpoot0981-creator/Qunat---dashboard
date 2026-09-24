import streamlit as st
import pandas as pd
import requests
import time

# Page Configuration
st.set_page_config(
    page_title="Top 100+ Crypto Signal Scanner",
    page_icon="🐋",
    layout="wide"
)

st.title("🐋 Top 100+ Crypto 1-Min Long/Short Signal Scanner")
st.markdown("""
Yeh app Binance se live top 100+ USDT pairs ka data fetch karti hai. 
Har 1 minute mein market momentum aur price change ko analyze karke batati hai ke kis coin mein **LONG** banta hai aur kis mein **SHORT**.
""")

# Sidebar Controls
auto_refresh = st.sidebar.checkbox("Auto-Refresh Every 60 Seconds", value=True)
limit_coins = st.sidebar.slider("Select Number of Coins to Scan", 20, 100, 100)

@st.cache_data(ttl=30)
def fetch_binance_top_coins():
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Sirf USDT pairs filter karein
            usdt_pairs = [item for item in data if item['symbol'].endswith('USDT')]
            df = pd.DataFrame(usdt_pairs)
            
            # Data types convert karein
            df['lastPrice'] = df['lastPrice'].astype(float)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['quoteVolume'] = df['quoteVolume'].astype(float)
            
            # Volume ke hisaab se top active coins nikalen
            df = df.sort_values(by='quoteVolume', ascending=False).reset_index(drop=True)
            return df
    except Exception:
        return None
    return None

with st.spinner("Scanning top 100+ coins from Binance..."):
    df = fetch_binance_top_coins()

if df is not None:
    top_df = df.head(limit_coins).copy()
    
    # 1-Minute Signal Logic (Momentum Based)
    signals = []
    for idx, row in top_df.iterrows():
        change = row['priceChangePercent']
        if change > 3.0:
            signals.append("🟢 STRONG LONG")
        elif change > 1.0:
            signals.append("🟢 LONG")
        elif change < -3.0:
            signals.append("🔴 STRONG SHORT")
        elif change < -1.0:
            signals.append("🔴 SHORT")
        else:
            signals.append("⚪ SIDEWAYS")
            
    top_df['Signal'] = signals
    
    # Clean display formatting
    display_df = top_df[['symbol', 'lastPrice', 'priceChangePercent', 'quoteVolume', 'Signal']].copy()
    display_df.columns = ['Coin Pair', 'Price (USDT)', '24h Change (%)', 'Volume (USDT)', 'Signal Action']
    display_df['Price (USDT)'] = display_df['Price (USDT)'].apply(lambda x: f"{x:,.4f}" if x < 1 else f"{x:,.2f}")
    display_df['24h Change (%)'] = display_df['24h Change (%)'].apply(lambda x: f"{x:+.2f}%")
    display_df['Volume (USDT)'] = display_df['Volume (USDT)'].apply(lambda x: f"${x:,.0f}")

    # Summary Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Coins Scanned", len(top_df))
    col2.metric("Long Opportunities", len([s for s in signals if "LONG" in s]))
    col3.metric("Short Opportunities", len([s for s in signals if "SHORT" in s]))

    st.markdown("---")
    
    # Live Table
    st.dataframe(display_df, use_container_width=True, height=600)

else:
    st.error("Binance API se connect nahi ho pa raha. Internet connection check karein.")

# Auto-refresh every 60 seconds
if auto_refresh:
    time.sleep(60)
    st.rerun()
