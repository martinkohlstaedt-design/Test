"""Grid-Bot-Simulation (long-only, 1x) auf Kraken-Futures-5m-Kerzen.
Gitter: N Kaufstufen geometrisch unter dem Startkurs (Abstand STEP), Verkauf je eine Stufe hoeher.
Kapital C gleich auf die Stufen verteilt. Faellt der Kurs unter die unterste Stufe - 5 %: Variante HOLD (halten,
Gitter bleibt) oder STOP (alles verkaufen, Gitter am neuen Kurs neu). Steigt der Kurs ueber die oberste
Verkaufsstufe und ist nichts mehr gekauft: Gitter am neuen Kurs neu. Gebuehr je Ausfuehrung FEE.
Kaeufe einer Kerze koennen erst ab der naechsten Kerze verkauft werden (vorsichtig)."""
import sys, numpy as np, pandas as pd
D = "/root/ft_workdir/user_data/data/krakenfutures/futures/"
W = {"w1": ("2022-08-24", "2023-05-01"), "w2": ("2023-05-01", "2024-01-01"), "w2c": ("2024-01-01", "2024-05-01"),
     "w4a": ("2024-09-01", "2025-01-01"), "w3": ("2024-10-01", "2025-04-01"), "val": ("2025-04-01", "2025-10-01"),
     "h1": ("2025-09-26", "2026-03-15"), "h2": ("2026-03-15", "2026-10-06")}
FEE = 0.0002

def sim(df, N=20, STEP=0.01, mode="HOLD", C=10000.0):
    lo, hi, cl = df["low"].values, df["high"].values, df["close"].values
    cash, eq_curve = C, []
    def setup(p):
        return p * (1 - STEP) ** np.arange(1, N + 1)
    lv = setup(cl[0]); held = np.zeros(N); qty = np.zeros(N)
    per = C / N
    for i in range(len(cl)):
        # Verkaeufe (nur Bestaende aus frueheren Kerzen)
        for k in np.nonzero(held)[0]:
            sp = lv[k] * (1 + STEP)
            if hi[i] >= sp:
                cash += qty[k] * sp * (1 - FEE); held[k] = 0; qty[k] = 0
        newly = []
        for k in range(N):
            if not held[k] and lo[i] <= lv[k] and cash >= per * 0.999:
                q = per / lv[k]; cash -= per * (1 + FEE) / (1 + FEE) ; cash -= per * FEE
                qty[k] = q; held[k] = 1; newly.append(k)
        pos_val = float((qty * cl[i]).sum())
        eq_curve.append(cash + pos_val)
        # Neu ausrichten
        if not held.any() and cl[i] > lv[0] * (1 + STEP) * 1.02:
            per = (cash) / N; lv = setup(cl[i])
        elif cl[i] < lv[-1] * 0.95 and mode == "STOP":
            cash += float((qty * cl[i]).sum()) * (1 - FEE); held[:] = 0; qty[:] = 0
            per = cash / N; lv = setup(cl[i])
    eq = np.array(eq_curve); pk = np.maximum.accumulate(eq)
    return (eq[-1] / C - 1) * 100, ((pk - eq) / pk).max() * 100

coins = sys.argv[1].split(",") if len(sys.argv) > 1 else ["BTC", "ETH", "SOL", "XRP"]
for N, STEP in [(20, 0.01), (15, 0.02)]:
    for mode in ["HOLD", "STOP"]:
        line = f"N={N:2d} Abstand={STEP*100:.0f}% {mode:4s} |"
        for w, (a, b) in W.items():
            r, d = [], []
            for c in coins:
                df = pd.read_feather(D + f"{c}_USD_USD-5m-futures.feather")
                df = df[(df.date >= a) & (df.date < b)]
                if len(df) < 1000: continue
                x, y = sim(df, N, STEP, mode); r.append(x); d.append(y)
            line += f" {w} {np.mean(r):6.1f}/{max(d):4.1f} |"
        print(line, flush=True)
