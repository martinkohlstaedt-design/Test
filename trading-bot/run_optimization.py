"""CLI: walk-forward parameter search for the signal engine.

Splits fetched history into a training window (searched over) and a
held-out test window (reported, never optimized against) — see the
overfitting warning in optimizer.py. Saves the winning params to a JSON
file you can point config.yaml's `signal_params` at, or pass to
run_backtest.py --params.

Example:
    python run_optimization.py --exchange binance --symbol BTC/USDT --timeframe 1d --days 1095
"""
from __future__ import annotations

import argparse
import json
import time

from data_feed import fetch_ohlcv_full_history
from optimizer import DEFAULT_PARAM_GRID, run_walk_forward
from risk_manager import RiskManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--days", type=int, default=1095)
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--train-frac", type=float, default=0.7)
    parser.add_argument("--out", default="best_params.json")
    args = parser.parse_args()

    since_ms = int((time.time() - args.days * 86400) * 1000)
    print(f"Fetching {args.days}d of {args.timeframe} candles for {args.symbol} on {args.exchange}...")
    df = fetch_ohlcv_full_history(args.exchange, args.symbol, timeframe=args.timeframe, since_ms=since_ms)
    print(f"Got {len(df)} candles: {df.index[0]} .. {df.index[-1]}")

    result = run_walk_forward(
        df, DEFAULT_PARAM_GRID, train_frac=args.train_frac,
        risk_manager=RiskManager(), symbol=args.symbol,
        initial_balance=args.balance, timeframe=args.timeframe,
    )

    print(f"\nTrain window: {result['train_size']} candles, test window: {result['test_size']} candles")
    print("\n--- Train metrics (optimized against this data — expect this to look good) ---")
    for k, v in (result["train_metrics"] or {}).items():
        print(f"{k}: {v}")
    print("\n--- Test metrics (held-out, never optimized against — trust this more) ---")
    for k, v in result["test_metrics"].items():
        print(f"{k}: {v}")

    with open(args.out, "w") as f:
        json.dump(result["best_params"], f, indent=2)
    print(f"\nBest params written to {args.out}")
    if result["test_metrics"]["total_return_pct"] <= 0 or result["test_metrics"]["num_round_trips"] < 3:
        print(
            "\nWARNING: the held-out test result is weak or based on very few trades. "
            "Do not treat this as a strategy that's ready for real money — try a longer "
            "history, a different timeframe, or accept that this signal set may not have "
            "a real edge on this symbol."
        )


if __name__ == "__main__":
    main()
