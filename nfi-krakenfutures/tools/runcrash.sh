#!/bin/bash
# usage: runcrash.sh DATADIR TIMERANGE PREFIX STRAT...   -> Backtest mit 1m-Detail (realistische Fuellung/Exits in der Kerze)
cd /root/ft_workdir
D=$1; TR=$2; P=$3; shift 3
for s in "$@"; do
  for mode in detail plain; do
    X=""; [ $mode = detail ] && X="--timeframe-detail 1m"
    /root/freqtrade-venv/bin/freqtrade backtesting --config user_data/config_kf86_main.json --strategy $s \
      --strategy-path user_data/strategies --datadir $D --timerange $TR --timeframe 5m --cache none $X \
      > logs/${P}_${mode}_${s}.log 2>&1
    echo "$mode $(grep -E "^│ *$s " logs/${P}_${mode}_${s}.log | tail -1)"
  done
done
echo ALL_DONE
