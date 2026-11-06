#!/bin/bash
# usage: okx_r4.sh PREFIX "EXTRA" STRATS...
cd /root/ft_workdir; P=$1; X=$2; shift 2
for grp in "w1 w2 w2c w4a" "w3 val h1 h2"; do
  for w in $grp; do CFG=user_data/config_okx_spot.json SPATH=sd_ext WINS=$w EXTRA="--fee 0.001 --enable-protections --datadir /root/ft_workdir/data_okx_snap $X" bash tools/run8.sh $P "$@" > logs/${P}_$w.out 2>&1 & done; wait
done
echo R_DONE
