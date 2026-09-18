"""Historical + live OHLCV fetching via ccxt (exchange-agnostic).

Works with any exchange ccxt supports (binance, kraken, coinbase, ...) purely
from its public market-data endpoints — no API key needed for this part,
even when the bot itself later trades live on that exchange.
"""
from __future__ import annotations

import time

import ccxt
import pandas as pd


def get_exchange(exchange_id: str) -> ccxt.Exchange:
    if not hasattr(ccxt, exchange_id):
        raise ValueError(f"ccxt has no exchange named '{exchange_id}'. See ccxt.exchanges for the full list.")
    return getattr(ccxt, exchange_id)({"enableRateLimit": True})


def fetch_ohlcv(exchange_id: str, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Returns a DataFrame indexed by UTC timestamp with columns
    open/high/low/close/volume, oldest row first."""
    exchange = get_exchange(exchange_id)
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    return df


def fetch_ohlcv_full_history(
    exchange_id: str, symbol: str, timeframe: str = "1d", since_ms: int | None = None, page_limit: int = 1000
) -> pd.DataFrame:
    """Pages through an exchange's history (for backtesting), starting at
    `since_ms` (epoch milliseconds) or the earliest data the exchange has."""
    exchange = get_exchange(exchange_id)
    all_rows: list[list[float]] = []
    since = since_ms
    while True:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=page_limit)
        if not batch:
            break
        all_rows.extend(batch)
        last_ts = batch[-1][0]
        if since is not None and last_ts <= since:
            break
        since = last_ts + 1
        if len(batch) < page_limit:
            break
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp")


def fetch_current_price(exchange_id: str, symbol: str) -> float:
    exchange = get_exchange(exchange_id)
    ticker = exchange.fetch_ticker(symbol)
    return float(ticker["last"])
