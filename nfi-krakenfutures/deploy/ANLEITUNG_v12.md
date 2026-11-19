# Live-Update v12: Liquidationsschutz + Derisk-Verbesserung

Neue Strategie: `NFI_KF_V12` (ersetzt v8, v9, v10 oder v11 – Zwischenversionen
muessen vorher NICHT eingespielt sein)

Aenderungen gegenueber v8 (`NFI_KF_V8_Clean15`):
1. Liquidationsschutz: 3x statt 4x Hebel bei GLEICHER Positionsgroesse (ein
   Drittel mehr Marge) fuer
   - Kaeufe waehrend eines akuten Crashs (BTC in 60 min mehr als 3 % gefallen),
   - Signal 145 (schwaechstes Top-Signal),
   - Quick-Modus (Signale 41-46).
   Diese Positionen werden erst bei ca. -31 % statt ca. -23 % Kursbewegung
   liquidiert. Rebuy-Modus bleibt bei 4x.
2. Derisk Stufen 1 und 2 (Teilverkaeufe ab ca. -9 % / -13,5 % Kurs) entfallen bei
   starken Signalen (141-144, Normal-, Scalp-, Rapid-Modus); diese Teilverkaeufe
   fielen meist genau auf das Kurstief. Stufe 3 (ab ca. -15 %) bleibt als
   Crash-Schutz, fuer alle anderen Signale bleibt alles wie in v8.
- NFIs Derisk-, Nachkauf- und ROI-Schwellen werden fuer 3x-Trades umgerechnet.
- config.json bleibt UNVERAENDERT.

Backtest, 8 Zeitfenster (Gewinn):
| Fenster | v8 (live) | v11 | v12 |
|---|---|---|---|
| W2 | 36,4 % | 37,5 % | 37,5 % |
| W2c (Crash) | 26,2 % | 17,0 % | 17,0 % |
| W4a | 247 % | 263 % | 277 % |
| W3 | 1440 % | 1391 % | 1610 % |
| H1 | 884 % | 895 % | 937 % |
| H2 | 258 % | 267 % | 267 % |
| W1, Val | gleich | gleich | gleich |

- Positionen mit mehr als 80 % Margenverlust: v8 5, v12 2 (JASMY 87 %, ZEC 86 %).
- Monte-Carlo-Drawdown (95 %-Fall): v8 24,9 %, v12 18,5 %; groesster Einzelverlust
  v8 -15,1 %, v12 -10,6 %.
- Drawdown inkl. offener Positionen (Crash-Momente): v8 bis 55 %, v12 bis 51 %.
- Doppelte Gebuehren: H1 913 %, H2 252 %.

## Vorab-Check (BTC muss in der Coin-Liste sein)

```bash
cd ~/nfi-krakenfutures-live
grep -c '"BTC/USD:USD"' user_data/config.json
```
Erwartet: `1` (oder groesser). Bei `0` NICHT updaten und Bescheid geben.

## Schritte auf dem Server (Befehle EINZELN eingeben)

```bash
cd ~
mkdir -p nfi_update_v12
tar xzf nfi_kf_deploy_v12.tar.gz -C nfi_update_v12
cd ~/nfi-krakenfutures-live
docker compose down
cp user_data/strategies/NFI_KF_Variants.py user_data/strategies/NFI_KF_Variants.py.vorv12
cp docker-compose.yml docker-compose.yml.vorv12
cp ../nfi_update_v12/user_data/strategies/NFI_KF_Variants.py user_data/strategies/NFI_KF_Variants.py
cp ../nfi_update_v12/docker-compose.yml docker-compose.yml
grep "strategy" docker-compose.yml
```
Erwartet: `--strategy NFI_KF_V12`

```bash
docker compose up -d
```
1-2 Minuten warten, dann:
```bash
docker compose logs freqtrade-krakenfutures | grep -iE "Strategy:|error|traceback"
```
Erwartet: Zeile mit `NFI_KF_V12`, keine error/traceback.
Nach ca. 5 Minuten: `docker compose logs freqtrade-krakenfutures | grep -i heartbeat | tail -2`

Offene Trades bleiben erhalten (Datenbank unveraendert).

## Rueckgaengig machen (zurueck auf die vorige Version)

```bash
docker compose down
cp user_data/strategies/NFI_KF_Variants.py.vorv12 user_data/strategies/NFI_KF_Variants.py
cp docker-compose.yml.vorv12 docker-compose.yml
docker compose up -d
```
