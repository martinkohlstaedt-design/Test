"""Paper-trading bot for the daily trend filter (50d breakout / 20d low exit / SMA200).

Run once per trading day AFTER the close (>= ~16:30 ET; the free Alpaca plan
delays SIP data by 15 min). It rebuilds today's target positions from daily
history exactly like the backtest (swing.trend_donchian + equal slots), then
sends market-on-open (time_in_force=opg) orders for the difference, so fills
happen at the next open - the same timing the backtest assumed.

    python -m daytrade.paper_bot             # dry run: prints the plan, sends nothing
    python -m daytrade.paper_bot --execute   # places the paper orders

Hard-wired to Alpaca's PAPER endpoint; it cannot trade real money.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from . import data, swing
from .download_daily import UNIVERSE

PAPER_URL = "https://paper-api.alpaca.markets/v2"   # constant on purpose: no live-trading switch
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "paper_bot.jsonl"
MIN_SLOTS = 10          # each position = 1/max(#open, MIN_SLOTS) of equity (same as the backtest)
HISTORY_DAYS = 1100     # ~3 years of calendar history so the entry/exit state is reproducible


def _headers() -> dict:
    key, secret = os.environ.get("ALPACA_API_KEY_ID"), os.environ.get("ALPACA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Set ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY (trading-bot/.env).")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def api(method: str, path: str, **kw):
    r = requests.request(method, f"{PAPER_URL}{path}", headers=_headers(), timeout=30, **kw)
    if not r.ok:
        raise RuntimeError(f"Alpaca {method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else None


def target_weights(panel: dict, universe: list[str]) -> pd.Series:
    """Target weight per symbol decided at the latest close."""
    sub = {k: v[universe] for k, v in panel.items()}
    w = swing.equalise(swing.trend_donchian(sub), MIN_SLOTS)
    return w.iloc[-1]


def plan_orders(weights: pd.Series, last_close: pd.Series, equity: float,
                held: dict[str, int], min_trade_frac: float = 0.25) -> list[dict]:
    """Share-count diffs to reach the targets. Held positions are only resized
    if they drift by more than `min_trade_frac` of the target (avoids churn
    from price moves alone - the backtest only trades on signal changes)."""
    orders = []
    for sym in sorted(set(weights.index) | set(held)):
        want_val = float(weights.get(sym, 0.0)) * equity
        px = float(last_close.get(sym, float("nan")))
        have = held.get(sym, 0)
        if weights.get(sym, 0.0) <= 0:
            want = 0
        elif math.isnan(px) or px <= 0:
            continue
        else:
            want = math.floor(want_val / px)
            if have > 0 and abs(have - want) <= min_trade_frac * max(want, 1):
                want = have
        diff = want - have
        if diff:
            orders.append({"symbol": sym, "side": "buy" if diff > 0 else "sell", "qty": abs(diff)})
    return sorted(orders, key=lambda o: o["side"] != "sell")   # sells first


def load_panel(universe: list[str]) -> dict:
    end = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")  # free SIP plan: >15 min old
    start = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    frames = {s: data.fetch_daily(s, start, end) for s in universe}
    return {k: pd.DataFrame({s: f[k] for s, f in frames.items()}).sort_index()
            for k in ("open", "high", "low", "close")}


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="actually place paper orders (default: dry run)")
    a = ap.parse_args()

    if api("GET", "/clock")["is_open"]:
        raise SystemExit("Market is open: today's daily bar is incomplete. Run after the close (>= 16:30 ET).")
    acct = api("GET", "/account")
    if acct.get("trading_blocked") or acct.get("status") != "ACTIVE":
        raise SystemExit(f"Account not tradable: {acct.get('status')}, blocked={acct.get('trading_blocked')}")
    equity = float(acct["equity"])

    panel = load_panel(UNIVERSE)
    last_day = panel["close"].index[-1].date()
    weights = target_weights(panel, UNIVERSE)
    held = {p["symbol"]: int(float(p["qty"])) for p in api("GET", "/positions")}
    orders = plan_orders(weights, panel["close"].iloc[-1], equity, held)

    longs = [s for s in UNIVERSE if weights[s] > 0]
    print(f"Signal day {last_day} | equity ${equity:,.0f} | targets: {len(longs)} longs {longs}")
    print(f"Currently held: {held or 'nothing'}")
    for o in orders:
        print(f"  {o['side'].upper():<4} {o['qty']:>5} {o['symbol']}")
    if not orders:
        print("  no changes")

    if a.execute and orders:
        api("DELETE", "/orders")          # clear stale open orders so reruns never double up
        for o in orders:
            res = api("POST", "/orders", json={**o, "type": "market", "time_in_force": "opg"})
            o["order_id"] = res["id"]
            time.sleep(0.2)
        LOG_PATH.parent.mkdir(exist_ok=True)
        with LOG_PATH.open("a") as f:
            f.write(json.dumps({"signal_day": str(last_day), "equity": equity, "orders": orders}) + "\n")
        print(f"Placed {len(orders)} market-on-open paper orders.")
    elif orders:
        print("Dry run - nothing sent. Use --execute to place these as paper orders.")


if __name__ == "__main__":
    main()
