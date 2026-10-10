"""Entry rules. Each takes one Day and params and returns at most one Setup
(one trade per symbol per day). A signal seen at the close of bar i is filled
at the OPEN of bar i+1 (`entry_i`) - never on the signal bar itself.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .features import Day


@dataclass
class Setup:
    entry_i: int
    side: int        # +1 long, -1 short
    stop: float
    target: float


def _bars(minutes: int, bar_minutes: int) -> int:
    return max(1, minutes // bar_minutes)


def _trend_ok(day: Day, side: int, use_trend: bool) -> bool:
    return (not use_trend) or day.trend == 0 or day.trend == side


def orb(day: Day, p: dict) -> Setup | None:
    """Opening Range Breakout: after the first `or_minutes`, enter in the
    direction of the first bar to CLOSE beyond the range. Stop inside the range
    (`stop_frac`: 1.0 = far side, 0.5 = midpoint), target `rr` x risk."""
    n_or = _bars(p["or_minutes"], day.bar_minutes)
    last_entry = day.n - 1 - _bars(p.get("cutoff_minutes_before_close", 90), day.bar_minutes)
    hi, lo = day.h[:n_or].max(), day.l[:n_or].min()
    rng = hi - lo
    if rng <= 0 or rng / day.o[0] < p.get("min_range_pct", 0.001):
        return None
    for i in range(n_or, last_entry):
        side = 1 if day.c[i] > hi else -1 if day.c[i] < lo else 0
        if side == 0:
            continue
        if side < 0 and not p.get("allow_short", True):
            return None
        if not _trend_ok(day, side, p.get("use_trend", True)):
            return None
        entry = day.o[i + 1]
        stop = (hi - p["stop_frac"] * rng) if side > 0 else (lo + p["stop_frac"] * rng)
        risk = (entry - stop) * side
        if risk <= 0:
            return None
        return Setup(i + 1, side, stop, entry + side * p["rr"] * risk)
    return None


def vwap_reversion(day: Day, p: dict) -> Setup | None:
    """Fade stretches away from VWAP: enter against a close at least `k` ATRs
    from VWAP, target VWAP, stop `stop_atr` ATRs beyond entry."""
    start = _bars(p.get("start_minutes", 45), day.bar_minutes)
    last_entry = day.n - 1 - _bars(p.get("cutoff_minutes_before_close", 90), day.bar_minutes)
    for i in range(start, last_entry):
        a = day.atr[i]
        if not a or np.isnan(a) or a <= 0:
            continue
        dev = (day.c[i] - day.vwap[i]) / a
        if abs(dev) < p["k"]:
            continue
        side = -1 if dev > 0 else 1
        if not _trend_ok(day, side, p.get("use_trend", False)):
            continue
        entry = day.o[i + 1]
        stop = entry - side * p["stop_atr"] * a
        target = day.vwap[i]
        if (target - entry) * side <= 0:
            continue
        return Setup(i + 1, side, stop, target)
    return None


def rvol_momentum(day: Day, p: dict) -> Setup | None:
    """Volume-spike continuation: a bar with relative volume >= `rvol_min` that
    closes beyond the previous `lookback` bars' extreme triggers entry with the
    bar, stop `stop_atr` ATRs away, target `rr` x risk."""
    lb = p.get("lookback", 3)
    last_entry = day.n - 1 - _bars(p.get("cutoff_minutes_before_close", 90), day.bar_minutes)
    for i in range(max(lb, 2), last_entry):
        if day.rvol[i] < p["rvol_min"]:
            continue
        a = day.atr[i]
        if not a or np.isnan(a) or a <= 0:
            continue
        up = day.c[i] > day.o[i] and day.c[i] > day.h[i - lb:i].max()
        dn = day.c[i] < day.o[i] and day.c[i] < day.l[i - lb:i].min()
        side = 1 if up else -1 if dn else 0
        if side == 0 or not _trend_ok(day, side, p.get("use_trend", True)):
            continue
        if side < 0 and not p.get("allow_short", True):
            continue
        entry = day.o[i + 1]
        risk = p["stop_atr"] * a
        return Setup(i + 1, side, entry - side * risk, entry + side * p["rr"] * risk)
    return None


STRATEGIES = {"orb": orb, "vwap_reversion": vwap_reversion, "rvol_momentum": rvol_momentum}

PARAM_GRIDS = {
    "orb": {"or_minutes": [15, 30, 60], "stop_frac": [0.5, 1.0], "rr": [1.0, 2.0],
            "use_trend": [True, False], "allow_short": [True, False]},
    "vwap_reversion": {"k": [1.5, 2.5, 3.5], "stop_atr": [2.0, 4.0], "use_trend": [True, False]},
    "rvol_momentum": {"rvol_min": [2.0, 3.0], "stop_atr": [1.0, 2.0], "rr": [1.5, 3.0],
                      "use_trend": [True, False]},
}
