"""Grid search over SignalEngine (and, optionally, RiskManager) parameters,
scored by backtest performance.

This is deliberately a plain grid search, not a fancy optimizer: with only a
handful of parameters it is fast enough, and — more importantly — its
exhaustive, transparent nature makes it easy to see exactly what was tried.

IMPORTANT — overfitting risk: searching for the parameters that would have
performed best on a fixed historical window will always find *something*
that looks great on that window, whether or not it generalizes. Always:
  1) Split your data into a training period (for the search) and a held-out
     test period (to check the winning params on data they never saw), and
  2) Prefer run_rolling_walk_forward() over a single train/test split — one
     lucky/unlucky split can make a mediocre strategy look great or a decent
     one look terrible. Several folds give a far more honest picture.
No amount of parameter search turns a strategy with no real edge into a
profitable one — it only ever tells you what would have worked on the past.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import pandas as pd

from backtester import run_backtest
from risk_manager import RiskManager
from signal_engine import DEFAULT_PARAMS, SignalEngine

# RiskManager's own tunable fields — split out from signal-engine params so a
# grid entry for e.g. "stop_loss_pct" builds a fresh RiskManager per combo
# instead of being silently ignored by SignalEngine.
RISK_MANAGER_KEYS = {"max_position_pct", "stop_loss_pct", "take_profit_pct", "max_daily_loss_pct"}

# Kept intentionally small: this grid's size is multiplied by n_folds in
# run_rolling_walk_forward, and every combination runs a full backtest.
# 3*3*2*3*3 = 162 combos/fold — a few seconds to ~1 minute per fold depending
# on how much history you fetch. Add rsi_oversold/rsi_overbought/
# weight_golden_death_cross back in for a more thorough (much slower) search.
DEFAULT_PARAM_GRID: dict[str, list[Any]] = {
    "score_buy": [2, 3, 4],
    "score_sell": [-2, -3, -4],
    # Known lever for real profitability, not just trade count: does refusing
    # to buy against the long-term trend actually help on this asset?
    "require_uptrend_filter": [0, 1],
    # Exit discipline matters as much as entries — search it too.
    "stop_loss_pct": [0.03, 0.05, 0.08],
    "take_profit_pct": [0.05, 0.10, 0.15],
}


@dataclass
class OptimizationRun:
    params: dict
    metrics: dict


def split_engine_and_risk_params(params: dict, base_risk: RiskManager) -> tuple[dict, RiskManager]:
    """Pulls any RiskManager-owned keys out of a combined param dict, building
    a RiskManager that keeps base_risk's other fields for the rest."""
    risk_overrides = {k: v for k, v in params.items() if k in RISK_MANAGER_KEYS}
    if not risk_overrides:
        return params, base_risk
    engine_params = {k: v for k, v in params.items() if k not in RISK_MANAGER_KEYS}
    risk = RiskManager(
        max_position_pct=risk_overrides.get("max_position_pct", base_risk.max_position_pct),
        stop_loss_pct=risk_overrides.get("stop_loss_pct", base_risk.stop_loss_pct),
        take_profit_pct=risk_overrides.get("take_profit_pct", base_risk.take_profit_pct),
        max_daily_loss_pct=risk_overrides.get("max_daily_loss_pct", base_risk.max_daily_loss_pct),
    )
    return engine_params, risk


def grid_search(
    df: pd.DataFrame,
    param_grid: dict[str, list[Any]] = None,
    base_params: dict[str, Any] = None,
    risk_manager: RiskManager = None,
    symbol: str = "ASSET",
    initial_balance: float = 10_000.0,
    timeframe: str = "1d",
    metric: str = "sharpe_ratio",
    trade_start_index: int | None = None,
) -> tuple[dict, list[OptimizationRun]]:
    param_grid = param_grid or DEFAULT_PARAM_GRID
    base_params = {**DEFAULT_PARAMS, **(base_params or {})}
    risk_manager = risk_manager or RiskManager()

    keys = list(param_grid.keys())
    combos = list(itertools.product(*[param_grid[k] for k in keys]))

    runs: list[OptimizationRun] = []
    for combo in combos:
        combined = {**base_params, **dict(zip(keys, combo))}
        engine_params, risk = split_engine_and_risk_params(combined, risk_manager)
        engine = SignalEngine(engine_params)
        result = run_backtest(df, engine, risk, symbol=symbol, initial_balance=initial_balance,
                              timeframe=timeframe, trade_start_index=trade_start_index)
        # keep the full combined dict (engine + risk) so callers see everything that was tried
        runs.append(OptimizationRun(params=combined, metrics=result.metrics))

    runs.sort(key=lambda r: r.metrics.get(metric, float("-inf")), reverse=True)
    best_params = runs[0].params if runs else base_params
    return best_params, runs


def _evaluate_params(df: pd.DataFrame, params: dict, risk_manager: RiskManager, **kwargs) -> dict:
    engine_params, risk = split_engine_and_risk_params(params, risk_manager)
    engine = SignalEngine(engine_params)
    result = run_backtest(df, engine, risk, **kwargs)
    return result.metrics


def run_walk_forward(
    df: pd.DataFrame,
    param_grid: dict[str, list[Any]] = None,
    train_frac: float = 0.6,
    **kwargs,
) -> dict:
    """Single train/test split — see run_rolling_walk_forward for a more
    robust, multi-fold version. Kept for quick one-off checks."""
    split = int(len(df) * train_frac)
    train_df = df.iloc[:split]

    risk_manager = kwargs.pop("risk_manager", None) or RiskManager()
    best_params, train_runs = grid_search(train_df, param_grid, risk_manager=risk_manager, **kwargs)

    test_metrics = _evaluate_params(
        df, best_params, risk_manager,
        symbol=kwargs.get("symbol", "ASSET"),
        initial_balance=kwargs.get("initial_balance", 10_000.0),
        timeframe=kwargs.get("timeframe", "1d"),
        trade_start_index=split,
    )

    return {
        "best_params": best_params,
        "train_metrics": train_runs[0].metrics if train_runs else None,
        "test_metrics": test_metrics,
        "train_size": len(train_df),
        "test_size": len(df) - split,
    }


def run_rolling_walk_forward(
    df: pd.DataFrame,
    param_grid: dict[str, list[Any]] = None,
    n_folds: int = 4,
    train_frac: float = 0.6,
    **kwargs,
) -> dict:
    """Repeats the train/test split across n_folds rolling windows instead of
    picking one arbitrary split point, and reports the out-of-sample metric
    from EVERY fold plus an aggregate. A strategy that only did well in one
    fold and poorly in the others has no real edge — this makes that visible
    instead of hiding it behind a single lucky split.

    Fold i trains on df[i*step : i*step + train_len] and tests on the
    following test_len rows, stepping forward so folds overlap the way a
    real "re-optimize every so often" schedule would.
    """
    risk_manager = kwargs.pop("risk_manager", None) or RiskManager()
    metric = kwargs.get("metric", "sharpe_ratio")

    # Fixed-size training window (train_frac of the total), rolled forward by
    # one test-window length per fold so folds tile the remaining data.
    train_len = int(len(df) * train_frac)
    total_test_len = len(df) - train_len
    test_len = max(50, total_test_len // n_folds)

    folds = []
    for i in range(n_folds):
        train_start = i * test_len
        train_end = train_start + train_len
        test_end = train_end + test_len
        if test_end > len(df):
            break

        fold_df = df.iloc[train_start:test_end]
        split = train_len

        best_params, train_runs = grid_search(
            fold_df.iloc[:split], param_grid, risk_manager=risk_manager, **kwargs
        )
        test_metrics = _evaluate_params(
            fold_df, best_params, risk_manager,
            symbol=kwargs.get("symbol", "ASSET"),
            initial_balance=kwargs.get("initial_balance", 10_000.0),
            timeframe=kwargs.get("timeframe", "1d"),
            trade_start_index=split,
        )
        folds.append({
            "fold": i,
            "train_range": (df.index[train_start], df.index[train_end - 1]),
            "test_range": (df.index[train_end], df.index[min(test_end, len(df)) - 1]),
            "best_params": best_params,
            "train_metrics": train_runs[0].metrics if train_runs else None,
            "test_metrics": test_metrics,
        })

    if not folds:
        raise ValueError("Not enough data for the requested n_folds/train_frac combination")

    test_values = [f["test_metrics"].get(metric, 0.0) for f in folds]
    test_returns = [f["test_metrics"].get("total_return_pct", 0.0) for f in folds]
    profitable_folds = sum(1 for r in test_returns if r > 0)

    return {
        "folds": folds,
        "summary": {
            "n_folds": len(folds),
            "profitable_folds": profitable_folds,
            f"mean_test_{metric}": round(sum(test_values) / len(test_values), 3),
            "mean_test_return_pct": round(sum(test_returns) / len(test_returns), 2),
            "worst_test_return_pct": round(min(test_returns), 2),
            "best_test_return_pct": round(max(test_returns), 2),
        },
    }
