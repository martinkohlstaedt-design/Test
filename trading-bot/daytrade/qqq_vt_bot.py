"""QQQ volatility-targeting paper bot.

Weight in QQQ = min(1, TARGET_VOL / realised 20-day vol); the rest stays in cash. No leverage.
Backtest 2016-2026 (3 bps/side, 10 % rebalance band): CAGR ~19.4 %, Sharpe 1.12, max drawdown ~26 %
vs. QQQ buy&hold 20.5 % / 0.97 / 36.6 %. Optimistic: the 2016-26 tech bull market flatters QQQ.

Run once per trading day after the close (>= 16:30 ET). Sends a market-on-open PAPER order only
when the target differs from the current weight by more than the band (~10 changes a year).
It only touches QQQ - other positions in the account are left alone.

    python -m daytrade.qqq_vt_bot             # dry run
    python -m daytrade.qqq_vt_bot --execute   # place the paper order
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timedelta, timezone

import numpy as np
from dotenv import load_dotenv

from . import data
from .paper_bot import LOG_PATH, api

TARGET_VOL = 0.20
BAND = 0.10
SYMBOL = "QQQ"


def target_weight(closes, target_vol: float = TARGET_VOL, window: int = 20) -> float:
    r = np.diff(closes[-(window + 1):]) / closes[-(window + 1):-1]
    vol = float(np.std(r, ddof=1) * math.sqrt(252))
    return 1.0 if vol <= 0 else min(1.0, target_vol / vol)


def decide(target: float, current: float, band: float = BAND) -> float:
    """New weight: only move when the gap exceeds the band, or to be fully invested / fully out."""
    if abs(target - current) > band or (target >= 0.999 and current < 0.98) or (target <= 0.001 and current > 0.02):
        return target
    return current


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if api("GET", "/clock")["is_open"]:
        raise SystemExit("Market is open: run after the close (>= 16:30 ET).")
    acct = api("GET", "/account")
    if acct.get("trading_blocked") or acct.get("status") != "ACTIVE":
        raise SystemExit(f"Account not tradable: {acct.get('status')}")
    equity = float(acct["equity"])

    end = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    start = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%d")
    df = data.fetch_daily(SYMBOL, start, end)
    price = float(df["close"].iloc[-1])
    held = {p["symbol"]: int(float(p["qty"])) for p in api("GET", "/positions")}.get(SYMBOL, 0)
    current = held * price / equity
    target = target_weight(df["close"].to_numpy())
    new_w = decide(target, current)
    want = math.floor(new_w * equity / price)
    diff = want - held
    print(f"{df.index[-1].date()} | QQQ ${price:.2f} | target {target:.0%} | current {current:.0%} -> new {new_w:.0%}")
    if not diff:
        print("  no change")
        return
    order = {"symbol": SYMBOL, "side": "buy" if diff > 0 else "sell", "qty": abs(diff)}
    print(f"  {order['side'].upper()} {order['qty']} {SYMBOL} (market on open)")
    if a.execute:
        api("DELETE", "/orders")
        res = api("POST", "/orders", json={**order, "type": "market", "time_in_force": "opg"})
        LOG_PATH.parent.mkdir(exist_ok=True)
        with LOG_PATH.open("a") as f:
            f.write(json.dumps({"bot": "qqq_vt", "signal_day": str(df.index[-1].date()), "equity": equity, "order": order, "id": res["id"]}) + "\n")
        time.sleep(0.2)
        print("Placed.")
    else:
        print("Dry run - nothing sent. Use --execute.")


if __name__ == "__main__":
    main()
