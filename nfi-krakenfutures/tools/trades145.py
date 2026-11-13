"""Verlauf aller Signal-145-Trades (v13): Rendite auf eingesetzte Marge ueber die Zeit seit Eroeffnung.
usage: SIGNAL=145 trades145.py [STRAT] [ZIP-PRAEFIX]   (Python mit matplotlib, z. B. /root/plotvenv/bin/python)
Ausgabe: /root/ft_workdir/out145_*.png und trades145_paths.csv"""
import glob, json, os, sys, zipfile
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

BT = "/root/ft_workdir/user_data/backtest_results/"
DATA = "/root/ft_workdir/user_data/data/krakenfutures/futures/"
SIG = os.environ.get("SIGNAL", "145")
strat = sys.argv[1] if len(sys.argv) > 1 else "NFI_KF_V13"
after = sys.argv[2] if len(sys.argv) > 2 else "backtest-result-2026-10-23_04-3"
WIN = {"2022-08-24": "w1", "2023-05-01": "w2", "2024-01-01": "w2c", "2024-10-01": "w3",
       "2025-04-01": "val", "2025-09-26": "h1", "2026-03-15": "h2"}
cache = {}
def candles(pair):
    if pair not in cache:
        cache[pair] = pd.read_feather(DATA + pair.replace("/", "_").replace(":", "_") + "-5m-futures.feather").set_index("date")[["close", "low"]]
    return cache[pair]

seen, rows, paths = set(), [], []
for z in sorted(glob.glob(BT + "backtest-result-*.zip")):
    if os.path.basename(z) < after:
        continue
    try:
        if list(json.load(open(z.replace(".zip", ".meta.json"))).keys()) != [strat]:
            continue
        zf = zipfile.ZipFile(z)
        jn = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
        s = json.load(zf.open(jn))["strategy"][strat]
        w = WIN.get(s["backtest_start"][:10])
        if not w or w in seen or s["trades"][0]["fee_open"] > 0.0006:
            continue
    except Exception:
        continue
    seen.add(w)
    for t in s["trades"]:
        tags = (t["enter_tag"] or "").split()
        if not tags or tags[0] != SIG:
            continue
        cd = candles(t["pair"])
        o = pd.Timestamp(t["open_date"]); c = pd.Timestamp(t["close_date"])
        px = cd.loc[(cd.index >= o) & (cd.index <= c)]
        if px.empty:
            continue
        idx = px.index.asi8 // (1000 if px.index.unit == "us" else 1) if False else px.index.as_unit("ms").asi8
        pos = np.zeros(len(px)); cash = np.zeros(len(px)); buys = np.zeros(len(px))
        for x in t["orders"]:
            m = idx >= x["order_filled_timestamp"]
            sg = 1 if x["ft_order_side"] == "buy" else -1
            pos[m] += sg * x["amount"]; cash[m] -= sg * x["amount"] * x["safe_price"]
            if sg > 0: buys[m] += x["amount"] * x["safe_price"]
        base = np.maximum(buys, 1e-9) / t["leverage"]
        mc = (cash + pos * px["close"].values) / base * 100
        ml = (cash + pos * px["low"].values) / base * 100
        hours = (px.index - o).total_seconds().values / 3600
        mc[-1] = t["profit_ratio"] * 100
        rows.append(dict(coin=t["pair"].split("/")[0], window=w, open=o, hours=(c - o).total_seconds() / 3600,
                         final=t["profit_ratio"] * 100, dip=ml.min(), dip_h=hours[ml.argmin()], peak=mc.max(),
                         orders=len(t["orders"]), grinds=sum(1 for x in t["orders"] if x["ft_order_side"] == "buy") - 1,
                         sells=sum(1 for x in t["orders"] if x["ft_order_side"] == "sell"), lev=t["leverage"],
                         profit_abs=t["profit_abs"], exit=t["exit_reason"].split(" ")[0]))
        paths.append((hours, mc, ml, t))
d = pd.DataFrame(rows)
d["win"] = d.final > 0
print(f"{strat}: {len(d)} Trades mit Signal {SIG} an erster Stelle, Fenster {sorted(seen)}\n")

def summ(g, name):
    print(f"{name:12s} n={len(g):3d}  Dauer h med {g.hours.median():5.1f} / max {g.hours.max():6.1f}  tiefster Stand med {g.dip.median():6.1f} %"
          f" / schlechtester {g.dip.min():6.1f} %  Nachkaeufe {g.grinds.mean():.1f}  Teilverkaeufe {g.sells.mean():.1f}  Endergebnis med {g.final.median():6.1f} %")
summ(d, "alle"); summ(d[d.win], "Gewinner"); summ(d[~d.win], "Verlierer")
print("\nje Fenster:")
for w, g in d.groupby("window"):
    print(f"  {w:4s} n={len(g):3d}  Gewinner {g.win.mean()*100:4.0f} %  Summe Gewinn {g.profit_abs.sum():9.0f} USD  schlechtester {g.final.min():6.1f} %")
print("\ntiefster Stand (auf Marge) vs. Ergebnis:")
for lo, hi in [(0, -10), (-10, -25), (-25, -50), (-50, -101)]:
    g = d[(d.dip <= lo) & (d.dip > hi)]
    if len(g): print(f"  Dip {lo:4d} bis {hi:5d} %: n={len(g):3d}  Gewinner {g.win.mean()*100:4.0f} %  Endergebnis med {g.final.median():6.1f} %  Dauer med {g.hours.median():5.1f} h")
print("\nVerlierer im Detail:")
print(d[~d.win] if (~d.win).any() else d.sort_values("dip").head(12).sort_values("final")[["coin", "window", "open", "final", "dip", "hours", "grinds", "sells", "lev", "exit"]].to_string(index=False, float_format=lambda v: f"{v:.1f}"))
d.to_csv(f"/root/ft_workdir/trades{SIG}_summary.csv", index=False)

# Grafik 1: alle Verlaeufe
fig, ax = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [3, 2]})
for (h, mc, ml, t), r in zip(paths, rows):
    col = "#2a9d4b" if r["final"] > 0 else "#d1342f"
    ax[0].plot(np.minimum(h, 168), mc, color=col, alpha=0.30 if r["final"] > 0 else 0.85, lw=0.8 if r["final"] > 0 else 1.2)
ax[0].axhline(0, color="k", lw=0.8); ax[0].set_xlim(0, 168)
ax[0].set_ylim(-100, 25)
ax[0].set_xlabel("Stunden seit Eroeffnung (bis 168 h)"); ax[0].set_ylabel("Rendite auf eingesetzte Marge (%)")
ax[0].set_title(f"Signal {SIG}: {len(d)} Trades (gruen = Gewinner {d.win.sum()}, rot = Verlierer {(~d.win).sum()})")
grid = np.arange(0, 169, 2)
med = []
for gh in grid:
    vals = [mc[min(np.searchsorted(h, gh), len(mc) - 1)] if gh <= h[-1] else mc[-1] for h, mc, ml, t in paths]
    med.append(np.median(vals))
ax[0].plot(grid, med, color="#1b3a8a", lw=2.5, label="Median aller Trades (abgeschlossene = Endergebnis)")
ax[0].legend(loc="lower right")
ax[1].scatter(d.dip, d.final, c=np.where(d.win, "#2a9d4b", "#d1342f"), s=18 + d.hours.clip(upper=200) / 4, alpha=0.7)
ax[1].axhline(0, color="k", lw=0.8)
ax[1].set_xlabel("tiefster Stand waehrend des Trades (% Marge, 5m-Tief)"); ax[1].set_ylabel("Endergebnis (%)")
ax[1].set_title("Wie tief ging es vs. wie endete es (Punktgroesse = Dauer)")
for _, r in d[d.final < -15].iterrows():
    ax[1].annotate(f"{r.coin} {r.open:%d.%m.%y}", (r.dip, r.final), fontsize=7, xytext=(3, 3), textcoords="offset points")
plt.tight_layout(); plt.savefig(f"/root/ft_workdir/out{SIG}_alle.png", dpi=110); plt.close()

# Grafik 2: Verlierer einzeln
los = sorted([(r, p) for r, p in zip(rows, paths) if r["final"] <= 0], key=lambda x: x[0]["final"])
LABEL = "Verlierer"
if len(los) < 8:   # kaum Verlierer: stattdessen die 12 Trades mit dem tiefsten Stand zeigen
    los = sorted(zip(rows, paths), key=lambda x: x[0]["dip"])[:12]; LABEL = "tiefste Staende"
n = len(los); cols = 4; rws = int(np.ceil(n / cols))
fig, axs = plt.subplots(rws, cols, figsize=(16, 3.1 * rws), squeeze=False)
for a in axs.ravel(): a.axis("off")
for a, (r, (h, mc, ml, t)) in zip(axs.ravel(), los):
    a.axis("on"); a.plot(h, mc, color="#d1342f" if r["final"] <= 0 else "#2a9d4b", lw=1.3); a.plot(h, ml, color="#d1342f" if r["final"] <= 0 else "#2a9d4b", lw=0.5, alpha=0.4)
    a.axhline(0, color="k", lw=0.6)
    for x in t["orders"][1:]:
        hx = (pd.Timestamp(x["order_filled_timestamp"], unit="ms", tz="UTC") - pd.Timestamp(t["open_date"])).total_seconds() / 3600
        a.axvline(hx, color="#1b3a8a" if x["ft_order_side"] == "buy" else "#e08a00", lw=0.8, ls=":")
    a.set_title(f"{r['coin']} {r['open']:%d.%m.%y}  Ende {r['final']:.0f} %  ({r['hours']:.0f} h, {r['lev']:.0f}x)", fontsize=9)
    a.tick_params(labelsize=7)
fig.suptitle(f"{LABEL}: Signal {SIG} (blau = Nachkauf, orange = Teilverkauf/Derisk)", y=1.0)
plt.tight_layout(); plt.savefig(f"/root/ft_workdir/out{SIG}_verlierer.png", dpi=100); plt.close()
print(f"\nGrafiken: out{SIG}_alle.png, out{SIG}_verlierer.png")
