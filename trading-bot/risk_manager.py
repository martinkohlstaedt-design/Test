"""Position sizing and loss limits — kept separate from the signal engine so
a promising signal never bypasses risk controls, and so these limits stay
easy to reason about and unit-test on their own.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskManager:
    max_position_pct: float = 0.2     # fraction of current balance to risk per trade
    stop_loss_pct: float = 0.05       # close if price falls this far below entry
    take_profit_pct: float = 0.10     # close if price rises this far above entry
    max_daily_loss_pct: float = 0.05  # halt new trades once daily loss exceeds this

    def position_size(self, balance: float, price: float) -> float:
        if price <= 0 or balance <= 0:
            return 0.0
        budget = balance * self.max_position_pct
        return budget / price

    def check_exit(self, entry_price: float, current_price: float) -> str | None:
        """Returns 'stop_loss', 'take_profit', or None."""
        if entry_price <= 0:
            return None
        change = (current_price - entry_price) / entry_price
        if change <= -self.stop_loss_pct:
            return "stop_loss"
        if change >= self.take_profit_pct:
            return "take_profit"
        return None

    def kill_switch_triggered(self, start_of_day_equity: float, current_equity: float) -> bool:
        if start_of_day_equity <= 0:
            return False
        drawdown = (start_of_day_equity - current_equity) / start_of_day_equity
        return drawdown >= self.max_daily_loss_pct
