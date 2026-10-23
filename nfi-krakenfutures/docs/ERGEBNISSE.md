# NFI Kraken Futures – Ergebnisse und Stand (22.10.2026)

Basis: NostalgiaForInfinityX8 **v18.0.61** (Commit `8a0f555` im Repo
`iterativv/NostalgiaForInfinity`), freqtrade **2026.8**, Kraken Futures, nur Long,
isolierte Marge, 5 Slots, 86 Coins, 5m. Die eigenen Varianten stehen in
`strategies/NFI_KF_Variants.py` (Klasse `NFI_KF_V13` = aktueller Stand).

## Backtest-Fenster

| Kürzel | Zeitraum | Coins | Hinweis |
|---|---|---|---|
| W1 | 24.08.2022 – 01.05.2023 | 61 (22 mit Daten) | nie zum Optimieren benutzt |
| W2 | 01.05.2023 – 01.01.2024 | 61 (26 mit Daten) | nie zum Optimieren benutzt |
| W2c | 01.01.2024 – 01.05.2024 | 61 (26 mit Daten) | Crash-Fenster 13.04.2024 |
| W4a | 01.09.2024 – 01.01.2025 | 61 (56 mit Daten) | |
| W3 | 01.10.2024 – 01.04.2025 | 86 (83 mit Daten) | Crash 03.02.2025 |
| Val | 01.04.2025 – 01.10.2025 | 83 | |
| H1 | 26.09.2025 – 15.03.2026 | 86 | Crash 10.10.2025 |
| H2 | 15.03.2026 – 06.10.2026 | 86 | |

Start 10.000 USD, 5 Slots, Gebühren der Börse (Stresstest: doppelte Gebühren).

## Versionsverlauf (Gewinn in %)

| Version | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| v6 | 17,1 | 17,2 | 12,9 | 131,9 | 434,6 | 36,6 | 290,4 | 100,3 |
| v8 | 34,8 | 36,4 | 26,2 | 246,7 | 1439,9 | 61,6 | 883,6 | 258,4 |
| v12 | 34,8 | 37,5 | 17,0 | 277,0 | 1609,9 | 61,2 | 936,7 | 267,0 |
| **v13** | 33,9 | 37,5 | 29,2 | 277,0 | 1609,9 | 60,2 | 936,7 | 264,4 |

Risiko (8 Fenster, 5.000 Monte-Carlo-Läufe über die Tradereihenfolge):

| | v8 | v12 | v13 |
|---|---|---|---|
| Monte-Carlo-Drawdown 95 %-Fall | 24,9 % | 18,5 % | 17,1 % |
| größter Einzelverlust | −15,1 % | −10,6 % | −10,6 % |
| Positionen mit > 80 % Margenverlust | 5 | 2 | 2 |
| Drawdown inkl. offener Positionen (Crash) | bis 55 % | bis 51 % | bis 51 % |

## Was die Versionen ändern

- **v6** Top-Coins-Modus ohne Meme-Coins, Grind-Modus für alle, 4x Hebel, Positionsdeckel.
- **v7+/v8** Positionsgröße je NFI-Signal (141–144 ×1,5, 145 ×0,75, Normal/Scalp/Rapid ×1,5).
- **v9** 3x statt 4x Hebel bei gleicher Positionsgröße für Käufe im akuten Crash
  (BTC in 60 min mehr als 3 % gefallen). NFI-Schwellen und ROI werden pro Trade mit
  Hebel/4 skaliert (Klasse `NFI_KF_V8_VolLev`).
- **v10** zusätzlich 3x für Signal 145 und Quick-Modus (Rebuy bleibt 4x, mit 3x
  war Rebuy bei doppelten Gebühren instabil).
- **v11/v12** Derisk Stufe 1 (v11) und Stufe 2 (v12) entfallen bei starken Signalen;
  Stufe 3 bleibt.
- **v13** Exit, wenn ein Trade nach 72 h als Gesamt-Trade wieder mindestens +0,5 % im
  Plus ist.

## Verworfene Ideen (nicht wiederholen)

FreqAI-Filter und -Notbremse, Shorts, Trailing nach ROI-Exit, Exposure-Deckel
(75 %/100 %), Kauf-Drossel (1–2 Trades/h), RebuyHalf, CapGate, DeriskHold
(mehr Gewinn, aber Drawdown inkl. offener Positionen 60 %), Quick ×1,5, GrindSlots 3,
MaxPos 30 %, 3x/3,5x Hebel für alle, volatilitätsabhängiger Hebel, Notbremse bei
−60/−70 % Margenverlust, Crash-Schwelle 2 %/2,5 %/4 % bzw. Fenster 120 min,
Meme-Coins im Top-Modus mit 3x, keine Nachkäufe bei > 50 % Margenverlust,
Top-Skala ×1,4 und ×1,6, 6 Slots, Stale-Exit 48 h/96 h/+1 %.

## Ehrliche Einschränkungen

- Alle Varianten v9–v13 wurden auf denselben Fenstern ausgewählt. Nur W1 und W2
  waren nie beteiligt, dort ist v13 ≈ v8. Belastbar ist vor allem der
  **Liquidationsschutz**, der Mehrgewinn von v12/v13 gegenüber v8 ist nicht
  unabhängig bestätigt.
- Der W2c-Vorteil von v13 hängt an einem einzigen Trade (DOT 145, 12.01.2024).
- Ohne Derisk-Stufen 1/2 bei starken Signalen kommen einzelne Positionen näher an die
  Liquidation (ZEC 141: 86 % Margenverlust).
- Ein kleines Live-Konto (ca. 400 USD) verhält sich anders als der Backtest mit
  10.000 USD (Mindestordergrößen, Füllquote, Kapital für die 3x-Marge).
- Bestehende Trades behalten ihren alten Hebel; der Schutz gilt nur für neue Trades.

## Live-Stand

- Server: `NFI_KF_V12` läuft live mit kleinem Kapital. v13 wird mit
  `deploy/nfi_v13_update.py` eingespielt.
- Beobachtungsfall: SAND 145 (eröffnet 19.10. unter v8, 4x), Derisk Stufe 1 am 22.10.
  ausgelöst, Verlauf normal. Füllquote Limit-Entries: 3 von 4 Signalen (75 %).

## Neuaufbau der Testumgebung (22./23.10.2026)

Die Cloud-Umgebung wurde zurueckgesetzt; alle Daten, Skripte und Ergebnisse gingen verloren.
Neu aufgebaut mit denselben 86 Coins fuer **alle** Fenster (die frueheren Listen mit
61/83 Coins sind nicht mehr vorhanden). Folge: W1, W2, W2c und W4a liegen jetzt hoeher als
in der Tabelle oben; W3, Val, H1 und H2 sind mit den frueheren Werten vergleichbar.

Referenz neu (Gewinn % / Drawdown %), `tools/run8.sh` + `tools/compare.py`:

| Version | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| v8 | 65,2/0 | 57,9/4,4 | 26,1/17,2 | 213,0/13,8 | 1437,8/13,9 | 61,6/6,5 | 883,5/15,1 | 253,3/5,1 |
| v13 | 64,1/0 | 59,2/4,3 | 52,3/12,0 | 243,7/6,2 | 1607,7/6,3 | 60,2/6,7 | 938,1/10,8 | 259,2/5,2 |

**Fallstrick:** Wird BTC nur teilweise geladen (z. B. durch einen Test-Download vorab,
ohne `--timerange`), ergaenzt `download-data` nur nach vorn. Dann fehlt BTC-Historie, die
Crash-Erkennung (`_wild`) greift im Backtest nie, und Crash-Kaeufe laufen mit 4x statt 3x
(Gewinn ca. 5 % zu hoch, Schutz fehlt). Kontrolle: Kaeufe vom 10.10.2025 ab 21:00 UTC
muessen `leverage 3.0` haben. Im Live-Bot ist BTC in der Whitelist und wird von Kraken
live geladen; ob der 3x-Hebel greift, steht in der Datenbank-Spalte `leverage`.
