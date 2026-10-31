#!/bin/bash
# usage: coinsets.sh STRAT [FEE]  -> STRAT auf Kraken Spot je Coin-Set aus spot_coinsets.json (alle 8 Fenster)
cd /root/ft_workdir
S=$1; FEE=${2:-0.0025}
for set in A_NFItop B_Rest L_Large20 N_NoMeme; do
  P=$(python3 -c "import json;print(' '.join(json.load(open('spot_coinsets.json'))['$set']))")
  CFG=user_data/config_spot.json SPATH=sd_ext EXTRA="--fee $FEE --pairs $P" bash tools/run8.sh cs_$set $S
done
echo COINSETS_DONE
