"""Vectorized technical indicators on pandas Series/DataFrames.

Mirrors the logic used in the crypto-dashboard's indicators.js, but as a
Python/pandas port so it can run inside the bot's backtester and live loop.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """EMA seeded with a plain SMA of the first `period` values (the classic
    MACD convention, and what the crypto-dashboard's JS indicators use) rather
    than pandas' default of recursing from the very first data point."""
    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) < period:
        return pd.Series(out, index=series.index)
    k = 2 / (period + 1)
    out[period - 1] = values[:period].mean()
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return pd.Series(out, index=series.index)


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's smoothed RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    # Wilder's formula divides by zero when avg_loss is 0 (pure uptrend) -> RSI should be 100,
    # and 0/0 (flat series) -> RSI should be 50.
    result = result.where(avg_loss != 0, np.where(avg_gain == 0, 50.0, 100.0))
    return result


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow

    signal_line = pd.Series(np.nan, index=series.index)
    valid = macd_line.dropna()
    if len(valid) >= signal:
        signal_line.loc[valid.index] = ema(valid, signal).to_numpy()

    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def bollinger_bands(series: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    middle = sma(series, period)
    std = series.rolling(window=period, min_periods=period).std(ddof=0)
    upper = middle + std_mult * std
    lower = middle - std_mult * std
    percent_b = (series - lower) / (upper - lower)
    percent_b = percent_b.where((upper - lower) != 0, 0.5)
    return pd.DataFrame({"middle": middle, "upper": upper, "lower": lower, "percent_b": percent_b})


def stochastic_rsi(
    series: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> pd.DataFrame:
    rsi_vals = rsi(series, rsi_period)
    lowest = rsi_vals.rolling(window=stoch_period, min_periods=stoch_period).min()
    highest = rsi_vals.rolling(window=stoch_period, min_periods=stoch_period).max()
    raw_k = (rsi_vals - lowest) / (highest - lowest) * 100
    raw_k = raw_k.where((highest - lowest) != 0, 50.0)
    k = raw_k.rolling(window=k_smooth, min_periods=k_smooth).mean()
    d = k.rolling(window=d_smooth, min_periods=d_smooth).mean()
    return pd.DataFrame({"k": k, "d": d})


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).fillna(0).cumsum()


def detect_crossover(short_ma: pd.Series, long_ma: pd.Series) -> str | None:
    """Golden/death cross using the two most recent points where both are defined."""
    diff = (short_ma - long_ma).dropna()
    if len(diff) < 2:
        return None
    prev, curr = diff.iloc[-2], diff.iloc[-1]
    if prev <= 0 < curr:
        return "golden"
    if prev >= 0 > curr:
        return "death"
    return "above" if curr > 0 else "below"


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Takes a DataFrame with a 'close' column (and optionally 'volume'),
    returns a new DataFrame with every indicator as extra columns."""
    out = df.copy()
    out["sma20"] = sma(out["close"], 20)
    out["sma50"] = sma(out["close"], 50)
    out["sma200"] = sma(out["close"], 200)

    macd_df = macd(out["close"])
    out["macd"] = macd_df["macd"]
    out["macd_signal"] = macd_df["signal"]
    out["macd_hist"] = macd_df["histogram"]

    bb = bollinger_bands(out["close"])
    out["bb_upper"] = bb["upper"]
    out["bb_lower"] = bb["lower"]
    out["bb_percent_b"] = bb["percent_b"]

    out["rsi"] = rsi(out["close"])

    stoch = stochastic_rsi(out["close"])
    out["stoch_k"] = stoch["k"]
    out["stoch_d"] = stoch["d"]

    if "volume" in out.columns:
        out["obv"] = obv(out["close"], out["volume"])

    return out
