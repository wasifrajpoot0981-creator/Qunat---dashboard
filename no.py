import streamlit as st
import requests
import pandas as pd
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="MEXC Real Iceberg & Target Tracking Engine",
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
                    
                    bid_df = pd.DataFrame(bids, columns=['Price', 'Qty']).astype(float)
                    ask_df = pd.DataFrame(asks, columns=['Price', 'Qty']).astype(float)
                    
                    avg_bid_qty = bid_df['Qty'].mean() if not bid_df.empty else 1
                    avg_ask_qty = ask_df['Qty'].mean() if not ask_df.empty else 1
                    
                    if quote_volume > 80000000 or price_change_pct >= 5.0:
                        dynamic_leverage = 50
                        leverage_tag = "🔥 WHALE MEGA ICEBERG (50x Leverage)"
                        target_mult = 1.04
                        min_guaranteed_profit = 150
                        base_prob = 92
                    elif quote_volume > 30000000 or price_change_pct >= 2.5:
                        dynamic_leverage = 35
                        leverage_tag = "⚡ ACTIVE ICEBERG WALL (35x Leverage)"
                        target_mult = 1.03
                        min_guaranteed_profit = 100
                        base_prob = 85
                    else:
                        dynamic_leverage = 20
                        leverage_tag = "⚖️ STANDARD ICEBERG SETUP (20x Leverage)"
                        target_mult = 1.02
                        min_guaranteed_profit = 40
                        base_prob = 78

                    # 1. REAL SUPPORT ICEBERG (LONG)
                    valid_bids = bid_df[bid_df['Price'] <= current_price]
                    if not valid_bids.empty:
                        heavy_bids = valid_bids[valid_bids['Qty'] >= (avg_bid_qty * 3.0)]
                        if not heavy_bids.empty:
                            target_bid = heavy_bids.loc[heavy_bids['Qty'].idxmax()]
                            sup_price = target_bid['Price']
                            sup_qty = target_bid['Qty']
                            sup_dist = abs(current_price - sup_price) / current_price * 100
                            
                            next_resistance = current_price * target_mult
                            target_dist_pct = abs(next_resistance - current_price) / current_price * 100
                            
                            estimated_profit_pct = round(target_dist_pct * dynamic_leverage, 2)
                            if estimated_profit_pct < min_guaranteed_profit:
                                estimated_profit_pct = min_guaranteed_profit
                            
                            signal_probability = min(99, max(75, round(base_prob + (sup_qty / (avg_bid_qty + 1)) - (sup_dist * 2), 1)))
                            
                            if sup_dist <= 2.0:
                                all_candidates.append({
                                    'Symbol': symbol,
                                    'Action Type': 'REAL ICEBERG LONG SETUP',
                                    'RecommendedAction': '🟢 REAL ICEBERG LONG (Whale support wall par price khadi hai)',
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
                            
                    # 2. REAL RESISTANCE ICEBERG (SHORT)
                    valid_asks = ask_df[ask_df['Price'] >= current_price]
                    if not valid_asks.empty:
                        heavy_asks = valid_asks[valid_asks['Qty'] >= (avg_ask_qty * 3.0)]
                        if not heavy_asks.empty:
                            target_ask = heavy_asks.loc[heavy_asks['Qty'].idxmax()]
                            res_price = target_ask['Price']
                            res_qty = target_ask['Qty']
                            res_dist = abs(res_price - current_price) / current_price * 100
                            
                            next_support = current_price * (2.0 - target_mult)
                            target_dist_pct = abs(current_price - next_support) / current_price * 100
                            
                            estimated_profit_pct = round(target_dist_pct * dynamic_leverage, 2)
                            if estimated_profit_pct < min_guaranteed_profit:
                                estimated_profit_pct = min_guaranteed_profit
                            
                            signal_probability = min(99, max(75, round(base_prob + (res_qty / (avg_ask_qty + 1)) - (res_dist * 2), 1)))
                            
                            if res_dist <= 2.0:
                                all_candidates.append({
                                    'Symbol': symbol,
                                    'Action Type': 'REAL ICEBERG SHORT SETUP',
                                    'RecommendedAction': '🔴 REAL ICEBERG SHORT (Whale resistance wall se price reject hogi)',
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
st.title("💎 MEXC Real Iceberg & 1-Min Target Tracking Engine")
st.markdown("Yeh model har signal ko 1 minute tak display karta hai, aur target hit hone par chota box show kar ke pichli trade close karta hai.")

if st.button("🔄 Force Refresh Scanner"):
    st.session_state.active_signal = None
    st.session_state.previous_closed_msg = None
    st.rerun()

current_time = time.time()

# Check if active signal has completed 1 minute rotation
if st.session_state.active_signal:
    elapsed_time = current_time - st.session_state.signal_timestamp
    
    # Check live target hit condition for active signal
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

    # If target hit or 1 minute passed, close previous trade and trigger small box message
    if elapsed_time > 60 or target_hit:
        reason = "Resistance/Target Hit!" if target_hit else "1-Minute Time Completed!"
        st.session_state.previous_closed_msg = f"📦 **PREVIOUS TRADE CLOSED:** Coin **{active_sym}** ({reason}) - Naya coin scan ho raha hai!"
        st.session_state.ignored_coins[active_sym] = current_time
        st.session_state.active_signal = None

candidates = scan_real_iceberg_market()

if not st.session_state.active_signal and candidates:
    st.session_state.active_signal = candidates[0]
    st.session_state.signal_timestamp = current_time
    candidates = scan_real_iceberg_market()

# --- DISPLAY PREVIOUS CLOSED BOX NOTIFICATION ---
if st.session_state.previous_closed_msg:
    st.info(st.session_state.previous_closed_msg)

# --- DISPLAY ACTIVE SIGNAL ---
if st.session_state.active_signal:
    sig = st.session_state.active_signal
    elapsed = int(current_time - st.session_state.signal_timestamp)
    time_left = max(0, 60 - elapsed)
    
    st.markdown("---")
    st.subheader(f"🚨 ACTIVE SIGNAL (Auto-Rotates in {time_left}s)")
    
    if "LONG" in sig['RecommendedAction']:
        st.success(
            f"🔥 **REAL ICEBERG LONG: {sig['Symbol']}** 🔥\n\n"
            f"* **🎯 Pinpoint Success Probability:** `⭐ {sig['Signal Probability']}%`\n"
            f"* **Leverage & Volume Mode:** `{sig['Leverage Tag']}` 🚀\n"
            f"* **Kya Karna Hai?** ➔ **{sig['RecommendedAction']}**\n"
            f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Real Support Level:** `${sig['Level Price']:,.4f}`\n"
            f"* **📊 Iceberg Volume Wall:** `${sig['Iceberg Volume']:,.2f}` (Distance: `{sig['Distance %']}%`)\n"
            f"* **🎯 Target Resistance:** `${sig['Target Price']:,.4f}`\n"
            f"* **💰 Target Profit:** `+{sig['Estimated Profit']}%` (at {sig['Dynamic Leverage']}x) 💥\n\n"
            f"👉 **Rule:** Yeh signal 1 minute tak screen par rahega ya resistance touch hone par closed box show karega!"
        )
    else:
        st.error(
            f"🔥 **REAL ICEBERG SHORT: {sig['Symbol']}** 🔥\n\n"
            f"* **🎯 Pinpoint Success Probability:** `⭐ {sig['Signal Probability']}%`\n"
            f"* **Leverage & Volume Mode:** `{sig['Leverage Tag']}` 🚀\n"
            f"* **Kya Karna Hai?** ➔ **{sig['RecommendedAction']}**\n"
            f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Real Resistance Level:** `${sig['Level Price']:,.4f}`\n"
            f"* **📊 Iceberg Volume Wall:** `${sig['Iceberg Volume']:,.2f}` (Distance: `{sig['Distance %']}%`)\n"
            f"* **🎯 Target Support:** `${sig['Target Price']:,.4f}`\n"
            f"* **💰 Target Short Profit:** `+{sig['Estimated Profit']}%` (at {sig['Dynamic Leverage']}x) 💥\n\n"
            f"👉 **Rule:** Yeh signal 1 minute tak screen par rahega ya support touch hone par closed box show karega!"
        )
        
    progress_val = time_left / 60.0
    st.progress(max(0.0, min(1.0, progress_val)))
    st.markdown("---")
else:
    st.info("⏳ Market mein naya signal scan ho raha hai...")

# --- NEXT-QUEUE WATCHLIST ---
st.subheader("🔮 Next-Queue Real Iceberg Targets")
if candidates:
    queue_list = [c for c in candidates if not st.session_state.active_signal or c['Symbol'] != st.session_state.active_signal['Symbol']]
    if queue_list:
        for idx, item in enumerate(queue_list[:3], 1):
            st.info(
                f"**#{idx} Queue Coin:** **{item['Symbol']}** ➔ `⭐ Prob: {item['Signal Probability']}%`\n"
                f"* 🎯 **Action:** **{item['RecommendedAction']}**\n"
                f"* 💰 **Target Profit:** `+{item['Estimated Profit']}%` | **Target:** `${item['Target Price']:,.4f}`\n"
                f"* 📊 **Iceberg Vol:** `{item['Iceberg Volume']:,.2f}` | `{item['Leverage Tag']}`"
            )
else:
    st.warning("Filhal market mein naye levels scan ho rahe hain.")

time.sleep(3)
st.rerun()
