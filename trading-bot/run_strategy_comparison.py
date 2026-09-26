"""CLI: compare Buy & Hold, DCA, the indicator bot, a grid bot and funding-rate
arbitrage on the same coin, period and starting capital.

Examples:
    python run_strategy_comparison.py --exchange binance --symbol BTC/USDT --days 1095
    python run_strategy_comparison.py --symbol ETH/USDT --days 730 --grid-range 0.4 --grids 30
"""
from __future__ import annotations

import argparse
import os
import time

import pandas as pd

from funding_backtest import CarryParams, run_carry_backtest
from funding_data import fetch_funding_history, fetch_price_history
from strategy_comparison import (StrategyResult, buy_and_hold, dca, grid_bot, indicator_bot, summarize,
                                 yearly_returns)

LEADIN_DAYS = 250  # daily candles before the start, so the indicator bot's SMA200 is warmed up


def daily(series: pd.Series) -> pd.Series:
    return series.resample("1D").last().dropna()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--days", type=int, default=1095)
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--fee", type=float, default=0.001, help="Fee per fill (0.001 = 0.1%%)")
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--grid-range", type=float, default=0.30, help="Grid band +/- this fraction around the start price")
    parser.add_argument("--grids", type=int, default=20)
    parser.add_argument("--funding-exchange", help="Exchange for the funding-carry leg (default: --exchange)")
    parser.add_argument("--no-funding", action="store_true", help="Skip the funding-rate arbitrage strategy")
    args = parser.parse_args()

    now = time.time()
    since_ms = int((now - args.days * 86400) * 1000)
    fill_cost = args.fee + args.slippage

    print(f"Fetching {args.days}d of hourly {args.symbol} candles on {args.exchange}...")
    hourly = fetch_price_history(args.exchange, args.symbol, since_ms, timeframe="1h")
    print(f"Got {len(hourly)} candles: {hourly.index[0]} .. {hourly.index[-1]}")
    start = hourly.index[0]

    print(f"Fetching daily candles incl. {LEADIN_DAYS}d lead-in for the indicator bot...")
    daily_df = fetch_price_history(args.exchange, args.symbol, since_ms - LEADIN_DAYS * 86_400_000, timeframe="1d")

    daily_prices = hourly.resample("1D").agg({"open": "first", "high": "max", "low": "min",
                                              "close": "last", "volume": "sum"}).dropna()

    results: list[StrategyResult] = [
        buy_and_hold(daily_prices, args.balance, fill_cost),
        dca(daily_prices, args.balance, fill_cost),
        indicator_bot(daily_df, start, args.balance, args.fee, args.slippage),
        grid_bot(hourly, args.balance, fill_cost, range_pct=args.grid_range, grids=args.grids),
    ]

    if not args.no_funding:
        fx = args.funding_exchange or args.exchange
        try:
            print(f"Fetching funding history on {fx}...")
            funding, perp = fetch_funding_history(fx, args.symbol, since_ms)
            perp_prices = fetch_price_history(fx, perp, since_ms, timeframe="1h")
            carry = run_carry_backtest(funding, perp_prices, CarryParams(entry_apr=None, exit_apr=None),
                                       initial_balance=args.balance)
            equity = carry.equity_curve
            note = f"{perp} on {fx}, 1x, always in"
            if equity.index[0] > start + pd.Timedelta(days=7):
                note += f"; funding data only from {equity.index[0]:%Y-%m-%d} (idle cash before)"
                before = pd.Series(args.balance, index=daily_prices.index[daily_prices.index < equity.index[0]])
                equity = pd.concat([before, equity])
            results.append(StrategyResult("Funding arbitrage", equity, trades=carry.metrics["entries"]
                                          + carry.metrics["exits"] + carry.metrics["rebalances"],
                                          fees=carry.metrics["fees_paid"], note=note))
        except Exception as exc:
            print(f"Funding arbitrage skipped: {exc}")

    # Compare everything on daily closes so drawdowns are measured the same way.
    for r in results:
        r.equity = daily(r.equity)

    rows = sorted((summarize(r, args.balance) for r in results), key=lambda x: x["final"], reverse=True)
    coin_move = (daily_prices["close"].iloc[-1] / daily_prices["close"].iloc[0] - 1) * 100
    print(f"\n=== {args.symbol}, {daily_prices.index[0]:%Y-%m-%d} .. {daily_prices.index[-1]:%Y-%m-%d}, "
          f"start capital {args.balance:,.0f}, coin price change {coin_move:+.1f}% ===")
    print(f"{'strategy':<30} {'final':>10} {'total':>8} {'per yr':>8} {'max DD':>8} {'fills':>6} {'fees':>8}")
    for row in rows:
        print(f"{row['strategy']:<30} {row['final']:>10,.0f} {row['total_pct']:>7.1f}% {row['per_year_pct']:>7.1f}% "
              f"{row['max_dd_pct']:>7.1f}% {row['trades']:>6} {row['fees']:>8,.0f}")
    notes = [(r["strategy"], r["note"]) for r in rows if r["note"]]
    if notes:
        print()
        for name, note in notes:
            print(f"  {name}: {note}")

    years = sorted({y for r in results for y in yearly_returns(r)})
    print("\nReturn per calendar year (first/last year partial):")
    print(f"{'strategy':<30} " + " ".join(f"{y:>8}" for y in years))
    for r in results:
        yr = yearly_returns(r)
        print(f"{r.name:<30} " + " ".join(f"{yr[y]:>7.1f}%" if y in yr else f"{'-':>8}" for y in years))

    os.makedirs("logs", exist_ok=True)
    pd.DataFrame({r.name: r.equity for r in results}).to_csv("logs/strategy_comparison.csv")
    print("\nDaily equity curves saved to logs/strategy_comparison.csv")
    print("Past performance says little about the future — each strategy wins in a different market phase. "
          "Not financial advice.")


if __name__ == "__main__":
    main()
