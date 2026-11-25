"""
Order Flow Radar - Streamlit dashboard (2 tabs)
  Tab 1: Order book radar  (walls, spoof vs real, imbalance, CVD, slippage, per-exchange bias)
  Tab 2: Derivatives + network (liquidations, L/S, funding, OI, fear&greed, mempool whales, Bitnodes)
Prediction: BUYERS / SELLERS / WAIT + probability, with a LIVE scorecard of its real hit-rate.

pip install streamlit plotly pandas requests
streamlit run dashboard.py
"""
import json, math, statistics, threading, time
from collections import deque

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor
import streamlit.components.v1 as components


# ---- animated panel (merged from anim.py) ----

TEMPLATE = """
<style>
*{box-sizing:border-box}
body{margin:0;background:#07080a;color:#e8e8e8;font-family:ui-monospace,Menlo,Consolas,monospace}
.wrap{display:grid;grid-template-columns:1.05fr 1fr;gap:12px;padding:6px}
.card{background:#0d0f12;border:1px solid #1d2128;border-radius:14px;padding:14px;position:relative;overflow:hidden}
.t{font-size:11px;letter-spacing:.18em;color:#8a919c;text-transform:uppercase}
.big{font-size:44px;font-weight:800;text-align:center;margin-top:-62px;text-shadow:0 0 18px currentColor}
.tag{display:block;margin:8px auto 0;width:max-content;padding:6px 16px;border-radius:12px;border:1px solid #6b4a2a;background:#2a1c10;color:#ffb35c;font-weight:700;letter-spacing:.12em;font-size:13px}
.bar{height:26px;border-radius:13px;background:#ff4d5e;overflow:hidden;display:flex;margin:6px 0 4px;box-shadow:0 0 14px #ff4d5e33}
.bar .g{background:linear-gradient(90deg,#1fd18b,#3df0a9);width:__W1__%;transition:width 1.2s cubic-bezier(.2,.8,.2,1)}
.lbl{display:flex;justify-content:space-between;font-size:12px;color:#8a919c;margin-bottom:10px}
.badge{display:inline-block;padding:8px 22px;border-radius:12px;font-weight:800;letter-spacing:.14em;font-size:20px;animation:pulse 1.4s infinite}
.BUYERS{background:#0f3d2b;color:#3df0a9;border:1px solid #3df0a9}
.SELLERS{background:#40161c;color:#ff6b7a;border:1px solid #ff6b7a}
.WAIT{background:#3b2f10;color:#f6c85f;border:1px solid #f6c85f}
@keyframes pulse{0%{box-shadow:0 0 0 0 currentColor}70%{box-shadow:0 0 0 14px transparent}100%{box-shadow:0 0 0 0 transparent}}
ul{list-style:none;margin:8px 0 0;padding:0}
li{display:flex;justify-content:space-between;font-size:13px;padding:5px 6px;border-bottom:1px solid #161a20;animation:slide .6s ease-out}
li.new{animation:slide .6s ease-out,flash 1.6s ease-out}
.S{color:#3df0a9}.L{color:#ff6b7a}
@keyframes slide{from{opacity:0;transform:translateX(-24px)}to{opacity:1;transform:none}}
@keyframes flash{0%{background:#ffffff30}100%{background:transparent}}
</style>
<div class="wrap">
 <div class="card">
  <div class="t">Liquidation Pulse Index &middot; <span id="coin"></span></div>
  <svg viewBox="0 0 300 175" width="100%">
   <defs><linearGradient id="gr" x1="0" x2="1"><stop offset="0" stop-color="#2de2a6"/><stop offset=".35" stop-color="#22c1f1"/><stop offset=".6" stop-color="#f6c85f"/><stop offset="1" stop-color="#ff6b6b"/></linearGradient>
   <filter id="gl"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
   <path d="M 30 150 A 120 120 0 0 1 270 150" fill="none" stroke="url(#gr)" stroke-width="16" stroke-linecap="round" filter="url(#gl)" opacity=".9"/>
   <circle id="dot" r="8" fill="#ffd166" filter="url(#gl)"/><circle id="ring" r="14" fill="none" stroke="#ffd166" stroke-width="2" opacity=".5"><animate attributeName="r" values="10;20;10" dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values=".7;0;.7" dur="1.6s" repeatCount="indefinite"/></circle>
  </svg>
  <div class="big" id="num">0</div>
  <span class="tag" id="tag"></span>
 </div>
 <div class="card">
  <div class="t">Signal</div>
  <div style="margin:8px 0 12px"><span id="badge" class="badge"></span> &nbsp;<span id="pup" style="font-size:22px;font-weight:800"></span></div>
  <div class="t">Taker flow (buying vs selling)</div>
  <div class="bar"><div class="g" id="b1"></div></div><div class="lbl"><span id="l1a"></span><span id="l1b"></span></div>
  <div class="t">Order book (bids vs asks)</div>
  <div class="bar"><div class="g" id="b2"></div></div><div class="lbl"><span id="l2a"></span><span id="l2b"></span></div>
 </div>
 <div class="card" style="grid-column:1/3">
  <div class="t"><span style="color:#3df0a9">&#9679;</span> Live liquidation tape</div><ul id="tape"></ul>
 </div>
</div>
<script>
const D=__DATA__, c=D.cur, p=D.prev;
const $=id=>document.getElementById(id);
function ease(t){return 1-Math.pow(1-t,3)}
function anim(a,b,ms,fn){const s=performance.now();(function f(n){const t=Math.min(1,(n-s)/ms);fn(a+(b-a)*ease(t));if(t<1)requestAnimationFrame(f)})(s)}
$("coin").textContent=D.coin;
function setDot(v){const a=Math.PI*(1-(v+100)/200);$("dot").setAttribute("cx",150+120*Math.cos(a));$("dot").setAttribute("cy",150-120*Math.sin(a));$("ring").setAttribute("cx",150+120*Math.cos(a));$("ring").setAttribute("cy",150-120*Math.sin(a));}
anim(p.pulse,c.pulse,1200,v=>{setDot(v);$("num").textContent=Math.round(v);$("num").style.color=v<-10?"#ffb35c":v>10?"#3df0a9":"#e8e8e8"});
$("tag").textContent=c.pulse<=-40?"CASCADE RISK (LONGS)":c.pulse>=40?"SQUEEZE RISK (SHORTS)":"BALANCED";
const bd=$("badge");bd.textContent=D.direction;bd.className="badge "+D.direction;
anim(p.p,c.p,1000,v=>{$("pup").innerHTML="P(up) "+v.toFixed(0)+"% <span style='color:#8a919c;font-size:14px'>/ down "+(100-v).toFixed(0)+"%</span>"});
function tug(id,la,lb,pv,cv,na,nb){$(id).style.width=pv+"%";setTimeout(()=>{$(id).style.width=cv+"%"},60);$(la).innerHTML="<span style='color:#3df0a9'>"+na+" "+cv.toFixed(0)+"%</span>";$(lb).innerHTML="<span style='color:#ff6b7a'>"+(100-cv).toFixed(0)+"% "+nb+"</span>"}
tug("b1","l1a","l1b",p.flow,c.flow,"BUYING","SELLING");tug("b2","l2a","l2b",p.book,c.book,"BIDS","ASKS");
$("tape").innerHTML=D.tape.length?D.tape.map(x=>{const s=x.side=="BUY";return "<li class='"+(x.age<15?"new":"")+"'><span>"+x.t+"</span><span>"+x.sym+"</span><span class='"+(s?"S":"L")+"'>"+(s?"SHORT":"LONG")+" LIQ @ "+x.price.toLocaleString(undefined,{maximumFractionDigits:4})+"</span><span>$"+Math.round(x.usd).toLocaleString()+"</span></li>"}).join(""):"<li><span>waiting for liquidations...</span></li>";
</script>
"""


def anim_html(data):
    html = TEMPLATE.replace("__DATA__", json.dumps(data)).replace("__W1__", str(round(data["prev"]["flow"], 1)))
    return html


st.set_page_config(page_title="Order Flow Radar", layout="wide")
st.markdown("""<style>
.stApp{background:radial-gradient(1200px 600px at 8% -10%,#0f1c18 0,#07080a 55%)}
html,body,[class*="css"]{font-family:ui-monospace,Menlo,Consolas,monospace}
[data-testid="stMetric"]{background:#0d0f12;border:1px solid #1d2128;border-radius:14px;padding:12px}
[data-testid="stMetricValue"]{text-shadow:0 0 14px #3df0a955}
.card{background:#0d0f12;border:1px solid #1d2128;border-radius:14px;padding:14px;margin-bottom:10px}
.k{font-size:11px;letter-spacing:.16em;color:#8a919c;text-transform:uppercase}.v{font-size:30px;font-weight:800;line-height:1.2}
.g{color:#3df0a9}.r{color:#ff6b7a}.y{color:#f6c85f}.c{color:#22c1f1}
.al{display:flex;justify-content:space-between;gap:10px;background:#0d0f12;border:1px solid #1d2128;border-left:3px solid #ff6b7a;border-radius:10px;padding:10px 12px;margin-bottom:8px;font-size:13px}
.bd{font-size:10px;border:1px solid #666;border-radius:6px;padding:1px 6px;margin-left:6px}
</style>""", unsafe_allow_html=True)


def card(k, v, sub="", cls=""):
    st.markdown(f'<div class="card"><div class="k">{k}</div><div class="v {cls}">{v}</div><div class="k">{sub}</div></div>', unsafe_allow_html=True)


def ur(t): st.caption('🗣 ' + t)


def usd(x): return f"${x/1e6:.2f}M" if abs(x) >= 1e6 else f"${x/1e3:.0f}K" if abs(x) >= 1e3 else f"${x:.0f}"
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"
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
STABLES = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "USDE", "USD1", "EUR", "PAXG", "WBTC"}


@st.cache_resource
def watch(): return set(COINS[:8])


@st.cache_resource
def liq_status(): return dict(ok=0, err="", n=0, bad=set())


@st.cache_resource
def liq_store():
    """Background thread: liquidations from OKX public REST for the watch-list (top coins + the coin you select)."""
    dq, seen, ctv, W, ST = deque(maxlen=20000), set(), {}, watch(), liq_status()

    def run():
        while True:
            for coin in list(W):
                if coin in ST["bad"]: continue
                try:
                    u = f"{coin}-USDT"
                    if coin not in ctv:
                        i = get("https://www.okx.com/api/v5/public/instruments", instType="SWAP", instFamily=u)
                        if not (i and i.get("data")):
                            ST["bad"].add(coin); continue
                        ctv[coin] = float(i["data"][0]["ctVal"])
                    d = get("https://www.okx.com/api/v5/public/liquidation-orders", instType="SWAP", instFamily=u, state="filled")
                    if d is None:
                        ST["err"] = "OKX unreachable (blocked/rate-limited)"; continue
                    ST["ok"], ST["err"] = time.time(), ""
                    for grp in d.get("data", []):
                        for x in grp.get("details", []):
                            k = (u, x["ts"], x["bkPx"], x["sz"])
                            if k in seen: continue
                            seen.add(k)
                            px = float(x["bkPx"])
                            long_liq = x.get("posSide") == "long" or (x.get("posSide") == "net" and x.get("side") == "sell")
                            dq.append(dict(t=int(x["ts"]) / 1000, sym=f"{coin}USDT", side="SELL" if long_liq else "BUY", price=px, usd=px * float(x["sz"]) * ctv[coin]))
                    ST["n"] = len(dq)
                except Exception as e:
                    ST["err"] = str(e)[:80]
                time.sleep(0.5)
            time.sleep(2)

    threading.Thread(target=run, daemon=True).start()
    return dq


@st.cache_data(ttl=60)
def ticker_all():
    """Top-100 USDT coins by volume with price, 24h change, and spread, from ONE MEXC call."""
    d = get("https://api.mexc.com/api/v3/ticker/24hr") or []
    rows = []
    for x in d:
        sy = x.get("symbol", "")
        if not sy.endswith("USDT"): continue
        b = sy[:-4]
        if b in STABLES or b.endswith(("3L", "3S", "5L", "5S")): continue
        try:
            last, op = float(x["lastPrice"]), float(x.get("openPrice") or 0)
            bid, ask = float(x.get("bidPrice") or 0), float(x.get("askPrice") or 0)
            rows.append(dict(coin=b, price=last, chg=(last / op - 1) * 100 if op else 0.0, vol=float(x.get("quoteVolume") or 0),
                             spread_bps=(ask - bid) / ((ask + bid) / 2) * 1e4 if bid and ask else None))
        except Exception:
            pass
    rows.sort(key=lambda r_: -r_["vol"])
    return rows[:100]


@st.cache_data(ttl=2)
def fetch_books(coin):
    out = {}
    d = get("https://api.mexc.com/api/v3/depth", symbol=f"{coin}USDT", limit=500)
    if d: out["MEXC"] = (arr(d["bids"]), arr(d["asks"]))
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
    t = get("https://api.mexc.com/api/v3/trades", symbol=f"{coin}USDT", limit=1000)
    if not t: return 0.0, 0.0
    buy = sell = 0.0
    for x in t:
        usd = float(x.get("price", x.get("p", 0))) * float(x.get("qty", x.get("q", 0)))
        if x.get("isBuyerMaker", x.get("m", False)): sell += usd
        else: buy += usd
    return (buy - sell) / (buy + sell + 1e-9), buy - sell


@st.cache_data(ttl=20)
def fetch_deriv(coin):
    tk = (get("https://contract.mexc.com/api/v1/contract/ticker", symbol=f"{coin}_USDT") or {}).get("data") or {}
    if isinstance(tk, list): tk = tk[0] if tk else {}
    ls = (get("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio", ccy=coin, period="5m") or {}).get("data") or [[0, 1]]
    oi = (get("https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume", ccy=coin, period="5m") or {}).get("data") or []
    fg = get("https://api.alternative.me/fng/", limit=1) or {}
    return dict(mark=float(tk.get("fairPrice", 0) or 0), funding=float(tk.get("fundingRate", 0) or 0),
                ls=float(ls[0][1] or 1), oi=[dict(timestamp=int(r[0]), sumOpenInterestValue=r[1]) for r in oi[::-1]],
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
        if crossed: FL.append((now, coin, side, w["peak"], now - w["first"], p))      # price hit it = real
        elif now - w["first"] < 90: SP.append((now, coin, side, w["peak"], now - w["first"], p))  # pulled early, untouched = spoof
        del W[k]


def analyse(coin, books, flow, dv, mid_cfg):
    now = time.time()
    pct, min_usd = mid_cfg
    bids, asks = books["MEXC"]
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
    liq = [x for x in liq_store() if x["sym"] == f"{coin}USDT" and now - x["t"] < 600]
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



# ---------------- extra analytics (v2) ----------------
@st.cache_data(ttl=5)
def fetch_trades(coin):
    t = get("https://api.mexc.com/api/v3/trades", symbol=f"{coin}USDT", limit=1000) or []
    return [(float(x["price"]), float(x["qty"]), bool(x.get("isBuyerMaker")), x.get("time", 0)) for x in t]


def vpin(trades, n=30):
    """Volume-bucketed |buy-sell| imbalance (VPIN). Returns list of bucket imbalances."""
    if len(trades) < 100: return []
    bs = sum(q for _, q, _, _ in trades) / n
    b = s = cur = 0.0; out = []
    for _, q, m, _ in trades:
        rem = q
        while rem > 1e-15:
            take = min(rem, bs - cur)
            if m: s += take
            else: b += take
            cur += take; rem -= take
            if cur >= bs - 1e-12:
                out.append(abs(b - s) / bs); b = s = cur = 0.0
    return out


@st.cache_data(ttl=3)
def fetch_hl(coin):
    try:
        return float(S.post("https://api.hyperliquid.xyz/info", json={"type": "allMids"}, timeout=6).json()[coin])
    except Exception:
        return None


@st.cache_data(ttl=60)
def fetch_hist(coin):
    k = get("https://api.mexc.com/api/v3/klines", symbol=f"{coin}USDT", interval="5m", limit=288) or []
    return [float(x[4]) for x in k]


@st.cache_data(ttl=30)
def footprint(coins):
    def one(c):
        t = get("https://api.mexc.com/api/v3/trades", symbol=f"{c}USDT", limit=500) or []
        k = get("https://api.mexc.com/api/v3/klines", symbol=f"{c}USDT", interval="1m", limit=60) or []
        if len(t) < 50 or len(k) < 30: return None
        buy = sum(float(x["price"]) * float(x["qty"]) for x in t if not x["isBuyerMaker"])
        sell = sum(float(x["price"]) * float(x["qty"]) for x in t if x["isBuyerMaker"])
        chg = (float(t[-1]["price"]) / float(t[0]["price"]) - 1) * 100
        t0_, t1_ = t[0].get("time") or 0, t[-1].get("time") or 0
        win = round((t1_ - t0_) / 1000) if t0_ and t1_ else None
        v = [float(x[5]) for x in k]; mu, sd = statistics.mean(v[:-1]), statistics.pstdev(v[:-1]) or 1
        bsh = buy / (buy + sell + 1e-9)
        fp = ("Bearish Absorption" if bsh > .55 and chg <= 0.02 else "Bullish Absorption" if bsh < .45 and chg >= -0.02
              else "Buy Pressure" if bsh > .55 else "Sell Pressure" if bsh < .45 else "Neutral")
        return dict(coin=c, price=float(t[-1]["price"]), footprint=fp, buy_pct=round(bsh * 100), delta_usd=round(buy - sell), vol_sigma=round((v[-1] - mu) / sd, 1), move_pct=round(chg, 3), window_s=win)
    with ThreadPoolExecutor(8) as ex:
        return [x for x in ex.map(one, coins) if x]


@st.cache_data(ttl=60)
def funding_heat():
    d = (get("https://contract.mexc.com/api/v1/contract/ticker") or {}).get("data") or []
    f = {x["symbol"].split("_")[0]: float(x.get("fundingRate") or 0) for x in d if x.get("symbol", "").endswith("_USDT")}
    vals = sorted(abs(v) for v in f.values())
    return {c: (round(100 * sum(1 for v in vals if v <= abs(f[c])) / len(vals)), f[c]) for c in COINS if c in f and vals}


def update_verdict(coin, obi, now, hold):
    V = st.session_state.setdefault("verdict", {}).setdefault(coin, dict(ema=obi, t=now, cur="Balanced", cand="Balanced", since=now, held=now))
    V["ema"] = obi; V["t"] = now; hold = max(hold, 1)   # raw OBI, no EMA
    cand = "Buyers in control" if V["ema"] > 0.15 else "Sellers in control" if V["ema"] < -0.15 else "Balanced"
    if cand != V["cand"]: V["cand"], V["since"] = cand, now
    if cand != V["cur"] and now - V["since"] >= hold: V["cur"], V["held"] = cand, now
    V["pending"] = cand if cand != V["cur"] else None
    V["prog"] = min(1.0, (now - V["since"]) / hold) if V["pending"] else 0.0
    return V


def scenario(books, mid, dv, pulse):
    bids, asks = books["MEXC"]
    def best(levels):
        c = [(p, p * q) for p, q in levels if abs(p - mid) / mid <= 0.02]
        if not c: return None
        med = statistics.median(n for _, n in c); p, n = max(c, key=lambda x: x[1])
        return dict(price=p, dist=(p - mid) / mid * 100, strength=min(100, round(100 * n / (n + 4 * med))), usd=n)
    lsq = clip((dv["ls"] - 1) / 0.5, 0, 1) * 50 + clip(dv["funding"] / 0.0005, 0, 1) * 30 + clip(-pulse / 100, 0, 1) * 20
    ssq = clip((1 - dv["ls"]) / 0.5, 0, 1) * 50 + clip(-dv["funding"] / 0.0005, 0, 1) * 30 + clip(pulse / 100, 0, 1) * 20
    return best(asks), best(bids), round(lsq), round(ssq)


def add_alert(kind, key, sev, text, now):
    A = st.session_state.setdefault("alerts", [])
    if any(a["kind"] == kind and a["key"] == key and now - a["t"] < 180 for a in A): return
    A.append(dict(t=now, kind=kind, key=key, sev=sev, text=text)); del A[:-60]



@st.cache_data(ttl=15)
def scan_books(coins):
    def one(c):
        d = get("https://api.mexc.com/api/v3/depth", symbol=f"{c}USDT", limit=100)
        return c, ((sorted(arr(d["bids"]), reverse=True), sorted(arr(d["asks"]))) if d and d.get("bids") and d.get("asks") else None)
    with ThreadPoolExecutor(10) as ex:
        return dict(ex.map(one, coins))


def update_absorption(c, f, now):
    A = st.session_state.setdefault("absorb", {}); H = st.session_state.setdefault("absorb_hist", [])
    cur = A.get(c)
    kind = f["footprint"] if f and "Absorption" in f["footprint"] else None
    if kind:
        px = f["price"]
        if cur and cur["kind"] == kind and now - cur["last"] < 90:
            cur.update(last=now, hi=max(cur["hi"], px), lo=min(cur["lo"], px))
        else:
            if cur: H.append(dict(cur)); del H[:-200]
            A[c] = dict(coin=c, kind=kind, start=now, last=now, p0=px, hi=px, lo=px)
    elif cur and now - cur["last"] >= 90:
        H.append(dict(cur)); del H[:-200]; del A[c]


def run_scan(rows, n, now, skip):
    for k in ("walls", "fills"): st.session_state.setdefault(k, {} if k == "walls" else deque(maxlen=500))
    st.session_state.setdefault("spoof", deque(maxlen=500))
    coins = tuple(r_["coin"] for r_ in rows[:n])
    bk, fps = scan_books(coins), {x["coin"]: x for x in footprint(coins)}
    W, out = st.session_state["walls"], []
    for i, r_ in enumerate(rows):
        row = dict(r_, rank=i + 1)
        if i < n:
            c, b = r_["coin"], bk.get(r_["coin"])
            if b:
                mid, bb, aa = band(b[0], b[1], 0.01)
                if c != skip: track_walls(c, b[0], b[1], mid, 15000, 0.01, now)
                row["bid_pct"] = round(bb / (bb + aa + 1e-9) * 100)
            conf = [w for k, w in W.items() if k[0] == c and now - w["first"] >= 30]
            row["conf_walls"], row["conf_usd"] = len(conf), round(sum(w["last"] for w in conf))
            row["unconf"] = sum(1 for k, w in W.items() if k[0] == c and now - w["first"] < 30)
            row["spoof_10m"] = sum(1 for x in st.session_state["spoof"] if x[1] == c and now - x[0] < 600)
            f = fps.get(c)
            if f:
                row.update(footprint=f["footprint"], buy_pct=f["buy_pct"], vol_sigma=f["vol_sigma"])
                update_absorption(c, f, now)
            bp, by = row.get("bid_pct"), row.get("buy_pct")
            row["bias"] = "" if bp is None or by is None else "🟢 BULL" if bp > 55 and by > 52 else "🔴 BEAR" if bp < 45 and by < 48 else "⚪ MIXED"
        out.append(row)
    return out


def final_call(coin, p, agree, now, margin, hold):
    """Raw live signal from current data (NO EMA, no averaging, no lag).
    Anti-flicker is only a dead zone: LONG flips to SHORT only when raw P(up) <= 50% - margin (and vice versa)."""
    C = st.session_state.setdefault("call", {}).setdefault(coin, dict(dir=None, since=now))
    flipped = False
    want = "LONG" if p >= 0.5 + margin else "SHORT" if p <= 0.5 - margin else None
    if C["dir"] is None:
        C["dir"], C["since"], flipped = ("LONG" if p >= .5 else "SHORT"), now, True
    elif want and want != C["dir"] and now - C["since"] >= hold:
        C["dir"], C["since"], flipped = want, now, True
    e = abs(p - .5)
    conf = "HIGH" if e > .2 and agree >= 3 else "MEDIUM" if e > .1 else "LOW"
    return dict(label=f"{'LONG ▲' if C['dir'] == 'LONG' else 'SHORT ▼'} ({conf})", dir=C["dir"], conf=conf, p=p, flipped=flipped, age=now - C["since"])


def live_fg(parts, flow, dv, hist, pulse):
    comps = {"taker flow": flow, "book imbalance": parts["book"], "funding": clip(dv["funding"] / 0.0005),
             "long/short crowd": clip((dv["ls"] - 1) / 0.5), "liquidations (shorts-longs)": pulse / 100}
    if hist: comps["24h momentum"] = clip((hist[-1] / hist[0] - 1) / 0.05)
    sc = round(50 + 50 * sum(comps.values()) / len(comps))
    return sc, comps, ("Extreme Fear" if sc < 25 else "Fear" if sc < 45 else "Neutral" if sc < 55 else "Greed" if sc < 75 else "Extreme Greed")


# ---------------- UI ----------------
st.sidebar.title("Order Flow Radar")
TOP = [x["coin"] for x in ticker_all()] or COINS
coin = st.sidebar.selectbox("Coin (click, then type to search: top 100)", TOP)
watch().add(coin)
refresh = st.sidebar.slider("Refresh (sec)", 2, 15, 4)
pct = st.sidebar.slider("Book window ±%", 0.1, 3.0, 1.0) / 100
min_usd = st.sidebar.number_input("Whale wall min $", 10_000, 50_000_000, 250_000 if coin in ("BTC", "ETH") else 50_000, step=10_000)
margin = st.sidebar.slider("Dead zone around 50% (anti-flicker)", 0.00, 0.20, 0.06)
hold_s = st.sidebar.slider("Min hold before signal flips (sec, 0 = instant)", 0, 120, 0)
deep_n = st.sidebar.slider("Deep-scan coins (top N of 100)", 10, 100, 30)
horizon = st.sidebar.slider("Score signals after (min)", 1, 30, 5)
persist = st.sidebar.slider("Verdict must hold (min, 0 = instant)", 0, 10, 0)
addrs = [a.strip() for a in st.sidebar.text_area("BTC addresses to watch (one per line)").splitlines() if a.strip()]
st.sidebar.caption("Higher threshold + more agreement = fewer signals, higher hit-rate. Check the scorecard for the REAL number.")
liq_store()


@st.fragment(run_every=refresh)
def live():
    now = time.time()
    _t0 = time.time()
    books = fetch_books(coin)
    lag = int((time.time() - _t0) * 1000)
    if "MEXC" not in books:
        st.error("MEXC order book unreachable. Check internet / try a VPN.")
        return
    flow, cvd = fetch_flow(coin)
    dv = fetch_deriv(coin)
    r = analyse(coin, books, (flow, cvd), dv, (pct, min_usd))
    p = r["p_up"]
    call = final_call(coin, p, r["agree"], now, margin, hold_s)
    direction = {"LONG": "BUYERS", "SHORT": "SELLERS", None: "WAIT"}[call["dir"]]
    P = st.session_state.setdefault("preds", [])
    if call["flipped"]:
        P.append(dict(t=now, coin=coin, dir=direction, p=p, entry=r["mid"], out=None))
    for x in P:
        if x["out"] is None and x["coin"] == coin and now - x["t"] >= horizon * 60:
            x["out"] = (r["mid"] > x["entry"]) == (x["dir"] == "BUYERS")

    c = st.columns(5)
    c[0].metric(f"{coin} price", f"${r['mid']:,.4f}" if r["mid"] < 10 else f"${r['mid']:,.2f}")
    c[1].metric("Signal (latched)", call["label"], f"held {call['age']/60:.1f} min" if call["dir"] else None)
    c[2].metric("P(up) / P(down)", f"{p*100:.0f}% / {(1-p)*100:.0f}%")
    c[3].metric("Spoof rate (10m)", f"{r['spoof_rate']*100:.0f}%")
    done = [x for x in P if x["out"] is not None]
    c[4].metric("Live hit-rate", f"{sum(x['out'] for x in done)/len(done)*100:.0f}% ({len(done)})" if done else "collecting...")

    pdir = call.get("p", 0.5) if call["dir"] == "LONG" else 1 - call.get("p", 0.5)
    st.info(f"🗣 {coin}: abhi market {'LONG (upar jayega)' if call['dir'] == 'LONG' else 'SHORT (neeche jayega)' if call['dir'] == 'SHORT' else 'ka data jama ho raha hai'}, imkaan {pdir*100:.0f}% (live data se, bina EMA ke). "
            f"Confidence {call['conf']}. Signal {call['age']/60:.1f} minute se tika hua hai; sirf tab badlega jab raw probability 50% ke dead-zone se bahar jaye. Guarantee nahi.")
    cur = dict(pulse=r["pulse"], flow=(flow + 1) * 50, book=r["b"] / (r["b"] + r["a"]) * 100, p=p * 100)
    PA = st.session_state.setdefault("prev_anim", {})
    allq = sorted(liq_store(), key=lambda x: -x["t"])
    mine = [x for x in allq if x["sym"] == f"{coin}USDT"] or allq
    tape = [dict(t=time.strftime("%H:%M:%S", time.localtime(x["t"])), sym=x["sym"].replace("USDT", ""), side=x["side"], price=x["price"], usd=x["usd"], age=now - x["t"]) for x in mine[:8]]
    components.html(anim_html(dict(cur=cur, prev=PA.get(coin, cur), direction=direction, tape=tape, coin=coin)), height=560)
    PA[coin] = cur

    tabs = st.tabs(["Radar", "Order Book: Real vs Fake", "Derivatives + Network", "Liquidations", "Whales + Market", "Top 100 + Absorption"])
    t1, t2 = tabs[1], tabs[2]
    with t1:
        l, rr = st.columns([3, 2])
        with l:
            bids, asks = books["MEXC"]
            fig = go.Figure()
            bx = [x for x in bids if x[0] >= r["mid"] * (1 - pct)]
            ax = [x for x in asks if x[0] <= r["mid"] * (1 + pct)]
            fig.add_scatter(x=[x[0] for x in bx], y=pd.Series([x[0] * x[1] for x in bx]).cumsum(), fill="tozeroy", name="Bids", line_color="#2ecc71")
            fig.add_scatter(x=[x[0] for x in ax], y=pd.Series([x[0] * x[1] for x in ax]).cumsum(), fill="tozeroy", name="Asks", line_color="#e74c3c")
            for k_, w_ in st.session_state["walls"].items():
                if k_[0] == coin: fig.add_vline(x=k_[2], line_dash="dot", line_color=("#3df0a9" if k_[1] == "bid" else "#ff6b7a") if now - w_["first"] >= 30 else "#f6c85f")
            fig.update_layout(title="MEXC depth (cumulative $) + walls", template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=330, margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
            ur("Dotted line = wall. Hari/laal = CONFIRMED (asli, 30s+ tiki), peeli = unconfirmed (abhi naya, bharosa mat karo). Graph ka dher bada ho to wahan support/resistance zyada hai.")
            exdf = pd.DataFrame({"Exchange": list(r["ex"]), "Bid-heavy (+) / Ask-heavy (-)": [round(v, 3) for v in r["ex"].values()]})
            fig2 = go.Figure(go.Bar(x=exdf.iloc[:, 1], y=exdf.Exchange, orientation="h", marker_color=["#2ecc71" if v > 0 else "#e74c3c" for v in exdf.iloc[:, 1]]))
            fig2.update_layout(title="Per-exchange book bias (±window)", height=240, margin=dict(t=40, b=10))
            st.plotly_chart(fig2, use_container_width=True)
            ur("Har exchange ka book bias. Zyada hara = wahan bids zyada (buyers), zyada laal = asks zyada (sellers). Sab ek taraf hon to signal mazboot.")
        with rr:
            st.subheader("Signal breakdown")
            st.dataframe(pd.DataFrame({"component": list(r["parts"]), "score (-1..+1)": [round(v, 3) for v in r["parts"].values()]}), hide_index=True)
            st.caption(f"CVD (last 1000 trades): ${cvd:,.0f} | taker buy-sell ratio {flow:+.2f}")
            ur("CVD positive = market buyers asli trades mein aage hain; negative = sellers. Yeh order book se zyada sachcha hai.")
            st.subheader("Slippage (bps) buy / sell")
            st.dataframe(pd.DataFrame([{"order $": f"{u:,}", "buy": None if v[0] is None else round(v[0], 2), "sell": None if v[1] is None else round(v[1], 2)} for u, v in r["slip"].items()]), hide_index=True)
            ur("Slippage = itna paisa market order mein price se door bhar kar milega. Jitni kam bps, utna liquid coin.")
        W = st.session_state["walls"]
        wl = []
        for k, w in W.items():
            if k[0] != coin: continue
            wl.append(dict(status="🟢 CONFIRMED (real)" if now - w["first"] >= 30 else "🟡 unconfirmed", side=k[1].upper(), price=k[2],
                           dist_pct=round((k[2] - r["mid"]) / r["mid"] * 100, 3), size_usd=round(w["last"]),
                           first_seen=time.strftime("%H:%M:%S", time.localtime(w["first"])), age_s=round(now - w["first"])))
        st.subheader("Walls at live price: CONFIRMED vs unconfirmed")
        cc = {"price": st.column_config.NumberColumn(format="%.6g"), "size_usd": st.column_config.NumberColumn(format="$%d"), "dist_pct": st.column_config.NumberColumn("dist %", format="%+.3f")}
        if wl:
            wdf = pd.DataFrame(wl); wdf = wdf.reindex(wdf.dist_pct.abs().sort_values().index)
            st.dataframe(wdf, hide_index=True, use_container_width=True, column_config=cc)
            nc = [x for x in wl if x["status"].startswith("🟢")]
            if nc:
                z = min(nc, key=lambda x: abs(x["dist_pct"]))
                ur(f"Live price ke sab se qareeb CONFIRMED wall ${z['price']:,.6g} par hai ({z['side']}, {usd(z['size_usd'])}, {z['dist_pct']:+.2f}% door). Yeh asli order hai.")
            else:
                ur("Abhi koi wall confirmed nahi (sab naye hain). 30 second tikne ka intezar karein.")
        else:
            ur("Threshold se bara koi wall nahi. Sidebar mein Whale wall min $ kam karein.")
        q1, q2 = st.columns(2)
        sp_ = [x for x in st.session_state["spoof"] if x[1] == coin and len(x) >= 6]
        fl_ = [x for x in st.session_state["fills"] if x[1] == coin and len(x) >= 6]
        with q1:
            st.subheader("SPOOFING (fake): kahan, kis price par")
            if sp_:
                st.dataframe(pd.DataFrame([dict(ago_s=round(now - x[0]), side=x[2].upper(), price=x[5], dist_pct=round((x[5] - r["mid"]) / r["mid"] * 100, 3),
                                                size_usd=round(x[3]), lived_s=round(x[4]), near="NEAR LIVE PRICE" if abs((x[5] - r["mid"]) / r["mid"]) < 0.003 else "") for x in sorted(sp_, key=lambda e: -e[0])[:25]]),
                             hide_index=True, use_container_width=True, column_config=cc)
                nz = [x for x in sp_ if abs((x[5] - r["mid"]) / r["mid"]) < 0.003]
                ur(f"Live price ke bilkul paas {len(nz)} fake order pakre gaye (0.3% ke andar). Yeh bina touch hue cancel hue, inpar bharosa mat karo." if nz else "Abhi live price ke paas koi spoofing nahi pakri gayi.")
            else:
                st.info("Abhi koi spoof nahi mila (kuch minute chalne dein).")
        with q2:
            st.subheader("TAPE: REAL touch (price wall mein trade hua)")
            if fl_:
                st.dataframe(pd.DataFrame([dict(ago_s=round(now - x[0]), side=x[2].upper(), price=x[5], size_usd=round(x[3]), held_s=round(x[4])) for x in sorted(fl_, key=lambda e: -e[0])[:25]]),
                             hide_index=True, use_container_width=True, column_config=cc)
                ur("Yeh woh prices hain jahan wall asli tha aur price ne usay actually touch/trade kiya.")
            else:
                st.info("Abhi koi real touch nahi hua.")

    with t2:
        g = st.columns(3)
        for col, title, val, rng in ((g[0], "Liquidation Pulse (5m)", r["pulse"], [-100, 100]), (g[1], "Official Fear & Greed (market-wide, daily)", dv["fg"], [0, 100])):
            f = go.Figure(go.Indicator(mode="gauge+number", value=val, title={"text": title}, gauge={"axis": {"range": rng}}))
            f.update_layout(height=230, margin=dict(t=50, b=0)); col.plotly_chart(f, use_container_width=True)
        g[2].metric("L/S ratio (OKX 5m)", f"{dv['ls']:.2f}x", "short-heavy" if dv["ls"] < 1 else "long-heavy")
        g[2].metric("Funding rate", f"{dv['funding']*100:.4f}%")
        g[2].caption("Negative pulse = longs being liquidated (long-side magnet).")
        ur("Liquidation Pulse: minus = longs ki liquidation (neeche ka dabao), plus = shorts ki liquidation (upar ka squeeze).")
        fgs, fgc, fgl = live_fg(r["parts"], flow, dv, fetch_hist(coin), r["pulse"])
        h1, h2 = st.columns([1, 2])
        gg = go.Figure(go.Indicator(mode="gauge+number", value=fgs, title={"text": f"LIVE order-flow Fear/Greed: {fgl}"}, gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#f6c85f"}}))
        gg.update_layout(height=240, margin=dict(t=60, b=0), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)"); h1.plotly_chart(gg, use_container_width=True)
        h2.dataframe(pd.DataFrame({"component": list(fgc), "-1 fear ... +1 greed": [round(v, 2) for v in fgc.values()]}), hide_index=True)
        ur("Official index poore market ka rozana andaza hai. LIVE index is coin ke asli flow, funding, long/short aur liquidation se banta hai, isliye zyada realistic hai.")
        liq = [x for x in liq_store() if x["sym"] == f"{coin}USDT"]
        a1, a2 = st.columns(2)
        with a1:
            if liq:
                df = pd.DataFrame(liq)
                f = go.Figure(go.Scatter(x=pd.to_datetime(df.t, unit="s"), y=df.price, mode="markers",
                                         marker=dict(size=(df.usd ** 0.5 / 20).clip(6, 40), color=["#e74c3c" if s == "SELL" else "#2ecc71" for s in df.side], opacity=.7)))
                f.update_layout(title="Liquidations from OKX (red=longs, green=shorts)", height=320, margin=dict(t=40, b=10)); st.plotly_chart(f, use_container_width=True)
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
                tot_ = gb.sum(axis=1); pk_ = tot_.idxmax(); dom_ = "LONGS" if gb.loc[pk_].get("SELL", 0) >= gb.loc[pk_].get("BUY", 0) else "SHORTS"
                ur(f"Sab se bara liquidation cluster ${pk_:,.6g} ke qareeb hai ({dom_} ki liquidation, {usd(tot_[pk_])}). Price wahan pohanche to tez jhatka aa sakta hai.")
        if dv["oi"]:
            o = pd.DataFrame(dv["oi"])
            f = go.Figure(go.Scatter(x=pd.to_datetime(o.timestamp, unit="ms"), y=o.sumOpenInterestValue.astype(float), fill="tozeroy"))
            f.update_layout(title="Open interest (OKX, USD)", height=260, margin=dict(t=40, b=10)); st.plotly_chart(f, use_container_width=True)
        st.subheader("Bitcoin network / whale alerts (mempool)")
        mp, fees = fetch_mempool()
        m1, m2, m3 = st.columns(3)
        m1.metric("Reachable nodes (Bitnodes)", fetch_bitnodes() or "n/a")
        m2.metric("Fee fast / hour (sat/vB)", f"{fees.get('fastestFee','?')} / {fees.get('hourFee','?')}")
        min_btc = m3.number_input("Whale min BTC", 1, 5000, 10)
        wh = [dict(txid=t["txid"][:14] + "...", BTC=round(t["value"] / 1e8, 2), fee_sat=t["fee"]) for t in mp if t["value"] >= min_btc * 1e8]
        st.dataframe(pd.DataFrame(wh) if wh else pd.DataFrame({"info": [f"no ≥{min_btc} BTC txs in latest mempool sample"]}), hide_index=True)

    with tabs[0]:
        tr = fetch_trades(coin); vo = vpin(tr); vv = statistics.mean(vo) if vo else None
        V = update_verdict(coin, r["parts"]["book"], now, persist * 60)
        up, dn, lsq, ssq = scenario(books, r["mid"], dv, r["pulse"])
        us = up["strength"] / (1 + abs(up["dist"])) if up else 0
        ds = dn["strength"] / (1 + abs(dn["dist"])) if dn else 0
        ps = us / (us + ds) if us + ds else 0.5
        lab = "STRONG-BULL" if ps >= .7 else "WEAK-BULL" if ps >= .55 else "STRONG-BEAR" if ps <= .3 else "WEAK-BEAR" if ps <= .45 else "NEUTRAL"
        H = st.session_state.setdefault("vpin", {}).setdefault(coin, [])
        if vv is not None: H.append((now, vv)); del H[:-600]
        p90 = sorted(v for _, v in H)[int(.9 * (len(H) - 1))] if len(H) > 20 else 0.2
        vlab, vcls = ("LOW", "g") if vv is not None and vv < p90 * 0.6 else ("HIGH", "r") if vv is not None and vv >= p90 else ("MEDIUM", "y")
        hist = fetch_hist(coin)
        a, b, c = st.columns([1.1, 1, 1])
        with a:
            vc = "g" if "Buyers" in V["cur"] else "r" if "Sellers" in V["cur"] else ""
            card("Current verdict", V["cur"], f"held {(now - V['held'])/60:.1f} min | OBI raw {V['ema']:+.3f}", vc)
            if V["pending"]:
                st.caption(f"{V['pending']} PENDING: verdict flips when candidate holds {persist}m"); st.progress(V["prog"])
            card("Next sweep", f"{ps*100:.0f}%", lab, "g" if ps > .5 else "r")
            ur("Next sweep = price pehle upar ke wall ko chhoo kar stop-hunt karega ya neeche ke ko. 55% se upar = upar ka imkaan.")
            fpc = footprint((coin,)); fpc = fpc[0] if fpc else None
            if fpc: update_absorption(coin, fpc, now)
            ab = st.session_state.get("absorb", {}).get(coin)
            card("Whale footprint (absorption)", fpc["footprint"] if fpc else "n/a",
                 (f"since {time.strftime('%H:%M:%S', time.localtime(ab['start']))} | running {(now - ab['start'])/60:.1f} min | price {ab['lo']:g} - {ab['hi']:g}" if ab else "no active absorption"),
                 "g" if fpc and "Bullish" in fpc["footprint"] else "r" if fpc and "Bearish" in fpc["footprint"] else "")
            ur("Absorption = bade players aggressive trades ko chup chaap jazb kar rahe hain. Bullish = sellers ko kharid rahe hain, Bearish = buyers ko bech rahe hain.")
        with b:
            card("Toxic flow (VPIN)", f"{vv:.3f}" if vv is not None else "n/a", vlab + f" | p90 {p90:.3f}", vcls)
            card("Book imbalance", f"{sum(q for p, q in books['MEXC'][0] if p >= r['mid']*(1-pct)) - sum(q for p, q in books['MEXC'][1] if p <= r['mid']*(1+pct)):+,.2f} {coin}", f"NOW / {lag}MS LAG | spread {(books['MEXC'][1][0][0] - books['MEXC'][0][0][0]) / r['mid'] * 1e4:.1f} bps", "c")
            ur("Book imbalance = bids minus asks (coin mein). Plus = khareedar zyada. Spread = bid aur ask ka farq; kam = tight market.")
        with c:
            card("Long squeeze risk", f"{lsq}%", "longs get flushed", "r")
            card("Short squeeze risk", f"{ssq}%", "shorts get flushed", "g")
            ur("Squeeze risk = funding, long/short ratio aur liquidations se andaza ke kaun si side phans kar zabardasti band hogi.")
        if hist:
            f = go.Figure(go.Scatter(y=hist, mode="lines", fill="tozeroy", line_color="#3df0a9" if hist[-1] >= hist[0] else "#ff6b7a"))
            f.update_layout(title=f"{coin} 24h (5m)  {(hist[-1]/hist[0]-1)*100:+.2f}%", height=200, margin=dict(t=40, b=10), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(f, use_container_width=True)
        s1, s2 = st.columns(2)
        with s1:
            st.markdown("**Liquidity scenario map**")
            ur("Upar ka bara wall = target/stop-hunt zone, neeche ka = liquidity magnet. Strength 100 mein se, dist = price se kitna door.")
            for nm, z, cl in (("Target / stop-hunt zone (above)", up, "y"), ("Liquidity magnet (below)", dn, "c")):
                card(nm, f"${z['price']:,.4f}" if z else "n/a", f"{z['dist']:+.2f}% from price | {z['strength']}/100 strength | {usd(z['usd'])}" if z else "", cl)
        with s2:
            st.markdown("**Basis spread across venues**")
            mv = {k: (bb[0][0] + aa[0][0]) / 2 for k, (bb, aa) in books.items()}
            hl = fetch_hl(coin)
            if hl: mv["Hyperliquid (perp)"] = hl
            ref = statistics.mean(mv.values())
            st.dataframe(pd.DataFrame([dict(venue=k, price=v, vs_mean_usd=round(v - ref, 4), bps=round((v - ref) / ref * 1e4, 2)) for k, v in mv.items()]), hide_index=True)
            hi, lo = max(mv.values()), min(mv.values())
            st.caption(f"Spread {hi - lo:,.4f} ({(hi-lo)/ref*1e4:.1f} bps, {'tight' if (hi-lo)/ref*1e4 < 5 else 'wide'}) | best bid / ask arb gap: {max(v[0][0][0] for v in books.values()) - min(v[1][0][0] for v in books.values()):+,.4f}")
        for x in st.session_state["spoof"]:
            if x[1] == coin and now - x[0] < 120 and len(x) >= 6:
                sc = int(min(100, 45 + 40 * (1 - min(x[4], 90) / 90) + 15 * min(1, x[3] / (5 * min_usd))))
                add_alert("spoof", (round(x[0]), x[5]), "HIGH" if sc >= 75 else "MEDIUM", f"Possible Spoofing, score {sc}/100: {usd(x[3])} {coin} {x['bid ask'.split()[0] == x[2] and 0 or 0] if False else x[2]} wall at {x[5]:,.4f}, cancelled after {x[4]:.0f}s, 0% filled", now)
        for z, nm in ((up, "ask"), (dn, "bid")):
            if z and z["strength"] >= 80: add_alert("target", (nm, round(z["price"], 2)), "MEDIUM", f"Liquidity Target Forming: {nm} cluster near ${z['price']:,.4f}. Score {z['strength']}/100", now)
        st.subheader("LIVE ALERTS")
        ur("Alerts: spoofing (fake wall) aur liquidity target ka live ilaan, score jitna zyada utna pakka.")
        A = [a for a in reversed(st.session_state.get("alerts", [])) if coin in a["text"] or a["kind"] == "target"][:8]
        for al in A or [dict(t=now, sev="INFO", text="No alerts yet. They appear when spoofing or liquidity targets are detected.")]:
            st.markdown(f'<div class="al"><span>{al["text"]}<span class="bd">{al["sev"]}</span></span><span class="k">{int(now - al["t"])}s ago</span></div>', unsafe_allow_html=True)

    with tabs[3]:
        L = [x for x in liq_store() if x["sym"] == f"{coin}USDT"]
        _st = liq_status()
        st.caption(f"Feed status: last OKX poll {int(now - _st['ok']) if _st['ok'] else 'never'}s ago | events captured {_st['n']} | error: {_st['err'] or 'none'} | unsupported on OKX: {', '.join(sorted(_st['bad'])) or 'none'}")
        st.caption("Source: OKX public liquidation feed (one venue, recent sample). Not the full market total; a Coinglass-style total needs their paid API.")
        if L:
            df = pd.DataFrame(L).sort_values("t"); df["m"] = (df.t // 60 * 60)
            lo_ = df[df.side == "SELL"].groupby("m").usd.sum(); sh_ = df[df.side == "BUY"].groupby("m").usd.sum()
            idx = sorted(set(lo_.index) | set(sh_.index)); lo_, sh_ = lo_.reindex(idx, fill_value=0), sh_.reindex(idx, fill_value=0)
            net = sh_ - lo_
            x1, x2, x3 = st.columns(3)
            x1.metric("Peak $/min", usd(net.abs().max())); x2.metric("Mean (last 10 min)", usd(net.abs().tail(10).mean())); x3.metric("Baseline (median)", usd(net.abs().median()))
            f = go.Figure(go.Bar(x=pd.to_datetime(idx, unit="s"), y=net.values, marker_color=["#3df0a9" if v > 0 else "#ff6b7a" for v in net.values]))
            f.update_layout(title="Liquidation $ per minute (up = shorts liquidated, down = longs)", height=280, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(f, use_container_width=True)
            ur("Upar bar = shorts liquidate (price upar ja raha tha), neeche bar = longs liquidate (price gir raha tha). Bara bar = cascade ka ishara.")
            cu = go.Figure()
            cu.add_scatter(x=pd.to_datetime(df.t, unit="s"), y=df.usd.where(df.side == "SELL", 0).cumsum(), name="long liq", line_color="#ff6b7a")
            cu.add_scatter(x=pd.to_datetime(df.t, unit="s"), y=df.usd.where(df.side == "BUY", 0).cumsum(), name="short liq", line_color="#3df0a9")
            cu.update_layout(title="Cumulative $", height=260, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(cu, use_container_width=True)
        else:
            st.info("Collecting liquidations for this coin (top 8 coins supported)...")
        st.subheader("Cross-asset pulse")
        ur("Dusre coins mein kitni liquidation hui. Jis coin mein zyada, wahan volatility zyada.")
        cols = st.columns(4)
        for i, cc in enumerate(COINS[:8]):
            E = [x for x in liq_store() if x["sym"] == f"{cc}USDT"]
            cols[i % 4].metric(cc, usd(sum(x["usd"] for x in E)), f"L {usd(sum(x['usd'] for x in E if x['side']=='SELL'))} / S {usd(sum(x['usd'] for x in E if x['side']=='BUY'))}", delta_color="off")

    with tabs[4]:
        st.subheader("Whale footprint (absorption) + volume anomaly")
        ur("Har coin mein whale kya kar raha hai: absorption, buy %, aur volume anomaly (sigma = aam se kitna zyada volume).")
        fp = footprint(tuple(COINS[:12]))
        st.dataframe(pd.DataFrame(fp), hide_index=True, use_container_width=True) if fp else st.info("loading...")
        st.caption("Bearish absorption = aggressive buying but price not rising (sellers absorbing). Bullish = the opposite. vol_sigma = last 1m volume vs previous hour.")
        fh = funding_heat()
        if fh:
            st.subheader("Funding heat (percentile among all MEXC perps)")
            fg2 = go.Figure(go.Bar(x=[fh[c][0] for c in fh], y=list(fh), orientation="h", marker_color=["#f6a623" if fh[c][0] > 66 else "#8a919c" for c in fh]))
            fg2.update_layout(height=320, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fg2, use_container_width=True)
        st.subheader("Mempool heat")
        mst = get("https://mempool.space/api/mempool") or {}
        heat = int(min(100, (fees.get("fastestFee", 1) if (fees := fetch_mempool()[1]) else 1) * 4 + mst.get("count", 0) / 2000))
        g3 = go.Figure(go.Indicator(mode="gauge+number", value=heat, title={"text": "COLD" if heat < 30 else "WARM" if heat < 60 else "HOT"}, gauge={"axis": {"range": [0, 100]}}))
        g3.update_layout(height=220, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(g3, use_container_width=True)
        if addrs:
            rows = []
            for ad in addrs[:6]:
                d = get(f"https://mempool.space/api/address/{ad}") or {}
                cs = d.get("chain_stats", {}); rows.append(dict(address=ad[:10] + "..." + ad[-6:], BTC=round((cs.get("funded_txo_sum", 0) - cs.get("spent_txo_sum", 0)) / 1e8, 4), tx=cs.get("tx_count")))
            st.subheader("Address watch"); st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.subheader("Recent trades tape (big = 3x median)")
        ur("Haal ki trades. BIG = aam trade se 3 guna bari, yani whale ka nishan.")
        tr2 = fetch_trades(coin)[-15:][::-1]; md = statistics.median(p * q for p, q, _, _ in fetch_trades(coin)) or 1
        st.dataframe(pd.DataFrame([dict(price=p, usd=round(p * q), side="SELL" if m else "BUY", big="BIG" if p * q >= 3 * md else "") for p, q, m, _ in tr2]), hide_index=True)

    with tabs[5]:
        rows_ = ticker_all()
        if not rows_:
            st.error("MEXC ticker unreachable.")
        else:
            scan = run_scan(rows_, deep_n, now, coin)
            A_, H_ = st.session_state.get("absorb", {}), st.session_state.get("absorb_hist", [])
            def est(c_, k_):
                d_ = [h["last"] - h["start"] for h in H_ if h["kind"] == k_ and h["coin"] == c_] or [h["last"] - h["start"] for h in H_ if h["kind"] == k_]
                return f"~{statistics.median(d_)/60:.0f} min (past median)" if d_ else "learning..."
            st.subheader("WHALE ABSORPTION: kis coin mein, kab se, kitni der")
            if A_:
                st.dataframe(pd.DataFrame([dict(coin=c_, type=("🟢 Bullish" if "Bullish" in a_["kind"] else "🔴 Bearish") + " absorption", started=time.strftime("%H:%M:%S", time.localtime(a_["start"])),
                                                running_min=round((now - a_["start"]) / 60, 1), from_price=a_["p0"], price_range=f"{a_['lo']:.6g} - {a_['hi']:.6g}", likely_total=est(c_, a_["kind"])) for c_, a_ in A_.items()]),
                             hide_index=True, use_container_width=True)
            else:
                st.info("Abhi koi active absorption nahi. Scan chalne ke baad aayegi.")
            ur("Started = absorption kab shuru hui, running = ab tak kitne minute. Kab tak chalegi uska andaza sirf is session ki purani episodes ke median se hai, pakka nahi.")
            if H_:
                st.caption("Finished absorptions (this session)")
                st.dataframe(pd.DataFrame([dict(coin=h["coin"], type=h["kind"], started=time.strftime("%H:%M:%S", time.localtime(h["start"])), minutes=round((h["last"] - h["start"]) / 60, 1), price_range=f"{h['lo']:.6g} - {h['hi']:.6g}") for h in reversed(H_[-20:])]), hide_index=True, use_container_width=True)
            st.subheader("TOP 100 SCREENER (price, spread, pressure, whales, spoofing)")
            sdf = pd.DataFrame(scan)
            cols_ = [c_ for c_ in ("rank", "coin", "price", "chg", "vol", "spread_bps", "bias", "bid_pct", "buy_pct", "footprint", "conf_walls", "conf_usd", "unconf", "spoof_10m", "vol_sigma") if c_ in sdf]
            st.dataframe(sdf[cols_], hide_index=True, use_container_width=True, height=520, column_config={
                "price": st.column_config.NumberColumn(format="%.6g"), "chg": st.column_config.NumberColumn("24h %", format="%+.2f"),
                "vol": st.column_config.NumberColumn("24h volume $", format="$%d"), "spread_bps": st.column_config.NumberColumn("spread bps", format="%.1f"),
                "bid_pct": st.column_config.ProgressColumn("bids % of book", min_value=0, max_value=100, format="%d%%"),
                "buy_pct": st.column_config.ProgressColumn("taker buy %", min_value=0, max_value=100, format="%d%%"),
                "conf_walls": st.column_config.NumberColumn("confirmed walls"), "conf_usd": st.column_config.NumberColumn("confirmed $", format="$%d"),
                "unconf": st.column_config.NumberColumn("unconfirmed")})
            ur(f"Top {deep_n} coins ka deep scan (walls, absorption, spoof) har ~15 second mein; baqi coins ka sirf price/spread. Bias: BULL = bids zyada + taker buying, BEAR = ulta. Spread kam = tight. Jo coin dekhna ho sidebar se select karein.")

    with st.expander("Scorecard: every signal this session vs what price did"):
        if P:
            st.dataframe(pd.DataFrame([dict(time=time.strftime("%H:%M:%S", time.localtime(x["t"])), coin=x["coin"], signal=x["dir"], P_up=round(x["p"], 3),
                                            entry=x["entry"], result={None: "pending", True: "HIT", False: "MISS"}[x["out"]]) for x in reversed(P)]), hide_index=True)
        else:
            st.write("No signals yet. WAIT is normal; the bot only fires when confidence and agreement are high.")


live()
