"""Intraday bar loading: Alpaca market data (free paper account), CSV import,
and a synthetic random-walk generator used only to test the machinery.

All frames are regular-session bars (09:30-16:00 America/New_York) with
columns open/high/low/close/volume and a tz-aware New York DatetimeIndex.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

NY = "America/New_York"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ALPACA_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[["open", "high", "low", "close", "volume"]].astype(float).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df.index = df.index.tz_convert(NY)
    t = df.index.time
    return df[(t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())]


def cache_path(symbol: str, timeframe: str) -> Path:
    return DATA_DIR / f"{symbol.upper()}_{timeframe}.csv"


def load_csv(path: str | Path) -> pd.DataFrame:
    """CSV with a timestamp column (any tz-aware or naive-UTC format) plus
    open/high/low/close/volume. Column names are matched case-insensitively."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    ts_col = next(c for c in ("timestamp", "datetime", "date", "time", "t") if c in df.columns)
    df.index = pd.to_datetime(df[ts_col], utc=True)
    return _clean(df)


def load_symbol(symbol: str, timeframe: str = "5Min") -> pd.DataFrame:
    p = cache_path(symbol, timeframe)
    if not p.exists():
        raise FileNotFoundError(f"{p} missing - run `python -m daytrade.download` or put a CSV there.")
    return load_csv(p)


def fetch_alpaca(symbol: str, start: str, end: str, timeframe: str = "5Min", feed: str = "iex") -> pd.DataFrame:
    """Download bars from Alpaca (free tier: feed='iex'). Credentials come from
    ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY in the environment (.env)."""
    key, secret = os.environ.get("ALPACA_API_KEY_ID"), os.environ.get("ALPACA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY (trading-bot/.env).")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    params = {"timeframe": timeframe, "start": start, "end": end, "limit": 10000,
              "adjustment": "all", "feed": feed, "sort": "asc"}
    rows: list[dict] = []
    while True:
        r = requests.get(ALPACA_URL.format(symbol=symbol), headers=headers, params=params, timeout=30)
        r.raise_for_status()
        body = r.json()
        rows.extend(body.get("bars") or [])
        token = body.get("next_page_token")
        if not token:
            break
        params["page_token"] = token
        time.sleep(0.3)
    if not rows:
        raise RuntimeError(f"No bars returned for {symbol}.")
    df = pd.DataFrame(rows).rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                            "l": "low", "c": "close", "v": "volume"})
    df.index = pd.to_datetime(df["timestamp"], utc=True)
    return _clean(df)


def synthetic(days: int = 120, bar_minutes: int = 5, seed: int = 0, daily_vol: float = 0.012,
              start: str = "2023-01-02") -> pd.DataFrame:
    """Pure random walk with a U-shaped volume profile. By construction it has
    NO exploitable edge, so any strategy should lose money to costs here -
    a built-in sanity check against look-ahead bugs."""
    rng = np.random.default_rng(seed)
    bars = 390 // bar_minutes
    frames, price = [], 100.0
    for d in pd.bdate_range(start, periods=days, tz=NY):
        idx = d + pd.Timedelta(hours=9, minutes=30) + pd.to_timedelta(np.arange(bars) * bar_minutes, unit="m")
        rets = rng.normal(0, daily_vol / np.sqrt(bars), bars)
        closes = price * np.exp(np.cumsum(rets))
        opens = np.concatenate([[price], closes[:-1]])
        spread = np.abs(rng.normal(0, daily_vol / np.sqrt(bars), bars)) * price * 0.5
        x = np.linspace(-1, 1, bars)
        vol = (1 + 2.5 * x**2) * 1e5 * rng.lognormal(0, 0.3, bars)
        frames.append(pd.DataFrame({"open": opens, "high": np.maximum(opens, closes) + spread,
                                    "low": np.minimum(opens, closes) - spread, "close": closes,
                                    "volume": vol}, index=idx))
        price = closes[-1]
    return pd.concat(frames)


def fetch_daily(symbol: str, start: str, end: str, feed: str = "sip") -> pd.DataFrame:
    """Split/dividend-adjusted daily bars (index = trading date, tz-naive)."""
    key, secret = os.environ.get("ALPACA_API_KEY_ID"), os.environ.get("ALPACA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY (trading-bot/.env).")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    params = {"timeframe": "1Day", "start": start, "end": end, "limit": 10000,
              "adjustment": "all", "feed": feed, "sort": "asc"}
    rows: list[dict] = []
    while True:
        r = requests.get(ALPACA_URL.format(symbol=symbol), headers=headers, params=params, timeout=30)
        r.raise_for_status()
        body = r.json()
        rows.extend(body.get("bars") or [])
        if not body.get("next_page_token"):
            break
        params["page_token"] = body["next_page_token"]
    if not rows:
        raise RuntimeError(f"No daily bars for {symbol}.")
    df = pd.DataFrame(rows).rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                            "l": "low", "c": "close", "v": "volume"})
    df.index = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(NY).dt.tz_localize(None).dt.normalize()
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def load_daily(symbol: str) -> pd.DataFrame:
    p = cache_path(symbol, "1Day")
    if not p.exists():
        raise FileNotFoundError(f"{p} missing - run `python -m daytrade.download_daily`.")
    return pd.read_csv(p, index_col=0, parse_dates=True)
