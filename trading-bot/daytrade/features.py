"""Turns a raw intraday frame into per-day numpy bundles with the indicators
the strategies need. Every value at bar i uses only data up to and including
bar i's close (decisions are taken at bar close, fills happen at the NEXT
bar's open), and the daily trend / volume baselines use prior days only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Day:
    symbol: str
    date: pd.Timestamp
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    vwap: np.ndarray
    atr: np.ndarray       # ATR(14 bars), in price units
    rvol: np.ndarray      # volume / same-time-of-day average over prior 20 days
    trend: int            # +1 / -1: prior close above / below its 20-day SMA (0 = unknown)
    prev_close: float
    bar_minutes: int

    @property
    def n(self) -> int:
        return len(self.c)


def build_days(df: pd.DataFrame, symbol: str, atr_len: int = 14, rvol_days: int = 20,
               trend_len: int = 20, min_bars_frac: float = 0.9) -> list[Day]:
    df = df.copy()
    bar_minutes = int(round(df.index.to_series().diff().dt.total_seconds().median() / 60))
    full_bars = 390 // bar_minutes
    dates = df.index.normalize()
    df["date"] = dates

    tp = (df["high"] + df["low"] + df["close"]) / 3
    pv = (tp * df["volume"]).groupby(dates).cumsum()
    cv = df["volume"].groupby(dates).cumsum().replace(0, np.nan)
    df["vwap"] = (pv / cv).fillna(df["close"])

    prev_c = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(atr_len, min_periods=atr_len // 2).mean()

    tod = df.index.strftime("%H:%M")
    base = df.groupby(tod)["volume"].transform(lambda s: s.shift(1).rolling(rvol_days, min_periods=5).mean())
    df["rvol"] = (df["volume"] / base).replace([np.inf, -np.inf], np.nan)

    daily_close = df.groupby("date")["close"].last()
    sma = daily_close.rolling(trend_len, min_periods=trend_len).mean()
    trend = np.sign(daily_close - sma).fillna(0).astype(int)  # known at that day's close -> use next day

    days: list[Day] = []
    dc_vals = daily_close.shift(1)
    tr_vals = trend.shift(1).fillna(0).astype(int)
    for date, g in df.groupby("date"):
        if len(g) < full_bars * min_bars_frac:   # skip half days / data gaps
            continue
        days.append(Day(
            symbol=symbol, date=date, o=g["open"].to_numpy(), h=g["high"].to_numpy(),
            l=g["low"].to_numpy(), c=g["close"].to_numpy(), v=g["volume"].to_numpy(),
            vwap=g["vwap"].to_numpy(), atr=g["atr"].to_numpy(),
            rvol=g["rvol"].fillna(1.0).to_numpy(), trend=int(tr_vals.loc[date]),
            prev_close=float(dc_vals.loc[date]) if not np.isnan(dc_vals.loc[date]) else float(g["open"].iloc[0]),
            bar_minutes=bar_minutes))
    return days
