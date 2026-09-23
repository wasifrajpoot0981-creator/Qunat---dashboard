import streamlit as st
import requests
import pandas as pd
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="MEXC Dynamic Volume-Driven Iceberg Engine",
    page_icon="⚡",
    layout="wide"
)

# Initialize Session State
if 'active_signal' not in st.session_state:
    st.session_state.active_signal = None
if 'signal_timestamp' not in st.session_state:
    st.session_state.signal_timestamp = 0
if 'ignored_coins' not in st.session_state:
    st.session_state.ignored_coins = {} # Cooldown tracker

@st.cache_data(ttl=60) # Cache for 60 seconds to avoid API spamming
def get_top_volume_coins(limit=35):
    """Automatically fetch top volume USDT coins from MEXC live market"""
    try:
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        usdt_pairs = []
        for item in data:
            symbol = item.get('symbol', '')
            if symbol.endswith('USDT'):
                quote_vol = float(item.get('quoteVolume', 0))
                # Exclude leveraged tokens like UP/DOWN
                if 'UP' not in symbol and 'DOWN' not in symbol and 'BEAR' not in symbol and 'BULL' not in symbol:
                    usdt_pairs.append({'symbol': symbol, 'volume': quote_vol})
                    
        # Sort by highest 24h volume
        usdt_pairs = sorted(usdt_pairs, key=lambda x: x['volume'], reverse=True)
        top_symbols = [p['symbol'] for p in usdt_pairs[:limit]]
        return top_symbols
    except Exception as e:
        # Fallback list if API fails
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOGEUSDT', 'LINKUSDT', 'PEPEUSDT']

def scan_iceberg_resistance_market():
    current_time = time.time()
    
    # Clear cooldowns older than 60 seconds
    expired_cooldowns = [sym for sym, t in st.session_state.ignored_coins.items() if current_time - t > 60]
    for sym in expired_cooldowns:
        del st.session_state.ignored_coins[sym]
        
    all_candidates = []
    
    # Automatically get top active volume coins right now
    active_coins = get_top_volume_coins(limit=35)
    
    for symbol in active_coins:
        if symbol in st.session_state.ignored_coins:
            continue
            
        try:
            # Fetch Order Book Depth (100 limits for deep iceberg walls)
            url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit=100"
            response = requests.get(url, timeout=2)
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
                    
                    # 1. LONG SETUP: Hidden Support Iceberg
                    valid_bids = bid_df[bid_df['Price'] <= current_price]
                    if not valid_bids.empty:
                        heavy_bids = valid_bids[valid_bids['Qty'] >= (avg_bid_qty * 3.0)]
                        target_bid = heavy_bids.loc[heavy_bids['Qty'].idxmax()] if not heavy_bids.empty else valid_bids.loc[valid_bids['Qty'].idxmax()]
                        
                        sup_price = target_bid['Price']
                        sup_qty = target_bid['Qty']
                        sup_dist = abs(current_price - sup_price) / current_price * 100
                        
                        valid_asks = ask_df[ask_df['Price'] >= current_price]
                        if not valid_asks.empty:
                            heavy_asks = valid_asks[valid_asks['Qty'] >= (avg_ask_qty * 2.5)]
                            target_ask = heavy_asks.iloc[0] if not heavy_asks.empty else valid_asks.iloc[0]
                            next_resistance = target_ask['Price']
                        else:
                            next_resistance = current_price * 1.025
                            
                        target_dist_pct = abs(next_resistance - current_price) / current_price * 100
                        leverage_multiplier = 20
                        estimated_profit_pct = round(target_dist_pct * leverage_multiplier, 2)
                        
                        prob_score = round((sup_qty * 15) / (sup_dist + 0.05), 2)
                        
                        if prob_score >= 80:
                            prob_tag = "🚀 HIGH PROBABILITY ICEBERG LONG"
                        else:
                            prob_tag = "⚡ MEDIUM PROBABILITY SETUP"
                            
                        if sup_dist <= 2.5:
                            all_candidates.append({
                                'Symbol': symbol,
                                'Action Type': 'LONG SETUP (Hidden Support Absorption)',
                                'RecommendedAction': '🟢 LONG KARNA HAI (Support wall par price ruk kar upar jayegi)',
                                'Current Price': current_price,
                                'Level Price': sup_price,
                                'Target Price': next_resistance,
                                'Target Distance %': round(target_dist_pct, 2),
                                'Estimated Profit (20x)': estimated_profit_pct,
                                'Iceberg Volume': sup_qty,
                                'Distance %': round(sup_dist, 2),
                                'Probability Score': prob_score,
                                'Probability Tag': prob_tag
                            })
                            
                    # 2. SHORT SETUP: Hidden Resistance Iceberg
                    valid_asks = ask_df[ask_df['Price'] >= current_price]
                    if not valid_asks.empty:
                        heavy_asks = valid_asks[valid_asks['Qty'] >= (avg_ask_qty * 3.0)]
                        target_ask = heavy_asks.loc[heavy_asks['Qty'].idxmax()] if not heavy_asks.empty else valid_asks.loc[valid_asks['Qty'].idxmax()]
                        
                        res_price = target_ask['Price']
                        res_qty = target_ask['Qty']
                        res_dist = abs(res_price - current_price) / current_price * 100
                        
                        valid_bids_down = bid_df[bid_df['Price'] <= current_price]
                        next_support = valid_bids_down.iloc[0]['Price'] if not valid_bids_down.empty else current_price * 0.98
                        
                        target_dist_pct = abs(current_price - next_support) / current_price * 100
                        leverage_multiplier = 20
                        estimated_profit_pct = round(target_dist_pct * leverage_multiplier, 2)
                        
                        prob_score = round((res_qty * 15) / (res_dist + 0.05), 2)
                        
                        if prob_score >= 80:
                            prob_tag = "🚀 HIGH PROBABILITY RESISTANCE SHORT"
                        else:
                            prob_tag = "⚡ MEDIUM PROBABILITY SETUP"
                            
                        if res_dist <= 2.5:
                            all_candidates.append({
                                'Symbol': symbol,
                                'Action Type': 'SHORT SETUP (Heavy Resistance Wall)',
                                'RecommendedAction': '🔴 SHORT KARNA HAI (Resistance par price ruk kar neeche giregi)',
                                'Current Price': current_price,
                                'Level Price': res_price,
                                'Target Price': next_support,
                                'Target Distance %': round(target_dist_pct, 2),
                                'Estimated Profit (20x)': estimated_profit_pct,
                                'Iceberg Volume': res_qty,
                                'Distance %': round(res_dist, 2),
                                'Probability Score': prob_score,
                                'Probability Tag': prob_tag
                            })
        except Exception as e:
            continue
            
    all_candidates = sorted(all_candidates, key=lambda x: x['Probability Score'], reverse=True)
    return all_candidates

# --- STREAMLIT UI ---
st.title("⚡ MEXC Dynamic Top-Volume Iceberg & Resistance Engine")
st.markdown("Yeh model khud MEXC se **Top Volume wale active coins** automatically uthata hai aur unmein hidden iceberg walls scan karta hai.")

if st.button("🔄 Force Refresh Scanner"):
    st.session_state.active_signal = None
    st.rerun()

current_time = time.time()

# Expiration check for active signal (60 seconds)
if st.session_state.active_signal and (current_time - st.session_state.signal_timestamp > 60):
    expired_sym = st.session_state.active_signal['Symbol']
    st.session_state.ignored_coins[expired_sym] = current_time
    st.session_state.active_signal = None

candidates = scan_iceberg_resistance_market()

if not st.session_state.active_signal and candidates:
    st.session_state.active_signal = candidates[0]
    st.session_state.signal_timestamp = current_time
    candidates = scan_iceberg_resistance_market()

# --- DISPLAY ACTIVE SIGNAL ---
if st.session_state.active_signal:
    sig = st.session_state.active_signal
    elapsed = int(current_time - st.session_state.signal_timestamp)
    time_left = max(0, 60 - elapsed)
    
    st.markdown("---")
    st.subheader(f"🚨 ACTIVE ICEBERG SIGNAL (Auto-Expires in {time_left}s)")
    
    if "LONG" in sig['RecommendedAction']:
        st.success(
            f"🔥 **ACTIVE SIGNAL: {sig['Symbol']}** 🔥\n\n"
            f"* **🎯 Signal Quality:** `{sig['Probability Tag']}` (Score: `{sig['Probability Score']}`)\n"
            f"* **Kya Karna Hai?** ➔ **{sig['RecommendedAction']}**\n"
            f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Hidden Support Wall:** `${sig['Level Price']:,.4f}`\n"
            f"* **📊 Iceberg Volume:** `{sig['Iceberg Volume']:,.2f}`\n"
            f"* **🎯 Next Resistance Target:** `${sig['Target Price']:,.4f}` (Distance: `+{sig['Target Distance %']}%`)\n"
            f"* **💰 Estimated Profit (at 20x Leverage):** `+{sig['Estimated Profit (20x)']}%` 🚀\n\n"
            f"👉 **Exit Rule:** Support par price ruk chuki hai, long open karein aur jaise hi target resistance `${sig['Target Price']:,.4f}` par price aaye, trade close kar dein!"
        )
    else:
        st.error(
            f"🔥 **ACTIVE SIGNAL: {sig['Symbol']}** 🔥\n\n"
            f"* **🎯 Signal Quality:** `{sig['Probability Tag']}` (Score: `{sig['Probability Score']}`)\n"
            f"* **Kya Karna Hai?** ➔ **{sig['RecommendedAction']}**\n"
            f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Hidden Resistance Wall:** `${sig['Level Price']:,.4f}`\n"
            f"* **📊 Iceberg Volume:** `{sig['Iceberg Volume']:,.2f}`\n"
            f"* **🎯 Support Drop Target:** `${sig['Target Price']:,.4f}` (Distance: `{sig['Target Distance %']}%`)\n"
            f"* **💰 Estimated Short Profit (at 20x):** `+{sig['Estimated Profit (20x)']}%` 🚀\n\n"
            f"👉 **Exit Rule:** Resistance par price ruk kar reject ho rahi hai, short open karein aur target support par trade close kar dein!"
        )
        
    st.progress(time_left / 60.0)
    st.markdown("---")
else:
    st.info("⏳ Market scan ho rahi hai... agla hidden iceberg signal jald aane wala hai.")

# --- NEXT-QUEUE WATCHLIST ---
st.subheader("🔮 Next-Queue Iceberg Walls & Target Resistance")
st.markdown("Yeh aglay queue wale coins hain jo hidden levels par kharay hain:")

if candidates:
    queue_list = [c for c in candidates if not st.session_state.active_signal or c['Symbol'] != st.session_state.active_signal['Symbol']]
    
    if queue_list:
        for idx, item in enumerate(queue_list[:3], 1):
            st.info(
                f"**#{idx} Next Coin:** **{item['Symbol']}**\n"
                f"* 🎯 **Quality / Tag:** `{item['Probability Tag']}` (Score: `{item['Probability Score']}`)\n"
                f"* 🎯 **Action:** **{item['RecommendedAction']}**\n"
                f"* 📊 **Iceberg Vol:** `{item['Iceberg Volume']:,.2f}` | **Target Distance:** `+{item['Target Distance %']}%`\n"
                f"* 💰 **Est. Profit (20x):** `+{item['Estimated Profit (20x)']}%` | **Target:** `${item['Target Price']:,.4f}`"
            )
    else:
        st.write("Baaki coins abhi apne levels par absorb nahi ho rahe.")
else:
    st.warning("Filhal koi doosra iceberg candidate queue mein nahi hai.")

time.sleep(5)
st.rerun()
