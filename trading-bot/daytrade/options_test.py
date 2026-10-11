"""Covered calls / cash-secured puts on QQQ with REAL option prices (Alpaca daily option bars, ~Feb 2024 on).

Each cycle: enter the day after the previous monthly expiry, sell one option (ATM or 2 % OTM, next monthly
expiry, ~4-5 weeks), hold to expiry, settle at QQQ's close. Entry price = that day's option VWAP minus a
`haircut` of the premium (bid/ask not available historically). Underlying leg valued from the entry-day open.
Sample is ~2.7 years of one bull market - illustrative only, not statistical proof.

    python -m daytrade.options_test
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

from . import data

URL = "https://data.alpaca.markets/v1beta1/options/bars"


def third_friday(y: int, m: int) -> date:
    d = date(y, m, 15)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d


def option_vwap(sym: str, day: date) -> tuple[float, int] | None:
    h = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY_ID"], "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET_KEY"]}
    p = {"symbols": sym, "timeframe": "1Day", "start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat()}
    r = requests.get(URL, headers=h, params=p, timeout=30)
    r.raise_for_status()
    bars = (r.json().get("bars") or {}).get(sym) or []
    time.sleep(0.15)
    return (bars[0]["vw"], bars[0]["v"]) if bars else None


def find_option(kind: str, expiry: date, entry: date, spot: float, otm: float):
    target = spot * (1 + otm) if kind == "C" else spot * (1 - otm)
    base = int(round(target))
    for off in (0, 1, -1, 2, -2, 3, -3):
        k = base + off
        sym = f"QQQ{expiry:%y%m%d}{kind}{int(k * 1000):08d}"
        res = option_vwap(sym, entry)
        if res and res[1] >= 5:
            return k, res[0]
    return None


def main():
    load_dotenv()
    q = data.load_daily("QQQ")
    shy = data.load_daily("SHY")["close"]
    expiries = [third_friday(2024 + (m - 1) // 12, (m - 1) % 12 + 1) for m in range(1, 34)]
    expiries = [e for e in expiries if date(2024, 2, 16) <= e <= date(2026, 9, 30)]
    cycles = []
    for prev, exp in zip(expiries[:-1], expiries[1:]):
        days = q.index[q.index > pd.Timestamp(prev)]
        entry = days[0]
        S0 = float(q.loc[entry, "open"])
        ST = float(q.loc[:pd.Timestamp(exp), "close"].iloc[-1])
        cash_ret = float(shy.loc[:pd.Timestamp(exp)].iloc[-1] / shy.loc[:entry].iloc[-1] - 1)
        row = {"entry": entry.date(), "exp": exp, "S0": S0, "ST": ST, "hold": ST / S0 - 1, "cash": cash_ret}
        for name, kind, otm in (("CC_ATM", "C", 0.0), ("CC_2OTM", "C", 0.02), ("CSP_ATM", "P", 0.0), ("CSP_2OTM", "P", 0.02)):
            f = find_option(kind, exp, entry.date(), S0, otm)
            row[name] = f
        cycles.append(row)
        print(row["entry"], row["exp"], f"S0 {S0:.1f} ST {ST:.1f}", {k: row[k] for k in ("CC_ATM", "CC_2OTM", "CSP_ATM", "CSP_2OTM")}, flush=True)
    pd.to_pickle(cycles, "/tmp/option_cycles.pkl")
    report(cycles)


def report(cycles, haircuts=(0.0, 0.05)):
    yrs = len(cycles) * 4.35 / 52
    for h in haircuts:
        print(f"\n--- premium haircut {h:.0%} (assumed spread cost), {len(cycles)} monthly cycles ---")
        series = {"QQQ buy&hold": [c["hold"] for c in cycles]}
        for name in ("CC_ATM", "CC_2OTM", "CSP_ATM", "CSP_2OTM"):
            rets = []
            for c in cycles:
                f = c[name]
                if f is None:
                    rets.append(None); continue
                k, prem = f; prem *= (1 - h)
                if name.startswith("CC"):
                    rets.append((c["ST"] - c["S0"] + prem - max(c["ST"] - k, 0)) / c["S0"])
                else:                                           # cash collateral earns SHY
                    rets.append((prem - max(k - c["ST"], 0)) / c["S0"] + c["cash"])
            series[name] = rets
        for name, rets in series.items():
            ok = [r for r in rets if r is not None]
            eq = np.cumprod([1 + r for r in ok])
            dd = abs((eq / np.maximum.accumulate(eq) - 1).min()) * 100
            print(f"{name:<14} total {100 * (eq[-1] - 1):>6.1f}%  CAGR {100 * (eq[-1] ** (1 / yrs) - 1):>5.1f}%  worst month {100 * min(ok):>6.1f}%  "
                  f"cycle-DD {dd:>5.1f}%  cycles {len(ok)}/{len(rets)}")


if __name__ == "__main__":
    main()
