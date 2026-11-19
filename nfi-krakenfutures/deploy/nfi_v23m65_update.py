#!/usr/bin/env python3
"""Update v23M -> v23M65: NFI-Einstiegssignal 65 abschalten.

Befund (8 Backtest-Fenster, 552 Trades): Signal 65 hat nur 6 Einstiege, verursacht aber die zwei
groessten Verluste (H1 Stop -97 %, H2 -48 %). Ohne Signal 65: H1 +31, H2 +31 Prozentpunkte Gewinn,
H2-Drawdown etwas niedriger, w3 -11, w4a/w2c/val unveraendert.

Ausfuehren im Ordner ~/nfi-krakenfutures-live:
    python3 ~/nfi_v23m65_update.py

- Backups: NFI_KF_Variants.py.vorv23m65 und docker-compose.yml.vorv23m65
- haengt die Klasse NFI_KF_V23M65 (= v23M ohne Signal 65) an, nur falls noch nicht vorhanden
- stellt --strategy NFI_KF_V23M auf NFI_KF_V23M65 um
config.json und Datenbank werden NICHT angefasst. Offene Trades bleiben unveraendert.
"""
import json
import shutil
import sys
from pathlib import Path

STRAT = Path("user_data/strategies/NFI_KF_Variants.py")
COMPOSE = Path("docker-compose.yml")
CONFIG = Path("user_data/config.json")

ADDON = '''

# ============================================================================
# v23M65 = v23M ohne Einstiegssignal 65 (nur 6 Einstiege in 8 Fenstern, aber die zwei groessten Verluste).
# ============================================================================
class NFI_KF_V23M65(NFI_KF_V23M):
    long_entry_signal_params = {
        **NFI_KF_V23M.long_entry_signal_params,
        "long_entry_condition_65_enable": False,
    }
'''


def fail(msg):
    print("FEHLER: " + msg)
    print("Es wurde nichts veraendert. Bitte die Ausgabe an Claude schicken.")
    sys.exit(1)


def main():
    if not STRAT.is_file() or not COMPOSE.is_file():
        fail("Bitte im Ordner ~/nfi-krakenfutures-live ausfuehren (cd ~/nfi-krakenfutures-live).")
    code = STRAT.read_text()
    compose = COMPOSE.read_text()
    if "class NFI_KF_V23M(" not in code:
        fail("In NFI_KF_Variants.py fehlt NFI_KF_V23M - ist v23M eingespielt?")
    if "--strategy NFI_KF_V23M" not in compose:
        fail("docker-compose.yml enthaelt nicht --strategy NFI_KF_V23M.")
    try:
        cfg = json.loads(CONFIG.read_text())
        if "long_entry_signal_params" in cfg:
            fail("config.json enthaelt eigene long_entry_signal_params; die wuerden die Abschaltung ueberschreiben.")
    except FileNotFoundError:
        pass
    already = "class NFI_KF_V23M65(" in code

    for path in (STRAT, COMPOSE):
        backup = Path(str(path) + ".vorv23m65")
        if backup.exists():
            print("Backup existiert schon, bleibt unveraendert: " + str(backup))
        else:
            shutil.copy2(path, backup)
            print("Backup angelegt: " + str(backup))

    if already:
        print("NFI_KF_V23M65 ist schon in der Strategie-Datei - nichts angehaengt.")
    else:
        new_code = code + ADDON
        compile(new_code, str(STRAT), "exec")
        STRAT.write_text(new_code)
        print("v23M65-Klasse an NFI_KF_Variants.py angehaengt.")

    COMPOSE.write_text(compose.replace("--strategy NFI_KF_V23M65", "--strategy NFI_KF_V23M")
                       .replace("--strategy NFI_KF_V23M", "--strategy NFI_KF_V23M65"))
    for line in COMPOSE.read_text().splitlines():
        if "--strategy" in line:
            print("docker-compose.yml:" + line)
    print("FERTIG. Jetzt: docker compose up -d")
    print("Rueckweg: cp user_data/strategies/NFI_KF_Variants.py.vorv23m65 user_data/strategies/NFI_KF_Variants.py "
          "&& cp docker-compose.yml.vorv23m65 docker-compose.yml && docker compose up -d")


main()
