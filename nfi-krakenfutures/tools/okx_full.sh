#!/bin/bash
cd /root/ft_workdir
while pgrep -f "[d]ownload-data" >/dev/null; do sleep 30; done
rm -rf data_okx_snap && cp -r data_okx data_okx_snap
S="NASS_Roi15 NASO_StopFix20Prot NASO_StopFix12Prot NASO_StopFixProt"
for grp in "w1 w2 w2c w4a" "w3 val h1 h2"; do
  for w in $grp; do CFG=user_data/config_okx_spot.json SPATH=sd_ext WINS=$w EXTRA="--fee 0.001 --enable-protections --datadir /root/ft_workdir/data_okx_snap" bash tools/run8.sh okf $S > logs/okf_$w.out 2>&1 & done; wait
done
echo OKX_FULL_DONE
