"""Broker abstraction: PaperBroker (simulated fills) and LiveBroker (real
orders via ccxt). The bot's main loop talks to whichever one is configured
through the exact same interface, so switching modes never touches strategy
code — only the config file.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Position:
    symbol: str
    amount: float = 0.0
    entry_price: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.amount > 0


@dataclass
class Trade:
    timestamp: float
    symbol: str
    side: str  # "buy" | "sell"
    amount: float
    price: float
    fee: float
    reason: str = ""


class Broker:
    def get_balance(self) -> float:
        raise NotImplementedError

    def get_position(self, symbol: str) -> Position:
        raise NotImplementedError

    def place_order(self, symbol: str, side: str, amount: float, price: float, reason: str = "") -> Trade:
        raise NotImplementedError


class PaperBroker(Broker):
    """Simulates fills at the given price, applying a fee and optional
    slippage, and tracks a single quote-currency cash balance plus one
    position per symbol. Trades are logged to a JSON-lines file so a paper
    run's history survives restarts."""

    def __init__(self, initial_balance: float, fee_pct: float = 0.001, slippage_pct: float = 0.0005,
                 log_path: str | Path = "logs/paper_trades.jsonl"):
        self.cash = initial_balance
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def get_balance(self) -> float:
        return self.cash

    def get_position(self, symbol: str) -> Position:
        return self.positions.get(symbol, Position(symbol=symbol))

    def equity(self, current_prices: dict[str, float]) -> float:
        total = self.cash
        for symbol, pos in self.positions.items():
            if pos.is_open and symbol in current_prices:
                total += pos.amount * current_prices[symbol]
        return total

    def place_order(self, symbol: str, side: str, amount: float, price: float, reason: str = "",
                     timestamp: float | None = None) -> Trade:
        if amount <= 0:
            raise ValueError("amount must be positive")

        fill_price = price * (1 + self.slippage_pct) if side == "buy" else price * (1 - self.slippage_pct)
        cost = amount * fill_price
        fee = cost * self.fee_pct

        pos = self.positions.setdefault(symbol, Position(symbol=symbol))

        if side == "buy":
            total_cost = cost + fee
            if total_cost > self.cash:
                raise ValueError(f"Insufficient paper balance: need {total_cost:.2f}, have {self.cash:.2f}")
            self.cash -= total_cost
            new_amount = pos.amount + amount
            pos.entry_price = (pos.entry_price * pos.amount + fill_price * amount) / new_amount if new_amount else 0
            pos.amount = new_amount
        elif side == "sell":
            if amount > pos.amount + 1e-12:
                raise ValueError(f"Cannot sell {amount}, only holding {pos.amount}")
            self.cash += cost - fee
            pos.amount -= amount
            if pos.amount <= 1e-12:
                pos.amount = 0.0
                pos.entry_price = 0.0
        else:
            raise ValueError(f"Unknown side: {side}")

        trade = Trade(timestamp=timestamp if timestamp is not None else time.time(),
                      symbol=symbol, side=side, amount=amount, price=fill_price, fee=fee, reason=reason)
        self.trades.append(trade)
        self._append_log(trade)
        return trade

    def _append_log(self, trade: Trade) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps(trade.__dict__) + "\n")


class LiveBroker(Broker):
    """Places real orders on a real exchange via ccxt. Never construct this
    directly from a config file alone — it requires the explicit environment
    variable safety check below, so a mistyped config value can't accidentally
    put real money at risk."""

    def __init__(self, exchange_id: str, api_key: str, api_secret: str):
        if os.environ.get("I_UNDERSTAND_LIVE_TRADING_RISK", "").lower() != "true":
            raise RuntimeError(
                "Refusing to start LiveBroker: set the environment variable "
                "I_UNDERSTAND_LIVE_TRADING_RISK=true only once you have paper-traded "
                "and backtested this strategy and accept that live trading can lose "
                "real money."
            )
        import ccxt  # imported lazily so paper-only users don't need it configured

        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"ccxt has no exchange named '{exchange_id}'")
        self.exchange = getattr(ccxt, exchange_id)({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })

    def get_balance(self, currency: str = "USDT") -> float:
        balance = self.exchange.fetch_balance()
        return float(balance.get(currency, {}).get("free", 0.0))

    def get_position(self, symbol: str) -> Position:
        # Spot exchanges don't track "positions" the way futures do; approximate
        # via the free balance of the symbol's base currency.
        base = symbol.split("/")[0]
        balance = self.exchange.fetch_balance()
        amount = float(balance.get(base, {}).get("free", 0.0))
        return Position(symbol=symbol, amount=amount)

    def place_order(self, symbol: str, side: str, amount: float, price: float | None = None, reason: str = "") -> Trade:
        order = self.exchange.create_order(symbol, type="market", side=side, amount=amount)
        filled_price = float(order.get("average") or order.get("price") or price or 0.0)
        fee = float(sum(f.get("cost", 0.0) for f in order.get("fees", []) or []))
        return Trade(timestamp=time.time(), symbol=symbol, side=side, amount=amount, price=filled_price, fee=fee, reason=reason)
