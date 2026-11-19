#!/bin/bash
cd /root/ft_workdir
R() { CFG=user_data/config_ext.json SPATH=sd_ext WINS=$1 EXTRA="--enable-protections" bash tools/run8.sh $2 "${@:3}" > logs/${2}_$1.out 2>&1; }
S2="NASMAO_Lev2 KF2_StopFixProt KF2_Ewo2Max1 KF2_Ewo2Max2"
R w2 k2b KF2_Ewo2Max2 & R w3 k2b $S2 & R val k2b $S2 & R h1 k2b $S2 & wait
R h2 k2b $S2 &
S3="KF_E2M2 KF15_StopFix KF15_E2M2 KF2_StopFix KF2_E2M2"
R w1 k3 $S3 & R w2 k3 $S3 & R w2c k3 $S3 & wait
R w4a k3 $S3 & R w3 k3 $S3 & R val k3 $S3 & R h1 k3 $S3 & wait
R h2 k3 $S3
echo K3_ALL
tools/kf_crash.sh kc NotAnotherSMAOffsetStrategyHO KF_StopFix KF_StopFixProt KF_Ewo2Max2 KF_E2M2 NASMAO_Lev15 KF15_StopFix KF15_StopFixProt KF15_Ewo2Max2 KF15_E2M2 NASMAO_Lev2 KF2_StopFix KF2_E2M2 KF2_Ewo2Max2
