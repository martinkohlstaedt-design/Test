"""BTC-Absicherung als Nachrechnung auf vorhandenen Backtests (keine neuen Laeufe).
Zu jedem Zeitpunkt: Long-Positionswert L(t) aller offenen Trades. Absicherung = BTC-Short mit h x L(t),
angepasst bei jeder Order des Bots und alle 4 h; optional nur, wenn L/Konto > MINEXP. Gebuehr 0,05 % je Anpassung.
Bewertung auf 5m-Schlusskursen. Naeherung: Positionsgroessen des Bots bleiben wie im Backtest (keine Rueckwirkung).
usage: hedgesim.py STRAT PRAEFIX [BEFORE]"""
import glob, json, os, sys, zipfile
import numpy as np, pandas as pd
BT = "/root/ft_workdir/user_data/backtest_results/"
DATA = "/root/ft_workdir/user_data/data/krakenfutures/futures/"
WIN = {"2022-08-24": "w1", "2023-05-01": "w2", "2024-01-01": "w2c", "2024-09-01": "w4a", "2024-10-01": "w3",
       "2025-04-01": "val", "2025-09-26": "h1", "2026-03-15": "h2", "2026-10-06": "neu"}
strat, after = sys.argv[1], sys.argv[2]
before = sys.argv[3] if len(sys.argv) > 3 else "~"
FEE = 0.0005
cache = {}
def close(pair):
    if pair not in cache:
        f = DATA + pair.replace("/", "_").replace(":", "_") + "-5m-futures.feather"
        cache[pair] = pd.read_feather(f, columns=["date", "close"]).set_index("date")["close"]
    return cache[pair]
def tzu(x):
    x = pd.Timestamp(x); return x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")
found = {}
for z in sorted(glob.glob(BT + "backtest-result-*.zip")):
    b = os.path.basename(z)
    if b < after or b >= before: continue
    try:
        if list(json.load(open(z.replace(".zip", ".meta.json"))).keys()) != [strat]: continue
        zf = zipfile.ZipFile(z); jn = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
        s = json.load(zf.open(jn))["strategy"][strat]
    except Exception: continue
    w = WIN.get(s["backtest_start"][:10])
    if w and s["trades"]: found[w] = s
VARS = [(0.0, 0.0), (0.3, 0.0), (0.5, 0.0), (0.75, 0.0), (1.0, 0.0), (0.5, 1.0), (1.0, 1.0), (1.0, 2.0)]
res = {v: {} for v in VARS}
for w in ["w1", "w2", "w2c", "w4a", "w3", "val", "h1", "h2", "neu"]:
    if w not in found: continue
    s = found[w]; eq0 = s["starting_balance"]
    grid = pd.date_range(tzu(s["backtest_start"]), tzu(s["backtest_end"]), freq="5min")
    n = len(grid); pnl = np.zeros(n); L = np.zeros(n); ev = np.zeros(n, dtype=bool)
    gts_all = grid.as_unit("ms").asi8
    for t in s["trades"]:
        o = tzu(t["open_date"]); c = tzu(t["close_date"]); i0 = grid.searchsorted(o); i1 = grid.searchsorted(c)
        if i1 <= i0:
            pnl[i1:] += t["profit_abs"]; continue
        px = close(t["pair"]).reindex(grid[i0:i1]).ffill().bfill().values
        pos = np.zeros(i1 - i0); cash = np.zeros(i1 - i0); g = gts_all[i0:i1]
        for x in t["orders"]:
            if not x.get("order_filled_timestamp"): continue
            sg = 1 if x["ft_order_side"] == "buy" else -1; m = g >= x["order_filled_timestamp"]
            pos[m] += sg * x["amount"]; cash[m] -= sg * x["amount"] * x["safe_price"]
            k = min(max(np.searchsorted(gts_all, x["order_filled_timestamp"]), 0), n - 1); ev[k] = True
        pnl[i0:i1] += cash + pos * px; L[i0:i1] += pos * px
        pnl[i1:] += t["profit_abs"]; ev[min(i1, n - 1)] = True
    eq = eq0 + pnl
    btc = close("BTC/USD:USD").reindex(grid).ffill().bfill().values
    ev[::48] = True
    for (h, minexp) in VARS:
        q = 0.0; hp = np.zeros(n); cum = 0.0
        for i in range(n):
            if i:
                cum -= q * (btc[i] - btc[i - 1])
            if ev[i] and h > 0:
                e_now = eq[i] + cum
                tgt = h * L[i] / btc[i] if (L[i] > minexp * max(e_now, 1.0)) else 0.0
                cum -= abs(tgt - q) * btc[i] * FEE; q = tgt
            hp[i] = cum
        e = eq + hp; pk = np.maximum.accumulate(e); dd = ((pk - e) / pk).max() * 100
        res[(h, minexp)][w] = ((e[-1] / eq0 - 1) * 100, dd)
    print(w, "fertig, max. Positionswert/Konto: %.1f" % (L / np.maximum(eq, 1)).max(), flush=True)
ws = [w for w in ["w1", "w2", "w2c", "w4a", "w3", "val", "h1", "h2", "neu"] if w in found]
print(f"{'h / ab Exposure':16s}" + "".join(f"{w:>13s}" for w in ws) + "   Summe o.H1  maxDD  Mittel")
for v in VARS:
    r = res[v]; tot = sum(r[w][0] for w in ws if w not in ("h1", "neu")); dds = [r[w][1] for w in ws if w != "neu"]
    print(f"h={v[0]:.2f} ab {v[1]:.1f}x  " + "".join(f"{r[w][0]:7.0f}/{r[w][1]:4.1f} " for w in ws) + f" {tot:8.0f} {max(dds):6.1f} {np.mean(dds):6.1f}")
