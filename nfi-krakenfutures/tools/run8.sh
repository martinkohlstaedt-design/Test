#!/bin/bash
# usage: run8.sh PREFIX STRAT...   -> fuehrt jede Strategie nacheinander auf den Fenstern aus
# Umgebungsvariablen: WINS="h2 h1 ..." (Standard: alle 8), EXTRA="--fee 0.001" (Zusatzoptionen)
cd /root/ft_workdir
OUT=/root/ft_workdir/logs; mkdir -p $OUT
export SSL_CERT_FILE=/root/.ccr/ca-bundle.crt REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt
P=$1; shift
declare -A TR=([h1]=20250926-20260315 [h2]=20260315-20261006 [w3]=20241001-20250401 [val]=20250401-20251001 [w2c]=20240101-20240501 [w4a]=20240901-20250101 [w2]=20230501-20240101 [w1]=20220824-20230501)
for s in "$@"; do for w in ${WINS:-h2 w2c h1 w3 val w4a w2 w1}; do
  echo "START $s $w $(date +%T)"
  /root/freqtrade-venv/bin/freqtrade backtesting --config user_data/config_kf86_main.json --strategy $s \
    --strategy-path user_data/strategies --timerange ${TR[$w]} --timeframe 5m --cache none $EXTRA > $OUT/${P}_${s}_$w.log 2>&1
  grep -E "^\│ *$s " $OUT/${P}_${s}_$w.log | tail -1
done; done
echo ALL_DONE
