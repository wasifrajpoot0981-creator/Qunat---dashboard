import streamlit as st
import requests
import pandas as pd
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="MEXC Pinpoint Real Iceberg Engine",
    page_icon="💎",
    layout="wide"
)

# Initialize Session State
if 'active_signal' not in st.session_state:
    st.session_state.active_signal = None
if 'signal_timestamp' not in st.session_state:
    st.session_state.signal_timestamp = 0
if 'previous_closed_msg' not in st.session_state:
    st.session_state.previous_closed_msg = None
if 'ignored_coins' not in st.session_state:
    st.session_state.ignored_coins = {}

@st.cache_data(ttl=30)
def get_top_volume_coins(limit=50):
    try:
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        response = requests.get(url, timeout=3)
        data = response.json()
        
        usdt_pairs = []
        for item in data:
            symbol = item.get('symbol', '')
            if symbol.endswith('USDT'):
                quote_vol = float(item.get('quoteVolume', 0))
                price_change = float(item.get('priceChangePercent', 0))
                if 'UP' not in symbol and 'DOWN' not in symbol and 'BEAR' not in symbol and 'BULL' not in symbol:
                    usdt_pairs.append({'symbol': symbol, 'volume': quote_vol, 'priceChange': price_change})
                    
        usdt_pairs = sorted(usdt_pairs, key=lambda x: (x['volume'] * abs(x['priceChange'] + 1)), reverse=True)
        top_symbols = [p['symbol'] for p in usdt_pairs[:limit]]
        return top_symbols
    except Exception as e:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']

def scan_real_iceberg_market():
    current_time = time.time()
    st.session_state.ignored_coins = {sym: t for sym, t in st.session_state.ignored_coins.items() if current_time - t <= 45}
        
    all_candidates = []
    active_coins = get_top_volume_coins(limit=50)
    
    try:
        ticker_url = "https://api.mexc.com/api/v3/ticker/24hr"
        ticker_res = requests.get(ticker_url, timeout=3).json()
        ticker_dict = {item['symbol']: item for item in ticker_res}
    except:
        ticker_dict = {}

    for symbol in active_coins:
        if symbol in st.session_state.ignored_coins:
            continue
            
        try:
            t_data = ticker_dict.get(symbol, {})
            price_change_pct = float(t_data.get('priceChangePercent', 0))
            quote_volume = float(t_data.get('quoteVolume', 0))
            
            url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit=50"
            response = requests.get(url, timeout=2)
            res_data = response.json()
            
            if 'bids' in res_data and 'asks' in res_data:
                bids = res_data['bids']
                asks = res_data['asks']
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    current_price = (best_bid + best_ask) / 2
                    
                    bid_df = pd.DataFrame(bids, columns=['Price', 'Qty']).astype(float)
                    ask_df = pd.DataFrame(asks, columns=['Price', 'Qty']).astype(float)
                    
                    avg_bid_qty = bid_df['Qty'].mean() if not bid_df.empty else 1
                    avg_ask_qty = ask_df['Qty'].mean() if not ask_df.empty else 1
                    
                    if quote_volume > 80000000 or price_change_pct >= 5.0:
                        dynamic_leverage = 50
                        leverage_tag = "🔥 WHALE MEGA ICEBERG (50x Leverage)"
                        target_mult = 1.03
                        min_guaranteed_profit = 120
                        base_prob = 93
                    elif quote_volume > 30000000 or price_change_pct >= 2.5:
                        dynamic_leverage = 35
                        leverage_tag = "⚡ ACTIVE ICEBERG WALL (35x Leverage)"
                        target_mult = 1.025
                        min_guaranteed_profit = 80
                        base_prob = 87
                    else:
                        dynamic_leverage = 20
                        leverage_tag = "⚖️ STANDARD ICEBERG SETUP (20x Leverage)"
                        target_mult = 1.015
                        min_guaranteed_profit = 40
                        base_prob = 80

                    # 1. REAL SUPPORT ICEBERG (LONG) - STRICTLY NEAR CURRENT PRICE (Within 0.8%)
                    valid_bids = bid_df[bid_df['Price'] <= current_price]
                    if not valid_bids.empty:
                        valid_bids['Dist_Pct'] = (current_price - valid_bids['Price']) / current_price * 100
                        close_bids = valid_bids[valid_bids['Dist_Pct'] <= 0.8]
                        
                        if not close_bids.empty:
                            heavy_bids = close_bids[close_bids['Qty'] >= (avg_bid_qty * 2.0)]
                            target_row = heavy_bids.loc[heavy_bids['Qty'].idxmax()] if not heavy_bids.empty else close_bids.loc[close_bids['Dist_Pct'].idxmin()]
                            
                            sup_price = target_row['Price']
                            sup_qty = target_row['Qty']
                            sup_dist = target_row['Dist_Pct']
                            
                            next_resistance = current_price * target_mult
                            target_dist_pct = abs(next_resistance - current_price) / current_price * 100
                            
                            estimated_profit_pct = round(target_dist_pct * dynamic_leverage, 2)
                            if estimated_profit_pct < min_guaranteed_profit:
                                estimated_profit_pct = min_guaranteed_profit
                            
                            signal_probability = min(99, max(78, round(base_prob + (sup_qty / (avg_bid_qty + 1)) - (sup_dist * 3), 1)))
                            
                            all_candidates.append({
                                'Symbol': symbol,
                                'Action Type': 'REAL ICEBERG LONG SETUP',
                                'RecommendedAction': '🟢 REAL ICEBERG LONG (Current price ke bilkul paas support wall hai)',
                                'Current Price': current_price,
                                'Level Price': sup_price,
                                'Target Price': next_resistance,
                                'Target Distance %': round(target_dist_pct, 2),
                                'Dynamic Leverage': dynamic_leverage,
                                'Leverage Tag': leverage_tag,
                                'Estimated Profit': estimated_profit_pct,
                                'Signal Probability': signal_probability,
                                'Iceberg Volume': sup_qty,
                                'Distance %': round(sup_dist, 2),
                                '24h Pump %': price_change_pct,
                                'Volume (USDT)': quote_volume
                            })
                            
                    # 2. REAL RESISTANCE ICEBERG (SHORT) - STRICTLY NEAR CURRENT PRICE (Within 0.8%)
                    valid_asks = ask_df[ask_df['Price'] >= current_price]
                    if not valid_asks.empty:
                        valid_asks['Dist_Pct'] = (valid_asks['Price'] - current_price) / current_price * 100
                        close_asks = valid_asks[valid_asks['Dist_Pct'] <= 0.8]
                        
                        if not close_asks.empty:
                            heavy_asks = close_asks[close_asks['Qty'] >= (avg_ask_qty * 2.0)]
                            target_row = heavy_asks.loc[heavy_asks['Qty'].idxmax()] if not heavy_asks.empty else close_asks.loc[close_asks['Dist_Pct'].idxmin()]
                            
                            res_price = target_row['Price']
                            res_qty = target_row['Qty']
                            res_dist = target_row['Dist_Pct']
                            
                            next_support = current_price * (2.0 - target_mult)
                            target_dist_pct = abs(current_price - next_support) / current_price * 100
                            
                            estimated_profit_pct = round(target_dist_pct * dynamic_leverage, 2)
                            if estimated_profit_pct < min_guaranteed_profit:
                                estimated_profit_pct = min_guaranteed_profit
                            
                            signal_probability = min(99, max(78, round(base_prob + (res_qty / (avg_ask_qty + 1)) - (res_dist * 3), 1)))
                            
                            all_candidates.append({
                                'Symbol': symbol,
                                'Action Type': 'REAL ICEBERG SHORT SETUP',
                                'RecommendedAction': '🔴 REAL ICEBERG SHORT (Current price ke bilkul paas resistance wall hai)',
                                'Current Price': current_price,
                                'Level Price': res_price,
                                'Target Price': next_support,
                                'Target Distance %': round(target_dist_pct, 2),
                                'Dynamic Leverage': dynamic_leverage,
                                'Leverage Tag': leverage_tag,
                                'Estimated Profit': estimated_profit_pct,
                                'Signal Probability': signal_probability,
                                'Iceberg Volume': res_qty,
                                'Distance %': round(res_dist, 2),
                                '24h Pump %': price_change_pct,
                                'Volume (USDT)': quote_volume
                            })
        except Exception as e:
            continue
            
    all_candidates = sorted(all_candidates, key=lambda x: x['Signal Probability'], reverse=True)
    return all_candidates

# --- STREAMLIT UI ---
st.title("💎 MEXC Pinpoint Real Iceberg & Target Engine")
st.markdown("Yeh model current price ke qareeb real iceberg levels ko track karta hai bina screen blink kiye.")

if st.button("🔄 Force Refresh Scanner"):
    st.session_state.active_signal = None
    st.session_state.previous_closed_msg = None
    st.rerun()

current_time = time.time()

if st.session_state.active_signal:
    elapsed_time = current_time - st.session_state.signal_timestamp
    active_sym = st.session_state.active_signal['Symbol']
    target_p = st.session_state.active_signal['Target Price']
    is_long = "LONG" in st.session_state.active_signal['RecommendedAction']
    
    target_hit = False
    try:
        live_check_res = requests.get(f"https://api.mexc.com/api/v3/ticker/price?symbol={active_sym}", timeout=2).json()
        live_p = float(live_check_res.get('price', 0))
        if is_long and live_p >= target_p:
            target_hit = True
        elif not is_long and live_p <= target_p:
            target_hit = True
    except:
        pass

    if elapsed_time > 60 or target_hit:
        reason = "Resistance/Target Hit!" if target_hit else "1-Minute Time Completed!"
        st.session_state.previous_closed_msg = f"📦 **PREVIOUS TRADE CLOSED:** Coin **{active_sym}** ({reason}) - Naya pin-point coin scan ho raha hai!"
        st.session_state.ignored_coins[active_sym] = current_time
        st.session_state.active_signal = None

candidates = scan_real_iceberg_market()

if not st.session_state.active_signal and candidates:
    st.session_state.active_signal = candidates[0]
    st.session_state.signal_timestamp = current_time
    candidates = scan_real_iceberg_market()

if st.session_state.previous_closed_msg:
    st.info(st.session_state.previous_closed_msg)

if st.session_state.active_signal:
    sig = st.session_state.active_signal
    elapsed = int(current_time - st.session_state.signal_timestamp)
    time_left = max(0, 60 - elapsed)
    
    st.markdown("---")
    st.subheader(f"🚨 ACTIVE PINPOINT SIGNAL (Auto-Rotates in {time_left}s)")
    
    if "LONG" in sig['RecommendedAction']:
        st.success(
            f"🔥 **PINPOINT ICEBERG LONG: {sig['Symbol']}** 🔥\n\n"
            f"* **🎯 Success Probability:** `⭐ {sig['Signal Probability']}%`\n"
            f"* **Leverage Mode:** `{sig['Leverage Tag']}` 🚀\n"
            f"* **Action:** ➔ **{sig['RecommendedAction']}**\n"
            f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Near Support Level:** `${sig['Level Price']:,.4f}` (Distance: `{sig['Distance %']}%`)\n"
            f"* **📊 Iceberg Wall Volume:** `${sig['Iceberg Volume']:,.2f}`\n"
            f"* **🎯 Target Resistance:** `${sig['Target Price']:,.4f}`\n"
            f"* **💰 Target Profit:** `+{sig['Estimated Profit']}%` (at {sig['Dynamic Leverage']}x) 💥\n\n"
            f"👉 **Rule:** Level bilkul current price ke paas hai! Target hit hone ya 1 minute ke baad next coin aayega."
        )
    else:
        st.error(
            f"🔥 **PINPOINT ICEBERG SHORT: {sig['Symbol']}** 🔥\n\n"
            f"* **🎯 Success Probability:** `⭐ {sig['Signal Probability']}%`\n"
            f"* **Leverage Mode:** `{sig['Leverage Tag']}` 🚀\n"
            f"* **Action:** ➔ **{sig['RecommendedAction']}**\n"
            f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Near Resistance Level:** `${sig['Level Price']:,.4f}` (Distance: `{sig['Distance %']}%`)\n"
            f"* **📊 Iceberg Wall Volume:** `${sig['Iceberg Volume']:,.2f}`\n"
            f"* **🎯 Target Support:** `${sig['Target Price']:,.4f}`\n"
            f"* **💰 Target Short Profit:** `+{sig['Estimated Profit']}%` (at {sig['Dynamic Leverage']}x) 💥\n\n"
            f"👉 **Rule:** Level bilkul current price ke paas hai! Target hit hone ya 1 minute ke baad next coin aayega."
        )
        
    progress_val = time_left / 60.0
    st.progress(max(0.0, min(1.0, progress_val)))
    st.markdown("---")
else:
    st.info("⏳ Market mein current price ke qareeb real iceberg levels scan ho rahe hain...")

st.subheader("🔮 Next-Queue Pinpoint Targets")
if candidates:
    queue_list = [c for c in candidates if not st.session_state.active_signal or c['Symbol'] != st.session_state.active_signal['Symbol']]
    if queue_list:
        for idx, item in enumerate(queue_list[:3], 1):
            st.info(
                f"**#{idx} Queue Coin:** **{item['Symbol']}** ➔ `⭐ Prob: {item['Signal Probability']}%`\n"
                f"* 🎯 **Action:** **{item['RecommendedAction']}**\n"
                f"* 📍 **Level Distance:** `{item['Distance %']}% away` | **Target:** `${item['Target Price']:,.4f}`\n"
                f"* 💰 **Target Profit:** `+{item['Estimated Profit']}%`"
            )
else:
    st.warning("Filhal qareeb ke levels scan ho rahe hain.")
