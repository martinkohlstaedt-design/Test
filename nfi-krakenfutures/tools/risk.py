"""Risikokennzahlen je Strategie aus den Backtest-Ergebnissen (7 Fenster ohne W4a).
usage: risk.py AB_DATEINAME STRAT [STRAT ...]   (AB_DATEINAME z. B. backtest-result-2026-10-23_04-3 fuer ref2)"""
import glob, json, os, sys, zipfile
import numpy as np, pandas as pd
BT = "/root/ft_workdir/user_data/backtest_results/"
W = {"2022-08-24": "w1", "2023-05-01": "w2", "2024-01-01": "w2c", "2024-10-01": "w3",
     "2025-04-01": "val", "2025-09-26": "h1", "2026-03-15": "h2"}
after = sys.argv[1]; strats = sys.argv[2:]
rng = np.random.default_rng(1)
def load(strat):
    seen, out = {}, []
    for z in sorted(glob.glob(BT + "backtest-result-*.zip")):
        if os.path.basename(z) < after or os.path.basename(z) >= os.environ.get("BEFORE", "~"): continue
        try:
            if list(json.load(open(z.replace(".zip", ".meta.json"))).keys()) != [strat]: continue
            zf = zipfile.ZipFile(z); jn = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
            s = json.load(zf.open(jn))["strategy"][strat]
        except Exception: continue
        w = W.get(s["backtest_start"][:10])
        if w and s["trades"] and s["trades"][0]["fee_open"] < 0.0006: seen[w] = s
    for w, s in seen.items():
        df = pd.DataFrame(s["trades"]); df["close_date"] = pd.to_datetime(df["close_date"]); df["open_date"] = pd.to_datetime(df["open_date"])
        c = df.sort_values("close_date"); cum = c["profit_abs"].cumsum().values; cd = c["close_date"].values
        def eq(t):
            i = np.searchsorted(cd, np.datetime64(t.tz_convert(None)), side="left"); return s["starting_balance"] + (cum[i-1] if i > 0 else 0.0)
        df["rel"] = df["profit_abs"] / df["open_date"].apply(eq); df["w"] = w; out.append(df)
    return pd.concat(out), sorted(seen)
print(f"{'strategie':22s}{'Fenster':>8s}{'Trades':>7s}{'<-50%':>6s}{'<-80%':>6s}{'Liq':>4s}{'schlechtester':>14s}{'Summe-Beitrag':>14s}{'MC-DD med':>10s}{'MC-DD 95%':>10s}")
for s in strats:
    d, ws = load(s)
    r = d["rel"].values
    sims = np.array([rng.permutation(r) for _ in range(3000)])
    eq = np.cumprod(1 + sims, axis=1); dd = ((np.maximum.accumulate(eq, axis=1) - eq) / np.maximum.accumulate(eq, axis=1)).max(axis=1) * 100
    print(f"{s[-22:]:22s}{len(ws):8d}{len(d):7d}{(d.profit_ratio<-0.5).sum():6d}{(d.profit_ratio<-0.8).sum():6d}"
          f"{(d.exit_reason=='liquidation').sum():4d}{d.profit_ratio.min()*100:13.0f}%{d.rel.sum()*100:14.0f}{np.median(dd):10.1f}{np.percentile(dd,95):10.1f}")
