"""Drawdown inkl. offener Positionen (Mark-to-Market, 5m-Tiefstkurse) je Fenster.
usage: mtm.py STRAT [ZIP-PRAEFIX]     Fenster: alle 8 (neuester Lauf je Fenster, Gebuehr <= 0,06 %)
Naeherung: Kursgewinn der gehaltenen Menge zum 5m-Tief, ohne Gebuehren/Funding bis zum Schliessen."""
import glob, json, os, sys, zipfile
import numpy as np, pandas as pd

BT = "/root/ft_workdir/user_data/backtest_results/"
DATA = "/root/ft_workdir/user_data/data/krakenfutures/futures/"
strat = sys.argv[1]
after = sys.argv[2] if len(sys.argv) > 2 else "backtest-result-2026-10-23_04-3"
WIN = {"2022-08-24": "w1", "2023-05-01": "w2", "2024-01-01": "w2c", "2024-09-01": "w4a", "2024-10-01": "w3",
       "2025-04-01": "val", "2025-09-26": "h1", "2026-03-15": "h2"}
found = {}
for z in sorted(glob.glob(BT + "backtest-result-*.zip")):
    if os.path.basename(z) < after:
        continue
    try:
        if list(json.load(open(z.replace(".zip", ".meta.json"))).keys()) != [strat]:
            continue
        zf = zipfile.ZipFile(z)
        jn = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
        s = json.load(zf.open(jn))["strategy"][strat]
        if not s["trades"] or s["trades"][0]["fee_open"] > 0.0006:
            continue
    except Exception:
        continue
    w = WIN.get(s["backtest_start"][:10])
    if w:
        found[w] = s
cache = {}
def candles(pair):
    if pair not in cache:
        cache[pair] = pd.read_feather(DATA + pair.replace("/", "_").replace(":", "_") + "-5m-futures.feather").set_index("date")["low"]
    return cache[pair]
res = {}
for w in ["w1", "w2", "w2c", "w4a", "w3", "val", "h1", "h2"]:
    if w not in found:
        continue
    s = found[w]
    eq0 = s["starting_balance"]
    def tzu(x):
        x = pd.Timestamp(x)
        return x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")
    t0 = tzu(s["backtest_start"]); t1 = tzu(s["backtest_end"])
    grid = pd.date_range(t0, t1, freq="5min")
    pnl = np.zeros(len(grid))
    for t in s["trades"]:
        lo = candles(t["pair"])
        o = tzu(t["open_date"]); c = tzu(t["close_date"])
        i0 = grid.searchsorted(o); i1 = grid.searchsorted(c)
        if i1 <= i0:
            pnl[i1:] += t["profit_abs"]; continue
        px = lo.reindex(grid[i0:i1]).ffill().bfill().values
        ts = np.array([x["order_filled_timestamp"] for x in t["orders"]], dtype="int64")
        pos = np.zeros(i1 - i0); cash = np.zeros(i1 - i0)
        gts = grid[i0:i1].as_unit("ms").asi8
        for x, tsx in zip(t["orders"], ts):
            sgn = 1 if x["ft_order_side"] == "buy" else -1
            m = gts >= tsx
            pos[m] += sgn * x["amount"]; cash[m] -= sgn * x["amount"] * x["safe_price"]
        pnl[i0:i1] += cash + pos * px
        pnl[i1:] += t["profit_abs"]
    eq = eq0 + pnl
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak * 100
    res[w] = (dd.max(), (eq[-1] / eq0 - 1) * 100)
    print(f"{w:4s} MtM-DD {dd.max():5.1f} %   Gewinn {res[w][1]:8.1f} %   (tiefster Punkt {grid[dd.argmax()]:%Y-%m-%d %H:%M})", flush=True)
if res:
    print(f"{strat}: max MtM-DD {max(v[0] for v in res.values()):.1f} %, Mittel {np.mean([v[0] for v in res.values()]):.1f} %")
