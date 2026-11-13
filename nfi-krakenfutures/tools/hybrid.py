"""Vergleicht Kraken-Spot-Kerzen (data_krakenspot) mit Futures-Kerzen (data_spot) im Crash-Fenster
und baut data_hybrid: Futures-Kerzen, im Fenster durch echte Spot-Kerzen ersetzt (nur 5m).
usage: python hybrid.py [START] [END]
"""
import os, sys, glob, shutil
import pandas as pd

S = sys.argv[1] if len(sys.argv) > 1 else "2025-10-09"
E = sys.argv[2] if len(sys.argv) > 2 else "2025-10-12"
W0, W1 = pd.Timestamp("2025-10-10 20:00", tz="UTC"), pd.Timestamp("2025-10-11 02:00", tz="UTC")
SP, FU, OK, HY = "/root/ft_workdir/data_krakenspot", "/root/ft_workdir/data_spot", "/root/ft_workdir/data_okx", "/root/ft_workdir/data_hybrid"
os.makedirs(HY, exist_ok=True)
for f in glob.glob(FU + "/*"):
    t = os.path.join(HY, os.path.basename(f))
    if not os.path.exists(t):
        shutil.copy(os.path.realpath(f), t)
rows = []
for f in sorted(glob.glob(SP + "/*-5m.feather")):
    n = os.path.basename(f)
    sp = pd.read_feather(f)
    fu_p = os.path.join(FU, n)
    if not os.path.exists(fu_p) or sp.empty:
        continue
    fu = pd.read_feather(fu_p)
    a, b = pd.Timestamp(S, tz="UTC"), pd.Timestamp(E, tz="UTC")
    sp = sp[(sp.date >= a) & (sp.date < b)]
    hy = pd.concat([fu[(fu.date < a) | (fu.date >= b)], sp]).sort_values("date").drop_duplicates("date", keep="last")
    # Luecken (keine Spot-Trades) mit Futures-Kerzen auffuellen
    miss = fu[(fu.date >= a) & (fu.date < b) & (~fu.date.isin(sp.date))]
    hy = pd.concat([hy, miss]).sort_values("date").reset_index(drop=True)
    hy.to_feather(os.path.join(HY, n))
    def lowdrop(d):
        d = d[(d.date >= W0) & (d.date < W1)]
        return None if d.empty else round((d.low.min() / d.open.iloc[0] - 1) * 100, 1)
    okp = os.path.join(OK, n.replace("_USD-", "_USDT-"))
    ok = lowdrop(pd.read_feather(okp)) if os.path.exists(okp) else None
    rows.append((n.split("-")[0], lowdrop(sp), lowdrop(fu), ok, len(miss)))
print(f"{'Coin':12s} {'Spot%':>7s} {'Fut%':>7s} {'OKX%':>7s} fehlend")
for r in sorted(rows, key=lambda r: (r[1] if r[1] is not None else 0)):
    print(f"{r[0]:12s} {str(r[1]):>7s} {str(r[2]):>7s} {str(r[3]):>7s} {r[4]}")
