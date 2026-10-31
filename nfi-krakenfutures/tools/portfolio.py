"""Kapitalaufteilung auf zwei Strategien: Equity-Kurven inkl. offener Positionen (wie mtm.py) je Fenster
normiert und gewichtet addiert (zwei getrennte Konten, keine Umschichtung).
usage: portfolio.py STRAT_A PRAEFIX_A [BEFORE_A] -- STRAT_B PRAEFIX_B [BEFORE_B]"""
import glob, json, os, sys, zipfile
import numpy as np, pandas as pd
BT = "/root/ft_workdir/user_data/backtest_results/"
DATA = "/root/ft_workdir/user_data/data/krakenfutures/futures/"
WIN = {"2022-08-24": "w1", "2023-05-01": "w2", "2024-01-01": "w2c", "2024-09-01": "w4a", "2024-10-01": "w3",
       "2025-04-01": "val", "2025-09-26": "h1", "2026-03-15": "h2"}
ORDER = ["w1", "w2", "w2c", "w4a", "w3", "val", "h1", "h2"]
cache = {}
def low(pair):
    if pair not in cache:
        cache[pair] = pd.read_feather(DATA + pair.replace("/", "_").replace(":", "_") + "-5m-futures.feather").set_index("date")["low"]
    return cache[pair]
def tzu(x):
    x = pd.Timestamp(x); return x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")
def runs(strat, after, before):
    found = {}
    for z in sorted(glob.glob(BT + "backtest-result-*.zip")):
        b = os.path.basename(z)
        if b < after or b >= before: continue
        try:
            if list(json.load(open(z.replace(".zip", ".meta.json"))).keys()) != [strat]: continue
            zf = zipfile.ZipFile(z); jn = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
            s = json.load(zf.open(jn))["strategy"][strat]
            if not s["trades"] or s["trades"][0]["fee_open"] > 0.0006: continue
        except Exception: continue
        w = WIN.get(s["backtest_start"][:10])
        if w: found[w] = s
    return found
def curve(s):
    eq0 = s["starting_balance"]; grid = pd.date_range(tzu(s["backtest_start"]), tzu(s["backtest_end"]), freq="5min")
    pnl = np.zeros(len(grid))
    for t in s["trades"]:
        o = tzu(t["open_date"]); c = tzu(t["close_date"]); i0 = grid.searchsorted(o); i1 = grid.searchsorted(c)
        if i1 > i0:
            px = low(t["pair"]).reindex(grid[i0:i1]).ffill().bfill().values; gts = grid[i0:i1].as_unit("ms").asi8
            pos = np.zeros(i1 - i0); cash = np.zeros(i1 - i0)
            for x in t["orders"]:
                sg = 1 if x["ft_order_side"] == "buy" else -1; m = gts >= x["order_filled_timestamp"]
                pos[m] += sg * x["amount"]; cash[m] -= sg * x["amount"] * x["safe_price"]
            pnl[i0:i1] += cash + pos * px
        pnl[i1:] += t["profit_abs"]
    return pd.Series((eq0 + pnl) / eq0, index=grid)
args = sys.argv[1:]; sep = args.index("--"); A, B = args[:sep], args[sep + 1:]
ra = runs(A[0], A[1], A[2] if len(A) > 2 else "~"); rb = runs(B[0], B[1], B[2] if len(B) > 2 else "~")
ca = {w: curve(s) for w, s in ra.items()}; cb = {w: curve(s) for w, s in rb.items()}
print(f"A = {A[0]}, B = {B[0]}  (Gewinn % / max. Drawdown inkl. offener Positionen %)")
print(f"{'A-Anteil':>9s}" + "".join(f"{w:>15s}" for w in ORDER) + f"{'max DD':>9s}{'Mittel DD':>11s}")
for wa in [1.0, 0.7, 0.5, 0.3, 0.0]:
    cells, dds = [], []
    for w in ORDER:
        if w not in ca or w not in cb: cells.append(f"{'-':>15s}"); continue
        a, b = ca[w], cb[w].reindex(ca[w].index).ffill().bfill()
        eq = wa * a + (1 - wa) * b; pk = eq.cummax(); dd = ((pk - eq) / pk).max() * 100
        dds.append(dd); cells.append(f"{(eq.iloc[-1] - 1) * 100:8.1f} /{dd:5.1f}")
    print(f"{wa * 100:8.0f}%" + "".join(cells) + f"{max(dds):9.1f}{np.mean(dds):11.1f}")
