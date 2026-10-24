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

## Signal-Auswertung v13 (471 Trades, 7 Fenster ohne W4a, 23.10.2026)

`tools/signals.py`. Top-Coins-Signale 141-145 = 73 % der Trades und 81 % des Gewinns.
142: 23 % der Trades, 33 % des Gewinns (97 % Gewinner); 141: 21 % / 25 %; 145: 20 % der Trades,
9 % des Gewinns, 11 von 22 Verlierern (88 % Gewinner, Gewinn/Verlust 3,0); 143/144 selten, aber
sehr gut (Gewinn/Verlust ca. 70). Rebuy (61-68): 10 % der Trades, 1 % des Gewinns, enthaelt
JASMY -97 %, LPT -64 %, ICP -48 %. Grind (120): 38/38 Gewinner, ca. 20 h Dauer, wenig Ertrag.
Normal (1-13): nur 19 Trades, 100 % Gewinner. Signale mit < 10 Trades sind nicht aussagekraeftig.

### Test: Signale nicht mehr handeln (Erst-Entries blockiert, Nachkaeufe bleiben)

| Gewinn %/DD % | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| v13 | 64,1/0 | 59,2/4,3 | 52,3/12,0 | 243,7/6,2 | 1607,7/6,3 | 60,2/6,7 | 938,1/10,8 | 259,2/5,2 |
| ohne 145 | 66,7/0 | 59,1/0 | 59,2/10,8 | 203,7/6,5 | 1579,4/6,6 | 43,2/6,4 | 755,9/10,6 | 224,5/6,1 |
| ohne Rebuy | 61,5/0 | 65,0/4,3 | 50,5/12,0 | 223,4/6,2 | 1468,8/6,3 | 67,1/0,3 | 916,6/10,8 | 241,1/11,2 |
| ohne beides | 64,1/0 | 64,9/0 | 57,3/10,8 | 185,5/6,5 | 1459,6/6,6 | 49,2/0 | 741,9/10,6 | 232,9/0 |

Risiko (7 Fenster, `tools/risk.py`):

| | Trades | < -50 % | < -80 % | schlechtester | MC-DD med / 95 % | Summe Beitrag |
|---|---|---|---|---|---|---|
| v8 | 478 | 5 | 1 | -97 % | 20,0 / 29,6 | 832 |
| v13 | 471 | 2 | 1 | -97 % | 13,4 / 19,6 | 868 |
| ohne 145 | 398 | 2 | 1 | -97 % | 10,9 / 17,4 | 833 |
| ohne Rebuy | 427 | 0 | 0 | -49 % | 13,4 / 20,0 | 854 |
| ohne beides | 352 | 0 | 0 | -49 % | 10,9 / 15,7 | 832 |

Ergebnis: Signal 145 weglassen kostet 13-28 % Gewinn in mehreren Fenstern, entschaerft den
Tail nicht (JASMY bleibt) -> verworfen. Rebuy weglassen entfernt alle Trades mit > 50 %
Margenverlust bei ca. -1,6 % Gesamtbeitrag, aber gemischte Fenster (W3 -9 %, W4a -8 %, H2 -7 %
bei DD 11,2 statt 5,2 %; Val +11 %, W2 +10 %) und keine Verbesserung der Monte-Carlo-Werte.

## Coin-Blacklist (verworfen) und Drawdown-Tests (23.10.2026)

**Blacklist JASMY, JUP, LDO, OP, ENS, LPT, ICP** (`NFI_KF_V17_NoWeak7`): im Backtest in jedem Fenster
gleich oder besser (W3 1607 -> 2111 %, W4a 244 -> 309 %), aber die 7 Coins wurden aus denselben 26
Trades ausgewaehlt. Geteilter Test (Auswahl in der einen Haelfte der Fenster, Pruefung in der anderen):
Beitrag der im Training schlechten Coins im Test -2,8 bzw. +6,8 Punkte -> kein stabiles Signal, nicht einspielen.

**Drawdown inkl. offener Positionen** (`tools/mtm.py`, 5m-Tiefstkurse; Mark-to-Market) und Gewinn %:

| | max MtM-DD | W2c | W3 | H1 | Gewinn W3 | Gewinn H1 |
|---|---|---|---|---|---|---|
| v8 | 55,5 | 55,5 | 55,3 | 52,0 | 1437,8 | 883,4 |
| v13 | 51,3 | 47,8 | 51,3 | 50,9 | 1607,7 | 938,1 |
| CrashHalf (halbe Positionen im Crash) | 53,0 | 45,4 | 53,0 | 28,8 | 1549,7 | 610,5 |
| CrashStop (kein Kauf im Crash) | 47,0 | 42,4 | 47,0 | 29,9 | 1386,8 | 341,0 |
| Slow5Half (+ BTC -5 % in 24 h) | 45,4 | 45,4 | 39,0 | 28,0 | 1154,5 | 360,5 |

Ergebnis: Der Drawdown sinkt nur um 4-6 Punkte, kostet aber 14-64 % Gewinn (H1 938 -> 341-610 %).
Die Crash-Einstiege sind gerade die profitabelsten Trades -> verworfen.

**Fallstrick mtm.py:** pandas 3 erzeugt `date_range` mit Einheit `us`; `asi8 // 10**6` liefert dann
Sekunden statt Millisekunden, die offenen Positionen fehlen und der Drawdown sieht aus wie der
realisierte (12 %). Mit `as_unit("ms")` reproduziert das Skript die frueheren Werte (v8 55 %, v13 51 %).

## Positionsgroesse nach Kontostand (v19, verworfen, 23.10.2026)

Neue Erst-Entries nur mit halber Marge, wenn das Konto inkl. offener Positionen mehr als 8 % bzw. 15 %
unter seinem Hoechststand liegt (`_EquityDDStakeMixin`, `NFI_KF_V19_EqDD08` / `EqDD15`).

| Gewinn %/MtM-DD % | W2c | W4a | W3 | H1 | max MtM-DD | Mittel MtM-DD |
|---|---|---|---|---|---|---|
| v13 | 52,3/47,8 | 243,7/41,7 | 1607,7/51,3 | 938,1/50,9 | 51,3 | 31,1 |
| EqDD15 | 52,3/47,8 | 243,7/41,7 | 1522,7/51,0 | 852,9/39,5 | 51,0 | 29,7 |
| EqDD08 | 41,8/47,8 | 219,4/40,7 | 1413,9/46,3 | 735,6/39,5 | 47,8 | 28,6 |

Der Drawdown entsteht durch die beim Crash schon offenen Positionen; kleinere Folgekaeufe kommen zu
spaet und kosten 5-24 % Gewinn in den Crash-Fenstern. Verworfen.

## Stand der Optimierung (23.10.2026, Autopilot beendet)

Gewinn-/Risikohebel auf Basis v13 sind ausgereizt: Hebel, Slots, Positionsgroessen, Crash-Regeln,
Signal- und Coin-Filter, Kontostand-abhaengige Groesse (siehe oben) bringen entweder weniger Gewinn
bei kaum weniger Drawdown oder nur In-Sample-Gewinn. Der Drawdown inkl. offener Positionen (~50 %
an Crash-Tagen) ist strukturell (5 gleichzeitig offene Positionen). Ungetestet blieben nur Eingriffe
in bestehende Positionen (Teilverkauf bei Crash), die der verworfenen Notbremse/DeriskHold aehneln.
Empfehlung: v13 live beobachten (Spalte `leverage` der neuen Crash-/145-/Quick-Trades = 3.0).

## Crash-Trim (v20, verworfen, 24.10.2026)

Bei akutem BTC-Crash (> 3 % in 60 min) wird jede offene Position mit > 10 % Margenverlust einmalig um
30 % (`NFI_KF_V20_Trim30`) bzw. 50 % (`Trim50`) verkleinert. Nur Crash-Fenster getestet (Gewinn %/MtM-DD %):

| | W2c | W4a | W3 | H1 |
|---|---|---|---|---|
| v13 | 52,3/47,8 | 243,7/41,7 | 1607,7/51,3 | 938,1/50,9 |
| Trim30 | 38,1/55,9 | 209,4/41,9 | 1144,2/53,0 | 910,9/51,6 |
| Trim50 | 48,1/42,0 | 209,0/41,9 | 978,6/52,2 | 763,7/44,8 |

Weniger Gewinn bei gleichem oder hoeherem Drawdown (Verluste werden realisiert, die Erholung fehlt,
der normale Drawdown steigt auf 14-22 %). Verworfen; restliche Fenster nicht mehr gelaufen.
Damit sind alle Ideen zur Drawdown-Senkung ausgereizt.

## Kleinkonto-Test: v13 mit 400 statt 10.000 USD (24.10.2026)

`EXTRA="--dry-run-wallet 400" tools/run8.sh s400 NFI_KF_V13`, Gewinn %/Drawdown %/Trades:

| | H2 | H1 | Val |
|---|---|---|---|
| 10.000 USD | 259,2/5,2/77 | 938,1/10,8/105 | 60,2/6,7/50 |
| 400 USD | 305,4/5,4/76 | 968,1/10,7/104 | 62,7/6,4/50 |

Keine Signale scheitern an Mindestordergroessen oder Marge (fast gleiche Tradezahl, keine
Warnungen im Log). Der leicht hoehere Gewinn kommt aus Rundungen kleiner Ordergroessen, kein Vorteil.
Nicht abgedeckt: Fuellquote der Limit-Orders und Slippage (live bisher 3 von 4 Signalen gefuellt).

## Robustheit v13 gegen v8 (24.10.2026, aus den Referenzlaeufen, ohne neue Backtests)

Gewinn v13 besser als v8 in 6 von 8 Fenstern (W2, W2c, W4a, W3, H1, H2), schlechter in W1 (-1,1) und Val
(-1,4); Drawdown inkl. offener Positionen niedriger oder gleich in allen 8 Fenstern. In den nie zum Tuning
benutzten Fenstern W1/W2 ist v13 neutral (-1,1 / +1,3 Punkte): Der belastbare Vorteil ist der
Liquidationsschutz in den Crash-Fenstern, nicht der Mehrgewinn. Weitere geteilte Tests sind ohne neue,
unabhaengige Kursdaten nicht moeglich (alle Fenster wurden schon zum Auswaehlen benutzt). Mit
Autopilot-Ende: Empfehlung weiterhin v13 live beobachten.

## Signal 145: Verlauf der einzelnen Trades (v13, `tools/trades145.py`, 24.10.2026)

95 Trades (7 Fenster, alle 3x). 84 Gewinner (Median +6,4 %, 4,8 h), 11 Verlierer (Median -23 %, 132 h, im Mittel
4,3 Nachkaeufe und 5,1 Teilverkaeufe). Tiefster Stand auf Marge: bis -10 % 60 Trades, alle im Plus; -10 bis -25 %
19 Trades, alle im Plus (Median 13,5 h); -25 bis -50 % 15 Trades, nur 5 im Plus. Faustregel: Wer in den ersten
Stunden nicht unter ca. -25 % faellt, endet immer im Plus; wer darunter faellt, braucht Tage und endet meist im
Minus. 7 von 11 Verlierern sind Grind-Faelle mit 3-9 Nachkaeufen (ENS, JUP x2, SUSHI, LDO, NEAR, BCH), ein
Trade (JASMY) scheitert in 3 h am Stop-Loss, FET/HYPE/ZEC enden fast bei null. Grafiken: `docs/img/out145_*.png`.
