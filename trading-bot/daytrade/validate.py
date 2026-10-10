"""Rolling walk-forward validation.

For each fold, parameters are picked on the training window (best Sharpe,
with a minimum trade count) and then traded UNCHANGED on the following
unseen test window. Only the stitched-together out-of-sample results count;
in-sample numbers are shown to expose how much optimisation flatters them.

    python -m daytrade.validate --symbols SPY QQQ AAPL        # real data in data/
    python -m daytrade.validate --synthetic                    # no-edge sanity check
"""
from __future__ import annotations

import argparse
import itertools

import pandas as pd

from . import data
from .engine import Costs, metrics, run
from .features import build_days
from .strategies import PARAM_GRIDS


def grid(space: dict):
    keys = list(space)
    for combo in itertools.product(*space.values()):
        yield dict(zip(keys, combo))


def walk_forward(days_by_symbol, strategy: str, costs: Costs, train_days: int, test_days: int,
                 min_train_trades: int = 30, space: dict | None = None):
    dates = pd.DatetimeIndex(sorted({d.date for ds in days_by_symbol.values() for d in ds}))
    space = space or PARAM_GRIDS[strategy]
    oos_trades, oos_dates, folds = [], [], []
    start = 0
    while start + train_days + test_days <= len(dates):
        tr = dates[start:start + train_days]
        te = dates[start + train_days:start + train_days + test_days]
        best, best_sh = None, -1e9
        for p in grid(space):
            t = run(days_by_symbol, strategy, p, costs, lambda d, lo=tr[0], hi=tr[-1]: lo <= d <= hi)
            if len(t) < min_train_trades:
                continue
            m = metrics(t, tr, costs)
            if m["sharpe"] > best_sh:
                best, best_sh, best_m = p, m["sharpe"], m
        if best is not None:
            t = run(days_by_symbol, strategy, best, costs, lambda d, lo=te[0], hi=te[-1]: lo <= d <= hi)
            oos_trades.append(t)
            m_te = metrics(t, te, costs)
            folds.append({"test_from": te[0].date(), "params": best, "train_sharpe": best_m["sharpe"],
                          "test_sharpe": m_te["sharpe"], "test_ret_pct": m_te["total_return_pct"],
                          "test_trades": m_te["trades"]})
        oos_dates.append(te)
        start += test_days
    all_oos = pd.concat([t for t in oos_trades if len(t)], ignore_index=True) if oos_trades else pd.DataFrame()
    oos_idx = pd.DatetimeIndex([d for te in oos_dates for d in te])
    return all_oos, oos_idx, folds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "AMD", "GOOGL"])
    ap.add_argument("--timeframe", default="5Min")
    ap.add_argument("--train-days", type=int, default=250)
    ap.add_argument("--test-days", type=int, default=60)
    ap.add_argument("--slippage-bps", type=float, default=2.0)
    ap.add_argument("--risk-pct", type=float, default=0.005)
    ap.add_argument("--synthetic", action="store_true", help="random-walk data: nothing should be profitable")
    ap.add_argument("--strategies", nargs="+", default=list(PARAM_GRIDS))
    a = ap.parse_args()

    costs = Costs(slippage_bps=a.slippage_bps, risk_pct=a.risk_pct)
    if a.synthetic:
        frames = {s: data.synthetic(days=a.train_days + 4 * a.test_days, seed=i) for i, s in enumerate(a.symbols[:5])}
    else:
        frames = {s: data.load_symbol(s, a.timeframe) for s in a.symbols}
    days = {s: build_days(df, s) for s, df in frames.items()}
    n = sum(len(v) for v in days.values())
    print(f"{len(days)} symbols, {n} symbol-days, slippage {a.slippage_bps} bps/side, risk {a.risk_pct:.2%}/trade\n")

    for strat in a.strategies:
        oos, idx, folds = walk_forward(days, strat, costs, a.train_days, a.test_days)
        print(f"=== {strat} ===")
        if not folds:
            print("  not enough data / trades for walk-forward\n")
            continue
        for f in folds:
            print(f"  from {f['test_from']}: train Sharpe {f['train_sharpe']:>5} -> test Sharpe {f['test_sharpe']:>5} "
                  f"({f['test_ret_pct']:>6}% , {f['test_trades']} trades)  {f['params']}")
        print("  OUT-OF-SAMPLE:", metrics(oos, idx, costs), "\n")


if __name__ == "__main__":
    main()
