#!/bin/bash
# usage: nfi_run2.sh PREFIX STRATS...  -> 8 Fenster NFI (config_kf86_main), 2 parallel
cd /root/ft_workdir; P=$1; shift
for grp in "w1 w2" "w2c w4a" "w3 val" "h1 h2"; do
  for w in $grp; do WINS=$w bash tools/run8.sh $P "$@" > logs/${P}_$w.out 2>&1 & done; wait
done
echo R_DONE
