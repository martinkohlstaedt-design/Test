"""Daily-bar swing strategies (long only), evaluated honestly.

Timing: a signal computed from data up to day d's CLOSE sets the target
weights that are bought/sold at day d+1's OPEN; the weight earns the
open(d+1) -> open(d+2) return. Each weight change pays `cost_bps` per side.
Strategies are evaluated with FIXED classic parameters plus a full parameter
grid (to show robustness) - not by cherry-picking the best in-sample combo.

    python -m daytrade.swing
"""
from __future__ import annotations

import argparse
import itertools

import numpy as np
import pandas as pd

from . import data
from .download_daily import BENCH, UNIVERSE


# ---------- signals: each returns a 0/1 (or weight) frame decided at the close ----------
def trend_donchian(px: dict, entry_n=50, exit_n=20, sma_n=200) -> pd.DataFrame:
    c, h, l = px["close"], px["high"], px["low"]
    breakout = c > h.rolling(entry_n).max().shift(1)
    ok = c > c.rolling(sma_n).mean()
    exit_ = c < l.rolling(exit_n).min().shift(1)
    return _state_machine(breakout & ok, exit_ | ~ok)


def rsi2_reversion(px: dict, rsi_thr=10, exit_sma=5, sma_n=200, max_hold=10) -> pd.DataFrame:
    c = px["close"]
    d = c.diff()
    up, dn = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(), (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    enter = (rsi < rsi_thr) & (c > c.rolling(sma_n).mean())
    exit_ = c > c.rolling(exit_sma).mean()
    return _state_machine(enter, exit_, max_hold=max_hold)


def _state_machine(enter: pd.DataFrame, exit_: pd.DataFrame, max_hold: int | None = None) -> pd.DataFrame:
    e, x = enter.fillna(False).to_numpy(), exit_.fillna(False).to_numpy()
    pos = np.zeros(e.shape)
    held = np.zeros(e.shape[1], dtype=int)
    for t in range(1, len(e)):
        prev = pos[t - 1] > 0
        held = np.where(prev, held + 1, 0)
        stay = prev & ~x[t] & ((held < max_hold) if max_hold else True)
        pos[t] = (stay | (~prev & e[t])).astype(float)
    return pd.DataFrame(pos, index=enter.index, columns=enter.columns)


def xsec_momentum(px: dict, top_k=8, lookback_m=12, skip_m=1, regime: pd.Series | None = None) -> pd.DataFrame:
    """Monthly: hold the top_k by (lookback_m-skip_m) return, equal weight; cash when regime is off."""
    c = px["close"]
    ret = c.shift(skip_m * 21) / c.shift(lookback_m * 21) - 1
    month_end = c.index.to_series().groupby(c.index.to_period("M")).transform("max") == c.index.to_series()
    ranks = ret.rank(axis=1, ascending=False)
    pick = (ranks <= top_k).astype(float) / top_k
    w = pick.where(month_end).ffill().fillna(0.0)
    if regime is not None:
        w = w.mul(regime.reindex(w.index).fillna(False).astype(float), axis=0)
    return w


# ---------- evaluation ----------
def backtest(weights: pd.DataFrame, px: dict, cost_bps: float = 3.0) -> pd.Series:
    """Daily net return series, indexed by the day the return is earned."""
    o = px["open"]
    ro = o.shift(-1) / o - 1                     # open(d) -> open(d+1)
    w = weights.shift(1).fillna(0.0)             # weights decided at close d-1 earn ro[d]
    gross = (w * ro).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    return (gross - turnover * cost_bps / 1e4).iloc[:-1]


def stats(r: pd.Series, weights: pd.DataFrame | None = None) -> dict:
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    sd = r.std()
    out = {"cagr_%": round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1),
           "vol_%": round(sd * np.sqrt(252) * 100, 1),
           "sharpe": round(r.mean() / sd * np.sqrt(252), 2) if sd > 0 else 0.0,
           "maxdd_%": round(abs((eq / eq.cummax() - 1).min()) * 100, 1)}
    if weights is not None:
        out["avg_exposure_%"] = round(weights.sum(axis=1).mean() * 100, 1)
        out["turnover_x/yr"] = round(weights.diff().abs().sum(axis=1).sum() / yrs, 1)
    return out


def load_panel(symbols: list[str]) -> dict:
    frames = {s: data.load_daily(s) for s in symbols}
    return {k: pd.DataFrame({s: f[k] for s, f in frames.items()}).sort_index() for k in ("open", "high", "low", "close")}


def equalise(w: pd.DataFrame, min_slots: int = 10) -> pd.DataFrame:
    """Binary positions -> weights: each position = 1/max(#open, min_slots) of capital."""
    return w.div(np.maximum(w.sum(axis=1), min_slots), axis=0)


PERIODS = {"2016-19": ("2016-01-01", "2019-12-31"), "2020-22": ("2020-01-01", "2022-12-31"), "2023-26": ("2023-01-01", "2026-12-31")}


def report(name: str, r: pd.Series, w: pd.DataFrame | None = None):
    s = stats(r, w)
    sub = "  ".join(f"{k}:{stats(r.loc[a:b])['sharpe']:>5}" for k, (a, b) in PERIODS.items())
    print(f"{name:<34} " + " ".join(f"{k}={v}" for k, v in s.items()) + f"\n{'':<34} Sharpe by period -> {sub}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-bps", type=float, default=3.0)
    ap.add_argument("--grid", action="store_true", help="print the full parameter-robustness grids")
    a = ap.parse_args()

    px = load_panel(UNIVERSE + BENCH)
    uni = {k: v[UNIVERSE] for k, v in px.items()}
    spy_close = px["close"]["SPY"]
    regime = spy_close > spy_close.rolling(200).mean()
    cb = a.cost_bps
    print(f"Universe {len(UNIVERSE)} stocks, {px['close'].index[0].date()} .. {px['close'].index[-1].date()}, cost {cb} bps/side\n")

    # benchmarks
    spy_w = pd.DataFrame({"SPY": 1.0}, index=px["close"].index)
    report("BENCH SPY buy&hold", backtest(spy_w, {k: v[["SPY"]] for k, v in px.items()}, cb), spy_w)
    ew = pd.DataFrame(1 / len(UNIVERSE), index=uni["close"].index, columns=UNIVERSE)
    report("BENCH equal-weight universe (biased)", backtest(ew, uni, cb), ew)
    print()

    w = equalise(trend_donchian(uni)); report("trend: 50d breakout/20d exit/SMA200", backtest(w, uni, cb), w)
    w = equalise(rsi2_reversion(uni)); report("reversion: RSI2<10, exit>SMA5", backtest(w, uni, cb), w)
    w = equalise(trend_donchian(uni)).reindex(columns=UNIVERSE + ["SPY"], fill_value=0.0)
    w["SPY"] = (1 - w[UNIVERSE].sum(axis=1)).clip(lower=0)
    report("trend + idle capital in SPY", backtest(w, px, cb), w)
    w = xsec_momentum(uni, regime=regime); report("momentum: top8 12-1m, SPY>SMA200", backtest(w, uni, cb), w)
    w = xsec_momentum(uni); report("momentum: top8 12-1m, no regime", backtest(w, uni, cb), w)

    if a.grid:
        print("\n--- robustness (Sharpe) ---")
        for en, ex in itertools.product([20, 50, 100], [10, 20, 50]):
            w = equalise(trend_donchian(uni, en, ex)); print(f"trend entry={en:>3} exit={ex:>2}: {stats(backtest(w, uni, cb))['sharpe']}")
        for thr, xs in itertools.product([5, 10, 15], [5, 10]):
            w = equalise(rsi2_reversion(uni, thr, xs)); print(f"rsi2 thr={thr:>2} exitSMA={xs:>2}: {stats(backtest(w, uni, cb))['sharpe']}")
        for k, lb in itertools.product([5, 8, 12], [6, 9, 12]):
            w = xsec_momentum(uni, k, lb, regime=regime); print(f"momentum top{k:>2} lookback={lb:>2}m: {stats(backtest(w, uni, cb))['sharpe']}")


if __name__ == "__main__":
    main()
