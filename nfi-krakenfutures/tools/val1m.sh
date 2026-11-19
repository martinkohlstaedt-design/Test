#!/bin/bash
# "Wie live"-Pruefung: H2 (15.03.-06.10.2026) mit 1m-Detail fuer die wichtigsten NFI-Staende. Wiederaufnehmbar.
cd /root/ft_workdir
export SSL_CERT_FILE=/root/.ccr/ca-bundle.crt REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt
# erst den 5-Wochen-Abgleich fertig laufen lassen (liest dieselben 1m-Dateien)
until grep -qE "^│ *NFI_KF_V23_Grind3 |Error|Traceback" logs/recent1m_sd_new3.log 2>/dev/null; do sleep 30; done
while pgrep -f "[f]reqtrade (download-data|backtesting)" >/dev/null; do sleep 30; done
if [ ! -f logs/dl_1m_h2.done ]; then
  /root/freqtrade-venv/bin/freqtrade download-data --config user_data/config_kf86_main.json --timerange 20260310-20261002 --prepend --timeframes 1m --trading-mode futures > logs/dl_1m_h2.log 2>&1 && touch logs/dl_1m_h2.done
fi
run() { # name path strat
  f=logs/val1m_$1.log
  grep -qE "^│ *$3 " $f 2>/dev/null && return
  /root/freqtrade-venv/bin/freqtrade backtesting --config user_data/config_kf86_main.json --strategy $3 --strategy-path $2 --timerange 20260315-20261006 --timeframe 5m --timeframe-detail 1m --cache none > $f 2>&1
  echo "$1 $(grep -E "^│ *$3 " $f | tail -1 | awk -F'│' '{print $3,$6,$9}')"
}
run alt_V23 user_data/strategies NFI_KF_V23_Grind3
run neu_V23 sd_new3 NFI_KF_V23_Grind3
run neu_V13 sd_new3 NFI_KF_V13
run neu_V10 sd_new3 NFI_KF_V10
echo VAL1M_ALL
