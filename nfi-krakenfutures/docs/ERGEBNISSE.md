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

## Signal 145 mit 2x statt 3x Hebel (v21, verworfen, 24.10.2026)

`NFI_KF_V21_145Lev2`: Erst-Entries mit Signal 145 mit 2x (gleiches Notional). Gewinn %/Drawdown %:

| | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| v13 | 64,1/0 | 59,2/4,3 | 52,3/12,0 | 243,7/6,2 | 1607,7/6,3 | 60,2/6,7 | 938,1/10,8 | 259,2/5,2 |
| 145 mit 2x | 64,1/0 | 59,1/4,4 | 49,3/12,0 | 235,8/6,3 | 1430,7/8,4 | 60,1/6,8 | 933,3/10,9 | 258,3/5,3 |

Drawdown inkl. offener Positionen: max 50,9 statt 51,3 %, Mittel 30,4 statt 31,1 %. Risiko (7 Fenster):
Trades < -50 %: 2 (v13: 2), < -80 %: 1 (1, JASMY Rebuy), MC-DD 95 % 19,9 (19,6), Summe Beitrag 854 (868).
Fazit: kein Risikovorteil (die Fast-Liquidationen kommen nicht aus 145), W3 -11 %, W2c -6 %. Verworfen.
`tools/risk.py` hat die Umgebungsvariable `BEFORE` (obere Grenze des Dateinamens), damit spaetere Laeufe
derselben Strategie (z. B. 400-USD-Test) die Referenz nicht ueberschreiben.

## Rebuy mit 2x statt 4x Hebel (v22, verworfen, 24.10.2026)

`NFI_KF_V22_RebuyLev2`: Erst-Entries im Rebuy-Modus (61-68) mit 2x (gleiches Notional). Normale Gebuehren,
Gewinn %/Drawdown %: W4a 246,0/6,2 (v13 243,7), W3 1634,6/6,3 (1607,7), Val 60,8/6,8 (60,2), H1 929,7/10,8
(938,1), H2 255,8/11,2 (259,2/5,2); W1, W2, W2c identisch. Risiko (7 Fenster): Trades < -50 %: 1 (2),
< -80 %: 0 (1), schlechtester -62 % (-97 %), MC-DD 95 % 20,5 (19,6), max MtM-DD 51,3 (51,3).
H2-Drawdown 11,2 % entsteht durch Platzvergabe (SUSHI-145 -1618 USD statt ICP-Rebuy -967 USD), nicht systematisch.

**Gebuehren-Stresstest (doppelte Gebuehren, `--fee 0.001`)**, Gewinn %/Drawdown %:

| | H2 | H1 |
|---|---|---|
| v13 | 244,1/5,3 | 913,9/10,9 |
| Rebuy 2x | 158,7/24,0 | 906,1/10,9 |

Wie schon bei Rebuy 3x kippt H2 bei doppelten Gebuehren (-85 Punkte Gewinn, Drawdown 24 %). Der Tail-Vorteil
(schlechtester Trade -62 % statt -97 %) ist klein, die Instabilitaet gross -> verworfen.

## Signal 120 (Grind-Modus): Verlauf der Trades (v13, `SIGNAL=120 tools/trades145.py`, 24.10.2026)

38 Trades (5 Fenster), alle im Plus (Median +8,1 %, 19,7 h, max. 72 h), nur 0,2 Nachkaeufe, aber im Median 2,1
Teilverkaeufe. Tiefster Stand: Median -4,7 %; 6 Trades unter -25 % (ZEC 16.10.25 -58 %, BTC 13.04.24 -40 %,
AVAX -38 %), alle erholten sich innerhalb von 34 h und endeten mit +2 bis +9 %. Beitrag zum Gesamtgewinn klein
(ca. 4.800 USD ueber alle Fenster), dafuer Kennzahl "kein einziger Verlierer". Grafiken: `docs/img/out120_*.png`.

## Grind-Modus (Signal 120) mit 3-fachem Einsatz (v23, schwacher Kandidat, 24.10.2026)

Ursache des kleinen Einsatzes: NFI startet im Grind-Modus mit Faktor 0,2 auf den Grundeinsatz (20 % Konto bei 5 Slots)
= 4 % Marge (Top-Signale 29,7 %, Rebuy 5 %). `NFI_KF_V23_Grind3`: Faktor 3 -> ca. 12 % Marge. Gewinn %/Drawdown %:

| | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| v13 | 64,1/0 | 59,2/4,3 | 52,3/12,0 | 243,7/6,2 | 1607,7/6,3 | 60,2/6,7 | 938,1/10,8 | 259,2/5,2 |
| Grind x3 | 64,1/0 | 59,2/4,3 | 57,2/12,0 | 257,5/6,2 | 1741,6/6,3 | 68,0/6,7 | 1015,0/10,8 | 237,7/11,2 |

Risiko: max MtM-DD 51,2 % (51,3), Trades < -50 %: 2 (2), < -80 %: 1 (1), MC-DD 95 % 20,3 (19,6), Summe Beitrag 882 (868).
H2-Rueckgang durch Platzvergabe: Am 04.06.2026 belegten groessere Grind-Positionen (AVAX, ARB) Slots, danach wurde ein
SUSHI-145-Trade eroeffnet (-1599 USD). Gebuehren-Stresstest (doppelte Gebuehren), Gewinn %/DD %:
H2 223,6/11,1 (v13 244,1/5,3), H1 990,5/10,9 (913,9/10,9) -> kein Kippen wie bei Rebuy 2x/3x.
Fazit: kleiner Vorteil (+5-8 % Gewinn in 5 von 8 Fenstern, -8 % in H2), Risiko unveraendert; nur ein Wert (x3) getestet, nicht gesucht.
Praktisch fuer ein 400-USD-Konto: Marge 12 % (ca. 48 USD) statt 4 % (ca. 16 USD) liegt eher ueber der Mindestordergroesse.

## Drawdown: Positionsgroesse global und LossGate (v24, 25.10.2026)

`NFI_KF_V24_Scale75/50` (alle Erst-Entries x0,75 bzw. x0,5), `NFI_KF_V24_LossGate2` (keine neuen Erst-Entries, solange
>= 2 offene Positionen mehr als 15 % Margenverlust haben). Gewinn %/MtM-DD %:

| | W2c | W4a | W3 | H1 | H2 | max MtM-DD | Mittel MtM-DD |
|---|---|---|---|---|---|---|---|
| v13 | 52,3/47,8 | 243,7/41,7 | 1607,7/51,3 | 938,1/50,9 | 259,2/19,4 | 51,3 | 31,1 |
| Scale75 | 45,1/40,2 | 181,5/34,7 | 1009,9/47,1 | 510,3/41,4 | 163,2/14,7 | 47,1 | 25,8 |
| Scale50 | 31,3/27,5 | 102,6/24,3 | 441,1/38,2 | 258,1/28,0 | 93,2/9,9 | 38,2 | 18,4 |
| LossGate2 | 46,6/47,8 | 195,7/42,0 | 1206,2/46,2 | 888,1/50,9 | 220,2/19,4 | 50,9 | 30,5 |

Gewinn/Drawdown (H1): v13 18,4; Scale75 12,3; Scale50 9,2 -> Verkleinern senkt den Gewinn (Zinseszins) staerker als den
Drawdown. LossGate2 laesst den Drawdown fast unveraendert (50,9) und kostet 5-25 % Gewinn. Beide verworfen als
Verbesserung; Scale ist nur ein Regler fuer wen weniger Risiko wichtiger ist als Gewinn.

## Signal 141: Verlauf der Trades (v13, `SIGNAL=141 tools/trades145.py`, 25.10.2026)

98 Trades (7 Fenster), 96 Gewinner (Median +5,3 %, 3,2 h), 2 Verlierer: ZEC 01.12.25 (-20,9 %, 84 h, 7 Nachkaeufe,
-9143 USD) und LDO 03.02.25 (-10,9 %, -2084 USD). Tiefster Stand: 60 Trades bis -10 %, 27 bis -25 %, 8 bis -50 %
(alle im Plus), 3 darunter (DOGE 12.04.24 -56 % endet +0,4 %, ZEC -72 %, LDO -65 %). Summe Gewinn 74.468 USD, groesster
Einzelverlust frisst ca. 12 % davon. Beste Trades: AXS +25 %, XMR +19 %, ONDO +25 % (ROI-Deckel ca. 25 %).
Grafiken: `docs/img/out141_*.png`.

## Zeitstopp: Trades nach X Stunden schliessen? (v13, `tools/timestop.py`, 29.10.2026)

Simulation auf den 471 Trades (7 Fenster): Wert der Position nach X h (5m-Schlusskurs, Gebuehren 0,05 % je Seite,
ohne Funding) statt des echten Ausstiegs; + = besser als heute. Summe in % vom Kontostand bei Eroeffnung
(heutiger Gesamtbeitrag 868):

| Frist | betroffene Trades | alle schliessen | nur die im Minus schliessen |
|---|---|---|---|
| 12 h | 104 | -142,6 | -128,7 |
| 24 h | 57 | -79,4 | -74,7 |
| 48 h | 27 | -30,7 | -31,6 |
| 72 h | 18 | -18,8 | -18,8 |
| 120 h | 11 | -10,0 | -10,0 |

Bei 24 h verbessern sich die 16 Verlierer (> 24 h) um 15 Punkte (-91,0 -> -75,8), aber die 41 Gewinner > 24 h verlieren
94 Punkte (+42,4 -> -52,0): Sie sind nach 24 h noch tief im Minus und erholen sich (DOGE 141 -55 % -> +2,4 %, EGLD,
INJ, WLD, FET). Es gibt keine Frist, die netto etwas bringt, auch 5 Tage nicht (alle 6 Trades > 7 Tage enden zwar
im Verlust, aber ein Stopp nach 5 Tagen waere trotzdem schlechter als halten). Verworfen.

## Zusatzsignale einschalten (v25, alle verworfen, 29.10.2026)

Idee: Slots sind meist frei (Trades median 3 h), Signale sind der Engpass. NFI-Signale, die standardmaessig aus sind:
Gewinn %/Drawdown %/Trades (v13: H2 259,2/5,2/77, W3 1607,7/6,3/125):

| | H2 | W3 |
|---|---|---|
| Signale 7-11 (`NFI_KF_V25_Exp7to11`) | -80,8/96,6/589 | nicht gelaufen |
| Signal 105 Rapid (`_Rapid105`) | 141,3/64,9/313 | -93,0/99,0/427 |
| Signal 121 BTC (`_Btc121`) | 38,1/24,4/340 | abgebrochen |

Alle loesen 4-7x mehr Trades aus, die im Median laenger laufen und oefter verlieren; die Marge ist ausgelastet,
die Top-Signale finden keinen freien Slot mehr. Die Signale sind zu Recht aus. Verworfen.

## Update-Paket v23 (Grind x3) vorbereitet (29.10.2026)

`deploy/nfi_v23_update.py`: haengt `NFI_KF_V23_Grind3` an die Strategie-Datei an, stellt `--strategy` in der
`docker-compose.yml` von `NFI_KF_V13` auf `NFI_KF_V23_Grind3`, legt Backups `*.vorv23` an, fasst `config.json` und
Datenbank nicht an. Lokal gegen einen simulierten Serverstand getestet (zweimal ausgefuehrt, Klasse nur einmal,
`_scale_for("120") = 3.0`, 141-145/Rebuy unveraendert). Noch nicht auf dem Server eingespielt.

## Anatomie der Drawdown-Tiefpunkte (`tools/troughs.py`, 29.10.2026)

An allen vier Tiefpunkten (13.04.24, 20.12.24, 03.02.25, 10.10.25; BTC 8-11 % unter 24h-Hoch) wurden alle Slots
innerhalb von 20-30 min im fallenden Markt gefuellt (je 20-48 % Marge), Konto unrealisiert -41 bis -51 %. Die
meisten dieser Positionen enden im Plus (HYPE 10.10.25 +50 %). Der Drawdown ist also "alles gleichzeitig am Anfang
des Falls gekauft", nicht schlechte Trades.

## Crash-Staffel (v26, verworfen)

Erlaubte Zahl frischer Positionen (letzte 2 h) waechst mit BTC-Abstand zum 24h-Hoch (ab 3 %, je Stufe +1).
Gewinn %, Crash-Fenster:

| | W2c | W4a | W3 | H1 | max MtM-DD |
|---|---|---|---|---|---|
| v13 | 52,3 | 243,7 | 1607,7 | 938,1 | 51,3 |
| Stufe 1,5 % | 54,0 | 202,6 | 1161,3 | 864,8 | 50,9 |
| Stufe 2 % | 52,1 | 195,5 | 1135,0 | 579,4 | 50,9 |
| Stufe 3 % | 35,0 | - | - | 701,3 | - |

Beim 10.10.25 faellt BTC in 1 h fast 11 %, die Staffel erlaubt sofort 4 Positionen; blockiert werden vor allem
spaetere Kaeufe in der Erholung (die profitabelsten). Drawdown kaum besser, W3 -28 bis -30 %. Verworfen.

## Crash-Limit tiefer (v27, nicht belastbar -> verworfen, 29.10.2026)

Im akuten Crash Erst-Entries als Limit 1,5/3/5 % unter dem vorgeschlagenen Kurs (`NFI_KF_V27_CrashDip15/30/50`).
5m-Backtest Crash-Fenster, Gewinn %/MtM-DD %: v13 W2c 52,3/47,8, W3 1607,7/51,3, H1 938,1/50,9; Dip15 75,6/42,4,
1676,8/41,7, 406,2/30,0; Dip30 68,8/41,9, 1772,7/41,7, 469,2/30,1; Dip50 60,2/41,9, 1444,8/42,2, 566,0/30,2.

**Artefakt:** Die tieferen Limits werden im 5m-Backtest in derselben Kerze gefuellt und sofort zum Eroeffnungskurs
der Kerze wieder verkauft (Dauer 0, z. B. HYPE 10.10.25 +4,3 % statt +50 % bei v13) - real unmoeglich.

**Gegenprobe mit 1m-Detail** (`tools/runcrash.sh`, nur 10.-13.10.2025, 1m-Kerzen aller 86 Coins in `data_d1`):

| 10.-13.10.25, Start 10.000 USD | nur 5m | mit 1m-Detail |
|---|---|---|
| v13 | 293,6 % | 440,9 % |
| Dip 1,5 % | 129,7 % | 331,1 % |
| Dip 3 % | 157,3 % | 334,5 % |

Mit realistischer Simulation kostet das tiefere Limit am Crash-Tag rund ein Viertel des Gewinns. Der MtM-Drawdown
(22 statt 51 %) ist bei 1m-Detail nicht sauber messbar (mtm.py nutzt 5m-Tiefs, Positionen laufen nur 1-4 min).
Verworfen. Nebenbefund: Crash-Fenster reagieren stark auf die Simulationsgenauigkeit (v13 294 vs 441 % am
selben Tag); die Crash-Gewinne im 5m-Backtest sind entsprechend unsicher.

## Grind x3 an den vier Crash-Tagen mit 1m-Detail (30.10.2026)

`tools/runcrash.sh`, je 3-4 Tage ab leerem Konto (10.000 USD), 1m-Kerzen aller 86 Coins (`data_d1`..`data_d4`).
Gewinn %/Drawdown %:

| Crash | v13 1m-Detail | Grind x3 1m-Detail | v13 nur 5m | Grind x3 nur 5m |
|---|---|---|---|---|
| 12.-16.04.2024 | -16,5/34,7 | -16,7/34,7 | -44,7/53,4 | -45,6/53,4 |
| 19.-22.12.2024 | -1,1/17,8 | -3,5/19,8 | 8,7/7,9 | 6,2/10,0 |
| 02.-05.02.2025 | 64,7/0,5 | 67,2/0,5 | 63,8/10,0 | 60,1/10,1 |
| 10.-13.10.2025 | 440,9/1,6 | 443,9/1,6 | 293,6/2,3 | 295,8/2,3 |

Grind x3 ist an Crash-Tagen praktisch neutral (-2,4 bis +3,1 Punkte), das Crash-Risiko steigt nicht. Der
Vorteil aus dem 5m-Backtest (+5-8 % in 5 von 8 Fenstern) entsteht in normalen Phasen und ist mit 1m-Detail
nicht nachgerechnet (dafuer fehlen 1m-Daten fuer ganze Fenster). Nebenbefund: Der 5m-Backtest liegt an
Crash-Tagen in beide Richtungen deutlich daneben (13.04.24: -45 % statt -17 %; 10.10.25: 294 % statt 441 %).

## Trades am Anfang im Minus (v13, `tools/underwater.py`, 30.10.2026)

471 Trades: 36 % nach der ersten 5m-Kerze im Minus, 28 % nach 1 h. Der Kurs faellt nach dem Einstieg median noch
1,8 % (25 %: > 4,4 %, 10 %: > 7,5 %). Trotzdem erstmals im Plus: sofort 354 Trades (97 % Gewinner), < 1 h 81 (95 %),
1-6 h 25 (88 %), 6-24 h 5 (60 %), > 24 h 6 (50 %, Ergebnis median -5,9 %). Rebuy startet am haeufigsten im Minus (49 %).

## Einstieg bestaetigen (v28, verworfen)

Signal eine bzw. zwei Kerzen aufschieben, nur kaufen wenn danach hoeher geschlossen (`NFI_KF_V28_Confirm1/2`).
Gewinn %/Drawdown %:

| | W3 | Val | H1 | H2 |
|---|---|---|---|---|
| v13 | 1607,7/6,3 | 60,2/6,7 | 938,1/10,8 | 259,2/5,2 |
| 1 Kerze | 275,4/52,4 | 47,4/7,5 | 80,7/24,0 | 125,8/13,2 |
| 2 Kerzen | 124,4/70,5 | 25,4/7,1 | 51,0/41,2 | 26,0/34,6 |

Die NFI-Signale treffen den Dip; wer wartet, verpasst die sofortigen Gewinner und kauft die anderen teurer.
Gewinn bricht ein, Drawdown steigt massiv. Verworfen.

## Live-Stand 30.10.2026

`NFI_KF_V23_Grind3` laeuft live seit 30.10.2026 16:15 UTC (Log: "Using resolved strategy NFI_KF_V23_Grind3").
Eingespielt mit `deploy/nfi_v23_update.py`, Backups `*.vorv23` auf dem Server. Offene Trades beim Wechsel:
WLD 145 (3x), XMR 64 (4x). SAND (v8, 4x) wurde am 29./30.10. an der Boerse liquidiert und aus der Bot-Datenbank
geloescht (freqtrade erkennt Liquidationen live nicht; Verlust nur im Kontostand, nicht in /profit).
Live-Trades 1-11 passen zum Backtest: 8 von 8 abgeschlossenen im Plus, Hebel je Signal wie vorgesehen.

## Live-Pruefung aller Trades und Logs (30.10.2026)

Trades 1-11 und 28 Orders: Hebel je Signal korrekt, Positionsgroessen wie vorgesehen (Top 30 %, 145 20 %, Grind 4 %,
Rebuy 5 % Marge), fast nur Maker-Gebuehren (0,02 %), Fuellung in Sekunden, Grind/Derisk-Ablaeufe wie vorgesehen.
Hinweise: 5 Slots x 30 % Marge > 100 % Konto (4. Top-Position bekommt nur den Rest, z. B. BNB 68 statt 124 USD);
`liquidation_price` ist bei Kraken Futures immer None (Bot kennt keine Liquidationspreise).

**Fehler im Log:** `TypeError ... NoneType * float` in NFIs `check_exit_timeout` (und gleich gebaut
`check_entry_timeout`): Kraken Futures liefert `order.price = None`, NFI rechnet `order.price * 0.97`. Folge: NFIs
Regel "Order abbrechen, wenn Kurs > 3 % weggelaufen" greift nie; der normale 10-min-Timeout funktioniert.
Fix `deploy/nfi_v23f_update.py` (Klasse `NFI_KF_V23F` = v23 + `_OrderTimeoutFixMixin`, nimmt `ft_price`),
lokal mit simuliertem Serverstand und Kraken-artigen Orders getestet. Ausserdem: Kraken-API 503/502 am 30.10.
08:04 und 09:54 (voruebergehend, freqtrade wiederholt selbst).

**Live seit 30.10.2026 16:25 UTC: `NFI_KF_V23F`** (v23 Grind x3 + Timeout-Fix), Log ohne Fehler beim Start.
Backups auf dem Server: `*.vorv23` (Stand v13) und `*.vorv23f` (Stand v23).

## Recherche NFI-GitHub/Foren (30.10.2026)

- Live-NFI v18.0.61, aktuell v18.0.181 (367 X8-Commits, v. a. neue Signal-Schutzfilter, near-liquidation de-risk PR #1464).
  Test v23 mit neuer NFI (`sd_new`, `SPATH=sd_new tools/run8.sh`): W1 59,9 (64,1), W2 59,2 (59,2), W2c 69,1 (57,2),
  W4a 249,5 (257,5), W3 1814,3 (1741,6), Val 60,5 (68,0), H1 1003,7 (1015,0), H2 236,7/7,3 (237,7/11,2). Kein klarer
  Vorteil, kein Umstieg.
- Issue #1035: NFI-Schwellen sind auf 3x ausgelegt. Issue #1038: Liquidation ist der letzte Stop. Issue #1036:
  Derisk und Grind koennen sich gegenseitig aufheben.
- **Liquidationspreis:** Der Backtest setzt ihn (freqtrade rechnet aus Krakens Margin-Stufen, 4x ca. -22 bis -24 %
  Kurs, 3x ca. -31 bis -33 %), live liefert Kraken None. NFIs Logik nahe der Liquidation wirkt also nur im Backtest.
  Fix `deploy/nfi_v23l_update.py` (`NFI_KF_V23L` = v23F + `_LiqAwareMixin`: berechnet den Preis live wie der
  Backtest, Telegram-Warnung bei < 10 % Abstand, je Trade hoechstens alle 6 h). Lokal getestet.

## 3x Hebel fuer alle (v29, verworfen)

| Gewinn %/DD % | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| v23 | 64,1/0 | 59,2/4,3 | 57,2/12,0 | 257,5/6,2 | 1741,6/6,3 | 68,0/6,7 | 1015,0/10,8 | 237,7/11,2 |
| 3x gleicher Positionswert (`Lev3Eq`) | 65,8/0 | 56,6/4,3 | 46,2/12,0 | 218,2/7,3 | 1309,0/6,4 | 57,1/7,0 | 943,0/11,7 | 280,7/10,3 |
| 3x wie NFI (`Lev3Nat`) | 41,5/0 | 47,0/3,5 | 62,8/8,9 | 192,3/0 | 1069,8/6,4 | 46,0/7,8 | 569,4/10,8 | 177,3/6,1 |

Risiko: max/Mittel MtM-DD v23 51,2/32,1 (Lauf 24.10.), Lev3Eq 50,9/30,4, Lev3Nat 45,0/26,3. Trades < -50/-80 %, Liquidationen:
v23 2/1/0, Lev3Eq 1/1/1, Lev3Nat 3/2/1. MC-DD 95 %: 20,3 / 20,4 / 17,6.
Lev3Eq: mehr Marge je Trade, weniger Kapital fuer weitere Signale, Risiko gleich. Lev3Nat: wirkt wie kleinere Positionen
(aehnlich Scale75), dazu spaeteres Derisk -> mehr tiefe Verluste. Der gemischte Hebel von v23 bleibt besser.

Neue NFI v18.0.181 mit v23, Risiko: max/Mittel MtM-DD 51,3/32,5 (alte NFI 51,2/32,1), Trades < -50/-80 % 2/1,
Liquidationen 0, MC-DD 95 % 19,8 (20,3), Summe Beitrag 886 (882) -> praktisch gleich, kein Umstieg.
Hinweis: mtm.py/risk.py nehmen je Fenster den letzten passenden Lauf ab dem Praefix; bei mehreren Laeufen derselben
Strategie (alte/neue NFI) `BEFORE` setzen bzw. Praefix eng waehlen.

**Live seit 30.10.2026 18:06 UTC: `NFI_KF_V23L`** (v23F + selbst berechneter Liquidationspreis + Telegram-Warnung).
Backups auf dem Server: `*.vorv23` (v13), `*.vorv23f` (v23), `*.vorv23l` (v23F).

## Opt-in-Funktionen der neuen NFI v18.0.181 (v31, alle verworfen, 30.10.2026)

Getestet mit v23 auf der neuen NFI (`sd_new`, Klassen in `strategies/NFI_KF_Variants_newNFI.py`). Gewinn %/DD %,
nur Fenster mit Unterschied (sonst identisch zur Basis):

| | W2c | W3 | H1 | H2 |
|---|---|---|---|---|
| v23 neue NFI (Basis) | 69,1/12,0 | 1814,3/6,3 | 1003,7/10,8 | 236,7/7,3 |
| CapGate (keine Nachkaeufe bei 4h-Kapitulation) | 66,2/13,4 | 1939,8/8,6 | 1015,9/9,8 | = |
| GrindPre (Nachkaeufe vor Derisk) | = | 1824,5/6,5 | = | 246,5/10,2 |
| InclBad (Bad-Trade-Exit fuer Restpositionen) | = | = | = | = |
| DeriskHold (kein Derisk bei intaktem Tagestrend) | 65,0/12,0 | 2053,1/5,9 | 891,7/18,8 | 239,4/7,8 |

Keine Option ist klar besser: CapGate und GrindPre greifen selten und gemischt, InclBad nie, DeriskHold wie
die eigene fruehere DeriskHold-Idee (H1-Drawdown 18,8 statt 10,8 %). Nichts davon in die alte NFI uebernommen.
Live bleibt alte NFI (v18.0.61).

Hinweis Testumgebung: freqtrade ignoriert `datadir` in der Config; fuer Spot liegt `user_data/data/kraken` als Link auf
`data_spot` (Futures-Kerzen als Spot-Ersatz, `user_data/config_spot.json`, `CFG=... tools/run8.sh`).

## NFI auf Spot (Kraken, alte NFI v18.0.61 unveraendert, 30.10.2026)

83 der 86 Coins als Spot-Paare (/USD), 5 Slots, 10.000 USD, ohne Hebel. Kraken-Futures-Kerzen als Spot-Ersatz
(Kraken-Spot-API liefert nur 720 Kerzen, Binance aus dieser Umgebung gesperrt). Gewinn %/Drawdown %:

| | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| Futures v23 (live) | 64,1/0 | 59,2/4,3 | 57,2/12,0 | 257,5/6,2 | 1741,6/6,3 | 68,0/6,7 | 1015,0/10,8 | 237,7/11,2 |
| Spot, Kraken-Gebuehr 0,25 % | 6,2/0 | 6,4/2,5 | -9,3/14,2 | 23,2/4,6 | 34,6/20,0 | 7,3/3,6 | 4,1/28,5 | 16,1/5,0 |
| Spot, Gebuehr 0,1 % | 7,3/0 | 7,1/2,4 | 3,0/5,5 | 25,6/4,0 | 83,8/7,1 | 7,8/2,2 | 27,1/13,9 | 18,4/4,5 |

Spot bringt einen Bruchteil des Futures-Gewinns (kein Hebel, Trades laufen 2-7 Tage), bei Kraken-Spot-Gebuehren in
Crash-Fenstern sogar Verlust bzw. 28,5 % Drawdown. Fuer dieses Konto kein Wechsel. Config-Vorlage ohne Schluessel:
`backtest-template-spot.json`.

## Deckel fuer langsame Signale / ohne Rebuy auf v23 (v32, verworfen, 31.10.2026)

Langsame Signale = 145, Rebuy 61-68, Quick 41-53 (live WLD 145, XMR 64, SAND 145). Gewinn %/DD %:

| | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| v23 | 64,1/0 | 59,2/4,3 | 57,2/12,0 | 257,5/6,2 | 1741,6/6,3 | 68,0/6,7 | 1015,0/10,8 | 237,7/11,2 |
| WeakCap1 (max 1 gleichzeitig) | 68,0/0 | 59,2/4,3 | 60,4/10,8 | 234,4/6,2 | 1719,9/6,3 | 56,9/6,4 | 896,0/10,8 | 304,2/5,9 |
| WeakCap2 (max 2) | 64,1/0 | 59,2/4,3 | 57,2/12,0 | 249,4/6,2 | 1659,0/6,4 | 68,0/6,7 | 979,2/10,8 | 275,0/5,1 |
| ohne Rebuy | 61,5/0 | 65,0/4,3 | 55,3/12,0 | 236,8/6,2 | 1606,0/6,3 | 75,1/0,3 | 989,8/10,8 | 265,6/10,3 |

Risiko (7 Fenster): Trades < -50 % v23 2, WeakCap1 3, WeakCap2 2, ohne Rebuy 0 (schlechtester -49 % statt -97 %);
MC-DD 95 % 20,3 / 19,0 / 19,1 / 19,3; Summe Beitrag 882 / 890 / 887 / 885; max MtM-DD ueberall ca. 51 %.
Gebuehren-Stress (0,1 %) ohne Rebuy: H2 182,3/18,9 (v23 223,6/11,1), H1 955,8/10,9 (990,5/10,9), W3 1554,4/6,3.
Ohne Rebuy kippt in H2 bei doppelten Gebuehren (Drawdown 18,9 %) wie schon frueher -> nicht robust. Verworfen.

## Fremde Freqtrade-Strategien (Freqle-Top-Liste), 1x Hebel, Kraken Futures (31.10.2026)

Quellen: E0V1E (TheoBrigitte/freqtrade, strategies/e0v1e), NotAnotherSMAOffsetStrategyHO (davidzr/freqtrade-strategies,
letzter Commit 11/2023), NASOSv4_SMA und BinClucMadSMA (remiotore/ccxt-freqtrade). Nicht im Repo (fremder Code);
fuer freqtrade 2026.8 angepasst: veraltete Namen (sell->exit, buy->enter_long, populate_buy/sell_trend,
order_time_in_force buy/sell -> entry/exit), np.NAN -> np.nan, bool-Spalten in BinClucMadSMA als 0 statt False.
Logik unveraendert. Config `backtest-template-ext.json` (price_side "other", wegen Market-Orders).

| Gewinn %/DD % | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| v23 (live, 3-4x) | 64,1/0 | 59,2/4,3 | 57,2/12,0 | 257,5/6,2 | 1741,6/6,3 | 68,0/6,7 | 1015,0/10,8 | 237,7/11,2 |
| NotAnotherSMAOffsetHO | 105,2/11,7 | 157,3/6,0 | 54,0/9,6 | 89,1/7,1 | 59,4/15,6 | 54,5/4,8 | 1094,9/7,1 | 110,7/6,9 |
| NASOSv4_SMA | 259,5/24,6 | 370,9/10,5 | 93,2/18,8 | 239,8/13,6 | 217,4/34,4 | 179,7/21,0 | 293,2/18,5 | 314,2/22,3 |
| E0V1E | 48,4/13,1 | 93,3/1,9 | 34,9/5,9 | 131,5/1,5 | 178,6/3,5 | 25,2/2,4 | 168,0/7,8 | 62,2/3,2 |
| BinClucMadSMA | 16,6/18,9 | 37,7/20,0 | 47,5/11,8 | 66,4/18,5 | 16,1/41,6 | 12,3/27,1 | 51,5/22,3 | 178,1/12,4 |

Risiko (max/Mittel MtM-DD, MC-DD 95 %, Summe Beitrag, schlechtester Trade): v23 51,2/32,1, 20,3, 882, -97 %;
NotAnotherSMA 29,2/17,2, 16,5, 674, -48 %; NASOS 46,8/26,4, 28,6, 902, -46 %; E0V1E 34,8/15,9, 10,9, 415, -37 %;
BinCluc 44,9/28,3, 31,0, 281, -37 %.

Gebuehren-Stress (0,1 %): NotAnotherSMA 89,9/141,4/50,0/80,0/45,3/52,2/908,4/95,7 (DD kaum hoeher), NASOS
202,8/315,0/81,6/185,0/160,2/140,5/188,9/192,2 -> beide stabil.

1m-Detail an Crash-Tagen (Gewinn %, 10.000 USD, mit 1m / nur 5m): NotAnotherSMA 13.04.24 -6,5/-8,3, 20.12.24 7,7/7,5,
03.02.25 -5,7/-2,3, 10.10.25 259,2/367,8; NASOS -7,9/1,1, 2,9/2,3, 12,7/10,2, 97,0/66,5 (v23: -16,7/-45,6, -3,5/6,2,
67,2/60,1, 443,9/295,8). H1 ist bei allen stark vom 10.10.2025 gepraegt.

Aufteilung des Kapitals v23 + NotAnotherSMA (zwei Konten, `tools/portfolio.py`), Gewinn %/MtM-DD %:

| v23-Anteil | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 | max DD | Mittel DD |
|---|---|---|---|---|---|---|---|---|---|---|
| 100 % | 64,1/9,6 | 59,2/14,2 | 57,2/49,1 | 257,5/41,6 | 1741,6/51,2 | 68,0/14,1 | 1015,0/50,9 | 237,7/26,5 | 51,2 | 32,1 |
| 70 % | 76,5/6,5 | 88,6/9,0 | 56,2/40,2 | 207,0/34,3 | 1236,9/48,2 | 63,9/10,5 | 1038,9/40,9 | 199,6/18,9 | 48,2 | 26,1 |
| 50 % | 84,7/10,8 | 108,2/7,5 | 55,6/34,3 | 173,3/28,0 | 900,5/45,1 | 61,3/7,9 | 1054,9/34,8 | 174,2/14,9 | 45,1 | 22,9 |
| 30 % | 92,9/15,0 | 127,9/7,5 | 54,9/28,7 | 139,6/20,0 | 564,0/40,4 | 58,6/5,8 | 1070,9/29,0 | 148,8/11,0 | 40,4 | 19,7 |
| 0 % | 105,2/23,4 | 157,3/10,5 | 54,0/23,0 | 89,1/11,2 | 59,4/29,2 | 54,5/5,9 | 1094,9/23,8 | 110,7/10,8 | 29,2 | 17,2 |

Bewertung: NotAnotherSMAOffsetHO ist der erste Kandidat, der in ungesehenen Fenstern (Val/H1/H2, nach Commit 11/2023)
mit v23 mithaelt bei etwa halbem Drawdown. Empfehlung: erst Dry-Run (Papierhandel) parallel zum Live-Bot.

## NotAnotherSMAOffset optimieren (31.10.2026)

Varianten (in der lokalen Kopie angehaengt): 2x Hebel mit auf Kursbewegung umgerechneten ROI/Stop/Trailing, Stop -20 %,
ohne Trailing-Stop, 8 statt 5 Slots. Gewinn %/DD % (Auswahl auf W1-W3, Pruefung auf Val/H1/H2):

| | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| Basis 1x | 105,2/11,7 | 157,3/6,0 | 54,0/9,6 | 89,1/7,1 | 59,4/15,6 | 54,5/4,8 | 1094,9/7,1 | 110,7/6,9 |
| 2x | 460,2/21,2 | 623,9/11,9 | 145,4/19,0 | 259,9/14,0 | 137,9/33,8 | 156,8/9,5 | 22754,0/12,9 | 402,4/13,6 |
| Stop -20 % | 97,1/16,1 | 159,7/4,1 | 50,0/12,1 | 87,5/7,9 | 122,2/8,4 | 54,0/5,1 | 970,2/11,1 | 106,3/6,3 |
| ohne Trailing | 138,8/14,1 | 169,2/7,9 | 68,2/7,7 | 99,0/7,1 | 55,5/22,3 | 55,1/7,0 | 508,0/7,2 | 137,2/7,4 |
| 8 Slots | 80,5/9,2 | 109,7/3,8 | 35,8/8,3 | 62,0/4,4 | 43,9/10,2 | 39,3/3,0 | 599,6/3,7 | 66,8/4,3 |

Risiko (max/Mittel MtM-DD, Trades < -50 %, schlechtester, MC-DD 95 %, Summe Beitrag): Basis 29,2/17,2, 0, -48 %, 16,5,
674; 2x 58,9/35,0, 7, -96 %, 30,7, 1589; Stop -20 % 36,1/18,3, 0, -29 %, 15,6, 696; ohne Trailing 39,4/20,0, 0, -48 %,
17,6, 612; 8 Slots 27,7/15,7, 0, -48 %, 10,5, 501.
Bewertung: 2x verdoppelt das Risiko (max MtM-DD 59 %, ein Trade -96 %), H1 durch den 10.10.2025 aufgeblaeht -> nein.
Stop -20 % und ohne Trailing sind Abwaegungen ohne klaren Sieger; ohne Trailing ist in 6 von 8 Fenstern besser und
haengt weniger am Trailing-Artefakt, verliert aber H1 (10.10.25). 8 Slots = nur kleinere Positionen.
Empfehlung: Basis 1x unveraendert in den Dry-Run; ohne Trailing als Vergleich beobachten.

NASMAO mit 1,5x (ROI/Stop/Trailing auf gleiche Kursbewegung, Stop -52,5 % Marge = -35 % Kurs, Liquidation erst
ca. -64 %): W1 242,2/16,6, W2 338,1/9,0, W2c 95,9/14,3, W4a 160,8/10,6, W3 94,2/25,4, Val 98,6/7,1, H1 6322,9/10,2
(10.10.25 aufgeblaeht), H2 234,9/10,2. Max/Mittel MtM-DD 45,0/25,6, Trades < -50 % 5 (Stop-Ausloesungen, keine
< -80 %), schlechtester -72 %, MC-DD 95 % 23,7, Summe Beitrag 1148 (v23: 51,2/32,1, 2, -97 %, 20,3, 882).
Kandidat fuer den Dry-Run neben 1x.

NASMAO 1,5x weiter optimiert (Gewinn %/DD %):

| | W1 | W2 | W2c | W4a | W3 | Val | H1 | H2 |
|---|---|---|---|---|---|---|---|---|
| 1,5x Basis | 242,2/16,6 | 338,1/9,0 | 95,9/14,3 | 160,8/10,6 | 94,2/25,4 | 98,6/7,1 | 6322,9/10,2 | 234,9/10,2 |
| Stop -20 % Kurs | 222,5/23,8 | 339,6/7,3 | 87,9/17,6 | 157,3/11,8 | 282,4/12,8 | 97,5/7,6 | 5062,3/16,1 | 222,8/9,6 |
| ohne Trailing | 262,1/20,8 | 336,6/11,8 | 115,8/11,5 | 177,9/10,5 | 89,5/32,3 | 92,3/10,4 | 1241,3/10,7 | 257,9/11,0 |
| Crash-Stopp BTC | 282,0/4,0 | 268,1/9,0 | 105,8/9,5 | 135,7/10,6 | 80,8/27,8 | 94,8/7,1 | 910,2/9,6 | 222,1/10,2 |
| Schutzregeln (Prot) | 237,3/11,5 | 345,4/9,0 | 100,4/9,2 | 158,7/10,6 | 85,4/27,6 | 106,6/7,1 | 366,5/25,9 | 215,9/10,2 |

Risiko (max/Mittel MtM-DD, Trades < -50 %, schlechtester, MC-DD 95 %, Summe Beitrag): Basis 45,0/25,6, 5, -72 %,
23,7, 1148; Stop -20 % 51,9/27,3, 0, -44 %, 21,9, 1201; ohne Trailing 57,6/29,4, 6, -72 %, 25,6, 913; Crash-Stopp
47,6/25,8, 5, -72 %, 24,5, 839; Prot 34,3/20,4, 5, -72 %, 24,2, 765.
Prot (Pause 12 h nach 3 Stops in 24 h, Pause bei > 15 % Konto-Drawdown in 24 h, 2 Kerzen Cooldown) senkt den
Drawdown deutlich und ist in W1-W4a/Val/H2 fast gleich; es verpasst vor allem den Rebound am 10.10.2025 (H1).

## Getrennte Coin-Listen NFI + NASMAO (31.10.2026)

Grund: Kraken Futures fuehrt je Coin nur eine Position pro Konto; zwei Bots im selben Coin stoeren sich. Regel-Aufteilung
(`docs/split_lists.json`): Liste A = 48 Coins der NFI-Top-Liste -> NFI, Liste B = 38 uebrige -> NASMAO.
Einzeln, Gewinn %/DD %: NFI(A) 47,4/0, 51,1/4,3, 63,6/9,6, 218,8/6,7, 1638,7/6,3, 59,9/0,3, 632,6/10,8, 232,1/5,1;
NASMAO 1x(B) 45,7/10,4, 118,2/6,0, 35,9/10,8, 73,2/3,5, 56,3/11,4, 37,6/4,8, 240,1/20,7, 99,6/4,6;
NASMAO 1,5x(B) 86,6/15,1, 221,4/9,0, 67,0/16,0, 131,1/5,1, 100,1/16,5, 67,9/7,1, 626,9/10,7, 198,1/6,8;
NASMAO 1,5x+Schutz(B) H1 100,3/44,5 (Schutzregeln auf Liste B nicht robust -> verworfen).

Kombination 50/50 (Gewinn % je Fenster W1..H2, max/Mittel MtM-DD):
- NFI(86) allein (heute): 64,1 / 59,2 / 57,2 / 257,5 / 1741,6 / 68,0 / 1015,0 / 237,7; 51,2 / 32,1
- NFI(A)+NASMAO 1x(B): 46,5 / 84,6 / 49,7 / 146,0 / 847,5 / 48,7 / 436,3 / 165,8; 43,9 / 20,9
- NFI(A)+NASMAO 1,5x(B): 67,0 / 136,3 / 65,3 / 175,0 / 869,4 / 63,9 / 629,8 / 215,1; 46,6 / 23,8
- zum Vergleich gleiche Coins (braucht Unterkonto) NFI(86)+NASMAO 1x(86): 84,7 / 108,2 / 55,6 / 173,3 / 900,5 / 61,3 /
  1054,9 / 174,2; 45,1 / 22,9
Fazit: Getrennte Listen funktionieren technisch, kosten aber mehr Gewinn als die Variante mit gemeinsamen Coins
(NASMAO ist auf den grossen Coins staerker). Bevorzugt: Unterkonto. NFI nur auf Liste A senkt allein schon den
Drawdown (48,9/27,0 statt 51,2/32,1), kostet aber H1 (633 statt 1015 %).
