"""Auswertung je NFI-Signal aus den Backtest-Ergebnissen.
usage: signals.py STRATEGIE [ZIP-PRAEFIX]   (Standard: nur Laeufe ab 23.10. 04:30, Fenster ohne W4a)
Beitrag = Gewinn des Trades relativ zum Kontostand bei Eroeffnung (summiert ~ Konto-Rendite der Fenster)."""
import collections
import glob
import json
import os
import sys
import zipfile

import pandas as pd

BT = "/root/ft_workdir/user_data/backtest_results/"
strat = sys.argv[1] if len(sys.argv) > 1 else "NFI_KF_V13"
after = sys.argv[2] if len(sys.argv) > 2 else "backtest-result-2026-10-23_04-3"
WINDOWS = {"2022-08-24": "w1", "2023-05-01": "w2", "2024-01-01": "w2c", "2024-10-01": "w3",
           "2025-04-01": "val", "2025-09-26": "h1", "2026-03-15": "h2"}   # W4a ueberlappt W3 -> weglassen

MODES = {
    "Normal (1-13)": range(1, 14), "Pump (21-26)": range(21, 27), "Quick (41-53)": range(41, 54),
    "Rebuy (61-68)": range(61, 69), "High-Profit (81-82)": range(81, 83), "Rapid (101-110)": range(101, 111),
    "Grind (120)": [120], "BTC (121)": [121], "Top-Coins (141-145)": range(141, 146), "Scalp (161-173)": range(161, 174),
}


def mode_of(tag):
    n = int(tag)
    for name, r in MODES.items():
        if n in r:
            return name
    return "andere"


trades = []
seen = set()
for z in sorted(glob.glob(BT + "backtest-result-*.zip")):
    if os.path.basename(z) < after:
        continue
    try:
        keys = list(json.load(open(z.replace(".zip", ".meta.json"))).keys())
        if keys != [strat]:
            continue
        zf = zipfile.ZipFile(z)
        jn = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
        s = json.load(zf.open(jn))["strategy"][strat]
    except Exception:
        continue
    w = WINDOWS.get(s["backtest_start"][:10])
    if not w or w in seen or s["trades"][0]["fee_open"] > 0.0006:
        continue
    seen.add(w)
    df = pd.DataFrame(s["trades"])
    df["close_date"] = pd.to_datetime(df["close_date"])
    df["open_date"] = pd.to_datetime(df["open_date"])
    eq0 = s["starting_balance"]
    closed = df.sort_values("close_date")
    cum = closed["profit_abs"].cumsum().values
    cd = closed["close_date"].values
    import numpy as np
    def equity_at(t):
        i = np.searchsorted(cd, np.datetime64(t.tz_convert(None) if t.tzinfo else t), side="left")
        return eq0 + (cum[i - 1] if i > 0 else 0.0)
    df["equity_open"] = df["open_date"].apply(equity_at)
    df["beitrag"] = df["profit_abs"] / df["equity_open"] * 100
    df["window"] = w
    trades.append(df)

if not trades:
    sys.exit("keine passenden Ergebnisse gefunden")
d = pd.concat(trades, ignore_index=True)
d["tags"] = d["enter_tag"].fillna("").str.split()
d["primary"] = d["tags"].apply(lambda t: t[0] if t else "?")
d["multi"] = d["tags"].apply(len) > 1
d["mode"] = d["primary"].apply(mode_of)
d["dauer_h"] = d["trade_duration"] / 60
d["orders"] = d["orders"].apply(len)
print(f"{strat}: {len(d)} Trades in Fenstern {sorted(seen)} (ohne W4a), "
      f"Mehrfach-Signale: {d.multi.sum()} ({d.multi.mean()*100:.0f} %)\n")


def table(g, label):
    r = g.agg(
        n=("profit_abs", "size"),
        gewinn_pct=("profit_ratio", lambda x: (x > 0).mean() * 100),
        mittel_pct=("profit_ratio", lambda x: x.mean() * 100),
        median_pct=("profit_ratio", lambda x: x.median() * 100),
        schlechtester=("profit_ratio", lambda x: x.min() * 100),
        beitrag=("beitrag", "sum"),
        dauer=("dauer_h", "median"),
        orders=("orders", "mean"),
        verlierer=("profit_abs", lambda x: (x < 0).sum()),
    )
    r["anteil_n"] = r["n"] / len(d) * 100
    r["anteil_beitrag"] = r["beitrag"] / d["beitrag"].sum() * 100
    r = r.sort_values("beitrag", ascending=False)
    print(f"--- {label} ---")
    print(f"{'':20s}{'n':>5s}{'%n':>6s}{'Gew%':>6s}{'mittel%':>9s}{'med%':>7s}{'schlecht%':>10s}"
          f"{'Verl':>5s}{'Beitrag':>9s}{'%Beitr':>8s}{'Dauer h':>9s}{'Orders':>7s}")
    for k, x in r.iterrows():
        print(f"{str(k):20s}{int(x.n):5d}{x.anteil_n:6.1f}{x.gewinn_pct:6.0f}{x.mittel_pct:9.1f}{x.median_pct:7.1f}"
              f"{x.schlechtester:10.0f}{int(x.verlierer):5d}{x.beitrag:9.1f}{x.anteil_beitrag:8.1f}{x.dauer:9.1f}{x.orders:7.1f}")
    print()


table(d.groupby("mode"), "Signalgruppen (nach erstem Signal)")
table(d.groupby("primary"), "Einzelne Signale (erstes Signal)")
print("Mehrfach-Signale:")
table(d.groupby("multi"), "Einzel- vs. Mehrfach-Signal")
d.to_csv("/root/ft_workdir/signals_trades.csv", index=False)
