"""Runs a SignalEngine + RiskManager over historical OHLCV data using the
same PaperBroker the live paper-trading loop uses, so backtest and live
paper trading share the exact fill/fee/risk logic — no separate "backtest
only" code path to drift out of sync.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from broker import PaperBroker
from risk_manager import RiskManager
from signal_engine import SignalEngine

TIMEFRAME_PERIODS_PER_YEAR = {
    "1h": 365 * 24, "4h": 365 * 6, "1d": 365, "1w": 52,
}


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: list
    metrics: dict = field(default_factory=dict)


def run_backtest(
    df: pd.DataFrame,
    signal_engine: SignalEngine,
    risk_manager: RiskManager,
    symbol: str = "ASSET",
    initial_balance: float = 10_000.0,
    fee_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    timeframe: str = "1d",
    warmup: int = 200,
    trade_start_index: int | None = None,
) -> BacktestResult:
    """`warmup` rows are always excluded from trading (indicators like SMA200
    need that much lead-in to be meaningful). `trade_start_index`, if given,
    pushes the "trading allowed" point further out — e.g. to mark a
    train/test split — while indicators still see every prior row as lead-in.
    Metrics are computed only from `trade_start_index` (or `warmup`) onward,
    so an untraded warmup/training prefix can't dilute the reported numbers.
    """
    prepared = signal_engine.prepare(df)
    broker = PaperBroker(initial_balance, fee_pct=fee_pct, slippage_pct=slippage_pct,
                         log_path="logs/backtest_trades.jsonl")

    trade_start_index = max(warmup, trade_start_index) if trade_start_index is not None else warmup

    equity_points: list[tuple] = []
    day_anchor = None
    start_of_day_equity = initial_balance
    halted_today = False

    for i in range(len(prepared)):
        row = prepared.iloc[i]
        price = row["close"]
        ts = prepared.index[i]

        current_day = ts.floor("D") if hasattr(ts, "floor") else None
        if current_day != day_anchor:
            day_anchor = current_day
            start_of_day_equity = broker.equity({symbol: price})
            halted_today = False

        if i < trade_start_index:
            equity_points.append((ts, broker.equity({symbol: price})))
            continue

        pos = broker.get_position(symbol)

        if pos.is_open:
            exit_reason = risk_manager.check_exit(pos.entry_price, price)
            if exit_reason:
                broker.place_order(symbol, "sell", pos.amount, price, reason=exit_reason, timestamp=ts.timestamp())
                pos = broker.get_position(symbol)

        if not halted_today and risk_manager.kill_switch_triggered(start_of_day_equity, broker.equity({symbol: price})):
            halted_today = True

        signal = signal_engine.evaluate(prepared, index=i)

        if not halted_today:
            if not pos.is_open and signal.label in ("BUY", "STRONG_BUY"):
                amount = risk_manager.position_size(broker.get_balance(), price)
                if amount > 0:
                    broker.place_order(symbol, "buy", amount, price, reason=signal.label, timestamp=ts.timestamp())
            elif pos.is_open and signal.label in ("SELL", "STRONG_SELL"):
                broker.place_order(symbol, "sell", pos.amount, price, reason=signal.label, timestamp=ts.timestamp())

        equity_points.append((ts, broker.equity({symbol: price})))

    equity_curve = pd.Series(dict(equity_points))
    scoring_curve = equity_curve.iloc[trade_start_index:]
    scoring_baseline = equity_curve.iloc[trade_start_index] if len(scoring_curve) else initial_balance
    scoring_start_ts = prepared.index[trade_start_index] if trade_start_index < len(prepared) else prepared.index[-1]
    scoring_trades = [t for t in broker.trades if t.timestamp >= scoring_start_ts.timestamp()]
    metrics = compute_metrics(scoring_curve, scoring_trades, scoring_baseline, timeframe)
    return BacktestResult(equity_curve=equity_curve, trades=broker.trades, metrics=metrics)


def compute_metrics(equity_curve: pd.Series, trades: list, initial_balance: float, timeframe: str) -> dict:
    final_equity = equity_curve.iloc[-1] if len(equity_curve) else initial_balance
    total_return_pct = (final_equity / initial_balance - 1) * 100

    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    max_drawdown_pct = abs(drawdown.min()) * 100 if len(drawdown) else 0.0

    returns = equity_curve.pct_change().dropna()
    periods_per_year = TIMEFRAME_PERIODS_PER_YEAR.get(timeframe, 365)
    sharpe = 0.0
    if returns.std() > 0:
        sharpe = (returns.mean() / returns.std()) * np.sqrt(periods_per_year)

    round_trips = _pair_trades(trades)
    wins = [rt for rt in round_trips if rt > 0]
    win_rate = (len(wins) / len(round_trips) * 100) if round_trips else 0.0

    return {
        "initial_balance": initial_balance,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "sharpe_ratio": round(sharpe, 2),
        "num_trades": len(trades),
        "num_round_trips": len(round_trips),
        "win_rate_pct": round(win_rate, 1),
    }


def _pair_trades(trades: list) -> list[float]:
    """Matches buy->sell pairs (FIFO, one open position per symbol at a time
    in this simple engine) and returns each round trip's PnL in quote currency."""
    pnls = []
    open_buy = None
    for t in trades:
        if t.side == "buy":
            open_buy = t
        elif t.side == "sell" and open_buy is not None:
            pnl = (t.price - open_buy.price) * t.amount - t.fee - open_buy.fee
            pnls.append(pnl)
            open_buy = None
    return pnls
