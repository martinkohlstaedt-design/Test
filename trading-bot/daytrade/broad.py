"""Momentum / trend on the (current) S&P 500 constituents, long only, no leverage.

Point-in-time membership is approximated with the index's "Date added": a stock is only
eligible from that date on (removes the look-ahead of buying stocks BEFORE their rise got
them into the index). Stocks removed from the index are missing -> results stay optimistic.
Idle capital is parked in QQQ. Monthly rebalance unless noted.

    python -m daytrade.broad /tmp/sp500.csv
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import data, rotation, swing


def load(constituents_csv: str):
    meta = pd.read_csv(constituents_csv)
    meta["Date added"] = pd.to_datetime(meta["Date added"], errors="coerce")
    syms = [s for s in meta["Symbol"] if "." not in s and data.cache_path(s, "1Day").exists()]
    syms += [s for s in ("QQQ", "SPY") if s not in syms]
    frames = {s: data.load_daily(s) for s in syms}
    px = {k: pd.DataFrame({s: f[k] for s, f in frames.items()}).sort_index() for k in ("open", "high", "low", "close")}
    added = meta.set_index("Symbol")["Date added"].reindex(px["close"].columns)
    member = pd.DataFrame(True, index=px["close"].index, columns=px["close"].columns)
    for s, d in added.items():
        if pd.notna(d):
            member.loc[member.index < d, s] = False
    member[["QQQ", "SPY"]] = False
    return px, member


def momentum_weights(px, member, top_n=30, lookback_m=12, skip_m=1, need_trend=True, park="QQQ"):
    c = px["close"]
    mom = c.shift(skip_m * 21) / c.shift(lookback_m * 21) - 1
    ok = member & mom.notna() & (mom > 0)
    if need_trend:
        ok &= c > c.rolling(200).mean()
    score = mom.where(ok)
    rank = score.rank(axis=1, ascending=False)
    pick = (rank <= top_n).astype(float) / top_n
    pick = pick.where(rotation._month_end_mask(c.index)).ffill().fillna(0.0)
    pick[park] = 1 - pick.drop(columns=[park]).sum(axis=1)
    return pick


def trend_weights(px, member, slots=30, park="QQQ"):
    c = px["close"]
    stocks = [s for s in c.columns if s not in ("QQQ", "SPY")]
    sub = {k: v[stocks] for k, v in px.items()}
    pos = swing.trend_donchian(sub) * member[stocks].astype(float)
    w = swing.equalise(pos, slots).reindex(columns=c.columns, fill_value=0.0)
    w[park] = (1 - w[stocks].sum(axis=1)).clip(lower=0)
    return w


def main():
    px, member = load(sys.argv[1])
    c = px["close"]
    print(f"{len(c.columns) - 2} stocks, {c.index[0].date()}..{c.index[-1].date()}, avg eligible/day {member.sum(axis=1).mean():.0f}\n")
    rows: list = []
    one = lambda s: pd.DataFrame({k: (1.0 if k == s else 0.0) for k in c.columns}, index=c.index)
    rotation.evaluate("SPY buy&hold", one("SPY"), px, 3.0, rows)
    rotation.evaluate("QQQ buy&hold", one("QQQ"), px, 3.0, rows)
    ew = member.astype(float); ew = ew.div(ew.sum(axis=1), axis=0).fillna(0.0)
    rotation.evaluate("equal-weight members (biased)", ew, px, 3.0, rows)
    for n in (20, 40):
        for lb in (6, 12):
            rotation.evaluate(f"momentum top{n} {lb}-1m +trend, idle->QQQ", momentum_weights(px, member, n, lb), px, 3.0, rows)
    rotation.evaluate("momentum top30 12-1m, no trend filter", momentum_weights(px, member, 30, 12, need_trend=False), px, 3.0, rows)
    for sl in (20, 40):
        rotation.evaluate(f"trend Donchian all members, {sl} slots, ->QQQ", trend_weights(px, member, sl), px, 3.0, rows)
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
