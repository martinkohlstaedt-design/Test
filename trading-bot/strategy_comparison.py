"""Runs several crypto strategies over the SAME price history with the SAME
starting capital, so they can be compared on equal terms instead of each
tool's own marketing backtest.

Strategies:
  - buy_and_hold:    buy everything on day one, never sell.
  - dca:             split the capital into equal weekly buys over the whole
                     period (uninvested cash earns nothing meanwhile).
  - indicator_bot:   this repo's SignalEngine + RiskManager (backtester.py),
                     on daily candles, sized to use the whole balance.
  - grid_bot:        classic spot grid in a fixed price band around the
                     starting price, simulated on hourly candles.
  - funding_carry:   long spot + short perp (funding_backtest.py), if the
                     exchange has perpetuals and funding history.

Every strategy pays the same fee + slippage per fill.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtester import run_backtest
from risk_manager import RiskManager
from signal_engine import SignalEngine


@dataclass
class StrategyResult:
    name: str
    equity: pd.Series                     # indexed by timestamp, in quote currency
    trades: int = 0
    fees: float = 0.0
    note: str = ""
    extra: dict = field(default_factory=dict)


def buy_and_hold(prices: pd.DataFrame, capital: float, fee_pct: float) -> StrategyResult:
    close = prices["close"]
    qty = capital * (1 - fee_pct) / close.iloc[0]
    return StrategyResult("Buy & Hold", qty * close, trades=1, fees=capital * fee_pct)


def dca(prices: pd.DataFrame, capital: float, fee_pct: float, every: str = "7D") -> StrategyResult:
    close = prices["close"]
    buy_times = pd.date_range(close.index[0], close.index[-1], freq=every)
    buy_idx = sorted(set(close.index.searchsorted(buy_times)))
    per_buy = capital / len(buy_idx)
    cash, qty, fees = capital, 0.0, 0.0
    buys = set(buy_idx)
    values = np.empty(len(close))
    for i, price in enumerate(close.to_numpy()):
        if i in buys:
            spend = min(per_buy, cash)
            qty += spend * (1 - fee_pct) / price
            fees += spend * fee_pct
            cash -= spend
        values[i] = cash + qty * price
    return StrategyResult(f"DCA ({every.replace('7D', 'weekly')})", pd.Series(values, index=close.index),
                          trades=len(buy_idx), fees=fees)


def indicator_bot(daily_with_leadin: pd.DataFrame, start, capital: float, fee_pct: float,
                  slippage_pct: float, params: dict | None = None) -> StrategyResult:
    """`daily_with_leadin` must include ~200 days BEFORE `start`, so the
    long moving averages are warmed up by the time the comparison begins."""
    trade_start = int(daily_with_leadin.index.searchsorted(start))
    risk = RiskManager(max_position_pct=0.99)  # whole balance, like the other strategies
    result = run_backtest(daily_with_leadin, SignalEngine(params), risk, symbol="ASSET",
                          initial_balance=capital, fee_pct=fee_pct, slippage_pct=slippage_pct,
                          timeframe="1d", warmup=min(200, trade_start), trade_start_index=trade_start)
    equity = result.equity_curve.iloc[trade_start:]
    equity = equity / equity.iloc[0] * capital
    trades = [t for t in result.trades if t.timestamp >= start.timestamp()]
    return StrategyResult("Indicator bot (RSI/MACD/...)", equity, trades=len(trades),
                          fees=float(sum(t.fee for t in trades)),
                          note="stop-loss 5% / take-profit 10% (RiskManager defaults)")


def grid_bot(prices: pd.DataFrame, capital: float, fee_pct: float, range_pct: float = 0.30,
             grids: int = 20) -> StrategyResult:
    """Spot grid between start*(1-range) and start*(1+range), geometric
    levels, never re-centered. Each grid cell either holds coins waiting to
    sell one level up, or cash waiting to buy at its lower level. A cell can
    flip at most once per candle (the order of high/low inside a candle is
    unknown, so assuming more round trips would flatter the grid)."""
    p0 = float(prices["open"].iloc[0])
    levels = np.geomspace(p0 * (1 - range_pct), p0 * (1 + range_pct), grids + 1)
    per_cell = capital / grids
    cash, fees, fills = capital, 0.0, 0
    holding = np.zeros(grids)  # coin qty per cell, 0 = waiting to buy

    # Cells entirely above the start price start out holding coin (bought now).
    for k in range(grids):
        if levels[k] >= p0:
            qty = per_cell * (1 - fee_pct) / p0
            holding[k] = qty
            cash -= per_cell
            fees += per_cell * fee_pct
            fills += 1

    values = np.empty(len(prices))
    lows, highs, closes = prices["low"].to_numpy(), prices["high"].to_numpy(), prices["close"].to_numpy()
    grid_profit = 0.0
    for i in range(len(prices)):
        flipped = np.zeros(grids, dtype=bool)
        for k in range(grids):
            if holding[k] == 0 and lows[i] <= levels[k] and cash >= per_cell * 0.5:
                spend = min(per_cell, cash)
                holding[k] = spend * (1 - fee_pct) / levels[k]
                cash -= spend
                fees += spend * fee_pct
                fills += 1
                flipped[k] = True
        for k in range(grids):
            if holding[k] > 0 and not flipped[k] and highs[i] >= levels[k + 1]:
                proceeds = holding[k] * levels[k + 1]
                cash += proceeds * (1 - fee_pct)
                fees += proceeds * fee_pct
                grid_profit += proceeds * (1 - fee_pct) - per_cell
                holding[k] = 0.0
                fills += 1
        values[i] = cash + holding.sum() * closes[i]

    below = float(closes[-1]) < levels[0]
    above = float(closes[-1]) > levels[-1]
    note = f"band {levels[0]:,.0f}-{levels[-1]:,.0f}, {grids} grids"
    if below or above:
        note += f"; price ended {'BELOW' if below else 'ABOVE'} the band"
    return StrategyResult(f"Grid bot (+/-{range_pct:.0%})", pd.Series(values, index=prices.index),
                          trades=fills, fees=fees, note=note)


def summarize(result: StrategyResult, capital: float) -> dict:
    eq = result.equity
    days = max((eq.index[-1] - eq.index[0]).total_seconds() / 86400, 1)
    total = eq.iloc[-1] / capital - 1
    cagr = (eq.iloc[-1] / capital) ** (365 / days) - 1 if eq.iloc[-1] > 0 else -1.0
    dd = float(((eq - eq.cummax()) / eq.cummax()).min())
    return {
        "strategy": result.name,
        "final": float(eq.iloc[-1]),
        "total_pct": float(total) * 100,
        "per_year_pct": float(cagr) * 100,
        "max_dd_pct": dd * 100,
        "trades": result.trades,
        "fees": result.fees,
        "note": result.note,
    }


def yearly_returns(result: StrategyResult) -> dict[int, float]:
    """Return per calendar year (partial years at the edges included)."""
    eq = result.equity
    out = {}
    for year, chunk in eq.groupby(eq.index.year):
        prev = eq[eq.index < chunk.index[0]]
        start_val = prev.iloc[-1] if len(prev) else chunk.iloc[0]
        out[int(year)] = float(chunk.iloc[-1] / start_val - 1) * 100
    return out
