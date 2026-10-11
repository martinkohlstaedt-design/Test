"""More documented anomalies on S&P 500 constituents / QQQ, long only, no leverage.

    python -m daytrade.more /tmp/sp500.csv
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import broad, rotation, swing


def high52_weights(px, member, top_n=20, park="QQQ"):
    c = px["close"]
    near = c / c.rolling(252).max()
    ok = member & (c > c.rolling(200).mean()) & near.notna()
    rank = near.where(ok).rank(axis=1, ascending=False)
    w = (rank <= top_n).astype(float) / top_n
    w = w.where(rotation._month_end_mask(c.index)).ffill().fillna(0.0)
    w[park] = 1 - w.drop(columns=[park]).sum(axis=1)
    return w


def reversal_weights(px, member, slots=25, rsi_thr=10, max_hold=5, park="QQQ"):
    """Connors-style: buy stocks above SMA200 after an RSI(2) washout, exit on close > SMA5 or after max_hold days."""
    c = px["close"]
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    elig = (member & (c > c.rolling(200).mean()) & (rsi < rsi_thr)).to_numpy()
    rsi_a = rsi.to_numpy()
    exit_ok = (c > c.rolling(5).mean()).to_numpy()
    n_days, n = c.shape
    held = np.zeros(n, dtype=int)
    pos = np.zeros(n, dtype=bool)
    W = np.zeros((n_days, n))
    for t in range(n_days):
        if pos.any():
            held[pos] += 1
            pos &= ~(exit_ok[t] | (held >= max_hold))
        free = slots - int(pos.sum())
        if free > 0:
            cand = np.where(elig[t] & ~pos)[0]
            if len(cand):
                best = cand[np.argsort(rsi_a[t, cand])[:free]]
                pos[best] = True
                held[best] = 0
        W[t] = pos / slots
    w = pd.DataFrame(W, index=c.index, columns=c.columns)
    w[park] = 1 - w.drop(columns=[park]).sum(axis=1)
    return w


def totm_weights(px, asset="QQQ", before=2, after=3, off="SHY"):
    """Hold `asset` from `before` days before month-end through `after` days after; else `off` (cash-like)."""
    c = px["close"]
    idx = c.index
    per = idx.to_period("M")
    pos_in_month = pd.Series(1, index=idx).groupby(per).cumsum()
    from_end = pd.Series(1, index=idx).groupby(per).cumsum().groupby(per).transform("max") - pos_in_month
    on = ((from_end < before) | (pos_in_month <= after)).astype(float)
    w = pd.DataFrame(0.0, index=idx, columns=c.columns)
    w[asset] = on
    w[off] = 1 - on
    return w


def overnight_returns(px, asset="QQQ", cost_bps=3.0):
    """Buy at the close, sell at next open, every day. Two trades per day."""
    o, c = px["open"][asset], px["close"][asset]
    return (o.shift(-1) / c - 1 - 2 * cost_bps / 1e4).dropna()


def dip_weights(px, asset="QQQ", rsi_thr=10, max_hold=5, off="SHY"):
    c = px["close"][asset]
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn)
    enter = ((rsi < rsi_thr) & (c > c.rolling(200).mean())).to_frame(asset)
    exit_ = (c > c.rolling(5).mean()).to_frame(asset)
    pos = swing._state_machine(enter, exit_, max_hold=max_hold)[asset]
    w = pd.DataFrame(0.0, index=px["close"].index, columns=px["close"].columns)
    w[asset] = pos
    w[off] = 1 - pos
    return w


def main():
    px, member = broad.load(sys.argv[1])
    etf = swing.load_panel(rotation.ALL_ETF)
    for k in px:                      # add SHY/IEF etc. to the panel
        for s in ("SHY", "IEF"):
            px[k][s] = etf[k][s].reindex(px[k].index)
    member = member.reindex(columns=px["close"].columns, fill_value=False)
    c = px["close"]
    rows: list = []
    one = lambda s: pd.DataFrame({k: (1.0 if k == s else 0.0) for k in c.columns}, index=c.index)
    rotation.evaluate("QQQ buy&hold", one("QQQ"), px, 3.0, rows)
    rotation.evaluate("52w-high top20 monthly +trend, idle->QQQ", high52_weights(px, member, 20), px, 3.0, rows)
    rotation.evaluate("52w-high top40 monthly +trend, idle->QQQ", high52_weights(px, member, 40), px, 3.0, rows)
    for sl, thr in ((25, 10), (25, 5), (50, 10)):
        rotation.evaluate(f"reversal RSI2<{thr}, {sl} slots, idle->QQQ", reversal_weights(px, member, sl, thr), px, 3.0, rows)
    rotation.evaluate("turn-of-month QQQ (else SHY)", totm_weights(px), px, 3.0, rows)
    rotation.evaluate("QQQ RSI2<10 dip-buy (else SHY)", dip_weights(px), px, 3.0, rows)
    on = overnight_returns(px)
    f, a, b = swing.stats(on), swing.stats(on.loc[:"2020-12-31"]), swing.stats(on.loc["2021-01-01":])
    rows.append({"strategy": "overnight QQQ (close->open) 3bps", "CAGR": f["cagr_%"], "Sharpe": f["sharpe"], "MaxDD": f["maxdd_%"],
                 "dev CAGR": a["cagr_%"], "dev Sh": a["sharpe"], "test CAGR": b["cagr_%"], "test Sh": b["sharpe"]})
    on0 = overnight_returns(px, cost_bps=0.0)
    f = swing.stats(on0)
    rows.append({"strategy": "overnight QQQ with ZERO cost", "CAGR": f["cagr_%"], "Sharpe": f["sharpe"], "MaxDD": f["maxdd_%"],
                 "dev CAGR": swing.stats(on0.loc[:'2020-12-31'])["cagr_%"], "dev Sh": swing.stats(on0.loc[:'2020-12-31'])["sharpe"],
                 "test CAGR": swing.stats(on0.loc['2021-01-01':])["cagr_%"], "test Sh": swing.stats(on0.loc['2021-01-01':])["sharpe"]})
    pd.set_option("display.width", 220)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
