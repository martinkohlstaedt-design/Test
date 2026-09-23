"""CLI: show current and recent funding rates for several coins, as an
annualized percentage, so you can see where (and whether) funding-rate
arbitrage currently pays anything.

Example:
    python run_funding_monitor.py --exchange binance --symbols BTC/USDT ETH/USDT SOL/USDT
"""
from __future__ import annotations

import argparse
import time

import pandas as pd

from funding_data import annualize, fetch_current_funding, fetch_funding_history, infer_interval_hours

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "XRP/USDT", "SOL/USDT", "DOGE/USDT"]


def fmt_pct(value) -> str:
    return "     n/a" if value is None else f"{value:7.1f}%"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="binance",
                        help="ccxt exchange id with perpetual futures, e.g. binance, okx, krakenfutures, hyperliquid")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help="Spot pairs (mapped to the matching perpetual) or perp symbols like BTC/USDT:USDT")
    parser.add_argument("--days", type=int, default=30, help="History window for the averages")
    args = parser.parse_args()

    since_ms = int((time.time() - args.days * 86400) * 1000)
    rows = []
    for symbol in args.symbols:
        try:
            hist, perp = fetch_funding_history(args.exchange, symbol, since_ms)
        except Exception as exc:  # one bad symbol shouldn't kill the whole table
            print(f"{symbol}: skipped ({exc})")
            continue
        interval_h = infer_interval_hours(hist.index)
        rates = hist["funding_rate"]
        last_7d = rates[rates.index >= rates.index[-1] - pd.Timedelta(days=7)]
        try:
            current = fetch_current_funding(args.exchange, perp)["rate"]
        except Exception:
            current = None
        rows.append({
            "symbol": perp,
            "interval": f"{interval_h:g}h",
            "current": annualize(current, interval_h) if current is not None else None,
            "avg_7d": annualize(last_7d.mean(), interval_h),
            "avg_full": annualize(rates.mean(), interval_h),
            "positive": (rates > 0).mean() * 100,
        })

    if not rows:
        print("No funding data fetched.")
        return

    rows.sort(key=lambda r: r["avg_full"], reverse=True)
    print(f"\nFunding rates on {args.exchange} — annualized (APR), what a SHORT receives if positive")
    print(f"{'symbol':<18} {'every':>5} {'current':>8} {'7d avg':>8} {f'{args.days}d avg':>8} {'% positive':>11}")
    for r in rows:
        print(f"{r['symbol']:<18} {r['interval']:>5} {fmt_pct(r['current'])} {fmt_pct(r['avg_7d'])} "
              f"{fmt_pct(r['avg_full'])} {r['positive']:10.0f}%")
    print("\nWith 1x leverage only about HALF your capital is in the short, so your return on total")
    print("capital is roughly half these numbers, minus fees. See README 'Funding-rate arbitrage'.")


if __name__ == "__main__":
    main()
