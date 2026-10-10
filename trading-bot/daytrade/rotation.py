"""ETF rotation / allocation strategies (long only, no leverage, monthly decisions).

Same timing and cost model as swing.py: weights decided at a month-end CLOSE
trade at the next OPEN. Compared on a development window (2016-2020) and an
untouched test window (2021-2026) so a strategy that only shines in one half is exposed.

    python -m daytrade.rotation
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import swing
from .download_daily import BENCH, UNIVERSE

SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB"]
RISK = ["SPY", "QQQ", "IWM", "EFA", "EEM"]
DEFENSIVE = ["IEF", "TLT", "GLD", "SHY"]
ALL_ETF = sorted(set(SECTORS + RISK + DEFENSIVE))


def _month_end_mask(idx: pd.DatetimeIndex) -> pd.Series:
    s = idx.to_series()
    return s.groupby(idx.to_period("M")).transform("max") == s


def _hold(w_at_decision: pd.DataFrame, idx) -> pd.DataFrame:
    """Keep month-end weights until the next month-end."""
    return w_at_decision.where(_month_end_mask(idx), np.nan).ffill().fillna(0.0)


def sector_rotation(c: pd.DataFrame, top_k=3, lookback_m=6, defensive="IEF") -> pd.DataFrame:
    mom = c[SECTORS] / c[SECTORS].shift(lookback_m * 21) - 1
    rank = mom.rank(axis=1, ascending=False)
    w = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    sel = (rank <= top_k) & (mom > 0)                       # absolute filter: only positive momentum
    w[SECTORS] = sel.astype(float).div(top_k)
    w[defensive] = 1 - w[SECTORS].sum(axis=1)               # unfilled slots -> defensive asset
    return _hold(w, c.index)


def dual_momentum(c: pd.DataFrame, lookback_m=12, top_k=1) -> pd.DataFrame:
    mom = c[RISK] / c[RISK].shift(lookback_m * 21) - 1
    cash_mom = c["SHY"] / c["SHY"].shift(lookback_m * 21) - 1
    rank = mom.rank(axis=1, ascending=False)
    sel = (rank <= top_k) & mom.gt(cash_mom, axis=0)
    w = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    w[RISK] = sel.astype(float).div(top_k)
    w["IEF"] = 1 - w[RISK].sum(axis=1)
    return _hold(w, c.index)


def asset_trend(c: pd.DataFrame, sma_days=210, universe=None) -> pd.DataFrame:
    """Faber-style: hold each asset that is above its 10-month SMA, equal weight; rest in SHY."""
    uni = universe or (RISK + ["TLT", "IEF", "GLD"] + SECTORS)
    on = (c[uni] > c[uni].rolling(sma_days).mean()).astype(float)
    w = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    slot = 1.0 / len(uni)
    w[uni] = on * slot
    w["SHY"] = 1 - w[uni].sum(axis=1)
    return _hold(w, c.index)


def stocks_trend_park(px_all: dict, park="SPY", min_slots=10) -> pd.DataFrame:
    """Existing bot logic: trend stocks, idle capital parked in `park` (daily decisions)."""
    uni = {k: v[UNIVERSE] for k, v in px_all.items()}
    w = swing.equalise(swing.trend_donchian(uni), min_slots).reindex(columns=px_all["close"].columns, fill_value=0.0)
    w[park] = (1 - w[UNIVERSE].sum(axis=1)).clip(lower=0)
    return w


def stocks_trend_regime(px_all: dict, min_slots=10) -> pd.DataFrame:
    """Trend stocks; idle capital -> SPY while SPY>SMA200, else IEF (defensive)."""
    spy = px_all["close"]["SPY"]
    on = (spy > spy.rolling(200).mean()).astype(float)
    w = stocks_trend_park(px_all, "SPY", min_slots)
    idle = w["SPY"].copy()
    w["SPY"] = idle * on
    w["IEF"] = idle * (1 - on)
    return w


def evaluate(name: str, w: pd.DataFrame, px_all: dict, cost_bps: float, rows: list):
    r = swing.backtest(w, px_all, cost_bps)
    f, a, b = swing.stats(r), swing.stats(r.loc[:"2020-12-31"]), swing.stats(r.loc["2021-01-01":])
    rows.append({"strategy": name, "CAGR": f["cagr_%"], "Sharpe": f["sharpe"], "MaxDD": f["maxdd_%"],
                 "dev CAGR": a["cagr_%"], "dev Sh": a["sharpe"], "test CAGR": b["cagr_%"], "test Sh": b["sharpe"]})
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-bps", type=float, default=3.0)
    a = ap.parse_args()
    px = swing.load_panel(UNIVERSE + BENCH + ALL_ETF)
    c = px["close"]
    rows: list = []
    one = lambda s: pd.DataFrame({k: (1.0 if k == s else 0.0) for k in c.columns}, index=c.index)
    evaluate("SPY buy&hold", one("SPY"), px, a.cost_bps, rows)
    evaluate("QQQ buy&hold", one("QQQ"), px, a.cost_bps, rows)
    base = stocks_trend_park(px)
    evaluate("A  trend stocks + SPY park (bot)", base, px, a.cost_bps, rows)
    evaluate("A2 trend stocks + QQQ park", stocks_trend_park(px, "QQQ"), px, a.cost_bps, rows)
    evaluate("A3 trend stocks, idle->SPY/IEF regime", stocks_trend_regime(px), px, a.cost_bps, rows)
    for k, lb in ((3, 6), (3, 12), (2, 6), (4, 6)):
        evaluate(f"B  sector rotation top{k} {lb}m", sector_rotation(c, k, lb), px, a.cost_bps, rows)
    for lb in (6, 12):
        evaluate(f"C  dual momentum {lb}m", dual_momentum(c, lb), px, a.cost_bps, rows)
    evaluate("D  asset trend (Faber, 10m SMA)", asset_trend(c), px, a.cost_bps, rows)
    evaluate("E  50% A + 50% B(top3,6m)", 0.5 * base + 0.5 * sector_rotation(c), px, a.cost_bps, rows)
    evaluate("F  50% A + 50% D", 0.5 * base + 0.5 * asset_trend(c), px, a.cost_bps, rows)
    evaluate("G  1/3 A + 1/3 B + 1/3 D", (base + sector_rotation(c) + asset_trend(c)) / 3, px, a.cost_bps, rows)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
