"""Grid search over SignalEngine parameters, scored by backtest performance.

This is deliberately a plain grid search, not a fancy optimizer: with only a
handful of parameters it is fast enough, and — more importantly — its
exhaustive, transparent nature makes it easy to see exactly what was tried.

IMPORTANT — overfitting risk: searching for the parameters that would have
performed best on a fixed historical window will always find *something*
that looks great on that window, whether or not it generalizes. Always:
  1) Split your data into a training period (for the search) and a held-out
     test period (to check the winning params on data they never saw), and
  2) Treat a walk-forward re-optimization schedule as the real goal, not a
     single one-off search.
run_walk_forward() below does a minimal version of that split for you.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import pandas as pd

from backtester import run_backtest
from risk_manager import RiskManager
from signal_engine import DEFAULT_PARAMS, SignalEngine

# A conservative default search space: the thresholds/weights most likely to
# matter, each varied around its default. Extend this dict to search more.
DEFAULT_PARAM_GRID: dict[str, list[Any]] = {
    "rsi_oversold": [25, 30, 35],
    "rsi_overbought": [65, 70, 75],
    "weight_golden_death_cross": [2, 3, 4],
    "score_buy": [2, 3, 4],
    "score_sell": [-2, -3, -4],
}


@dataclass
class OptimizationRun:
    params: dict
    metrics: dict


def grid_search(
    df: pd.DataFrame,
    param_grid: dict[str, list[Any]] = None,
    base_params: dict[str, Any] = None,
    risk_manager: RiskManager = None,
    symbol: str = "ASSET",
    initial_balance: float = 10_000.0,
    timeframe: str = "1d",
    metric: str = "sharpe_ratio",
) -> tuple[dict, list[OptimizationRun]]:
    param_grid = param_grid or DEFAULT_PARAM_GRID
    base_params = {**DEFAULT_PARAMS, **(base_params or {})}
    risk_manager = risk_manager or RiskManager()

    keys = list(param_grid.keys())
    combos = list(itertools.product(*[param_grid[k] for k in keys]))

    runs: list[OptimizationRun] = []
    for combo in combos:
        params = {**base_params, **dict(zip(keys, combo))}
        engine = SignalEngine(params)
        result = run_backtest(df, engine, risk_manager, symbol=symbol,
                              initial_balance=initial_balance, timeframe=timeframe)
        runs.append(OptimizationRun(params=params, metrics=result.metrics))

    runs.sort(key=lambda r: r.metrics.get(metric, float("-inf")), reverse=True)
    best_params = runs[0].params if runs else base_params
    return best_params, runs


def run_walk_forward(
    df: pd.DataFrame,
    param_grid: dict[str, list[Any]] = None,
    train_frac: float = 0.6,
    **kwargs,
) -> dict:
    """Splits df into a training window (used to pick params) and a held-out
    test window (used only to report how those params actually did). This is
    the minimum needed to catch a search that just memorized the training
    data; it is NOT a substitute for re-running this periodically as new
    data comes in (true walk-forward re-optimization)."""
    split = int(len(df) * train_frac)
    train_df = df.iloc[:split]

    best_params, train_runs = grid_search(train_df, param_grid, **kwargs)

    # Re-run on the FULL series (train history as indicator lead-in) but only
    # start trading — and only score — from the split point onward, so the
    # test metrics reflect genuinely unseen data rather than a fresh, mostly
    # untraded warmup window.
    engine = SignalEngine(best_params)
    risk_manager = kwargs.get("risk_manager") or RiskManager()
    test_result = run_backtest(
        df, engine, risk_manager,
        symbol=kwargs.get("symbol", "ASSET"),
        initial_balance=kwargs.get("initial_balance", 10_000.0),
        timeframe=kwargs.get("timeframe", "1d"),
        trade_start_index=split,
    )

    return {
        "best_params": best_params,
        "train_metrics": train_runs[0].metrics if train_runs else None,
        "test_metrics": test_result.metrics,
        "train_size": len(train_df),
        "test_size": len(df) - split,
    }
