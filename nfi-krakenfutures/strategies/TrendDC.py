"""Eigene Trendfolge-Strategie (Donchian-Ausbruch, klassisches Prinzip), Kraken Futures, 4h.
Long: Schluss ueber dem Hoch der letzten N Kerzen (ohne aktuelle) und EMA50 > EMA200.
Short: Schluss unter dem Tief der letzten N Kerzen und EMA50 < EMA200.
Ausstieg: Gegen-Extrem der letzten M Kerzen (Long: Schluss unter M-Tief, Short: ueber M-Hoch).
Harter Stop als Notbremse; kein ROI (Gewinne laufen lassen)."""
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy


class TrendDC(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "4h"
    can_short = True
    startup_candle_count = 220
    minimal_roi = {"0": 100}
    stoploss = -0.25
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    order_types = {"entry": "market", "exit": "market", "stoploss": "market", "stoploss_on_exchange": False}
    _N = 55
    _M = 20
    _LEV = 1.0
    _SHORT = True
    _FILTER = True

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag, side, **kwargs):
        return min(self._LEV, max_leverage)

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["hi_n"] = df["high"].rolling(self._N).max().shift(1)
        df["lo_n"] = df["low"].rolling(self._N).min().shift(1)
        df["hi_m"] = df["high"].rolling(self._M).max().shift(1)
        df["lo_m"] = df["low"].rolling(self._M).min().shift(1)
        df["ema50"] = ta.EMA(df, timeperiod=50)
        df["ema200"] = ta.EMA(df, timeperiod=200)
        return df

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        up = df["ema50"] > df["ema200"] if self._FILTER else True
        dn = df["ema50"] < df["ema200"] if self._FILTER else True
        df.loc[(df["close"] > df["hi_n"]) & up & (df["volume"] > 0), ["enter_long", "enter_tag"]] = (1, "dc_long")
        if self._SHORT:
            df.loc[(df["close"] < df["lo_n"]) & dn & (df["volume"] > 0), ["enter_short", "enter_tag"]] = (1, "dc_short")
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[df["close"] < df["lo_m"], "exit_long"] = 1
        df.loc[df["close"] > df["hi_m"], "exit_short"] = 1
        return df


class TrendDC_Long(TrendDC):
    _SHORT = False


class TrendDC_Fast(TrendDC):
    _N = 20
    _M = 10


class TrendDC_NoF(TrendDC):
    _FILTER = False
