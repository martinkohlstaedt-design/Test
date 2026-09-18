"""CLI: fetch historical OHLCV and run one backtest with the default (or a
saved) signal-engine configuration.

Example:
    python run_backtest.py --exchange binance --symbol BTC/USDT --timeframe 1d --days 730
"""
from __future__ import annotations

import argparse
import json
import time

from backtester import run_backtest
from data_feed import fetch_ohlcv_full_history
from optimizer import split_engine_and_risk_params
from risk_manager import RiskManager
from signal_engine import DEFAULT_PARAMS, SignalEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--days", type=int, default=730, help="How many days of history to fetch")
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--params", help="Path to a JSON file with signal_engine params (optional)")
    args = parser.parse_args()

    since_ms = int((time.time() - args.days * 86400) * 1000)
    print(f"Fetching {args.days}d of {args.timeframe} candles for {args.symbol} on {args.exchange}...")
    df = fetch_ohlcv_full_history(args.exchange, args.symbol, timeframe=args.timeframe, since_ms=since_ms)
    print(f"Got {len(df)} candles: {df.index[0]} .. {df.index[-1]}")

    params = DEFAULT_PARAMS
    if args.params:
        with open(args.params) as f:
            params = {**DEFAULT_PARAMS, **json.load(f)}

    # A saved params file (from run_optimization.py) may include RiskManager
    # fields like stop_loss_pct alongside the signal-engine ones — route each
    # to where it actually takes effect instead of silently dropping them.
    engine_params, risk = split_engine_and_risk_params(params, RiskManager())
    engine = SignalEngine(engine_params)
    result = run_backtest(df, engine, risk, symbol=args.symbol, initial_balance=args.balance, timeframe=args.timeframe)

    print("\n--- Backtest metrics ---")
    for k, v in result.metrics.items():
        print(f"{k}: {v}")
    print(f"\n{len(result.trades)} trades logged to logs/backtest_trades.jsonl")


if __name__ == "__main__":
    main()
