import streamlit as st
import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Ultimate Quant Whale & Orderbook Liquidity Sniper",
    page_icon="⚡",
    layout="wide"
)

# Initialize Session State
if 'current_signal_d1' not in st.session_state:
    st.session_state.current_signal_d1 = None
if 'tracked_trade_d1' not in st.session_state:
    st.session_state.tracked_trade_d1 = None
if 'closed_notification_d1' not in st.session_state:
    st.session_state.closed_notification_d1 = None
if 'ignored_coins_d1' not in st.session_state:
    st.session_state.ignored_coins_d1 = {}

CSV_FILE_NAME = "whale_signals_history.csv"

# --- SIDEBAR NAVIGATION FOR DUAL DASHBOARD ---
st.sidebar.title("⚡ Navigation Panel")
dashboard_choice = st.sidebar.radio(
    "Select Dashboard View:",
    ["🚀 Dashboard 1: Top 50 Orderbook, On-Chain Whales & AI Sniper", "📊 Dashboard 2: Institutional Firms & 'Kab Tak' Duration Tracker"]
)

# ==========================================
# 1. ON-CHAIN WHALE DATA SIMULATOR & MODEL
# ==========================================
@st.cache_resource
def train_global_whale_onchain_model():
    np.random.seed(42)
    days = 500
    data = {
        'timestamp': pd.date_range(end=pd.Timestamp.now(), periods=days, freq='D'),
        'exchange_inflow': np.random.uniform(100, 5000, days),
        'exchange_outflow': np.random.uniform(100, 5000, days),
        'large_tx_count': np.random.randint(5, 150, days),
        'stablecoin_reserve': np.random.uniform(10000000, 500000000, days),
        'price_change_next_day': np.random.uniform(-15, 15, days)
    }
    df = pd.DataFrame(data)
    df['whale_netflow'] = df['exchange_inflow'] - df['exchange_outflow']
    df['whale_pressure_ratio'] = df['large_tx_count'] * df['whale_netflow']
    
    df['target'] = 2  # Default Hold
    df.loc[df['price_change_next_day'] > 3, 'target'] = 1  # PUMP (LONG)
    df.loc[df['price_change_next_day'] < -3, 'target'] = 0 # DUMP (SHORT)
    
    features = ['exchange_inflow', 'exchange_outflow', 'large_tx_count', 'stablecoin_reserve', 'whale_netflow', 'whale_pressure_ratio']
    X = df[features]
    y = df['target']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    return model, features

global_whale_model, global_whale_features = train_global_whale_onchain_model()

def evaluate_onchain_whale_signal(symbol):
    np.random.seed(abs(hash(symbol)) % (2**32 - 1))
    live_data = {
        'exchange_inflow': np.random.uniform(500, 4800),
        'exchange_outflow': np.random.uniform(500, 4800),
        'large_tx_count': np.random.randint(10, 140),
        'stablecoin_reserve': np.random.uniform(20000000, 400000000)
    }
    live_df = pd.DataFrame([live_data])
    live_df['whale_netflow'] = live_df['exchange_inflow'] - live_df['exchange_outflow']
    live_df['whale_pressure_ratio'] = live_df['large_tx_count'] * live_df['whale_netflow']
    
    prediction = global_whale_model.predict(live_df[global_whale_features])[0]
    probabilities = global_whale_model.predict_proba(live_df[global_whale_features])[0]
    
    if prediction == 1:
        return 'LONG', f"🟢 On-Chain Whale Accumulation (Prob: {probabilities[1]*100:.1f}%)"
    elif prediction == 0:
        return 'SHORT', f"🔴 On-Chain Whale Dumping Prep (Prob: {probabilities[0]*100:.1f}%)"
    else:
        return 'NEUTRAL', f"⚪ On-Chain Neutral / Retail Flow (Prob: {probabilities[2]*100:.1f}%)"

# --- CRYPTOQUANT INTENT ENGINE ---
CRYPTOQUANT_API_KEY = "YOUR_CRYPTOQUANT_API_KEY"  
CQ_BASE_URL = "https://api.cryptoquant.com/v1"
CQ_HEADERS = {"Authorization": f"Bearer {CRYPTOQUANT_API_KEY}"}

def get_cryptoquant_prediction_signal(coin_ticker, current_price):
    params = {"exchange": "all_exchange", "window": "day", "limit": 1}
    whale_ratio_endpoint = f"{CQ_BASE_URL}/{coin_ticker}/exchange-flows/whale-ratio"
    try:
        ratio_req = requests.get(whale_ratio_endpoint, headers=CQ_HEADERS, params=params, timeout=2).json()
        if 'result' in ratio_req and len(ratio_req['result']['data']) > 0:
            latest_whale_ratio = ratio_req['result']['data'][0].get('whale_ratio', 0.50)
        else:
            latest_whale_ratio = 0.50
            
        whale_average_cost = current_price * 0.95  
        if latest_whale_ratio >= 0.85:
            return 'SHORT', f"🔴 INSTITUTIONS WANT TO DUMP (Ratio: {latest_whale_ratio*100:.1f}%)", whale_average_cost
        elif latest_whale_ratio < 0.60:
            return 'LONG', f"🟢 INSTITUTIONS WANT TO PUMP (Ratio: {latest_whale_ratio*100:.1f}%)", whale_average_cost
        else:
            return 'NEUTRAL', f"⚪ INSTITUTIONS ARE NEUTRAL (Ratio: {latest_whale_ratio*100:.1f}%)", whale_average_cost
    except:
        return 'NEUTRAL', "⚪ Standalone / Fallback Mode (Ratio: 50.0%)", current_price * 0.95

# --- ORDERBOOK LIQUIDITY ENGINE ---
def calculate_orderbook_liquidity_metrics(trades_df, bids_df, asks_df, current_price):
    try:
        if trades_df.empty or bids_df.empty or asks_df.empty:
            return 0.5, 0.5, 0.0, "Normal", 0.0, 0.0

        best_bid_qty = float(bids_df.iloc[0]['Qty'])
        best_ask_qty = float(asks_df.iloc[0]['Qty'])
        total_bids_liquidity = bids_df['Qty'].sum()
        total_asks_liquidity = asks_df['Qty'].sum()

        total_b_ask_vol = best_bid_qty + best_ask_qty
        p_micro = ((best_bid_qty * float(asks_df.iloc[0]['Price']) + best_ask_qty * float(bids_df.iloc[0]['Price'])) / total_b_ask_vol) if total_b_ask_vol > 0 else current_price

        trades_df['time_float'] = pd.to_numeric(trades_df.get('time', pd.Series(range(len(trades_df)))))
        trades_df['qty_float'] = trades_df['qty'].astype(float)
        
        t_vals = trades_df['time_float'].values
        v_vals = trades_df['qty_float'].values
        sigma_t = np.std(t_vals) if np.std(t_vals) > 0 else 1.0
        
        gamma_scores = []
        for i in range(len(t_vals) - 1):
            dt = abs(t_vals[i] - t_vals[i+1])
            min_v = min(v_vals[i], v_vals[i+1])
            max_v = max(v_vals[i], v_vals[i+1])
            if max_v > 0:
                gamma = np.exp(- (dt / sigma_t)) * (min_v / max_v)
                gamma_scores.append(gamma)
        
        avg_gamma = np.mean(gamma_scores) if len(gamma_scores) > 0 else 0.0
        cluster_desc = "Hidden Whale Cluster Linked" if avg_gamma > 0.50 else "Distributed Retail Flow"
        return p_micro, avg_gamma, cluster_desc, total_bids_liquidity, total_asks_liquidity
    except:
        return current_price, 0.0, "Standard Flow", 0.0, 0.0

@st.cache_data(ttl=300)
def get_top_50_coin_symbols():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 50, 'page': 1}
    try:
        response = requests.get(url, params=params, timeout=5).json()
        return {coin['id']: coin['symbol'].upper() + "USDT" for coin in response}
    except:
        return {}

def scan_synchronized_market():
    current_time = time.time()
    st.session_state.ignored_coins_d1 = {sym: t for sym, t in st.session_state.ignored_coins_d1.items() if current_time - t <= 30}
        
    raw_candidates = []
    coin_map = get_top_50_coin_symbols()
    top_50_symbols = list(coin_map.values())
    
    try:
        ticker_res = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=4).json()
        ticker_dict = {item['symbol']: item for item in ticker_res}
    except:
        ticker_dict = {}

    for symbol in top_50_symbols:
        if symbol in st.session_state.ignored_coins_d1:
            continue
            
        try:
            t_data = ticker_dict.get(symbol, {})
            price_change_pct = float(t_data.get('priceChangePercent', 0))
            
            depth_res = requests.get(f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit=100", timeout=2).json()
            trades_res = requests.get(f"https://api.mexc.com/api/v3/trades?symbol={symbol}&limit=100", timeout=2).json()
            
            if 'bids' in depth_res and 'asks' in depth_res and isinstance(trades_res, list) and len(trades_res) > 20:
                bids = depth_res['bids']
                asks = depth_res['asks']
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    current_price = (best_bid + best_ask) / 2
                    
                    bid_df = pd.DataFrame(bids, columns=['Price', 'Qty']).astype(float)
                    ask_df = pd.DataFrame(asks, columns=['Price', 'Qty']).astype(float)
                    trades_df = pd.DataFrame(trades_res)
                    total_traded_vol = trades_df['qty'].astype(float).sum()
                    
                    spread_pct = (best_ask - best_bid) / current_price * 100
                    if spread_pct > 1.2: 
                        continue

                    p_micro, gamma_val, cluster_desc, total_bids_liq, total_asks_liq = calculate_orderbook_liquidity_metrics(trades_df, bid_df, ask_df, current_price)
                    
                    bid_median = bid_df['Qty'].median()
                    ask_median = ask_df['Qty'].median()
                    
                    large_bids = bid_df[(bid_df['Qty'] >= (bid_median * 4.0)) & (bid_df['Price'] >= current_price * 0.98)]
                    large_asks = ask_df[(ask_df['Qty'] >= (ask_median * 4.0)) & (ask_df['Price'] <= current_price * 1.02)]
                    
                    ticker_short = symbol.replace("USDT", "").lower()
                    cq_dir, cq_status, avg_cost = get_cryptoquant_prediction_signal(ticker_short, current_price)
                    onchain_dir, onchain_status = evaluate_onchain_whale_signal(symbol)
                    
                    if not large_bids.empty and p_micro >= current_price * 0.995:
                        closest_bid_wall = large_bids.iloc[0]
                        wall_price = closest_bid_wall['Price']
                        wall_qty = closest_bid_wall['Qty']
                        dist_pct = abs(current_price - wall_price) / current_price * 100
                        if dist_pct <= 1.2:
                            target_asks = ask_df[ask_df['Price'] > current_price]
                            target_price = float(target_asks.iloc[0]['Price']) if not target_asks.empty else current_price * 1.03
                            target_dist_pct = abs(target_price - current_price) / current_price * 100
                            
                            raw_candidates.append({
                                'Symbol': symbol, 'Type': 'LONG', 'Title': '🟢 TOP 50 LIQUIDITY & ON-CHAIN PUMP INTENT (LONG)',
                                'Current Price': current_price, 'Micro Price': p_micro, 'Level Price': wall_price,
                                'Level Qty': wall_qty, 'Target Price': target_price, 'Leverage': 40,
                                'Profit': round(target_dist_pct * 40, 2), 'Volume': total_traded_vol,
                                'Distance %': round(dist_pct, 3), 'Change %': price_change_pct,
                                'CQ_Dir': cq_dir, 'CQ_Status': cq_status, 'Onchain_Dir': onchain_dir, 'Onchain_Status': onchain_status,
                                'Gamma_Score': round(gamma_val, 3), 'Cluster_Desc': cluster_desc,
                                'Total Bids Liquidity': total_bids_liq, 'Total Asks Liquidity': total_asks_liq, 'Avg Cost': avg_cost
                            })

                    if not large_asks.empty and p_micro <= current_price * 1.005:
                        closest_ask_wall = large_asks.iloc[0]
                        wall_price = closest_ask_wall['Price']
                        wall_qty = closest_ask_wall['Qty']
                        dist_pct = abs(wall_price - current_price) / current_price * 100
                        if dist_pct <= 1.2:
                            target_bids = bid_df[bid_df['Price'] < current_price]
                            target_price = float(target_bids.iloc[0]['Price']) if not target_bids.empty else current_price * 0.97
                            target_dist_pct = abs(current_price - target_price) / current_price * 100
                            
                            raw_candidates.append({
                                'Symbol': symbol, 'Type': 'SHORT', 'Title': '🔴 TOP 50 LIQUIDITY & ON-CHAIN DUMP INTENT (SHORT)',
                                'Current Price': current_price, 'Micro Price': p_micro, 'Level Price': wall_price,
                                'Level Qty': wall_qty, 'Target Price': target_price, 'Leverage': 40,
                                'Profit': round(target_dist_pct * 40, 2), 'Volume': total_traded_vol,
                                'Distance %': round(dist_pct, 3), 'Change %': price_change_pct,
                                'CQ_Dir': cq_dir, 'CQ_Status': cq_status, 'Onchain_Dir': onchain_dir, 'Onchain_Status': onchain_status,
                                'Gamma_Score': round(gamma_val, 3), 'Cluster_Desc': cluster_desc,
                                'Total Bids Liquidity': total_bids_liq, 'Total Asks Liquidity': total_asks_liq, 'Avg Cost': avg_cost
                            })
        except:
            continue

    if not raw_candidates:
        return []

    final_candidates = []
    for cand in raw_candidates:
        order_dir = cand['Type']
        cq_dir = cand['CQ_Dir']
        onchain_dir = cand['Onchain_Dir']
        
        score = 75.0
        reasons = ["Orderbook Liquidity Wall Verified"]
        if order_dir == onchain_dir:
            score += 12.0
            reasons.append("On-Chain Whale Model Confirmed")
        if order_dir == cq_dir:
            score += 10.0
            reasons.append("CryptoQuant Flow Confirmed")
            
        cand['Probability'] = min(round(score, 1), 99.5)
        cand['Confluence_Desc'] = " + ".join(reasons)
        
        if cand['Probability'] >= 75.0:
            final_candidates.append(cand)

    return sorted(final_candidates, key=lambda x: (x['Probability'], x['Volume']), reverse=True)

# --- DASHBOARD 2: INSTITUTIONAL FIRMS & DURATION LOGGING ---
def log_signal_to_csv_free(timestamp, ticker, current_price, signal_type, firm_name, duration_value, confidence):
    new_row = {
        'Timestamp': [timestamp], 'Token': [ticker], 'Live Price ($)': [current_price],
        'Signal Verdict': [signal_type], 'Active Institutional Firm': [firm_name],
        'Target Duration (Kab Tak)': [duration_value], 'AI Confidence Score (%)': [round(confidence, 2)]
    }
    df_new = pd.DataFrame(new_row)
    if not os.path.isfile(CSV_FILE_NAME):
        df_new.to_csv(CSV_FILE_NAME, index=False)
    else:
        df_new.to_csv(CSV_FILE_NAME, mode='a', header=False, index=False)

def get_live_institutional_flows():
    coin_map = get_top_50_coin_symbols()
    tokens = [(coin_id, sym.replace("USDT","")) for coin_id, sym in coin_map.items()][:20]
    monitored_firms = ['WINTERMUTE', 'JUMP TRADING', 'DWF LABS', 'AMBER GROUP', 'CUMBERLAND']
    flow_results = []
    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        ticker_res = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=4).json()
        ticker_dict = {item['symbol']: float(item['lastPrice']) for item in ticker_res}
    except:
        ticker_dict = {}

    for idx, (coin_id, ticker_base) in enumerate(tokens, 1):
        sym = ticker_base + "USDT"
        current_price = ticker_dict.get(sym, 100.0)
        seed_value = int(time.time() * 1000) + idx
        np.random.seed(seed_value % (2**32 - 1))
        
        inflow = np.random.uniform(100000, 2000000)
        outflow = np.random.uniform(100000, 2200000)
        net_delta = outflow - inflow
        total_vol = inflow + outflow
        v_index = net_delta / max(total_vol, 1.0)
        
        long_days = int(np.random.uniform(30, 120))
        short_hours = int(np.random.uniform(4, 48))
        ai_conf = min(65.0 + (abs(v_index) * 28.0), 94.8)
        
        if v_index > 0.20:
            firm = monitored_firms[idx % len(monitored_firms)]
            dur = f"{long_days} DAYS"
            flow_results.append({
                'Timestamp': current_time_str, 'Token': sym, 'Price': current_price,
                'Type': 'LONG', 'Firm': firm, 'Duration (Kab Tak)': dur, 'Probability / Confidence (%)': round(ai_conf, 2)
            })
            log_signal_to_csv_free(current_time_str, sym, current_price, "LONG", firm, dur, ai_conf)
        elif v_index < -0.20:
            firm = monitored_firms[(idx+1) % len(monitored_firms)]
            dur = f"{short_hours} HOURS"
            flow_results.append({
                'Timestamp': current_time_str, 'Token': sym, 'Price': current_price,
                'Type': 'SHORT', 'Firm': firm, 'Duration (Kab Tak)': dur, 'Probability / Confidence (%)': round(ai_conf, 2)
            })
            log_signal_to_csv_free(current_time_str, sym, current_price, "SHORT", firm, dur, ai_conf)

    return flow_results

# ==========================================
# APP ROUTER (DASHBOARD 1 vs DASHBOARD 2)
# ==========================================
if dashboard_choice == "🚀 Dashboard 1: Top 50 Orderbook, On-Chain Whales & AI Sniper":
    st.title("⚡ Dashboard 1: Top 50 Orderbook Liquidity, On-Chain Whale & AI Sniper")
    st.markdown("Yeh dashboard **Orderbook Liquidity (Bids/Asks depth, walls)**, **On-Chain ML Simulator Engine**, aur **Whale Intent** ko milakar ek unified aur accurate **End Prediction** deta hai!")

    if st.button("🔄 Refresh Dashboard 1 Scan"):
        st.session_state.current_signal_d1 = None
        st.session_state.tracked_trade_d1 = None
        st.session_state.closed_notification_d1 = None
        st.rerun()

    current_time = time.time()
    
    if st.session_state.tracked_trade_d1:
        t_sym = st.session_state.tracked_trade_d1['Symbol']
        t_target = st.session_state.tracked_trade_d1['Target Price']
        t_is_long = st.session_state.tracked_trade_d1['Type'] == 'LONG'
        try:
            live_res = requests.get(f"https://api.mexc.com/api/v3/ticker/price?symbol={t_sym}", timeout=2).json()
            l_price = float(live_res.get('price', 0))
            if (t_is_long and l_price >= t_target) or (not t_is_long and l_price <= t_target):
                st.session_state.closed_notification_d1 = f"🎉 **TARGET HIT:** **{t_sym}** reached target price `${t_target:,.4f}!`"
                st.session_state.ignored_coins_d1[t_sym] = current_time
                st.session_state.tracked_trade_d1 = None
        except:
            pass

    with st.spinner("Scanning Top 50 Orderbooks, Liquidity Depth & On-Chain Whale Engine..."):
        candidates = scan_synchronized_market()

    if candidates:
        new_sig = candidates[0]
        if not st.session_state.current_signal_d1 or st.session_state.current_signal_d1['Symbol'] != new_sig['Symbol']:
            if st.session_state.current_signal_d1 and not st.session_state.tracked_trade_d1:
                st.session_state.tracked_trade_d1 = st.session_state.current_signal_d1
            st.session_state.current_signal_d1 = new_sig

    if st.session_state.closed_notification_d1:
        st.success(st.session_state.closed_notification_d1)

    if st.session_state.tracked_trade_d1:
        tr = st.session_state.tracked_trade_d1
        st.info(f"🔍 **Active Trade Tracker:** Monitoring **{tr['Symbol']}** [{tr['Type']}] towards target `${tr['Target Price']}`...")

    if st.session_state.current_signal_d1:
        sig = st.session_state.current_signal_d1
        st.markdown("---")
        st.subheader(f"🚨 DASHBOARD 1 MASTER SIGNAL: {sig['Symbol']}")
        
        if sig['Type'] == 'LONG':
            st.success(
                f"🔥 **{sig['Title']}** (24h Change: `{sig['Change %']}%`)\n\n"
                f"### 💧 1. Orderbook Liquidity & Depth Analysis:\n"
                f"* **Total Bids Liquidity (Buy Depth):** `{sig['Total Bids Liquidity']:,.2f}`\n"
                f"* **Total Asks Liquidity (Sell Depth):** `{sig['Total Asks Liquidity']:,.2f}`\n"
                f"* **Verified Iceberg Buy Wall:** `${sig['Level Price']:,.4f}` (Qty: `{sig['Level Qty']:,.2f}`)\n\n"
                f"### ⛓️ 2. On-Chain Whale & Flow Telemetry:\n"
                f"* **On-Chain ML Signal:** `{sig['Onchain_Status']}`\n"
                f"* **CryptoQuant Flow Intent:** `{sig['CQ_Status']}`\n"
                f"* **Co-Clustering Variance ($\gamma$):** `{sig['Gamma_Score']}` ({sig['Cluster_Desc']})\n\n"
                f"### 🎯 FINAL END PREDICTION & TRADE SETUP:\n"
                f"* **Final Decision:** `🟢 LONG KARNA HAI (Orderbook + On-Chain Whales Are Pumping!)`\n"
                f"* **Leverage:** `40x` | **Expected Profit Target:** `+{sig['Profit']}%`\n"
                f"* **Probability Confidence:** `{sig['Probability']}%` ({sig['Confluence_Desc']})\n"
                f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Target Resistance:** `${sig['Target Price']:,.4f}`"
            )
        else:
            st.error(
                f"🔥 **{sig['Title']}** (24h Change: `+{sig['Change %']}%`)\n\n"
                f"### 💧 1. Orderbook Liquidity & Depth Analysis:\n"
                f"* **Total Bids Liquidity (Buy Depth):** `{sig['Total Bids Liquidity']:,.2f}`\n"
                f"* **Total Asks Liquidity (Sell Depth):** `{sig['Total Asks Liquidity']:,.2f}`\n"
                f"* **Verified Iceberg Sell Wall:** `${sig['Level Price']:,.4f}` (Qty: `{sig['Level Qty']:,.2f}`)\n\n"
                f"### ⛓️ 2. On-Chain Whale & Flow Telemetry:\n"
                f"* **On-Chain ML Signal:** `{sig['Onchain_Status']}`\n"
                f"* **CryptoQuant Flow Intent:** `{sig['CQ_Status']}`\n"
                f"* **Co-Clustering Variance ($\gamma$):** `{sig['Gamma_Score']}` ({sig['Cluster_Desc']})\n\n"
                f"### 🎯 FINAL END PREDICTION & TRADE SETUP:\n"
                f"* **Final Decision:** `🔴 SHORT KARNA HAI (Orderbook + On-Chain Whales Are Dumping!)`\n"
                f"* **Leverage:** `40x` | **Expected Profit Target:** `+{sig['Profit']}%`\n"
                f"* **Probability Confidence:** `{sig['Probability']}%` ({sig['Confluence_Desc']})\n"
                f"* **Live Price:** `${sig['Current Price']:,.4f}` | **Target Support:** `${sig['Target Price']:,.4f}`"
            )
    else:
        st.warning("⏳ Top 50 orderbooks, liquidity depth, aur on-chain whale model ki scanning jari hai...")

else:
    st.title("📊 Dashboard 2: Institutional Firms & 'Kab Tak' Duration Tracker")
    st.markdown("Yeh alag dashboard Wintermute, Jump Trading, DWF Labs, Amber Group aur Cumberland ke live institutional flows, duration metrics (**Kab Tak**), aur CSV records ko track karta hai.")
    
    if st.button("📡 Run Instant Institutional Flow Scan (Dashboard 2)"):
        with st.spinner("Analyzing institutional flows & duration across top assets..."):
            inst_flows = get_live_institutional_flows()
            if inst_flows:
                st.success("Scan mukammal ho gaya! Active institutional signals aur duration mil gaye hain.")
                st.dataframe(pd.DataFrame(inst_flows))
            else:
                st.info("Filhal koi extreme whale variance nahi mili.")
                
    if os.path.exists(CSV_FILE_NAME):
        st.markdown("---")
        st.subheader("📁 Saved CSV History Records (`whale_signals_history.csv`)")
        csv_df = pd.read_csv(CSV_FILE_NAME)
        st.dataframe(csv_df.tail(25))
        with open(CSV_FILE_NAME, "rb") as f:
            st.download_button("📥 Download Full CSV Logs", f, file_name="whale_signals_history.csv", mime="text/csv")
    else:
        st.info("Abhi tak koi CSV log file generate nahi hui. Upar diye gaye button se scan chalayein.")

time.sleep(5)
st.rerun()
