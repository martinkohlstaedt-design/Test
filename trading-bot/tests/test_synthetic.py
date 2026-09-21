"""Offline smoke test for the signal engine + risk manager + backtester
pipeline, using generated OHLCV data instead of a real exchange.

Useful whenever a real exchange API isn't reachable (firewalled sandbox,
no network, rate-limited) but you still want to confirm the core logic
(indicators -> signal -> risk-managed paper fills -> metrics) runs
end-to-end and produces sane numbers. Run with:

    python tests/test_synthetic.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from backtester import run_backtest
from risk_manager import RiskManager
from signal_engine import SignalEngine


def make_synthetic_ohlcv(n: int = 800, seed: int = 42, start_price: float = 100.0) -> pd.DataFrame:
    """Random-walk-with-drift close prices, then OHLV derived around each
    close so the shape resembles real candles (open near prior close, high/low
    straddling both, positive volume)."""
    rng = np.random.default_rng(seed)
    drift = 0.0002
    vol = 0.02
    log_returns = rng.normal(drift, vol, n)
    close = start_price * np.exp(np.cumsum(log_returns))

    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1]

    intraday_range = np.abs(rng.normal(0, vol, n)) * close
    high = np.maximum(open_, close) + intraday_range
    low = np.minimum(open_, close) - intraday_range
    volume = rng.uniform(1000, 5000, n)

    index = pd.date_range("2023-01-01", periods=n, freq="1D")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def main() -> None:
    df = make_synthetic_ohlcv()
    signal_engine = SignalEngine()
    risk_manager = RiskManager()

    result = run_backtest(
        df,
        signal_engine,
        risk_manager,
        symbol="SYNTH/USDT",
        initial_balance=10_000.0,
        timeframe="1d",
        warmup=200,
    )

    print("Synthetic backtest metrics:", result.metrics)

    assert len(result.equity_curve) > 0, "backtest produced no equity curve"
    assert result.metrics["final_equity"] > 0, "equity went to zero or negative"
    assert not np.isnan(result.metrics["sharpe_ratio"]), "sharpe ratio is NaN"

    print("OK: signal engine + risk manager + backtester pipeline runs end-to-end.")


if __name__ == "__main__":
    main()
