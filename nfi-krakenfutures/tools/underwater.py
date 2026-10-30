"""Wie lange und wie tief sind Trades nach dem Einstieg im Minus? (v13, 7 Fenster)"""
import glob, json, zipfile
import numpy as np, pandas as pd
BT = "/root/ft_workdir/user_data/backtest_results/"; DATA = "/root/ft_workdir/user_data/data/krakenfutures/futures/"
WIN = {"2022-08-24": "w1", "2023-05-01": "w2", "2024-01-01": "w2c", "2024-10-01": "w3", "2025-04-01": "val", "2025-09-26": "h1", "2026-03-15": "h2"}
MODES = {"Top 141-145": range(141, 146), "Rebuy 61-68": range(61, 69), "Grind 120": [120], "Quick 41-53": range(41, 54), "Normal 1-13": range(1, 14)}
def mode(tag):
    for k, r in MODES.items():
        if int(tag) in r: return k
    return "andere"
cache = {}
def candles(p):
    if p not in cache: cache[p] = pd.read_feather(DATA + p.replace("/", "_").replace(":", "_") + "-5m-futures.feather").set_index("date")[["open", "low", "close"]]
    return cache[p]
rows, seen = [], set()
for z in sorted(glob.glob(BT + "backtest-result-2026-10-23_04-[3-5]*.zip")):
    try:
        if list(json.load(open(z.replace(".zip", ".meta.json"))).keys()) != ["NFI_KF_V13"]: continue
        zf = zipfile.ZipFile(z); jn = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
        s = json.load(zf.open(jn))["strategy"]["NFI_KF_V13"]
    except Exception: continue
    w = WIN.get(s["backtest_start"][:10])
    if not w or w in seen: continue
    seen.add(w)
    for t in s["trades"]:
        o = pd.Timestamp(t["open_date"]); c = pd.Timestamp(t["close_date"]); e = t["orders"][0]["safe_price"]; lev = t["leverage"]
        cd = candles(t["pair"]); seg = cd.loc[(cd.index >= o) & (cd.index < max(c, o + pd.Timedelta(minutes=5)))]
        if seg.empty: continue
        h = (seg.index - o).total_seconds().values / 3600
        r_close = (seg["close"].values / e - 1) * lev * 100; r_low = (seg["low"].values / e - 1) * lev * 100
        pos = np.where(r_close >= 0)[0]
        first_pos = h[pos[0]] if len(pos) else (t["trade_duration"] / 60)
        # Kurs nach dem Einstieg: wie viel tiefer ging es noch, bevor es drehte (erste 6 h)
        m6 = h <= 6
        rows.append(dict(w=w, mode=mode((t["enter_tag"] or "0").split()[0]), lev=lev, dur=t["trade_duration"] / 60,
                         final=t["profit_ratio"] * 100, first_pos_h=first_pos,
                         mae6=r_low[m6].min() if m6.any() else r_low.min(), price_drop6=(seg["low"].values[m6].min() / e - 1) * 100 if m6.any() else 0,
                         uw1=r_close[h <= 1][-1] < 0 if (h <= 1).any() else False,
                         first_green=r_close[0] >= 0, minute_dd_first_candle=(seg["low"].values[0] / e - 1) * 100,
                         btc_trend=0))
d = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(f"{len(d)} Trades\n")
print("Anteil im Minus (nach Kerze 1 / nach 1 h), Zeit bis erstmals im Plus, tiefster Stand in den ersten 6 h (Marge / Kurs):")
g = d.groupby("mode").agg(n=("final", "size"), minus_kerze1=("first_green", lambda x: (~x).mean() * 100), minus_1h=("uw1", "mean"),
                         bis_plus_h_med=("first_pos_h", "median"), bis_plus_h_p75=("first_pos_h", lambda x: x.quantile(.75)),
                         mae6_med=("mae6", "median"), kurs_tiefer6_med=("price_drop6", "median"), gewinner=("final", lambda x: (x > 0).mean() * 100))
g["minus_1h"] *= 100
print(g.round(1).to_string())
a = d
print(f"\nalle: im Minus nach 1. Kerze {(~a.first_green).mean()*100:.0f} %, nach 1 h {a.uw1.mean()*100:.0f} %, Zeit bis Plus median {a.first_pos_h.median():.1f} h, 75 % {a.first_pos_h.quantile(.75):.1f} h, 90 % {a.first_pos_h.quantile(.9):.1f} h")
print("Kurs faellt nach Einstieg in den ersten 6 h noch um (median / 75 % / 90 %):", round(-a.price_drop6.median(), 2), round(-a.price_drop6.quantile(.25), 2), round(-a.price_drop6.quantile(.1), 2), "%")
print("\nZeit bis erstmals im Plus vs. Endergebnis:")
a["bucket"] = pd.cut(a.first_pos_h, [-0.1, 0.1, 1, 6, 24, 1e5], labels=["sofort", "<1h", "1-6h", "6-24h", ">24h"])
print(a.groupby("bucket", observed=True).agg(n=("final", "size"), gewinner=("final", lambda x: (x > 0).mean() * 100), ergebnis_med=("final", "median"), dauer_med=("dur", "median")).round(1).to_string())
d.to_csv("/root/ft_workdir/underwater.csv", index=False)
