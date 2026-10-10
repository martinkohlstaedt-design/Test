"""Cost-aware, flat-by-close simulation and performance metrics.

Position sizing: risk `risk_pct` of equity per trade (distance entry->stop),
capped at `max_leverage` x equity per trade and per day in total. Because
sizing is a fraction of equity, a trade's account return is simply
position_fraction x net price return - no equity state is needed per trade.
If stop and target are both touched inside one bar, the STOP is assumed to
have hit first (pessimistic).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import Day
from .strategies import STRATEGIES, Setup


@dataclass
class Costs:
    slippage_bps: float = 2.0       # per side, applied against you on every fill
    commission_bps: float = 0.0     # per side (Alpaca stocks: 0)
    risk_pct: float = 0.005         # equity risked per trade (0.5 %)
    max_leverage: float = 2.0       # max gross exposure as multiple of equity (per day)


def simulate_trade(day: Day, s: Setup, costs: Costs) -> dict | None:
    slip = costs.slippage_bps / 1e4
    entry = day.o[s.entry_i] * (1 + s.side * slip)
    if (entry - s.stop) * s.side <= 0 or (s.target - entry) * s.side <= 0:
        return None            # gapped through stop/target at the fill
    exit_px, reason, exit_i = day.c[-1], "eod", day.n - 1
    for j in range(s.entry_i, day.n):
        if s.side > 0:
            if day.l[j] <= s.stop:
                exit_px, reason, exit_i = min(s.stop, day.o[j]) if j > s.entry_i else s.stop, "stop", j
                break
            if day.h[j] >= s.target:
                exit_px, reason, exit_i = s.target, "target", j
                break
        else:
            if day.h[j] >= s.stop:
                exit_px, reason, exit_i = max(s.stop, day.o[j]) if j > s.entry_i else s.stop, "stop", j
                break
            if day.l[j] <= s.target:
                exit_px, reason, exit_i = s.target, "target", j
                break
    exit_px *= 1 - s.side * slip
    ret = s.side * (exit_px - entry) / entry - 2 * costs.commission_bps / 1e4
    stop_dist = abs(entry - s.stop) / entry
    pos_frac = min(costs.risk_pct / stop_dist, costs.max_leverage)
    return {"date": day.date, "symbol": day.symbol, "side": s.side, "entry_i": s.entry_i,
            "exit_i": exit_i, "reason": reason, "ret": ret, "pos_frac": pos_frac,
            "r": ret / stop_dist}


def run(days_by_symbol: dict[str, list[Day]], strategy: str, params: dict, costs: Costs,
        date_filter=None) -> pd.DataFrame:
    fn = STRATEGIES[strategy]
    rows = []
    for days in days_by_symbol.values():
        for d in days:
            if date_filter is not None and not date_filter(d.date):
                continue
            s = fn(d, params)
            if s is None:
                continue
            t = simulate_trade(d, s, costs)
            if t:
                rows.append(t)
    return pd.DataFrame(rows)


def daily_returns(trades: pd.DataFrame, all_dates: pd.DatetimeIndex, costs: Costs) -> pd.Series:
    """Portfolio return per trading day (0 on days without trades). If the
    day's combined exposure exceeds max_leverage, positions are scaled down."""
    out = pd.Series(0.0, index=all_dates)
    if trades.empty:
        return out
    t = trades.copy()
    expo = t.groupby("date")["pos_frac"].transform("sum")
    t["scale"] = np.minimum(1.0, costs.max_leverage / expo)
    t["contrib"] = t["ret"] * t["pos_frac"] * t["scale"]
    return out.add(t.groupby("date")["contrib"].sum(), fill_value=0.0)


def metrics(trades: pd.DataFrame, all_dates: pd.DatetimeIndex, costs: Costs) -> dict:
    dr = daily_returns(trades, all_dates, costs)
    eq = (1 + dr).cumprod()
    n_days = max(len(dr), 1)
    sharpe = dr.mean() / dr.std() * np.sqrt(252) if dr.std() > 0 else 0.0
    wins = trades[trades["ret"] > 0] if not trades.empty else trades
    gp = (trades["ret"] * trades["pos_frac"])[trades["ret"] > 0].sum() if not trades.empty else 0.0
    gl = -(trades["ret"] * trades["pos_frac"])[trades["ret"] <= 0].sum() if not trades.empty else 0.0
    return {
        "trades": int(len(trades)),
        "trades_per_day": round(len(trades) / n_days, 2),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1) if len(trades) else 0.0,
        "avg_R": round(float(trades["r"].mean()), 3) if len(trades) else 0.0,
        "profit_factor": round(float(gp / gl), 2) if gl > 0 else (float("inf") if gp > 0 else 0.0),
        "total_return_pct": round(float((eq.iloc[-1] - 1) * 100), 2),
        "annual_return_pct": round(float((eq.iloc[-1] ** (252 / n_days) - 1) * 100), 2),
        "max_drawdown_pct": round(float(abs((eq / eq.cummax() - 1).min()) * 100), 2),
        "sharpe": round(float(sharpe), 2),
    }
