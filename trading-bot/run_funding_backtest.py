"""CLI: backtest funding-rate arbitrage (long spot + short perpetual) on real
historical funding rates and prices.

Examples:
    python run_funding_backtest.py --exchange binance --symbol BTC/USDT --days 1095
    python run_funding_backtest.py --symbol ETH/USDT --leverage 2 --entry-apr 8 --exit-apr 2
"""
from __future__ import annotations

import argparse
import json
import os
import time

from funding_backtest import CarryParams, run_carry_backtest
from funding_data import fetch_funding_history, fetch_price_history


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="binance",
                        help="ccxt exchange id with perpetual futures, e.g. binance, okx, krakenfutures, hyperliquid")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--days", type=int, default=1095, help="How many days of history to fetch")
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--leverage", type=float, default=1.0, help="Short notional / futures margin")
    parser.add_argument("--entry-apr", type=float, default=5.0,
                        help="Enter when the trailing funding APR (%%) is above this")
    parser.add_argument("--exit-apr", type=float, default=0.0,
                        help="Exit when the trailing funding APR (%%) drops below this")
    parser.add_argument("--lookback-days", type=float, default=7.0)
    parser.add_argument("--price-timeframe", default="1h",
                        help="Candle size for valuing positions / liquidation checks")
    args = parser.parse_args()

    since_ms = int((time.time() - args.days * 86400) * 1000)
    print(f"Fetching {args.days}d of funding history for {args.symbol} on {args.exchange}...")
    funding, perp = fetch_funding_history(args.exchange, args.symbol, since_ms)
    print(f"Got {len(funding)} funding payments for {perp}: {funding.index[0]} .. {funding.index[-1]}")
    print(f"Fetching {args.price_timeframe} prices...")
    prices = fetch_price_history(args.exchange, perp, since_ms, timeframe=args.price_timeframe)
    print(f"Got {len(prices)} candles")

    base = dict(leverage=args.leverage, lookback_days=args.lookback_days)
    scenarios = {
        "with entry/exit rule": CarryParams(entry_apr=args.entry_apr, exit_apr=args.exit_apr, **base),
        "always in (baseline)": CarryParams(entry_apr=None, exit_apr=None, **base),
    }

    results = {}
    for name, params in scenarios.items():
        results[name] = run_carry_backtest(funding, prices, params, initial_balance=args.balance)

    main_result = results["with entry/exit rule"]
    print(f"\n--- Funding-rate arbitrage backtest: {perp}, leverage {args.leverage:g}x, "
          f"enter > {args.entry_apr:g}% / exit < {args.exit_apr:g}% trailing {args.lookback_days:g}d APR ---")
    for k, v in main_result.metrics.items():
        print(f"{k}: {v}")

    print("\n--- Comparison ---")
    print(f"{'scenario':<24} {'return':>9} {'per year':>9} {'max DD':>8} {'in pos.':>8} {'liq.':>5}")
    for name, res in results.items():
        m = res.metrics
        print(f"{name:<24} {m['total_return_pct']:8.2f}% {m['annualized_return_pct']:8.2f}% "
              f"{m['max_drawdown_pct']:7.2f}% {m['time_in_position_pct']:7.1f}% {m['liquidations']:5d}")

    os.makedirs("logs", exist_ok=True)
    with open("logs/funding_backtest_events.jsonl", "w") as f:
        for e in main_result.events:
            f.write(json.dumps({**e, "time": str(e["time"])}) + "\n")
    print(f"\n{len(main_result.events)} entries/exits/rebalances logged to logs/funding_backtest_events.jsonl")
    print("Not included: exchange default risk, basis between spot and perp, taxes. Not financial advice.")


if __name__ == "__main__":
    main()
