"""'Stocks in Play' opening-range breakout, rebuilt from the public description of
Zarattini/Barbon/Aziz ("A Profitable Day Trading Strategy For The U.S. Equity Market").

Rules as implemented (parameters from the paper as I know them - NOT verified against the PDF):
  * Each day, rank stocks by relative volume of the FIRST 5-min bar vs. its 14-day average;
    keep those with price > $5, daily ATR14 >= $0.50 and RVOL >= rvol_min; trade the top_n.
  * Direction = colour of the first 5-min candle; enter at the OPEN of the second candle.
  * Stop = stop_atr x daily ATR14 from entry (paper: 10 %); no target; flat at the close.
  * Risk 1 % of equity per trade, total gross exposure capped at max_leverage.
`random_direction=True` keeps everything but flips a coin for the side - if that makes the
same money, the first-candle signal has no edge (the check suggested by the independent replication).

    python -m daytrade.stocks_in_play
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import data
from .engine import Costs, daily_returns, metrics, simulate_trade
from .features import build_days
from .strategies import Setup
from .download_daily import UNIVERSE


def candidates(days_by_symbol: dict, atr_len=14, rvol_len=14) -> pd.DataFrame:
    rows = []
    for sym, days in days_by_symbol.items():
        fv = pd.Series([d.v[0] for d in days], dtype=float)
        rvol = (fv / fv.rolling(rvol_len).mean().shift(1)).to_numpy()
        hi = pd.Series([d.h.max() for d in days]); lo = pd.Series([d.l.min() for d in days])
        cl = pd.Series([d.c[-1] for d in days]); pc = cl.shift(1)
        tr = pd.concat([hi - lo, (hi - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)
        atr = tr.rolling(atr_len).mean().shift(1).to_numpy()          # known before the open
        for i, d in enumerate(days):
            if d.n >= 3 and not np.isnan(rvol[i]) and not np.isnan(atr[i]):
                rows.append({"date": d.date, "symbol": sym, "i": i, "rvol": rvol[i], "atr": atr[i], "day": d})
    return pd.DataFrame(rows)


def run(cands: pd.DataFrame, costs: Costs, top_n=20, stop_atr=0.10, rvol_min=1.0,
        random_direction=False, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    trades = []
    sel = cands[(cands.rvol >= rvol_min) & (cands.atr >= 0.5) & (cands.day.map(lambda d: d.o[0]) > 5)]
    for date, g in sel.groupby("date"):
        for _, r in g.nlargest(top_n, "rvol").iterrows():
            d = r.day
            side = int(np.sign(d.c[0] - d.o[0]))
            if side == 0:
                continue
            if random_direction:
                side = int(rng.choice([-1, 1]))
            entry = d.o[1]
            stop = entry - side * stop_atr * r.atr
            target = entry * 1e3 if side > 0 else 1e-6
            t = simulate_trade(d, Setup(1, side, stop, target), costs)
            if t:
                trades.append(t)
    return pd.DataFrame(trades)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=UNIVERSE)
    a = ap.parse_args()
    days = {}
    for s in a.symbols:
        try:
            days[s] = build_days(data.load_symbol(s, "5Min"), s)
        except FileNotFoundError:
            pass
    cands = candidates(days)
    dates = pd.DatetimeIndex(sorted(cands.date.unique()))
    print(f"{len(days)} symbols, {len(dates)} days {dates[0].date()}..{dates[-1].date()}, {len(cands)} candidates\n")
    cols = ["trades", "win_rate_pct", "avg_R", "profit_factor", "total_return_pct", "annual_return_pct", "max_drawdown_pct", "sharpe"]
    print(f"{'config':<58}" + "".join(f"{c[:9]:>11}" for c in cols))
    for slip in (0.0, 1.0, 2.0):
        for lev in (1.0, 4.0):
            for top_n, stop_atr in ((5, 0.10), (10, 0.10), (20, 0.10), (10, 0.25), (10, 0.50)):
                costs = Costs(slippage_bps=slip, risk_pct=0.01, max_leverage=lev)
                for rnd in (False, True):
                    if rnd and (top_n, stop_atr) != (10, 0.10):
                        continue
                    t = run(cands, costs, top_n, stop_atr, 1.0, rnd)
                    m = metrics(t, dates, costs)
                    name = f"slip{slip:g}bps lev{lev:g}x top{top_n} stop{stop_atr:g}ATR{' RANDOM-DIR' if rnd else ''}"
                    print(f"{name:<58}" + "".join(f"{m[c]:>11}" for c in cols))
        print()


if __name__ == "__main__":
    main()
