"""Backtest for funding-rate arbitrage ("cash and carry"): hold the asset
spot and short the same amount as a perpetual future, so price moves cancel
out and what's left is the funding the short side receives (or pays).

Model, per price candle:
  1. Funding events inside the candle are credited to (or debited from) the
     futures wallet: rate * qty * price. Shorts receive positive funding.
  2. Liquidation check against the candle HIGH: if the short's losses eat the
     futures margin down to the maintenance margin, the short is force-closed
     (its margin is lost). The now-unhedged spot is only sold at the candle's
     close — in reality you notice and react after the spike, not at its top.
  3. Rebalance check at the close: if the futures margin has shrunk below
     `rebalance_margin_ratio` of the position, sell some spot and shrink the
     short so the split is back to target — this is what keeps a real
     cash-and-carry position from being liquidated in a rally.
  4. Entry/exit decision at the close, using only funding already paid
     (trailing average over `lookback_days`) — no look-ahead.

Simplifications, on purpose, so the numbers stay easy to reason about:
  - Spot and perp are valued at the same price (the basis between them is
    ignored — in reality it adds small gains/losses on entry and exit).
  - Fees are taker fees on every leg, plus slippage.
  - No interest on idle cash, no borrowing costs, no exchange default risk.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from funding_data import annualize, infer_interval_hours


@dataclass
class CarryParams:
    leverage: float = 1.0                 # short notional / futures margin
    entry_apr: float | None = 5.0         # enter when trailing funding APR (%) is above this; None = always in
    exit_apr: float | None = 0.0          # exit when trailing funding APR (%) drops below this
    lookback_days: float = 7.0            # window for the trailing funding average
    spot_fee_pct: float = 0.001           # 0.10 % taker fee on spot
    perp_fee_pct: float = 0.0005          # 0.05 % taker fee on perps
    slippage_pct: float = 0.0005
    maintenance_margin_pct: float = 0.005  # 0.5 % of notional, typical for BTC/ETH
    rebalance_margin_ratio: float | None = 0.5  # rebalance when margin < this fraction of the target margin; None = never


@dataclass
class CarryResult:
    equity_curve: pd.Series
    events: list
    metrics: dict = field(default_factory=dict)


def run_carry_backtest(
    funding: pd.DataFrame,
    prices: pd.DataFrame,
    params: CarryParams,
    initial_balance: float = 10_000.0,
) -> CarryResult:
    """`funding`: index=timestamp, column 'funding_rate' (per period).
    `prices`: OHLCV indexed by candle open timestamp."""
    p = params
    interval_h = infer_interval_hours(funding.index)

    # Only simulate the stretch covered by both data sets.
    start = max(funding.index[0], prices.index[0])
    end = min(funding.index[-1], prices.index[-1])
    prices = prices.loc[start:end]
    funding = funding.loc[start:end]
    if len(prices) < 2 or funding.empty:
        raise ValueError("Funding and price history don't overlap enough to backtest.")

    trailing_apr = funding["funding_rate"].rolling(pd.Timedelta(days=p.lookback_days)).mean().map(
        lambda r: annualize(r, interval_h))
    warmup_until = start + pd.Timedelta(days=p.lookback_days)

    # Assign each funding event to the candle it falls in.
    candle_of_event = prices.index.searchsorted(funding.index, side="right") - 1
    events_by_candle: dict[int, list[tuple]] = {}
    for (ts, rate), ci, apr in zip(funding["funding_rate"].items(), candle_of_event, trailing_apr):
        events_by_candle.setdefault(int(ci), []).append((ts, rate, apr))

    spot_share = p.leverage / (p.leverage + 1)  # of equity that goes into spot (= short notional)
    target_margin_ratio = 1 / p.leverage         # futures margin / short notional right after (re)balancing

    cash = initial_balance   # idle USDT while flat
    qty = 0.0                # asset held spot == asset shorted
    futures_equity = 0.0     # margin + funding - short PnL, marked at `ref_price`
    ref_price = 0.0
    last_apr = np.nan

    funding_received = 0.0
    fees_paid = 0.0
    counts = {"entries": 0, "exits": 0, "rebalances": 0, "liquidations": 0}
    events: list[dict] = []
    equity_points: list[tuple] = []
    candles_in_position = 0

    def equity_at(price: float) -> float:
        if qty == 0:
            return cash
        return cash + qty * price + futures_equity - qty * (price - ref_price)

    def trade_cost(notional: float, fee: float) -> float:
        return notional * (fee + p.slippage_pct)

    def open_position(price: float, ts, reason: str):
        nonlocal cash, qty, futures_equity, ref_price, fees_paid
        equity = cash
        # Solve for notional N so that spot N + margin N/lev + entry fees == equity.
        fee_rate = p.spot_fee_pct + p.perp_fee_pct + 2 * p.slippage_pct
        notional = equity / (1 + 1 / p.leverage + fee_rate)
        cost = trade_cost(notional, p.spot_fee_pct) + trade_cost(notional, p.perp_fee_pct)
        qty = notional / price
        futures_equity = notional / p.leverage
        ref_price = price
        cash = equity - notional - futures_equity - cost
        fees_paid += cost
        counts["entries"] += 1
        events.append({"time": ts, "event": "enter", "reason": reason, "price": price, "notional": notional})

    def close_position(price: float, ts, reason: str, liquidated: bool = False, spot_price: float | None = None):
        nonlocal cash, qty, futures_equity, fees_paid
        notional = qty * price
        spot_notional = qty * (spot_price if spot_price is not None else price)
        spot_proceeds = spot_notional - trade_cost(spot_notional, p.spot_fee_pct)
        if liquidated:
            futures_back = 0.0          # the exchange keeps whatever margin was left
            cost = trade_cost(spot_notional, p.spot_fee_pct)
        else:
            futures_back = futures_equity - qty * (price - ref_price) - trade_cost(notional, p.perp_fee_pct)
            cost = trade_cost(notional, p.spot_fee_pct) + trade_cost(notional, p.perp_fee_pct)
        cash += spot_proceeds + futures_back
        fees_paid += cost
        counts["liquidations" if liquidated else "exits"] += 1
        events.append({"time": ts, "event": "liquidation" if liquidated else "exit", "reason": reason,
                       "price": price, "equity_after": cash})
        qty = 0.0
        futures_equity = 0.0

    def rebalance(price: float, ts):
        nonlocal qty, futures_equity, ref_price, fees_paid
        # Mark the short to market, then shrink both legs to the target split.
        futures_equity -= qty * (price - ref_price)
        ref_price = price
        equity = qty * price + futures_equity
        new_qty = equity * spot_share / price
        traded = abs(qty - new_qty) * price
        cost = trade_cost(traded, p.spot_fee_pct) + trade_cost(traded, p.perp_fee_pct)
        # Selling spot moves cash into the futures wallet (or the reverse).
        futures_equity += (qty - new_qty) * price - cost
        qty = new_qty
        fees_paid += cost
        counts["rebalances"] += 1
        events.append({"time": ts, "event": "rebalance", "price": price, "traded_notional": traded})

    for i, (ts, row) in enumerate(prices.iterrows()):
        # 1. Funding payments in this candle.
        for f_ts, rate, apr in events_by_candle.get(i, []):
            if qty > 0:
                payment = rate * qty * row["open"]
                futures_equity += payment
                funding_received += payment
            last_apr = apr

        if qty > 0:
            # 2. Liquidation check at the candle's worst price for a short.
            worst = row["high"]
            margin_left = futures_equity - qty * (worst - ref_price)
            if margin_left <= p.maintenance_margin_pct * qty * worst:
                close_position(worst, ts, "short liquidated in price spike", liquidated=True,
                               spot_price=row["close"])
            # 3. Rebalance at the close if the margin has shrunk too far.
            elif p.rebalance_margin_ratio is not None:
                margin_now = futures_equity - qty * (row["close"] - ref_price)
                if margin_now < p.rebalance_margin_ratio * target_margin_ratio * qty * row["close"]:
                    rebalance(row["close"], ts)

        # 4. Entry / exit decision on already-known funding.
        if ts >= warmup_until and not np.isnan(last_apr):
            if qty == 0 and (p.entry_apr is None or last_apr > p.entry_apr):
                open_position(row["close"], ts, f"trailing APR {last_apr:.1f}%")
            elif qty > 0 and p.exit_apr is not None and p.entry_apr is not None and last_apr < p.exit_apr:
                close_position(row["close"], ts, f"trailing APR {last_apr:.1f}%")

        if qty > 0:
            candles_in_position += 1
        equity_points.append((ts, equity_at(row["close"])))

    equity = pd.Series(dict(equity_points))
    days = (equity.index[-1] - equity.index[0]).total_seconds() / 86400
    total_return = equity.iloc[-1] / initial_balance - 1
    running_max = equity.cummax()
    max_dd = float(((equity - running_max) / running_max).min())

    rates = funding["funding_rate"]
    metrics = {
        "period": f"{equity.index[0]:%Y-%m-%d} .. {equity.index[-1]:%Y-%m-%d} ({days:.0f} days)",
        "funding_interval_hours": interval_h,
        "avg_funding_apr_pct": round(float(annualize(rates.mean(), interval_h)), 2),
        "funding_positive_pct": round(float((rates > 0).mean()) * 100, 1),
        "final_equity": round(float(equity.iloc[-1]), 2),
        "total_return_pct": round(float(total_return) * 100, 2),
        "annualized_return_pct": round(float(total_return) * 365 / days * 100, 2) if days > 0 else 0.0,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "time_in_position_pct": round(candles_in_position / len(prices) * 100, 1),
        "funding_received": round(float(funding_received), 2),
        "fees_paid": round(float(fees_paid), 2),
        **counts,
    }
    return CarryResult(equity_curve=equity, events=events, metrics=metrics)
