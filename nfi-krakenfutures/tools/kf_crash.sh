#!/bin/bash
# usage: kf_crash.sh PREFIX STRATS... -> 4 Crash-Fenster, 1m-Detail und 5m, Kraken Futures
cd /root/ft_workdir; P=$1; shift
declare -A C=([d1]=20251009-20251013 [d2]=20240411-20240416 [d3]=20241218-20241222 [d4]=20250201-20250205)
for s in "$@"; do
  for d in d1 d2 d3 d4; do
    for mode in 1m 5m; do
      X=""; [ $mode = 1m ] && X="--timeframe-detail 1m"
      /root/freqtrade-venv/bin/freqtrade backtesting --config user_data/config_ext.json --strategy $s --strategy-path sd_ext \
        --datadir data_$d --timerange ${C[$d]} --timeframe 5m --cache none --enable-protections $X > logs/${P}_${s}_${d}_$mode.log 2>&1 &
    done
  done
  wait
  for d in d1 d2 d3 d4; do for mode in 1m 5m; do
    echo "$s $d $mode $(grep -E "^│ *$s " logs/${P}_${s}_${d}_$mode.log | tail -1 | awk -F'│' '{print $6, $9}')"
  done; done
done
echo CRASH_DONE
