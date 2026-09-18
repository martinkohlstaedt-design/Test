"""Composite buy/sell/hold signal, built from the indicators in indicators.py.

Every threshold and weight lives in a plain dict so the optimizer can search
over them without touching this logic. This is the same scoring approach as
the crypto-dashboard's computeSignal() in indicators.js, generalized so it
can be tuned against historical performance instead of fixed by hand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from indicators import compute_all_indicators, detect_crossover

DEFAULT_PARAMS: dict[str, Any] = {
    "rsi_oversold": 30,
    "rsi_oversold_weak": 40,
    "rsi_overbought": 70,
    "rsi_overbought_weak": 60,
    "weight_rsi_strong": 2,
    "weight_rsi_weak": 1,
    "weight_macd_cross": 2,
    "weight_macd_hist": 1,
    "weight_trend": 1,
    "weight_golden_death_cross": 3,
    "weight_ma_trend_state": 1,
    "weight_bollinger": 1,
    "weight_stoch_rsi": 1,
    "stoch_rsi_oversold": 20,
    "stoch_rsi_overbought": 80,
    "weight_obv": 1,
    "obv_lookback": 10,
    "weight_momentum": 1,
    "score_strong_buy": 6,
    "score_buy": 3,
    "score_sell": -3,
    "score_strong_sell": -6,
    # Well-known fix for oscillator strategies (RSI/Stochastic "buy the dip"):
    # refuse new longs while price is below the long-term trend filter MA,
    # so an oversold reading in a strong downtrend doesn't get bought.
    # 0 = off (score-only, original behavior), 1 = on.
    "require_uptrend_filter": 0,
    "trend_filter_ma": "sma200",
}


@dataclass
class Signal:
    score: float
    label: str
    reasons: list[str] = field(default_factory=list)
    row: pd.Series | None = None  # the indicator row the signal was computed from


class SignalEngine:
    def __init__(self, params: dict[str, Any] | None = None):
        self.params = {**DEFAULT_PARAMS, **(params or {})}

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Attach every indicator column. Call once per fresh OHLCV frame."""
        return compute_all_indicators(df)

    def evaluate(self, df_with_indicators: pd.DataFrame, index: int = -1) -> Signal:
        """Compute the composite signal at a given row (default: most recent)."""
        p = self.params
        row = df_with_indicators.iloc[index]
        # crossover needs the recent history, not just one row
        sma50_series = df_with_indicators["sma50"]
        sma200_series = df_with_indicators["sma200"]
        if index != -1:
            sma50_series = sma50_series.iloc[: index + 1 if index >= 0 else index + len(df_with_indicators) + 1]
            sma200_series = sma200_series.iloc[: index + 1 if index >= 0 else index + len(df_with_indicators) + 1]
        crossover = detect_crossover(sma50_series, sma200_series)

        score = 0.0
        reasons: list[str] = []

        rsi_val = row.get("rsi")
        if pd.notna(rsi_val):
            if rsi_val < p["rsi_oversold"]:
                score += p["weight_rsi_strong"]
                reasons.append(f"RSI {rsi_val:.0f} (oversold)")
            elif rsi_val < p["rsi_oversold_weak"]:
                score += p["weight_rsi_weak"]
                reasons.append(f"RSI {rsi_val:.0f} (weak)")
            elif rsi_val > p["rsi_overbought"]:
                score -= p["weight_rsi_strong"]
                reasons.append(f"RSI {rsi_val:.0f} (overbought)")
            elif rsi_val > p["rsi_overbought_weak"]:
                score -= p["weight_rsi_weak"]
                reasons.append(f"RSI {rsi_val:.0f} (strong)")

        macd_val, macd_sig, hist = row.get("macd"), row.get("macd_signal"), row.get("macd_hist")
        if pd.notna(macd_val) and pd.notna(macd_sig):
            prev_hist = df_with_indicators["macd_hist"].iloc[: index if index != -1 else len(df_with_indicators) - 1]
            prev_hist = prev_hist.dropna().iloc[-1] if not prev_hist.dropna().empty else None
            bullish_cross = macd_val > macd_sig and prev_hist is not None and prev_hist <= 0 < hist
            bearish_cross = macd_val < macd_sig and prev_hist is not None and prev_hist >= 0 > hist
            if bullish_cross:
                score += p["weight_macd_cross"]
                reasons.append("MACD bullish crossover")
            elif bearish_cross:
                score -= p["weight_macd_cross"]
                reasons.append("MACD bearish crossover")
            elif pd.notna(hist) and hist > 0:
                score += p["weight_macd_hist"]
                reasons.append("MACD histogram positive")
            elif pd.notna(hist) and hist < 0:
                score -= p["weight_macd_hist"]
                reasons.append("MACD histogram negative")

        price, sma20, sma50 = row.get("close"), row.get("sma20"), row.get("sma50")
        if pd.notna(sma20) and pd.notna(sma50):
            if price > sma20 > sma50:
                score += p["weight_trend"]
                reasons.append("Uptrend (price > SMA20 > SMA50)")
            elif price < sma20 < sma50:
                score -= p["weight_trend"]
                reasons.append("Downtrend (price < SMA20 < SMA50)")

        if crossover == "golden":
            score += p["weight_golden_death_cross"]
            reasons.append("Golden cross (SMA50 crossing above SMA200)")
        elif crossover == "death":
            score -= p["weight_golden_death_cross"]
            reasons.append("Death cross (SMA50 crossing below SMA200)")
        elif crossover == "above":
            score += p["weight_ma_trend_state"]
            reasons.append("SMA50 above SMA200 (long-term uptrend)")
        elif crossover == "below":
            score -= p["weight_ma_trend_state"]
            reasons.append("SMA50 below SMA200 (long-term downtrend)")

        pb = row.get("bb_percent_b")
        if pd.notna(pb):
            if pb < 0:
                score += p["weight_bollinger"]
                reasons.append("Price below lower Bollinger band")
            elif pb > 1:
                score -= p["weight_bollinger"]
                reasons.append("Price above upper Bollinger band")

        stoch_k = row.get("stoch_k")
        if pd.notna(stoch_k):
            if stoch_k < p["stoch_rsi_oversold"]:
                score += p["weight_stoch_rsi"]
                reasons.append(f"Stochastic RSI {stoch_k:.0f} (oversold)")
            elif stoch_k > p["stoch_rsi_overbought"]:
                score -= p["weight_stoch_rsi"]
                reasons.append(f"Stochastic RSI {stoch_k:.0f} (overbought)")

        if "obv" in df_with_indicators.columns:
            lookback = p["obv_lookback"]
            pos = index if index >= 0 else len(df_with_indicators) + index
            if pos - lookback >= 0:
                obv_now = df_with_indicators["obv"].iloc[pos]
                obv_prev = df_with_indicators["obv"].iloc[pos - lookback]
                price_now = df_with_indicators["close"].iloc[pos]
                price_prev = df_with_indicators["close"].iloc[pos - lookback]
                if pd.notna(obv_now) and pd.notna(obv_prev):
                    price_trend = price_now - price_prev
                    obv_trend = obv_now - obv_prev
                    if price_trend > 0 and obv_trend > 0:
                        score += p["weight_obv"]
                        reasons.append("Volume confirms uptrend (OBV rising)")
                    elif price_trend < 0 and obv_trend < 0:
                        score -= p["weight_obv"]
                        reasons.append("Volume confirms downtrend (OBV falling)")
                    elif price_trend > 0 and obv_trend < 0:
                        score -= p["weight_obv"]
                        reasons.append("Warning: bearish OBV divergence")
                    elif price_trend < 0 and obv_trend > 0:
                        score += p["weight_obv"]
                        reasons.append("Note: bullish OBV divergence")

        if score >= p["score_strong_buy"]:
            label = "STRONG_BUY"
        elif score >= p["score_buy"]:
            label = "BUY"
        elif score <= p["score_strong_sell"]:
            label = "STRONG_SELL"
        elif score <= p["score_sell"]:
            label = "SELL"
        else:
            label = "HOLD"

        if p.get("require_uptrend_filter") and label in ("BUY", "STRONG_BUY"):
            trend_ma = row.get(p["trend_filter_ma"])
            if pd.notna(trend_ma) and price < trend_ma:
                reasons.append(f"Kein Kauf: Preis unter {p['trend_filter_ma'].upper()} (Trendfilter aktiv)")
                label = "HOLD"

        return Signal(score=score, label=label, reasons=reasons, row=row)
