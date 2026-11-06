#!/bin/bash
# usage: tr_run.sh PREFIX CFG STRATS... -> 8 Fenster, 4h, 2 parallel
cd /root/ft_workdir; P=$1; C=$2; shift 2
declare -A TR=([h1]=20250926-20260315 [h2]=20260315-20261006 [w3]=20241001-20250401 [val]=20250401-20251001 [w2c]=20240101-20240501 [w4a]=20240901-20250101 [w2]=20230501-20240101 [w1]=20220824-20230501)
run() { for s in "$@"; do /root/freqtrade-venv/bin/freqtrade backtesting --config $C --strategy $s --strategy-path sd_trend --timerange ${TR[$W]} --timeframe 4h --cache none > logs/${P}_${s}_$W.log 2>&1; echo "$W $(grep -E "^│ *$s " logs/${P}_${s}_$W.log | tail -1)"; done; }
for grp in "w1 w2" "w2c w4a" "w3 val" "h1 h2"; do for W in $grp; do (W=$W; run "$@") & done; wait; done
echo TR_DONE
