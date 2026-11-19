import glob, json, os, zipfile
import numpy as np, pandas as pd
BT = "/root/ft_workdir/user_data/backtest_results/"
DATA = "/root/ft_workdir/user_data/data/krakenfutures/futures/"
WIN = {"2022-08-24": "w1", "2023-05-01": "w2", "2024-01-01": "w2c", "2024-10-01": "w3", "2025-04-01": "val", "2025-09-26": "h1", "2026-03-15": "h2"}
CUTS = [12, 24, 48, 72, 120]
cache = {}
def px(pair):
    if pair not in cache:
        cache[pair] = pd.read_feather(DATA + pair.replace("/", "_").replace(":", "_") + "-5m-futures.feather").set_index("date")["close"]
    return cache[pair]
FEE = 0.0005
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
    df = pd.DataFrame(s["trades"]); df["cd"] = pd.to_datetime(df.close_date)
    c = df.sort_values("cd"); cum = c.profit_abs.cumsum().values; cds = c.cd.values
    for t in s["trades"]:
        dur_h = t["trade_duration"] / 60
        if dur_h <= 12: continue
        o = pd.Timestamp(t["open_date"])
        i = np.searchsorted(cds, np.datetime64(o.tz_convert(None)), side="left")
        eq = s["starting_balance"] + (cum[i - 1] if i > 0 else 0)
        ords = t["orders"]
        cash_f = sum((-1 if x["ft_order_side"] == "buy" else 1) * x["amount"] * x["safe_price"] for x in ords)
        fees_f = sum(FEE * x["amount"] * x["safe_price"] for x in ords)
        approx_final = cash_f - fees_f
        p = px(t["pair"])
        r = dict(w=w, coin=t["pair"].split("/")[0], tag=(t["enter_tag"] or "").split()[0], dur=dur_h, equity=eq, actual=t["profit_abs"], approx_final=approx_final, ratio=t["profit_ratio"] * 100)
        for h in CUTS:
            if dur_h <= h:
                r[f"d{h}"] = 0.0; r[f"u{h}"] = False; continue
            tc = o + pd.Timedelta(hours=h); ms = int(tc.timestamp() * 1000)
            pos = 0; cash = 0; fees = 0
            for x in ords:
                if x["order_filled_timestamp"] <= ms:
                    sg = 1 if x["ft_order_side"] == "buy" else -1
                    pos += sg * x["amount"]; cash -= sg * x["amount"] * x["safe_price"]; fees += FEE * x["amount"] * x["safe_price"]
            price = float(p.loc[:tc].iloc[-1])
            val = cash + pos * price - fees - FEE * pos * price
            r[f"d{h}"] = val - approx_final
            r[f"u{h}"] = (cash + pos * price) < 0
        rows.append(r)
d = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print("Trades laenger als 12 h:", len(d), "| laenger als 24 h:", (d.dur > 24).sum())
print("\nWirkung eines Zeitstopps (Summe USD und in % vom Kontostand bei Eroeffnung; + = besser als heute)")
print(f"{'Frist':>6s}{'alle Trades: USD':>18s}{'% Konto':>9s}{'nur im Minus: USD':>19s}{'% Konto':>9s}{'  betroffen':>11s}")
for h in CUTS:
    a = d[f"d{h}"]; m = d[f"u{h}"]
    print(f"{h:5d}h{a.sum():18.0f}{(a / d.equity).sum()*100:9.1f}{a[m].sum():19.0f}{(a[m] / d.equity[m]).sum()*100:9.1f}{(d.dur > h).sum():11d}")
print("\nNach Fenster (alle Trades, Frist 24 h, % Konto):")
d["p24"] = d.d24 / d.equity * 100
print(d.groupby("w").agg(n=("dur", "size"), betroffen=("dur", lambda x: (x > 24).sum()), delta_pct=("p24", "sum")).round(2))
print("\nEinzeltrades > 24 h (Ergebnis heute vs. Stopp nach 24 h, in % Konto):")
e = d[d.dur > 24].copy(); e["heute"] = e.actual / e.equity * 100; e["nach24"] = (e.approx_final + e.d24) / e.equity * 100
print(e.sort_values("dur", ascending=False)[["coin", "w", "tag", "dur", "ratio", "heute", "nach24"]].head(25).round(2).to_string(index=False))
print("\nGewinner > 24 h:", (e.ratio > 0).sum(), " Summe heute % Konto", round(e.heute[e.ratio > 0].sum(), 1), " nach 24 h", round(e.nach24[e.ratio > 0].sum(), 1))
print("Verlierer > 24 h:", (e.ratio <= 0).sum(), " Summe heute % Konto", round(e.heute[e.ratio <= 0].sum(), 1), " nach 24 h", round(e.nach24[e.ratio <= 0].sum(), 1))
