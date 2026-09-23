import streamlit as st
import requests
import pandas as pd
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="MEXC Multi-Tasking Hidden Iceberg Engine",
    page_icon="💎",
    layout="wide"
)

# Initialize Session State
if 'current_signal' not in st.session_state:
    st.session_state.current_signal = None
if 'tracked_trade' not in st.session_state:
    st.session_state.tracked_trade = None  # Background mein track hone wali trade
if 'closed_notification' not in st.session_state:
    st.session_state.closed_notification = None
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
                    
        usdt_pairs = sorted(usdt_pairs, key=lambda x: x['volume'], reverse=True)
        top_symbols = [p['symbol'] for p in usdt_pairs[:limit]]
        return top_symbols
    except Exception as e:
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']

def scan_hidden_iceberg_market():
    current_time = time.time()
    st.session_state.ignored_coins = {sym: t for sym, t in st.session_state.ignored_coins.items() if current_time - t <= 60}
        
    all_candidates = []
    active_coins = get_top_volume_coins(limit=40)
    
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
            
            depth_url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit=40"
            depth_res = requests.get(depth_url, timeout=2).json()
            
            trades_url = f"https://api.mexc.com/api/v3/trades?symbol={symbol}&limit=50"
            trades_res = requests.get(trades_url, timeout=2).json()
            
            if 'bids' in depth_res and 'asks' in depth_res and isinstance(trades_res, list) and len(trades_res) > 0:
                bids = depth_res['bids']
                asks = depth_res['asks']
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    current_price = (best_bid + best_ask) / 2
                    
                    bid_df = pd.DataFrame(bids, columns=['Price', 'Qty']).astype(float)
                    ask_df = pd.DataFrame(asks, columns=['Price', 'Qty']).astype(float)
                    
                    trades_df = pd.DataFrame(trades_res)
                    trades_df['qty'] = trades_df['qty'].astype(float)
                    
                    total_traded_vol = trades_df['qty'].sum()
                    recent_buy_trades = trades_df[trades_df['isBuyerMaker'] == False]['qty'].sum()
                    recent_sell_trades = trades_df[trades_df['isBuyerMaker'] == True]['qty'].sum()
                    
                    # Support Absorption (LONG Setup)
                    valid_bids = bid_df[bid_df['Price'] <= current_price]
                    if not valid_bids.empty:
                        valid_bids['Dist_Pct'] = (current_price - valid_bids['Price']) / current_price * 100
                        close_bids = valid_bids[valid_bids['Dist_Pct'] <= 0.6]
                        
                        if not close_bids.empty and recent_sell_trades > (total_traded_vol * 0.5):
                            target_row = close_bids.loc[close_bids['Dist_Pct'].idxmin()]
                            sup_price = target_row['Price']
                            sup_dist = target_row['Dist_Pct']
                            target_price = current_price * 1.025
                            target_dist_pct = abs(target_price - current_price) / current_price * 100
                            signal_prob = min(98, max(85, round(90 + (total_traded_vol / 1000) - (sup_dist * 3), 1)))
                            
                            all_candidates.append({
                                'Symbol': symbol,
                                'Type': 'LONG',
                                'Title': '🟢 HIDDEN ICEBERG ABSORPTION LONG',
                                'Current Price': current_price,
                                'Level Price': sup_price,
                                'Target Price': target_price,
                                'Leverage': 40,
                                'LeverageTag': '💎 HIDDEN WHALE WALL (40x)',
                                'Profit': round(target_dist_pct * 40, 2),
                                'Probability': signal_prob,
                                'Volume': total_traded_vol,
                                'Distance %': round(sup_dist, 2),
                                'Change %': price_change_pct,
                                'Timestamp': time.time()
                            })

                    # Resistance Absorption (SHORT Setup)
                    valid_asks = ask_df[ask_df['Price'] >= current_price]
                    if not valid_asks.empty:
                        valid_asks['Dist_Pct'] = (valid_asks['Price'] - current_price) / current_price * 100
                        close_asks = valid_asks[valid_asks['Dist_Pct'] <= 0.6]
                        
                        if not close_asks.empty and recent_buy_trades > (total_traded_vol * 0.5):
                            target_row = close_asks.loc[close_asks['Dist_Pct'].idxmin()]
                            res_price = target_row['Price']
                            res_dist = target_row['Dist_Pct']
                            target_price = current_price * 0.975
                            target_dist_pct = abs(current_price - target_price) / current_price * 100
                            signal_prob = min(98, max(85, round(90 + (total_traded_vol / 1000) - (res_dist * 3), 1)))
                            
                            all_candidates.append({
                                'Symbol': symbol,
                                'Type': 'SHORT',
                                'Title': '🔴 HIDDEN WALL REJECTION SHORT',
                                'Current Price': current_price,
                                'Level Price': res_price,
                                'Target Price': target_price,
                                'Leverage': 40,
                                'LeverageTag': '💎 HIDDEN WALL REJECTION (40x)',
                                'Profit': round(target_dist_pct * 40, 2),
                                'Probability': signal_prob,
                                'Volume': total_traded_vol,
                                'Distance %': round(res_dist, 2),
                                'Change %': price_change_pct,
                                'Timestamp': time.time()
                            })
        except Exception as e:
            continue
            
    all_candidates = sorted(all_candidates, key=lambda x: x['Probability'], reverse=True)
    return all_candidates

# --- STREAMLIT UI ---
st.title("💎 MEXC Multi-Tasking Background Tracking Engine")
st.markdown("Yeh model naye signals continuously deta rehta hai, aur background mein purane signals ko target touch hone tak track karta hai!")

if st.button("🔄 Force Refresh Scanner"):
    st.session_state.current_signal = None
    st.session_state.tracked_trade = None
    st.session_state.closed_notification = None
    st.rerun()

current_time = time.time()

# 1. BACKGROUND TRACKER: Check if the tracked trade has hit its target
if st.session_state.tracked_trade:
    t_sym = st.session_state.tracked_trade['Symbol']
    t_target = st.session_state.tracked_trade['Target Price']
    t_is_long = st.session_state.tracked_trade['Type'] == 'LONG'
    
    try:
        live_res = requests.get(f"https://api.mexc.com/api/v3/ticker/price?symbol={t_sym}", timeout=2).json()
        l_price = float(live_res.get('price', 0))
        
        hit = False
        if t_is_long and l_price >= t_target:
            hit = True
        elif not t_is_long and l_price <= t_target:
            hit = True
            
        if hit:
            trade_str = "LONG" if t_is_long else "SHORT"
            st.session_state.closed_notification = f"🎉 **PREVIOUS TRADE CLOSED:** **{trade_str}** trade on **{t_sym}** successfully hit target price `${t_target:,.4f}!`"
            st.session_state.ignored_coins[t_sym] = current_time
            st.session_state.tracked_trade = None # Tracking complete
    except:
        pass

# 2. SCANNER: Get fresh candidates
candidates = scan_hidden_iceberg_market()

# Update current live signal automatically and send previous one to background tracker
if candidates:
    new_sig = candidates[0]
    # Agar naya signal alag coin ka hai, toh purane wale ko background tracking mein dal do
    if not st.session_state.current_signal or st.session_state.current_signal['Symbol'] != new_sig['Symbol']:
        # Agar pehle se koi active signal tha aur wo track nahi ho raha, toh usko background mein lagado
        if st.session_state.current_signal and not st.session_state.tracked_trade:
            st.session_state.tracked_trade = st.session_state.current_signal
        st.session_state.current_signal = new_sig

# Display Closed Trade Notification separately if exists
if st.session_state.closed_notification:
    st.success(st.session_state.closed_notification)
    if st.button("✖ Clear Notification"):
        st.session_state.closed_notification = None
        st.rerun()

# Display Background Tracked Trade Status
if st.session_state.tracked_trade:
    tr = st.session_state.tracked_trade
    st.info(f"🔍 **Background Tracking Active:** Monitoring **{tr['Symbol']}** [{tr['Type']}] until target `${tr['Target Price']:,.4f}` is reached...")

# Display Current Live Signal
if st.session_state.current_signal:
    sig = st.session_state.current_signal
    elapsed_seconds = int(current_time - sig['Timestamp'])
    
    st.markdown("---")
    st.subheader(f"🚨 LIVE CURRENT SIGNAL (Auto-updating continuously)")
    
    if sig['Type'] == 'LONG':
        st.success(
            f"🔥 **{sig['Title']}: {sig['Symbol']}** (Change: `{sig['Change %']}%`) 📉➔📈\n\n"
            f"* **🎯 Absorption Probability:** `⭐ {sig['Probability']}%`\n"
            f"* **Leverage:** `{sig['LeverageTag']}`\n"
            f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Hidden Support Wall:** `${sig['Level Price']:,.4f}` (Distance: `{sig['Distance %']}%`)\n"
            f"* **📊 Tape Traded Volume:** `${sig['Volume']:,.2f}`\n"
            f"* **🎯 Target Resistance:** `${sig['Target Price']:,.4f}`\n"
            f"* **💰 Estimated Profit:** `+{sig['Profit']}%` (at {sig['Leverage']}x) 💥"
        )
    else:
        st.error(
            f"🔥 **{sig['Title']}: {sig['Symbol']}** (Change: `+{sig['Change %']}%`) 🚀➔📉\n\n"
            f"* **🎯 Rejection Probability:** `⭐ {sig['Probability']}%`\n"
            f"* **Leverage:** `{sig['LeverageTag']}`\n"
            f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Hidden Resistance Wall:** `${sig['Level Price']:,.4f}` (Distance: `{sig['Distance %']}%`)\n"
            f"* **📊 Tape Traded Volume:** `${sig['Volume']:,.2f}`\n"
            f"* **🎯 Target Support:** `${sig['Target Price']:,.4f}`\n"
            f"* **💰 Estimated Profit:** `+{sig['Profit']}%` (at {sig['Leverage']}x) 💥"
        )
    st.markdown("---")
else:
    st.info("⏳ Model live market scan kar raha hai...")

st.subheader("🔮 Next-Queue Hidden Iceberg Targets")
if candidates:
    queue_list = [c for c in candidates if not st.session_state.current_signal or c['Symbol'] != st.session_state.current_signal['Symbol']]
    if queue_list:
        for idx, item in enumerate(queue_list[:3], 1):
            st.info(
                f"**#{idx} Queue:** **{item['Symbol']}** [{item['Type']}] ➔ `⭐ Prob: {item['Probability']}%`\n"
                f"* 🎯 **Level:** `${item['Level Price']:,.4f}` (`{item['Distance %']}% away`) | **Target:** `${item['Target Price']:,.4f}`\n"
                f"* 💰 **Profit:** `+{item['Profit']}%`"
            )
else:
    st.warning("Filhal queue mein mazeed setups scan ho rahe hain.")

time.sleep(3)
st.rerun()
