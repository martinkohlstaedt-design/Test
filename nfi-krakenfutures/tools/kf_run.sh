#!/bin/bash
# usage: kf_run.sh PREFIX "EXTRA" STRATS...  -> 8 Fenster Kraken Futures (config_ext), 4 parallel
cd /root/ft_workdir; P=$1; X=$2; shift 2
for grp in "w1 w2 w2c w4a" "w3 val h1 h2"; do
  for w in $grp; do CFG=user_data/config_ext.json SPATH=sd_ext WINS=$w EXTRA="--enable-protections $X" bash tools/run8.sh $P "$@" > logs/${P}_$w.out 2>&1 & done; wait
done
echo R_DONE
