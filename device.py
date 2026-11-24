"""
Order Flow Radar - Streamlit dashboard (2 tabs)
  Tab 1: Order book radar  (walls, spoof vs real, imbalance, CVD, slippage, per-exchange bias)
  Tab 2: Derivatives + network (liquidations, L/S, funding, OI, fear&greed, mempool whales, Bitnodes)
Prediction: BUYERS / SELLERS / WAIT + probability, with a LIVE scorecard of its real hit-rate.

pip install streamlit plotly pandas requests websocket-client
streamlit run dashboard.py
"""
import json, math, statistics, threading, time
from collections import deque

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
import websocket

from anim import anim_html

st.set_page_config(page_title="Order Flow Radar", layout="wide")
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"
FAPI = "https://fapi.binance.com"
COINS = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LINK", "TON", "SUI", "LTC", "DOT", "PEPE", "ARB", "OP", "NEAR", "APT"]


def get(url, **p):
    try:
        r = S.get(url, params=p, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def sig(x): return 1 / (1 + math.exp(-x))
def clip(x, a=-1.0, b=1.0): return max(a, min(b, x))
def arr(rows): return [(float(r[0]), float(r[1])) for r in rows]


# ---------------- data ----------------
@st.cache_resource
def liq_store():
    """Background thread: live liquidations from Binance futures (all symbols)."""
    dq = deque(maxlen=8000)

    def on_msg(ws, m):
        try:
            o = json.loads(m)["o"]
            px = float(o["ap"]) or float(o["p"])
            dq.append(dict(t=time.time(), sym=o["s"], side=o["S"], price=px, usd=px * float(o["q"])))
        except Exception:
            pass

    def run():
        while True:
            try:
                websocket.WebSocketApp("wss://fstream.binance.com/ws/!forceOrder@arr", on_message=on_msg).run_forever(ping_interval=20)
            except Exception:
                pass
            time.sleep(3)

    threading.Thread(target=run, daemon=True).start()
    return dq


@st.cache_data(ttl=2)
def fetch_books(coin):
    out = {}
    d = get("https://api.binance.com/api/v3/depth", symbol=f"{coin}USDT", limit=500)
    if d: out["Binance"] = (arr(d["bids"]), arr(d["asks"]))
    d = get(f"https://api.exchange.coinbase.com/products/{coin}-USD/book", level=2)
    if d: out["Coinbase"] = (arr(d["bids"]), arr(d["asks"]))
    d = get("https://api.kraken.com/0/public/Depth", pair=f"{'XBT' if coin == 'BTC' else coin}USD", count=500)
    if d and d.get("result"):
        v = list(d["result"].values())[0]
        out["Kraken"] = (arr(v["bids"]), arr(v["asks"]))
    d = get("https://www.okx.com/api/v5/market/books", instId=f"{coin}-USDT", sz=400)
    if d and d.get("data"):
        out["OKX"] = (arr(d["data"][0]["bids"]), arr(d["data"][0]["asks"]))
    return {k: (sorted(b, reverse=True), sorted(a)) for k, (b, a) in out.items() if b and a}


@st.cache_data(ttl=3)
def fetch_flow(coin):
    t = get("https://api.binance.com/api/v3/aggTrades", symbol=f"{coin}USDT", limit=1000)
    if not t: return 0.0, 0.0
    buy = sum(float(x["p"]) * float(x["q"]) for x in t if not x["m"])
    sell = sum(float(x["p"]) * float(x["q"]) for x in t if x["m"])
    return (buy - sell) / (buy + sell + 1e-9), buy - sell


@st.cache_data(ttl=20)
def fetch_deriv(coin):
    s = f"{coin}USDT"
    pi = get(f"{FAPI}/fapi/v1/premiumIndex", symbol=s) or {}
    ls = get(f"{FAPI}/futures/data/globalLongShortAccountRatio", symbol=s, period="15m", limit=1) or [{}]
    oi = get(f"{FAPI}/futures/data/openInterestHist", symbol=s, period="15m", limit=48) or []
    fg = get("https://api.alternative.me/fng/", limit=1) or {}
    return dict(mark=float(pi.get("markPrice", 0) or 0), funding=float(pi.get("lastFundingRate", 0) or 0),
                ls=float(ls[0].get("longShortRatio", 1) or 1), oi=oi,
                fg=int((fg.get("data") or [{"value": 50}])[0]["value"]))


@st.cache_data(ttl=10)
def fetch_mempool():
    return get("https://mempool.space/api/mempool/recent") or [], get("https://mempool.space/api/v1/fees/recommended") or {}


@st.cache_data(ttl=300)
def fetch_bitnodes():
    d = get("https://bitnodes.io/api/v1/snapshots/latest/")
    return d.get("total_nodes") if d else None


# ---------------- analytics ----------------
def band(bids, asks, pct):
    mid = (bids[0][0] + asks[0][0]) / 2
    b = sum(p * q for p, q in bids if p >= mid * (1 - pct))
    a = sum(p * q for p, q in asks if p <= mid * (1 + pct))
    return mid, b, a


def slip(levels, usd, mid):
    rem, cost, qty = usd, 0.0, 0.0
    for p, q in levels:
        t = min(rem, p * q); cost += t; qty += t / p; rem -= t
        if rem <= 1e-9: break
    return abs(cost / qty - mid) / mid * 1e4 if rem <= 1e-9 and qty else None


def track_walls(coin, bids, asks, mid, min_usd, pct, now):
    W = st.session_state.setdefault("walls", {})
    SP = st.session_state.setdefault("spoof", deque(maxlen=500))
    FL = st.session_state.setdefault("fills", deque(maxlen=500))
    cur = {}
    for side, lv in (("bid", bids), ("ask", asks)):
        for p, q in lv:
            if abs(p - mid) / mid <= pct: cur[(coin, side, p)] = p * q
    if not cur: return
    thr = max(min_usd, 5 * statistics.median(cur.values()))
    for k, n in cur.items():
        if n >= thr:
            w = W.setdefault(k, dict(first=now, peak=n, last=n))
            w["peak"], w["last"] = max(w["peak"], n), n
    for k, w in list(W.items()):
        if k[0] != coin: continue
        _, side, p = k
        n = cur.get(k, 0)
        if k in cur: w["last"] = n
        if n >= 0.3 * w["peak"]: continue
        if k not in cur and abs(p - mid) / mid > pct * 0.9:
            del W[k]; continue                                   # drifted out of window
        crossed = (side == "bid" and mid <= p * 1.0003) or (side == "ask" and mid >= p * 0.9997)
        if crossed: FL.append((now, coin, side, w["peak"]))      # price hit it = real
        elif now - w["first"] < 90: SP.append((now, coin, side, w["peak"]))  # pulled early, untouched = spoof
        del W[k]


def analyse(coin, books, flow, dv, mid_cfg):
    now = time.time()
    pct, min_usd = mid_cfg
    bids, asks = books["Binance"]
    mid, b, a = band(bids, asks, pct)
    track_walls(coin, bids, asks, mid, min_usd, pct, now)
    obi = (b - a) / (b + a)
    ex = {k: (lambda m, bb, aa: (bb - aa) / (bb + aa))(*band(bk, ak, pct)) for k, (bk, ak) in books.items()}
    cons = sum(ex.values()) / len(ex)
    W = st.session_state["walls"]
    rb = sum(w["last"] for k, w in W.items() if k[0] == coin and k[1] == "bid" and now - w["first"] >= 30)
    ra = sum(w["last"] for k, w in W.items() if k[0] == coin and k[1] == "ask" and now - w["first"] >= 30)
    wall = (rb - ra) / (rb + ra) if rb + ra else 0.0
    sp = sum(x[3] for x in st.session_state["spoof"] if x[1] == coin and now - x[0] < 600)
    fl = sum(x[3] for x in st.session_state["fills"] if x[1] == coin and now - x[0] < 600)
    spoof_rate = sp / (sp + fl) if sp + fl else 0.0
    liq = [x for x in liq_store() if x["sym"] == f"{coin}USDT" and now - x["t"] < 300]
    sl = sum(x["usd"] for x in liq if x["side"] == "BUY")      # shorts liquidated
    ll = sum(x["usd"] for x in liq if x["side"] == "SELL")     # longs liquidated
    pulse = (sl - ll) / (sl + ll) * 100 if sl + ll else 0.0
    parts = dict(book=obi, flow=flow[0], walls=wall, cross_ex=cons,
                 funding=-clip(dv["funding"] / 0.0005) * 0.6, longshort=-clip((dv["ls"] - 1) / 0.5) * 0.6, liq=pulse / 100 * 0.6)
    w = dict(book=1.0, flow=1.0, walls=0.8, cross_ex=0.6, funding=0.4, longshort=0.4, liq=0.4)
    score = sum(parts[k] * w[k] for k in parts) / sum(w.values()) * 3 * (1 - 0.5 * spoof_rate)
    p_up = sig(3 * score)
    agree = sum(1 for k in ("book", "flow", "walls", "cross_ex") if abs(parts[k]) > 0.05 and (parts[k] > 0) == (p_up > .5))
    return dict(mid=mid, p_up=p_up, parts=parts, ex=ex, spoof_rate=spoof_rate, pulse=pulse, agree=agree, b=b, a=a,
                slip={u: (slip(asks, u, mid), slip(bids, u, mid)) for u in (10_000, 100_000, 1_000_000)}, liq=liq)


# ---------------- UI ----------------
st.sidebar.title("Order Flow Radar")
coin = st.sidebar.selectbox("Coin", COINS)
refresh = st.sidebar.slider("Refresh (sec)", 2, 15, 4)
pct = st.sidebar.slider("Book window ±%", 0.1, 3.0, 1.0) / 100
min_usd = st.sidebar.number_input("Whale wall min $", 10_000, 50_000_000, 250_000 if coin in ("BTC", "ETH") else 50_000, step=10_000)
thr = st.sidebar.slider("Signal threshold P", 0.55, 0.90, 0.68)
horizon = st.sidebar.slider("Score signals after (min)", 1, 30, 5)
min_agree = st.sidebar.slider("Min agreeing signals (of 4)", 1, 4, 3)
st.sidebar.caption("Higher threshold + more agreement = fewer signals, higher hit-rate. Check the scorecard for the REAL number.")
liq_store()


@st.fragment(run_every=refresh)
def live():
    now = time.time()
    books = fetch_books(coin)
    if "Binance" not in books:
        st.error("Binance order book unreachable (blocked region / no internet). Use a VPN or run locally.")
        return
    flow, cvd = fetch_flow(coin)
    dv = fetch_deriv(coin)
    r = analyse(coin, books, (flow, cvd), dv, (pct, min_usd))
    p = r["p_up"]
    direction = "BUYERS" if p >= thr and r["agree"] >= min_agree else "SELLERS" if p <= 1 - thr and r["agree"] >= min_agree else "WAIT"
    P = st.session_state.setdefault("preds", [])
    if direction != "WAIT" and (not P or P[-1]["coin"] != coin or now - P[-1]["t"] > 60):
        P.append(dict(t=now, coin=coin, dir=direction, p=p, entry=r["mid"], out=None))
    for x in P:
        if x["out"] is None and x["coin"] == coin and now - x["t"] >= horizon * 60:
            x["out"] = (r["mid"] > x["entry"]) == (x["dir"] == "BUYERS")

    c = st.columns(5)
    c[0].metric(f"{coin} price", f"${r['mid']:,.4f}" if r["mid"] < 10 else f"${r['mid']:,.2f}")
    c[1].metric("Signal", direction)
    c[2].metric("P(up) / P(down)", f"{p*100:.0f}% / {(1-p)*100:.0f}%")
    c[3].metric("Spoof rate (10m)", f"{r['spoof_rate']*100:.0f}%")
    done = [x for x in P if x["out"] is not None]
    c[4].metric("Live hit-rate", f"{sum(x['out'] for x in done)/len(done)*100:.0f}% ({len(done)})" if done else "collecting...")

    cur = dict(pulse=r["pulse"], flow=(flow + 1) * 50, book=r["b"] / (r["b"] + r["a"]) * 100, p=p * 100)
    PA = st.session_state.setdefault("prev_anim", {})
    allq = list(liq_store())[::-1]
    mine = [x for x in allq if x["sym"] == f"{coin}USDT"] or allq
    tape = [dict(t=time.strftime("%H:%M:%S", time.localtime(x["t"])), sym=x["sym"].replace("USDT", ""), side=x["side"], price=x["price"], usd=x["usd"], age=now - x["t"]) for x in mine[:8]]
    components.html(anim_html(dict(cur=cur, prev=PA.get(coin, cur), direction=direction, tape=tape, coin=coin)), height=560)
    PA[coin] = cur

    t1, t2 = st.tabs(["Order Book Radar", "Derivatives + Network"])
    with t1:
        l, rr = st.columns([3, 2])
        with l:
            bids, asks = books["Binance"]
            fig = go.Figure()
            bx = [x for x in bids if x[0] >= r["mid"] * (1 - pct)]
            ax = [x for x in asks if x[0] <= r["mid"] * (1 + pct)]
            fig.add_scatter(x=[x[0] for x in bx], y=pd.Series([x[0] * x[1] for x in bx]).cumsum(), fill="tozeroy", name="Bids", line_color="#2ecc71")
            fig.add_scatter(x=[x[0] for x in ax], y=pd.Series([x[0] * x[1] for x in ax]).cumsum(), fill="tozeroy", name="Asks", line_color="#e74c3c")
            fig.update_layout(title="Binance depth (cumulative $)", height=330, margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
            exdf = pd.DataFrame({"Exchange": list(r["ex"]), "Bid-heavy (+) / Ask-heavy (-)": [round(v, 3) for v in r["ex"].values()]})
            fig2 = go.Figure(go.Bar(x=exdf.iloc[:, 1], y=exdf.Exchange, orientation="h", marker_color=["#2ecc71" if v > 0 else "#e74c3c" for v in exdf.iloc[:, 1]]))
            fig2.update_layout(title="Per-exchange book bias (±window)", height=240, margin=dict(t=40, b=10))
            st.plotly_chart(fig2, use_container_width=True)
        with rr:
            st.subheader("Signal breakdown")
            st.dataframe(pd.DataFrame({"component": list(r["parts"]), "score (-1..+1)": [round(v, 3) for v in r["parts"].values()]}), hide_index=True)
            st.caption(f"CVD (last 1000 trades): ${cvd:,.0f} | taker buy-sell ratio {flow:+.2f}")
            st.subheader("Slippage (bps) buy / sell")
            st.dataframe(pd.DataFrame([{"order $": f"{u:,}", "buy": None if v[0] is None else round(v[0], 2), "sell": None if v[1] is None else round(v[1], 2)} for u, v in r["slip"].items()]), hide_index=True)
        W = st.session_state["walls"]
        rows = [dict(side=k[1].upper(), price=k[2], usd=round(w["last"]), age_s=round(now - w["first"]), status="REAL (confirmed)" if now - w["first"] >= 30 else "unconfirmed")
                for k, w in W.items() if k[0] == coin]
        st.subheader("Whale walls")
        st.dataframe(pd.DataFrame(rows).sort_values("usd", ascending=False) if rows else pd.DataFrame({"info": ["no walls above threshold"]}), hide_index=True)
        ev = [dict(ago_s=round(now - x[0]), kind="SPOOF (pulled, untouched)", side=x[2], usd=round(x[3])) for x in st.session_state["spoof"] if x[1] == coin] + \
             [dict(ago_s=round(now - x[0]), kind="REAL (price hit it)", side=x[2], usd=round(x[3])) for x in st.session_state["fills"] if x[1] == coin]
        st.subheader("Spoof / fill events")
        st.dataframe(pd.DataFrame(sorted(ev, key=lambda e: e["ago_s"])[:30]) if ev else pd.DataFrame({"info": ["none detected yet (needs a few minutes)"]}), hide_index=True)

    with t2:
        g = st.columns(3)
        for col, title, val, rng in ((g[0], "Liquidation Pulse (5m)", r["pulse"], [-100, 100]), (g[1], "Fear & Greed", dv["fg"], [0, 100])):
            f = go.Figure(go.Indicator(mode="gauge+number", value=val, title={"text": title}, gauge={"axis": {"range": rng}}))
            f.update_layout(height=230, margin=dict(t=50, b=0)); col.plotly_chart(f, use_container_width=True)
        g[2].metric("Binance L/S ratio (15m)", f"{dv['ls']:.2f}x", "short-heavy" if dv["ls"] < 1 else "long-heavy")
        g[2].metric("Funding rate", f"{dv['funding']*100:.4f}%")
        g[2].caption("Negative pulse = longs being liquidated (long-side magnet).")
        liq = [x for x in liq_store() if x["sym"] == f"{coin}USDT"]
        a1, a2 = st.columns(2)
        with a1:
            if liq:
                df = pd.DataFrame(liq)
                f = go.Figure(go.Scatter(x=pd.to_datetime(df.t, unit="s"), y=df.price, mode="markers",
                                         marker=dict(size=(df.usd ** 0.5 / 20).clip(6, 40), color=["#e74c3c" if s == "SELL" else "#2ecc71" for s in df.side], opacity=.7)))
                f.update_layout(title="Liquidations (red=longs, green=shorts) since app start", height=320, margin=dict(t=40, b=10)); st.plotly_chart(f, use_container_width=True)
            else:
                st.info("Collecting live liquidations... (needs a few minutes)")
        with a2:
            if liq:
                df = pd.DataFrame(liq); df["bin"] = (df.price / (r["mid"] * 0.002)).round() * (r["mid"] * 0.002)
                gb = df.groupby(["bin", "side"]).usd.sum().unstack(fill_value=0)
                f = go.Figure()
                if "SELL" in gb: f.add_bar(y=gb.index, x=-gb["SELL"], orientation="h", name="longs liq", marker_color="#e74c3c")
                if "BUY" in gb: f.add_bar(y=gb.index, x=gb["BUY"], orientation="h", name="shorts liq", marker_color="#2ecc71")
                f.update_layout(title="Liquidation clusters by price", height=320, barmode="relative", margin=dict(t=40, b=10)); st.plotly_chart(f, use_container_width=True)
        if dv["oi"]:
            o = pd.DataFrame(dv["oi"])
            f = go.Figure(go.Scatter(x=pd.to_datetime(o.timestamp, unit="ms"), y=o.sumOpenInterestValue.astype(float), fill="tozeroy"))
            f.update_layout(title="Open interest (USD, 12h)", height=260, margin=dict(t=40, b=10)); st.plotly_chart(f, use_container_width=True)
        st.subheader("Bitcoin network / whale alerts (mempool)")
        mp, fees = fetch_mempool()
        m1, m2, m3 = st.columns(3)
        m1.metric("Reachable nodes (Bitnodes)", fetch_bitnodes() or "n/a")
        m2.metric("Fee fast / hour (sat/vB)", f"{fees.get('fastestFee','?')} / {fees.get('hourFee','?')}")
        min_btc = m3.number_input("Whale min BTC", 1, 5000, 10)
        wh = [dict(txid=t["txid"][:14] + "...", BTC=round(t["value"] / 1e8, 2), fee_sat=t["fee"]) for t in mp if t["value"] >= min_btc * 1e8]
        st.dataframe(pd.DataFrame(wh) if wh else pd.DataFrame({"info": [f"no ≥{min_btc} BTC txs in latest mempool sample"]}), hide_index=True)

    with st.expander("Scorecard: every signal this session vs what price did"):
        if P:
            st.dataframe(pd.DataFrame([dict(time=time.strftime("%H:%M:%S", time.localtime(x["t"])), coin=x["coin"], signal=x["dir"], P_up=round(x["p"], 3),
                                            entry=x["entry"], result={None: "pending", True: "HIT", False: "MISS"}[x["out"]]) for x in reversed(P)]), hide_index=True)
        else:
            st.write("No signals yet. WAIT is normal; the bot only fires when confidence and agreement are high.")


live()
