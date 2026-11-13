"""Welche Positionen machen den MtM-Drawdown an den Tiefpunkten aus?"""
import glob, json, os, zipfile
import numpy as np, pandas as pd
BT = "/root/ft_workdir/user_data/backtest_results/"
DATA = "/root/ft_workdir/user_data/data/krakenfutures/futures/"
TROUGHS = {"w2c": "2024-04-13 20:05", "w4a": "2024-12-20 11:50", "w3": "2025-02-03 02:05", "h1": "2025-10-10 21:25"}
WIN = {"2024-01-01": "w2c", "2024-09-01": "w4a", "2024-10-01": "w3", "2025-09-26": "h1"}
btc = pd.read_feather(DATA + "BTC_USD_USD-5m-futures.feather").set_index("date")["close"]
found = {}
for z in sorted(glob.glob(BT + "backtest-result-2026-10-23_04-[3-5]*.zip")):
    try:
        if list(json.load(open(z.replace(".zip", ".meta.json"))).keys()) != ["NFI_KF_V13"]: continue
        zf = zipfile.ZipFile(z); jn = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
        s = json.load(zf.open(jn))["strategy"]["NFI_KF_V13"]
    except Exception: continue
    w = WIN.get(s["backtest_start"][:10])
    if w and w not in found: found[w] = s
pd.set_option("display.width", 220)
for w, tt in TROUGHS.items():
    s = found[w]; T = pd.Timestamp(tt, tz="UTC"); ms = int(T.timestamp() * 1000)
    closed = sum(t["profit_abs"] for t in s["trades"] if pd.Timestamp(t["close_date"]) <= T)
    eq_real = s["starting_balance"] + closed
    rows = []
    for t in s["trades"]:
        o = pd.Timestamp(t["open_date"]); c = pd.Timestamp(t["close_date"])
        if not (o <= T < c): continue
        p = pd.read_feather(DATA + t["pair"].replace("/", "_").replace(":", "_") + "-5m-futures.feather").set_index("date")["low"]
        price = float(p.loc[:T].iloc[-1])
        pos = cash = buys = 0.0
        for x in t["orders"]:
            if x["order_filled_timestamp"] <= ms:
                sg = 1 if x["ft_order_side"] == "buy" else -1
                pos += sg * x["amount"]; cash -= sg * x["amount"] * x["safe_price"]
                if sg > 0: buys += x["amount"] * x["safe_price"]
        unreal = cash + pos * price
        b0 = float(btc.loc[:o].iloc[-1]); b12 = float(btc.loc[:o - pd.Timedelta(hours=1)].iloc[-1])
        rows.append(dict(coin=t["pair"].split("/")[0], tag=(t["enter_tag"] or "").split()[0], lev=t["leverage"],
                         open=o.strftime("%m-%d %H:%M"), h_vor=round((T - o).total_seconds() / 3600, 1),
                         btc_1h_vor_kauf=round((b0 / b12 - 1) * 100, 1), marge_pct_konto=round(buys / t["leverage"] / eq_real * 100, 1),
                         unreal_pct_konto=round(unreal / eq_real * 100, 1), ende=round(t["profit_ratio"] * 100, 1)))
    d = pd.DataFrame(rows).sort_values("unreal_pct_konto")
    bt = float(btc.loc[:T].iloc[-1]); bmax = float(btc.loc[T - pd.Timedelta(hours=24):T].max())
    print(f"\n=== {w} Tiefpunkt {tt}  BTC {bt:.0f} ({(bt/bmax-1)*100:.1f} % unter 24h-Hoch)  offene Positionen {len(d)}  unrealisiert {d.unreal_pct_konto.sum():.1f} % Konto")
    print(d.to_string(index=False))
