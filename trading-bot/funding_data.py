"""Funding-rate data for perpetual futures via ccxt (public endpoints, no API
key needed).

Every exchange reports funding differently (Binance/OKX every 8h, Kraken
Futures and Hyperliquid every hour, ...). ccxt already normalizes each rate
to a relative rate per funding period; this module adds what the funding
monitor and backtester need on top: full-history paging, perp-symbol lookup
from a spot pair, and period-length detection so rates from different
exchanges can be compared as an annualized percentage.

Note: exchanges keep very different amounts of funding history — Binance,
Kraken Futures and Hyperliquid go back years, OKX/Bitget/KuCoin only a few
months. A backtest can only cover what the exchange returns.
"""
from __future__ import annotations

import time

import ccxt
import pandas as pd

from data_feed import get_exchange

HOURS_PER_YEAR = 365 * 24


def resolve_perp_symbol(exchange, symbol: str) -> str:
    """Maps a spot pair like 'BTC/USDT' to the exchange's linear perpetual
    ('BTC/USDT:USDT'). Symbols that already contain ':' are returned as-is.
    Falls back to any perpetual with the same base asset (e.g. Kraken
    Futures only lists 'BTC/USD:USD', Hyperliquid 'BTC/USDC:USDC')."""
    exchange.load_markets()
    if ":" in symbol:
        if symbol not in exchange.markets:
            raise ValueError(f"{exchange.id} has no market '{symbol}'")
        return symbol

    base, quote = symbol.split("/")
    direct = f"{symbol}:{quote}"
    if direct in exchange.markets and exchange.markets[direct].get("swap"):
        return direct

    candidates = [
        m["symbol"] for m in exchange.markets.values()
        if m.get("swap") and m.get("base") == base and m.get("active", True) is not False
    ]
    linear = [s for s in candidates if exchange.markets[s].get("linear")]
    if linear or candidates:
        return sorted(linear or candidates)[0]
    raise ValueError(f"{exchange.id} has no perpetual futures market for {base}")


def infer_interval_hours(index: pd.DatetimeIndex) -> float:
    """Funding period length in hours, from the spacing of the timestamps."""
    if len(index) < 2:
        return 8.0
    diffs = pd.Series(index).diff().dropna().dt.total_seconds() / 3600
    # Round to 0.5h so millisecond jitter in timestamps doesn't matter.
    return max(0.5, round(float(diffs.median()) * 2) / 2)


def annualize(rate_per_period: float, interval_hours: float) -> float:
    """Simple (non-compounded) annualized percentage for a per-period rate."""
    return rate_per_period * (HOURS_PER_YEAR / interval_hours) * 100


def _with_retries(call, attempts: int = 5, base_delay: float = 2.0):
    """Retries rate-limit and network errors with exponential backoff —
    paging years of hourly funding data easily hits exchange rate limits."""
    for attempt in range(attempts):
        try:
            return call()
        except (ccxt.RateLimitExceeded, ccxt.NetworkError):
            if attempt == attempts - 1:
                raise
            time.sleep(base_delay * 2 ** attempt)


def _page_forward(fetch_page, since_ms: int, ts_of, max_pages: int = 10_000) -> list:
    """Generic forward pager: keeps asking for the next page after the last
    timestamp until the exchange returns nothing new. Doesn't assume a fixed
    page size, since exchanges cap page sizes differently."""
    rows: list = []
    since = since_ms
    now_ms = int(time.time() * 1000)
    for _ in range(max_pages):
        batch = _with_retries(lambda: fetch_page(since))
        if not batch:
            break
        new = [r for r in batch if ts_of(r) >= since]
        if not new:
            break
        rows.extend(new)
        last_ts = max(ts_of(r) for r in new)
        if last_ts <= since or last_ts >= now_ms:
            break
        since = last_ts + 1
    return rows


def fetch_funding_history(exchange_id: str, symbol: str, since_ms: int) -> tuple[pd.DataFrame, str]:
    """Returns (DataFrame indexed by UTC timestamp with a 'funding_rate'
    column, oldest first; the perp symbol actually used)."""
    exchange = get_exchange(exchange_id)
    perp = resolve_perp_symbol(exchange, symbol)
    rows = _page_forward(
        lambda since: exchange.fetch_funding_rate_history(perp, since=since),
        since_ms,
        ts_of=lambda r: r["timestamp"],
    )
    if not rows:
        raise RuntimeError(f"{exchange_id} returned no funding history for {perp}")
    df = pd.DataFrame({"timestamp": [r["timestamp"] for r in rows],
                       "funding_rate": [float(r["fundingRate"]) for r in rows]})
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp"), perp


def fetch_price_history(exchange_id: str, perp_symbol: str, since_ms: int, timeframe: str = "1h") -> pd.DataFrame:
    """OHLCV of the perpetual itself (on the same exchange as the funding
    data), used to value positions and check liquidation risk."""
    exchange = get_exchange(exchange_id)
    rows = _page_forward(
        lambda since: exchange.fetch_ohlcv(perp_symbol, timeframe=timeframe, since=since),
        since_ms,
        ts_of=lambda r: r[0],
    )
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp")


def fetch_current_funding(exchange_id: str, perp_symbol: str) -> dict:
    """The currently accruing (next) funding rate, if the exchange reports it."""
    exchange = get_exchange(exchange_id)
    info = exchange.fetch_funding_rate(perp_symbol)
    return {
        "rate": info.get("fundingRate"),
        "next_funding": info.get("fundingDatetime"),
        "interval": info.get("interval"),
    }
