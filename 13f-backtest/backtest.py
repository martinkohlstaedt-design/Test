"""Backtest copying 13F positions with realistic filing delay.

Rebalance on (period end + 46 days), i.e. after the 45-day filing deadline, so no
look-ahead. Hold to the next rebalance. Quarterly returns, no costs.
"""
import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from edgar13f import load_manager
from securities import map_cusips, prices

LAG_DAYS = 46


def top_positions(positions, n):
    items = sorted(positions.items(), key=lambda kv: -kv[1]["value"])[:n]
    tot = sum(v["value"] for _, v in items)
    return {c: v["value"] / tot for c, v in items} if tot else {}


def build_signals(data, tickers, top_n, broad_n, min_consensus):
    """-> {period: {strategy: {ticker: weight}}}"""
    periods = sorted({f["period"] for fl in data.values() for f in fl})
    sig = {}
    for p in periods:
        strat = {"Top-N pro Manager": {}, "Konsens": {}, "Neu-Einstiege": {}, "Breit (Top-Broad)": {}}
        cons, new_w, n_mgr = {}, {}, 0
        for fl in data.values():
            idx = next((i for i, f in enumerate(fl) if f["period"] == p), None)
            if idx is None:
                continue
            n_mgr += 1
            pos = fl[idx]["positions"]
            prev = fl[idx - 1]["positions"] if idx else {}

            def to_t(w):
                out = {}
                for c, x in w.items():
                    if tickers.get(c):
                        out[tickers[c]] = out.get(tickers[c], 0) + x
                s = sum(out.values())
                return {t: x / s for t, x in out.items()} if s else {}

            for t, x in to_t(top_positions(pos, top_n)).items():
                strat["Top-N pro Manager"][t] = strat["Top-N pro Manager"].get(t, 0) + x
                cons[t] = cons.get(t, 0) + 1
            for t, x in to_t(top_positions(pos, broad_n)).items():
                strat["Breit (Top-Broad)"][t] = strat["Breit (Top-Broad)"].get(t, 0) + x
            fresh = {c: v for c, v in pos.items() if c not in prev} if idx else {}
            for t, x in to_t(top_positions(fresh, top_n)).items():
                new_w[t] = new_w.get(t, 0) + x
        strat["Konsens"] = {t: 1.0 for t, k in cons.items() if k >= min_consensus}
        strat["Neu-Einstiege"] = new_w
        sig[p] = {k: v for k, v in strat.items()}
        sig[p]["_n_mgr"] = n_mgr
    return sig


def period_return(weights, start, end, px):
    """Weighted return start->end; returns (ret, covered weight share)."""
    tot = sum(weights.values())
    acc = cov = 0.0
    for t, w in weights.items():
        s = px.get(t)
        if s is None or s.empty:
            continue
        i0, i1 = s.index.searchsorted(start), s.index.searchsorted(end, side="right") - 1
        if i0 >= len(s) or i1 <= i0 or s.index[i0] > start + timedelta(days=7):
            continue
        acc += w * (s.iloc[i1] / s.iloc[i0] - 1)
        cov += w
    return (acc / cov if cov else np.nan), (cov / tot if tot else 0.0)


def metrics(r, b):
    r, b = np.asarray(r), np.asarray(b)
    n = len(r)
    eq = np.cumprod(1 + r)
    ex = r - b
    beta, alpha = np.polyfit(b, r, 1)
    return {
        "Quartale": n,
        "CAGR %": round((eq[-1] ** (4 / n) - 1) * 100, 1),
        "Vola % p.a.": round(r.std(ddof=1) * 2 * 100, 1),
        "Sharpe": round(r.mean() * 4 / (r.std(ddof=1) * 2), 2),
        "MaxDD % (Qrt.)": round((eq / np.maximum.accumulate(eq) - 1).min() * 100, 1),
        "Beta": round(beta, 2),
        "Alpha % p.a.": round(alpha * 4 * 100, 1),
        "Excess/Qrt. %": round(ex.mean() * 100, 2),
        "t-Stat Excess": round(ex.mean() / (ex.std(ddof=1) / np.sqrt(n)), 2),
        "Trefferquote": f"{(ex > 0).mean():.0%}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--broad", type=int, default=30)
    ap.add_argument("--min-consensus", type=int, default=3)
    ap.add_argument("--managers", default="managers.json")
    a = ap.parse_args()

    mgrs = json.loads(Path(a.managers).read_text())
    data = {}
    for name, cik in mgrs.items():
        print(f"Lade {name} ...", flush=True)
        data[name] = load_manager(cik)

    need = {c for fl in data.values() for f in fl
            for c in top_positions(f["positions"], max(a.top, a.broad))}
    print(f"{len(need)} CUSIPs mappen ...", flush=True)
    tickers = map_cusips(need)

    sig = build_signals(data, tickers, a.top, a.broad, a.min_consensus)
    all_t = {t for p in sig.values() for k, w in p.items() if k != "_n_mgr" for t in w}
    print(f"{len(all_t)} Ticker: Kurse laden ...", flush=True)
    px = {t: prices(t) for t in sorted(all_t | {"SPY", "RSP"})}

    periods = sorted(sig)
    starts = [pd.Timestamp(p) + timedelta(days=LAG_DAYS) for p in periods]
    last_day = px["SPY"].index[-1]
    rows, covs = [], {}
    for p, s0, s1 in zip(periods, starts, starts[1:] + [last_day]):
        if s1 > last_day or s1 <= s0:
            continue
        row = {"Periode": p, "SPY": period_return({"SPY": 1}, s0, s1, px)[0],
               "RSP": period_return({"RSP": 1}, s0, s1, px)[0]}
        for k, w in sig[p].items():
            if k == "_n_mgr" or not w:
                continue
            row[k], c = period_return(w, s0, s1, px)
            covs.setdefault(k, []).append(c)
        rows.append(row)
    df = pd.DataFrame(rows).set_index("Periode")

    out = Path("output")
    out.mkdir(exist_ok=True)
    df.to_csv(out / "quarterly_returns.csv")
    strategies = [c for c in df.columns if c not in ("SPY", "RSP")]
    table = {}
    for k in strategies + ["RSP", "SPY"]:
        d = df[[k, "SPY"]].dropna() if k != "SPY" else df[["SPY"]].dropna()
        table[k] = metrics(d[k], d["SPY"])
    res = pd.DataFrame(table).T
    res["Kursabdeckung"] = [f"{np.mean(covs[k]):.0%}" if k in covs else "-" for k in res.index]
    md = ["# 13F-Backtest (Rebalance 46 Tage nach Quartalsende, ohne Kosten)\n",
          f"Parameter: top={a.top}, broad={a.broad}, min-consensus={a.min_consensus}, "
          f"{len(mgrs)} Manager, {df.index[0]} bis {df.index[-1]}\n", res.to_markdown(), ""]
    latest = periods[-1]
    md.append(f"\n## Aktuelle Signale (Periode {latest}, {sig[latest]['_n_mgr']} Manager)\n")
    cons = sorted(sig[latest]["Konsens"])
    md.append("Konsens (>= %d Manager in den Top-%d): %s\n" % (a.min_consensus, a.top, ", ".join(cons) or "-"))
    new = sorted(sig[latest]["Neu-Einstiege"].items(), key=lambda kv: -kv[1])[:15]
    md.append("Größte Neu-Einstiege: " + ", ".join(f"{t} ({w:.1f})" for t, w in new))
    (out / "report.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
