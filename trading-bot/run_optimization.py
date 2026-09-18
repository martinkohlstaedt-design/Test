"""CLI: rolling walk-forward parameter search for the signal engine.

Splits fetched history into several rolling train/test folds (searching only
on each fold's training window, scoring only on its held-out test window) so
you see whether a parameter set actually generalizes across different market
periods — not just whether it got lucky on one split. See optimizer.py's
module docstring for the overfitting caveats this does and doesn't address.

Example:
    python run_optimization.py --exchange binance --symbol BTC/USDT --timeframe 1d --days 1095
"""
from __future__ import annotations

import argparse
import json
import time

from data_feed import fetch_ohlcv_full_history
from optimizer import DEFAULT_PARAM_GRID, run_rolling_walk_forward
from risk_manager import RiskManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--days", type=int, default=1095)
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--train-frac", type=float, default=0.5)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--out", default="best_params.json")
    args = parser.parse_args()

    since_ms = int((time.time() - args.days * 86400) * 1000)
    print(f"Fetching {args.days}d of {args.timeframe} candles for {args.symbol} on {args.exchange}...")
    df = fetch_ohlcv_full_history(args.exchange, args.symbol, timeframe=args.timeframe, since_ms=since_ms)
    print(f"Got {len(df)} candles: {df.index[0]} .. {df.index[-1]}")
    print(f"Running {args.folds}-fold rolling walk-forward search "
          f"({len(DEFAULT_PARAM_GRID)} params, this can take a while)...\n")

    result = run_rolling_walk_forward(
        df, DEFAULT_PARAM_GRID, n_folds=args.folds, train_frac=args.train_frac,
        risk_manager=RiskManager(), symbol=args.symbol,
        initial_balance=args.balance, timeframe=args.timeframe,
    )

    print("--- Per-fold results (out-of-sample only) ---")
    for f in result["folds"]:
        tr, te = f["train_range"], f["test_range"]
        m = f["test_metrics"]
        print(f"Fold {f['fold']}: train {tr[0].date()}..{tr[1].date()}  "
              f"test {te[0].date()}..{te[1].date()}  "
              f"return={m['total_return_pct']:+.2f}%  trades={m['num_trades']}  "
              f"sharpe={m['sharpe_ratio']:.2f}")

    s = result["summary"]
    print("\n--- Summary across all folds ---")
    print(f"Profitable folds: {s['profitable_folds']}/{s['n_folds']}")
    print(f"Mean out-of-sample return: {s['mean_test_return_pct']:+.2f}%  "
          f"(worst: {s['worst_test_return_pct']:+.2f}%, best: {s['best_test_return_pct']:+.2f}%)")
    print(f"Mean out-of-sample Sharpe: {s['mean_test_sharpe_ratio']:.2f}")

    # Use the most recent fold's params — closest to current market conditions —
    # as the one written out for config.yaml.
    latest_params = result["folds"][-1]["best_params"]
    with open(args.out, "w") as f:
        json.dump(latest_params, f, indent=2)
    print(f"\nMost recent fold's params written to {args.out}")

    if s["profitable_folds"] < s["n_folds"] * 0.6:
        print(
            "\nWARNING: this parameter set was only profitable in a minority of "
            "out-of-sample folds. That is evidence against a real, consistent edge "
            "on this symbol/timeframe — treat any single profitable fold as noise "
            "rather than a strategy worth trading, paper or otherwise."
        )


if __name__ == "__main__":
    main()
