"""Zaehlt je 5m-Kerze, wie viele Coins ein NASMAO-Kaufsignal haben (Signal-Kerze), fuer den Cluster-Filter im Backtest.
Ergebnis: /root/ft_workdir/sigcount.feather (date, n)"""
import sys, gc
import pandas as pd
sys.path.insert(0, "/root/ft_workdir/sd_ext")
from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode, CandleType
from freqtrade.data.history import load_pair_history
from freqtrade.data.dataprovider import DataProvider
from freqtrade.resolvers import StrategyResolver
c = Configuration.from_files(["/root/ft_workdir/user_data/config_ext.json"])
c["runmode"] = RunMode.BACKTEST
c["strategy"] = "NotAnotherSMAOffsetStrategyHO"
c["strategy_path"] = "/root/ft_workdir/sd_ext"
s = StrategyResolver.load_strategy(c)
s.dp = DataProvider(c, None)
tot = None
for i, p in enumerate(c["exchange"]["pair_whitelist"]):
    df = load_pair_history(pair=p, timeframe="5m", datadir=c["datadir"] if "datadir" in c else None,
                           candle_type=CandleType.FUTURES) if False else None
    from pathlib import Path
    df = load_pair_history(pair=p, timeframe="5m", datadir=Path("/root/ft_workdir/user_data/data/krakenfutures"),
                           candle_type=CandleType.FUTURES)
    if df.empty:
        continue
    df = s.advise_indicators(df, {"pair": p})
    df = s.advise_entry(df, {"pair": p})
    sig = df[["date"]].copy()
    sig["n"] = (df["enter_long"].fillna(0) == 1).astype(int)
    tot = sig if tot is None else tot.merge(sig, on="date", how="outer", suffixes=("", "_b")).fillna(0).assign(
        n=lambda x: x["n"] + x["n_b"]).drop(columns=["n_b"])
    del df; gc.collect()
    print(i, p, int(sig["n"].sum()), flush=True)
tot = tot.sort_values("date").reset_index(drop=True)
tot["n"] = tot["n"].astype(int)
tot.to_feather("/root/ft_workdir/sigcount.feather")
print("fertig", len(tot), tot["n"].describe())
